# ==============================================================================
# FILE: tasks.py
# PURPOSE: Defines the CrewAI tasks for the agents.
# ==============================================================================
from crewai import Task
from agents import JobAgents

class JobTasks:
    def find_jobs_task(self, agent, keywords: str, location: str):
        return Task(
            description=(
                "You MUST call the tool 'Scrape LinkedIn for jobs' exactly once with these Tool Args:\n"
                f"{{\"keywords\": \"{keywords}\", \"location\": \"{location}\"}}\n"
                "Do not attempt to scrape yourself. Do not produce prose. "
                "Return exactly the JSON that the tool returns."
            ),
            agent=agent,
            expected_output=(
                "{\"ok\": true, \"csv_path\": \".../jobs_YYYY-MM-DD.csv\", \"appended\": <int>, "
                "\"jobs\": [ { <full CSV-schema row> }, ... ] }"
            ),
        )
    def analyze_jobs_task(self, agent, context):
        return Task(
            description=(
                "Input is the JSON from the previous task under key 'jobs'. "
                "For each job, extract 'skills_extracted' (comma-separated), and optionally "
                "'seniority_level', 'employment_type', 'salary_range'. "
                "Use the 'Update Jobs CSV' tool to persist updates by 'job_id'. "
                "Finally, return a JSON object mapping job_id -> updates applied. "
                "Output ONLY JSON."
            ),
            agent=agent,
            context=context,
            expected_output="{\"ok\": true, \"updates\": {\"<job_id>\": {\"skills_extracted\": \"...\"}}}"
        )
