from crewai import Agent, LLM
from tools.scraping_tools import ScrapeLinkedInTool

tool = ScrapeLinkedInTool()
llm = LLM(model="openai/llama-2-7b-chat", base_url="http://localhost:8000/v1", api_key="x", max_tokens=256)

agent = Agent(
    role="Tester",
    goal="Call the tool",
    backstory="Short.",
    tools=[tool],
    verbose=1,
    llm=llm,
)

from crewai import Task
t = Task(
    description="Call the tool named 'Scrape LinkedIn for jobs' with {\"keywords\":\"Data Scientist\",\"location\":\"Ontario, Canada\"}. Return only the tool output.",
    agent=agent,
    expected_output="..."
)

# Run a single task crew
from crewai import Crew, Process
print(Crew(agents=[agent], tasks=[t], process=Process.sequential, verbose=1).kickoff())
