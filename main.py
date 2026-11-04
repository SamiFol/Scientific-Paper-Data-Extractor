import os
import re
import subprocess
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

OUTPUT_FILE = "generated_paper.tex"


def clean_latex(text: str) -> str:
    """Elimină fence-urile Markdown și textul dinainte/după document."""
    text = text.strip()
    # scoate ```latex ... ``` sau ``` ... ```
    text = re.sub(r"^```(?:latex|tex)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    # păstrează doar între \documentclass și \end{document}
    start = text.find("\\documentclass")
    end = text.find("\\end{document}")
    if start != -1 and end != -1:
        text = text[start:end + len("\\end{document}")]
    return text.strip() + "\n"


def try_compile(tex_file: str) -> None:
    """Încearcă pdflatex dacă e disponibil; altfel sare."""
    try:
        r = subprocess.run(
            ["pdflatex", "-interaction=nonstopmode", "-halt-on-error", tex_file],
            capture_output=True, text=True, timeout=120
        )
        if r.returncode == 0:
            print("[OK] LaTeX a compilat cu succes -> generated_paper.pdf")
        else:
            print("[WARN] pdflatex a returnat eroare. Vezi generated_paper.log")
            print(r.stdout[-1500:])
    except FileNotFoundError:
        print("[INFO] pdflatex nu este instalat — sar peste compilare.")
    except subprocess.TimeoutExpired:
        print("[WARN] pdflatex a depășit timeout-ul.")


if __name__ == "__main__":
    sample_input = """
    Paper 1: "Multi-Agent Summarization with GPT-3.5" — proposed a basic multi-agent system
    for text summarization using GPT-3.5. Reported accuracy 82% on CNN/DailyMail, but token
    usage was ~3x higher than a single-agent baseline. Limitation: no cost optimization.

    Paper 2: "Prompt Caching for LLM Cost Reduction" — introduced prompt caching to reduce
    LLM inference costs by 40% in single-agent architectures. Limitation: evaluated only on
    single-agent pipelines, not on multi-agent collaboration.
    """

    inputs = {
        'input_papers': sample_input,
        'target_conference': 'IEEE International Conference on AI Agents 2026'
    }

    print("[INFO] Pornire flux cu agenți separați...")
    result = academic_crew.kickoff(inputs=inputs)

    raw = result.raw if hasattr(result, "raw") else str(result)
    latex = clean_latex(raw)

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write(latex)

    print(f"\n[SUCCESS] Fișier generat: {OUTPUT_FILE} ({len(latex)} caractere)")

    # validare minimă structurală
    if "\\begin{document}" not in latex or "\\end{document}" not in latex:
        print("[WARN] LaTeX-ul generat nu conține \\begin{document}/\\end{document}.")

    try_compile(OUTPUT_FILE)