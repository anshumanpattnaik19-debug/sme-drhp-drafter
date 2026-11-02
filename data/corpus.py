"""SME offer-document sections, rebuilt as whole text from the section-aware chunks of ipo_prospectus_sft.

    load_sections(split, sections=CORE | EXTENDED, limit_docs=None) -> [Section]

The chunks are token windows (1,500 Qwen tokens, 100-token overlap) of one SEBI section each; joining a
section's chunks in order and removing the literal overlap gives the section text back. The company split
(train 354 / test 101 SME documents) is inherited from the chunk files, so no company is in both splits.
"""
from __future__ import annotations

import os
from dataclasses import dataclass

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CHUNKS_DIR = os.environ.get("DRHP_CHUNKS_DIR", os.path.join(os.path.dirname(HERE), "ipo_prospectus_sft", "chunks"))

# chunk section_key -> outline key (draft/outline.py)
CORE = {"risk_factors": "risk_factors", "our_business": "business", "objects_of_the_offer": "objects",
        "our_management": "management", "promoters": "promoters", "history_and_corporate_matters": "history"}
EXTENDED = {"industry_overview": "industry", "mdna": "mdna", "outstanding_litigation": "litigation",
            "government_approvals": "approvals", "summary_of_offer_document": "summary"}
# promoters and history are one core section for the row budget (PLAN.md 5.5)
BUDGET_GROUP = {"promoters": "promoters_history", "history": "promoters_history"}


@dataclass
class Section:
    split: str
    doc_id: int
    company: str
    listing_year: int
    doc_type: str
    section_key: str
    outline_key: str
    title: str
    page_start: int
    page_end: int
    text: str

    @property
    def core(self):
        return self.section_key in CORE


def join_chunks(texts):
    """Concatenate chunk texts, dropping the overlap each chunk repeats from the previous one."""
    out = texts[0] if texts else ""
    for nxt in texts[1:]:
        probe = nxt[:24]
        tail = out[-4000:]
        cut = None
        i = tail.find(probe) if len(probe) >= 12 else -1
        while i >= 0:                    # the earliest position whose suffix the next chunk starts with = longest overlap
            if nxt.startswith(tail[i:]):
                cut = len(tail) - i
                break
            i = tail.find(probe, i + 1)
        out += nxt[cut:] if cut else "\n" + nxt
    return out


def load_sections(split, sections=None, limit_docs=None, doc_ids=None, chunks_dir=None):
    import pyarrow.parquet as pq
    keys = dict(sections or {**CORE, **EXTENDED})
    path = os.path.join(chunks_dir or CHUNKS_DIR, f"{split}.parquet")
    cols = ["doc_id", "company_name", "board", "listing_year", "doc_type", "section_key", "section_title",
            "chunk_index", "page_start", "page_end", "text"]
    filters = [("board", "=", "sme"), ("section_key", "in", list(keys))]
    if doc_ids:
        filters.append(("doc_id", "in", list(doc_ids)))
    df = pq.read_table(path, columns=cols, filters=filters).to_pandas()
    if limit_docs:
        keep = sorted(df.doc_id.unique())[:limit_docs]
        df = df[df.doc_id.isin(keep)]
    out = []
    for (doc, key), g in df.groupby(["doc_id", "section_key"], sort=True):
        g = g.sort_values("chunk_index")
        r = g.iloc[0]
        out.append(Section(split, int(doc), str(r.company_name).strip(), int(r.listing_year), str(r.doc_type), key, keys[key],
                           str(r.section_title).strip(), int(g.page_start.min()), int(g.page_end.max()),
                           join_chunks(g.text.tolist())))
    return out
