from crewai import Agent
from config import gemini_llm

strategist = Agent(
    role="Academic Strategist & Architect",
    goal="Identify research gaps, synthesize extracted findings, and create a comprehensive paper outline.",
    backstory=(
        "You are a senior academic strategist. You analyze extracted research data, identify novel research gaps, "
        "and structure a logical, publication-ready outline tailored for target conference requirements."
    ),
    verbose=True,
    allow_delegation=False,
    llm=gemini_llm
)