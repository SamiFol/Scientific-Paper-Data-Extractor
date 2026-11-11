import pytest
from pipeline import config
from pipeline import export_latex as ex
MD = ("# T\n\n**Author:** Jane Doe\n\n## Abstract\n\nText.\n\n## Intro\n\nSee [Yao et al., 2023].\n\n"
      "| x | y |\n|---|---|\n| 1 | 2 |\n\n## References\n\n- [Yao et al., 2023] Yao. ReAct. ICLR.\n")


def tpl(tmp_path, **cfg):
    d = tmp_path / "tpl"
    d.mkdir()
    (d / "venue.sty").write_text("% dummy style")
    (d / "venue.bst").write_text("% dummy bst")
    return d


def test_default_uses_resizebox_template_does_not(tmp_path):
    assert r"\resizebox" in ex.md_to_latex(MD)
    t = ex.load_template(tpl(tmp_path))
    out = ex.md_to_latex(MD, template=t)
    assert r"\resizebox" not in out and r"\usepackage{venue}" in out and "margin=" not in out


def test_anonymous_removes_author(tmp_path):
    out = ex.md_to_latex(MD, anonymous=True)
    assert "Jane Doe" not in out and "Anonymous Authors" in out


def test_template_files_copied_and_bib_used(tmp_path):
    config.set_root(tmp_path)
    (tmp_path / "refs.bib").write_text("@inproceedings{yao2023,\n title={ReAct}\n}\n")
    md = tmp_path / "p.md"
    md.write_text(MD)
    tex = ex.convert_file(md, tmp_path / "out" / "paper.tex", template_dir=tpl(tmp_path))
    text = tex.read_text()
    assert (tex.parent / "venue.sty").exists() and (tex.parent / "refs.bib").exists()
    assert r"\bibliography{refs}" in text and r"\bibliographystyle{venue}" in text
    assert r"\cite{yao2023}" in text


def test_bib_missing_key_fails(tmp_path):
    (tmp_path / "refs.bib").write_text("@article{other2020,\n title={x}\n}\n")
    with pytest.raises(ex.LatexExportError, match="unresolved"):
        ex.md_to_latex(MD, bib_file=tmp_path / "refs.bib")
