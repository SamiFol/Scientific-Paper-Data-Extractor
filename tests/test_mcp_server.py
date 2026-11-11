import asyncio
import importlib.util
import sys
from pathlib import Path

import pytest

pytest.importorskip("mcp")
pytest.importorskip("chromadb")
from pdfutil import make_pdf  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
TRANSFORMER = ("The Transformer relies on self-attention instead of recurrence. It reaches 28.4 BLEU on the WMT 2014 "
               "English-to-German translation task and trains in 3.5 days on eight GPUs. ") * 2
LIMITS = ("Limitations: the model needs large amounts of training data and quadratic memory for long sequences. "
          "Future work will study local attention for images and audio. ") * 2


@pytest.fixture()
def env(tmp_path, monkeypatch):
    """Server module wired to a temp papers folder, a temp vector store and the offline hash embedding."""
    papers = tmp_path / "papers"
    papers.mkdir()
    make_pdf(papers / "attention.pdf", [TRANSFORMER, LIMITS])
    make_pdf(papers / "react.pdf", ["ReAct interleaves reasoning traces and actions in language models. " * 6])
    monkeypatch.setenv("PAPER_DIRS", str(papers))
    spec = importlib.util.spec_from_file_location("server_under_test", ROOT / "mcp_server" / "server.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    monkeypatch.setattr(m, "EMBEDDING", "hash")
    monkeypatch.setattr(m, "STORE_DIR", tmp_path / "store")
    monkeypatch.setattr(m, "_index", None)
    m.papers = papers
    return m


def run(coro):
    return asyncio.run(coro)


# ---------------------------------------------------------------- rag
def test_chunks_have_pages_and_search_finds_the_right_page(env):
    run(env.index_paper("attention"))
    hits = env.index().search("BLEU score on English-to-German", 3, env.resolve_pdf("attention"))
    assert hits[0]["page"] == 1 and "28.4" in hits[0]["text"]
    lim = env.index().search("limitations future work", 2, env.resolve_pdf("attention"))
    assert lim[0]["page"] == 2


def test_indexing_is_idempotent_and_replaces_changed_files(env):
    first = run(env.index_paper("attention"))
    assert '"indexed"' in first and "already indexed" in run(env.index_paper("attention"))
    n = env.index().count()
    make_pdf(env.papers / "attention.pdf", ["A completely different paper about image classification. " * 8])
    assert '"indexed"' in run(env.index_paper("attention"))
    assert env.index().count() != n and "28.4" not in " ".join(h["text"] for h in env.index().search("BLEU", 5))


def test_search_can_be_limited_to_one_paper(env):
    run(env.index_folder())
    out = run(env.search_papers("reasoning traces and actions", k=3, paper="react"))
    assert "react.pdf" in out and "attention.pdf" not in out


def test_pdf_without_text_is_reported(env):
    make_pdf(env.papers / "scan.pdf", [""])
    with pytest.raises(ValueError, match="no extractable text"):
        run(env.index_paper("scan"))


# ---------------------------------------------------------------- path safety
def test_resolve_by_name_part_and_ambiguity(env, tmp_path):
    assert env.resolve_pdf("attention.pdf").name == "attention.pdf"
    assert env.resolve_pdf("reac").name == "react.pdf"
    make_pdf(env.papers / "attention2.pdf", ["x " * 100])
    with pytest.raises(ValueError, match="several PDFs"):
        env.resolve_pdf("attention")
    with pytest.raises(ValueError, match="no PDF matching"):
        env.resolve_pdf("nothing-like-this")


def test_files_outside_allowed_folders_are_refused(env, tmp_path):
    other = make_pdf(tmp_path / "secret.pdf", ["secret " * 30])
    with pytest.raises(PermissionError, match="outside the allowed"):
        env.resolve_pdf(str(other))
    with pytest.raises(PermissionError):
        env.resolve_pdf(str(env.papers / ".." / "secret.pdf"))


def test_read_output_blocks_traversal_and_binary(env, monkeypatch, tmp_path):
    out = tmp_path / "out"
    out.mkdir()
    (out / "paper_draft.md").write_text("# T\nhello")
    (tmp_path / "secret.txt").write_text("nope")
    (out / "x.pdf").write_bytes(b"%PDF")
    monkeypatch.setattr(env.config, "OUT_DIR", out)
    assert "hello" in run(env.read_output("paper_draft.md"))
    with pytest.raises(PermissionError):
        run(env.read_output("../secret.txt"))
    with pytest.raises(FileNotFoundError):
        run(env.read_output("x.pdf"))
    assert "paper_draft.md" in run(env.list_outputs())


# ---------------------------------------------------------------- LLM tools (fake LLM)
def fake_llm(env, monkeypatch, reply="Answer text (p. 1)."):
    seen = {}

    def call(model, prompt, system, **kw):
        print("noise from the llm layer")                    # must never reach stdout
        seen.update(prompt=prompt, system=system)
        return reply
    monkeypatch.setattr(env.llm, "call", call)
    monkeypatch.setattr(env.config, "has_api_key", lambda: True)
    return seen


def test_ask_paper_sends_only_retrieved_excerpts_and_cites_sources(env, monkeypatch, capsys):
    seen = fake_llm(env, monkeypatch)
    out = run(env.ask_paper("attention", "How many BLEU points on English-to-German?"))
    assert "28.4" in seen["prompt"] and "[p. 1]" in seen["prompt"] and "Question: How many BLEU" in seen["prompt"]
    assert "ReAct interleaves" not in seen["prompt"]                      # other paper never leaks in
    assert out.startswith("Answer text") and "attention.pdf, pages" in out
    cap = capsys.readouterr()
    assert cap.out == "" and "noise from the llm layer" in cap.err         # stdout stays clean for the protocol


def test_summarize_paper_retrieves_for_every_aspect(env, monkeypatch):
    seen = fake_llm(env, monkeypatch, "## Problem\nx (p. 1)")
    out = run(env.summarize_paper("attention"))
    for title in ("Problem", "Method", "Results", "Limitations"):
        assert f"Retrieved for: {title}" in seen["prompt"]
    assert out.startswith("# attention.pdf") and "Sources: pages" in out


def test_llm_tools_fail_clearly_without_an_api_key(env, monkeypatch):
    monkeypatch.setattr(env.config, "has_api_key", lambda: False)
    with pytest.raises(RuntimeError, match="No API key"):
        run(env.ask_paper("attention", "anything"))


# ---------------------------------------------------------------- pipeline tools
def test_run_step_validates_and_cannot_inject_flags(env):
    with pytest.raises(ValueError, match="step must"):
        run(env.run_step("rm -rf"))
    with pytest.raises(ValueError, match="must not start"):
        run(env.run_step("analyze", topic="--force"))
    with pytest.raises(ValueError, match="name:"):
        run(env.run_step("analyze", topic="t", name="--force"))
    with pytest.raises(ValueError, match="paper_type"):
        run(env.run_step("analyze", paper_type="x"))


def test_run_step_runs_main_py_as_subprocess_and_returns_the_log(env, monkeypatch, tmp_path):
    fake_root = tmp_path / "fakeproject"
    fake_root.mkdir()
    (fake_root / "main.py").write_text("import sys\nprint('ARGS', sys.argv[1:])\nprint('x' * 3)\nsys.exit(3)\n")
    monkeypatch.setattr(env, "ROOT", fake_root)
    out = run(env.run_step("analyze", topic="Agents memory", venue="ICML", name="MyFw", pages=8))
    assert out.startswith("exit code: 3") and "'--step', 'analyze'" in out
    assert "'--name', 'MyFw'" in out and "'--pages', '8'" in out
    assert "'--', 'Agents memory', 'ICML'" in out


def test_run_step_times_out_and_kills(env, monkeypatch, tmp_path):
    fake_root = tmp_path / "slow"
    fake_root.mkdir()
    (fake_root / "main.py").write_text("import time\ntime.sleep(30)\n")
    monkeypatch.setattr(env, "ROOT", fake_root)
    monkeypatch.setattr(env, "STEP_TIMEOUT", 1)
    assert "Timed out" in run(env.run_step("lint"))


def test_get_paper_sheet_lists_and_selects_fields(env, monkeypatch, tmp_path):
    import json
    monkeypatch.setattr(env.config, "EXTRACTED_DIR", tmp_path / "sheets")
    (tmp_path / "sheets").mkdir()
    (tmp_path / "sheets" / "a.json").write_text(json.dumps(
        {"cite_key": "[Vaswani et al., 2017]", "title": "Attention Is All You Need", "authors": ["A"], "year": 2017,
         "source_file": "1706.03762v7.pdf", "limitations": ["needs data"]}))
    assert "Attention Is All You Need" in run(env.get_paper_sheet())
    out = run(env.get_paper_sheet("vaswani", "limitations,year"))
    assert "needs data" in out and "2017" in out and "title" not in out