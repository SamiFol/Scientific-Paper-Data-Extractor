"""Shared regexes and helpers used by lint, gate and the LaTeX exporter."""
import hashlib
import re

# [Author et al., 2023] or [A, 2020; B, 2021]
CITE_RE = re.compile(r"\[([^\[\]]+?,\s*(?:\d{4}|n\.d\.)(?:\s*;[^\[\]]+)?)\]")
PLACEHOLDER_RE = re.compile(r"\[TODO|TODO:|Target venue|Author Name|Anonymous Author", re.I)


def norm(s):
    """Collapse whitespace."""
    return re.sub(r"\s+", " ", s).strip()


def cite_parts(group):
    """'A, 2020; B, 2021' -> ['[A, 2020]', '[B, 2021]'] (the cite_key format)."""
    return [f"[{norm(p)}]" for p in group.split(";")]


def strip_code(text):
    """Remove fenced code blocks (TikZ, listings)."""
    return re.sub(r"```.*?```", " ", text, flags=re.S)


def sha256(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def bibkey(first_author, year):
    """BibTeX key 'yao2023' from the first author's last name."""
    name = (first_author or "x").strip()
    last = name.split(",")[0] if "," in name else name.split()[-1]
    return re.sub(r"[^a-z0-9]", "", last.lower()) + str(year or "")
