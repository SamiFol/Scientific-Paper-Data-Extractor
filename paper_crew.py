# paper_crew.py
import os
import re
import subprocess
import asyncio
from crewai import Crew, Process
from agent_researcher import researcher
from agent_strategist import strategist
from agent_writer import writer
from tasks import task_extract, task_plan, task_write


def clean_latex(text: str) -> str:
    """Elimină fence-urile Markdown și repară documentul dacă e tăiat."""
    text = text.strip()
    text = re.sub(r"^```(?:latex|tex)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)

    # Găsește începutul
    start = text.find("\\documentclass")
    if start != -1:
        text = text[start:]

    # Verifică dacă lipsește finalul (din cauza limitei de tokeni)
    if "\\begin{document}" in text and "\\end{document}" not in text:
        print("[INFO] Auto-reparare: Modelul a fost tăiat. Adăugăm \\end{document} la final.")
        text += "\n\\end{document}\n"

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

async def run_paper_generation_async(
    input_papers: str, 
    target_conference: str, 
    output_file: str = "generated_paper.tex"
) -> str:
    """
    Funcția principală ASINCRONĂ care rulează crew-ul.
    Folosește această funcție în Jupyter Notebook cu `await`.
    """
    academic_crew = Crew(
        agents=[researcher, strategist, writer],
        tasks=[task_extract, task_plan, task_write],
        process=Process.sequential,
        verbose=True
    )

    inputs = {
        'input_papers': input_papers,
        'target_conference': target_conference
    }

    print("[INFO] Pornire flux cu agenți separați...")
    # Folosim kickoff_async pentru a nu bloca bucla de evenimente (Jupyter)
    result = await academic_crew.kickoff_async(inputs=inputs)

    raw = result.raw if hasattr(result, "raw") else str(result)
    latex = clean_latex(raw)

    with open(output_file, "w", encoding="utf-8") as f:
        f.write(latex)

    print(f"\n[SUCCESS] Fișier generat: {output_file} ({len(latex)} caractere)")

    if "\\begin{document}" not in latex or "\\end{document}" not in latex:
        print("[WARN] LaTeX-ul generat nu conține \\begin{document}/\\end{document}.")

    try_compile(output_file)
    return latex

def run_paper_generation(
    input_papers: str, 
    target_conference: str, 
    output_file: str = "generated_paper.tex"
) -> str:
    """
    Wrapper SINCRON pentru a rula din linia de comandă (main.py).
    NU folosi această funcție în Jupyter Notebook!
    """
    return asyncio.run(run_paper_generation_async(input_papers, target_conference, output_file))