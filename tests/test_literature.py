import json
from pipeline import config
from pipeline import export_latex as ex
from pipeline.agents import literature as lit

ARXIV = """<feed xmlns="http://www.w3.org/2005/Atom"><entry><id>http://arxiv.org/abs/2210.03629v3</id>
<title>ReAct: Synergizing Reasoning and Acting in Language Models</title><published>2022-10-06T00:00:00Z</published>
<author><name>Shunyu Yao</name></author><author><name>Jeffrey Zhao</name></author></entry></feed>"""


import pytest


@pytest.fixture(autouse=True)
def _reset_disabled():
    lit._DISABLED.clear()
    yield
    lit._DISABLED.clear()


def setup(tmp_path, monkeypatch, fetch):
    config.set_root(tmp_path)
    config.ensure_dirs()
    monkeypatch.setattr(lit, "fetch", fetch)


def fake_fetch(url):
    if "arxiv" in url:
        return ARXIV
    return json.dumps({"result": {"hits": {"hit": []}}})


def test_resolved_goes_to_bib_unresolved_does_not(tmp_path, monkeypatch):
    setup(tmp_path, monkeypatch, fake_fetch)
    config.ANALYSIS_FILE.write_text(json.dumps({"missing_related_work": [
        "ReAct: Synergizing Reasoning and Acting in Language Models", "Totally Invented Paper Name"]}))
    r = lit.run()
    bib = (tmp_path / "refs.bib").read_text()
    assert "ReAct" in bib and "Invented" not in bib and r["unresolved"] == ["Totally Invented Paper Name"]
    assert "Totally Invented" in (config.OUT_DIR / "reading_list.md").read_text()


def test_offline_still_writes_reading_list_and_is_idempotent(tmp_path, monkeypatch):
    def down(url):
        raise OSError("no network")
    setup(tmp_path, monkeypatch, down)
    (config.EXTRACTED_DIR / "a.json").write_text(json.dumps(
        {"cite_key": "[Yao et al., 2023]", "title": "ReAct", "authors": ["Shunyu Yao"], "year": 2023}))
    config.ANALYSIS_FILE.write_text(json.dumps({"missing_related_work": ["Some Paper"]}))
    lit.run()
    lit.run()                                                      # second run adds nothing
    bib = (tmp_path / "refs.bib").read_text()
    assert bib.count("@misc") == 1 and "citelabel = {[Yao et al., 2023]}" in bib
    assert "Some Paper" in (config.OUT_DIR / "reading_list.md").read_text()


def test_export_maps_label_through_citelabel(tmp_path):
    (tmp_path / "r.bib").write_text("@misc{xyz1,\n  title = {T},\n  citelabel = {[Yao et al., 2023]}\n}\n")
    md = "# T\n\n## Abstract\n\nA.\n\n## Intro\n\nSee [Yao et al., 2023].\n\n## References\n\n- [Yao et al., 2023] Yao.\n"
    assert r"\cite{xyz1}" in ex.md_to_latex(md, bib_file=tmp_path / "r.bib")


def test_ssl_context_uses_a_real_context():
    import ssl
    assert isinstance(lit._ssl_context(), ssl.SSLContext)


def test_get_retries_429_then_succeeds_and_names_status_on_failure(monkeypatch):
    import io
    import urllib.error
    monkeypatch.setattr(lit.time, "sleep", lambda s: None)
    calls = {"n": 0}

    class Resp(io.BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    def flaky(req, timeout=None, context=None):
        calls["n"] += 1
        if calls["n"] < 3:
            raise urllib.error.HTTPError(req.full_url, 429, "Too Many Requests", {}, None)
        return Resp(b"ok")
    monkeypatch.setattr(lit.urllib.request, "urlopen", flaky)
    assert lit._get("https://x.test") == b"ok" and calls["n"] == 3

    def forbidden(req, timeout=None, context=None):
        raise urllib.error.HTTPError(req.full_url, 403, "Forbidden", {}, None)
    monkeypatch.setattr(lit.urllib.request, "urlopen", forbidden)
    import pytest
    with pytest.raises(RuntimeError, match="HTTP 403"):
        lit._get("https://x.test")


def test_dblp_html_gives_a_clear_error_and_search_survives(monkeypatch, capsys):
    import pytest
    with pytest.raises(ValueError, match="did not return JSON"):
        lit.parse_dblp("<html>rate limited</html>")
    monkeypatch.setattr(lit, "fetch", lambda url: ARXIV if "arxiv" in url else "<html>blocked</html>")
    res = lit.search("ReAct: Synergizing Reasoning and Acting in Language Models")
    assert res and "did not return JSON" in capsys.readouterr().out


def test_clean_query_drops_author_notes():
    assert lit.clean_query("Reflexion (Shinn et al., 2023)") == "Reflexion"
    assert lit.clean_query("AutoGPT") == "AutoGPT"


def test_dblp_bot_check_is_reported_once_then_skipped(monkeypatch, capsys):
    hits = {"dblp": 0}

    def fetch(url):
        if "arxiv" in url:
            return ARXIV
        hits["dblp"] += 1
        return "<!doctype html><title>Making sure you're not a bot!</title>"
    monkeypatch.setattr(lit, "fetch", fetch)
    lit.search("ReAct: Synergizing Reasoning and Acting in Language Models")
    lit.search("Another query")
    out = capsys.readouterr().out
    assert hits["dblp"] == 1 and out.count("disabled for this run") == 1