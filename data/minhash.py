"""Near-duplicate control (PLAN.md 5.6): MinHash over 5-word shingles, LSH banding, Jaccard >= 0.6 flagged.

Many SME issues share lead managers and law firms, so boilerplate repeats across companies. Every test unit
gets `near_dup` (and the train unit it matches) so metrics can be reported on the full and the novel subset.
"""
from __future__ import annotations

import hashlib
import re
import struct

NUM_PERM, BANDS = 64, 16          # 16 bands x 4 rows: a pair at Jaccard 0.6 collides with probability ~0.88
SHINGLE = 5
THRESHOLD = 0.6
_MAX = (1 << 61) - 1
_SEEDS = [(int.from_bytes(hashlib.blake2b(f"a{i}".encode(), digest_size=8).digest(), "big") | 1,
           int.from_bytes(hashlib.blake2b(f"b{i}".encode(), digest_size=8).digest(), "big")) for i in range(NUM_PERM)]


def shingles(text, n=SHINGLE):
    toks = re.findall(r"[a-z0-9]+", text.lower())
    return {" ".join(toks[i:i + n]) for i in range(max(0, len(toks) - n + 1))}


def signature(text):
    hs = [struct.unpack(">Q", hashlib.blake2b(s.encode(), digest_size=8).digest())[0] for s in shingles(text)]
    if not hs:
        return [0] * NUM_PERM
    return [min((a * h + b) % _MAX for h in hs) for a, b in _SEEDS]


def jaccard_est(s1, s2):
    return sum(x == y for x, y in zip(s1, s2)) / NUM_PERM


class LSH:
    def __init__(self):
        self.r = NUM_PERM // BANDS
        self.buckets = [{} for _ in range(BANDS)]
        self.sigs = {}

    def add(self, key, sig):
        self.sigs[key] = sig
        for b in range(BANDS):
            self.buckets[b].setdefault(tuple(sig[b * self.r:(b + 1) * self.r]), []).append(key)

    def query(self, sig, threshold=THRESHOLD):
        cand = set()
        for b in range(BANDS):
            cand.update(self.buckets[b].get(tuple(sig[b * self.r:(b + 1) * self.r]), []))
        best = max(((jaccard_est(sig, self.sigs[k]), k) for k in cand), default=(0.0, None))
        return best if best[0] >= threshold else (best[0], None)


def flag_near_duplicates(train_units, test_units):
    """Sets u['near_dup'], u['near_dup_of'], u['near_dup_j'] on every test unit (dicts)."""
    lsh = LSH()
    for u in train_units:
        lsh.add(u["unit_id"], signature(u["target"]))
    for u in test_units:
        j, key = lsh.query(signature(u["target"]))
        u["near_dup"], u["near_dup_of"], u["near_dup_j"] = key is not None, key, round(j, 3)
    return test_units
