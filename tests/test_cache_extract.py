import json
from pipeline import config
from pipeline import cache
from pipeline.agents import extractor


def setup(tmp_path):
    config.set_root(tmp_path)
    config.ensure_dirs()


def test_hash_change_warns_and_fresh_clears(tmp_path, capsys):
    setup(tmp_path)
    config.ANALYSIS_FILE.write_text("{}")
    cache.save("topic")
    assert not cache.check("topic")
    config.PLAN_FILE.write_text("budget 5")
    assert cache.check("topic") and "re-run with --fresh" in capsys.readouterr().out
    (config.SECTIONS_DIR / "01_a.md").write_text("x")
    cache.fresh()
    assert not config.ANALYSIS_FILE.exists() and not list(config.SECTIONS_DIR.glob("*.md"))


def test_cite_key_collisions_get_suffix(tmp_path):
    setup(tmp_path)
    for n in ("a", "b", "c"):
        (config.EXTRACTED_DIR / f"{n}.json").write_text(json.dumps(
            {"authors": ["A Yao", "B Zhu", "C Lee"], "year": 2023, "title": n}))
    keys = [f["cite_key"] for f in extractor.load_all()]
    assert keys == ["[Yao et al., 2023]", "[Yao et al., 2023b]", "[Yao et al., 2023c]"]


def test_extract_records_model_and_strict(tmp_path, monkeypatch):
    setup(tmp_path)
    (config.PAPERS_DIR / "p.pdf").write_bytes(b"%PDF-1.4")
    sheet = json.dumps({"title": "T", "authors": ["A B"], "year": 2020})

    def fake(*a, **k):
        extractor.llm.LAST_MODEL = "groq:llama"
        return sheet
    monkeypatch.setattr(extractor.llm, "call", fake)
    monkeypatch.setattr(extractor.llm, "pdf_truncated", lambda p: True)
    monkeypatch.setattr(extractor.llm, "pdf_part", lambda p: "pdf")
    import pytest
    with pytest.raises(extractor.ExtractError):
        extractor.run(strict=True)
    extractor.run()
    data = json.loads((config.EXTRACTED_DIR / "p.json").read_text())
    assert data["extracted_by"] == "groq:llama" and data["truncated"] is True
