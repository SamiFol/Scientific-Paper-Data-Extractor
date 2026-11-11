"""Load prompt texts from the prompts/ folder (plain text files, edit them without touching Python).
Placeholders look like {{NAME}} (UPPERCASE).
Output format is written as a readable field list between [fields] and [/fields]; load() turns it into the
JSON skeleton the model is asked to return, so the files stay plain text and the code still gets JSON."""
import os
import re
from pathlib import Path

PROMPTS_DIR = Path(os.getenv("PROMPTS_DIR") or Path(__file__).resolve().parent.parent / "prompts")
_VAR = re.compile(r"\{\{([A-Z][A-Z0-9_]*)\}\}")
_FIELDS = re.compile(r"^\[fields\]\n(.*?)^\[/fields\]\n?", re.S | re.M)
_SCALARS = {"text": "str", "whole number": "int", "number": "number", "yes/no": "bool",
            "list of text": "[str]", "list of cite_keys": "[cite_key]", "text or null": "str|null",
            "whole number or null": "int|null"}


def load(prompt, /, **values):
    """Read prompts/<prompt>.md and fill {{VARS}}. Fails if a variable is missing or unused (typo protection)."""
    path = PROMPTS_DIR / f"{prompt}.md"
    if not path.exists():
        raise FileNotFoundError(f"prompt file not found: {path}")
    text = path.read_text(encoding="utf-8").strip()
    wanted = set(_VAR.findall(text))
    given = {k.upper() for k in values}
    if wanted - given:
        raise KeyError(f"prompt '{prompt}' needs {sorted(wanted - given)}")
    if given - wanted:
        raise KeyError(f"prompt '{prompt}' has no placeholder for {sorted(given - wanted)}")
    text = _FIELDS.sub(lambda m: fields_to_json_skeleton(m.group(1)) + "\n", text)
    return _VAR.sub(lambda m: str(values[m.group(1)] if m.group(1) in values else values[m.group(1).lower()]), text)


def _scalar(value):
    """Readable type -> JSON skeleton value."""
    v = value.strip()
    if v in _SCALARS:
        return _SCALARS[v]
    if v.startswith("one of "):
        opts = [o.strip() for o in v[7:].split("|")]
        return "|".join(o if o.isdigit() else f'"{o}"' for o in opts)
    return '"' + v.replace('"', "'") + '"'            # anything else is a description of the value


def _parse(lines, i, indent):
    """-> (nodes, next_index); node = (key, value, children)."""
    nodes = []
    while i < len(lines):
        raw = lines[i]
        cur = len(raw) - len(raw.lstrip())
        if cur < indent:
            break
        key, _, value = raw.strip().partition(":")
        i += 1
        kids = []
        if i < len(lines) and len(lines[i]) - len(lines[i].lstrip()) > cur:
            kids, i = _parse(lines, i, len(lines[i]) - len(lines[i].lstrip()))
        nodes.append((key.strip(), value.strip(), kids))
    return nodes, i


def _render(nodes, depth):
    pad = "  " * (depth + 1)
    out = []
    for key, value, kids in nodes:
        if kids and value.startswith("list"):
            body = "[{\n" + _render(kids, depth + 1) + "\n" + pad + "}]"
        elif kids:
            body = "{\n" + _render(kids, depth + 1) + "\n" + pad + "}"
        else:
            body = _scalar(value)
        out.append(f'{pad}"{key}": {body}')
    return ",\n".join(out)


def fields_to_json_skeleton(block):
    """Readable field list -> JSON skeleton text, e.g. 'year: whole number' -> '"year": int'."""
    lines = [ln.rstrip() for ln in block.splitlines() if ln.strip() and not ln.strip().startswith("#")]
    nodes, _ = _parse(lines, 0, 0)
    return "{\n" + _render(nodes, 0) + "\n}"


def field_names(block):
    """All field names in a readable field list (used by tests to check the code's expected keys)."""
    return [ln.strip().partition(":")[0] for ln in block.splitlines() if ln.strip() and not ln.strip().startswith("#")]
