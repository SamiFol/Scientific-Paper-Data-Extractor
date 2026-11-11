import json
from pipeline import config
from pipeline.agents import writer

OUTLINE = [{"id": 1, "title": "Introduction", "level": 2, "goal": "g", "key_points": ["k"], "papers": [], "target_words": 5},
           {"id": 2, "title": "Results", "level": 2, "goal": "g", "key_points": ["k"], "papers": [], "target_words": 5}]


def setup(tmp_path, monkeypatch):
    config.set_root(tmp_path)
    config.ensure_dirs()
    config.ANALYSIS_FILE.write_text(json.dumps({"paper_title": "T", "outline": OUTLINE}))
    (config.EXTRACTED_DIR / "a.json").write_text(json.dumps(
        {"cite_key": "[A, 2020]", "title": "t", "authors": ["A B"], "year": 2020}))
    seen = []

    def fake(model, contents, system, **k):
        seen.append(contents)
        return "## X\n\nSome words here for the section text ok."
    monkeypatch.setattr(writer.llm, "call", fake)
    return seen


def test_results_section_skipped_without_results_json(tmp_path, monkeypatch):
    setup(tmp_path, monkeypatch)
    writer.run("topic")
    assert "Results" not in "".join(p.name for p in config.SECTIONS_DIR.glob("*results*"))
    assert not list(config.SECTIONS_DIR.glob("*results*"))


def test_results_json_is_passed_to_writer(tmp_path, monkeypatch):
    seen = setup(tmp_path, monkeypatch)
    config.RESULTS_FILE.write_text('{"em": 0.4321}')
    writer.run("topic")
    assert any("0.4321" in p for p in seen) and list(config.SECTIONS_DIR.glob("*results*"))
