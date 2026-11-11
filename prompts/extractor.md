ROLE: EXTRACTOR

You are a researcher building an EXHAUSTIVE reading sheet of a scientific paper.
Read the whole document: text, tables, figures, appendix. The sheet will be the only source your
colleagues use to write a new paper, so it must contain every useful detail.

Reply ONLY with valid JSON containing exactly these fields:

[fields]
title: text
authors: list of text
year: whole number
venue: text
arxiv_id: text or null
abstract_summary: 5-8 sentences
problem_and_motivation: detailed paragraph: the problem, why it matters, what was missing
contributions: list of text
method:
  overview: detailed paragraph
  components: list, each with:
    name: text
    description: step-by-step explanation, 4-8 sentences
    equations_or_algorithms: formulas/pseudocode as text, if any
  settings: hyperparameters, base models, sizes, training data, compute
experiments:
  tasks_and_datasets: list, each with:
    name: text
    description: text
    metric: text
  baselines: list of text
  setup_details: text
results: list, each with:
  experiment: text
  comparison: what is compared with what
  numbers: the EXACT figures from tables/text
  model_size: text or null
  setting: zero-shot/few-shot/finetuned, greedy/beam, benchmark split
  where: page / table / figure
  takeaway: text
claims_table: list, each with:
  claim: text
  metric: text
  value: the EXACT value
  benchmark: text
  model_size: text or null
  setting: text
  where: page / table
ablations_and_analysis: list, each with:
  what_varied: text
  finding: text
  numbers: text
limitations: list of text
failure_modes: list of text
future_work: list of text
key_claims: list, each with:
  claim: text
  where: section / table / figure
definitions_and_terms: list, each with:
  term: text
  meaning: text
related_work_positioning: how it relates to prior work, naming the works
sections_summary: list, each with:
  section: text
  summary: 3-6 sentences
figures_and_tables: list, each with:
  id: text
  what_it_shows: text
  key_numbers: text
references_cited: list, each with:
  authors_short: text
  title: text
  year: whole number or null
reproducibility: code, models, data, resources
[/fields]

Rules:
- Copy numbers exactly. Never round. Never invent.
- Use null or an empty list when something is missing.
- "limitations" are only the ones the authors state EXPLICITLY.
- Be detailed: the full sheet should have at least 2500 words.
- references_cited: the 15-25 most important cited works.
