"""Literature agent: resolve missing related work via arXiv/DBLP, build refs.bib and out/reading_list.md.
Only entries that were actually resolved (title + authors + year from a real record) go into refs.bib."""
import json
import re
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

from pipeline import config
from pipeline.agents.extractor import load_all
from pipeline.common import bibkey

ATOM = "{http://www.w3.org/2005/Atom}"
UA = {"User-Agent": "paper_project/1.0 (research tool)"}


_DISABLED = set()       # sources that failed for good in this run (e.g. DBLP behind a bot check)
RETRY_WAIT = 2          # seconds; doubles after each retry


def _ssl_context():
    """Trust the certifi CA bundle (plain Python on Windows/conda often lacks usable CA certificates)."""
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except Exception:
        return ssl.create_default_context()


def _get(url, timeout=20, tries=3):
    """GET -> bytes. Retries 429/5xx with a short wait; errors name the HTTP status."""
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=timeout, context=_ssl_context()) as r:
                return r.read()
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 502, 503, 504) and i < tries - 1:
                time.sleep(RETRY_WAIT * 2 ** i)
                continue
            raise RuntimeError(f"HTTP {e.code} {e.reason}") from e


def fetch(url, timeout=20):
    """GET url -> text; the only text network call (tests replace it)."""
    return _get(url, timeout).decode("utf-8", "replace")


def clean_query(name):
    """'Reflexion (Shinn et al., 2023)' -> 'Reflexion' (author/year notes hurt the search)."""
    return re.sub(r"\s+", " ", re.sub(r"\(.*?\)", " ", name)).strip() or name


def _tokens(s):
    return set(re.findall(r"[a-z0-9]+", s.lower()))


def title_match(a, b, thr=0.6):
    """Token Jaccard similarity >= thr."""
    ta, tb = _tokens(a), _tokens(b)
    return bool(ta and tb) and len(ta & tb) / len(ta | tb) >= thr


def parse_arxiv(xml_text):
    out = []
    for e in ET.fromstring(xml_text).findall(f"{ATOM}entry"):
        aid = (e.findtext(f"{ATOM}id") or "").rsplit("/abs/", 1)[-1]
        out.append({"title": " ".join((e.findtext(f"{ATOM}title") or "").split()),
                    "authors": [a.findtext(f"{ATOM}name") for a in e.findall(f"{ATOM}author")],
                    "year": int((e.findtext(f"{ATOM}published") or "0")[:4]) or None,
                    "venue": "arXiv", "arxiv_id": re.sub(r"v\d+$", "", aid),
                    "url": f"https://arxiv.org/abs/{re.sub(r'v\d+$', '', aid)}", "source": "arxiv"})
    return [x for x in out if x["title"] and x["authors"] and x["year"]]


def parse_dblp(json_text):
    try:
        data = json.loads(json_text)
    except ValueError:
        raise ValueError(f"DBLP did not return JSON (got {json_text[:60]!r})") from None
    hits = data.get("result", {}).get("hits", {}).get("hit", [])
    out = []
    for h in hits:
        i = h.get("info", {})
        au = i.get("authors", {}).get("author", [])
        au = [au] if isinstance(au, dict) else au
        names = [re.sub(r"\s+\d{4}$", "", a.get("text", "")) for a in au]     # DBLP disambiguation digits
        out.append({"title": i.get("title", "").rstrip("."), "authors": names,
                    "year": int(i["year"]) if i.get("year", "").isdigit() else None,
                    "venue": i.get("venue") if isinstance(i.get("venue"), str) else ", ".join(i.get("venue", [])),
                    "url": i.get("ee") or i.get("url"), "arxiv_id": None, "source": "dblp"})
    return [x for x in out if x["title"] and x["authors"] and x["year"]]


def search(query, n=5):
    """Candidates from arXiv then DBLP. A failing source is skipped; DBLP's bot check disables it for the run."""
    q = urllib.parse.quote(clean_query(query))
    found = []
    for url, parser in ((f"https://export.arxiv.org/api/query?search_query=all:{q}&max_results={n}", parse_arxiv),
                        (f"https://dblp.org/search/publ/api?q={q}&format=json&h={n}", parse_dblp)):
        host = url.split("/")[2]
        if host in _DISABLED:
            continue
        try:
            found += parser(fetch(url))
        except ValueError as e:                  # HTML instead of JSON/XML: bot check, will not fix itself
            _DISABLED.add(host)
            print(f"  [literature] {host} disabled for this run: {str(e)[:70]} (using the other source)")
        except Exception as e:
            hint = " (fix: pip install -U certifi)" if "CERTIFICATE_VERIFY_FAILED" in str(e) else ""
            print(f"  [literature] {host} unavailable: {str(e)[:100]}{hint}")
    return found


def resolve(name):
    """First candidate whose title matches `name`, else None (never guess)."""
    return next((c for c in search(name) if title_match(clean_query(name), c["title"])), None)


def sheet_entry(f):
    """Entry from a sheet's own metadata (read from the PDF); None if title/authors/year are missing."""
    authors = [a.get("name", "") if isinstance(a, dict) else str(a) for a in (f.get("authors") or [])]
    authors = [a.replace("∗", "").replace("†", "").strip() for a in authors if a]
    if not (f.get("title") and authors and isinstance(f.get("year"), int)):
        return None
    aid = f.get("arxiv_id")
    return {"label": f.get("cite_key"), "title": f["title"], "authors": authors, "year": f["year"], "venue": f.get("venue") or "",
            "arxiv_id": aid, "url": f"https://arxiv.org/abs/{aid}" if aid else None, "source": "pdf"}


def bibtex(key, e):
    f = lambda s: str(s).replace("{", "").replace("}", "")
    fields = [("title", "{" + f(e["title"]) + "}"), ("author", " and ".join(f(a) for a in e["authors"])),
              ("year", e["year"]), ("note", f"source: {e['source']}")]
    if e.get("label"):                  # draft citation label; export_latex maps label -> key through this
        fields.append(("citelabel", f(e["label"])))
    if e.get("venue"):
        fields.insert(2, ("howpublished", f(e["venue"])))
    if e.get("url"):
        fields.append(("url", e["url"]))
    return f"@misc{{{key},\n" + ",\n".join(f"  {k} = {{{v}}}" for k, v in fields) + "\n}\n"


def existing(path):
    """(keys, normalized titles) already in the .bib, so re-runs add nothing twice."""
    if not path.exists():
        return set(), set()
    t = path.read_text(encoding="utf-8")
    return (set(re.findall(r"@\w+\s*\{\s*([^,\s]+)\s*,", t)),
            {" ".join(sorted(_tokens(x))) for x in re.findall(r"title\s*=\s*\{+(.*?)\}+\s*,", t, re.S)})


def reading_list(resolved, unresolved, downloaded):
    lines = ["# Reading list (generated; verify before citing)\n", "## Found - add these PDFs to papers/ and re-run\n"]
    for e in resolved:
        mark = "downloaded" if e["title"] in downloaded else "download manually"
        lines.append(f"- {', '.join(e['authors'][:3])} ({e['year']}). {e['title']}. {e['url'] or ''} [{mark}]")
    lines += ["", "## Not found automatically - search by hand (NOT added to refs.bib)\n"]
    lines += [f"- {u}  (try https://scholar.google.com/scholar?q={urllib.parse.quote(u)})" for u in unresolved]
    return "\n".join(lines) + "\n"


def download_pdf(e):
    """Save an arXiv PDF into papers/; returns True on success."""
    if not e.get("arxiv_id"):
        return False
    try:
        data = _get(f"https://arxiv.org/pdf/{e['arxiv_id']}", timeout=60)
        if not data.startswith(b"%PDF"):
            return False
        (config.PAPERS_DIR / f"{e['arxiv_id'].replace('/', '_')}.pdf").write_bytes(data)
        return True
    except Exception as ex:
        print(f"  [literature] download failed for {e['arxiv_id']}: {str(ex)[:80]}")
        return False


def run(download=False):
    config.ensure_dirs()
    analysis = json.loads(config.ANALYSIS_FILE.read_text(encoding="utf-8")) if config.ANALYSIS_FILE.exists() else {}
    wanted = list(analysis.get("missing_related_work", []))
    print(f"[lit] resolving {len(wanted)} missing works + {len(load_all())} sheet entries")
    bib_path = config.ROOT / "refs.bib"
    have, have_titles = existing(bib_path)
    entries, resolved, unresolved, downloaded = [], [], [], set()

    for f in load_all():                                   # papers we already hold: metadata from the PDF
        e = sheet_entry(f)
        if e:
            entries.append(e)
    for name in wanted:
        e = resolve(name)
        if not e:
            unresolved.append(name)
            continue
        resolved.append(e)
        entries.append(e)
        if download and download_pdf(e):
            downloaded.add(e["title"])

    out, used = [], set(have)
    for e in entries:
        tk = " ".join(sorted(_tokens(e["title"])))
        if tk in have_titles:
            continue
        have_titles.add(tk)
        base = bibkey(e["authors"][0], e["year"])
        key, k = base, 1
        while key in used:                                  # same key + same title = already present
            k += 1
            key = f"{base}{chr(96 + k)}"
        used.add(key)
        out.append(bibtex(key, e))
    if out:
        with bib_path.open("a", encoding="utf-8") as fh:
            fh.write(("\n" if bib_path.exists() and bib_path.stat().st_size else "") + "\n".join(out))
    (config.OUT_DIR / "reading_list.md").write_text(reading_list(resolved, unresolved, downloaded), encoding="utf-8")
    print(f"  refs.bib: +{len(out)} entries; reading list: {len(resolved)} found, {len(unresolved)} unresolved "
          f"-> {config.OUT_DIR / 'reading_list.md'}")
    return {"added": len(out), "resolved": resolved, "unresolved": unresolved}