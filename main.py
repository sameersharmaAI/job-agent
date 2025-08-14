
# FILE: main.py (UPDATED)
# PURPOSE: The main entry point for the AI Job Agent application.
# ==============================================================================
import os
import sys
import time
import json
import requests
os.environ["OTEL_SDK_DISABLED"] = "true"
os.environ["OTEL_EXPORTER_OTLP_TIMEOUT"] = "1"
os.environ["CREWAI_TELEMETRY_OPT_OUT"] = "1"
os.environ["CREWAI_LOG_LEVEL"] = "DEBUG"   # more verbose tool logs

from config import APP_CONFIG
from crewai import Crew, Process

# Import the new agent and task classes
from agents import JobAgents
from tasks import JobTasks

# -----------------------------
# Helper: ping OpenAI-compatible server
# -----------------------------
def check_llm_server() -> bool:
    """
    Send a minimal OpenAI-compatible /v1/chat/completions request.
    """
    url = APP_CONFIG.LLM_API_URL
    payload = {
        "model": "llama-2-7b-chat",
        "messages": [{"role": "user", "content": "Ping"}],
        "max_tokens": 1,
    }
    headers = {"Content-Type": "application/json"}

    try:
        r = requests.post(url, json=payload, headers=headers, timeout=10)
        return r.status_code == 200
    except (requests.exceptions.ConnectionError, requests.exceptions.Timeout):
        return False

def main():
    print("=======================================")
    print("    AI Job Application Agent Started   ")
    print("=======================================")

    # --- Server and Path Checks (from your script) ---
    try:
        APP_CONFIG.verify_paths()
    except Exception as e:
        print(f"❌ Path verification failed: {e}")
        sys.exit(1)

    print("Config summary:", json.dumps(APP_CONFIG.summary(), indent=2))

    retries = 5
    while retries > 0 and not check_llm_server():
        print(f"LLM server not found. Retrying in 10s... ({retries} left)")
        time.sleep(10)
        retries -= 1

    if not check_llm_server():
        print("❌ Could not connect to the LLM server.")
        sys.exit(1)
    
    print("✅ LLM server is online.")

    # --- Phase 2: Agentic Workflow ---
    print("\n--- Starting Phase 2: Job Scraping & Analysis ---")

    # Set environment variables for CrewAI to use the local LLM
    os.environ["OPENAI_API_BASE"] = "http://localhost:8000/v1"
    os.environ["OPENAI_MODEL_NAME"] = "openai/llama-2-7b-chat" 
    os.environ["OPENAI_API_KEY"] = "not-needed" # Required but not used

    # Initialize agents and tasks
    agents = JobAgents()
    tasks = JobTasks()

    researcher = agents.research_agent()
    analyst = agents.analysis_agent()

    # Define the job search criteria
    search_keywords = ", ".join(APP_CONFIG.JOB_SEARCH_KEYWORDS)
    search_location = "Ontario, Canada"  

    # Create the tasks
    find_jobs = tasks.find_jobs_task(researcher, search_keywords, search_location)
    analyze_jobs = tasks.analyze_jobs_task(analyst, context=[find_jobs])

    # Form the crew
    crew = Crew(
        agents=[researcher, analyst],
        tasks=[find_jobs, analyze_jobs],
        process=Process.sequential,
        verbose=1
    )

    # Kick off the crew's work
    print("\n🚀 Launching Crew to find and analyze jobs...")
    result = crew.kickoff()

    print("\n--- Phase 2 Complete ---")
    print("\nFinal Report:")
    print(result)


if __name__ == "__main__":
    APP_CONFIG.ensure_dirs()
    main()
