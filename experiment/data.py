"""HotpotQA (distractor setting) loading and the fixed pilot/main split."""
import json
import random
from pathlib import Path

N_MAIN = 500
N_PILOT = 50
SPLIT_SEED = 1234      # fixed: the split must never depend on the run seed


def load(path):
    """Read the official hotpot_dev_distractor_v1.json (list of dicts)."""
    items = json.loads(Path(path).read_text(encoding="utf-8"))
    need = {"_id", "question", "answer", "context"}
    bad = [i for i in items[:50] if not need <= set(i)]
    if bad:
        raise ValueError("not a HotpotQA distractor file: missing keys " + str(need - set(bad[0])))
    return items


def split(items, n_main=N_MAIN, n_pilot=N_PILOT):
    """Deterministic, disjoint (pilot, main) lists; pilot is for debugging/tuning only."""
    if len(items) < n_main + n_pilot:
        raise ValueError(f"need {n_main + n_pilot} questions, got {len(items)}")
    ids = sorted(i["_id"] for i in items)
    random.Random(SPLIT_SEED).shuffle(ids)
    pilot_ids, main_ids = set(ids[:n_pilot]), set(ids[n_pilot:n_pilot + n_main])
    by_id = {i["_id"]: i for i in items}
    return ([by_id[i] for i in sorted(pilot_ids)], [by_id[i] for i in sorted(main_ids)])


def order(questions, seed):
    """Per-seed question order (memory conditions depend on order, so it varies by seed)."""
    qs = list(questions)
    random.Random(seed).shuffle(qs)
    return qs
