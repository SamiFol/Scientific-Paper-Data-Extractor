"""End to end over the real MCP protocol: starts server.py as a subprocess and talks to it like the notebook does.
Only tools that need no LLM are called, so no API key or network is needed."""
import asyncio
import os
import sys
from pathlib import Path

import pytest

pytest.importorskip("mcp")
pytest.importorskip("chromadb")
from mcp import Client, StdioServerParameters  # noqa: E402
from mcp.client.stdio import stdio_client  # noqa: E402
from pdfutil import make_pdf  # noqa: E402

SERVER = Path(__file__).resolve().parent.parent / "mcp_server" / "server.py"


async def session_calls(env, calls):
    params = StdioServerParameters(command=sys.executable, args=[str(SERVER)], env=env)
    async with Client(stdio_client(params)) as client:
        tools = [t.name for t in (await client.list_tools()).tools]
        results = [await client.call_tool(name, args) for name, args in calls]
        return tools, results


def is_error(res):
    return bool(res.is_error)


def text(res):
    return "".join(getattr(c, "text", "") for c in res.content)


def test_server_speaks_mcp_and_rag_works_through_the_protocol(tmp_path):
    papers = tmp_path / "papers"
    papers.mkdir()
    make_pdf(papers / "attention.pdf", ["The Transformer reaches 28.4 BLEU on WMT14 English-to-German. " * 6])
    env = {**os.environ, "PAPER_DIRS": str(papers), "RAG_STORE": str(tmp_path / "store"), "RAG_EMBEDDING": "hash"}
    tools, res = asyncio.run(session_calls(env, [
        ("list_papers", {}),
        ("index_paper", {"pdf": "attention"}),
        ("search_papers", {"query": "BLEU English-to-German", "k": 2, "paper": "attention"}),
        ("read_output", {"name": "../../etc/passwd"}),
        ("ask_paper", {"pdf": "no-such-paper", "question": "x"}),
    ]))
    assert {"ask_paper", "summarize_paper", "search_papers", "run_step", "read_output"} <= set(tools)
    assert "attention.pdf" in text(res[0])
    assert '"indexed"' in text(res[1])
    assert "28.4" in text(res[2]) and "p. 1" in text(res[2])
    assert is_error(res[3]) and "only files inside out/" in text(res[3])      # refused, with the real reason
    assert is_error(res[4]) and "no PDF matching" in text(res[4])