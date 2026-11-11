"""Regulile globale, folosite de analist, scriitor si revizor (aceleasi pentru toti)."""

GLOBAL_RULES = """GLOBAL RULES (mandatory):
1. NEVER invent results, numbers, ablation outcomes or observations. If something is not in the
   provided data, do not write it; write "we hypothesize" or "we plan to evaluate" instead.
   Forbidden unless real measurements are provided: "our results validate", "consistently
   outperforms/underperforms", "achieves parity with", "we observe that ...".
2. ONE framework name and ONE technical idea in the whole paper (see framework_spec). Never introduce
   alternative names or mechanisms that contradict it.
3. Every number taken from another paper must be traceable: cite_key + table/page + model size +
   setting. Never present another paper's result as our target or achievement.
4. No placeholders in the final text: no [TODO], no "Target venue", no author placeholder.
5. Every section has a distinct job and a distinct opening. Do not repeat openings or sentences."""
