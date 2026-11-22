"""Risk factors from red flags in the issuer's own files.

    risk_factors(ctx) -> (blocks, flags)

Each rule looks for evidence (register rows, schedule tables or sentences) and, when found, writes one
numbered risk factor: a bold risk statement, the issuer-specific facts with their source, the consequence
and a cross-reference. Rules that find nothing write nothing. Offer-related risks that every SME DRHP
carries are added from templates and marked as such.
"""
from __future__ import annotations

import re

from extract.tables import find
from . import fmt
from .builders import Ctx, PH, rows_matching

CONSEQ = "Any such event may adversely affect our business, results of operations, cash flows and financial condition."


def _src_row(t, r):
    i = t.rows.index(r) if r in t.rows else 0
    return {"file_id": t.file_id, "file_name": t.file_name, "loc": t.row_locs[i] if i < len(t.row_locs) else t.loc,
            "snippet": " | ".join(c for c in r if c)[:300]}


def _flag(key, group, title, body, sources, xref):
    return {"key": key, "group": group, "title": title, "body": body, "sources": sources, "xref": xref}


def _cell(t, r, *words):
    i = t.col(*words)
    return r[i] if i is not None and i < len(r) else ""


def rule_approvals(ctx: Ctx):
    t = find(ctx.tables, ["approvals"], header=["approval", "status"])
    out = []
    if t:
        bad = [r for r in t.rows if re.search(r"expir|applied|pending|not (yet )?obtained|yet to", _cell(t, r, "status"), re.I)]
        expired = [r for r in bad if re.search(r"expir", _cell(t, r, "status") + _cell(t, r, "valid"), re.I)]
        if expired:
            items = "; ".join(f"{_cell(t, r, 'approval')} ({_cell(t, r, 'number')}), valid up to {_cell(t, r, 'valid')}: {_cell(t, r, 'status')}"
                              for r in expired[:4])
            out.append(_flag("approvals_expired", "internal",
                             "Certain approvals required for our business have expired and our applications for renewal are pending.",
                             f"The following approval(s) of our Company have expired: {items}. If the renewal is delayed or refused, we may be required to "
                             f"stop or restrict operations at the affected premises and may be subject to penalties. {CONSEQ}",
                             [_src_row(t, r) for r in expired[:4]], "Government and Other Approvals"))
        pending = [r for r in bad if r not in expired]
        if pending:
            items = "; ".join(f"{_cell(t, r, 'approval')}: {_cell(t, r, 'status')}" for r in pending[:5])
            out.append(_flag("approvals_pending", "internal",
                             "We are yet to obtain, or have applied for, certain approvals.",
                             f"As on the date of this Draft Red Herring Prospectus: {items}. There is no assurance that these will be granted in time or at all. {CONSEQ}",
                             [_src_row(t, r) for r in pending[:5]], "Government and Other Approvals"))
    return out


def rule_ip(ctx: Ctx):
    t = find(ctx.tables, ["insurance_ip", "business_note", "approvals"], header=["mark", "status"])
    if not t:
        return []
    bad = [r for r in t.rows if re.search(r"objected|opposed|refused|abandoned|pending|not (yet )?registered", _cell(t, r, "status"), re.I)]
    if not bad:
        return []
    def num(r):                      # the register may head the column "Application no." or "Registration no."
        v = _cell(t, r, "application") or _cell(t, r, "registration") or _cell(t, r, "no.")
        return f" (no. {v})" if v else ""
    items = "; ".join(f"{r[0]}{num(r)}: {_cell(t, r, 'status')}" for r in bad[:4])
    return [_flag("ip", "internal", "We may not be able to protect our intellectual property; some of our trade marks are not registered in our name or are still applications.",
                  f"{items}. If registration is refused, we may not be able to prevent others from using similar marks and may have to rebrand. {CONSEQ}",
                  [_src_row(t, r) for r in bad[:4]], "Our Business — Intellectual Property")]


def rule_customers(ctx: Ctx):
    hits = ctx.sentences(r"top[- ]?(10|ten|5|five)\s+customers.{0,80}\d+(\.\d+)?\s?%|\d+(\.\d+)?\s?% of (our )?revenue.{0,60}top", ["business_note", "offer_note", "operational_data"], 2, prose_only=True)
    t = find(ctx.tables, ["operational_data", "business_note"], header=["customer"], title=r"customer")
    srcs = [s for _, s in hits]
    share, period = "", ""
    if hits:
        m = re.search(r"(\d+(?:\.\d+)?)\s?%", hits[0][0])
        share = m.group(1) + "%" if m else ""
        per = re.search(r"%.{0,60}?\b(?:in|for|during)\s+((?:H[12]\s+)?FY\s?[\d-]+(?:\s?[\d-]+)?)", hits[0][0])
        period = f" in {per.group(1).strip()}" if per else ""
    top1 = ""
    if t and t.rows:
        # only a column that is a share (its header says % or share) is a percentage: the last column of a customer table is
        # often an amount in lakhs (22 Nov 2026: "accounted for 952.06% of revenue")
        share_cols = [i for i, h in enumerate(t.header) if re.search(r"%|share|per ?cent", h, re.I)]
        if share_cols:
            last = share_cols[-1]
            v = t.rows[0][last]
            if fmt.parse(v) is not None and 0 < fmt.parse(v) <= 100:
                top1 = f" Our largest customer accounted for {fmt.pct(v)} of revenue from operations in {t.header[last]}."
                srcs.append(_src_row(t, t.rows[0]))
    if not srcs:
        return []
    lead = f"Our top-10 customers contributed {share} of our revenue from operations{period}" if share else "A significant part of our revenue comes from a limited number of customers"
    return [_flag("customers", "internal", "We depend on a limited number of customers for a significant portion of our revenue.",
                  f"{lead} (see {srcs[0]['file_name']}).{top1} We do not have long-term contracts with most of our customers. The loss of, or a significant "
                  f"reduction in orders from, any of these customers may adversely affect our revenue and profitability.",
                  srcs[:3], "Our Business — Our Customers")]


def rule_rpt(ctx: Ctx):
    t = find(ctx.tables, ["group_rpt", "people_profiles"], header=["related party"])
    lease = ctx.sentences(r"(leave and licen[cs]e|lease).{0,120}(related party|promoter|director)|(related party|promoter).{0,80}(leave and licen[cs]e|lease)",
                          ["lease", "business_note", "group_rpt"], 1, prose_only=True)
    if not (t or lease):
        return []
    body, srcs = [], []
    if t:
        last = len(t.header) - 1
        party = t.col("related party")
        rows = [r for r in t.rows if fmt.parse(r[last]) is not None and not re.match(r"total", r[0], re.I)
                and (party is None or r[party].strip())]
        top = sorted(rows, key=lambda r: -abs(fmt.parse(r[last])))[:3]
        if top:
            body.append("In " + t.header[last] + ", our related party transactions included " +
                        "; ".join(f"{r[0].lower()} with {r[1]} of ₹ {fmt.lakhs(r[last])} lakhs" for r in top) + ".")
            srcs += [_src_row(t, r) for r in top]
    if lease:
        body.append(lease[0][0])
        srcs.append(lease[0][1])
    return [_flag("rpt", "internal", "We have entered into, and will continue to enter into, related party transactions, including with our Promoters.",
                  " ".join(body) + " There can be no assurance that such transactions could not have been made on more favourable terms with unrelated parties, "
                  "and they may involve conflicts of interest.", srcs, "Restated Financial Information — Related Party Transactions")]


def rule_lender(ctx: Ctx):
    hits = ctx.sentences(r"(no[- ]objection|NOC|consent).{0,80}(bank|lender)|(bank|lender).{0,80}(no[- ]objection|NOC|consent)|negative covenant|restrictive covenant",
                         ["offer_note", "sanction_letter", "borrowings", "business_note"], 3, prose_only=True)
    pend = [h for h in hits if re.search(r"pending|not yet|yet to|awaited|to be obtained|applied", h[0], re.I)] or hits
    if not pend:
        return []
    return [_flag("lender", "internal", "Our financing agreements contain restrictive covenants, and the consent of our lender for the Offer is pending.",
                  " ".join(h[0] for h in pend[:2]) + " Failure to obtain the consent, or a breach of the covenants, may lead to the lender recalling "
                  "the facilities or enforcing its security. " + CONSEQ, [h[1] for h in pend[:2]], "Financial Indebtedness")]


def rule_litigation(ctx: Ctx):
    t = find(ctx.tables, ["litigation"], header=["category", "company"])
    if not t:
        return []
    lakhs = bool(ctx.sentences(r"amounts? in .{0,3}\s?lakhs", ["litigation"], 1, prose_only=True))   # the certificate's own note on its unit
    hits, rows = [], []
    for r in t.rows:
        for i, h in enumerate(t.header[1:], start=1):
            v = r[i] if i < len(r) else ""
            if v and not re.match(r"^(nil|-|–|0|none|na|n\.a\.|not applicable)$", v.strip(), re.I) and not re.match(r"total", r[0], re.I):
                cat = re.sub(r"\s*-\s*(by|against)\b.*$|\s*\(.*?\)", "", r[0]).strip().lower()
                by = bool(re.search(r"-\s*by\b", r[0], re.I))
                m = re.match(r"^(\d+)\s*\(([\d,.]+|not quantified)\)$", v.strip(), re.I)
                if m:       # "1 (31.20)": a number of cases and the amount involved
                    n, amt = int(m.group(1)), m.group(2)
                    v = f"{n} case{'s' if n != 1 else ''}" + (f" (amount not quantified)" if amt.lower().startswith("not") else
                                                                 f" (amount involved: ₹ {amt} lakhs)" if lakhs else f" (amount involved: {amt})")
                hits.append(f"{cat} {'initiated by' if by else 'involving'} our {h.split('(')[0].strip().lower()}: {v}")
                if r not in rows:
                    rows.append(r)
    if not hits:
        return []
    return [_flag("litigation", "internal", "There are outstanding legal proceedings involving our Company, Promoters and Group Companies.",
                  "As certified by our legal counsel, outstanding proceedings include " + "; ".join(hits[:6]) +
                  ". An adverse outcome may result in liabilities, penalties or restrictions on our operations. " + CONSEQ,
                  [_src_row(t, r) for r in rows], "Outstanding Litigation and Material Developments")]


def rule_contingent(ctx: Ctx):
    t = find(ctx.tables, ["litigation", "restated_fs"], title=r"contingent")
    if not t or not t.rows:
        return []
    last = len(t.header) - 1
    tot = next((r for r in t.rows if re.match(r"total", r[0], re.I)), None)
    items = [r for r in t.rows if r is not tot and fmt.parse(r[last]) not in (None, 0)]
    if not items:
        return []
    txt = "; ".join(f"{r[0]}: ₹ {fmt.lakhs(r[last])} lakhs" for r in items[:4])
    total = f" aggregating ₹ {fmt.lakhs(tot[last])} lakhs" if tot and fmt.parse(tot[last]) is not None else ""
    return [_flag("contingent", "internal", "We have contingent liabilities which, if they materialise, may affect our financial condition.",
                  f"As at {t.header[last]}, our contingent liabilities{total} comprised {txt}.",
                  [_src_row(t, r) for r in items[:4] + ([tot] if tot else [])], "Restated Financial Information")]


def rule_text(ctx: Ctx, key, rx, doc_types, title, tail, xref, group="internal", limit=2, prose_only=False, row_note=""):
    """One risk factor from sentences matching rx. prose_only reads sentences only; a match found only in a table or a
    spreadsheet row (a quotation line is not a sentence) is then stated as row_note, with the row as its source."""
    hits = ctx.sentences(rx, doc_types, limit, prose_only=prose_only)
    if not hits and prose_only and row_note:
        rows = ctx.sentences(rx, doc_types, 1)
        if rows:
            return [_flag(key, group, title, f"{row_note} {tail}", [rows[0][1]], xref)]
    if not hits:
        return []
    return [_flag(key, group, title, " ".join(h[0] for h in hits) + " " + tail, [h[1] for h in hits], xref)]


def rule_cash_flow(ctx: Ctx):
    t = find(ctx.tables, ["restated_workings", "restated_fs"], header=["particulars"], title=r"cash flow|\bCF!")
    if not t:
        return []
    neg, rows = [], []
    for r in t.rows:
        if re.search(r"net cash", r[0], re.I):
            for i, h in enumerate(t.header[1:], start=1):
                v = fmt.parse(r[i]) if i < len(r) else None
                if v is not None and v < 0:
                    neg.append(f"{r[0].lower()} of ₹ {fmt.lakhs(v)} lakhs in {h}")
                    if r not in rows:
                        rows.append(r)
    if not neg:
        return []
    return [_flag("cash_flow", "internal", "We have had negative cash flows in the past and may have them in the future.",
                  "Our restated cash flows show " + "; ".join(neg[:4]) + ". Negative cash flows may affect our ability to fund operations and capital expenditure.",
                  [_src_row(t, r) for r in rows], "Management's Discussion and Analysis — Cash Flows")]


TEMPLATE_OFFER_RISKS = [
    ("There has been no prior public market for our Equity Shares, and the price may fluctuate after listing.",
     "The Offer Price will be determined through the Book Building Process and may not be indicative of the market price after listing. "
     "An active trading market may not develop or be sustained."),
    ("The Equity Shares will be listed on an SME platform, where liquidity is typically lower and trading is subject to market making requirements.",
     "Trading on the SME platform is in the minimum lot size prescribed and may be less liquid than the main board (to be confirmed by the BRLM)."),
    ("Our Promoters will continue to hold a majority of our Equity Shares after the Offer and can influence our decisions.",
     "After the Offer, our Promoters and Promoter Group will hold [●]% of our post-Offer paid-up share capital."),
    ("Any future issue of Equity Shares may dilute your shareholding, and sales by our Promoters may affect the trading price.", ""),
    ("The Offer includes an Offer for Sale; our Company will not receive the proceeds of the Offer for Sale.", "offer_for_sale"),
]


def risk_factors(ctx: Ctx):
    flags = []
    flags += rule_approvals(ctx)
    flags += rule_lender(ctx)
    flags += rule_customers(ctx)
    flags += rule_rpt(ctx)
    flags += rule_litigation(ctx)
    flags += rule_contingent(ctx)
    flags += rule_ip(ctx)
    flags += rule_text(ctx, "insurance", r"not (yet )?(taken|obtained|availed).{0,40}insurance|insurance.{0,40}not (yet )?(taken|obtained)|D&O.{0,60}not",
                       ["insurance_ip", "business_note"], "Our insurance cover may not be adequate, and we do not have certain insurance policies.",
                       "Losses beyond, or not covered by, our policies may have to be borne by us. " + CONSEQ, "Our Business — Insurance")
    flags += rule_text(ctx, "lei", r"\bLEI\b.{0,80}not|Legal Entity Identifier.{0,80}not", ["approvals", "business_note"],
                       "We have not yet obtained a Legal Entity Identifier.", "This may restrict certain banking and capital-market transactions until obtained.",
                       "Government and Other Approvals", limit=1)
    flags += rule_text(ctx, "single_plant", r"single (manufacturing )?(plant|facility|location|unit)|all (of )?our (manufacturing|production).{0,40}(one|single)",
                       ["business_note"], "All our manufacturing is at a single facility; any disruption there would affect our operations.",
                       CONSEQ,
                       "Our Business — Manufacturing Facility", limit=1)
    flags += rule_text(ctx, "audit_remark", r"emphasis of matter|qualified opinion|adverse (remark|opinion)|qualification", ["audited_fs", "restated_fs", "business_note"],
                       "Our statutory auditor has included an emphasis of matter or remarks in its reports for past periods.",
                       "Investors should read the auditor's reports in full; such remarks may indicate weaknesses in our accounting or controls.",
                       "Restated Financial Information", limit=2)
    flags += rule_text(ctx, "not_appraised", r"not (been )?appraised", ["offer_note", "objects_cost"],
                       "Our funding requirements and the deployment of the Net Proceeds are based on management estimates and have not been appraised by any bank or financial institution.",
                       "The estimates may change and the actual cost may be higher; the deployment is at the discretion of our Board, subject to the monitoring under applicable law.",
                       "Objects of the Offer", limit=1)
    flags += rule_text(ctx, "forex", r"\b(EUR|USD|foreign currency|imported)\b.{0,80}(₹|INR|quotation|machine)|exchange rate", ["offer_note", "objects_cost", "quotation"],
                       "Part of the plant and machinery is imported and priced in foreign currency; exchange rate movements may increase the cost of the objects.",
                       "Any increase will have to be met from internal accruals or borrowings.", "Objects of the Offer", limit=1,
                       prose_only=True, row_note="Part of the equipment proposed to be bought from the Net Proceeds is quoted in foreign currency.")
    flags += rule_text(ctx, "group_conflict", r"(group compan|promoter group|partnership|firm|LLP).{0,160}(supplier|similar|same line|conflict|loose spices|competes?)",
                       ["group_rpt", "people_profiles", "business_note"],
                       "An entity connected with our Promoters is engaged in a related line of business, which may lead to conflicts of interest.",
                       "Any conflict of interest could affect our business and the interests of our shareholders.", "Our Group Companies", limit=1, prose_only=True)
    flags += rule_cash_flow(ctx)
    flags += rule_text(ctx, "raw_material", r"(raw material|polymer|film).{0,60}(price|cost).{0,60}(volatil|fluctuat|crude)", ["business_note", "industry_report"],
                       "Our business depends on the availability and price of raw materials, which are volatile.",
                       "We may not be able to pass on cost increases to our customers in time or at all. " + CONSEQ,
                       "Our Business — Raw Materials", group="external", limit=1)
    flags += rule_text(ctx, "plastic_regulation", r"plastic waste|extended producer responsibility|\bEPR\b|single-use plastic", ["business_note", "industry_report", "approvals"],
                       "Changes in regulations on plastic packaging and waste management may affect demand for our products and increase our costs.",
                       "Compliance with extended producer responsibility and any restriction on multi-layer plastics may require changes to our products and processes.",
                       "Key Industry Regulations and Policies", group="external", limit=1)
    ofs = (ctx.offer.get("ofs_shares") or "").strip() not in ("", "0", PH)
    for title, body in TEMPLATE_OFFER_RISKS:
        if body == "offer_for_sale":
            if not ofs:
                continue
            body = f"The proceeds of the Offer for Sale will be paid to the Selling Shareholder, {ctx.o('selling_shareholder')}, net of its share of the Offer expenses."
        flags.append(_flag("offer_" + str(len(flags)), "offer", title, body or "", [], "The Offer", ) | {"template": True})

    # one risk factor per piece of evidence: a later rule that only repeats an earlier one's source is dropped
    used, kept = set(), []
    for f in flags:
        locs = {(s.get("file_id"), s.get("loc"), s.get("snippet", "")[:60]) for s in f["sources"]}
        if locs and locs <= used:
            continue
        snippet_dup = any(s.get("snippet", "")[:60] in {u[2] for u in used} for s in f["sources"] if s.get("snippet"))
        if f["sources"] and snippet_dup and not f.get("template"):
            continue
        used |= locs
        kept.append(f)
    flags = kept

    blocks = [{"type": "paragraph", "text": "An investment in equity shares involves a high degree of risk. Investors should carefully consider all the information "
               "in this Draft Red Herring Prospectus, including the risks described below, before making an investment in the Equity Shares. The risks are not "
               "the only ones relevant to us or the Equity Shares. Unless otherwise stated, the financial information in this section is derived from the Restated "
               "Financial Information.", "facts": [], "sources": []}]
    n = 0
    for group, head in (("internal", "Internal Risk Factors"), ("external", "External Risk Factors"), ("offer", "Risks Relating to the Offer")):
        gf = [f for f in flags if f["group"] == group]
        if not gf:
            continue
        blocks.append({"type": "heading", "text": head, "facts": []})
        for f in gf:
            n += 1
            xref = f" For further details, see “{f['xref']}” on page {PH}." if f.get("xref") and group != "offer" else ""
            blocks.append({"type": "paragraph", "text": f"{n}. **{f['title']}** {f['body']}{xref}".strip(), "facts": [],
                           "sources": f["sources"], "flag": f["key"], "template": bool(f.get("template"))})
    return blocks, flags
