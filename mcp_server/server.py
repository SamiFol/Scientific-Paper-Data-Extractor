"""MCP server (stdio): ask questions about local PDFs with RAG, summarize a paper, run the paper pipeline.
stdio rule: NEVER print() here (stdout carries the protocol). Use logging (stderr)."""
import asyncio
import contextlib
import functools
import json
import logging
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))                       # lets `pipeline` and `mcp_server` import when run as a script

logging.basicConfig(stream=sys.stderr, level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
log = logging.getLogger("paper-server")

from mcp.server import MCPServer                     # MCP Python SDK 2.0+ (as in the official docs)
from mcp.server.mcpserver.exceptions import ToolError

from mcp_server import rag                           # noqa: E402
from pipeline import config, llm, prompts            # noqa: E402

config.set_root(ROOT)                                # out/, papers/ ... absolute, whatever the working folder is

EMBEDDING = os.getenv("RAG_EMBEDDING", "default")    # "default" = Chroma's built-in model; "hash" = offline test mode
STORE_DIR = Path(os.getenv("RAG_STORE") or ROOT / ".rag_store")
STEP_TIMEOUT = int(os.getenv("STEP_TIMEOUT_MIN", "30")) * 60
STEPS = ("extract", "analyze", "literature", "write", "review", "fix", "lint", "gate", "latex", "pdf", "all")
TYPES = ("position", "empirical")
READABLE = {".md", ".txt", ".tex", ".json", ".log", ".bib"}
ASPECTS = {                                          # what to retrieve for a summary
    "Problem": "What problem does the paper address, why does it matter, and what are its contributions?",
    "Method": "How does the proposed method work? architecture, algorithm, components, training",
    "Results": "What are the main experimental results? benchmarks, accuracy, scores, comparisons with baselines",
    "Limitations": "What limitations, failure cases or future work do the authors state?",
}

server = MCPServer("paper-assistant")


def tool(fn):
    """Register fn as an MCP tool. Expected errors become ToolError so the client sees the real message
    (the SDK hides other exceptions behind 'Error executing tool'). fn itself stays directly callable."""
    @functools.wraps(fn)
    async def safe(*args, **kwargs):
        try:
            return await fn(*args, **kwargs)
        except (ValueError, PermissionError, RuntimeError, FileNotFoundError, OSError) as e:
            log.warning("%s failed: %s", fn.__name__, e)
            raise ToolError(str(e)) from e
    server.tool()(safe)
    return fn

_index = None
_run_lock = asyncio.Lock()


# ------------------------------------------------------------------ helpers
@contextlib.contextmanager
def quiet():
    """Libraries may print; send that to stderr so it cannot corrupt the protocol."""
    with contextlib.redirect_stdout(sys.stderr):
        yield


def index():
    global _index
    if _index is None:
        with quiet():
            _index = rag.PaperIndex(STORE_DIR, EMBEDDING)
    return _index


def allowed_dirs():
    """Folders the server may read PDFs from: PAPER_DIRS (os.pathsep separated) or only papers/."""
    env = os.getenv("PAPER_DIRS")
    dirs = [Path(d) for d in env.split(os.pathsep) if d] if env else [ROOT / "papers"]
    return [d.resolve() for d in dirs if d.is_dir()]


def resolve_pdf(ref):
    """File name, part of a name, or full path -> a PDF inside the allowed folders. Raises with a clear message."""
    ref = (ref or "").strip().strip('"')
    dirs = allowed_dirs()
    if not ref:
        raise ValueError("no paper given")
    if not dirs:
        raise ValueError("no paper folder exists; create papers/ or set PAPER_DIRS")
    direct = Path(ref).expanduser()
    hits = [direct.resolve()] if direct.is_file() else [(d / ref).resolve() for d in dirs if (d / ref).is_file()]
    if not hits:
        needle = ref.lower()
        hits = sorted({f.resolve() for d in dirs for f in d.rglob("*.pdf") if needle in f.name.lower()})
        if len(hits) > 1:
            raise ValueError(f"several PDFs match '{ref}': " + ", ".join(h.name for h in hits[:8]))
    if not hits:
        raise ValueError(f"no PDF matching '{ref}' in: " + ", ".join(str(d) for d in dirs))
    pdf = hits[0]
    if pdf.suffix.lower() != ".pdf":
        raise ValueError(f"{pdf.name} is not a PDF")
    if not any(pdf.is_relative_to(d) for d in dirs):
        raise PermissionError(f"{pdf} is outside the allowed folders ({', '.join(map(str, dirs))}); set PAPER_DIRS")
    return pdf


def ask_llm(system, prompt, max_tokens=2500):
    if not config.has_api_key():
        raise RuntimeError("No API key found. Add GEMINI_API_KEY or ANTHROPIC_API_KEY to the .env file.")
    with quiet():
        return llm.call(config.MODEL_SMART, prompt, system, temperature=0.2, max_tokens=max_tokens)


def fmt_excerpts(hits):
    return "\n\n".join(f"[p. {h['page']}] {h['text']}" for h in hits)


def pages_of(hits):
    return ", ".join(str(p) for p in sorted({h["page"] for h in hits}))


def ready(ref):
    """Resolve and index one paper (no-op when already indexed). Returns the path."""
    pdf = resolve_pdf(ref)
    with quiet():
        index().index_pdf(pdf)
    return pdf


# ------------------------------------------------------------------ RAG tools
@tool
async def list_papers() -> str:
    """List the PDFs found in the allowed folders (papers/ by default) and whether each is indexed."""
    def work():
        done = set(index().indexed_sources())
        rows = [f"- {f.name} ({f.stat().st_size / 1e6:.1f} MB){' [indexed]' if str(f.resolve()) in done else ''}  {f}"
                for d in allowed_dirs() for f in sorted(d.rglob("*.pdf"))]
        return "\n".join(rows) or "No PDFs found in: " + ", ".join(map(str, allowed_dirs()))
    return await asyncio.to_thread(work)


@tool
async def index_paper(pdf: str) -> str:
    """Index one PDF (file name, part of the name, or full path) so it can be searched. Safe to repeat."""
    def work():
        with quiet():
            return json.dumps(index().index_pdf(resolve_pdf(pdf)), ensure_ascii=False)
    return await asyncio.to_thread(work)


@tool
async def index_folder(folder: str = "") -> str:
    """Index every PDF in a folder (default: the first allowed folder, normally papers/). Folder must be allowed."""
    def work():
        target = Path(folder).expanduser().resolve() if folder else (allowed_dirs() or [ROOT / "papers"])[0]
        if not any(target.is_relative_to(d) for d in allowed_dirs()):
            raise PermissionError(f"{target} is not an allowed folder; set PAPER_DIRS")
        out = []
        for f in sorted(target.glob("*.pdf")):
            try:
                with quiet():
                    out.append(index().index_pdf(f))
            except Exception as e:                                # one bad PDF must not stop the rest
                out.append({"name": f.name, "status": f"failed: {e}"})
        return json.dumps(out, ensure_ascii=False, indent=1) if out else "No PDFs in " + str(target)
    return await asyncio.to_thread(work)


@tool
async def search_papers(query: str, k: int = 5, paper: str = "") -> str:
    """Semantic search over indexed papers. Give `paper` to search only one PDF. Returns top chunks with page."""
    def work():
        path = ready(paper) if paper else None
        with quiet():
            hits = index().search(query, max(1, min(k, 20)), path)
        if not hits:
            return "No indexed text found. Index a paper first (index_paper or index_folder)."
        return "\n\n".join(f"**{h['name']} p. {h['page']}** (distance {h['distance']})\n{h['text']}" for h in hits)
    return await asyncio.to_thread(work)


@tool
async def ask_paper(pdf: str, question: str, k: int = 6) -> str:
    """Answer a specific question about ONE downloaded paper: retrieves the best passages (RAG), then the LLM
    answers only from them and cites pages. `pdf` = file name, part of it, or full path."""
    def work():
        path = ready(pdf)
        with quiet():
            hits = index().search(question, max(1, min(k, 12)), path)
        if not hits:
            return f"No text could be retrieved from {path.name}."
        prompt = prompts.load("rag_answer_input", paper=path.name, question=question, excerpts=fmt_excerpts(hits))
        answer = ask_llm(prompts.load("rag_answer"), prompt)
        return f"{answer.strip()}\n\n_Sources: {path.name}, pages {pages_of(hits)}_"
    return await asyncio.to_thread(work)


@tool
async def summarize_paper(pdf: str) -> str:
    """Summarize ONE paper (problem, method, results, limitations) from retrieved passages, with page citations."""
    def work():
        path = ready(pdf)
        seen, blocks, all_hits = set(), [], []
        for title, query in ASPECTS.items():
            with quiet():
                hits = [h for h in index().search(query, 4, path) if (h["page"], h["text"][:60]) not in seen]
            seen.update((h["page"], h["text"][:60]) for h in hits)
            all_hits += hits
            blocks.append(f"### Retrieved for: {title}\n{fmt_excerpts(sorted(hits, key=lambda h: h['page']))}")
        if not all_hits:
            return f"No text could be retrieved from {path.name}."
        prompt = prompts.load("rag_summary_input", paper=path.name, excerpts="\n\n".join(blocks))
        summary = ask_llm(prompts.load("rag_summary"), prompt, max_tokens=3000)
        return f"# {path.name}\n\n{summary.strip()}\n\n_Sources: pages {pages_of(all_hits)}_"
    return await asyncio.to_thread(work)


@tool
async def get_paper_sheet(paper: str = "", fields: str = "") -> str:
    """Read the detailed sheet the pipeline's extractor already made (out/extracted_v3). With no `paper`, list the
    sheets. `fields` = comma-separated keys (e.g. 'results,limitations'); default is a short overview."""
    def work():
        from pipeline.agents.extractor import load_all
        sheets = load_all()
        if not paper:
            return "\n".join(f"- {s['cite_key']} {s.get('title')} ({s.get('source_file')})" for s in sheets) \
                or "No sheets yet. Run extract_sheets first."
        needle = paper.lower()
        found = [s for s in sheets if needle in json.dumps([s.get("source_file"), s.get("title"), s["cite_key"]]).lower()]
        if len(found) != 1:
            return f"{len(found)} sheets match '{paper}'. Call get_paper_sheet() with no arguments to list them."
        keys = [k.strip() for k in fields.split(",") if k.strip()] or \
            ["cite_key", "title", "authors", "year", "contributions", "limitations", "claims_table"]
        return json.dumps({k: found[0].get(k) for k in keys}, ensure_ascii=False, indent=1)
    return await asyncio.to_thread(work)


# ------------------------------------------------------------------ pipeline tools
async def _main_py(args):
    """Run `python main.py ...` as a subprocess (config is global state; pipeline prints to stdout)."""
    if _run_lock.locked():
        return "Another pipeline run is already in progress."
    async with _run_lock:
        env = {**os.environ, "PYTHONUNBUFFERED": "1", "PYTHONIOENCODING": "utf-8"}
        log.info("running: main.py %s", " ".join(args))
        proc = await asyncio.create_subprocess_exec(
            sys.executable, str(ROOT / "main.py"), *args, cwd=str(ROOT), env=env,
            stdin=asyncio.subprocess.DEVNULL, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT)
        try:
            out, _ = await asyncio.wait_for(proc.communicate(), timeout=STEP_TIMEOUT)
        except asyncio.TimeoutError:
            proc.kill()
            await proc.wait()
            return f"Timed out after {STEP_TIMEOUT // 60} minutes; the run was stopped."
    tail = "\n".join(out.decode("utf-8", "replace").splitlines()[-40:])
    return f"exit code: {proc.returncode}\n\n```\n{tail}\n```"


def _check_text(label, value):
    if value.startswith("-"):
        raise ValueError(f"{label} must not start with '-'")
    return value


@tool
async def run_step(step: str, topic: str = "", venue: str = "", paper_type: str = "position",
                   name: str = "", pages: int = 0) -> str:
    """Run one stage of the paper pipeline (main.py --step ...). step: extract|analyze|literature|write|review|fix|
    lint|gate|latex|pdf|all. Slow (minutes) and uses the LLM. Returns the exit code and the end of the log."""
    if step not in STEPS:
        raise ValueError(f"step must be one of {STEPS}")
    if paper_type not in TYPES:
        raise ValueError(f"paper_type must be one of {TYPES}")
    if pages < 0 or pages > 100:
        raise ValueError("pages must be 0-100")
    args = ["--step", step, "--type", paper_type]
    if name:
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9 _.-]{0,59}", name):
            raise ValueError("name: letters, digits, space, _ . - (max 60)")
        args += ["--name", name]
    if pages:
        args += ["--pages", str(pages)]
    if venue and not topic:
        raise ValueError("venue needs a topic")
    if topic:
        args += ["--", _check_text("topic", topic)] + ([_check_text("venue", venue)] if venue else [])
    return await _main_py(args)


@tool
async def extract_sheets() -> str:
    """Stage 1: read every PDF in papers/ and build detailed sheets (out/extracted_v3). Skips ones already done."""
    return await run_step("extract")


@tool
async def analyze_topic(topic: str, paper_type: str = "position") -> str:
    """Stage 2: analyze all sheets for a topic (gaps, novelty, hypotheses, outline) -> out/analysis.json."""
    return await run_step("analyze", topic=topic, paper_type=paper_type)


@tool
async def write_draft(topic: str, venue: str = "", paper_type: str = "position", pages: int = 0) -> str:
    """Stage 3: write the paper draft from the analysis -> out/paper_draft.md."""
    return await run_step("write", topic=topic, venue=venue, paper_type=paper_type, pages=pages)


@tool
async def review_draft(paper_type: str = "position") -> str:
    """Stage 4: audit the draft (claims vs evidence) -> out/review.json, claims_vs_evidence.md, lint_report.md."""
    return await run_step("review", paper_type=paper_type)


@tool
async def list_outputs() -> str:
    """List the files the pipeline wrote to out/."""
    out = config.OUT_DIR
    if not out.is_dir():
        return "out/ does not exist yet. Run a pipeline step first."
    rows = [f"- {f.relative_to(out).as_posix()} ({f.stat().st_size} bytes)" for f in sorted(out.rglob("*")) if f.is_file()]
    return "\n".join(rows) or "out/ is empty."


@tool
async def read_output(name: str, max_chars: int = 20000) -> str:
    """Read a text file from out/ (md, txt, tex, json, log, bib), e.g. 'paper_draft.md' or 'review.json'."""
    out = config.OUT_DIR.resolve()
    path = (out / name).resolve()
    if not path.is_relative_to(out):
        raise PermissionError("only files inside out/ can be read")
    if path.suffix.lower() not in READABLE or not path.is_file():
        raise FileNotFoundError(f"{name}: not found or not a text file ({', '.join(sorted(READABLE))})")
    text = path.read_text(encoding="utf-8", errors="replace")
    limit = max(500, min(max_chars, 200000))
    return text if len(text) <= limit else text[:limit] + f"\n\n[... cut, {len(text) - limit} more characters]"


if __name__ == "__main__":
    server.run()