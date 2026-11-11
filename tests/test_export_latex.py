import pytest
from pipeline import export_latex as ex
REFS = "\n## References\n\n- [Yao et al., 2023] Yao. ReAct. ICLR.\n"


def doc(body):
    return "# T\n\n## Abstract\n\nText.\n\n## Intro\n\n" + body + "\n" + REFS


def test_resolved_citation_becomes_cite():
    tex = ex.md_to_latex(doc("ReAct works [Yao et al., 2023]."))
    assert r"\cite{yao2023}" in tex and r"\begin{thebibliography}" in tex


def test_unresolved_citation_fails():
    with pytest.raises(ex.LatexExportError, match="Smith"):
        ex.md_to_latex(doc("See [Smith et al., 2020]."))


def test_todo_fails_unless_lenient():
    with pytest.raises(ex.LatexExportError, match="TODO"):
        ex.md_to_latex(doc("Missing [TODO: add result]."))
    assert r"\todo{" in ex.md_to_latex(doc("Missing [TODO: add result]."), strict=False)


def test_list_and_table_conversion():
    tex = ex.md_to_latex(doc("- a\n- b\n\n| x | y |\n|---|---|\n| 1 | 2 |"))
    assert r"\begin{itemize}" in tex and r"\begin{tabular}" in tex
