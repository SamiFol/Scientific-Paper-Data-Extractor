import json
from pipeline import config
from pipeline import fixloop
from pipeline.common import sha256

SHEET = {"cite_key": "[Yao et al., 2023]", "results": [{"value": "71"}]}


def project(tmp_path):
    config.set_root(tmp_path)
    config.ensure_dirs()
    (config.EXTRACTED_DIR / "a.json").write_text(json.dumps(SHEET))
    (config.SECTIONS_DIR / "00_abstract.md").write_text("## Abstract\n\nShort.")
    (config.SECTIONS_DIR / "01_intro.md").write_text("## Intro\n\nIt reaches 93% [Yao et al., 2023].")
    (config.SECTIONS_DIR / "02_end.md").write_text("## End\n\nFine text here.")
    fixloop.rebuild([dict(SHEET)])
    config.DRAFT_FILE.write_text("# T\n\n" + config.DRAFT_FILE.read_text().split("\n", 2)[2])


def test_only_bad_section_rewritten_and_loop_stops(tmp_path, monkeypatch):
    project(tmp_path)
    calls = []

    def fake_call(model, contents, system, **k):
        calls.append(contents)
        return "## Intro\n\nIt reaches 71% [Yao et al., 2023]."

    def fake_review():
        d = config.DRAFT_FILE.read_text()
        config.REVIEW_FILE.write_text(json.dumps({"_draft_sha256": sha256(d), "claims": []}))
    monkeypatch.setattr(fixloop.llm, "call", fake_call)
    monkeypatch.setattr(fixloop.reviewer, "run", fake_review)
    config.REVIEW_FILE.write_text(json.dumps({"_draft_sha256": "x", "claims": []}))
    left = fixloop.run()
    assert len(calls) == 1 and "93%" in calls[0]            # only the bad section was sent
    assert "71%" in (config.SECTIONS_DIR / "01_intro.md").read_text()
    assert (config.SECTIONS_DIR / "02_end.md").read_text().endswith("Fine text here.")
    assert not [b for b in left if b.startswith("lint:")]
