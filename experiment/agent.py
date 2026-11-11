"""ReAct agent (optionally with cross-question memory). `call(prompt, system) -> text` is injected."""
from experiment import metrics
from pipeline import prompts
from experiment.env import Env, parse_action

MAX_STEPS = 8
MAX_CTX_CHARS = 6000        # trajectory budget inside one episode; oldest steps are dropped first

SYSTEM = prompts.load("experiment_agent")
REFLECT_SYSTEM = prompts.load("experiment_reflect")


def _trajectory_text(steps):
    text = "\n".join(steps)
    while len(text) > MAX_CTX_CHARS and len(steps) > 2:
        steps = steps[:1] + steps[2:]        # keep the first step, drop the oldest after it
        text = "\n".join(steps)
    return text


def _prompt(question, notes, steps):
    mem = ("Lessons from earlier questions:\n" + "\n".join(f"- {n}" for n in notes) + "\n\n") if notes else ""
    return f"{mem}Question: {question}\n{_trajectory_text(steps)}\nThought:"


def run_episode(item, cond, memory, call, max_steps=MAX_STEPS):
    """-> record dict (no gold-based fields). Updates `memory` after the episode when the condition says so."""
    env = Env(item)
    notes = memory.retrieve(env.question, cond["retrieval"]) if cond["memory"] and memory is not None else []
    steps, actions, titles = [], [], []
    calls = tin = tout = 0
    for t in range(1, max_steps + 1):
        prompt = _prompt(env.question, notes, steps)
        out = call(prompt, SYSTEM)
        calls, tin, tout = calls + 1, tin + metrics.est_tokens(prompt + SYSTEM), tout + metrics.est_tokens(out)
        act = parse_action(out)
        thought = out.split("Action:")[0].strip()
        if act is None:
            steps.append(f"Thought: {thought}\nObservation: Invalid action. Use Search[...], Lookup[...] or Finish[...].")
            continue
        actions.append(act)
        obs, title, done = env.step(act)
        titles.append(title)
        steps.append(f"Thought: {thought}\nAction: {act[0]}[{act[1]}]\nObservation: {obs}")
        if done:
            break
    pred = env.answer if env.finished else ""
    note = None
    rec = {"question": env.question, "pred": pred, "finished": env.finished, "steps": len(steps),
           "actions": actions, "titles": titles}
    if cond["memory"] and memory is not None:
        if cond["note"] == "reflection":
            traj = _trajectory_text(steps)
            prompt = f"Question: {env.question}\n{traj}\nFinal answer given: {pred or '(none)'}\nAdvice:"
            note = call(prompt, REFLECT_SYSTEM)
            calls, tin, tout = calls + 1, tin + metrics.est_tokens(prompt + REFLECT_SYSTEM), tout + metrics.est_tokens(note)
        else:
            searched = ", ".join(a for n, a in actions if n == "Search") or "nothing"
            note = f"Searched: {searched}. Answered: {pred or '(none)'}."
        memory.add(env.question, note)
    rec.update(note=note, calls=calls, tokens_in=tin, tokens_out=tout, tokens_estimated=True)
    return rec
