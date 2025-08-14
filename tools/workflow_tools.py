# ==============================================================================
# FILE: tools/workflow_tools.py
# PURPOSE: Update workflow/status fields for a job in the daily CSV by job_id.
# ==============================================================================

from crewai.tools import BaseTool
from config import APP_CONFIG

import os
import csv
import json
import glob
import tempfile
from datetime import date as _date

# Keep schema consistent with scraper
try:
    from tools.scraping_tools import ScrapeLinkedInTool
    CSV_FIELDS = ScrapeLinkedInTool.CSV_FIELDS
except Exception:
    CSV_FIELDS = [
        "job_id","date_scraped","title","company","location","link","source",
        "raw_description","keywords_matched",
        "resume_customized","ats_score_checked","ats_score","approved_for_application",
        "application_submitted","resume_id_used","date_applied",
        "seniority_level","employment_type","salary_range","skills_extracted"
    ]

UPDATABLE_FIELDS = set(CSV_FIELDS) - {"job_id","date_scraped","title","company","location","link","source"}

def _bool_to_yesno(v):
    if isinstance(v, bool):
        return "yes" if v else "no"
    if isinstance(v, str):
        low = v.strip().lower()
        if low in {"yes","no"}: return low
        if low in {"true","y","1"}: return "yes"
        if low in {"false","n","0"}: return "no"
    return v

def _data_dir():
    p = os.path.join(APP_CONFIG.PROJECT_BASE_DIR, "data")
    os.makedirs(p, exist_ok=True)
    return p

def _csv_for_date(date_str: str):
    return os.path.join(_data_dir(), f"jobs_{date_str}.csv")

def _today_csv():
    return _csv_for_date(_date.today().isoformat())

def _latest_csv():
    files = sorted(glob.glob(os.path.join(_data_dir(), "jobs_*.csv")))
    return files[-1] if files else None

def _read_all(path: str):
    rows = []
    if not os.path.exists(path): return rows
    with open(path, "r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for r in reader:
            rows.append(r)
    return rows

def _write_all_atomic(path: str, rows):
    dir_ = os.path.dirname(path)
    os.makedirs(dir_, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", dir=dir_, delete=False, newline="", encoding="utf-8") as tmp:
        writer = csv.DictWriter(tmp, fieldnames=CSV_FIELDS)
        writer.writeheader()
        for r in rows:
            for k in CSV_FIELDS:
                r.setdefault(k, "")
            writer.writerow({k: r.get(k, "") for k in CSV_FIELDS})
        tmp_path = tmp.name
    os.replace(tmp_path, path)

class UpdateJobsCsvTool(BaseTool):
    """
    Update workflow/status fields in jobs_YYYY-MM-DD.csv by job_id.

    INPUT (JSON string):
    {
      "job_id": "...",                 # required
      "updates": {                     # optional if 'action' provided
        "resume_customized": true,
        "ats_score_checked": "yes",
        "ats_score": 86,
        "approved_for_application": false,
        "application_submitted": "no",
        "resume_id_used": "resume-01",
        "date_applied": "2025-08-13",
        "seniority_level": "Entry",
        "employment_type": "Full-time",
        "salary_range": "80-100k CAD",
        "skills_extracted": "Python, SQL, ML"
      },
      "date": "YYYY-MM-DD",            # optional target file; defaults to today or latest
      "action": "approve" | "submit_application" | "mark_resume_customized" | "set_ats_score",
      "args": { ... }                  # optional extra args for action
    }

    OUTPUT (JSON):
    { "ok": true, "csv_path": "...", "updated_fields": {...}, "row": {...} }
    """
    name: str = "Update Jobs CSV"
    description: str = "Update workflow/status fields for a job row in the daily CSV by job_id. Returns JSON."

    def _resolve_csv_path(self, date_str: str | None):
        if date_str:
            p = _csv_for_date(date_str)
            return p if os.path.exists(p) else None
        p = _today_csv()
        if os.path.exists(p): return p
        return _latest_csv()

    def _apply_action(self, action: str, updates: dict, args: dict | None):
        a = (action or "").strip().lower()
        args = args or {}
        if a == "approve":
            updates["approved_for_application"] = "yes"
        elif a == "submit_application":
            updates["application_submitted"] = "yes"
            if "resume_id_used" in args:
                updates["resume_id_used"] = args["resume_id_used"]
            if "date_applied" in args:
                updates["date_applied"] = args["date_applied"]
        elif a == "mark_resume_customized":
            updates["resume_customized"] = "yes"
            if "resume_id_used" in args:
                updates["resume_id_used"] = args["resume_id_used"]
        elif a == "set_ats_score":
            if "ats_score" in args:
                updates["ats_score"] = args["ats_score"]
            updates.setdefault("ats_score_checked", "yes")

    def _run(self, json_payload: str) -> str:
        try:
            payload = json.loads(json_payload)
        except Exception:
            return json.dumps({"ok": False, "error": "Input must be a JSON string."})

        job_id = payload.get("job_id")
        if not job_id:
            return json.dumps({"ok": False, "error": "Missing 'job_id'."})

        csv_path = self._resolve_csv_path(payload.get("date"))
        if not csv_path:
            return json.dumps({"ok": False, "error": "No CSV found for the given date, and no prior CSVs exist."})

        rows = _read_all(csv_path)
        if not rows:
            return json.dumps({"ok": False, "error": f"No rows in CSV: {csv_path}"})

        updates = payload.get("updates", {}) or {}
        action = payload.get("action")
        args = payload.get("args", {}) or {}
        if action:
            self._apply_action(action, updates, args)

        # sanitize & whitelist
        sanitized = {}
        for k, v in updates.items():
            if k in UPDATABLE_FIELDS:
                sanitized[k] = _bool_to_yesno(v)

        # auto-fill date_applied if submitting
        if sanitized.get("application_submitted") == "yes" and not sanitized.get("date_applied"):
            sanitized["date_applied"] = _date.today().isoformat()

        target = None
        for r in rows:
            if r.get("job_id") == job_id:
                target = r
                break

        if target is None:
            return json.dumps({"ok": False, "error": f"job_id not found: {job_id}", "csv_path": csv_path})

        target.update(sanitized)

        try:
            _write_all_atomic(csv_path, rows)
        except Exception as e:
            return json.dumps({"ok": False, "error": f"Failed to write CSV: {e}", "csv_path": csv_path})

        return json.dumps({
            "ok": True,
            "csv_path": csv_path,
            "updated_fields": sanitized,
            "row": target
        }, ensure_ascii=False)

    def _arun(self, *args, **kwargs):
        raise NotImplementedError("This tool does not support async")
