"""Issuer schedules as tables: the structured inputs (Excel sheets, Word tables) the code builders render.

    tables_from_blocks(blocks, file) -> [Table]
    find(tables, doc_types=None, header=(), any_header=(), title=None) -> Table | None

A Table keeps its file and location, a caption (the sheet title row or the paragraph just before a Word
table), a header row and data rows. Excel sheets are split into tables at gaps in the row numbers and at
new header rows; title rows above a header become the caption.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

RE_NUMLIKE = re.compile(r"^\(?-?[\d,]+(\.\d+)?\)?%?$")


@dataclass
class Table:
    file_id: str
    file_name: str
    doc_type: str
    loc: str
    caption: str
    header: list[str]
    rows: list[list[str]]
    row_locs: list[str] = field(default_factory=list)

    def col(self, *words) -> int | None:
        """Index of the first header cell containing all words (case-insensitive)."""
        for i, h in enumerate(self.header):
            hl = h.lower()
            if all(w.lower() in hl for w in words):
                return i
        return None

    def source(self) -> dict:
        return {"file_id": self.file_id, "file_name": self.file_name, "loc": self.loc,
                "snippet": (self.caption + " — " if self.caption else "") + " | ".join(self.header)}


def _is_header(cells):
    filled = [c for c in cells if c]
    return len(filled) >= 2 and not any(RE_NUMLIKE.match(c.replace(" ", "")) for c in filled)


def _sheet_tables(blocks, meta):
    out = []
    by_sheet: dict[str, list[dict]] = {}
    for b in blocks:
        if b["kind"] == "row":
            by_sheet.setdefault(b.get("sheet") or "", []).append(b)
    for sheet, rows in by_sheet.items():
        cur, caption, last_row = None, "", None
        for b in rows:
            cells = [c.strip() for c in b["text"].split(" | ")]
            filled = [c for c in cells if c]
            gap = last_row is not None and b["row"] - last_row > 1
            last_row = b["row"]
            if len(filled) == 1 and not RE_NUMLIKE.match(filled[0].replace(" ", "")):
                # a title or note row: caption of the next table, or a note under the current one
                if cur is None or gap:
                    caption = filled[0] if "synthetic" not in filled[0].lower() and "colour code" not in filled[0].lower() else caption
                cur = None if gap else cur
                continue
            if (cur is None or gap) and _is_header(cells):
                cur = Table(meta["id"], meta["name"], meta.get("doc_type", ""), f"{sheet}!{b['row']}", caption, cells, [], [])
                out.append(cur)
                caption = ""
                continue
            if cur is not None:
                cur.rows.append(cells + [""] * (len(cur.header) - len(cells)))
                cur.row_locs.append(b["loc"])
    return out


def _word_tables(blocks, meta):
    out, prev_text = [], ""
    for b in blocks:
        if b["kind"] == "text":
            prev_text = b["text"] if len(b["text"]) < 160 else ""
            continue
        if b["kind"] != "table":
            continue
        rows = [[c.strip() for c in r.split(" | ")] for r in b["text"].split("\n")]
        if not rows:
            continue
        width = max(len(r) for r in rows)
        rows = [r + [""] * (width - len(r)) for r in rows]
        out.append(Table(meta["id"], meta["name"], meta.get("doc_type", ""), b["loc"], prev_text.rstrip(":"),
                         rows[0], rows[1:], [f"{b['loc']}, row {i}" for i in range(2, len(rows) + 1)]))
        prev_text = ""
    return out


def tables_from_blocks(blocks, meta) -> list[Table]:
    return _sheet_tables(blocks, meta) + _word_tables(blocks, meta)


def find(tables, doc_types=None, header=(), any_header=(), title=None, min_rows=1):
    """First table (in file order) whose header has every word in `header` and one of `any_header`,
    and whose caption or sheet matches `title` (regex), from files of the given doc types."""
    for t in tables:
        if doc_types and t.doc_type not in doc_types:
            continue
        h = " ".join(t.header).lower()
        if any(w.lower() not in h for w in header):
            continue
        if any_header and not any(w.lower() in h for w in any_header):
            continue
        if title and not re.search(title, f"{t.caption} {t.loc}", re.I):
            continue
        if len(t.rows) >= min_rows:
            return t
    return None


def find_all(tables, doc_types=None, header=(), title=None):
    return [t for t in tables if (not doc_types or t.doc_type in doc_types)
            and all(w.lower() in " ".join(t.header).lower() for w in header)
            and (not title or re.search(title, f"{t.caption} {t.loc}", re.I))]
