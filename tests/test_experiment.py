import json
import pytest
from experiment import analyze, data, metrics, run
from experiment.agent import run_episode
from experiment.conditions import CONDITIONS
from experiment.env import Env, parse_action
from experiment.memory import Memory

GOLD, SUPP = "ZZGOLDZZ", "ZZSUPPZZ"


def item(i=0):
    return {"_id": f"q{i}", "question": f"Who founded the company number {i}?", "answer": GOLD,
            "supporting_facts": [[SUPP, 0]], "type": "bridge", "level": "hard",
            "context": [["Acme Corp", ["Acme Corp was founded by a person.", "It makes anvils."]],
                        ["Bob", ["Bob is a person."]]]}


class Script:
    """Fake llm: Search[Acme Corp], then Finish[Bob]; records every prompt it receives."""
    def __init__(self):
        self.prompts = []

    def __call__(self, prompt, system):
        self.prompts.append(system + "\n" + prompt)
        if system.startswith("You review"):
            return "Search the company page first."
        return "Thought: look it up\nAction: Search[Acme Corp]" if "Observation" not in prompt \
            else "Thought: done\nAction: Finish[Bob]"


def test_no_gold_or_supporting_facts_reach_the_model_or_memory():
    call, mem = Script(), Memory()
    for name, cond in CONDITIONS.items():
        for i in range(3):
            run_episode(item(i), cond, mem if cond["memory"] else None, call)
    blob = "\n".join(call.prompts) + json.dumps(mem.notes)
    assert GOLD not in blob and SUPP not in blob and len(call.prompts) > 10


def test_env_has_no_gold_attributes():
    env = Env(item())
    assert GOLD not in str(vars(env)) and SUPP not in str(vars(env))


def test_conditions_differ_as_documented():
    c = CONDITIONS
    assert not c["react"]["memory"]
    assert c["react_mem"]["note"] == "reflection" and c["react_mem_noreflect"]["note"] == "trajectory"
    assert c["react_mem"]["retrieval"] == "relevance" and c["react_mem_recency"]["retrieval"] == "recency"


def test_reflection_costs_an_extra_call():
    a = run_episode(item(), CONDITIONS["react_mem"], Memory(), Script())
    b = run_episode(item(), CONDITIONS["react_mem_noreflect"], Memory(), Script())
    assert a["calls"] == b["calls"] + 1 and a["pred"] == "Bob"


def test_parse_action_and_env_lookup():
    assert parse_action("Thought: x\nAction: Search[Acme Corp]") == ("Search", "Acme Corp")
    env = Env(item())
    obs, title, _ = env.step(("Search", "acme corp"))
    assert title == "Acme Corp" and "founded" in obs
    assert "anvils" in env.step(("Lookup", "anvils"))[0]


def test_metrics():
    assert metrics.em("The Bob", "bob") == 1.0 and metrics.f1("big bob", "bob") == pytest.approx(2 / 3)
    assert metrics.redundancy_repeat_action([("Search", "A"), ("Search", "a"), ("Search", "B")]) == pytest.approx(1 / 3)
    assert metrics.redundancy_repeat_paragraph(["A", "A", None, "B"]) == pytest.approx(1 / 3)
    assert metrics.cost_usd({}, "m", 10, 10) is None and metrics.cost_usd({"m": {"in": 1, "out": 2}}, "m", 1e6, 1e6) == 3


def test_split_is_disjoint_and_deterministic():
    items = [item(i) | {"_id": f"id{i}"} for i in range(600)]
    p1, m1 = data.split(items)
    p2, m2 = data.split(items)
    assert [x["_id"] for x in m1] == [x["_id"] for x in m2]
    assert len(p1) == 50 and len(m1) == 500 and not {x["_id"] for x in p1} & {x["_id"] for x in m1}


def test_run_resume_and_analyze_only_writer(tmp_path, monkeypatch):
    qs = [item(i) | {"_id": f"q{i}"} for i in range(6)]
    call = Script()
    for seed in (1, 2):
        for c in ("react", "react_mem"):
            run.run_condition(qs[:3], c, seed, call, tmp_path, "main", "fake")
    n_before = len(call.prompts)
    run.run_condition(qs[:3], "react", 1, call, tmp_path, "main", "fake")      # resume: nothing left to do
    assert len(call.prompts) == n_before
    log = tmp_path / "main" / "react_seed1.jsonl"
    log.write_text(log.read_text() + '{"torn":')                               # simulated crash mid-write
    run.run_condition(qs[:3], "react", 1, call, tmp_path, "main", "fake")      # torn line ignored
    out = tmp_path / "results.json"
    res = analyze.run(tmp_path, out_path=out)
    assert res["complete"] and res["conditions"]["react"]["em"]["mean"] == 0.0     # pred Bob != gold
    assert "react_mem_vs_react" in res["paired_bootstrap"]
    log.write_text(log.read_text().splitlines()[0] + "\n")                      # now react/seed1 is incomplete
    with pytest.raises(SystemExit, match="incomplete"):
        analyze.run(tmp_path, out_path=tmp_path / "r2.json")


def test_paired_bootstrap_detects_clear_difference():
    a = {f"q{i}": 1.0 for i in range(50)}
    b = {f"q{i}": 0.0 for i in range(50)}
    r = analyze.paired_bootstrap(a, b, n_boot=500)
    assert r["diff"] == 1.0 and r["ci95"][0] > 0


def test_main_run_requires_lock(tmp_path, monkeypatch):
    monkeypatch.setattr(run, "LOCK", tmp_path / "none.json")
    with pytest.raises(SystemExit, match="lock"):
        run.check_lock()
