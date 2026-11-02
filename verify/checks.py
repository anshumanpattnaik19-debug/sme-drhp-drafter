"""Checks run on every drafted section and on the whole project (the review pack).

    verify_section(sec, draft, facts, offer) -> {"ungrounded", "grounded", "placeholders", "checklist", "drhp_stage", "score"}
    review_pack(project, files, facts, drafts) -> {"issues": [...], "summary": {...}}
"""
from __future__ import annotations

import re
from collections import defaultdict

from draft.outline import SECTIONS, SECTION_BY_KEY
from extract.rules import norm_value

# a figure is not part of a longer token such as a date (31.03.2024) or an identifier
RE_FIGURE = re.compile(r"(?<![A-Za-z0-9/.])(\d{1,3}(?:,\d{2,3})+(?:\.\d+)?|\d+\.\d+|\d{3,})(?![A-Za-z0-9/]|\.\d)")
RE_YEAR = re.compile(r"^(19|20)\d{2}$")
RE_ANYNUM = re.compile(r"\d[\d,]*(?:\.\d+)?")
DRHP_STAGE = [
    (re.compile(r"price band of ₹\s?\d", re.I), "price band stated"),
    (re.compile(r"(?:offer|issue) price of ₹\s?\d", re.I), "offer price stated"),
    (re.compile(r"(?:offer|issue|floor|cap) price\D{0,30}₹\s?\d[\d,.]*\s+per equity share", re.I), "per-share offer price stated"),
    (re.compile(r"(?:bid|offer|issue) (?:opening|closing|opens|closes)[^.]{0,30}\d{1,2}\s+[A-Z][a-z]+\s+20\d{2}", re.I), "offer date stated"),
    (re.compile(r"lot size of \d", re.I), "lot size stated"),
]


def num_key(s):
    """1,860.00 / 1860 / 1860.0 / 56.00% compare equal; None for non-numbers."""
    t = str(s).replace(",", "").replace("₹", "").strip().rstrip("%").strip("()")
    try:
        return round(float(t), 2)
    except ValueError:
        return None


def _numbers(text):
    out = set()
    for x in RE_FIGURE.findall(str(text)):
        k = num_key(x)
        if k is not None:
            out.add(k)
    k = num_key(text)
    if k is not None:
        out.add(k)
    return out


def known_values(facts, offer):
    vals = set()
    for f in facts:
        vals |= _numbers(f["value"])
    for v in (offer or {}).values():
        if isinstance(v, (str, int, float)):
            vals |= _numbers(v)
    return vals


def verify_section(key, draft, facts, offer):
    """Figures: 'in place' when the block's own cited facts or sources contain them (tables copied by code from a
    cited schedule count as in place); 'weak' when they only exist somewhere else in the inputs; else ungrounded.
    Checklist: 'covered' only when a builder produced the item; 'unconfirmed' when prose merely mentions it."""
    sec = SECTION_BY_KEY[key]
    known = known_values(facts, offer)
    offer_nums = known_values([], offer)
    by_id = {f["id"]: f for f in facts}
    in_place, weak, ungrounded = 0, [], []
    prose, text_all = [], []
    for b in draft.get("blocks", []):
        if b["type"] == "brief":
            continue
        if b["type"] == "table":
            cells = [c for r in (b.get("rows") or [])[1:] for c in r[1:]]
            text_all.append(" ".join(cells))
            if b.get("sources"):
                in_place += sum(len(_numbers(c)) for c in cells)
                continue
            texts = cells
        else:
            text_all.append(b.get("text", ""))
            texts = [b.get("text", "")]
            if b["type"] == "paragraph":
                prose.append(b.get("text", ""))
        local = set(offer_nums)
        for fid in b.get("facts", []):
            if fid in by_id:
                local |= _numbers(by_id[fid]["value"])
        for s in b.get("sources", []):
            # a cited passage or schedule row: every number in it counts, small integers included
            local |= {k for k in (num_key(x) for x in RE_ANYNUM.findall(s.get("snippet", ""))) if k is not None}
        for t in texts:
            for m in RE_FIGURE.finditer(t):
                raw = m.group(1)
                k = num_key(raw)
                if k is None or RE_YEAR.match(raw):
                    continue
                ctx = t[max(0, m.start() - 60):m.end() + 40]
                if k in local:
                    in_place += 1
                elif k in known:
                    weak.append({"figure": raw, "context": ctx})
                else:
                    ungrounded.append({"figure": raw, "context": ctx})
    joined = "\n".join(text_all)
    low = "\n".join(prose).lower()
    covered = set(draft.get("covered") or [])
    checklist = []
    for item in sec["checklist"]:
        words = [w for w in re.findall(r"[a-z]+", item.lower()) if len(w) > 3]
        mentioned = bool(words) and sum(w[:6] in low for w in words) >= max(1, (len(words) + 1) // 2)
        status = "covered" if item in covered else "unconfirmed" if mentioned else "missing"
        checklist.append({"item": item, "status": status, "covered": status == "covered"})
    stage = [label for rx, label in DRHP_STAGE if rx.search(joined)]
    total = in_place + len(weak) + len(ungrounded)
    cov = sum(c["covered"] for c in checklist)
    return {"grounded": in_place, "weak": weak[:50], "ungrounded": ungrounded[:50],
            "grounding": round(in_place / total, 3) if total else None,
            "placeholders": joined.count("[●]"), "checklist": checklist,
            "checklist_coverage": round(cov / len(checklist), 3) if checklist else None, "drhp_stage": stage,
            "narrative_pending": len(draft.get("narrative_pending") or []),
            "missing_inputs": draft.get("missing") or []}


def _consistency(facts):
    """Same label, period and kind of number (a % column is not compared with a ₹ column), different values
    in different files. 58.1 and 58.10 are the same value."""
    groups = defaultdict(list)
    for f in facts:
        if f["type"] in ("amount", "percent", "count") and f.get("period") and not f.get("superseded"):
            per = f["period"].lower()
            kind = "pct" if f["type"] == "percent" or "%" in per else "lakhs" if "lakh" in per or "₹" in per else f["type"]
            key = (re.sub(r"[^a-z]", "", f["label"].lower()), re.sub(r"[^0-9]", "", per), kind)
            groups[key].append(f)
    out = []
    for _key, fs in groups.items():
        vals = {num_key(f["value"]) if num_key(f["value"]) is not None else norm_value(f["value"]) for f in fs}
        files = {f["file_id"] for f in fs}
        if len(vals) > 1 and len(files) > 1:
            out.append(fs)
    return out


def review_pack(project, files, facts, drafts):
    issues = []
    present = {f.get("doc_type") for f in files if f.get("status") == "processed"}
    for sec in SECTIONS:
        missing = [n for n in sec["needs"] if n not in present]
        if missing:
            issues.append({"severity": "high" if sec["writer"] in ("slm_core", "inserted") else "medium",
                           "kind": "missing_input", "section": sec["key"],
                           "title": f"Missing input for {sec['title']}",
                           "detail": "No file classified as: " + ", ".join(missing)})
    for f in files:
        if f.get("status") == "failed":
            issues.append({"severity": "high", "kind": "ingest", "file_id": f["id"], "title": f"Could not read {f['name']}",
                           "detail": f.get("error", "")})
        elif f.get("needs_ocr_pages"):
            issues.append({"severity": "medium", "kind": "ocr", "file_id": f["id"],
                           "title": f"{f['name']}: {f['needs_ocr_pages']} page(s) not OCR'd",
                           "detail": "Scanned pages carry no text yet. Enable OCR or raise the OCR page limit in Settings, then reprocess the file."})
    for fs in _consistency(facts)[:40]:
        vals = "; ".join(f"{f['value']} ({f.get('file_name', '')})" for f in fs[:4])
        issues.append({"severity": "medium", "kind": "inconsistency", "fact_ids": [f["id"] for f in fs],
                       "title": f"Inconsistent figure: {fs[0]['label']} · {fs[0]['period']}", "detail": vals})
    for key, d in (drafts or {}).items():
        v = d.get("verification") or {}
        sec = SECTION_BY_KEY.get(key, {"title": key, "writer": ""})
        title = sec["title"]
        core = sec["writer"] in ("slm_core", "code")
        if v.get("ungrounded"):
            issues.append({"severity": "high", "kind": "ungrounded", "section": key,
                           "title": f"{len(v['ungrounded'])} figure(s) in {title} not found in the inputs",
                           "detail": ", ".join(u["figure"] for u in v["ungrounded"][:8])})
        if v.get("weak"):
            issues.append({"severity": "medium", "kind": "weak", "section": key,
                           "title": f"{len(v['weak'])} figure(s) in {title} not traced to the cited source",
                           "detail": "Found elsewhere in the inputs but not in the facts or schedule this block cites: "
                                     + ", ".join(u["figure"] for u in v["weak"][:8])})
        for m in v.get("missing_inputs", []):
            issues.append({"severity": "high" if core else "medium", "kind": "missing_input", "section": key,
                           "title": f"{title}: {m['item']}", "detail": f"Not in the inputs. Request from the issuer: {m['where']}."})
        if v.get("narrative_pending"):
            issues.append({"severity": "medium", "kind": "narrative", "section": key,
                           "title": f"{title}: {v['narrative_pending']} sub-heading(s) need prose",
                           "detail": "Shown as drafting briefs. Connect the fine-tuned SLM in Settings, or write them in the editor."})
        for c in v.get("checklist", []):
            st = c.get("status", "covered" if c["covered"] else "missing")
            if st == "missing":
                issues.append({"severity": "medium", "kind": "checklist", "section": key,
                               "title": f"{title}: “{c['item']}” not covered", "detail": "Mandatory disclosure item missing from the draft."})
            elif st == "unconfirmed":
                issues.append({"severity": "low", "kind": "checklist", "section": key,
                               "title": f"{title}: “{c['item']}” to confirm", "detail": "Mentioned in prose; a reviewer must confirm the disclosure is complete."})
        for s in v.get("drhp_stage", []):
            issues.append({"severity": "high", "kind": "drhp_stage", "section": key, "title": f"{title}: {s}",
                           "detail": "At DRHP stage this must be [●]."})
    if "risk_factors" not in (drafts or {}):
        for f in facts:
            if f["type"] == "short_text" and re.search(r"\bexpired\b|\bnot obtained\b|\bobjected\b", f["value"], re.I):
                issues.append({"severity": "medium", "kind": "disclosure", "fact_ids": [f["id"]],
                               "title": f"Flag for risk factors: {f['label']} — {f['value']}",
                               "detail": f"{f.get('file_name', '')} · {f.get('loc', '')}"})
    order = {"high": 0, "medium": 1, "low": 2}
    issues.sort(key=lambda i: order[i["severity"]])
    for i, it in enumerate(issues):
        it["id"] = f"iss{i + 1}"
    drafted = list(drafts or {})
    signed = [k for k, d in (drafts or {}).items() if (d.get("review") or {}).get("status") == "reviewed"]
    summary = {
        "sections_total": len(SECTIONS), "sections_drafted": len(drafted), "sections_signed_off": len(signed),
        "high": sum(i["severity"] == "high" for i in issues), "medium": sum(i["severity"] == "medium" for i in issues),
        "low": sum(i["severity"] == "low" for i in issues),
        "placeholders": sum((d.get("verification") or {}).get("placeholders", 0) for d in (drafts or {}).values()),
        "narrative_pending": sum((d.get("verification") or {}).get("narrative_pending", 0) for d in (drafts or {}).values()),
        "by_kind": {k: sum(i["kind"] == k for i in issues) for k in
                    ("missing_input", "ungrounded", "weak", "narrative", "checklist", "inconsistency", "drhp_stage", "ocr", "ingest", "disclosure")},
    }
    return {"issues": issues, "summary": summary}
