"""Draft .docx in SME section order. Fact citations become Word comments; [●] is highlighted.

    build_docx(project, drafts, facts, review, path, include_review=True, include_sources=True)

python-docx here; the production assembler uses the drhp_template/lib.js styling (PLAN.md section 4).
"""
from __future__ import annotations

import datetime as dt
import re

from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_COLOR_INDEX
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Pt, RGBColor, Cm

from draft.outline import PARTS, SECTIONS

NAVY = RGBColor(0x1F, 0x2A, 0x44)
GREY = RGBColor(0x66, 0x6E, 0x7A)
RE_TOKEN = re.compile(r"(\*\*[^*]+\*\*|\[●\])")


def _shade(cell, hex_fill):
    tc_pr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), hex_fill)
    tc_pr.append(shd)


def _runs(par, text, size=None):
    runs = []
    for part in RE_TOKEN.split(text):
        if not part:
            continue
        if part.startswith("**") and part.endswith("**"):
            r = par.add_run(part[2:-2])
            r.bold = True
        elif part == "[●]":
            r = par.add_run(part)
            r.font.highlight_color = WD_COLOR_INDEX.YELLOW
        else:
            r = par.add_run(part)
        if size:
            r.font.size = Pt(size)
        runs.append(r)
    return runs


def _styles(doc):
    st = doc.styles["Normal"]
    st.font.name = "Times New Roman"
    st.font.size = Pt(11)
    st.element.rPr.rFonts.set(qn("w:eastAsia"), "Times New Roman")
    pf = st.paragraph_format
    pf.space_after = Pt(6)
    pf.line_spacing = 1.15
    for name, size in (("Heading 1", 15), ("Heading 2", 13), ("Heading 3", 11.5)):
        h = doc.styles[name]
        h.font.name = "Times New Roman"
        h.font.size = Pt(size)
        h.font.bold = True
        h.font.color.rgb = NAVY
        h.element.rPr.rFonts.set(qn("w:eastAsia"), "Times New Roman")


def _header_footer(doc, company):
    for s in doc.sections:
        s.left_margin = s.right_margin = Cm(2.2)
        hp = s.header.paragraphs[0]
        hp.alignment = WD_ALIGN_PARAGRAPH.CENTER
        r = hp.add_run(f"DRAFT FOR REVIEW — {company} — Not for filing. Machine-generated first draft; "
                       "every statement to be verified by the BRLM and legal counsel.")
        r.font.size = Pt(8)
        r.font.color.rgb = GREY
        fp = s.footer.paragraphs[0]
        fp.alignment = WD_ALIGN_PARAGRAPH.CENTER
        fr = fp.add_run("Draft Red Herring Prospectus — SME Platform")
        fr.font.size = Pt(8)
        fr.font.color.rgb = GREY


def _comment(doc, runs, text):
    if not runs or not hasattr(doc, "add_comment"):
        return
    try:
        doc.add_comment(runs, text=text, author="DRHP Drafter", initials="DD")
    except Exception:  # noqa: BLE001 - comments are a convenience
        pass


def build_docx(project, drafts, facts, review, path, include_review=True, include_sources=True):
    doc = Document()
    _styles(doc)
    offer = project.get("offer") or {}
    company = offer.get("company_name") or project.get("name") or "[●]"
    board = {"bse_sme": "BSE SME", "nse_emerge": "NSE Emerge"}.get(offer.get("board"), "[●]")
    _header_footer(doc, company)
    fact_by_id = {f["id"]: f for f in facts}

    # cover
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_before = Pt(90)
    r = p.add_run("DRAFT RED HERRING PROSPECTUS")
    r.bold, r.font.size, r.font.color.rgb = True, Pt(20), NAVY
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.add_run(f"Dated {dt.date.today().strftime('%d %B %Y')}\nPlease read Section 26 and 32 of the Companies Act, 2013\n"
              f"Book Built Offer — proposed to be listed on {board}").font.size = Pt(10)
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_before = Pt(30)
    r = p.add_run(company.upper())
    r.bold, r.font.size = True, Pt(18)
    cover_rows = [("Registered office", offer.get("registered_office") or "[●]"),
                  ("Book Running Lead Manager", offer.get("lead_manager") or "[●]"),
                  ("Registrar to the Offer", offer.get("registrar") or "[●]"),
                  ("Offer", f"Up to {offer.get('fresh_issue_shares') or '[●]'} Equity Shares of face value ₹ {offer.get('face_value') or '[●]'} each at a price of ₹ [●] per Equity Share")]
    for k, v in cover_rows:
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        rk = p.add_run(k + ": ")
        rk.bold = True
        _runs(p, v)
    doc.add_page_break()

    # table of contents (field; Word updates it on open)
    doc.add_heading("Table of Contents", level=1)
    p = doc.add_paragraph()
    run = p.add_run()
    for tag, txt in (("begin", None), (None, 'TOC \\o "1-2" \\h \\z \\u'), ("separate", None), (None, None), ("end", None)):
        if tag:
            el = OxmlElement("w:fldChar")
            el.set(qn("w:fldCharType"), tag)
            run._r.append(el)
        elif txt:
            el = OxmlElement("w:instrText")
            el.set(qn("xml:space"), "preserve")
            el.text = txt
            run._r.append(el)
    note = doc.add_paragraph()
    _runs(note, "Right-click and choose Update Field to build the table of contents.", size=9)
    doc.add_page_break()

    for part in PARTS:
        doc.add_heading(f"SECTION {part}", level=1)
        for sec in [s for s in SECTIONS if s["part"] == part]:
            doc.add_heading(sec["title"].upper(), level=2)
            d = drafts.get(sec["key"])
            if not d:
                p = doc.add_paragraph()
                _runs(p, "[●] Section not drafted yet.")
                continue
            rv = d.get("review") or {}
            status = (f"Signed off by {rv.get('by')} on {str(rv.get('at', ''))[:10]}" if rv.get("status") == "reviewed"
                      else "Not yet signed off by the reviewer")
            sp = doc.add_paragraph()
            sr = sp.add_run(f"[{status}]")
            sr.italic, sr.font.size, sr.font.color.rgb = True, Pt(8), GREY
            for b in d["blocks"]:
                if b["type"] == "heading":
                    doc.add_heading(b["text"], level=3)
                elif b["type"] == "table":
                    rows = b.get("rows") or []
                    if not rows:
                        continue
                    if b.get("caption"):
                        cp = doc.add_paragraph()
                        cr = cp.add_run(b["caption"])
                        cr.bold, cr.font.size = True, Pt(9.5)
                    ncol = max(len(r) for r in rows)
                    t = doc.add_table(rows=len(rows), cols=ncol)
                    t.style = "Table Grid"
                    t.alignment = WD_TABLE_ALIGNMENT.CENTER
                    for i, row in enumerate(rows):
                        for j in range(ncol):
                            cell = t.cell(i, j)
                            cell.text = ""
                            val = row[j] if j < len(row) else ""
                            _runs(cell.paragraphs[0], val, size=9)
                            if j > 0 and re.match(r"^\(?-?[\d,]+(\.\d+)?\)?%?$", val.strip()):
                                cell.paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.RIGHT
                            if i == 0:
                                for r in cell.paragraphs[0].runs:
                                    r.bold = True
                                _shade(cell, "E8ECF3")
                    if include_sources and b.get("sources"):
                        sp = doc.add_paragraph()
                        src = "; ".join(f"{x.get('file_name', '')} ({x.get('loc', '')})" for x in b["sources"][:3])
                        r = sp.add_run(f"Source: {src}")
                        r.italic, r.font.size, r.font.color.rgb = True, Pt(8), GREY
                    else:
                        doc.add_paragraph()
                elif b["type"] == "brief":
                    p = doc.add_paragraph()
                    r = p.add_run(f"[●] {b.get('sub', '')}: not stated in the issuer's files; to be provided by the issuer."
                                  if b.get("missing") else f"[Drafting brief — prose to be written: {b.get('sub', '')}]")
                    r.italic, r.bold, r.font.size, r.font.color.rgb = True, True, Pt(9), GREY
                    for it in b.get("items", [])[:8]:
                        bp = doc.add_paragraph(style="List Bullet")
                        br = bp.add_run(f"{it['label']}{' (' + it['period'] + ')' if it.get('period') else ''}: {it['value']} — {it['file_name']}, {it['loc']}")
                        br.font.size, br.font.color.rgb = Pt(8.5), GREY
                else:
                    p = doc.add_paragraph()
                    runs = _runs(p, b.get("text", ""), size=9.5 if b["type"] == "note" else None)
                    if b["type"] == "note":
                        for r in runs:
                            r.italic = True
                            r.font.color.rgb = GREY
                    if include_sources and (b.get("facts") or b.get("sources")):
                        srcs = []
                        for fid in (b.get("facts") or [])[:8]:
                            f = fact_by_id.get(fid)
                            if f:
                                srcs.append(f"{f['label']}: {f['value']} — {f.get('file_name', '?')}, {f.get('loc', '')}")
                        for x in (b.get("sources") or [])[:4]:
                            srcs.append(f"{x.get('file_name', '?')}, {x.get('loc', '')}: {x.get('snippet', '')[:160]}")
                        if srcs:
                            _comment(doc, runs, "Sources:\n" + "\n".join(srcs))

    if include_review and review:
        doc.add_page_break()
        doc.add_heading("ANNEXURE — REVIEW PACK", level=1)
        s = review["summary"]
        doc.add_paragraph(f"High-severity items: {s['high']}  ·  Medium: {s['medium']}  ·  Placeholders [●]: {s['placeholders']}  ·  "
                          f"Sections drafted: {s['sections_drafted']} of {s['sections_total']}  ·  "
                          f"Signed off: {s.get('sections_signed_off', 0)} of {s['sections_total']}")
        t = doc.add_table(rows=1, cols=3)
        t.style = "Table Grid"
        for j, h in enumerate(("Severity", "Issue", "Detail")):
            t.cell(0, j).text = h
            _shade(t.cell(0, j), "E8ECF3")
        for it in review["issues"][:300]:
            row = t.add_row().cells
            row[0].text, row[1].text, row[2].text = it["severity"].upper(), it["title"], it.get("detail", "")[:300]
    doc.save(path)
    return path
