# ==============================================================================
# FILE: agents.py
# PURPOSE: Defines the CrewAI agents for the project (Scraper + Analyst).
# - Scraper returns JSON rows and persists to CSV via ScrapeLinkedInTool.
# - Analyst reads JSON, extracts fields, and persists updates via UpdateJobsCsvTool.
# ==============================================================================

from crewai import Agent, LLM
from tools.scraping_tools import ScrapeLinkedInTool
from tools.workflow_tools import UpdateJobsCsvTool

# Instantiate tools
linkedin_scraper_tool = ScrapeLinkedInTool()
update_jobs_csv_tool = UpdateJobsCsvTool()

# Local OpenAI-compatible LLM
local_llm = LLM(
    model="openai/llama-2-7b-chat",
    base_url="http://localhost:8000/v1",
    api_key="not-needed",
    temperature=0.2,
    max_tokens=1024,   # ample room now that your engine is 4k context
    top_p=0.9,
)

class JobAgents:
    def research_agent(self):
        """
        Returns JSON from ScrapeLinkedInTool:
        {
          "ok": true,
          "csv_path": "<.../data/jobs_YYYY-MM-DD.csv>",
          "appended": <int>,
          "jobs": [ {<full CSV-schema row>}, ... ]   # only new rows for the day
        }
        """
        return Agent(
            role="Job Market Research Analyst",
            goal=(
                "Scrape LinkedIn for relevant roles and persist them to the daily CSV. "
                "Always return a compact JSON object with the 'jobs' list matching the CSV schema."
            ),
            backstory=(
                "You quickly find jobs and save them as structured rows. "
                "Use the 'Scrape LinkedIn for jobs' tool to both scrape and persist. "
                "Do not produce prose; return the tool's JSON output."
            ),
            tools=[linkedin_scraper_tool],
            verbose=True,              # keep prompts small -> more room for results
            allow_delegation=False,
            llm=local_llm,
        )

    def analysis_agent(self):
        """
        INPUT context: JSON from the scraper agent, with a 'jobs' array of rows.
        TASK: For each job row, extract skills and optional enrichment, then update the CSV.
        OUTPUT: JSON mapping job_id -> updates applied, e.g.:
        {
          "ok": true,
          "updates": {
            "<job_id>": {
              "skills_extracted": "Python, SQL, TensorFlow",
              "seniority_level": "Mid",
              "employment_type": "Full-time"
            },
            ...
          }
        }

        Persistence: Use Update Jobs CSV tool with payloads like:
        {
          "job_id": "<job_id>",
          "updates": {
            "skills_extracted": "...",
            "seniority_level": "...",
            "employment_type": "...",
            "salary_range": "..."
          }
        }
        """
        return Agent(
            role="Job Requirements Analyst",
            goal=(
                "Read the JSON 'jobs' array from the previous task. "
                "For each job, extract 'skills_extracted' (comma-separated), and where possible "
                "'seniority_level', 'employment_type', and 'salary_range'. "
                "Persist these fields back to the CSV using the 'Update Jobs CSV' tool. "
                "Return a single JSON object mapping job_id -> updates you applied."
            ),
            backstory=(
                "You analyze structured job rows and enrich them. "
                "You must persist updates via the helper tool, one call per job_id or in multiple calls. "
                "Only output JSON—no markdown or prose."
            ),
            tools=[update_jobs_csv_tool],
            verbose=False,
            allow_delegation=False,
            llm=local_llm,
        )
