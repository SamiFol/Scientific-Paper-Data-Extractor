"""Cross-question memory. Stores notes written WITHOUT gold feedback (reflection or raw trajectory summary)."""
import re


def _tok(s):
    return set(re.findall(r"[a-z0-9]+", s.lower()))


class Memory:
    def __init__(self, k=3):
        self.k, self.notes = k, []          # notes: [{"q": question, "text": note}]

    def add(self, question, text):
        if text and text.strip():
            self.notes.append({"q": question, "text": text.strip()})

    def retrieve(self, question, mode="relevance"):
        """Top-k notes: 'relevance' = token overlap with the question (ties -> newer), 'recency' = last k."""
        if mode == "recency":
            return [n["text"] for n in self.notes[-self.k:]]
        qt = _tok(question)
        scored = [(len(qt & _tok(n["q"] + " " + n["text"])) / (len(qt | _tok(n["q"])) or 1), i, n["text"])
                  for i, n in enumerate(self.notes)]
        return [t for s, _, t in sorted(scored, reverse=True)[:self.k] if s > 0]

    def __len__(self):
        return len(self.notes)
