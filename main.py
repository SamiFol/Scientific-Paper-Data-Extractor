from paper_crew import run_paper_generation
from sample_data import SAMPLE_PAPERS, TARGET_CONFERENCE

if __name__ == "__main__":
    print("[INFO] Rulare pipeline generare lucrare științifică...")
    latex_code = run_paper_generation(
        input_papers=SAMPLE_PAPERS,
        target_conference=TARGET_CONFERENCE
    )
    # Opțional, poți afișa primele caractere pentru verificare
    # print(latex_code[:500])