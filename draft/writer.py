"""Section writers. Every writer returns the same draft shape:

    {"blocks": [{"type": "heading"|"paragraph"|"table"|"note", "text", "rows"?, "facts": [fact ids]}],
     "writer", "engine", "routed": [fact ids], "latency_s", "usage"}

Placeholders are always the literal "[●]"; the writers never guess a value the inputs do not give.
Template text avoids numeric SEBI rules; anything regulatory is marked "(to be confirmed by the BRLM)".
"""
from __future__ import annotations

import re
import time

from data.prompts import drafting_messages, summary_of, trim_repeats
from verify.checks import RE_FIGURE, mask_ungrounded, num_key
from extract.canonical import current
from extract.tables import find, tables_from_blocks
from .builders import Build, Ctx, build, table_block
from .outline import SECTION_BY_KEY
from .red_flags import risk_factors
from .router import route

ROUTER_K_INFER = 40      # facts per sub-heading at inference; training inputs are own facts + about as many distractors
# Decoding penalty for drafts, the value the drafting evaluations used (vm/predict_qa.py, vm/rag_eval.py). It lowers
# loops but does not remove them (MODEL_CARD: 19% of drafts still loop), so trim_repeats cuts what remains.
DRAFT_FREQUENCY_PENALTY = 0.3

PH = "[●]"

# ---------- helpers ----------

def fact_text(f):
    unit = f.get("unit") or ""
    val = f["value"]
    if unit.startswith("₹"):
        s = f"₹ {val} {unit[2:]}".strip() if unit != "₹" else f"₹ {val}"
    elif unit == "%":
        s = f"{val}%"
    elif f["type"] == "identifier":
        s = val
    else:
        s = f"{val} {unit}".strip()
    return s


def offer_value(offer: dict, key: str) -> str:
    v = (offer or {}).get(key)
    return str(v).strip() if v not in (None, "") else PH


def find_fact(facts, *words, types=None):
    words = [w.lower() for w in words]
    for f in facts:
        lab = f["label"].lower()
        if all(w in lab for w in words) and (types is None or f["type"] in types):
            return f
    return None


def company_name(project):
    return (project.get("offer") or {}).get("company_name") or project.get("name") or PH


# ---------- template sections ----------

def _templates(project, facts):
    o = project.get("offer") or {}
    co = company_name(project)
    cin = current([f for f in facts if f.get("unit") == "CIN" or f["label"] == "CIN"])
    board = {"bse_sme": "BSE SME", "nse_emerge": "NSE Emerge"}.get(o.get("board"), PH)
    lm = offer_value(o, "lead_manager")
    reg = offer_value(o, "registrar")
    ro = offer_value(o, "registered_office")
    cs = offer_value(o, "company_secretary")
    auditor = offer_value(o, "statutory_auditor")
    t = {
        "definitions": [
            ("table", [["Term", "Description"],
                       ["“our Company”, “the Company”, “the Issuer”", f"{co}, a public limited company incorporated under the Companies Act"],
                       ["“we”, “us”, “our”", f"Unless the context otherwise requires, {co}"],
                       ["Book Running Lead Manager / BRLM", lm],
                       ["Registrar to the Offer", reg],
                       ["Statutory Auditor / Peer Review Auditor", auditor],
                       ["Stock Exchange", board],
                       ["SEBI ICDR Regulations", "Securities and Exchange Board of India (Issue of Capital and Disclosure Requirements) Regulations, 2018, as amended"],
                       ["Companies Act", "The Companies Act, 2013 and the rules made thereunder, as amended"]]),
        ],
        "conventions": [
            ("paragraph", f"Unless stated otherwise, the financial information in this Draft Red Herring Prospectus is derived from the Restated Financial Information of {co}, prepared in accordance with the Companies Act and Indian GAAP and restated in accordance with the SEBI ICDR Regulations."),
            ("paragraph", "All figures are presented in ₹ lakhs unless stated otherwise. Our Company's financial year commences on April 1 and ends on March 31 of the following calendar year."),
            ("paragraph", "Industry and market data used in this Draft Red Herring Prospectus has been derived from the industry report commissioned by our Company. Neither our Company nor the BRLM has independently verified such data."),
        ],
        "forward_looking": [
            ("paragraph", "This Draft Red Herring Prospectus contains certain “forward-looking statements”. These statements can generally be identified by words such as “aim”, “anticipate”, “believe”, “expect”, “estimate”, “intend”, “objective”, “plan”, “project”, “will” and similar expressions."),
            ("paragraph", "Forward-looking statements reflect our current views with respect to future events and are not a guarantee of future performance. Actual results may differ materially from those suggested by the forward-looking statements due to risks or uncertainties, including those described in “Risk Factors”."),
        ],
        "general_info": [
            ("table", [["Particulars", "Details"],
                       ["Name of the Company", co],
                       ["Corporate Identification Number", cin["value"] if cin else PH],
                       ["Registered Office", ro],
                       ["Company Secretary and Compliance Officer", cs],
                       ["Book Running Lead Manager", lm],
                       ["Registrar to the Offer", reg],
                       ["Statutory and Peer Review Auditor", auditor],
                       ["Market Maker", offer_value(o, "market_maker")],
                       ["Designated Stock Exchange", board]]),
            ("paragraph", "Whether a monitoring agency, credit rating, debenture trustee or appraising entity is required for the Offer will be as per the SEBI ICDR Regulations (to be confirmed by the BRLM)."),
        ],
        "regulations": [
            ("paragraph", "The following is an overview of certain laws and regulations in India which are relevant to our business. The description is based on the current provisions of applicable law, which are subject to change. It is not exhaustive and is not a substitute for professional legal advice."),
            ("heading", "Industry-specific and environmental laws"),
            ("paragraph", "The Factories Act, 1948; the Water (Prevention and Control of Pollution) Act, 1974; the Air (Prevention and Control of Pollution) Act, 1981; the Environment (Protection) Act, 1986 and the rules thereunder, including the Plastic Waste Management Rules, 2016 [VERIFY applicability]."),
            ("heading", "Tax and labour laws"),
            ("paragraph", "The Central Goods and Services Tax Act, 2017 and corresponding state laws; the Income-tax Act; and the labour codes and laws applicable to our employees [VERIFY]."),
        ],
        "group_companies": [
            ("paragraph", f"In terms of the SEBI ICDR Regulations and the materiality policy adopted by our Board, the group companies of {co} are set out below. Details are derived from the group companies and related party file provided."),
        ],
        "dividend_policy": [
            ("paragraph", f"The declaration and payment of dividends by {co} will be recommended by our Board and approved by our shareholders at their discretion, subject to the provisions of the Articles of Association and the Companies Act. Our Company has adopted a dividend policy approved by the Board on {PH}."),
        ],
        "regulatory": [
            ("heading", "Authority for the Offer"),
            ("paragraph", f"The Offer has been authorised by a resolution of our Board dated {offer_value(o, 'board_resolution_date')} and by a special resolution of our shareholders dated {offer_value(o, 'shareholder_resolution_date')}."),
            ("heading", "Eligibility for the Offer"),
            ("paragraph", f"Our Company is eligible for the Offer in accordance with Chapter IX of the SEBI ICDR Regulations and the eligibility norms of {board} (to be confirmed by the BRLM)."),
            ("heading", "Prohibition by SEBI or other governmental authorities"),
            ("paragraph", "Our Company, our Promoters, members of the Promoter Group and our Directors have not been prohibited from accessing the capital market or debarred from buying, selling or dealing in securities by SEBI or any other authority [VERIFY with declarations]."),
        ],
        "terms": [
            ("paragraph", f"The Equity Shares being offered are subject to the provisions of the Companies Act, the SEBI ICDR Regulations, the Memorandum and Articles of Association of {co}, the terms of the Red Herring Prospectus, and the terms and conditions of the listing agreement with {board}."),
            ("paragraph", f"The Equity Shares shall rank pari passu in all respects with the existing Equity Shares of our Company. The face value of each Equity Share is ₹ {offer_value(o, 'face_value')} and the Offer Price is {PH}."),
        ],
        "offer_procedure": [
            ("paragraph", "All Applicants shall apply in the Offer only through the ASBA process or the UPI mechanism, as applicable, in accordance with the General Information Document and SEBI circulars in force (to be confirmed by the BRLM)."),
            ("paragraph", f"The Bid/Offer Opening Date is {PH} and the Bid/Offer Closing Date is {PH}."),
        ],
        "foreign_ownership": [
            ("paragraph", "Foreign investment in Indian securities is regulated through the Industrial Policy of the Government of India and FEMA. The applicable sectoral cap and route for investment in our Company will be confirmed by the BRLM and legal counsel (to be confirmed by the BRLM)."),
        ],
        "material_contracts": [
            ("paragraph", f"Copies of the following contracts and documents will be available for inspection at the Registered Office of {co} from {PH} until the Bid/Offer Closing Date."),
            ("table", [["#", "Document"], ["1", "Offer Agreement between our Company and the BRLM"],
                       ["2", "Registrar Agreement"], ["3", "Market Making Agreement"], ["4", "Underwriting Agreement"],
                       ["5", "Certified copies of the Memorandum and Articles of Association"],
                       ["6", f"Board resolution dated {offer_value(o, 'board_resolution_date')} and shareholders' resolution dated {offer_value(o, 'shareholder_resolution_date')}"],
                       ["7", "Examination report on the Restated Financial Information"],
                       ["8", "Statement of special tax benefits"], ["9", "Industry report"]]),
        ],
        "declaration": [
            ("paragraph", "We hereby certify and declare that all relevant provisions of the Companies Act and the rules, regulations and guidelines issued by the Government of India or SEBI have been complied with, and that no statement made in this Draft Red Herring Prospectus is contrary to the provisions of the Companies Act, the SEBI Act or the rules, regulations or guidelines made thereunder."),
            ("paragraph", "Signed by the Directors, the Chief Financial Officer and the Company Secretary of our Company. Place: [●]  Date: [●]"),
        ],
    }
    return t


def write_template(key, project, facts):
    raw = _templates(project, facts).get(key, [("paragraph", PH)])
    blocks = []
    for kind, content in raw:
        if kind == "table":
            blocks.append({"type": "table", "rows": content, "text": "", "facts": []})
        else:
            blocks.append({"type": kind, "text": content, "facts": []})
    return blocks


# ---------- inserted sections ----------

def write_inserted(key, project, files):
    sec = SECTION_BY_KEY[key]
    src = [f for f in files if f.get("doc_type") in sec["needs"]]
    if not src:
        return [{"type": "note", "text": f"{PH} To be inserted as provided. Missing input: {', '.join(sec['needs'])}.", "facts": []}]
    names = ", ".join(f["name"] for f in src)
    return [{"type": "paragraph", "text": f"[Inserted as provided by the issuer, without modification: {names}]", "facts": []},
            {"type": "note", "text": f"Source file(s): {names}. The assembler appends the original document at this position in the exported draft.", "facts": []}]


# ---------- SLM output ----------


def parse_markdown(text):
    blocks = []
    for chunk in re.split(r"\n\s*\n", text.strip()):
        chunk = chunk.strip()
        if not chunk:
            continue
        lines = chunk.split("\n")
        if lines[0].startswith("#"):
            blocks.append({"type": "heading", "text": lines[0].lstrip("#").strip().strip("*"), "facts": []})
            rest = "\n".join(lines[1:]).strip()
            if rest:
                blocks.append({"type": "paragraph", "text": rest, "facts": []})
        elif all(ln.strip().startswith("|") for ln in lines) and len(lines) >= 2:
            rows = [[c.strip() for c in ln.strip().strip("|").split("|")] for ln in lines if not re.match(r"^\s*\|?\s*:?-{3,}", ln)]
            blocks.append({"type": "table", "rows": rows, "text": "", "facts": []})
        else:
            blocks.append({"type": "paragraph", "text": chunk, "facts": []})
    return _join_split_sentences(blocks)


RE_OPEN_END = re.compile(r"(,|\bno\.|\bpages?|\bon|\bdated|\bof|\bto|\bfor|\band)$", re.I)


def _join_split_sentences(blocks):
    """A model draft sometimes puts a blank line inside a sentence ("dated October 31," / "2017 issued by ...", or
    "beginning on page no." / "99."). Read as two paragraphs, the verifier never sees the whole date or page number. A
    paragraph that ends open (a comma, "page no.", a connector) is joined to the next one when that one goes on in lower
    case or with a digit."""
    out = []
    for b in blocks:
        prev = out[-1] if out else None
        if (prev and prev["type"] == "paragraph" and b["type"] == "paragraph"
                and RE_OPEN_END.search(prev["text"].rstrip()) and re.match(r"[0-9a-z(]", b["text"])):
            prev["text"] = prev["text"].rstrip() + " " + b["text"]
        else:
            out.append(b)
    return out


# ---------- composing a section ----------

BRIEF_NOTE = "Drafting brief: the facts routed to this sub-heading. The fine-tuned SLM writes the prose from these when it is connected."


def brief(facts, sub, sec, doc_types, k=8):
    picks = [f for f in route(facts, f"{sub} {sec['query']}", sec["needs"], k=k * 2, doc_types=doc_types)
             if not f.get("superseded")][:k]
    return {"type": "brief", "text": BRIEF_NOTE, "sub": sub, "facts": [f["id"] for f in picks],
            "items": [{"fact_id": f["id"], "label": f["label"], "value": fact_text(f), "period": f.get("period", ""),
                       "file_name": f.get("file_name", ""), "loc": f.get("loc", "")} for f in picks]}


def _order(sec, b: Build, narrative):
    """Sub-headings in outline order, with builder-only sub-headings kept where the builder put them."""
    outline = sec["subheads"] or []
    built = [s for s, _ in b.parts if s]
    order, done = [], set()
    for s in built:
        for o in outline:
            if o == s:
                break
            if o not in done and (o in narrative or o in built):
                order.append(o)
                done.add(o)
        if s not in done:
            order.append(s)
            done.add(s)
    order += [o for o in outline + narrative if o not in done and (o in narrative or o in built) and not done.add(o)]
    return order


def attach_citations(blocks, facts):
    """Cite facts whose values appear in a paragraph (model output and builder sentences): verbatim, or for a
    number by value, so "1440" cites the fact "1,440.00"."""
    live = [f for f in facts if not f.get("superseded")]
    vals = [(f, str(f["value"]).strip()) for f in live if len(str(f["value"]).strip()) >= 4]
    by_num = {}
    for f in live:
        k = num_key(f["value"])
        if k is not None and len(str(f["value"]).replace(",", "").replace(".", "").strip()) >= 3:
            by_num.setdefault(k, f)
    for b in blocks:
        if b["type"] == "paragraph" and not b.get("facts"):
            ids = [f["id"] for f, v in vals if v in b["text"]]
            ids += [by_num[k]["id"] for k in (num_key(x) for x in RE_FIGURE.findall(b["text"])) if k in by_num]
            b["facts"] = list(dict.fromkeys(ids))[:8]
    return blocks


def compose(key, ctx: Ctx, llm=None):
    sec = SECTION_BY_KEY[key]
    facts = ctx.facts
    doc_types = {f["id"]: f.get("doc_type") for f in ctx.files}
    b = build(key, ctx) or Build()
    built = {s for s, _ in b.parts if s}
    narrative = list(b.narrative)
    if sec["writer"].startswith("slm"):
        narrative += [s for s in (sec["subheads"] or [sec["title"]]) if s not in built and s not in narrative]
    engine, usage, prose, looped = "code", {}, {}, []
    if narrative and llm is not None:
        # one call per sub-heading, in the format the student is trained on (data/prompts.py)
        outline = _order(sec, b, narrative)
        prev, usage = "", {}
        for s in outline:
            if s not in narrative:
                prev = " ".join(x.get("text", "") for x in next((bl for x, bl in b.parts if x == s), []) if x.get("text"))
                continue
            routed = [f for f in route(facts, f"{s} {sec['query']}", sec["needs"], k=ROUTER_K_INFER, doc_types=doc_types)
                      if not f.get("superseded")]
            msgs = drafting_messages(ctx.company(), sec["title"], outline, s, routed, summary_of(prev) if prev else "")
            text, u = llm(msgs, frequency_penalty=DRAFT_FREQUENCY_PENALTY)
            for k, v in (u or {}).items():
                usage[k] = usage.get(k, 0) + (v if isinstance(v, (int, float)) else 0)
            # a greedy-decoded draft can loop on one sentence; cut it where the loop starts (data/prompts.py)
            text, cut = trim_repeats(text)
            if cut:
                looped.append(s)
            prose[s] = [blk for blk in parse_markdown(text) if blk["type"] != "heading"]
            for blk in prose[s]:                      # the model may not state what the inputs do not support
                if blk["type"] == "paragraph":
                    blk["text"], blk["masked"] = mask_ungrounded(blk["text"], facts, ctx.offer, f"{ctx.company()} {s}")
                elif blk["type"] == "table":          # table cells are prose too: a date or figure in a header is checked
                    rows, hits = [], []
                    for r in blk.get("rows", []):
                        cells = []
                        for c in r:
                            if isinstance(c, str) and c:
                                c, m = mask_ungrounded(c, facts, ctx.offer, f"{ctx.company()} {s}")
                                hits += m
                            cells.append(c)
                        rows.append(cells)
                    blk["rows"], blk["masked"] = rows, hits
            prev = text
        engine = "model"
    elif narrative:
        engine = "brief"
    blocks = []
    for s, bl in b.parts:
        if s is None:
            blocks += bl
    pending = []
    for s in _order(sec, b, narrative):
        if s != sec["title"] or len(narrative) > 1 or built:
            blocks.append({"type": "heading", "text": s, "facts": []})
        if s in narrative:
            if s in prose:
                blocks += prose[s]
            else:
                blocks.append(brief(facts, s, sec, doc_types))
                pending.append(s)
        blocks += next((bl for x, bl in b.parts if x == s), [])
    attach_citations(blocks, facts)
    if not blocks:
        blocks = [{"type": "note", "text": f"{PH} No input was found for this section.", "facts": []}]
    return blocks, engine if narrative else "code", usage, b, pending, looped


def write_section(key, ctx: Ctx, llm=None):
    """Draft one section. llm: callable(messages, frequency_penalty=...) -> (text, usage), or None (drafting briefs
    instead of prose). Sub-headings whose model draft looped are listed in "loop_trimmed"."""
    sec = SECTION_BY_KEY[key]
    facts = ctx.facts
    doc_types = {f["id"]: f.get("doc_type") for f in ctx.files}
    t0 = time.perf_counter()
    covered, missing, pending, usage, looped = [], [], [], {}, []
    if sec["writer"] == "template":
        blocks, engine = write_template(key, ctx.project, facts), "template"
        b = build(key, ctx)
        if b:
            for s, bl in b.parts:
                blocks += ([{"type": "heading", "text": s, "facts": []}] if s else []) + bl
        if key == "general_info":
            t = find(ctx.tables, ["offer_note"], header=["role", "name"])
            if t:
                blocks.append({"type": "heading", "text": "Intermediaries to the Offer", "facts": []})
                blocks.append(table_block(t, caption="Intermediaries"))
    elif sec["writer"] == "inserted":
        blocks, engine = write_inserted(key, ctx.project, ctx.files), "inserted"
    elif key == "risk_factors":
        blocks, flags = risk_factors(ctx)
        engine = "rules"
        covered = [c for c in sec["checklist"] if any(_rf_covers(c, f) for f in flags)]
    else:
        blocks, engine, usage, b, pending, looped = compose(key, ctx, llm)
        covered, missing = b.covered, b.missing
    routed = route(facts, f"{sec['title']} {sec['query']}", sec["needs"], doc_types=doc_types) if sec["query"] else []
    return {"blocks": blocks, "writer": sec["writer"], "engine": engine, "routed": [f["id"] for f in routed],
            "covered": covered, "missing": [{"item": m[0], "where": m[1]} for m in missing], "narrative_pending": pending,
            "loop_trimmed": looped, "latency_s": round(time.perf_counter() - t0, 3), "usage": usage}


RF_COVERS = {
    "internal risks": r".", "external risks": r"raw_material|plastic", "offer-related risks": r"^offer_",
    "outstanding litigation": r"litigation", "customer concentration": r"customers", "expired or pending approvals": r"approvals",
    "indebtedness and covenants": r"lender", "related party transactions": r"rpt", "contingent liabilities": r"contingent",
}


def _rf_covers(item, flag):
    rx = RF_COVERS.get(item)
    if not rx:
        return False
    if item == "internal risks":
        return flag["group"] == "internal"
    return bool(re.search(rx, flag["key"]))


def make_ctx(project, facts, files, load_blocks):
    """load_blocks(file_id) -> stored reader output or None."""
    blocks, tables = {}, []
    for f in files:
        if f.get("status") != "processed":
            continue
        got = load_blocks(f["id"]) or {}
        blocks[f["id"]] = got.get("blocks", [])
        tables += tables_from_blocks(blocks[f["id"]], f)
    return Ctx(project=project, facts=facts, files=files, tables=tables, blocks=blocks)
