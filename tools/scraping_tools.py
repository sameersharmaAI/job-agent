# ==============================================================================
# FILE: tools/scraping_tools.py
# PURPOSE: Scrape LinkedIn jobs (Firefox on ARM64), persist to a daily CSV, return JSON.
# ==============================================================================

from crewai.tools import BaseTool
from pydantic import BaseModel, Field
from typing import ClassVar, List, Optional, Type

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup

from tools.browser_tools import get_webdriver
from config import APP_CONFIG

import os
import csv
import json
import time
import hashlib
import re
from datetime import date
from urllib.parse import urlparse, quote_plus


# ----------------------------
# Tool input schema (CrewAI will render this to the model)
# ----------------------------
class LinkedInSearchArgs(BaseModel):
    keywords: str = Field(..., description="Comma-separated job keywords, e.g. 'Data Scientist, ML Engineer'")
    location: Optional[str] = Field(
        None,
        description="Job location, e.g. 'Ontario, Canada'. Defaults to env DEFAULT_JOB_LOCATION if omitted."
    )


class ScrapeLinkedInTool(BaseTool):
    """
    Scrape LinkedIn first page for given keywords/location.
    - Filters by experience levels & posted-window from env (APP_CONFIG).
    - Appends new rows to data/jobs_YYYY-MM-DD.csv (dedup by job_id).
    - Returns JSON with only the newly appended rows (full CSV schema).
    """
    name: str = "Scrape LinkedIn for jobs"
    description: str = (
        "Scrape LinkedIn for job postings with the given keywords and optional location. "
        "Uses env filters (experience levels, posted window). Persists to today's CSV and "
        "returns JSON {ok, csv_path, appended, jobs:[...]} (full-schema rows, new only)."
    )

    # structured tool args
    args_schema: Type[BaseModel] = LinkedInSearchArgs

    # CSV schema (Pydantic v2-safe as ClassVar)
    CSV_FIELDS: ClassVar[List[str]] = [
        "job_id",
        "date_scraped",
        "title",
        "company",
        "location",
        "link",
        "source",
        "raw_description",
        "keywords_matched",
        # workflow tracking
        "resume_customized",
        "ats_score_checked",
        "ats_score",
        "approved_for_application",
        "application_submitted",
        "resume_id_used",
        "date_applied",
        # optional enrichment
        "seniority_level",
        "employment_type",
        "salary_range",
        "skills_extracted",
    ]

    # ----------------------------
    # Helpers
    # ----------------------------
    def _daily_csv_path(self) -> str:
        data_dir = os.path.join(APP_CONFIG.PROJECT_BASE_DIR, "data")
        os.makedirs(data_dir, exist_ok=True)
        return os.path.join(data_dir, f"jobs_{date.today().isoformat()}.csv")

    def _ensure_csv(self, path: str) -> None:
        if not os.path.exists(path):
            with open(path, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=self.CSV_FIELDS)
                writer.writeheader()

    def _load_existing_ids(self, path: str) -> set:
        ids = set()
        if os.path.exists(path):
            with open(path, "r", newline="", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    jid = row.get("job_id")
                    if jid:
                        ids.add(jid)
        return ids

    def _normalize_link(self, link: str) -> str:
        try:
            u = urlparse(link)
            return f"{u.scheme}://{u.netloc}{u.path}".rstrip("/")
        except Exception:
            return link.strip().rstrip("/")

    def _job_id(self, title: str, company: str, location: str, link: str) -> str:
        base = f"{title.lower()}|{company.lower()}|{location.lower()}|{self._normalize_link(link).lower()}"
        return hashlib.sha1(base.encode("utf-8")).hexdigest()

    # ----------------------------
    # Main run (Firefox via get_webdriver)
    # ----------------------------
    def _run(self, keywords: str, location: Optional[str] = None) -> str:
        """
        JSON return format:
        {
          "ok": true,
          "csv_path": "<.../data/jobs_YYYY-MM-DD.csv>",
          "appended": <int>,
          "jobs": [ {<full CSV-schema row>}, ... ]   # only new rows
        }
        """
        driver = get_webdriver()
        if not driver:
            return json.dumps({"ok": False, "error": "WebDriver not available."})

        # ---- Build LinkedIn URL from env-driven filters ----
        exp_map = {
            "internship": "1",
            "entry_level": "2",
            "associate": "3",
            "mid_senior": "4",
            "director": "5",
            "executive": "6",
        }
        desired_levels = []
        for lvl in [s.strip().lower() for s in APP_CONFIG.DESIRED_EXPERIENCE_LEVELS.split(",") if s.strip()]:
            if lvl in exp_map:
                desired_levels.append(exp_map[lvl])
        # default to internship+entry+associate if none valid
        f_E = "%2C".join(desired_levels) if desired_levels else "1%2C2%2C3"

        f_TPR = ""
        if getattr(APP_CONFIG, "POSTED_WITHIN_DAYS", 0) and APP_CONFIG.POSTED_WITHIN_DAYS > 0:
            seconds = APP_CONFIG.POSTED_WITHIN_DAYS * 24 * 60 * 60
            f_TPR = f"&f_TPR=r{seconds}"

        loc = (location or APP_CONFIG.DEFAULT_JOB_LOCATION or "Canada").strip()
        kw = quote_plus(keywords)
        loc_q = quote_plus(loc)

        search_url = f"https://www.linkedin.com/jobs/search/?keywords={kw}&location={loc_q}&f_E={f_E}{f_TPR}"
        print(f"[LinkedIn] GET {search_url}")

        csv_path = self._daily_csv_path()
        self._ensure_csv(csv_path)
        existing_ids = self._load_existing_ids(csv_path)

        try:
            driver.get(search_url)
            # give time for LinkedIn to render the job results (headless)
            time.sleep(3)

            # (optional) handle cookie/consent here if needed

            WebDriverWait(driver, 15).until(
                EC.presence_of_element_located((By.CLASS_NAME, "jobs-search__results-list"))
            )

            soup = BeautifulSoup(driver.page_source, "lxml")
            cards = soup.find_all("div", class_="base-card")

            today_str = date.today().isoformat()
            to_append, to_return = [], []

            # title heuristics (belt & suspenders)
            intern_re = re.compile(r"\b(intern|internship|co[-\s]?op|coop|new\s*grad)\b", re.I)
            entry_re  = re.compile(r"\b(entry[-\s]?level|junior|graduate)\b", re.I)
            assoc_re  = re.compile(r"\b(associate)\b", re.I)
            exclude_re= re.compile(r"\b(senior|sr\.?|lead|principal|staff|director|vp|head|chief|architect)\b", re.I)

            for c in cards:
                title_elem = c.find("h3", class_="base-search-card__title")
                company_elem = c.find("h4", class_="base-search-card__subtitle")
                location_elem = c.find("span", class_="job-search-card__location")
                link_elem = c.find("a", class_="base-card__full-link")
                if not all([title_elem, company_elem, location_elem, link_elem]):
                    continue

                title = title_elem.text.strip()
                company = company_elem.text.strip()
                loc_txt = location_elem.text.strip()
                link = (link_elem.get("href") or "").strip()

                # safety filter
                t = title.lower()
                if exclude_re.search(t):
                    continue

                if intern_re.search(t):
                    seniority = "Internship"
                elif entry_re.search(t):
                    seniority = "Entry"
                elif assoc_re.search(t):
                    seniority = "Associate"
                else:
                    # If title unclear, trust f_E filter and default to Associate
                    seniority = "Associate"

                jid = self._job_id(title, company, loc_txt, link)
                if jid in existing_ids:
                    continue

                row = {
                    "job_id": jid,
                    "date_scraped": today_str,
                    "title": title,
                    "company": company,
                    "location": loc_txt,
                    "link": link,
                    "source": "LinkedIn",
                    "raw_description": "",
                    "keywords_matched": keywords,
                    # workflow defaults
                    "resume_customized": "no",
                    "ats_score_checked": "no",
                    "ats_score": "",
                    "approved_for_application": "no",
                    "application_submitted": "no",
                    "resume_id_used": "",
                    "date_applied": "",
                    # enrichment placeholders
                    "seniority_level": seniority,
                    "employment_type": "",
                    "salary_range": "",
                    "skills_extracted": "",
                }

                to_append.append(row)
                to_return.append(row)

            if to_append:
                with open(csv_path, "a", newline="", encoding="utf-8") as f:
                    writer = csv.DictWriter(f, fieldnames=self.CSV_FIELDS)
                    for r in to_append:
                        writer.writerow(r)

            print(f"[LinkedIn] levels={APP_CONFIG.DESIRED_EXPERIENCE_LEVELS}, posted_within={getattr(APP_CONFIG,'POSTED_WITHIN_DAYS',0)}d — appended {len(to_append)} → {csv_path}")

            return json.dumps({
                "ok": True,
                "csv_path": csv_path,
                "appended": len(to_append),
                "jobs": to_return
            }, ensure_ascii=False)

        except Exception as e:
            return json.dumps({"ok": False, "error": f"LinkedIn scrape error: {e}"})
        finally:
            try:
                driver.quit()
            except Exception:
                pass

    def _arun(self, *args, **kwargs):
        raise NotImplementedError("This tool does not support async")
