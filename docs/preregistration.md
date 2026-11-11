# Preregistration: ReAct vs. ReAct + reflective memory on HotpotQA

Written BEFORE any main-split run. After `python -m experiment.run --lock` this file is frozen (its SHA-256 is
stored in `experiment/prereg_lock.json`; main runs refuse to start if it changed, and `results.json` records the hash).
Edit the "Decisions to confirm" section first, then lock.

## Question
Does adding cross-question memory with self-reflection to a ReAct agent improve multi-hop QA, under a bounded
per-episode context, and which component (reflection, relevance retrieval) carries the effect?

## Data
- HotpotQA, distractor setting, dev split (`hotpot_dev_distractor_v1.json`), 10 paragraphs per question.
- Split fixed by `experiment/data.py` (seed 1234): 50 pilot questions (debugging/tuning only, never reported as
  results) and 500 main questions, disjoint.
- The agent never sees the gold answer or `supporting_facts` (enforced by `tests/test_experiment.py`).

## Conditions (each differs from `react_mem` in exactly one respect, except the baseline)
| name | memory | note written after each episode | retrieval of notes |
|---|---|---|---|
| `react` | no | - | - |
| `react_mem` | yes | LLM reflection (no gold feedback) | relevance (token overlap), k=3 |
| `react_mem_noreflect` | yes | raw trajectory summary (no LLM) | relevance, k=3 |
| `react_mem_recency` | yes | LLM reflection | most recent 3 |

## Protocol
- One hosted model for all conditions (`--model`; fallback models are disabled, a failure stops the run).
- Temperature 0; max 8 steps per question; per-episode trajectory budget 6000 characters.
- 3 seeds (1, 2, 3). The seed changes the question ORDER (memory depends on order). Memory resets per condition x seed.
- Hosted models are not fully deterministic even at temperature 0; this is reported as a limitation, not hidden.

## Metrics
- Primary: Exact Match (official HotpotQA normalization). Secondary: F1.
- Cost: LLM calls per question (reflection calls included), estimated tokens (4 chars/token, labelled as estimates),
  USD only if the model has a price in `experiment/prices.json`, otherwise reported as unknown.
- Redundancy, two definitions: (A) share of Search/Lookup actions identical to an earlier one in the same episode;
  (B) share of successful searches returning a paragraph already seen in the same episode.

## Analysis
- Per condition: mean over seeds, std across seeds.
- Paired bootstrap over questions (per-question mean across seeds, 10,000 resamples, fixed RNG seed 0), 95% percentile CI,
  for `react_mem` vs. each of the other three conditions, on EM and F1.
- Primary hypothesis H1: `react_mem` EM > `react` EM. H2: `react_mem` EM > `react_mem_noreflect` EM.
  H3: `react_mem` EM > `react_mem_recency` EM. A hypothesis counts as supported only if the 95% CI excludes 0.
- Results are written only by `experiment/analyze.py`; an incomplete run is refused.

## Decisions to confirm before locking
- [ ] Model name for the main run: ______
- [ ] Prices entered in `experiment/prices.json` (or accepted as unknown)
- [ ] Budget in LLM calls accepted (printed by `python -m experiment.run`; about 36,000 for the full design)

## Reporting commitments
- Report all four conditions and all pre-specified comparisons, including null or negative ones.
- Pilot data are used only to debug the code and are not reported as results.
- Any deviation from this document is stated in the paper.
