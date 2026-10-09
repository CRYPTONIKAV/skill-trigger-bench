"""TF-IDF cosine similarity between skill descriptions (stdlib only)."""

from __future__ import annotations

import math
import re
from collections import Counter

STOPWORDS = frozenset(
    """a an and are as at be by can do does for from has have how i if in into is it its
    me my of on or our should so such than that the their them then there these this those
    to up use used uses using via was we what when whenever where which while who will with
    you your any all also not no only other more most just like e g eg etc skill skills
    claude agent user users ask asks asked want wants need needs help helps load always
    include includes including about over out new make makes""".split()
)


def stem(word: str) -> str:
    for suf in ("ations", "ation", "ings", "ing", "ies", "ers", "er", "ed", "es", "s"):
        if suf == "es" and not word.endswith(("sses", "xes", "ches", "shes")):
            continue
        if word.endswith(suf) and len(word) - len(suf) >= 3:
            word = word[: -len(suf)] + ("y" if suf == "ies" else "")
            break
    return word


def tokens(text: str) -> list[str]:
    words = re.findall(r"[a-z0-9][a-z0-9+#.-]*[a-z0-9+#]|[a-z0-9]", text.lower())
    return [stem(w) for w in words if w not in STOPWORDS and len(w) > 1 and not w.isdigit()]


def tfidf_vectors(docs: list[str]) -> list[dict[str, float]]:
    toks = [tokens(d) for d in docs]
    n = len(docs)
    df = Counter(t for ts in toks for t in set(ts))
    vecs = []
    for ts in toks:
        tf = Counter(ts)
        v = {t: (1 + math.log(c)) * (math.log((1 + n) / (1 + df[t])) + 1) for t, c in tf.items()}
        norm = math.sqrt(sum(x * x for x in v.values())) or 1.0
        vecs.append({t: x / norm for t, x in v.items()})
    return vecs


def cosine(a: dict[str, float], b: dict[str, float]) -> float:
    if len(a) > len(b):
        a, b = b, a
    return sum(x * b.get(t, 0.0) for t, x in a.items())


def shared_terms(a: dict[str, float], b: dict[str, float], k: int = 6) -> list[str]:
    common = sorted(set(a) & set(b), key=lambda t: -(a[t] * b[t]))
    return common[:k]


def similar_pairs(docs: list[str], threshold: float) -> list[tuple[int, int, float, list[str]]]:
    vecs = tfidf_vectors(docs)
    out = []
    for i in range(len(vecs)):
        for j in range(i + 1, len(vecs)):
            s = cosine(vecs[i], vecs[j])
            if s >= threshold:
                out.append((i, j, s, shared_terms(vecs[i], vecs[j])))
    out.sort(key=lambda p: -p[2])
    return out
