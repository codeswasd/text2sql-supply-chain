"""BM25 retrieval over table docs, then one hop of relationship expansion so joins have both sides."""
import math
import re
from collections import Counter

TOKEN_RE = re.compile(r"[a-z0-9]+")
STOP = {"the", "a", "an", "of", "for", "in", "on", "to", "and", "or", "is", "are", "what", "which",
        "how", "many", "show", "me", "list", "by", "with", "each", "all", "do", "we", "have", "our"}


def tokenize(text: str) -> list:
    return [t for t in TOKEN_RE.findall(text.lower()) if t not in STOP]


class SchemaRetriever:
    def __init__(self, docs: dict, k1: float = 1.5, b: float = 0.75):
        self.docs = docs
        self.k1, self.b = k1, b
        self.tf = {name: Counter(tokenize(d.text())) for name, d in docs.items()}
        self.len = {name: sum(c.values()) for name, c in self.tf.items()}
        self.avg = sum(self.len.values()) / max(len(self.len), 1)
        df = Counter(t for c in self.tf.values() for t in c)
        n = len(docs)
        self.idf = {t: math.log(1 + (n - f + 0.5) / (f + 0.5)) for t, f in df.items()}

    def score(self, query: str) -> list:
        q = tokenize(query)
        out = []
        for name, tf in self.tf.items():
            s = 0.0
            for t in q:
                f = tf.get(t, 0)
                if f:
                    s += self.idf[t] * f * (self.k1 + 1) / (f + self.k1 * (1 - self.b + self.b * self.len[name] / self.avg))
            out.append((name, s))
        return sorted(out, key=lambda x: -x[1])

    def retrieve(self, query: str, k: int = 3, expand: bool = True) -> list:
        ranked = [n for n, s in self.score(query) if s > 0][:k]
        if not expand:
            return ranked
        # Add direct neighbours of the top hits only when they also matched the query,
        # so a join table is pulled in without flooding the prompt.
        scores = dict(self.score(query))
        extra = [r for n in ranked for r in sorted(self.docs[n].related) if r not in ranked and scores.get(r, 0) > 0]
        return ranked + list(dict.fromkeys(extra))
