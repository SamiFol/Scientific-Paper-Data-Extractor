from crewai import Crew, Process
from agent_researcher import researcher
from agent_strategist import strategist
from agent_writer import writer
from tasks import task_extract, task_plan, task_write

academic_crew = Crew(
    agents=[researcher, strategist, writer],
    tasks=[task_extract, task_plan, task_write],
    process=Process.sequential,
    verbose=True
)

if __name__ == "__main__":
    sample_input = """
    Paper 1: Proposed a basic multi-agent system for text summarizing using GPT-3.5. Accuracy was 82%, but token usage was high.
    Paper 2: Introduced prompt caching to reduce LLM costs by 40% in single-agent architectures.
    """

    inputs = {
        'input_papers': sample_input,
        'target_conference': 'IEEE International Conference on AI Agents 2026'
    }

    print("[INFO] Pornire flux cu agenți separați...")
    result = academic_crew.kickoff(inputs=inputs)

    with open("generated_paper.tex", "w", encoding="utf-8") as f:
        f.write(str(result))

    print("\n[SUCCESS] Proiectul a generat fișierul 'generated_paper.tex'!")