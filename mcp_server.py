import sys
import logging
import contextlib
import warnings

# Forțează UTF-8 pe Windows
sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

# Suprimă logging-ul zgomotos ÎNAINTE de a importa CrewAI/LiteLLM
logging.getLogger("LiteLLM").setLevel(logging.WARNING)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
warnings.filterwarnings("ignore")

# Dezactivează debug info LiteLLM
import litellm
litellm.suppress_debug_info = True
litellm.set_verbose = False

from mcp.server.fastmcp import FastMCP
from paper_crew import run_paper_generation_async
from sample_data import SAMPLE_PAPERS, TARGET_CONFERENCE

mcp = FastMCP("Academic Paper Generator")


@mcp.tool()
async def generate_paper(input_papers: str, target_conference: str) -> str:
    """
    Generează o lucrare științifică completă în format LaTeX pe baza unor texte sursă.
    """
    output_file = "mcp_generated_paper.tex"
    try:
        # Redirecționăm TOT ce se printează în timpul execuției către stderr,
        # ca să nu corupem protocolul JSON-RPC de pe stdout.
        with contextlib.redirect_stdout(sys.stderr):
            latex = await run_paper_generation_async(
                input_papers=input_papers,
                target_conference=target_conference,
                output_file=output_file,
            )
        return f"✅ Lucrare generată cu succes în '{output_file}'. Lungime: {len(latex)} caractere."
    except Exception as e:
        return f"❌ Eroare la generare: {str(e)}"


@mcp.tool()
async def generate_sample_paper() -> str:
    """
    Generează o lucrare de test folosind datele predefinite din sample_data.py.
    """
    return await generate_paper(SAMPLE_PAPERS, TARGET_CONFERENCE)


if __name__ == "__main__":
    mcp.run(transport="stdio")