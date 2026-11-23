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
from verify.claims import mask_event_dates, mask_future_dates, mask_malformed_amounts, mask_period_claims, mask_unit_claims
from verify.checks import RE_FIGURE, mask_misbased_percents,mask_ungrounded, mask_unknown_entities, misplaced_cells, num_key
from verify.places import mask_unknown_places
from extract.canonical import current
from extract.tables import find, tables_from_blocks
from .builders import NBSP, Build, Ctx, build, protect_abbrev, table_block
from .derive import derive_facts
from .slots import unknown_facts
from .outline import SECTION_BY_KEY
from .red_flags import risk_factors
from .router import route

ROUTER_K_INFER = 40      # facts per sub-heading at inference; training inputs are own facts + about as many distractors
# Decoding penalty for drafts. 0.3 was chosen on the first adapter, which looped in 19% of drafts. With the shipped adapter (DPO) it
# also makes the model reword the source: on a data room whose business note it copies from, the model dropped small words
# ("technical commercial comparison utilities inspect transformers switchgear") and added details the note does not have
# ("established at contract inception"). On the 89 test drafts (22 Nov 2026, one run each, three drafts per request, guarded):
#   0.3: fact use 0.659, loops 0.0%   0.1: fact use 0.714, loops 1.1%   0.0: fact use 0.686, loops 2.2%, slower
# and 0 of 89 drafts with an invented figure after the guard at all three. 0.1 is used; trim_repeats cuts the loops that remain.
DRAFT_FREQUENCY_PENALTY = 0.1
# Best of n (19 Nov 2026 fix plan 1.3): the endpoint writes n drafts of a sub-heading in one request, each is checked, and the
# one with the fewest masked values is kept (a looping draft loses a tie). vLLM shares the prompt across the n samples, so the
# cost is far below n times. 1 turns it off; a model client without n support always writes one draft.
DRAFT_BEST_OF = 3
BEST_OF_TEMPERATURE = 0.3

PH = "[●]"

# The typed facts the router returns are numbers, dates and short labels. For a business or history sub-heading they carry
# no description of what the issuer does, and a model given only those fills the gap from what it memorised in training
# (19 Nov 2026 dry run: "Our Business" described a manufacturer in Hyderabad; the issuer is an EPC contractor in Nagpur).
# So each narrative sub-heading also gets the issuer's own best-matching passages as facts, and a sub-heading the files
# do not speak to is not written: it stays a drafting brief and is listed in the review pack.
PASSAGE_FACTS = 4
PASSAGE_WORDS = 90
# The model's window is 32,768 tokens (the base model's native length; serve/runpod.py MAX_MODEL_LEN). A prompt is kept
# inside it: tokens are estimated at 3.2 characters each (an over-count for English, so it errs on the safe side), room
# is kept for the answer, and when the prompt is still too long the lowest-ranked facts and then passages are dropped.
CONTEXT_TOKENS = 32768
ANSWER_RESERVE = 3500 + 300           # max_tokens for a draft (the app's default is 3,000) and the chat template


def est_tokens(text):
    return int(len(text) / 3.2) + 1


def fit_messages(build, passages, routed, budget=CONTEXT_TOKENS - ANSWER_RESERVE):
    """build(passages, routed) -> messages. Drops facts from the low-ranked end, then passages, until the prompt fits
    the budget; returns (messages, number of items dropped). The first passage and the first five facts always stay."""
    passages, routed = list(passages), list(routed)
    dropped = 0
    msgs = build(passages, routed)
    while sum(est_tokens(m["content"]) for m in msgs) > budget and (len(routed) > 5 or len(passages) > 1):
        if len(routed) > 5:
            routed.pop()
        else:
            passages.pop()
        dropped += 1
        msgs = build(passages, routed)
    return msgs, dropped
GENERIC_TERMS = {"our", "overview", "details", "general", "certain", "other", "matters", "information", "description",
                 "summary", "key", "main", "and", "the", "of", "for", "with", "from", "about"}


def _stem(t):
    return re.sub(r"(ing|ed|es|s|ly)$", "", t) if len(t) > 5 else t


SKIP_NOTE_SECTIONS = re.compile(r"borrowing|related part|litigation|financ|contents|forward|history|working capital|restated|risk|regulation|not yet|approvals", re.I)


def business_subheads(ctx):
    """Sub-headings for "Our Business" taken from the issuer's own business note, so an EPC contractor is not asked for
    "Manufacturing Process" and "Raw Materials". [(heading, text)], or [] when there is no usable note."""
    return [(h, t) for h, t in ctx.note_sections() if len(t.split()) >= 40 and not SKIP_NOTE_SECTIONS.search(h)]


def note_passages(text, words=PASSAGE_WORDS, limit=14):
    """The note section cut into passages of about `words` words, each ending where a sentence ends (a passage cut
    mid-sentence is copied by the model as a broken sentence)."""
    sents = [x.replace(NBSP, ' ') for x in re.split(r'(?<=[.;:]) +(?=[A-Z(\u20b9\u2022\d])', protect_abbrev(' '.join(text.split()))) if x]
    out, cur, n = [], [], 0
    for x in sents:
        cur.append(x)
        n += len(x.split())
        if n >= words:
            out.append(" ".join(cur))
            cur, n = [], 0
    if cur:
        out.append(" ".join(cur))
    return out[:limit]


# Standard DRHP sub-headings name a kind of content, not a topic the files must repeat word for word ("Brief History" is
# written from a note that says "incorporated on ... converted ..."). Terms like these do not count as evidence terms, and a
# heading whose own term has a synonym is supported when a passage holds one (22 Nov 2026, Vidyunmaya data room: 14 sub-headings
# with plenty of source text were left as stubs because no passage held the word "brief" or "history").
GENERIC_TERMS |= {"brief", "primary", "significant", "factors", "affecting", "results", "operations", "comparison", "periods",
                  "discussion", "analysis", "condition", "management", "profiles", "government", "corporate", "material",
                  "financial", "business", "outstanding", "development", "developments"}
SUPPORT_SYNONYMS = {
    "history": ("incorporat", "milestone", "founded", "converted", "conversion"),
    "governance": ("committee", "independent director", "audit committee", "board of directors"),
    "approval": ("licence", "license", "registration", "certificate", "permit", "approval"),
    "agreement": ("agreement", "contract", "arrangement", "deed"),
    "director": ("director", "chairman", "managing director"),
    "office": ("registered office", "leave and licence"),
}
# Sub-headings of other sections that the issuer's business note answers under its own heading: (section, sub-heading regex,
# note heading regex). The note's passages come first, in order; retrieval adds what the other files hold.
NOTE_FOR_SUB = [
    ("history", r"history", r"history|milestone"),
    ("history", r"agreement", r"contracts|key contract"),
    ("summary", r"business", r"^overview$|segments"),
    ("mdna", r".", r"discussion|restated results|snapshot|kpi"),
    ("approvals", r".", r"approvals"),
]


# Sub-headings about an event are written only if some file states such an event. A file that says where the registered office is does
# not say that it changed; the model wrote "has not changed its registered office since incorporation" (22 Nov 2026).
REQUIRES_EVENT = [
    (r"changes? in (?:the )?registered office",
     r"change (?:in|of) (?:the )?registered office|registered office (?:was|has been|had been) (?:shifted|relocated|changed|transferred)|(?:shift|relocat)\w* (?:of )?(?:the )?registered office|registered office.{0,60}\b(?:shifted|relocated)\b"),
]


# Sub-headings that the issuer's own agreements answer: (section, sub-heading regex, document types). Their text is given as passages.
DOC_FOR_SUB = [
    ("history", r"agreement", ("material_agreement", "shareholder_agreement")),
]


def docs_for(ctx, sec_key, sub):
    """[(file name, passage)] from the files of the document types that answer a sub-heading (DOC_FOR_SUB)."""
    out = []
    for key, sub_rx, types in DOC_FOR_SUB:
        if key == sec_key and re.search(sub_rx, sub, re.I):
            for f in ctx.files:
                if f.get("doc_type") in types:
                    text = " ".join(b.get("text", "") for b in ctx.blocks.get(f["id"], []) if b.get("kind") in ("text", "ocr"))
                    out += [(f.get("name", ""), p) for p in note_passages(text, limit=4)]
    return out[:8]


def note_for(ctx, sec_key, sub):
    """Passages of the business note's sections that answer a sub-heading of another section (NOTE_FOR_SUB)."""
    out = []
    for key, sub_rx, head_rx in NOTE_FOR_SUB:
        if key == sec_key and re.search(sub_rx, sub, re.I):
            for h, t in ctx.note_sections():
                if re.search(head_rx, h, re.I):
                    out += [(h, p) for p in note_passages(t, limit=6)]
    return out[:10]


def passage_facts(ctx, sub, sec, k=PASSAGE_FACTS):
    """(facts, supported): the issuer's best passages for a sub-heading as fact dicts, and whether a passage that
    contains the sub-heading's own terms exists (a "Manufacturing Process" sub-heading is unsupported for an EPC firm)."""
    from rag.index import tokens
    own = dict(ctx.note_sections()).get(sub) if sec.get("key") == "business" else None
    if own:                                            # the note's own section, in order, is the best input there is
        return [{"id": f"n{i}", "type": "text", "label": f"Business note · {sub}", "value": p, "file_name": "business note",
                 "loc": sub, "snippet": p[:240], "origin": "passage"} for i, p in enumerate(note_passages(own))], True
    mapped = [{"id": f"n{i}", "type": "text", "label": f"Business note · {h}", "value": p, "file_name": "business note",
               "loc": h, "snippet": p[:240], "origin": "passage"} for i, (h, p) in enumerate(note_for(ctx, sec.get("key"), sub))]
    mapped += [{"id": f"d{i}", "type": "text", "label": n, "value": p, "file_name": n, "loc": "", "snippet": p[:240], "origin": "passage"}
               for i, (n, p) in enumerate(docs_for(ctx, sec.get("key"), sub))]
    try:
        ix = ctx.index()
    except Exception:                                  # noqa: BLE001  no index: fall back to typed facts alone
        return mapped, True
    query = f"{sub} {sec['query']}"
    hits = ix.search(query, k=k, kinds=("passage",), doc_types=set(sec["needs"]) or None)
    if len(hits) < k:
        seen = {h.chunk.id for h in hits}
        hits += [h for h in ix.search(query, k=k, kinds=("passage",)) if h.chunk.id not in seen][: k - len(hits)]
    terms = {_stem(t) for t in tokens(sub) if len(t) >= 4 and t.isalpha() and t not in GENERIC_TERMS}
    supported = not terms or bool(mapped)
    syn = [s for t in terms for s in SUPPORT_SYNONYMS.get(t, ())]
    out = list(mapped)
    for h in hits[:k]:
        words = h.chunk.text.split()
        text = " ".join(words[:PASSAGE_WORDS])
        have = {_stem(t) for t in tokens(h.chunk.text)}
        if terms and len(terms & have) >= (len(terms) if len(terms) <= 3 else round(0.6 * len(terms))):
            supported = True
        elif syn and any(s in h.chunk.text.lower() for s in syn) and len(terms) <= 1:
            supported = True                           # a one-term heading whose kind of content a passage holds
        out.append({"id": f"p{h.chunk.id}", "type": "text", "label": f"{h.chunk.file_name} {h.chunk.loc}".strip(),
                    "value": text, "file_id": h.chunk.file_id, "file_name": h.chunk.file_name, "loc": h.chunk.loc,
                    "snippet": text[:240], "origin": "passage"})
    if sub == sec.get("title") and (out or mapped):
        supported = True           # a section with one sub-heading, its own title ("Industry Overview"): written when any passage exists
    required = next((rx for sub_rx, rx in REQUIRES_EVENT if re.search(sub_rx, sub, re.I)), None)
    if required:                   # a sub-heading about a change is written only from a source that states one; "has not changed" is not inferred
        supported = bool(ctx.sentences(required, None, 1))
    return out, supported


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
        elif len(lines) >= 2 and all(ln.count(" | ") >= 1 for ln in lines):      # "Certification | Body | Valid till" without leading bars
            rows = [[c.strip() for c in ln.split("|")] for ln in lines]
            blocks.append({"type": "table", "rows": rows, "text": "", "facts": []})
        else:
            blocks.append({"type": "paragraph", "text": chunk, "facts": []})
    return _join_pipe_header([x for b in _rows_to_tables(_join_split_sentences(blocks)) for x in _flat_table(b)])


# A table the model wrote as one run of words: "FY 2023-24 FY 2024-25 FY 2025-26 H1 FY 2026-27 Tenders bid (number) 58 66 79 37 Value of
# bids (₹ lakhs) 41,600.00 52,300.00 ..." (22 Nov 2026, hosted test: five of these in Business). A header of two or more period labels
# followed by rows of "label, then as many values as there are periods" is read back into a table (two rows at least); the text after
# the last row stays a paragraph.
_PER = r"(?:H[12]\s+)?FY\s?\d{4}(?:-\d{2,4})?|(?:H[12]\s+)?FY\s?\d{2}\b|(?:31|30)\s+(?:March|September|June|December)\s+20\d{2}"
RE_FLAT_HEAD = re.compile(rf"^(?P<pre>(?:[^\d\[|]{{0,60}}?))\s*(?P<hdr>(?:(?:{_PER})\s+){{2,}})(?P<rest>.+)$", re.S)
_VAL = r"(?:-|\[●\]|\(?[\d,]+(?:\.\d+)?%?\)?)"


def _read_rows(text, k):
    """([label, v1..vk], ...) read from the start of text, and the position where they stop."""
    rx = re.compile(rf"\s*(?P<label>[A-Za-z(₹][^\n]*?[A-Za-z)%\]])\s+(?P<vals>{_VAL}(?:\s+{_VAL}){{{k - 1}}})(?=\s+[A-Za-z(₹•]|\s*$)")
    rows, pos = [], 0
    while pos < len(text):
        r = rx.match(text, pos)
        if not r:
            break
        rows.append([r["label"].strip()] + r["vals"].split())
        pos = r.end()
    return rows, pos


def _join_pipe_header(blocks):
    """A one-line header "₹ lakhs | FY 2023-24 | FY 2024-25" followed by a paragraph that starts with rows of the same width becomes
    one table; what follows the rows stays text."""
    out, i = [], 0
    while i < len(blocks):
        b = blocks[i]
        nxt = blocks[i + 1] if i + 1 < len(blocks) else None
        if b["type"] == "paragraph" and nxt and nxt["type"] == "paragraph" and "\n" not in b["text"] and b["text"].count(" | ") >= 2:
            cells = [c.strip() for c in b["text"].split("|")]
            rows, pos = _read_rows(" ".join(nxt["text"].split()), len(cells) - 1)
            if len(rows) >= 2:
                text = " ".join(nxt["text"].split())
                out.append({"type": "table", "rows": [cells] + rows, "text": "", "facts": []})
                if text[pos:].strip():
                    out += _flat_table({"type": "paragraph", "text": text[pos:].strip(), "facts": []})
                i += 2
                continue
        out.append(b)
        i += 1
    return out


def _flat_table(b):
    if b.get("type") != "paragraph":
        return [b]
    text = " ".join(b["text"].split())
    m = RE_FLAT_HEAD.match(text)
    if not m:
        return [b]
    labels = re.findall(_PER, m["hdr"])
    k = len(labels)
    if k < 2 or k > 8:
        return [b]
    rest = m["rest"].strip()
    rows, pos = _read_rows(rest, k)
    if len(rows) < 2:
        return [b]
    head = [m["pre"].strip() or ""] + [re.sub(r"\s+", " ", x) for x in labels]
    out = [{"type": "table", "rows": [head] + rows, "text": "", "facts": []}]
    if rest[pos:].strip():                       # what follows the rows (the next heading and its text) stays a paragraph
        out.append({"type": "paragraph", "text": rest[pos:].strip(), "facts": []})
    return out


VALUE = r"(?:-|\[●\]|[\d,]+(?:\.\d+)?)"
RE_TABLE_ROW = re.compile(rf"^(?P<label>.*?[A-Za-z\)\]].*?)\s+(?P<vals>{VALUE}(?:\s+{VALUE})*)\s*\*?$")


# "• Resumption of directorship from December 17, 2025" is a sentence ending in a date, not a row "label 17, 2025": the
# 19 Nov 2026 test drafts of "Management" were split into cells ("December | 17, | 2025") by this conversion.
RE_MONTH_END = re.compile(r"\b(?:January|February|March|April|May|June|July|August|September|October|November|December|"
                          r"Jan|Feb|Mar|Apr|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)\.?$", re.I)


def _rows_to_tables(blocks):
    """The model sometimes writes a table as plain lines: "Label 1,244.00 616.00 1,860.00", one line per row, with a
    blank line between the rows. A run of two or more such paragraphs with the same number of values becomes a table
    (label, then the values). The header line above the run stays as text: its column names are not guessed."""
    out, i = [], 0
    while i < len(blocks):
        j = i
        vals = None
        while j < len(blocks) and blocks[j]["type"] == "paragraph":
            m = RE_TABLE_ROW.match(blocks[j]["text"].strip())
            if not m or RE_MONTH_END.search(m["label"].strip()):
                break
            n = len(m["vals"].split())
            if n < 2 or (vals is not None and n != vals):      # one trailing number is a sentence, not a row
                break
            vals = n
            j += 1
        if j - i >= 2:
            rows = []
            for b in blocks[i:j]:
                m = RE_TABLE_ROW.match(b["text"].strip())
                rows.append([m["label"].strip()] + m["vals"].split())
            out.append({"type": "table", "rows": rows, "text": "", "facts": [], "converted": True})
            i = j
        else:
            out.append(blocks[i])
            i += 1
    return out


RE_OPEN_END = re.compile(r"(,|\bno\.|\bpages?|\bon|\bdated|\bof|\bto|\bfor|\band|\bwhich|\bwas|\bwere|\bis|\bare|\bby|\bin|\bat|\bwith|\bor|\bthe|\u20b9|\bRs\.?)$", re.I)


def _row_mismatch(row):
    """A deployment row [label, year 1, year 2, total] whose two years do not add up to the total ('-' is zero). Rows
    with a placeholder, or without three amounts, are not checked."""
    if len(row) != 4:
        return False
    vals = []
    for v in row[1:]:
        s = str(v).strip()
        if s == "-":
            vals.append(0.0)
        elif re.fullmatch(r"[\d,]+(?:\.\d+)?", s):
            vals.append(float(s.replace(",", "")))
        else:
            return False
    return abs(vals[0] + vals[1] - vals[2]) > 0.5


def _join_split_sentences(blocks):
    """A model draft sometimes puts a blank line inside a sentence ("dated October 31," / "2017 issued by ...", or
    "beginning on page no." / "99."). Read as two paragraphs, the verifier never sees the whole date or page number. A
    paragraph that ends open (a comma, "page no.", a connector) is joined to the next one when that one goes on in lower
    case or with a digit."""
    out = []
    for b in blocks:
        prev = out[-1] if out else None
        if (prev and prev["type"] == "paragraph" and b["type"] == "paragraph"
                and (prev["text"].count("(") > prev["text"].count(")") and not b["text"].lstrip().startswith(("\u2022", "-", "*"))
                     or RE_OPEN_END.search(prev["text"].rstrip()) and re.match(r"[0-9a-z(\u20b9]", b["text"])
                     or not re.search(r"[.!?:;)\u201d\"]$", prev["text"].rstrip()) and re.match(r"[a-z]", b["text"]))):
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


RE_SPLIT_DATE = re.compile(r"\b(January|February|March|April|May|June|July|August|September|October|November|December)\s*\|\s*"
                           r"(\d{1,2}(?:st|nd|rd|th)?,?)\s*\|\s*((?:19|20)\d{2})\b")


RE_SPACED_NUM = re.compile(r"(?<![\w,.])\d{1,3}(?:,\s+\d{2,3}){2,}(?![\w]|\s*,\s*\d)")


def close_spaced_numbers(text, facts):
    """A figure the model printed with spaces after its commas ("2, 85, 53, 700" for 2,85,53,700) is closed up, but only when its
    digits equal those of a fact: a list of section numbers is never rewritten."""
    known = {re.sub(r"\D", "", str(f.get("value", ""))) for f in facts}
    known.discard("")

    def fix(m):
        digits = re.sub(r"\D", "", m.group(0))
        return re.sub(r",\s+", ",", m.group(0)) if digits in known else m.group(0)
    return RE_SPACED_NUM.sub(fix, text)


def collapse_runs(text, keep=3):
    """Cut a draft where one short line repeats without end ("Rs." forty times, which trim_repeats ignores for being under 25
    characters). Returns (text, was_cut)."""
    out, last, run = [], None, 0
    for ln in text.split("\n"):
        key = re.sub(r"\d+", "#", ln.strip())
        if not key:
            out.append(ln)
            continue
        run = run + 1 if key == last else 1
        last = key
        if run > keep:
            return "\n".join(out).rstrip(), True
        out.append(ln)
    return text, False



TEMPLATE_PREFIX_WORDS, TEMPLATE_RUN, TEMPLATE_KEEP = 6, 5, 2


def cut_templated_run(text, source=""):
    """(text, was_cut): cut a draft where line after line opens with the same six words and goes on to say something else each time
    ("The industry is also responding to ... pressures by ...", 47 times: a 2,385-word Industry Overview, 23 Nov 2026), which
    trim_repeats cannot see because no two lines are equal. The first two lines of the run are kept. An opening that the inputs
    themselves use is left alone, so a list of agreements ("The Company has entered into an agreement with ...") is not cut."""
    source = re.sub(r"\s+", " ", source.lower())
    lines = text.split("\n")
    last, run, start = None, 0, 0
    for i, ln in enumerate(lines):
        if not ln.strip():
            continue                                   # blank lines between paragraphs do not end a run
        words = ln.split()
        key = None if ln.lstrip().startswith("|") or len(words) <= TEMPLATE_PREFIX_WORDS else " ".join(words[:TEMPLATE_PREFIX_WORDS]).lower()
        if key and key == last:
            run += 1
        else:
            last, run, start = key, (1 if key else 0), i
        if run >= TEMPLATE_RUN and key not in source:
            return _keep_lines(lines, start, TEMPLATE_KEEP), True
    return text, False


def _keep_lines(lines, start, keep):
    """The lines before index start, then the next keep non-empty lines (and the blank lines between them)."""
    kept, n = list(lines[:start]), 0
    for ln in lines[start:]:
        if ln.strip():
            if n == keep:
                break
            n += 1
        kept.append(ln)
    return "\n".join(kept).rstrip()


# A draft can also degenerate without repeating a sentence, which trim_repeats and collapse_runs look for (20 Nov 2026, hosted
# test: a list of risks ran on for some 300 words, with words split by spaces, "t o write-off s", "civil commotion s"). The text
# is cut before the first sentence that has three or more split words, or that runs past 120 words with ten or more semicolons.
RE_SPLIT_WORD = re.compile(r"(?<![\w'’])(?:t o|o f|i n|o n|a t|t he|th e|a nd|an d)(?![\w'’])|[A-Za-z-]{3,} s(?=[ ,;.:])")
RE_SENTENCE = re.compile(r"[^\n]*?(?:[.!?](?=\s|$)|\n|$)")
SPLIT_WORDS_CUT, RUNON_WORDS, RUNON_SEMICOLONS = 3, 120, 10


def cut_degenerate(text, source=""):
    """(text, was_cut): text cut before the first degenerate sentence (split words or an endless semicolon list). A split word
    that the inputs themselves hold (source: their text; a PDF can read "Technologie s") is not counted. Table lines are not read."""
    source = source.lower()
    for m in RE_SENTENCE.finditer(text):
        sent = m.group(0)
        if not sent.strip() or text[text.rfind("\n", 0, m.start()) + 1:].lstrip().startswith("|"):
            continue
        split = [w for w in RE_SPLIT_WORD.findall(sent) if w.lower() not in source]
        if (len(split) >= SPLIT_WORDS_CUT
                or len(sent.split()) > RUNON_WORDS and sent.count(";") >= RUNON_SEMICOLONS):
            return text[:m.start()].rstrip(), True
    return text, False


# Page footers the model learned from training documents ("13 | P a g e", "Page 4 of 120") are not prose. They are removed;
# the numbers in them would otherwise pass the figure check whenever the inputs hold the same number.
RE_PAGE_FOOTER = re.compile(r"[ \t]*(?:\b\d{1,4}\s*\|\s*P\s?a\s?g\s?e\b|\bP a g e(?:\s*\|?\s*\d{1,4})?\b|\bPage\s+\d{1,4}\s+of\s+\d{1,4}\b)[ \t]*")


def strip_page_footers(text):
    """(text, number removed)."""
    out, n = RE_PAGE_FOOTER.subn(" ", text)
    return (re.sub(r"(?<=\S) {2,}(?=\S)", " ", out) if n else text), n

# What the model copies from a source document besides prose (22 Nov 2026, hosted test on a data room: "3.2 Electricity demand" as
# a paragraph, "Chart 1: ..." with no chart, a "Source:" line of its own, report reference marks "[5]", a table flattened into
# one line of fifty numbers, a header row printed twice, a spreadsheet's "Check: ... | 0 | 0" row). None of it is prose.
RE_SECTION_NO = re.compile(r"^\d{1,2}(?:\.\d{1,2})+\.?\s+[A-Z][^.!?]{2,80}$")
RE_CAPTION = re.compile(r"^(?:Chart|Figure|Fig\.|Table|Exhibit)\s+\d+\s*[:.\-–]")
RE_SOURCE_LINE = re.compile(r"^Sources?\s*:", re.I)
RE_REF_MARK = re.compile(r"[ \t]?\[\d{1,2}(?:\s*[,–-]\s*\d{1,2})*\]")
# A letter's head copied from a certificate ("S R PANDE & CO. Chartered Accountants 501, ... Tel: ... Email: ... FRN: ... Peer Review Certificate No."),
# which the funds-deployed certificate gave to "Funds Deployed" in the Objects draft. Three markers of a letterhead make it one.
LETTERHEAD_MARKERS = ("tel:", "email:", "e-mail:", "frn:", "peer review certificate", "chartered accountants", "the board of directors", "sub:", "udin:")


def _is_letterhead(t):
    low = t.lower()
    return sum(m in low for m in LETTERHEAD_MARKERS) >= 3


TITLE_SMALL = {"a", "an", "at", "of", "the", "and", "in", "for", "to", "on", "by", "with", "or", "from", "as"}


def _is_title_fragment(t):
    """A heading copied as a paragraph ("Power Sector at a Glance ALL INDIA"): a few words, all capitalised or small words."""
    w = t.rstrip(". ").split()
    return 2 <= len(w) <= 9 and all(x[:1].isupper() or x.lower() in TITLE_SMALL or not x[:1].isalpha() for x in w) \
        and not re.search(r"[,;:]|\b(?:is|are|was|were|has|have|had)\b", t)


def _is_number_dump(t):
    nums = re.findall(r"\d[\d,.]*", t)
    return len(nums) >= 12 and len(nums) / max(1, len(t.split())) > 0.4


def _repeated_halves(t):
    w = [x.lower() for x in t.split()]
    n = len(w)
    return 4 <= n <= 40 and n % 2 == 0 and w[: n // 2] == w[n // 2:]


def clean_fragments(blocks):
    """Paragraphs of a model draft that are not prose are removed, and reference marks are stripped from the rest.
    Returns the kept blocks; a "Source:" line is kept only after a table (it names the table's source)."""
    from extract.rules import RE_HELPER_ROW
    out, seen, prev_dropped = [], set(), False
    for b in blocks:
        if b["type"] != "paragraph":
            out.append(b)
            prev_dropped = False
            continue
        t = RE_REF_MARK.sub("", b["text"]).strip()
        key = re.sub(r"[^a-z0-9]+", " ", t.lower()).strip()
        drop = (not t or _is_letterhead(t) or RE_SECTION_NO.match(t) or RE_HELPER_ROW.match(t) or _is_number_dump(t) or _repeated_halves(t)
                or (RE_CAPTION.match(t) and len(t.split()) <= 18)
                or (_is_title_fragment(t) and RE_REF_MARK.search(b["text"]))   # a source's title with its reference mark; a name list is not
                or (RE_SOURCE_LINE.match(t) and (prev_dropped or not out or out[-1]["type"] != "table"))
                or (len(key) > 60 and key in seen))
        prev_dropped = bool(drop)
        if drop:
            continue
        seen.add(key)
        out.append({**b, "text": t})
    return out


def dedupe_paragraphs(blocks):
    """A paragraph that repeats an earlier one of the section word for word (two sub-headings fed the same passage) is dropped."""
    seen, out = set(), []
    for b in blocks:
        if b.get("type") == "paragraph":
            key = re.sub(r"[^a-z0-9]+", " ", b.get("text", "").lower()).strip()
            if len(key) > 60 and key in seen:
                continue
            seen.add(key)
        out.append(b)
    return out


def guard_draft(text, s, facts, offer, company, corpus):
    """One sub-heading's raw model text, made safe to show: cut where it loops, parsed, and every value the inputs do not
    support masked as [●] (figures, dates, names, organisations, places; table cells also by row). Returns
    (blocks, masked, looped): masked is the number of values hidden, which best-of-n uses to pick a draft."""
    text = RE_SPLIT_DATE.sub(r"\1 \2 \3", text)          # "December | 17, | 2025" is a date the model put table bars in
    text = close_spaced_numbers(text, facts)
    text, _ = strip_page_footers(text)
    text, looped = trim_repeats(text)
    text, looped_short = collapse_runs(text)
    source = " ".join(f"{f.get('label', '')} {f.get('value', '')} {f.get('snippet', '')}" for f in facts)
    text, degenerate = cut_degenerate(text, source)
    text, templated = cut_templated_run(text, source)
    looped = looped or looped_short or degenerate or templated
    context = f"{company} {s}"
    blocks = clean_fragments([blk for blk in parse_markdown(text) if blk["type"] != "heading"])
    n = 0
    for blk in blocks:                            # the model may not state what the inputs do not support
        if blk["type"] == "paragraph":
            blk["text"], based = mask_misbased_percents(blk["text"], facts, context)
            blk["text"], timed = mask_period_claims(blk["text"], facts)
            blk["text"], future = mask_future_dates(blk["text"], facts)
            blk["text"], event = mask_event_dates(blk["text"], facts)
            blk["text"], malformed = mask_malformed_amounts(blk["text"], facts)
            blk["text"], units = mask_unit_claims(blk["text"], facts)
            timed = timed + future + event + malformed + units
            blk["text"], blk["masked"] = mask_ungrounded(blk["text"], facts, offer, context)
            blk["masked"] = based + timed + blk["masked"]
            blk["text"], ents = mask_unknown_entities(blk["text"], corpus, context)
            blk["text"], places = mask_unknown_places(blk["text"], corpus, context)
            blk["masked"] += ents + places
        elif blk["type"] == "table":              # table cells are prose too: a date or figure in a header is checked
            rows, hits = [], []
            for r in blk.get("rows", []):
                if blk.get("converted") and _row_mismatch(r):
                    # the model's own deployment row does not add up: its figures are not stated until a reviewer checks
                    hits.append({"kind": "reconciliation", "raw": " | ".join(str(c) for c in r), "context": context})
                    r = [r[0]] + [PH] * (len(r) - 1)
                line, m = mask_ungrounded(" | ".join(str(c) for c in r), facts, offer, context)    # one line: dates split across cells
                parts = line.split(" | ")
                if len(parts) == len(r):
                    cells, hits = parts, hits + m
                else:                                 # a mask removed a separator: fall back to cell by cell
                    cells = []
                    for c in r:
                        if isinstance(c, str) and c:
                            c, m = mask_ungrounded(c, facts, offer, context)
                            hits += m
                        cells.append(c)
                for i in misplaced_cells(cells, facts):       # a real figure on another row's line
                    hits.append({"kind": "misplaced", "raw": cells[i], "context": str(cells[0])})
                    cells[i] = PH
                rows.append(cells)
            blk["rows"], blk["masked"] = rows, hits
        n += len(blk.get("masked", []))
    return blocks, n, looped, text


def _facts_used(blocks, facts):
    """How many of the supplied facts' values a guarded draft states: the tie-break of best-of-n, so that among drafts with the
    same number of masked values the one that uses more of the issuer's facts wins."""
    parts = []
    for b in blocks:
        parts.append(" ".join(str(c) for r in b.get("rows", []) for c in r) if b["type"] == "table" else b.get("text", ""))
    low = " ".join(parts).lower()
    vals = {str(f.get("value", "")).lower() for f in facts if len(str(f.get("value", ""))) >= 3 and str(f.get("value")) != PH}
    return sum(v in low for v in vals)


MIN_LENGTH_SHARE = 0.6     # a candidate shorter than this share of the median candidate is not considered


def choose_draft(scored):
    """Index of the draft to show from [(key, length), ...]: the lowest key, among the drafts that are not much shorter than
    the median one. Without a length floor the rule (fewest masked values first) rewards a draft that says less: for the
    shipped adapter 36 of 89 chosen drafts were under half the length of the longest candidate (20 Nov 2026). The floor is
    set from the median, not the longest, so one runaway draft does not push it up."""
    lengths = sorted(n for _, n in scored)
    floor = MIN_LENGTH_SHARE * (lengths[len(lengths) // 2] if lengths else 0)
    ok = [i for i, (_, n) in enumerate(scored) if n >= floor] or list(range(len(scored)))
    return min(ok, key=lambda i: scored[i][0])


def _generate(llm, msgs, best_of):
    """[text, ...] from the model: best_of drafts in one request when the client supports it, else one."""
    if best_of > 1 and getattr(llm, "supports_n", False):
        try:
            texts, u = llm(msgs, frequency_penalty=DRAFT_FREQUENCY_PENALTY, n=best_of, temperature=BEST_OF_TEMPERATURE)
            return [t for t in texts if t] or [""], u
        except RuntimeError:                      # serve.llm.ModelError: a server that refuses n still gets one draft
            pass
    text, u = llm(msgs, frequency_penalty=DRAFT_FREQUENCY_PENALTY)
    return [text], u


def compose(key, ctx: Ctx, llm=None, best_of=DRAFT_BEST_OF):
    sec = SECTION_BY_KEY[key]
    if key == "business":
        own = [h for h, _ in business_subheads(ctx)]
        if own:
            sec = {**sec, "subheads": own}
    facts = ctx.facts
    doc_types = {f["id"]: f.get("doc_type") for f in ctx.files}
    b = build(key, ctx) or Build()
    built = {s for s, _ in b.parts if s}
    narrative = list(b.narrative)
    if key == "business" and sec["subheads"] != SECTION_BY_KEY[key]["subheads"]:
        narrative = [s for s in narrative if s in sec["subheads"]]     # the static manufacturer headings do not apply
    if sec["writer"].startswith("slm"):
        narrative += [s for s in (sec["subheads"] or [sec["title"]]) if s not in built and s not in narrative]
    engine, usage, prose, looped, trimmed = "code", {}, {}, [], []
    absent = set()                                  # sub-headings the issuer's files say nothing about
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
            passages, supported = passage_facts(ctx, s, sec)
            if not supported:                       # the files say nothing about this sub-heading: do not let the model invent it
                prev = ""
                absent.add(s)
                continue
            extras = unknown_facts(s, sec["title"], passages + routed) + derive_facts(routed, s, sec["title"])
            msgs, cut = fit_messages(lambda ps, rs: drafting_messages(ctx.company(), sec["title"], outline, s, extras + ps + rs,
                                                                      summary_of(prev) if prev else ""), passages, routed)
            if cut:
                trimmed.append(s)                   # the input was longer than the window: lowest-ranked items were left out
            cands, u = _generate(llm, msgs, best_of)
            for k, v in (u or {}).items():
                usage[k] = usage.get(k, 0) + (v if isinstance(v, (int, float)) else 0)
            # every value the model was shown is grounded: the typed facts, the passages and the computed or unknown facts
            grounding = facts + passages + extras
            scored = []
            for t in cands:
                blocks_t, n_masked, looped_t, text_t = guard_draft(t, s, grounding, ctx.offer, ctx.company(), ctx.corpus())
                # a draft that did not loop first, then fewest masked values, then most of the issuer's facts used
                # (19 Nov 2026, 89 live drafts: loops 5.6% to 0%, invented figures 6.7% to 4.5%, fact use 0.595 to 0.618)
                scored.append(((looped_t, n_masked, -_facts_used(blocks_t, routed)), blocks_t, looped_t, text_t))
            _, chosen, was_cut, text = scored[choose_draft([(k, len(t_)) for k, _, _, t_ in scored])]
            if was_cut:
                looped.append(s)                    # a greedy draft can loop on one sentence; guard_draft cut it (data/prompts.py)
            if len(cands) > 1:
                usage["drafts_sampled"] = usage.get("drafts_sampled", 0) + len(cands)
            prose[s] = chosen
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
            elif s in absent:                   # only facts that name the sub-heading's own terms are listed: unrelated ones
                from rag.index import tokens    # (rent lines under "Changes in Registered Office") mislead
                bf = brief(facts, s, sec, doc_types)
                terms = {_stem(t) for t in tokens(s) if len(t) >= 4 and t.isalpha() and t not in GENERIC_TERMS}
                keep = [it for it in bf["items"] if terms & {_stem(t) for t in tokens(f"{it['label']} {it['period']}")}]
                if keep:
                    bf["items"], bf["facts"] = keep, [it["fact_id"] for it in keep]
                    blocks.append(bf)
                else:
                    blocks.append({"type": "brief", "missing": True, "sub": s, "facts": [], "items": [],
                                   "text": f"{PH} The issuer's files do not state this. To be provided by the issuer."})
                pending.append(s)
            else:
                blocks.append(brief(facts, s, sec, doc_types))
                pending.append(s)
        blocks += next((bl for x, bl in b.parts if x == s), [])
    blocks = dedupe_paragraphs(blocks)
    attach_citations(blocks, facts)
    if not blocks:
        blocks = [{"type": "note", "text": f"{PH} No input was found for this section.", "facts": []}]
    return blocks, engine if narrative else "code", usage, b, pending, looped, trimmed


def write_section(key, ctx: Ctx, llm=None):
    """Draft one section. llm: callable(messages, frequency_penalty=...) -> (text, usage), or None (drafting briefs
    instead of prose). Sub-headings whose model draft looped are listed in "loop_trimmed"."""
    sec = SECTION_BY_KEY[key]
    facts = ctx.facts
    doc_types = {f["id"]: f.get("doc_type") for f in ctx.files}
    t0 = time.perf_counter()
    covered, missing, pending, usage, looped, trimmed = [], [], [], {}, [], []
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
        blocks, engine, usage, b, pending, looped, trimmed = compose(key, ctx, llm)
        covered, missing = b.covered, b.missing
    routed = route(facts, f"{sec['title']} {sec['query']}", sec["needs"], doc_types=doc_types) if sec["query"] else []
    return {"blocks": blocks, "writer": sec["writer"], "engine": engine, "routed": [f["id"] for f in routed],
            "covered": covered, "missing": [{"item": m[0], "where": m[1]} for m in missing], "narrative_pending": pending,
            "loop_trimmed": looped, "context_trimmed": trimmed, "latency_s": round(time.perf_counter() - t0, 3), "usage": usage}


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
    """load_blocks(file_id) -> stored reader output or None. A "fact" that is an instruction addressed to the
    assistant (prompt injection in an issuer's file) is left out, so neither drafting nor the assistant uses it."""
    from rag.guardrails import RE_INJECTION
    facts = [f for f in facts if not RE_INJECTION.search(f"{f.get('label', '')}: {f.get('value', '')}")]
    from verify.checks import platform_issue
    if platform_issue(project, facts):          # the files name the other listing platform: not stated until the Offer details settle it
        project = {**project, "offer": {**(project.get("offer") or {}), "board": ""}}
    blocks, tables = {}, []
    for f in files:
        if f.get("status") != "processed":
            continue
        got = load_blocks(f["id"]) or {}
        blocks[f["id"]] = got.get("blocks", [])
        tables += tables_from_blocks(blocks[f["id"]], f)
    return Ctx(project=project, facts=facts, files=files, tables=tables, blocks=blocks)
