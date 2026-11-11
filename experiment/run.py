"""Run the experiment: conditions x seeds x questions -> JSONL logs (never results.json; see analyze.py).
  python -m experiment.run --data data/hotpot_dev_distractor_v1.json --pilot --n 10     # debug on the pilot split
  python -m experiment.run --lock                                                        # human: freeze the preregistration
  python -m experiment.run --data data/hotpot_dev_distractor_v1.json                     # main run (needs the lock)
"""
import argparse
import hashlib
import json
import sys
from pathlib import Path

from pipeline import config, prompts
from experiment import data, metrics
from experiment.agent import run_episode
from experiment.conditions import CONDITIONS
from experiment.memory import Memory

HERE = Path(__file__).parent
PREREG = Path(config.ROOT) / "docs" / "preregistration.md"
LOCK = HERE / "prereg_lock.json"
SEEDS = (1, 2, 3)
AVG_CALLS = {"react": 5, "react_mem": 6, "react_mem_noreflect": 5, "react_mem_recency": 6}
AVG_TOK_IN, AVG_TOK_OUT = 900, 120          # rough per-call averages, used ONLY for the cost estimate


def _sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def _prompts_sha():
    """Hash of the experiment's prompt files: changing a prompt after the lock invalidates the run."""
    files = sorted(Path(prompts.PROMPTS_DIR).glob("experiment_*.md"))
    return hashlib.sha256(b"".join(f.read_bytes() for f in files)).hexdigest()


def write_lock():
    if not PREREG.exists():
        raise SystemExit(f"{PREREG} not found")
    LOCK.write_text(json.dumps({"prereg_sha256": _sha(PREREG), "prompts_sha256": _prompts_sha()}, indent=2),
                    encoding="utf-8")
    print(f"locked {PREREG} and prompts/experiment_*.md -> {LOCK}")


def check_lock():
    """Main runs require an unchanged preregistration."""
    if not LOCK.exists():
        raise SystemExit("No prereg lock. Fill docs/preregistration.md, then run: python -m experiment.run --lock")
    lock = json.loads(LOCK.read_text())
    if lock["prereg_sha256"] != _sha(PREREG):
        raise SystemExit("docs/preregistration.md changed after the lock. Restore it, or re-lock and report the change.")
    if lock.get("prompts_sha256") != _prompts_sha():
        raise SystemExit("prompts/experiment_*.md changed after the lock. Restore them, or re-lock and report the change.")


def estimate(n_q, conditions, seeds, model, prices):
    calls = sum(n_q * len(seeds) * AVG_CALLS[c] for c in conditions)
    cost = metrics.cost_usd(prices, model, calls * AVG_TOK_IN, calls * AVG_TOK_OUT)
    return calls, cost


def log_path(outdir, split, cname, seed):
    return Path(outdir) / split / f"{cname}_seed{seed}.jsonl"


def _load_done(path):
    if not path.exists():
        return []
    rows = []
    for ln in path.read_text(encoding="utf-8").splitlines():
        try:
            rows.append(json.loads(ln))
        except json.JSONDecodeError:
            pass                                    # a torn last line after a crash; episode is simply redone
    return rows


def run_condition(questions, cname, seed, call, outdir, split, model, prices=None):
    """Run (or resume) one condition x seed. Each finished episode is appended and flushed immediately."""
    cond, path = CONDITIONS[cname], log_path(outdir, split, cname, seed)
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = _load_done(path)
    done = {r["qid"] for r in rows}
    memory = Memory() if cond["memory"] else None
    for r in rows:                                  # resume: rebuild memory from logged notes, in order
        if memory is not None:
            memory.add(r["question"], r.get("note"))
    todo = [q for q in data.order(questions, seed) if q["_id"] not in done]
    print(f"[run] {split}/{cname}/seed{seed}: {len(done)} done, {len(todo)} to go")
    with path.open("a", encoding="utf-8") as fh:
        for item in todo:
            rec = run_episode(item, cond, memory, call)
            rec.update(qid=item["_id"], split=split, condition=cname, seed=seed, model=model,
                       em=metrics.em(rec["pred"], item["answer"]), f1=metrics.f1(rec["pred"], item["answer"]),
                       redundancy_action=metrics.redundancy_repeat_action(rec["actions"]),
                       redundancy_paragraph=metrics.redundancy_repeat_paragraph(rec["titles"]),
                       cost_usd=metrics.cost_usd(prices or {}, model, rec["tokens_in"], rec["tokens_out"]))
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
            fh.flush()


def make_call(model):
    from pipeline import llm
    config.FALLBACK_MODELS = []                     # one model for the whole experiment; fail loudly instead

    def call(prompt, system):
        return llm.call(model, prompt, system, temperature=0.0, max_tokens=400)
    return call


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--data", help="hotpot_dev_distractor_v1.json")
    p.add_argument("--pilot", action="store_true", help="run on the 50-question pilot split (no lock needed)")
    p.add_argument("--n", type=int, help="use only the first n questions of the split (smoke test)")
    p.add_argument("--conditions", nargs="+", default=list(CONDITIONS), choices=list(CONDITIONS))
    p.add_argument("--seeds", nargs="+", type=int, default=list(SEEDS))
    p.add_argument("--model", default=config.MODEL_SMART)
    p.add_argument("--out", default=str(HERE / "runs"))
    p.add_argument("--yes", action="store_true", help="skip the cost confirmation")
    p.add_argument("--lock", action="store_true", help="freeze docs/preregistration.md and exit")
    a = p.parse_args(argv)
    if a.lock:
        write_lock()
        return 0
    if not a.data:
        raise SystemExit("--data is required")
    split = "pilot" if a.pilot else "main"
    if split == "main":
        check_lock()
    pilot, main_q = data.split(data.load(a.data))
    qs = (pilot if a.pilot else main_q)[:a.n] if a.n else (pilot if a.pilot else main_q)
    prices = metrics.load_prices(HERE / "prices.json")
    calls, cost = estimate(len(qs), a.conditions, a.seeds, a.model, prices)
    print(f"[run] {len(qs)} questions x {len(a.seeds)} seeds x {len(a.conditions)} conditions ~ {calls} LLM calls; "
          f"estimated cost: {'unknown (add model to prices.json)' if cost is None else f'${cost:.2f}'}")
    if not a.yes and input("Proceed? [y/N] ").strip().lower() != "y":
        return 1
    config.require_api_key()
    call = make_call(a.model)
    for seed in a.seeds:
        for c in a.conditions:
            run_condition(qs, c, seed, call, a.out, split, a.model, prices)
    print(f"[run] done. Next: python -m experiment.analyze")
    return 0


if __name__ == "__main__":
    sys.exit(main())
