"""Rule-based guardrails around the assistant, a backstop to what the model is trained to do (data/qa.py).

    screen(question) -> (kind, answer) or None      investment advice, DRHP-stage price terms, personal identifiers,
                                                   omitting or softening a mandatory disclosure, stating what the
                                                   documents do not support, sign-off, the assistant's instructions
    Redactor().feed(delta) / .flush()              masks Aadhaar, PAN and mobile numbers in streamed model output,
                                                   a line at a time (no identifier spans a line)

    strip_injections(text) -> (text, n)            drops sentences addressed to the assistant (prompt injection)

The answers are the ones the model is trained on, so the assistant says the same thing with or without a model.
Prompt injection inside the issuer's files is stripped from the evidence before the model sees it (the model is also
trained to ignore and report it), and the answer check in rag/agent.py requires every figure to be in the evidence.
"""
from __future__ import annotations

import re

from data.qa import INVEST_A, OMIT_A, PII_A, PRICE_A

RULES = [
    ("pii", re.compile(r"\b(?:aadhaa?r|passport (?:no|number)|bank account (?:no|number|details)|mobile (?:no|number)|"
                       r"phone (?:no|number)|personal e-?mail|date of birth)\b", re.I)),
    ("pii", re.compile(r"\bPAN(?:\s+(?:no|number|card|of|details))?\b(?!\s+India)")),
    ("omission", re.compile(r"\b(?:remove|delete|drop|omit|leave out|hide|exclude|skip|move)\b.{0,60}?\b(?:litigation|criminal|"
                            r"case|default|notice|demand|penalt\w*|proceeding|show cause|tax dispute)", re.I)),
    ("omission", re.compile(r"\b(?:soften|tone down|downplay|water down|sound less|make (?:it|them|this) less|less serious|"
                            r"so (?:that )?investors (?:skip|miss|ignore))\b", re.I)),
    ("invest", re.compile(r"\b(?:should (?:i|we|investors?) (?:invest|subscribe|buy|apply)|good investment|worth (?:investing|"
                          r"buying|subscribing)|list(?:ing)? (?:at a )?(?:premium|gain)|expected returns?|grey market|\bGMP\b|"
                          r"target price|buy or (?:sell|avoid)|recommend (?:subscribing|investing|buying)|valuation .{0,20}attractive)\b", re.I)),
    ("price", re.compile(r"\b(?:issue|offer|anchor|floor|cap) price\b|\bprice band\b|\blot size\b|\bminimum (?:application|bid) lot\b|"
                         r"\b(?:issue|offer|bid|ipo) (?:open|opens|close|closes|opening|closing)\b|\bissue size in (?:rupees|₹)", re.I)),
]
# requests found by the app-level red team (evaluate/app_redteam.py, 19 Nov 2026) that reached the model or a command
RULES += [
    ("invest", re.compile(r"\b(?:predict|forecast|estimate)\b.{0,40}\b(?:listing|premium|share price|returns?|gains?)\b", re.I)),
    ("fabricate", re.compile(r"\beven (?:if|though|when) (?:the |our |its )?(?:documents?|files?|records?|evidence|issuer)\b|"
                             r"\b(?:make up|made-up|invent|fabricate|pretend|fake)\b|"
                             r"\bwithout (?:any )?(?:evidence|basis|support|documents?)\b", re.I)),
    ("signoff", re.compile(r"\bsign(?:\s|-)?off\b.{0,40}\b(?:draft|section|filing|drhp)\b|"
                           r"\bmark\b.{0,40}\b(?:resolved|reviewed|approved|signed)\b|\bapprove the (?:draft|drhp)\b", re.I)),
    ("prompt", re.compile(r"\b(?:system prompt|your (?:instructions|prompt|rules)|instructions you (?:were|are) given)\b", re.I)),
    ("market", re.compile(r"\b(?:share|stock|market|trading) price\b.{0,40}\b(?:today|now|current(?:ly)?|live|latest)\b|"
                          r"\b(?:current|today'?s|live|latest) (?:share|stock|market|trading) price\b", re.I)),
]
FABRICATE_A = ("I can't write a statement that the issuer's documents do not support. Every statement in the DRHP must be "
               "traceable to the issuer's documents; where a fact is missing, it is requested from the issuer and shown as "
               "[●] until it is confirmed.")
SIGNOFF_A = ("I can't sign off a section or mark review issues as resolved. Sign-off is the reviewer's decision, made section "
             "by section in the Draft screen after the open issues in Review are dealt with.")
PROMPT_A = ("I can't share my instructions. I answer questions about this issuer's documents and the draft, citing the "
            "passage each answer comes from.")
MARKET_A = ("I only have the issuer's documents and the draft, not market data. An SME issuer at DRHP stage is not yet listed, "
            "so its shares have no market price, and the offer price is shown as [●] until the Red Herring Prospectus.")
ANSWERS = {"invest": INVEST_A[0], "price": PRICE_A[0], "pii": PII_A[0], "omission": OMIT_A[0], "fabricate": FABRICATE_A,
           "signoff": SIGNOFF_A, "prompt": PROMPT_A, "market": MARKET_A}
LABELS = {"invest": "investment advice", "price": "DRHP-stage price terms", "pii": "personal identifiers",
          "omission": "omitting or softening a mandatory disclosure", "fabricate": "a statement the documents do not support",
          "signoff": "signing off or resolving review items", "prompt": "the assistant's instructions",
          "market": "market data the documents do not hold"}

# an instruction addressed to the assistant inside an issuer's file (prompt injection): never evidence
RE_INJECTION = re.compile(r"\b(?:note|instruction|message|request)s? (?:to|for) (?:the |any )?(?:ai|assistant|model|llm|chatbot)\b|"
                          r"\b(?:ignore|disregard|forget|override)\s+(?:(?:all|any|your|the|my|previous|prior|above|"
                          r"earlier|system|other)\s+)*(?:instructions|evidence|rules|prompts?)\b|"
                          r"(?:^|\n)\s*system\s*:|\b(?:ai|assistant|model)\s*,\s*(?:ignore|disregard|say|state|answer|reply)\b",
                          re.I)
RE_SENT = re.compile(r"[^.!?\n]*(?:[.!?]+|\n|$)")


def strip_injections(text):
    """(text without the sentences addressed to the assistant, number of sentences removed)."""
    if not text or not RE_INJECTION.search(text):
        return text, 0
    keep, n = [], 0
    for m in RE_SENT.finditer(text):
        s = m.group(0)
        if RE_INJECTION.search(s):
            n += 1
        else:
            keep.append(s)
    return "".join(keep).strip(), n

RE_REDACT = re.compile(r"\b[A-Z]{5}\d{4}[A-Z]\b"                    # PAN
                       r"|\b\d{4}\s?\d{4}\s?\d{4}\b"                 # Aadhaar
                       r"|(?<!\d)(?<!\d[,.])(?:\+91[\s-]?)?[6-9]\d{9}(?!\d|[,.]\d)")   # Indian mobile number; "...210." ends a sentence
REDACTED = "[redacted]"


def screen(question):
    """(kind, answer) when the question is one the assistant must not answer from the documents, else None."""
    for kind, rx in RULES:
        if rx.search(question or ""):
            return kind, ANSWERS[kind]
    return None


def redact(text):
    return RE_REDACT.sub(REDACTED, text)


class Redactor:
    """Holds streamed text back to the end of a line, then releases it redacted."""

    def __init__(self):
        self.buf = ""

    def feed(self, delta):
        self.buf += delta
        cut = self.buf.rfind("\n") + 1
        out, self.buf = self.buf[:cut], self.buf[cut:]
        return redact(out)

    def flush(self):
        out, self.buf = self.buf, ""
        return redact(out)
