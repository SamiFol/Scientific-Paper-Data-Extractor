"""The ONLY writer of out/results.json. Reads the main-split JSONL logs; refuses incomplete runs.
  python -m experiment.analyze [--runs experiment/runs] [--allow-incomplete]"""
import argparse
import json
import random
import statistics as st
import sys
from collections import defaultdict
from pathlib import Path

from pipeline import config
from experiment.conditions import CONDITIONS

HERE = Path(__file__).parent
METRICS = ("em", "f1", "calls", "tokens_in", "tokens_out", "redundancy_action", "redundancy_paragraph")
PAIRS = (("react_mem", "react"), ("react_mem", "react_mem_noreflect"), ("react_mem", "react_mem_recency"))
BOOT = 10_000


def load(runs_dir, split="main"):
    rows = []
    for f in sorted((Path(runs_dir) / split).glob("*.jsonl")):
        for ln in f.read_text(encoding="utf-8").splitlines():
            try:
                rows.append(json.loads(ln))
            except json.JSONDecodeError:
                pass
    return rows


def paired_bootstrap(a, b, n_boot=BOOT, seed=0):
    """a, b: {qid: value} over the same questions. Returns mean diff (a-b), 95% percentile CI, and p(diff<=0)."""
    qids = sorted(set(a) & set(b))
    d = [a[q] - b[q] for q in qids]
    rng = random.Random(seed)
    means = sorted(st.fmean(rng.choices(d, k=len(d))) for _ in range(n_boot))
    return {"n": len(d), "diff": st.fmean(d), "ci95": [means[int(.025 * n_boot)], means[int(.975 * n_boot) - 1]],
            "p_le_0": sum(m <= 0 for m in means) / n_boot}


def summarize(rows, conditions):
    by = defaultdict(list)
    for r in rows:
        by[(r["condition"], r["seed"])].append(r)
    out, per_q = {}, {}
    for c in conditions:
        seeds = sorted(s for (cc, s) in by if cc == c)
        if not seeds:
            continue
        entry = {"seeds": seeds, "n_per_seed": {str(s): len(by[(c, s)]) for s in seeds}}
        for m in METRICS:
            per_seed = [st.fmean(r[m] for r in by[(c, s)]) for s in seeds]
            entry[m] = {"mean": st.fmean(per_seed), "std_across_seeds": st.stdev(per_seed) if len(per_seed) > 1 else None,
                        "per_seed": per_seed}
        costs = [r["cost_usd"] for s in seeds for r in by[(c, s)]]
        entry["cost_usd_total"] = None if any(x is None for x in costs) else sum(costs)
        entry["models"] = sorted({r["model"] for s in seeds for r in by[(c, s)]})
        out[c] = entry
        q = defaultdict(lambda: defaultdict(list))
        for s in seeds:
            for r in by[(c, s)]:
                for m in ("em", "f1"):
                    q[m][r["qid"]].append(r[m])
        per_q[c] = {m: {k: st.fmean(v) for k, v in q[m].items()} for m in q}
    return out, per_q


def run(runs_dir=None, allow_incomplete=False, out_path=None):
    rows = load(runs_dir or HERE / "runs")
    if not rows:
        raise SystemExit("no main-split logs found; run experiment.run first")
    summary, per_q = summarize(rows, list(CONDITIONS))
    sizes = {n for e in summary.values() for n in e["n_per_seed"].values()}
    if len(sizes) > 1 and not allow_incomplete:
        raise SystemExit(f"incomplete runs (episodes per seed differ: {sorted(sizes)}); finish them or pass --allow-incomplete")
    comps = {}
    for a, b in PAIRS:
        if a in per_q and b in per_q:
            comps[f"{a}_vs_{b}"] = {m: paired_bootstrap(per_q[a][m], per_q[b][m]) for m in ("em", "f1")}
    lock = HERE / "prereg_lock.json"
    res = {"split": "main", "conditions": summary, "paired_bootstrap": comps, "bootstrap_resamples": BOOT,
           "prereg_sha256": json.loads(lock.read_text())["prereg_sha256"] if lock.exists() else None,
           "complete": len(sizes) <= 1}
    path = Path(out_path or config.RESULTS_FILE)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(res, indent=2), encoding="utf-8")
    print(f"[analyze] wrote {path}")
    return res


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs")
    ap.add_argument("--allow-incomplete", action="store_true")
    a = ap.parse_args()
    run(a.runs, a.allow_incomplete)
    sys.exit(0)
