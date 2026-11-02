"""Project index: chunks of every issuer file with provenance, searched by BM25 with optional dense retrieval
fused by reciprocal rank fusion (the pattern of ipo_pitch_dataset/rag/retrieve.py).

    idx = ProjectIndex(ctx)          # ctx from draft.writer.make_ctx
    idx.search(query, k=6, kinds=("passage", "table"), doc_types=None) -> [Hit]

Chunking (a documented decision): running text is split into sentences and packed into ~110-word chunks
with a one-sentence overlap; each schedule (Excel table or Word table) becomes chunks of its caption, header
and up to 8 rows, so a row is always read with its column names. Dense retrieval is used only when
DRHP_DENSE_MODEL names a sentence-transformers model that is installed (e.g. BAAI/bge-m3 on the GPU box);
on the laptop BM25 alone is used and the result says so.
"""
from __future__ import annotations

import collections
import math
import os
import re
from dataclasses import dataclass

TOKEN = re.compile(r"[a-z0-9][a-z0-9&/.-]*")
STOP = set("the a an of and or to in on for by with as at is are was were be been this that these those from our its it "
           "what which who whom how does do did has have had there their any all per".split())
CHUNK_WORDS = 110


def tokens(text):
    return [t.strip(".-/") for t in TOKEN.findall(text.lower()) if t.strip(".-/") and t not in STOP]


@dataclass
class Chunk:
    id: int
    kind: str           # passage | table
    file_id: str
    file_name: str
    doc_type: str
    loc: str
    text: str
    title: str = ""


@dataclass
class Hit:
    chunk: Chunk
    score: float
    rank: int = 0


class BM25:
    def __init__(self, docs, k1=1.4, b=0.75):
        self.toks = [tokens(d) for d in docs]
        self.k1, self.b = k1, b
        self.avg = (sum(len(d) for d in self.toks) / len(self.toks)) if self.toks else 1
        df = collections.Counter(t for d in self.toks for t in set(d))
        n = max(1, len(self.toks))
        self.idf = {t: math.log(1 + (n - f + 0.5) / (f + 0.5)) for t, f in df.items()}
        self.tf = [collections.Counter(d) for d in self.toks]

    def scores(self, query):
        q = tokens(query)
        out = []
        for d, tf in zip(self.toks, self.tf):
            s = 0.0
            for t in q:
                if t in tf:
                    f = tf[t]
                    s += self.idf[t] * f * (self.k1 + 1) / (f + self.k1 * (1 - self.b + self.b * len(d) / self.avg))
            out.append(s)
        return out


def _sentences(text):
    return [s for s in re.split(r"(?<=[.;])\s+(?=[A-Z(₹\d])", " ".join(text.split())) if s]


def build_chunks(ctx):
    chunks: list[Chunk] = []
    names = {f["id"]: f for f in ctx.files}

    def add(kind, f, loc, text, title=""):
        if len(text.strip()) >= 20:
            chunks.append(Chunk(len(chunks), kind, f["id"], f["name"], f.get("doc_type", ""), loc, text.strip(), title))

    for fid, blocks in ctx.blocks.items():
        f = names.get(fid)
        if not f or f.get("doc_type") == "document_index":
            continue
        buf, words, start_loc = [], 0, None
        for b in blocks:
            if b["kind"] not in ("text", "ocr"):
                continue
            for s in _sentences(b["text"]):
                if start_loc is None:
                    start_loc = b["loc"]
                buf.append(s)
                words += len(s.split())
                if words >= CHUNK_WORDS:
                    loc = start_loc if start_loc == b["loc"] else f"{start_loc} – {b['loc']}"
                    add("passage", f, loc, " ".join(buf))
                    buf, words, start_loc = buf[-1:], len(buf[-1].split()), b["loc"]
            if f.get("format") not in ("docx",) and buf and b["kind"] in ("text", "ocr"):
                # PDF pages and images: do not let a chunk run across pages
                add("passage", f, start_loc or b["loc"], " ".join(buf))
                buf, words, start_loc = [], 0, None
        if buf:
            add("passage", f, start_loc or "", " ".join(buf))
    for t in ctx.tables:
        f = names.get(t.file_id)
        if not f or t.doc_type == "document_index":
            continue
        head = " | ".join(h for h in t.header if h)
        for i in range(0, max(1, len(t.rows)), 8):
            rows = t.rows[i:i + 8]
            body = "\n".join(" | ".join(c for c in r if c) for r in rows)
            loc = t.loc if not t.row_locs else f"{t.loc} (rows {i + 1}-{i + len(rows)})"
            add("table", f, loc, f"{t.caption}\n{head}\n{body}".strip(), title=t.caption or head[:80])
    return chunks


class _Dense:
    model = None
    tried = False

    @classmethod
    def get(cls):
        name = os.environ.get("DRHP_DENSE_MODEL")
        if not name or cls.tried:
            return cls.model
        cls.tried = True
        try:
            from sentence_transformers import SentenceTransformer
            cls.model = SentenceTransformer(name)
        except Exception:  # noqa: BLE001 - optional on the laptop
            cls.model = None
        return cls.model


class ProjectIndex:
    def __init__(self, ctx):
        self.chunks = build_chunks(ctx)
        self.bm25 = BM25([f"{c.title} {c.text}" for c in self.chunks]) if self.chunks else None
        self.dense = _Dense.get()
        self.emb = self.dense.encode([c.text for c in self.chunks], normalize_embeddings=True) if self.dense and self.chunks else None

    @property
    def method(self):
        return "BM25 + dense (RRF)" if self.emb is not None else "BM25"

    def search(self, query, k=6, kinds=("passage", "table"), doc_types=None):
        if not self.bm25:
            return []
        ok = [i for i, c in enumerate(self.chunks) if c.kind in kinds and (not doc_types or c.doc_type in doc_types)]
        bm = self.bm25.scores(query)
        ranked = sorted((i for i in ok if bm[i] > 0), key=lambda i: -bm[i])
        if self.emb is not None:
            qv = self.dense.encode([query], normalize_embeddings=True)[0]
            dense = sorted(ok, key=lambda i: -float(self.emb[i] @ qv))[:50]
            rrf = collections.defaultdict(float)
            for r, i in enumerate(ranked[:50]):
                rrf[i] += 1 / (60 + r)
            for r, i in enumerate(dense):
                rrf[i] += 1 / (60 + r)
            ranked = sorted(rrf, key=lambda i: -rrf[i])
        return [Hit(self.chunks[i], bm[i], r) for r, i in enumerate(ranked[:k])]


def best_sentence(text, query, max_len=320):
    """The sentence (or schedule row) of a chunk that shares most terms with the query."""
    q = set(tokens(query))
    if "\n" in text:
        lines = text.split("\n")
        # a schedule chunk is caption, header, rows: quote the best data row with its column names
        if len(lines) >= 3:
            head, rows = lines[1], lines[2:]
            row = max(rows, key=lambda u: len(q & set(tokens(u))))
            if q & set(tokens(row)):
                s = f"{row}  ({head})" if len(head) < 160 else row
                return s if len(s) <= max_len else s[:max_len].rsplit(" ", 1)[0] + "…"
        units = lines
    else:
        units = _sentences(text)
    scored = sorted(units, key=lambda u: -len(q & set(tokens(u))))
    s = scored[0] if scored else text
    return s if len(s) <= max_len else s[:max_len].rsplit(" ", 1)[0] + "…"


def rrf_merge(lists, k=60):
    """Fuse ranked lists of hashable ids into one ranking."""
    score = collections.defaultdict(float)
    for lst in lists:
        for r, x in enumerate(lst):
            score[x] += 1 / (k + r)
    return sorted(score, key=lambda x: -score[x])
