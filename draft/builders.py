"""Code builders: the parts of each section that come straight from the issuer's schedules.

    build(key, ctx) -> Build(parts=[(sub_heading, [blocks])], covered=[checklist items], missing=[(item, where)],
                             narrative=[sub-headings still needing prose])
    offer_terms(ctx) -> {field: {"value", "source"}}    values for Offer details, read from the issuer's files

Builders never compute regulatory figures (allocation, lock-in, GCP limits); those stay [●] or
"(to be confirmed by the BRLM)". Every table carries the file and location it was read from.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from extract.canonical import current
from extract.tables import Table, find, find_all
from . import fmt

PH = "[●]"
TBC = "(to be confirmed by the BRLM)"


@dataclass
class Ctx:
    project: dict
    facts: list
    files: list
    tables: list
    blocks: dict          # file_id -> [block]
    _index: object = None
    _corpus: object = None
    _notes: object = None

    def note_sections(self):
        """The management's business note, split at its own numbered headings ("3. Business segments"): [(heading, text)].
        Tables are flattened to rows. Empty when the issuer gave no business note."""
        if self._notes is None:
            import re as _re
            head = _re.compile(r"^\d{1,2}\.\s+([A-Z][^.]{2,90})$")
            out = []
            for f in self.files:
                if f.get("doc_type") != "business_note":
                    continue
                cur = None
                for b in self.blocks.get(f["id"], []):
                    t = (b.get("text") or "").strip()
                    m = head.match(t) if b.get("kind") == "text" and len(t.split()) <= 14 else None
                    if m:
                        cur = [m.group(1).strip(), []]
                        out.append(cur)
                    elif cur is not None and t:
                        cur[1].append(t.replace("\n", " ; ") if b.get("kind") == "table" else t)
            self._notes = [(h, " ".join(parts)) for h, parts in out]
        return self._notes

    def corpus(self):
        """Every word the issuer's files, facts and offer details contain, compacted to lower-case letters and digits, so
        an organisation name can be looked up even where a PDF lost its spaces."""
        if self._corpus is None:
            import json
            import re as _re
            parts = [b.get("text", "") for bl in self.blocks.values() for b in bl]
            parts += [f"{f.get('label', '')} {f.get('value', '')}" for f in self.facts]
            parts += [json.dumps(self.offer, ensure_ascii=False), self.project.get("name", "")]
            self._corpus = _re.sub(r"[^a-z0-9]", "", " ".join(parts).lower())
        return self._corpus

    def index(self):
        """The retrieval index over this project's files, built once (rag/index.py)."""
        if self._index is None:
            from rag.index import ProjectIndex
            self._index = ProjectIndex(self)
        return self._index

    @property
    def offer(self):
        return self.project.get("offer") or {}

    def o(self, k, default=PH):
        v = (self.offer.get(k) or "").strip()
        return v or default

    def company(self):
        return self.o("company_name", self.project.get("name") or PH)

    def doc_type(self, fid):
        return next((f.get("doc_type") for f in self.files if f["id"] == fid), None)

    def sentences(self, rx, doc_types=None, limit=3):
        """Sentences matching rx in the text of files of the given types: [(sentence, source)]."""
        out, seen = [], set()
        rx = re.compile(rx, re.I) if isinstance(rx, str) else rx
        for f in self.files:
            if doc_types and f.get("doc_type") not in doc_types:
                continue
            for b in self.blocks.get(f["id"], []):
                if b["kind"] in ("text", "ocr"):
                    # PDF text breaks lines mid-sentence: join lines, then split into sentences
                    units = re.split(r"(?<=[.;])\s+(?=[A-Z(])", " ".join(b["text"].split()))
                elif b["kind"] in ("table", "row"):
                    units = [", ".join(c.strip() for c in r.split(" | ") if c.strip() and c.strip() not in ("-", "–"))
                             for r in b["text"].split("\n")]
                else:
                    continue
                for sent in units:
                    s = " ".join(sent.split()).rstrip(":").strip()
                    if s and s[-1] not in ".;)":
                        s += "."
                    if 25 <= len(s) <= 600 and rx.search(s) and s[:80] not in seen:
                        seen.add(s[:80])
                        out.append((s, {"file_id": f["id"], "file_name": f["name"], "loc": b["loc"], "snippet": s[:300]}))
                        if len(out) >= limit:
                            return out
        return out


@dataclass
class Build:
    parts: list = field(default_factory=list)       # [(sub_heading or None, [blocks])]
    covered: list = field(default_factory=list)
    missing: list = field(default_factory=list)     # [(what, expected source)]
    narrative: list = field(default_factory=list)   # sub-headings that still need prose

    def add(self, sub, *blocks):
        blocks = [b for b in blocks if b]
        if not blocks:
            return
        for i, (s, bs) in enumerate(self.parts):
            if s == sub:
                bs.extend(blocks)
                return
        self.parts.append((sub, list(blocks)))


# ---------- block helpers ----------

def para(text, sources=None, facts=None):
    return {"type": "paragraph", "text": text, "facts": facts or [], "sources": sources or []}


def note(text, sources=None):
    return {"type": "note", "text": text, "facts": [], "sources": sources or []}


def missing_note(b: Build, what, where):
    b.missing.append((what, where))
    return note(f"{PH} {what}: not found in the inputs. Expected in: {where}.")


def table_block(t: Table, cols=None, drop=r"^(check|formula|#|sr\.?|s\. ?no\.?)\b", rows=None, caption=None,
                max_rows=60, rename=None, unit=None, total_label=None):
    """Render an issuer table: chosen columns (by header words), Indian number formats, source attached."""
    if cols:
        idx = []
        for c in cols:
            i = t.col(*c.split("+")) if isinstance(c, str) else t.col(*c)
            if i is not None and i not in idx:
                idx.append(i)
    else:
        idx = [i for i, h in enumerate(t.header) if h and not re.search(drop, h.strip(), re.I)]
    if not idx:
        return None
    unit = unit or ("lakhs" if re.search(r"lakh", f"{t.caption} {t.header[0]}", re.I) else "")
    kinds = [fmt.column_kind(t.header[i]) for i in idx]
    if unit == "lakhs":   # in a ₹ lakhs schedule, amount columns are lakhs, not rupees
        kinds = ["lakhs" if k in ("rupees", "auto") and "(₹)" not in t.header[i] else k for k, i in zip(kinds, idx)]
    head = [(rename or {}).get(t.header[i], t.header[i]) for i in idx]
    body = []
    for r in (rows if rows is not None else t.rows)[:max_rows]:
        cells = [fmt.cell(r[i] if i < len(r) else "", k if k != "auto" else "auto", unit) for i, k in zip(idx, kinds)]
        if any(c for c in cells):
            body.append(cells)
    if not body:
        return None
    if total_label:
        body = [r for r in body if not re.match(r"total", r[0], re.I)]
    return {"type": "table", "text": "", "rows": [head] + body, "caption": caption if caption is not None else t.caption,
            "sources": [t.source()], "facts": []}


def rows_matching(t: Table, rx, col=0):
    rx = re.compile(rx, re.I)
    return [r for r in t.rows if col < len(r) and rx.search(r[col])]


def kv(t: Table) -> dict:
    out = {t.header[0].strip().lower(): t.header[1].strip()} if len(t.header) > 1 else {}
    for r in t.rows:
        if len(r) > 1 and r[0]:
            out[r[0].strip().lower()] = r[1].strip()
    return out


RE_SHARES = re.compile(r"([\d,]{4,})\s+(?:equity\s+)?shares", re.I)


def _shares_in(s):
    m = RE_SHARES.search(s or "")
    return m.group(1) if m else None


# ---------- offer terms (fills Offer details) ----------

def offer_terms(ctx: Ctx) -> dict:
    out = {}

    def put(k, v, t=None, src=None):
        if v and k not in out:
            out[k] = {"value": v.strip(), "source": src or (t.source() if t else None)}

    t = find(ctx.tables, ["offer_note"], header=["particulars", "details"])
    if t:
        d = kv(t)
        for k, v in d.items():
            if "fresh issue" in k:
                put("fresh_issue_shares", _shares_in(v), t)
                m = re.search(r"face value (?:of )?₹\s?([\d.]+)", v, re.I)
                if m:
                    put("face_value", m.group(1).rstrip("."), t)
            elif "offer for sale" in k:
                put("ofs_shares", _shares_in(v), t)
                m = re.search(r"by (.+?)(?: \(|,| aggregating|$)", v)
                if m:
                    put("selling_shareholder", m.group(1), t)
            elif re.search(r"pre-?\s?issue equity shares|pre-?\s?offer", k):
                put("pre_issue_shares", _shares_in(v + " shares") or v, t)
            elif re.search(r"post-?\s?issue equity shares|post-?\s?offer", k):
                put("post_issue_shares", _shares_in(v + " shares") or v, t)
        if out.get("ofs_shares") and out.get("fresh_issue_shares"):
            put("issue_type", "fresh_ofs", t)
        elif out.get("fresh_issue_shares"):
            put("issue_type", "fresh", t)
    t = find(ctx.tables, ["offer_note", "board_resolution"], header=["role", "name"])
    if t:
        roles = {"lead manager": "lead_manager", "registrar": "registrar", "market maker": "market_maker",
                 "legal": "legal_counsel", "statutory auditor": "statutory_auditor", "peer review": "statutory_auditor"}
        for r in t.rows:
            role, name = r[0].lower(), (r[1] if len(r) > 1 else "")
            if not name or re.search(r"not (yet )?appointed|to be appointed|\[●\]", name, re.I):
                continue
            for k, field_ in roles.items():
                if k in role:
                    put(field_, re.split(r";|\n", name)[0].strip(), t)
    f = current(ctx.facts, label="Registered Office")
    if f:
        put("registered_office", f["value"], src={"file_id": f["file_id"], "file_name": f["file_name"], "loc": f["loc"], "snippet": f["snippet"]})
    t = find(ctx.tables, ["people_profiles"], header=["name and designation"])
    if t:
        for r in t.rows:
            if re.search(r"company secretary", r[0], re.I):
                put("company_secretary", re.split(r";|\n", r[0])[0].strip(), t)
    t = find(ctx.tables, ["offer_note", "board_resolution", "shareholder_resolution"], header=["milestone", "date"])
    if t:
        for r in t.rows:
            if re.search(r"board", r[0], re.I) and re.search(r"issue|ipo|offer", r[0], re.I) and RE_DATE.search(r[1]):
                put("board_resolution_date", RE_DATE.search(r[1]).group(0), t)
            if re.search(r"shareholder|egm|special resolution|general meeting", r[0], re.I) and re.search(r"issue|ipo|offer|62", r[0], re.I) and RE_DATE.search(r[1]):
                put("shareholder_resolution_date", RE_DATE.search(r[1]).group(0), t)
    if "lead_manager" not in out:
        for s, src in ctx.sentences(r"\(BRLM\)|book running lead manager", ["offer_note", "business_note"], 1):
            m = re.search(r"([A-Z][\w&.\- ]+?(?:Private Limited|Limited|LLP))\s*\(BRLM\)", s)
            if m:
                put("lead_manager", m.group(1), src=src)
    return out


RE_DATE = re.compile(r"\d{1,2}\s+(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+20\d{2}")


# ---------- section builders ----------

def b_the_offer(ctx: Ctx, b: Build, structure=False):
    o = ctx.offer
    fresh, ofs = ctx.o("fresh_issue_shares"), ctx.o("ofs_shares", "")
    fv = ctx.o("face_value")
    seller = o.get("selling_shareholder") or PH
    total = PH
    if fmt.parse(fresh) is not None and (not ofs or fmt.parse(ofs) is not None):
        total = fmt.shares((fmt.parse(fresh) or 0) + (fmt.parse(ofs) or 0))
    rows = [["Particulars", "Details"],
            ["Offer of Equity Shares", f"Up to {total} Equity Shares of face value ₹ {fv} each for cash at a price of ₹ {PH} per Equity Share aggregating ₹ {PH} lakhs"],
            ["of which:", ""],
            ["Fresh Issue", f"Up to {fresh} Equity Shares aggregating ₹ {PH} lakhs"]]
    if ofs and ofs not in ("0", PH):
        rows.append(["Offer for Sale", f"Up to {ofs} Equity Shares by {seller} aggregating ₹ {PH} lakhs"])
    rows += [["Market Maker Reservation Portion", f"{PH} Equity Shares {TBC}"],
             ["Net Offer to the public", f"{PH} Equity Shares"],
             ["Allocation between investor categories", f"As per the SEBI ICDR Regulations {TBC}"],
             ["Equity Shares outstanding prior to the Offer", ctx.o("pre_issue_shares")],
             ["Equity Shares outstanding after the Offer", ctx.o("post_issue_shares")],
             ["Use of Net Proceeds", "See “Objects of the Offer”. The Company will not receive any proceeds from the Offer for Sale."
              if ofs and ofs not in ("0", PH) else "See “Objects of the Offer”."]]
    src = (ctx.project.get("offer_sources") or {}).get("fresh_issue_shares")
    blk = {"type": "table", "text": "", "rows": rows, "caption": "Offer structure", "sources": [src] if src else [], "facts": []}
    if structure:
        b.add(None, para(f"The Offer is being made through the Book Building Process in terms of Chapter IX of the SEBI ICDR Regulations, "
                         f"on {'BSE SME' if o.get('board') != 'nse_emerge' else 'NSE Emerge'}. The allocation between investor categories "
                         f"will be as per the SEBI ICDR Regulations {TBC}."))
    else:
        b.add(None, para(f"The following table summarises the Offer. The Offer has been authorised by our Board on "
                         f"{ctx.o('board_resolution_date')} and by our shareholders on {ctx.o('shareholder_resolution_date')}."))
    b.add(None, blk)
    if fresh == PH:
        b.missing.append(("Number of Equity Shares in the Fresh Issue", "Offer details / note on proposed issue"))


def b_capital_structure(ctx: Ctx, b: Build):
    fv = fmt.parse(ctx.o("face_value", "")) or None
    auth = find(ctx.tables, ["share_capital"], header=["authorised capital"])
    pre = fmt.parse(ctx.o("pre_issue_shares", ""))
    rows = [["Particulars", "Aggregate value at face value (₹)"]]
    if auth and auth.rows:
        last = auth.rows[-1]
        n = last[auth.col("number")] if auth.col("number") is not None else ""
        v = last[auth.col("authorised capital")]
        rows.append([f"Authorised share capital: {fmt.shares(n)} Equity Shares of face value ₹ {ctx.o('face_value')} each", fmt.rupees(v)])
    else:
        rows.append([f"Authorised share capital: {PH}", PH])
    rows.append([f"Issued, subscribed and paid-up share capital before the Offer: {fmt.shares(pre) if pre else PH} Equity Shares",
                 fmt.rupees(pre * fv) if pre and fv else PH])
    rows.append([f"Present Offer: up to {ctx.o('fresh_issue_shares')} Equity Shares (Fresh Issue)"
                 + (f" and up to {ctx.o('ofs_shares')} Equity Shares (Offer for Sale)" if ctx.o("ofs_shares", "") not in ("", "0", PH) else ""), PH])
    rows.append([f"Issued, subscribed and paid-up share capital after the Offer: {ctx.o('post_issue_shares')} Equity Shares", PH])
    rows.append(["Securities premium account: before the Offer / after the Offer", f"{PH} / {PH}"])
    b.add("Share Capital", para("The share capital of our Company as on the date of this Draft Red Herring Prospectus is set out below."),
          {"type": "table", "text": "", "rows": rows, "caption": "Share capital", "facts": [],
           "sources": [auth.source()] if auth else []})
    if auth:
        b.add("Changes in Authorised Share Capital", table_block(auth, caption="History of the authorised share capital"))
    t = find(ctx.tables, ["share_capital", "offer_note"], header=["date of allotment"])
    if t:
        b.add("Equity Share Capital History", table_block(t, drop=r"^(check|formula|#)\b", caption="Equity share capital history of our Company"))
    else:
        b.add("Equity Share Capital History", missing_note(b, "Allotment-wise build-up of the equity share capital", "share capital build-up (Excel)"))
    t = find(ctx.tables, ["share_capital", "offer_note"], header=["shareholder", "pre-issue"])
    if t:
        b.add("Shareholding Pattern", table_block(t, caption="Pre-Offer and post-Offer shareholding"))
    else:
        b.add("Shareholding Pattern", missing_note(b, "Pre-offer and post-offer shareholding", "share capital build-up / note on proposed issue"))
    t = find(ctx.tables, ["offer_note", "share_capital"], header=["shareholder", "average cost"])
    if t:
        prom = rows_matching(t, r"promoter", col=t.col("category") or 1)
        b.add("Average Cost of Acquisition of the Promoters", table_block(t, cols=["shareholder", "category", "pre-issue shares", "average cost"],
                                                                           rows=[r for r in prom if not re.search(r"group", r[t.col('category') or 1], re.I)] or prom,
                                                                           caption="Average cost of acquisition of Equity Shares by the Promoters"))
    b.add("Lock-in of Promoters' Contribution", para(f"Details of the Promoters' contribution and lock-in will be as per the SEBI ICDR Regulations {TBC}. "
                                                     f"Minimum Promoters' contribution: {PH} Equity Shares."))


def b_objects(ctx: Ctx, b: Build):
    t = find(ctx.tables, ["objects_cost", "offer_note"], header=["object"], any_header=["estimated amount", "total"])
    if not t:
        b.add("Requirement of Funds", missing_note(b, "Objects and estimated cost with deployment schedule", "objects / project cost (Excel)"))
        return
    b.add("Requirement of Funds", para(f"Our Company proposes to utilise the Net Proceeds from the Fresh Issue towards the following objects. "
                                       f"Our Company will not receive any proceeds from the Offer for Sale."),
          table_block(t, caption="Objects and deployment of the Net Proceeds (₹ lakhs)", unit="lakhs",
                      drop=r"^(check|formula|#)\b|total deployment"))
    b.covered += ["fund requirement table", "general corporate purposes", "deployment of funds"]
    b.add("Means of Finance", para("The fund requirements set out above are proposed to be met from the Net Proceeds. Accordingly, the requirement of firm "
                                   f"arrangements of finance through verifiable means will be examined against the SEBI ICDR Regulations {TBC}."))
    b.covered.append("means of finance")
    # details per object, with the supporting schedules
    oc = t.col("estimated") if t.col("estimated") is not None else (t.col("total") or 1)
    for r in t.rows:
        name = r[0]
        if not name or re.match(r"total|general corporate|issue expenses|gross proceeds", name, re.I) or fmt.parse(r[oc]) is None:
            continue
        sub = name if len(name) < 90 else name[:87] + "…"
        b.add(sub, para(f"Our Company proposes to utilise ₹ {fmt.lakhs(r[oc])} lakhs of the Net Proceeds towards {name[0].lower() + name[1:]}.",
                        sources=[t.source()]))
        b.narrative.append(sub)
        if re.search(r"machiner|equipment|plant", name, re.I):
            q = find(ctx.tables, ["objects_cost", "offer_note", "quotation"], header=["supplier"], any_header=["quotation", "ref"])
            if q:
                b.add(sub, table_block(q, caption="Quotations relied on (₹ lakhs)", unit="lakhs",
                                       cols=["supplier", "item", "quotation", "date", "qty", "amount", "valid"]))
                b.covered.append("quotations relied on")
        if re.search(r"solar", name, re.I):
            q = find(ctx.tables, ["objects_cost", "quotation"], title=r"solar")
            if q:
                b.add(sub, table_block(q, caption=q.caption or "Cost break-up (₹ lakhs)", unit="lakhs"))
        if re.search(r"loan|repay|borrow", name, re.I):
            q = find(ctx.tables, ["borrowings"], header=["lender", "facility"])
            if q:
                key = re.search(r"\(([A-Z]{2}-[IVX]+)\)|(TL-[IVX]+)", name)
                rws = rows_matching(q, re.escape(key.group(1) or key.group(2)), col=q.col("facility") or 1) if key else q.rows
                b.add(sub, table_block(q, rows=rws, caption="Details of the loan proposed to be repaid or prepaid (₹ lakhs)",
                                       cols=["lender", "facility", "sanctioned", "outstanding", "rate", "repayment"]))
            b.add(sub, para(f"The prepayment or repayment is subject to the consent of the lender and the terms of the sanction letter {TBC}."))
        if re.search(r"working capital", name, re.I):
            q = find(ctx.tables, ["offer_note", "working_capital"], title=r"working capital")
            if q:
                b.add(sub, table_block(q, caption="Working capital requirement: actual and estimated (₹ lakhs)", unit="lakhs"))
    b.covered.append("details of each object")
    s = find(ctx.tables, ["offer_note", "business_note"], header=["item", "order placement"])
    if s:
        b.add("Schedule of Implementation", table_block(s, caption="Schedule of implementation"))
        b.covered.append("schedule of implementation")
    else:
        b.add("Schedule of Implementation", missing_note(b, "Schedule of implementation", "note on proposed issue / business note"))
    e = find(ctx.tables, ["offer_note"], header=["expense head"])
    if e:
        b.add("Offer Related Expenses", para("The Offer expenses are estimated as follows. Expenses will be shared between our Company and the Selling Shareholder "
                                             f"in proportion to the Equity Shares offered, as agreed {TBC}."),
              table_block(e, caption="Estimated Offer expenses"))
        b.covered.append("offer expenses")
    else:
        b.add("Offer Related Expenses", missing_note(b, "Break-up of Offer expenses", "note on proposed issue"))
    dep = ctx.sentences(r"deployed.{0,80}₹\s?[\d,.]+\s*lakhs|₹\s?[\d,.]+\s*lakhs.{0,60}deployed", ["funds_deployed", "offer_note", "objects_cost"], 1)
    if dep:
        s_, src = dep[0]
        b.add("Funds Deployed", para(f"{s_}", sources=[src]))
        b.covered.append("deployment of funds")
    else:
        b.add("Funds Deployed", missing_note(b, "Funds deployed till date (auditor's certificate)", "funds deployed certificate"))
    b.add("Interim Use of Proceeds", para("Pending utilisation for the purposes described above, our Company will deposit the Net Proceeds only in scheduled "
                                          f"commercial banks as permitted under applicable law {TBC}."))
    b.add("Monitoring of Utilisation of Funds", para(f"The appointment of a monitoring agency will be as required under the SEBI ICDR Regulations {TBC}. "
                                                    "Our Audit Committee will monitor the utilisation of the Net Proceeds."))
    b.covered.append("monitoring agency or interim use")


KEY_PL = [r"^revenue from operations", r"^total income", r"^ebitda", r"^profit before tax", r"^profit after tax|^restated profit|^profit for the",
          r"earnings per share|^eps"]
KEY_BS = [r"^share capital", r"^reserves", r"net worth|shareholders.? funds", r"^long-term borrowings", r"^short-term borrowings",
          r"^total borrowings", r"^total assets|^total equity and liabilities"]


def _pick(t: Table, patterns):
    out = []
    for p in patterns:
        r = next((r for r in t.rows if re.search(p, r[0], re.I)), None)
        if r and r not in out:
            out.append(r)
    return out


def _fin_tables(ctx):
    pl = find(ctx.tables, ["restated_workings", "restated_fs"], header=["particulars"], title=r"profit and loss|\bPL!")
    bs = find(ctx.tables, ["restated_workings", "restated_fs"], header=["particulars"], title=r"balance sheet|assets and liabilities|\bBS!")
    cf = find(ctx.tables, ["restated_workings", "restated_fs"], header=["particulars"], title=r"cash flow|\bCF!")
    ratios = find(ctx.tables, ["restated_workings", "restated_fs"], header=["ratio"])
    return pl, bs, cf, ratios


def _drop_opening(t: Table):
    return [h for h in t.header if not re.search(r"opening", h, re.I)]


def b_summary_financials(ctx: Ctx, b: Build):
    pl, bs, cf, ratios = _fin_tables(ctx)
    if not (pl or bs):
        b.add(None, missing_note(b, "Restated financial statements in Excel", "restated financials workings"))
        return
    b.add(None, para("The following summary financial information is derived from the Restated Financial Information and should be read with it. "
                     "All figures are in ₹ lakhs."))
    if bs:
        cols = [h for h in _drop_opening(bs)]
        b.add("Restated Statement of Assets and Liabilities (summary)", table_block(bs, cols=cols, rows=_pick(bs, KEY_BS), caption="", unit="lakhs"))
    if pl:
        b.add("Restated Statement of Profit and Loss (summary)", table_block(pl, rows=_pick(pl, KEY_PL), caption="", unit="lakhs"))
    if cf:
        b.add("Restated Statement of Cash Flows (summary)", table_block(cf, rows=_pick(cf, [r"net cash (from|generated|used).{0,25}operat", r"net cash.{0,25}invest", r"net cash.{0,25}financ"]),
                                                                        caption="", unit="lakhs"))


def b_other_financial(ctx: Ctx, b: Build, basis=False):
    pl, bs, cf, ratios = _fin_tables(ctx)
    if ratios:
        b.add("Accounting Ratios", table_block(ratios, drop=r"^(formula)\b", caption="Accounting ratios derived from the Restated Financial Information"))
    else:
        b.add("Accounting Ratios", missing_note(b, "Accounting ratios", "restated financials workings"))
    if basis:
        k = find(ctx.tables, ["offer_note", "kpi"], header=["kpi"])
        if k:
            b.add("Key Performance Indicators", para("The KPIs below have been approved by our Audit Committee and certified by the statutory auditor."),
                  table_block(k, caption="Key performance indicators"))
        b.add("Price/Earnings Ratio", para(f"P/E ratio at the floor price and the cap price: {PH} and {PH} times. Industry peer comparison: {PH} "
                                           "(from the industry report and peers' filings; to be prepared by the BRLM)."))
        b.missing.append(("Peer comparison (listed peers)", "industry report / BRLM"))


def b_capitalisation(ctx: Ctx, b: Build):
    pl, bs, cf, ratios = _fin_tables(ctx)
    if not bs:
        b.add(None, missing_note(b, "Restated balance sheet", "restated financials workings"))
        return
    last = len(bs.header) - 1
    rows = [["Particulars (₹ lakhs)", f"Pre-Offer ({bs.header[last]})", "Post-Offer"]]
    for r in _pick(bs, [r"^short-term borrowings", r"^long-term borrowings", r"^total borrowings", r"^share capital", r"^reserves", r"net worth|shareholders.? funds"]):
        rows.append([r[0], fmt.lakhs(r[last]), PH])
    if ratios:
        de = next((r for r in ratios.rows if re.search(r"debt.?equity", r[0], re.I)), None)
        if de:
            rows.append(["Total borrowings / total equity (times)", fmt.cell(de[len(ratios.header) - 2 if ratios.col("formula") else -1]), PH])
    b.add(None, para("The capitalisation statement based on the Restated Financial Information is set out below. Post-Offer figures depend on the Offer Price and are [●]."),
          {"type": "table", "text": "", "rows": rows, "caption": "Capitalisation statement", "sources": [bs.source()], "facts": []})


def b_indebtedness(ctx: Ctx, b: Build):
    t = find(ctx.tables, ["borrowings"], header=["lender"])
    if not t:
        t = find(ctx.tables, ["business_note", "offer_note"], header=["lender"])
    if not t:
        b.add(None, missing_note(b, "Facility-wise statement of borrowings", "statement of borrowings (Excel)"))
        return
    b.add(None, para("Our Company has availed the following borrowings. The details below are as per the statement of borrowings certified by the statutory auditor "
                     f"{TBC}. Amounts in ₹ lakhs."),
          table_block(t, cols=["lender", "facility", "nature", "sanction", "outstanding", "rate", "repayment"], caption="Statement of borrowings", unit="lakhs"))
    sec = t.col("security")
    if sec is not None:
        b.add("Security and Key Terms", table_block(t, cols=["lender", "facility", "security", "remarks"], caption="Security created and key terms"))


def b_litigation(ctx: Ctx, b: Build):
    ts = [t for t in ctx.tables if t.doc_type == "litigation" and not re.search(r"documents reviewed", t.caption, re.I)]
    if not ts:
        b.add(None, missing_note(b, "Litigation certificate from legal counsel", "litigation certificate"))
        return
    b.add(None, para("Except as stated below, there are no outstanding (i) criminal proceedings, (ii) actions by statutory or regulatory authorities, "
                     "(iii) disciplinary actions by SEBI or a stock exchange against our Promoters in the last five financial years, (iv) claims related to direct and "
                     "indirect taxes, or (v) other pending litigation as determined to be material under the materiality policy, in each case involving our "
                     "Company, Directors, Promoters or Group Companies, as certified by the legal counsel."))
    for t in ts:
        cap = t.caption or ("Materiality threshold" if t.col("criterion") is not None else "")
        sub = "Materiality Policy" if re.search(r"criterion|materiality", " ".join(t.header) + cap, re.I) else \
              "Summary of Outstanding Proceedings" if re.search(r"summary", cap, re.I) else \
              "Outstanding Dues to Creditors" if re.search(r"creditor", " ".join(t.header), re.I) else \
              "Contingent Liabilities" if re.search(r"contingent", cap, re.I) else (cap.strip("()abcdefg ").strip() or "Details of Proceedings")
        b.add(sub[:90], table_block(t, caption=cap, drop=r"^(check|formula)\b"))
    b.covered += ["criminal proceedings", "actions by regulatory authorities", "tax proceedings", "material civil litigation",
                  "materiality policy", "outstanding dues to creditors"]


def b_approvals(ctx: Ctx, b: Build):
    t = find(ctx.tables, ["approvals"], header=["approval"]) or find(ctx.tables, ["business_note"], header=["approval", "status"])
    if not t:
        b.add(None, missing_note(b, "Register of licences and approvals", "licences and approvals register"))
        return
    b.add(None, para("Our Company has obtained the following material approvals for its business. Unless stated otherwise, these are valid as on the date "
                     "of this Draft Red Herring Prospectus."))
    cat = t.col("category")
    groups = {}
    for r in t.rows:
        groups.setdefault(r[cat] if cat is not None else "Approvals", []).append(r)
    for g, rws in groups.items():
        b.add(f"{g} Approvals" if not g.lower().endswith("approvals") else g, table_block(t, rows=rws, caption="", drop=r"^(#|category)$"))
    st = t.col("status")
    if st is not None:
        pend = [r for r in t.rows if re.search(r"expir|applied|pending|not (yet )?obtained|to be (applied|obtained)|renewal", r[st], re.I)]
        if pend:
            b.add("Pending and Expired Approvals", para("The following approvals have expired, have been applied for, or are yet to be obtained:"),
                  table_block(t, rows=pend, caption="", drop=r"^(#)$"))
            b.covered += ["pending approvals", "expired approvals"]
    b.covered += ["incorporation approvals", "tax approvals", "business approvals"]
    ip = find(ctx.tables, ["insurance_ip", "business_note"], header=["mark"])
    if ip:
        b.add("Intellectual Property", table_block(ip, caption="Trade marks and other intellectual property"))
        b.covered.append("intellectual property")


def b_management(ctx: Ctx, b: Build):
    P = ["people_profiles", "board_resolution"]
    board = find(ctx.tables, P, header=["din"], any_header=["designation", "category"], min_rows=2)
    if board:
        b.add("Board of Directors", table_block(board, caption="Board of Directors"))
        b.covered.append("board of directors table")
    else:
        b.add("Board of Directors", missing_note(b, "Details of the Board (name, DIN, designation, term)", "promoter, director and KMP profiles"))
    b.narrative.append("Brief Profiles of Our Directors")
    rem = find(ctx.tables, P, header=["director"], any_header=["per annum", "salary", "total"])
    if rem:
        b.add("Remuneration", table_block(rem, caption="Remuneration of the Executive Directors (₹ lakhs)", unit="lakhs"))
        b.covered.append("remuneration")
    sh = find(ctx.tables, P, header=["equity shares"], any_header=["% of pre", "pre-issue"])
    if sh:
        b.add("Shareholding of Directors", table_block(sh, caption="Shareholding of our Directors"))
        b.covered.append("shareholding of directors")
    com = find(ctx.tables, P, header=["committee"])
    if com:
        b.add("Committees of the Board", para("Our Company has constituted the following committees of the Board in compliance with the Companies Act and the "
                                              f"SEBI Listing Regulations {TBC}."), table_block(com, caption="Committees of the Board"))
        b.covered.append("corporate governance and committees")
    kmp = find(ctx.tables, P, header=["qualification"], any_header=["name and designation", "joined"])
    if kmp:
        b.add("Key Managerial Personnel", table_block(kmp, caption="Key Managerial Personnel and Senior Management"))
        b.covered.append("key managerial personnel")
    ch = find(ctx.tables, P, header=["change"], any_header=["reason", "date"])
    if ch:
        b.add("Changes in the Last Three Years", table_block(ch, caption="Changes in the Board and KMP in the last three years"))
        b.covered.append("changes in the last three years")


def b_promoters(ctx: Ctx, b: Build):
    P = ["people_profiles"]
    ind = [t for t in ctx.tables if t.doc_type in P and len(t.header) == 2 and re.search(r"date of birth", t.header[0], re.I)]
    for t in ind[:4]:
        rows = [[t.header[0], t.header[1]]] + [[r[0], r[1]] for r in t.rows]
        b.add("Our Promoters", {"type": "table", "text": "", "rows": [["Particulars", t.caption or "Promoter"]] + rows,
                                "caption": t.caption, "sources": [t.source()], "facts": []})
    if ind:
        b.covered.append("details of individual promoters")
    else:
        b.add("Our Promoters", missing_note(b, "Details of the individual Promoters", "promoter, director and KMP profiles"))
    b.narrative += ["Our Promoters", "Interest of Our Promoters"]
    g = find(ctx.tables, P, header=["individual", "relationship"])
    e = find(ctx.tables, P, header=["entity", "nature of interest"])
    if g or e:
        b.add("Promoter Group", table_block(g, caption="Individuals forming part of the Promoter Group") if g else None,
              table_block(e, caption="Entities forming part of the Promoter Group") if e else None)
        b.covered.append("promoter group")
    rpt = find(ctx.tables, ["group_rpt", "people_profiles"], header=["related party"]) or find(ctx.tables, P, header=["transaction"])
    if rpt:
        b.add("Payment or Benefits to Promoters", para("Except as stated below and in the related party transactions in the Restated Financial Information, "
                                                       "no amount or benefit has been paid or given to our Promoters or members of the Promoter Group in the two years preceding "
                                                       "the date of this Draft Red Herring Prospectus."),
              table_block(rpt, caption="Related party transactions (₹ lakhs)", unit="lakhs"))
        b.covered.append("payment or benefit to promoters")
    b.add("Change in Control", para(f"There has been no change in the control of our Company in the five years preceding the date of this Draft Red Herring Prospectus {TBC}."))


def b_group_companies(ctx: Ctx, b: Build):
    t = find(ctx.tables, ["group_rpt"], header=["name"], any_header=["nature of business", "identifier"])
    if t:
        b.add(None, table_block(t, caption="Our Group Companies"))
    fin = find(ctx.tables, ["group_rpt"], header=["entity", "turnover"])
    if fin:
        b.add("Financial Information of the Group Companies", table_block(fin, caption="Financial information (₹ lakhs)", unit="lakhs"))


def b_business(ctx: Ctx, b: Build):
    B = ["business_note", "operational_data"]
    b.narrative += ["Overview"]
    k = find(ctx.tables, ["business_note"], header=["key highlights"])
    if k:
        b.add("Overview", table_block(k, caption="Key financial and operational highlights", unit="lakhs"))
    pm = find(ctx.tables, B, header=["product"], any_header=["₹ lakhs", "lakhs"]) or find(ctx.tables, B, title=r"product mix|by product")
    if pm:
        b.add("Our Products", table_block(pm, caption=pm.caption or "Revenue by product group"))
        b.covered.append("products and services")
    b.narrative += ["Our Products", "Manufacturing Process"]
    cap = find(ctx.tables, B, title=r"capacity") or find(ctx.tables, B, header=["particulars"], title=r"capacity")
    if cap:
        b.add("Capacity and Capacity Utilisation", table_block(cap, caption=cap.caption or "Installed capacity, production and utilisation"))
        b.covered.append("installed capacity and utilisation")
    cus = find(ctx.tables, B, header=["customer"], title=r"customer")
    if cus:
        b.add("Our Customers", table_block(cus, caption=cus.caption or "Top customers (share of revenue)"))
        b.covered.append("customers and end-use")
    eu = find(ctx.tables, B, title=r"end-use")
    if eu:
        b.add("Our Customers", table_block(eu, caption=eu.caption))
    b.narrative += ["Our Customers", "Raw Materials", "Our Competitive Strengths", "Our Business Strategy"]
    rm = find(ctx.tables, ["business_note"], header=["material"], any_header=["%", "lakhs"])
    if rm:
        b.add("Raw Materials", table_block(rm, caption="Raw materials consumed"))
        b.covered.append("raw materials and suppliers")
    mc = find(ctx.tables, B, header=["machine"])
    if mc:
        b.add("Plant and Machinery", table_block(mc, caption=mc.caption or "Main plant and machinery"))
    emp = find(ctx.tables, B, header=["employees"]) or find(ctx.tables, B, header=["function", "number"])
    if emp:
        b.add("Human Resources", table_block(emp, caption=emp.caption or "Employees by function"))
        b.covered.append("human resources")
    pr = find(ctx.tables, ["business_note"], header=["address"], any_header=["owner", "lessor", "tenure"])
    if pr:
        b.add("Properties", table_block(pr, caption="Properties used by our Company"))
        b.covered.append("properties")
    ins = find(ctx.tables, ["insurance_ip", "business_note"], header=["policy"])
    if ins:
        b.add("Insurance", table_block(ins, caption=ins.caption or "Insurance policies"))
        b.covered.append("insurance")
    ip = find(ctx.tables, ["insurance_ip", "business_note"], header=["mark"])
    if ip:
        b.add("Intellectual Property", table_block(ip, caption="Intellectual property"))
        b.covered.append("intellectual property")


def b_history(ctx: Ctx, b: Build):
    b.narrative += ["Brief History", "Main Objects"]
    ev = find(ctx.tables, ["business_note", "coi", "moa"], header=["year", "event"]) or find(ctx.tables, None, header=["year", "key event"])
    if ev:
        b.add("Key Events and Milestones", table_block(ev, caption="Major events and milestones"))
        b.covered.append("major events and milestones")
    am = find(ctx.tables, ["shareholder_resolution"], header=["resolution"])
    if am:
        rows = [r for r in am.rows if re.search(r"memorandum|moa|object|name|capital clause|authorised", " ".join(r), re.I)]
        if rows:
            b.add("Amendments to the MoA", table_block(am, rows=rows, caption="Amendments to the Memorandum of Association"))
            b.covered.append("amendments to the MoA")
    gc = find(ctx.tables, ["group_rpt"], header=["name"], any_header=["nature of business"])
    b.add("Holding, Subsidiary and Joint Ventures", para("Our Company does not have a holding company, subsidiary or joint venture "
                                                         f"{TBC}." + (" Group companies are set out in “Our Group Companies”." if gc else "")))
    b.covered.append("holding and subsidiaries")


def b_mdna(ctx: Ctx, b: Build):
    pl, bs, cf, ratios = _fin_tables(ctx)
    b.narrative += ["Overview", "Significant Factors Affecting Our Results of Operations"]
    if pl:
        b.add("Results of Operations", table_block(pl, caption="Restated statement of profit and loss (₹ lakhs)", unit="lakhs"))
        b.covered += ["results of operations"]
    pct_t = find(ctx.tables, ["business_note"], header=["% of revenue"])
    if pct_t:
        b.add("Results of Operations", table_block(pct_t, caption="Items as a percentage of revenue from operations"))
    b.narrative += ["Comparison of Periods"]
    if cf:
        b.add("Cash Flows", table_block(cf, rows=_pick(cf, [r"net cash.{0,25}operat", r"net cash.{0,25}invest", r"net cash.{0,25}financ", r"net (increase|decrease|change)"]),
                                        caption="Summary of cash flows (₹ lakhs)", unit="lakhs"))
        b.covered.append("cash flows")
    bt = find(ctx.tables, ["borrowings"], header=["lender"])
    if bt:
        b.add("Indebtedness", para("For details of our borrowings, see “Financial Indebtedness”."))
        b.covered.append("indebtedness")
    cl = find(ctx.tables, ["litigation", "restated_fs"], title=r"contingent")
    if cl:
        b.add("Contingent Liabilities", table_block(cl, caption="Contingent liabilities (₹ lakhs)", unit="lakhs"))
        b.covered.append("contingent liabilities")
    rpt = find(ctx.tables, ["group_rpt"], header=["related party"])
    if rpt:
        b.add("Related Party Transactions", table_block(rpt, caption="Related party transactions (₹ lakhs)", unit="lakhs"))
        b.covered.append("related party transactions")


def b_summary(ctx: Ctx, b: Build):
    b.narrative += ["Primary Business", "Industry"]
    sub = Build()
    b_the_offer(ctx, sub)
    for s, bl in sub.parts:
        b.add("Offer Size", *[x for x in bl if x["type"] == "table"])
    t = find(ctx.tables, ["objects_cost", "offer_note"], header=["object"], any_header=["estimated amount", "total"])
    if t:
        b.add("Objects of the Offer", table_block(t, caption="Objects of the Offer (₹ lakhs)", unit="lakhs", cols=["object", "estimated"]))
    sh = find(ctx.tables, ["share_capital", "offer_note"], header=["shareholder", "pre-issue"])
    if sh:
        b.add("Pre-Offer Shareholding of the Promoters and Promoter Group", table_block(sh, cols=["shareholder", "category", "pre-issue shares", "% pre-issue"],
                                                                                         rows=rows_matching(sh, r"promoter", col=sh.col("category") or 1)))
    fs = Build()
    b_summary_financials(ctx, fs)
    for s, bl in fs.parts:
        if s:
            b.add(f"Summary Financial Information: {s}", *[x for x in bl if x["type"] == "table"])
    lit = find(ctx.tables, ["litigation"], header=["category", "company"])
    if lit:
        b.add("Summary of Outstanding Litigation", table_block(lit, caption=""))
    rpt = find(ctx.tables, ["group_rpt"], header=["related party"])
    if rpt:
        b.add("Summary of Related Party Transactions", table_block(rpt, caption="", unit="lakhs"))
    b.covered += ["offer size", "objects", "pre-issue shareholding", "summary financials", "outstanding litigation", "related party transactions"]


BUILDERS = {
    "the_offer": b_the_offer,
    "offer_structure": lambda c, b: b_the_offer(c, b, structure=True),
    "capital_structure": b_capital_structure,
    "objects": b_objects,
    "summary_financials": b_summary_financials,
    "other_financial": b_other_financial,
    "basis_price": lambda c, b: b_other_financial(c, b, basis=True),
    "capitalisation": b_capitalisation,
    "indebtedness": b_indebtedness,
    "litigation": b_litigation,
    "approvals": b_approvals,
    "management": b_management,
    "promoters": b_promoters,
    "group_companies": b_group_companies,
    "business": b_business,
    "history": b_history,
    "mdna": b_mdna,
    "summary": b_summary,
}


def build(key, ctx: Ctx) -> Build | None:
    fn = BUILDERS.get(key)
    if not fn:
        return None
    b = Build()
    fn(ctx, b)
    b.covered = list(dict.fromkeys(b.covered))
    b.narrative = list(dict.fromkeys(b.narrative))
    return b
