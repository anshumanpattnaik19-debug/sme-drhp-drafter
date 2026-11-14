"""Words that are generic in SME offer documents: used, in any case, in at least MIN_DOCS of the train-split offer
documents. The verifier treats a capitalised word outside this list and outside the issuer's inputs as a name the
inputs do not support (a place, an organisation, a product). Built from the train split only, so no test company
shapes it. Common place names (Mumbai, Thane, Surat) are in the list, so an invented common city is not caught.

    python -m verify.vocab                 rebuilds verify/vocab.txt from trainset/work/units_train.jsonl
"""
from __future__ import annotations

import json
import os
import re
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
PATH = os.path.join(HERE, "vocab.txt")
SOURCE = os.path.join(os.path.dirname(HERE), "trainset", "work", "units_train.jsonl")
MIN_DOCS = 5
_VOCAB = None


def generic_words():
    global _VOCAB
    if _VOCAB is None:
        try:
            with open(PATH, encoding="utf-8") as fh:
                _VOCAB = {w.strip() for w in fh if w.strip()}
        except OSError:
            _VOCAB = set()
    return _VOCAB


def build(source=SOURCE, dest=PATH, min_docs=MIN_DOCS):
    docs = defaultdict(set)
    with open(source, encoding="utf-8") as fh:
        for line in fh:
            u = json.loads(line)
            for w in set(re.findall(r"[a-z]+", (u.get("raw") or "").lower())):
                docs[w].add(u["doc_id"])
    words = sorted(w for w, d in docs.items() if len(d) >= min_docs)
    with open(dest, "w", encoding="utf-8") as fh:
        fh.write("\n".join(words) + "\n")
    return len(words)


if __name__ == "__main__":
    print(f"{build()} words -> {PATH}")
