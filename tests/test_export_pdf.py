import subprocess
import pytest
from pipeline import export_pdf as pdf


class R:
    def __init__(self, rc, out="", err=""):
        self.returncode, self.stdout, self.stderr = rc, out, err


def test_silent_tectonic_failure_is_retried_verbosely_and_logged(tmp_path, monkeypatch):
    tex = tmp_path / "paper.tex"
    tex.write_text("\\documentclass{article}\\begin{document}x\\end{document}")
    monkeypatch.setattr(pdf, "find_engine", lambda: "tectonic")
    calls = []

    def fake(cmd, cwd=None, **k):
        calls.append(cmd)
        return R(1) if "--print" not in cmd else R(1, "", "error: paper.tex:7: Undefined control sequence")
    monkeypatch.setattr(pdf.subprocess, "run", fake)
    with pytest.raises(RuntimeError) as e:
        pdf.compile_latex(tex)
    assert "Undefined control sequence" in str(e.value) and "exit code 1" in str(e.value)
    assert "--print" in calls[1] and (tmp_path / "latex_build.log").read_text().count("Undefined") == 1


def test_failure_message_for_non_silent_engine(tmp_path, monkeypatch):
    tex = tmp_path / "paper.tex"
    tex.write_text("x")
    monkeypatch.setattr(pdf, "find_engine", lambda: "pdflatex")
    monkeypatch.setattr(pdf.subprocess, "run", lambda cmd, cwd=None, **k: R(1, "! LaTeX Error: File `foo.sty' not found.\n"))
    with pytest.raises(RuntimeError, match="foo.sty"):
        pdf.compile_latex(tex)


def test_windows_startup_crash_gets_a_clear_hint(tmp_path, monkeypatch):
    tex = tmp_path / "paper.tex"
    tex.write_text("x")
    monkeypatch.setattr(pdf, "find_engine", lambda: "tectonic")
    monkeypatch.setattr(pdf.subprocess, "run", lambda cmd, cwd=None, **k: R(3221225785))
    with pytest.raises(RuntimeError, match="crashed on startup.*0xC0000139"):
        pdf.compile_latex(tex)