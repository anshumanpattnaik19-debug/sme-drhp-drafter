"""Agentic RAG over one project: plan → retrieve with tools → reflect (broaden if thin) → answer → verify.

    Agent(ctx, index, review, drafts).run(question, history, settings) -> iterator of events
        {"type": "step", "id", "label", "detail", "status": "running" | "done" | "warn"}
        {"type": "meta", "engine", "sources": [evidence], "retrieval": "BM25" | "BM25 + dense (RRF)"}
        {"type": "delta", "text"}
        {"type": "done"}

Tools: search_documents (passages and schedules), find_table (schedules only), search_facts (typed fact store),
read_section (current draft), review_issues (review pack), list_risk_factors. With a model connected, the model
chooses the tools (JSON, at most MAX_TOOL_CALLS) after a first retrieval round; without one, a rule-based
planner does. Every answer is checked: each figure in it must appear in the cited evidence.
"""
from __future__ import annotations

import json
import re
import time

from draft.outline import SECTION_BY_KEY, SECTIONS
from draft.router import route
from draft.writer import fact_text
from serve import llm
from .index import best_sentence, tokens

MAX_TOOL_CALLS = 4
MAX_EVIDENCE = 18
THIN_SCORE = 2.5

SYNONYMS = {
    "noc": "no-objection certificate", "rpt": "related party transactions", "brlm": "book running lead manager",
    "kmp": "key managerial personnel", "cin": "corporate identification number", "pat": "profit after tax",
    "revenue": "revenue from operations", "debt": "borrowings loans", "capex": "capital expenditure plant machinery",
    "md": "managing director", "ipo": "issue offer", "lm": "lead manager", "cs": "company secretary",
    "litigation": "proceedings cases suit", "licence": "licence approval registration", "objects": "objects of the issue deployment",
    "customers": "customers top revenue concentration", "promoter": "promoter promoter group shareholding",
}

ALIASES = {
    "risk_factors": ["risk factor", "risk factors", "red flag"],
    "objects": ["objects", "use of proceeds", "fund requirement", "deployment"],
    "capital_structure": ["capital structure", "shareholding pattern", "build-up", "build up", "allotment"],
    "business": ["our business", "business"],
    "promoters": ["promoters", "promoter group"],
    "management": ["management", "board of directors", "kmp", "key managerial"],
    "litigation": ["litigation", "legal proceedings", "court case"],
    "approvals": ["approvals", "licences", "licenses"],
    "summary_financials": ["summary financial", "financial summary"],
    "mdna": ["md&a", "mdna", "management discussion", "results of operations"],
    "indebtedness": ["indebtedness", "borrowings"],
    "the_offer": ["the offer", "issue size", "offer size"],
    "general_info": ["general information", "intermediaries"],
    "industry": ["industry overview"],
    "history": ["history", "corporate matters", "milestones"],
    "capitalisation": ["capitalisation", "capitalization"],
    "basis_price": ["basis for offer price", "kpi", "key performance"],
    "summary": ["summary of the offer document"],
}

ANSWER_SYSTEM = (
    "You are DRHP Assistant, helping a merchant banker prepare an SME Draft Red Herring Prospectus for {company}. "
    "Answer only from the EVIDENCE (numbered items from the issuer's files, the current draft and the review pack). "
    "Cite every figure and claim inline as [n]. If the evidence does not answer the question, say so plainly and name the "
    "document the issuer should provide. Never invent figures, names or dates. Offer price, price band and offer dates are "
    "[●] at DRHP stage. No legal or investment advice; flag regulatory points as 'to be confirmed by the BRLM'. "
    "Be concise: short paragraphs or bullet lists, bold for key figures.")

TOOL_SYSTEM = (
    "You research questions about an SME DRHP project by calling tools. Reply with exactly one JSON object and nothing else.\n"
    'Tools: {{"tool": "search_documents", "query": "..."}} passages and schedules in the issuer\'s files; '
    '{{"tool": "find_table", "query": "..."}} schedules only; {{"tool": "search_facts", "query": "..."}} typed facts; '
    '{{"tool": "read_section", "section": "<key>"}} the current draft of a section; {{"tool": "review_issues"}} open review issues; '
    '{{"answer": "ready"}} when the evidence is enough.\nSection keys: {keys}.')


def match_section(q):
    ql = q.lower()
    titles = [s for s in SECTIONS if s["title"].lower() in ql]
    if titles:                       # "objects of the offer" also contains "the offer": take the longest title
        return max(titles, key=lambda s: len(s["title"]))["key"]
    best = None
    for key, words in ALIASES.items():
        for w in words:
            if re.search(rf"\b{re.escape(w)}\b", ql) and (best is None or len(w) > best[1]):
                best = (key, len(w))
    return best[0] if best else None


def decompose(q):
    parts = [p.strip(" ,.?") for p in re.split(r"\?|;|\band also\b|\band (?=(?:what|how|who|when|where|which)\b)", q, flags=re.I)]
    parts = [p for p in parts if tokens(p)]
    return parts[:3] or [q]


def expand(q, key=None):
    extra = [v for k, v in SYNONYMS.items() if re.search(rf"\b{re.escape(k)}\b", q.lower())]
    if key:
        extra.append(SECTION_BY_KEY[key]["query"])
    return " ".join([q] + extra)


class Agent:
    def __init__(self, ctx, index, review, drafts):
        self.ctx, self.index, self.review, self.drafts = ctx, index, review, drafts
        self.evidence: list[dict] = []
        self._seen = set()
        self.top_score = 0.0
        self._q = None

    # ---------- evidence ----------

    def _add(self, item, key):
        if key in self._seen or len(self.evidence) >= MAX_EVIDENCE:
            return None
        self._seen.add(key)
        item["n"] = len(self.evidence) + 1
        self.evidence.append(item)
        return item

    # ---------- tools ----------

    def search_documents(self, query, kinds=("passage", "table"), k=5):
        hits = self.index.search(query, k=k, kinds=kinds)
        out = []
        for h in hits:
            c = h.chunk
            self.top_score = max(self.top_score, h.score)
            it = self._add({"kind": c.kind, "file_id": c.file_id, "file_name": c.file_name, "loc": c.loc,
                            "label": c.title or c.file_name, "text": c.text[:900], "quote": best_sentence(c.text, query),
                            "score": round(h.score, 2), "q": self._q}, ("chunk", c.id))
            if it:
                out.append(it)
        return out

    def find_table(self, query):
        return self.search_documents(query, kinds=("table",), k=4)

    def search_facts(self, query, k=6):
        facts = [f for f in route(self.ctx.facts, query, k=k * 2, doc_types={f["id"]: f.get("doc_type") for f in self.ctx.files})
                 if not f.get("superseded")][:k]
        out = []
        for f in facts:
            it = self._add({"kind": "fact", "fact_id": f["id"], "file_id": f.get("file_id"), "file_name": f.get("file_name", ""),
                            "loc": f.get("loc", ""), "label": f["label"], "period": f.get("period", ""), "value": fact_text(f),
                            "text": f.get("snippet", ""), "q": self._q}, ("fact", f["id"]))
            if it:
                out.append(it)
        return out

    def read_section(self, section):
        d = self.drafts.get(section)
        if section not in SECTION_BY_KEY:
            return []
        title = SECTION_BY_KEY[section]["title"]
        text = _section_text(d) if d else "Not drafted yet."
        it = self._add({"kind": "section", "section": section, "file_name": f"Draft: {title}", "loc": "current draft",
                        "label": title, "text": text, "draft": d}, ("section", section))
        return [it] if it else []

    def review_issues(self):
        it = self._add({"kind": "review", "file_name": "Review pack", "loc": "open issues", "label": "Review pack",
                        "text": "\n".join(f"[{i['severity']}] {i['title']} — {i['detail']}" for i in self.review["issues"][:40]),
                        "issues": self.review["issues"], "summary": self.review["summary"]}, ("review",))
        return [it] if it else []

    def call(self, name, args):
        self._q = args.get("query")          # evidence remembers the sub-question that found it
        if name == "search_documents":
            return self.search_documents(args.get("query", ""))
        if name == "find_table":
            return self.find_table(args.get("query", ""))
        if name == "search_facts":
            return self.search_facts(args.get("query", ""))
        if name == "read_section":
            return self.read_section(args.get("section", ""))
        if name == "review_issues":
            return self.review_issues()
        return []

    # ---------- planning ----------

    def plan(self, q):
        ql = q.lower()
        key = match_section(q)
        if re.search(r"missing|pending|outstanding items|request from|requisition|what (do|does) (we|i|the issuer) need|open items", ql):
            return "missing", key, [("review_issues", {})]
        if re.search(r"\b(status|progress|how far|readiness)\b", ql) and not key:
            return "status", key, [("review_issues", {})]
        if key == "risk_factors" or (re.search(r"\brisk", ql) and not key):
            return "risks", key, [("read_section", {"section": "risk_factors"}), ("search_documents", {"query": q})]
        if key and re.search(r"summar|show|what('s| is) in|explain|tell me about|overview|walk me|describe", ql):
            return "section", key, [("read_section", {"section": key})]
        steps = []
        for sq in decompose(q):
            steps += [("search_facts", {"query": sq}), ("search_documents", {"query": sq})]
        if key:
            steps.append(("read_section", {"section": key}))
        return "lookup", key, steps

    # ---------- run ----------

    def run(self, question, history, settings):
        sid = 0

        def step(label, detail="", status="done"):
            nonlocal sid
            sid += 1
            return {"type": "step", "id": sid, "label": label, "detail": detail, "status": status}

        mode, key, steps = self.plan(question)
        yield step("Planning", {"missing": "Checking the review pack for open items", "status": "Reading the review pack",
                                "risks": "Reading the risk factors and the issuer's files",
                                "section": f"Reading the draft of {SECTION_BY_KEY[key]['title'] if key else ''}",
                                "lookup": f"{len(decompose(question))} sub-question(s); searching facts, passages and schedules"}[mode])
        for name, args in steps:
            got = self.call(name, args)
            yield step(_label(name, args), _found(got))
        if mode == "lookup" and (len(self.evidence) < 2 or self.top_score < THIN_SCORE):
            q2 = expand(question, key)
            got = self.search_documents(q2, k=6) + self.search_facts(q2)
            yield step("Broadening the search", f"Expanded the query with synonyms and section terms · {_found(got)}",
                       "done" if got else "warn")

        model = settings.get("use_model")
        if model and mode == "lookup":
            try:
                for ev in self._model_tools(question, settings, step):
                    yield ev
            except llm.ModelError as e:
                yield step("Model tool use failed", str(e)[:120], "warn")
                model = False

        yield {"type": "meta", "engine": "model" if model else "offline", "model": settings.get("model_name") if model else None,
               "retrieval": self.index.method, "sources": [_public(e) for e in self.evidence if e["kind"] not in ("review",)]}
        text = ""
        if model:
            try:
                for d in llm.stream_chat(settings, self._answer_messages(question, history)):
                    text += d
                    yield {"type": "delta", "text": d}
            except llm.ModelError as e:
                note = f"_The model did not respond ({str(e)[:100]}). Answering offline instead._\n\n"
                yield {"type": "delta", "text": note}
                model = False
        if not model:
            text = self.compose(mode, key, question)
            for c in _chunks(text):
                yield {"type": "delta", "text": c}
                time.sleep(0.01)
        ok, total = self.verify(text)
        yield step("Checking the answer", (f"{ok} of {total} figure(s) traced to the cited evidence" if total else "No figures to check"),
                   "done" if ok == total else "warn")
        yield {"type": "done"}

    def _model_tools(self, question, settings, step):
        chat = llm.make_chat({**settings, "max_tokens": 160, "temperature": 0})
        keys = ", ".join(s["key"] for s in SECTIONS)
        msgs = [{"role": "system", "content": TOOL_SYSTEM.format(keys=keys)},
                {"role": "user", "content": f"QUESTION: {question}\n\nEVIDENCE SO FAR:\n{self._evidence_text(10)}"}]
        for _ in range(MAX_TOOL_CALLS):
            out, _usage = chat(msgs)
            m = re.search(r"\{.*\}", out, re.S)
            try:
                call = json.loads(m.group(0)) if m else {}
            except ValueError:
                call = {}
            if not call.get("tool"):
                yield step("Enough evidence", "The model is ready to answer")
                return
            got = self.call(call["tool"], call)
            yield step(_label(call["tool"], call), _found(got))
            msgs += [{"role": "assistant", "content": out},
                     {"role": "user", "content": "OBSERVATION:\n" + ("\n".join(_line(e) for e in got) or "(nothing found)")}]

    def _evidence_text(self, limit=MAX_EVIDENCE):
        return "\n".join(_line(e) for e in self.evidence[:limit]) or "(none)"

    def _answer_messages(self, question, history):
        msgs = [{"role": "system", "content": ANSWER_SYSTEM.format(company=self.ctx.company())}]
        for m in history[-6:]:
            msgs.append({"role": m["role"], "content": m["content"][:1500]})
        msgs.append({"role": "user", "content": f"EVIDENCE:\n{self._evidence_text()}\n\nQUESTION: {question}"})
        return msgs

    # ---------- offline answers ----------

    def compose(self, mode, key, question):
        co = self.ctx.company()
        rv = next((e for e in self.evidence if e["kind"] == "review"), None)
        if mode in ("missing", "status") and rv:
            s = rv["summary"]
            if mode == "status":
                return "\n".join([f"**{co}** — where the draft stands",
                                  f"- Files read: {sum(f['status'] == 'processed' for f in self.ctx.files)} of {len(self.ctx.files)}",
                                  f"- Sections drafted: {s['sections_drafted']} of {s['sections_total']}; signed off: {s.get('sections_signed_off', 0)}",
                                  f"- Sub-headings still needing prose: {s.get('narrative_pending', 0)}",
                                  f"- Open issues: {s['high']} high, {s['medium']} medium · placeholders [●]: {s['placeholders']}"])
            issues = rv["issues"]
            miss = [i for i in issues if i["kind"] == "missing_input"]
            ocr = [i for i in issues if i["kind"] == "ocr"]
            prose = [i for i in issues if i["kind"] == "narrative"]
            lines = []
            if miss:
                lines += [f"**To request from the issuer ({len(miss)})**"] + [f"- {i['title']} — {i['detail']}" for i in miss[:12]]
            if ocr:
                lines += ["", f"**Scanned pages not yet read ({len(ocr)})**"] + [f"- {i['title']}" for i in ocr[:6]]
            if prose:
                lines += ["", f"**Prose still to be written ({len(prose)} sections)**"] + [f"- {i['title']}" for i in prose[:10]]
            if not lines:
                lines = ["Nothing is flagged as missing in the review pack right now."]
            lines += ["", f"In all, {s['high']} high and {s['medium']} medium issues are open [{rv['n']}]. The full list is under **Review**."]
            return "\n".join(lines)
        if mode == "risks":
            sec = next((e for e in self.evidence if e["kind"] == "section"), None)
            d = sec and sec.get("draft")
            if not d:
                return "Risk Factors has not been drafted yet. Say *draft risk factors* and I'll do it."
            lines = [f"The draft has these risk factors [{sec['n']}], each built from a red flag in the issuer's files:"]
            for b in d["blocks"]:
                m = re.match(r"(\d+)\.\s+\*\*(.+?)\*\*", b.get("text", ""))
                if not m:
                    continue
                tag = ""
                if b.get("sources"):
                    s0 = b["sources"][0]
                    it = self._add({"kind": "passage", "file_id": s0.get("file_id"), "file_name": s0.get("file_name", ""), "loc": s0.get("loc", ""),
                                    "label": m.group(2)[:80], "text": s0.get("snippet", ""), "quote": (s0.get("snippet") or "")[:200]},
                                   ("rf", m.group(1)))
                    tag = f" [{it['n']}]" if it else ""
                lines.append(f"{m.group(1)}. {m.group(2)}{tag}{'  _(standard risk)_' if b.get('template') else ''}")
            return "\n".join(lines)
        if mode == "section":
            sec = next((e for e in self.evidence if e["kind"] == "section"), None)
            title = SECTION_BY_KEY[key]["title"]
            d = sec and sec.get("draft")
            if not d:
                return f"**{title}** has not been drafted yet. Say *draft {title.lower()}* and I'll start it."
            v = d.get("verification") or {}
            signed = (d.get("review") or {}).get("status") == "reviewed"
            return (f"**{title}** [{sec['n']}] — {'signed off' if signed else 'not yet signed off'}; "
                    f"{v.get('narrative_pending', 0)} sub-heading(s) need prose; {v.get('placeholders', 0)} placeholder(s).\n\n" + _section_outline(d))
        # lookup: per sub-question, the best-fitting facts, then the best passage or schedule row, each cited
        subqs = decompose(question)
        lines = ["Here is what the issuer's files say:"]
        found = False
        for sq in subqs:
            ev = [e for e in self.evidence if e.get("q") in (sq, None) or len(subqs) == 1]
            facts = [e for e in ev if e["kind"] == "fact"]
            docs = [e for e in ev if e["kind"] in ("passage", "table")]
            qterms = set(tokens(sq))
            years = set(re.findall(r"\d{2}(?=\D|$)", " ".join(re.findall(r"(?:fy|20)\s?\d{2}(?:-\d{2})?|h1", sq.lower()))))

            def fit(e, qterms=qterms, years=years):
                # label overlap with the question, plus a bonus when the period matches the year asked about
                lab = set(tokens(e["label"])) | set(tokens(e.get("period", "")))
                per_hit = bool(years) and bool(years & set(re.findall(r"\d{2}(?=\D|$)", e.get("period", ""))))
                return len(qterms & lab) + (2 if per_hit else 0) - (0.5 if len(e["label"].split()) > 8 else 0)
            facts = sorted(facts, key=lambda e: -fit(e))
            seen = set()
            facts = [e for e in facts if (e["label"].lower(), e["value"]) not in seen and not seen.add((e["label"].lower(), e["value"]))]
            if facts:
                top = fit(facts[0])
                facts = [e for e in facts if fit(e) >= max(1, top - 1)]
            quoted = [e for e in docs if qterms & set(tokens(e["quote"]))][:2 if len(subqs) > 1 else 3]
            if not (facts or quoted):
                continue
            found = True
            if len(subqs) > 1:
                lines += ["", f"**{sq[0].upper() + sq[1:]}?**"]
            for e in facts[:4 if len(subqs) > 1 else 5]:
                lines.append(f"- {e['label']}{' (' + e['period'] + ')' if e.get('period') else ''}: **{e['value']}** [{e['n']}]")
            for e in quoted:
                lines.append(f"> {e['quote']} [{e['n']}]")
        if not found:
            return ("I couldn't find that in the issuer's files. If it should be there, check that the document is uploaded and "
                    "classified under **Documents**, or ask the issuer for it.")
        lines.append("")
        lines.append(f"_Offline mode: found by {self.index.method} retrieval over the issuer's files. Connect the fine-tuned model "
                     "in Settings for written answers._")
        return "\n".join(lines)

    # ---------- verification ----------

    def verify(self, text):
        body = re.sub(r"\[\d+\]", "", text)
        figs = [f for f in re.findall(r"(?<![\w/.])\d[\d,]*\.\d+|(?<![\w/.])\d{1,3}(?:,\d{2,3})+(?![\d])", body)]
        if not figs:
            return 0, 0
        ev = " ".join(f"{e.get('text', '')} {e.get('value', '')} {e.get('quote', '')}" for e in self.evidence)
        evn = {_num(x) for x in re.findall(r"\d[\d,]*(?:\.\d+)?", ev)}
        ok = sum(1 for f in figs if _num(f) in evn)
        return ok, len(figs)


# ---------- helpers ----------

def _num(s):
    try:
        return round(float(s.replace(",", "")), 2)
    except ValueError:
        return None


def _label(name, args):
    q = args.get("query") or args.get("section") or ""
    return {"search_documents": f"Searching documents: “{q[:60]}”", "find_table": f"Looking up schedules: “{q[:60]}”",
            "search_facts": f"Searching the fact store: “{q[:60]}”",
            "read_section": f"Reading the draft: {SECTION_BY_KEY.get(q, {}).get('title', q)}",
            "review_issues": "Reading the review pack"}.get(name, name)


def _found(got):
    if not got:
        return "Nothing new found"
    files = {e.get("file_name") for e in got}
    return f"{len(got)} item(s) from {len(files)} source(s): " + ", ".join(list(files)[:3])


def _line(e):
    if e["kind"] == "fact":
        return f"[{e['n']}] FACT {e['label']}{' (' + e['period'] + ')' if e.get('period') else ''}: {e['value']} — {e['file_name']}, {e['loc']}"
    return f"[{e['n']}] {e['kind'].upper()} {e['file_name']}, {e['loc']}: {e.get('text', '')[:600]}"


def _public(e):
    return {k: v for k, v in e.items() if k not in ("draft", "issues", "summary")} | {"text": e.get("text", "")[:400]}


def _chunks(text, size=4):
    words = re.split(r"(\s+)", text)
    for i in range(0, len(words), size * 2):
        yield "".join(words[i:i + size * 2])


def _section_text(d, limit=3500):
    out = []
    for b in d.get("blocks", []):
        if b["type"] == "table":
            rows = b.get("rows") or []
            out.append((b.get("caption") or "Table") + ":\n" + "\n".join(" | ".join(r) for r in rows[:12]))
        elif b["type"] in ("paragraph", "heading", "note"):
            out.append(b.get("text", ""))
    return "\n".join(out)[:limit]


def _section_outline(d, limit=14):
    lines = []
    for b in d.get("blocks", []):
        if b["type"] == "heading":
            lines.append(f"**{b['text']}**")
        elif b["type"] == "table":
            lines.append(f"- Table: {b.get('caption') or (b.get('rows') or [['']])[0][0]} ({max(0, len(b.get('rows') or []) - 1)} rows)")
        elif b["type"] == "brief":
            lines.append("- _Prose pending (drafting brief)_")
        elif b["type"] == "paragraph" and b.get("text"):
            first = re.split(r"(?<=[.])\s", b["text"].replace("**", ""), maxsplit=1)[0]
            lines.append(f"- {first[:220]}")
        if len(lines) >= limit:
            lines.append("- …")
            break
    return "\n".join(lines)
