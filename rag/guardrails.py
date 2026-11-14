"""Rule-based guardrails around the assistant, a backstop to what the model is trained to do (data/qa.py).

    screen(question) -> (kind, answer) or None      investment advice, DRHP-stage price terms, personal identifiers,
                                                   omitting or softening a mandatory disclosure
    Redactor().feed(delta) / .flush()              masks Aadhaar, PAN and mobile numbers in streamed model output,
                                                   a line at a time (no identifier spans a line)

The answers are the ones the model is trained on, so the assistant says the same thing with or without a model.
Prompt injection inside the issuer's files is handled by the model (trained to ignore and report it) and by the
answer check in rag/agent.py (every figure must be in the cited evidence).
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
ANSWERS = {"invest": INVEST_A[0], "price": PRICE_A[0], "pii": PII_A[0], "omission": OMIT_A[0]}
LABELS = {"invest": "investment advice", "price": "DRHP-stage price terms", "pii": "personal identifiers",
          "omission": "omitting or softening a mandatory disclosure"}

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
