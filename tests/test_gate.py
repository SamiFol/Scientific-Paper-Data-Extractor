import json
import pytest
from pipeline import config
from pipeline import gate
from pipeline.common import sha256

SHEET = {"cite_key": "[Yao et al., 2023]", "results": [{"value": "71"}]}
DRAFT = "# T\n\n## Abstract\n\nReAct scores 71% [Yao et al., 2023].\n\n## References\n\n- [Yao et al., 2023] Yao.\n"


def test_missing_review_blocks():
    b, _ = gate.evaluate(DRAFT, [SHEET], {}, None, "position")
    assert any("no review" in x for x in b)


def test_stale_review_blocks_and_fresh_passes():
    fresh = {"_draft_sha256": sha256(DRAFT), "claims": []}
    assert gate.evaluate(DRAFT, [SHEET], {}, fresh, "position")[0] == []
    stale = {"_draft_sha256": "x", "claims": []}
    assert any("stale" in x for x in gate.evaluate(DRAFT, [SHEET], {}, stale, "position")[0])


def test_unsupported_claim_and_novelty_warning():
    rev = {"_draft_sha256": sha256(DRAFT), "claims": [{"claim": "c", "status": "unsupported"}]}
    b, w = gate.evaluate(DRAFT, [SHEET], {"novelty_statement": {"distinguishable": False}}, rev, "position")
    assert any("unsupported" in x for x in b) and any("NOVELTY" in x for x in w)


def test_lint_blocker_from_number_not_in_source():
    bad = DRAFT.replace("71%", "88%")
    rev = {"_draft_sha256": sha256(bad), "claims": []}
    assert any("Cited numbers" in x for x in gate.evaluate(bad, [SHEET], {}, rev, "position")[0])


def test_run_raises_unless_forced(tmp_path):
    config.set_root(tmp_path)
    config.ensure_dirs()
    config.DRAFT_FILE.write_text(DRAFT, encoding="utf-8")
    config.EXTRACTED_DIR.mkdir(parents=True, exist_ok=True)
    (config.EXTRACTED_DIR / "a.json").write_text(json.dumps(SHEET), encoding="utf-8")
    with pytest.raises(gate.GateError):
        gate.run()
    gate.run(force=True)
