from crewai import Task
from agent_researcher import researcher
from agent_strategist import strategist
from agent_writer import writer

task_extract = Task(
    description=(
        "Analyze the following source papers/text and extract all core methodologies, "
        "main results, datasets used, and key limitations:\n\n{input_papers}"
    ),
    expected_output="A structured summary (Markdown) with key concepts, results, and limitations.",
    agent=researcher
)

task_plan = Task(
    description=(
        "Based on the extracted research summary, identify a novel angle or gap. "
        "Create a full section-by-section outline for a new conference paper targeted at {target_conference}."
    ),
    expected_output="A detailed paper outline with key arguments for each section.",
    agent=strategist
)

task_write = Task(
    description=(
        "Using the detailed outline, write a complete, formal academic paper. "
        "Output ONLY compilable LaTeX code (using standard article class or IEEEtran)."
    ),
    expected_output="Complete compilable LaTeX source code for the new paper.",
    agent=writer
)