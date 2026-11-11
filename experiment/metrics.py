"""EM/F1 (official HotpotQA normalization), redundancy (two definitions), token and cost accounting."""
import json
import re
import string
from collections import Counter
from pathlib import Path


def normalize(s):
    s = s.lower()
    s = "".join(ch for ch in s if ch not in set(string.punctuation))
    s = re.sub(r"\b(a|an|the)\b", " ", s)
    return " ".join(s.split())


def em(pred, gold):
    return float(normalize(pred) == normalize(gold))


def f1(pred, gold):
    p, g = normalize(pred).split(), normalize(gold).split()
    common = Counter(p) & Counter(g)
    same = sum(common.values())
    if not p or not g or same == 0:
        return 0.0 if (p or g) and not (p == g) else float(p == g)
    prec, rec = same / len(p), same / len(g)
    return 2 * prec * rec / (prec + rec)


def redundancy_repeat_action(actions):
    """Def A: share of Search/Lookup actions identical (normalized) to an earlier one in the same episode."""
    acts = [(n, normalize(a)) for n, a in actions if n in ("Search", "Lookup")]
    return (len(acts) - len(set(acts))) / len(acts) if acts else 0.0


def redundancy_repeat_paragraph(titles):
    """Def B: share of successful Searches that return a paragraph already seen earlier in the episode."""
    t = [x for x in titles if x]
    return (len(t) - len(set(t))) / len(t) if t else 0.0


def est_tokens(text):
    """Rough token estimate (4 chars/token); logged as estimated, used only for cost."""
    return max(1, len(text) // 4)


def load_prices(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def cost_usd(prices, model, tokens_in, tokens_out):
    """USD for the call, or None if the model has no price entry (never guessed)."""
    p = prices.get(model)
    if not p or p.get("in") is None or p.get("out") is None:
        return None
    return (tokens_in * p["in"] + tokens_out * p["out"]) / 1e6
