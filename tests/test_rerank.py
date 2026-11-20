"""The optional reranking stage of the project index (rag/index.py): it re-orders the first-stage candidates."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from rag.index import BM25, Chunk, ProjectIndex  # noqa: E402


class LongestFirst:
    def predict(self, pairs):
        return [len(p[1]) for p in pairs]


def make(rerank):
    idx = object.__new__(ProjectIndex)
    texts = ["revenue from operations", "revenue from operations rose in fiscal 2025 on new export orders from Europe",
             "the board approved revenue targets"]
    idx.chunks = [Chunk(i, "passage", f"f{i}", "file", "", "", t, "") for i, t in enumerate(texts)]
    idx.bm25 = BM25([f"{c.title} {c.text}" for c in idx.chunks])
    idx.dense, idx.emb, idx.rerank = None, None, rerank
    return idx


def test_without_a_reranker_the_bm25_order_is_kept():
    hits = make(None).search("revenue from operations", k=3)
    assert hits[0].chunk.text == "revenue from operations"


def test_the_reranker_reorders_the_candidates():
    idx = make(LongestFirst())
    hits = idx.search("revenue from operations", k=3)
    assert hits[0].chunk.text.startswith("revenue from operations rose") and idx.method == "BM25 + reranker"
