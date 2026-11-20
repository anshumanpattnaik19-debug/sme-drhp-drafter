"""Accuracy: every figure, date and regulation number in an output is checked against the source documents; sentences are
labelled verified, assumption, missing or unsupported; an answer without enough support is masked or withheld.

    hc = HallucinationChecker(config["hallucination"])
    rep = hc.check(answer, sources=["[1] PASSAGE ...", "[2] TABLE ..."])
    rep.sentences            -> [{"text", "status", "claims", "unsupported", "sources"}]   status: verified | assumption |
                                                                                          missing | unsupported | no_claims
    rep.support              -> "supported" | "partly supported" | "unsupported" | "no checkable claims"
    hc.enforce(answer, sources) -> (text to show, report, action)          action: allow | mask | abstain | flag

What "verified" means here: every figure, date and regulation number in the sentence also appears in at least one source. It
does not mean the sentence is true (a source can be wrong, a sentence can combine true numbers into a false claim) and it is not
a probability. The checker uses the same figure and date rules as the evaluation (data/facts.py) and, for masking, the app's
verifier (verify/checks.py), so what is reported matches what is measured.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from data.facts import figures, parse_dates
from verify.checks import mask_ungrounded

PH = "[●]"
RE_SPLIT = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9\[(*•-])|\n+")      # sentence ends, never the point of "1,234.56"
# regulation and statute references: the number is a claim ("Regulation 229(2)", "Section 186 of the Companies Act")
RE_REG = re.compile(r"\b(?:Regulation|Reg\.|Section|Sec\.|Rule|Schedule|Clause|Article)s?\s+(\d+[A-Z]?(?:\s*\(\s*\w+\s*\))*)", re.I)
RE_CITE = re.compile(r"\[(\d{1,2})\]")
ABSTAIN = ("The documents provided do not support a reliable answer to this. Unsupported points: {items}. Please check the "
           "issuer's documents or ask the issuer for the missing information.")


def _norm_reg(s):
    return re.sub(r"\s+", "", s).lower()


@dataclass
class Report:
    sentences: list = field(default_factory=list)
    claims: int = 0
    grounded: int = 0
    unsupported: list = field(default_factory=list)
    missing: int = 0
    assumptions: int = 0

    @property
    def support_ratio(self):
        return self.grounded / self.claims if self.claims else None

    @property
    def support(self):
        """A plain label, never a probability."""
        if not self.claims:
            return "no checkable claims"
        if not self.unsupported:
            return "supported"
        return "unsupported" if self.grounded == 0 else "partly supported"

    def summary(self):
        r = self.support_ratio
        return {"support": self.support, "claims": self.claims, "grounded": self.grounded,
                "support_ratio": round(r, 3) if r is not None else None, "unsupported": self.unsupported[:20],
                "missing_placeholders": self.missing, "assumption_sentences": self.assumptions,
                "note": "checked claims are figures, dates and regulation numbers found in the sources; not a probability"}


class HallucinationChecker:
    def __init__(self, config=None):
        c = config or {}
        self.action = c.get("action", "mask")
        self.min_ratio = float(c.get("min_support_ratio", 0.8))
        self.max_unsupported = int(c.get("max_unsupported_claims", 0))
        self.hedges = [h.lower() for h in c.get("hedge_terms", ["assume", "estimated", "expected", "approximately", "proposed",
                                                               "subject to", "to be confirmed", "likely", "may"])]
        self.re_hedge = re.compile(r"\b(?:" + "|".join(re.escape(h) for h in self.hedges) + r")\b", re.I)

    def check(self, text, sources):
        src_list = [sources] if isinstance(sources, str) else list(sources or [])
        src_figs = [figures(s) for s in src_list]
        src_dates = [parse_dates(s) for s in src_list]
        src_regs = [{_norm_reg(m.group(1)) for m in RE_REG.finditer(s)} for s in src_list]
        all_figs = set().union(*src_figs) if src_figs else set()
        all_dates = set().union(*src_dates) if src_dates else set()
        all_regs = set().union(*src_regs) if src_regs else set()
        rep = Report()
        for sent in RE_SPLIT.split(text or ""):
            sent = (sent or "").strip()
            if not sent:
                continue
            body = RE_CITE.sub("", sent)
            figs, dates = figures(body), parse_dates(body)
            regs = {_norm_reg(x.group(1)) for x in RE_REG.finditer(body)}
            claims = [("figure", f, f in all_figs) for f in figs] + [("date", d, d in all_dates) for d in dates] + \
                     [("regulation", r, r in all_regs) for r in regs]
            bad = [f"{k} {v}" for k, v, ok in claims if not ok]
            where = sorted({i + 1 for i in range(len(src_list))
                            if any((k == "figure" and v in src_figs[i]) or (k == "date" and v in src_dates[i]) or
                                   (k == "regulation" and v in src_regs[i]) for k, v, ok in claims if ok)})
            if bad:
                status = "unsupported"
            elif PH in sent:
                status = "missing"
            elif self.re_hedge.search(sent):
                status = "assumption"
            elif claims:
                status = "verified"
            else:
                status = "no_claims"
            rep.claims += len(claims)
            rep.grounded += sum(ok for _, _, ok in claims)
            rep.unsupported += bad
            rep.missing += sent.count(PH)
            rep.assumptions += status == "assumption"
            rep.sentences.append({"text": sent[:300], "status": status, "claims": len(claims), "unsupported": bad,
                                  "sources": where})
        return rep

    def needs_action(self, rep):
        r = rep.support_ratio
        return len(rep.unsupported) > self.max_unsupported or (r is not None and r < self.min_ratio)

    def enforce(self, text, sources):
        """(text to show, report, action). mask: unsupported values become [●] through the app's verifier; abstain: the
        answer is replaced by a statement of what is unsupported; flag: the text is kept and the report marks it."""
        rep = self.check(text, sources)
        if not self.needs_action(rep):
            return text, rep, "allow"
        if self.action == "abstain":
            items = ", ".join(rep.unsupported[:6]) or "the answer's figures"
            return ABSTAIN.format(items=items), rep, "abstain"
        if self.action == "mask":
            src_list = [sources] if isinstance(sources, str) else list(sources or [])
            masked, _ = mask_ungrounded(text, [{"type": "short_text", "label": "source", "value": s} for s in src_list])
            return masked, rep, "mask"
        return text, rep, "flag"


def label_sentences(report):
    """Markdown with each sentence tagged, for a reviewer: [verified] [assumption] [missing] [unsupported]."""
    tag = {"verified": "verified", "assumption": "assumption", "missing": "missing information", "unsupported": "UNSUPPORTED",
           "no_claims": "narrative"}
    return "\n".join(f"- *{tag[s['status']]}*{' (sources ' + ', '.join(map(str, s['sources'])) + ')' if s['sources'] else ''}: "
                     f"{s['text']}" for s in report.sentences)
