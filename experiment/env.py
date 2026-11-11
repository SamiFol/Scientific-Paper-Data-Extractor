"""ReAct environment over one HotpotQA question's 10 paragraphs.
The agent sees ONLY the question and observations. Gold answer and supporting_facts are never exposed."""
import re

MAX_OBS_CHARS = 1200


def _norm(s):
    return re.sub(r"[^a-z0-9 ]", "", s.lower()).strip()


class Env:
    def __init__(self, item):
        # keep only (title, sentences); drop everything else from the item, including the gold fields
        self.question = item["question"]
        self.paras = [(t, " ".join(s)) for t, s in item["context"]]
        self.seen_titles, self.last, self.finished, self.answer = set(), None, False, None

    def _find(self, entity):
        e = _norm(entity)
        exact = [p for p in self.paras if _norm(p[0]) == e]
        if exact:
            return exact[0]
        words = set(e.split())
        scored = sorted(((len(words & set(_norm(t).split())), t, txt) for t, txt in self.paras), reverse=True)
        return (scored[0][1], scored[0][2]) if scored and scored[0][0] > 0 else None

    def step(self, action):
        """action = (name, arg). Returns (observation, title_or_None, done). title feeds the redundancy metric."""
        name, arg = action
        if name == "Finish":
            self.finished, self.answer = True, arg
            return "Episode finished.", None, True
        if name == "Search":
            hit = self._find(arg)
            if not hit:
                titles = ", ".join(t for t, _ in self.paras[:5])
                return f"Could not find [{arg}]. Similar: {titles}.", None, False
            self.last = hit
            return hit[1][:MAX_OBS_CHARS], hit[0], False
        if name == "Lookup":
            if not self.last:
                return "No paragraph open; use Search first.", None, False
            sents = [s for s in re.split(r"(?<=[.!?])\s+", self.last[1]) if arg.lower() in s.lower()]
            return (" ".join(sents)[:MAX_OBS_CHARS] if sents else f"No mention of [{arg}] in the open paragraph."), None, False
        return "Invalid action. Use Search[entity], Lookup[keyword] or Finish[answer].", None, False


ACTION_RE = re.compile(r"(Search|Lookup|Finish)\[(.*?)\]", re.S)


def parse_action(text):
    """First well-formed action in the model output, else None."""
    m = ACTION_RE.search(text)
    return (m.group(1), m.group(2).strip()) if m else None
