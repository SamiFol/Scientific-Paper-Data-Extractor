# Claims vs. evidence

| # | Claim | Section | Source | Status | Note |
|---|---|---|---|---|---|
| 1 | The Transformer architecture replaced recurrent bottleneck architectures with multi-head self-attention, enabling massive parallelization. | Introduction | [Vaswani et al., 2017] / none | verified | Matches the source paper's abstract and contributions. |
| 2 | CoT prompting improved performance on GSM8K, achieving 56.9% accuracy. | Abstract | [Wei et al., 2022] + Table 2, page 21 / none | verified | Matches the source paper's results. |
| 3 | ReAct achieved a 71% success rate on ALFWorld. | Abstract | [Yao et al., 2023] + Table 3, page 8 / none | verified | Matches the source paper's results. |
| 4 | Toolformer achieved 40.4% accuracy on ASDiv. | Abstract | [Schick et al., 2023] + Table 4, page 6 / none | verified | Matches the source paper's results. |
| 5 | Generative agents achieved a 29.89 TrueSkill believability rating. | Abstract | [Park et al., 2023] + Figure 8, page 14 / none | verified | Matches the source paper's results. |
| 6 | RCTA framework treats API interactions as first-class memory objects (ac, ic, r). | Abstract | own experiment | hypothesis | Proposed framework mechanism. |
| 7 | RCTA targets a 20% reduction in redundant API calls. | Abstract | own experiment | hypothesis | Proposed performance goal. |
| 8 | Transformer achieved 28.4 BLEU on WMT 2014 English-to-German. | Related Work | [Vaswani et al., 2017] + Table 2, page 8 / none | verified | Matches the source paper's results. |
| 9 | Toolformer achieved 44.0% accuracy on MAWPS compared to 19.8% for GPT-3. | Related Work | [Schick et al., 2023] + Table 4, page 6 / none | verified | Matches the source paper's results. |

## Abstract/Conclusion mismatches

- The Abstract introduces the framework as 'Recursive Cognitive Tool-Agent (RCTA)', but the Conclusion refers to it as 'NeuroSymbolic-ReAct Agent (NSRA)'.
- The Conclusion claims performance parity of a 13B model with 540B models, which is not mentioned in the Abstract or the Method section.
