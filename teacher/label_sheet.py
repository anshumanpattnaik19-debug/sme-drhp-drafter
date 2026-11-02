"""Reviewer labelling sheet for the teacher screen (PLAN.md section 10, Week 0: 10 units labelled from scratch).

    python -m teacher.label_sheet make --units trainset/screen/screen_units.jsonl --out trainset/screen/reviewer_labels.xlsx
    python -m teacher.label_sheet read --xlsx trainset/screen/reviewer_labels.xlsx    # -> reviewer_labels.json

One sheet per unit: the passage on the left, an empty fact table on the right (type has a drop-down). The reviewer
labels before seeing any teacher output, so the comparison is blind.
"""
from __future__ import annotations

import argparse
import json
import textwrap

TYPES = ["amount", "percent", "date", "count", "person", "entity", "place", "short_text"]
COLS = ["type", "label", "value", "unit", "period"]


def make(units, path, n=10):
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill
    from openpyxl.worksheet.datavalidation import DataValidation
    wb = Workbook()
    ws = wb.active
    ws.title = "Instructions"
    for i, line in enumerate([
        "Teacher screen: label the facts in each unit before you see any model output.",
        "Rules are the ones the teacher gets (teacher/prompts.py):",
        "1. Every figure, date and proper name in the passage is one fact. 2. Copy values exactly as written.",
        "3. label = what the value is, 2-8 words. 4. unit and period when the passage gives them.",
        "5. short_text: non-numeric attributes, at most 12 words, in your own words. 6. Ignore page and section references.",
        "Fill one row per fact on each unit sheet. Leave the unit_id cell alone.",
    ], start=1):
        ws.cell(i, 1, line).font = Font(bold=i == 1)
    ws.column_dimensions["A"].width = 120
    head = PatternFill("solid", fgColor="E8ECF3")
    for k, u in enumerate(units[:n], start=1):
        s = wb.create_sheet(f"Unit {k}")
        s["A1"], s["B1"] = "unit_id", u["unit_id"]
        s["A2"], s["B2"] = "company / section", f"{u['company']} · {u['section_title']} · {u['heading']}"
        s["A4"] = "Passage"
        s["A4"].font = Font(bold=True)
        s["A5"] = "\n".join(textwrap.wrap(u["raw"], 110))
        s["A5"].alignment = Alignment(wrap_text=True, vertical="top")
        s.merge_cells("A5:A60")
        s.column_dimensions["A"].width = 90
        for j, c in enumerate(COLS):
            cell = s.cell(4, 3 + j, c)
            cell.font, cell.fill = Font(bold=True), head
            s.column_dimensions[chr(ord("C") + j)].width = [12, 34, 26, 12, 18][j]
        dv = DataValidation(type="list", formula1='"' + ",".join(TYPES) + '"', allow_blank=True)
        s.add_data_validation(dv)
        dv.add("C5:C120")
    wb.save(path)
    return path


def read(path):
    from openpyxl import load_workbook
    wb = load_workbook(path, data_only=True)
    out = {}
    for s in wb.worksheets[1:]:
        uid = s["B1"].value
        facts = []
        for r in range(5, 121):
            vals = [s.cell(r, 3 + j).value for j in range(len(COLS))]
            if vals[0] and vals[2] not in (None, ""):
                facts.append({c: str(v).strip() if v is not None else "" for c, v in zip(COLS, vals)})
        if uid:
            out[uid] = facts
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["make", "read"])
    ap.add_argument("--units")
    ap.add_argument("--out")
    ap.add_argument("--xlsx")
    a = ap.parse_args()
    if a.cmd == "make":
        with open(a.units, encoding="utf-8") as fh:
            units = [json.loads(ln) for ln in fh if ln.strip()]
        print(make(units, a.out))
    else:
        labels = read(a.xlsx)
        out = a.xlsx.rsplit(".", 1)[0] + ".json"
        with open(out, "w", encoding="utf-8") as fh:
            json.dump(labels, fh, indent=1, ensure_ascii=False)
        print(f"{sum(len(v) for v in labels.values())} facts for {len(labels)} units -> {out}")


if __name__ == "__main__":
    main()
