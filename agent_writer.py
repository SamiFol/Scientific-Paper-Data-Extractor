from crewai import Agent
from config import gemini_llm

writer = Agent(
    role="Lead Academic Writer",
    goal="Write a full academic paper in clean, compilable LaTeX code based on the provided outline.",
    backstory=(
        "You are an expert paper author. You write rigorous academic text in formal English and output complete, "
        "valid LaTeX code including title, abstract, sections, equation blocks, and references."
    ),
    verbose=True,
    allow_delegation=False,
    llm=gemini_llm
)