import pytest
from pipeline import prompts


def test_load_fills_variables_and_keeps_json_braces(tmp_path, monkeypatch):
    monkeypatch.setattr(prompts, "PROMPTS_DIR", tmp_path)
    (tmp_path / "t.md").write_text('Hello {{NAME}}.\nReply {"a": {"b": 1}}\n')
    assert prompts.load("t", name="Bob") == 'Hello Bob.\nReply {"a": {"b": 1}}'


def test_missing_and_unused_variables_fail(tmp_path, monkeypatch):
    monkeypatch.setattr(prompts, "PROMPTS_DIR", tmp_path)
    (tmp_path / "t.md").write_text("Hello {{NAME}}")
    with pytest.raises(KeyError, match="needs"):
        prompts.load("t")
    with pytest.raises(KeyError, match="no placeholder"):
        prompts.load("t", name="x", other="y")


def test_global_rules_loaded_from_file():
    from pipeline.rules import GLOBAL_RULES
    assert GLOBAL_RULES.startswith("GLOBAL RULES") and "NEVER invent" in GLOBAL_RULES


def test_every_prompt_file_is_used_and_every_load_has_a_file():
    import re
    from pathlib import Path
    root = Path(__file__).resolve().parent.parent
    code = "\n".join(p.read_text(encoding="utf-8") for d in ("pipeline", "experiment", "mcp_server") for p in (root / d).rglob("*.py"))
    used = set(re.findall(r'prompts\.load\(\s*"([a-z0-9_]+)"', code))
    used |= {"writer_type_position", "writer_type_empirical",                       # loaded with an f-string
             "analyst_outline_position", "analyst_outline_empirical"}               # loaded via a conditional
    files = {p.stem for p in (root / "prompts").glob("*.md")}
    assert used == files, f"unused: {files - used}; missing: {used - files}"


def test_prompt_placeholders_are_uppercase_words():
    import re
    from pathlib import Path
    for p in (Path(__file__).resolve().parent.parent / "prompts").glob("*.md"):
        for tok in re.findall(r"\{\{(.*?)\}\}", p.read_text(encoding="utf-8")):
            assert re.fullmatch(r"[A-Z][A-Z0-9_]*", tok), f"{p.name}: bad placeholder {{{{{tok}}}}}"


def test_fields_block_renders_to_json_skeleton():
    block = ("title: text\nyear: whole number or null\nkind: one of a | b\nlevel: one of 2 | 3\n"
             "items: list, each with:\n  name: text\n  tags: list of text\nbox:\n  note: a short note\n")
    out = prompts.fields_to_json_skeleton(block)
    assert '"title": str' in out and '"year": int|null' in out and '"kind": "a"|"b"' in out
    assert '"level": 2|3' in out and '"items": [{' in out and '"tags": [str]' in out
    assert '"box": {' in out and '"note": "a short note"' in out


def test_prompt_files_are_text_not_json_and_keep_the_keys_the_code_reads(tmp_path):
    import re
    from pathlib import Path
    root = Path(__file__).resolve().parent.parent / "prompts"
    for name in ("extractor", "analyst", "reviewer"):
        raw = (root / f"{name}.md").read_text(encoding="utf-8")
        assert "[fields]" in raw and '": ' not in raw          # no JSON braces/quotes in the file itself
    ex = prompts.load("extractor")
    for k in ("title", "authors", "year", "venue", "results", "claims_table",
              "limitations", "experiments", "method", "arxiv_id"):
        assert f'"{k}":' in ex
    an = prompts.load("analyst", global_rules="G", outline_spec="O")
    for k in ("paper_title", "number_verification", "novelty_statement", "framework_spec", "hypotheses",
              "evaluation_plan", "missing_related_work", "outline", "target_words", "paper_type_recommendation"):
        assert f'"{k}":' in an
    rv = prompts.load("reviewer", global_rules="G")
    for k in ("claims", "status", "abstract_conclusion_mismatches", "change_log", "human_items"):
        assert f'"{k}":' in rv