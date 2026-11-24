import streamlit as st
import asyncio
import nest_asyncio
from paper_crew import run_paper_generation_async
from sample_data import SAMPLE_PAPERS, TARGET_CONFERENCE

# Permitem buclei de evenimente să ruleze în Streamlit
nest_asyncio.apply()

st.set_page_config(page_title="Academic Paper Generator", page_icon="📄", layout="wide")

st.title("📄 Academic Paper Multi-Agent Generator")
st.markdown("""
Această interfață folosește pipeline-ul **CrewAI** cu 3 agenți (Researcher, Strategist, Writer) 
și un sistem de fallback inteligent (Groq -> OpenRouter) pentru a genera lucrări științifice în LaTeX.
""")

col1, col2 = st.columns([2, 1])

with col1:
    input_papers = st.text_area(
        "Textul lucrărilor sursă (Input):",
        value=SAMPLE_PAPERS,
        height=300
    )

with col2:
    target_conference = st.text_input(
        "Conferința țintă:",
        value=TARGET_CONFERENCE
    )

    st.markdown("### ⚙️ Setări Output")
    output_filename = st.text_input("Nume fișier LaTeX:", value="ui_generated_paper.tex")

if st.button("🚀 Generează Lucrarea", type="primary", use_container_width=True):
    if not input_papers.strip():
        st.error("Te rog introdu textul sursă!")
    else:
        with st.spinner("Se procesează... Cei 3 agenți lucrează în fundal. Durează în jur de 1-2 minute."):
            try:
                # Rulăm funcția asincronă
                latex_result = asyncio.run(
                    run_paper_generation_async(
                        input_papers=input_papers,
                        target_conference=target_conference,
                        output_file=output_filename
                    )
                )

                st.success(f"✅ Lucrare generată cu succes! ({len(latex_result)} caractere)")
                st.download_button(
                    label="📥 Descarcă fișierul .tex",
                    data=latex_result,
                    file_name=output_filename,
                    mime="text/plain"
                )

                with st.expander("👀 Previzualizare Cod LaTeX"):
                    st.code(latex_result, language="latex")

            except Exception as e:
                st.error(f"❌ A apărut o eroare: {str(e)}")