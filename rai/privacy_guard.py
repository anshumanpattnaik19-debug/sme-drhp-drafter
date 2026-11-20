"""Privacy and confidentiality: personal-identifier detection and redaction, training-data memorisation checks and tenant
(project) isolation.

    pg = PrivacyGuard(config["privacy"])
    pg.scan("Aadhaar 2345 6789 0124, PAN ABCPD1234E")    -> [Finding(kind="aadhaar", ...), Finding(kind="pan_individual", ...)]
    pg.redact(text)                                         -> (text with [redacted], findings)

Recognisers are tuned to Indian offer documents: an Aadhaar number must pass its Verhoeff checksum, a card number its Luhn
checksum, a PAN is personal only when its fourth letter is P (a company's PAN, CIN, GSTIN and DIN are disclosed in a DRHP and
are left alone), an e-mail is personal only on a consumer domain, a bank account number needs an account keyword nearby.
Names of promoters and directors are not redacted: a DRHP must disclose them.

With backend "presidio" and Microsoft Presidio installed, Presidio's analyzer runs with these recognisers registered in it, so
its own e-mail, phone, card and IP recognisers are added; without Presidio the built-in recognisers run alone (no spaCy model,
no GPU, about a millisecond per page).

    idx = MemorisationIndex.from_jsonl("trainset/out/train_v3.jsonl")    # word 12-grams of the training targets
    idx.longest_run(output, exclude_doc=current_issuer)                    -> (words, doc_id): verbatim run from training text

    TenantGuard("7c0c669d53").filter(items)                                -> items of this project only; the others are reported
"""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field

# ---------- checksums ----------
_V_D = [[0, 1, 2, 3, 4, 5, 6, 7, 8, 9], [1, 2, 3, 4, 0, 6, 7, 8, 9, 5], [2, 3, 4, 0, 1, 7, 8, 9, 5, 6],
        [3, 4, 0, 1, 2, 8, 9, 5, 6, 7], [4, 0, 1, 2, 3, 9, 5, 6, 7, 8], [5, 9, 8, 7, 6, 0, 4, 3, 2, 1],
        [6, 5, 9, 8, 7, 1, 0, 4, 3, 2], [7, 6, 5, 9, 8, 2, 1, 0, 4, 3], [8, 7, 6, 5, 9, 3, 2, 1, 0, 4],
        [9, 8, 7, 6, 5, 4, 3, 2, 1, 0]]
_V_P = [[0, 1, 2, 3, 4, 5, 6, 7, 8, 9], [1, 5, 7, 6, 2, 8, 3, 0, 9, 4], [5, 8, 0, 3, 7, 9, 6, 1, 4, 2],
        [8, 9, 1, 6, 0, 4, 3, 5, 2, 7], [9, 4, 5, 3, 1, 2, 6, 8, 7, 0], [4, 2, 8, 6, 5, 7, 3, 9, 0, 1],
        [2, 7, 9, 3, 8, 0, 6, 4, 1, 5], [7, 0, 4, 6, 9, 1, 3, 2, 5, 8]]


def verhoeff_ok(digits):
    c = 0
    for i, ch in enumerate(reversed(digits)):
        c = _V_D[c][_V_P[i % 8][int(ch)]]
    return c == 0


def luhn_ok(digits):
    total, alt = 0, False
    for ch in reversed(digits):
        d = int(ch)
        if alt:
            d = d * 2 - 9 if d > 4 else d * 2
        total += d
        alt = not alt
    return total % 10 == 0


# ---------- recognisers ----------
RE_AADHAAR = re.compile(r"(?<![\d,.])([2-9]\d{3})[\s-]?(\d{4})[\s-]?(\d{4})(?![\d,.]\d|\d)")
RE_PAN = re.compile(r"\b[A-Z]{3}([ABCFGHJLPT])[A-Z]\d{4}[A-Z]\b")
RE_MOBILE = re.compile(r"(?<!\d)(?<!\d[,.])(?:\+91[\s-]?|0)?[6-9]\d{4}[\s-]?\d{5}(?!\d|[,.]\d)")
RE_EMAIL = re.compile(r"\b[\w.+-]+@([\w-]+(?:\.[\w-]+)+)\b")
RE_ACCOUNT = re.compile(r"\b(?:a/?c|account|acct)\b\.?[^\d\n]{0,25}?(\d[\d\s-]{7,20}\d)\b", re.I)   # "account number is 5010..."
RE_CARD = re.compile(r"(?<!\d)(?:\d[ -]?){13,19}(?!\d)")
RE_PASSPORT = re.compile(r"\bpassport\b[^.\n]{0,30}?\b([A-PR-WY][1-9]\d{6})\b", re.I)
RE_DOB = re.compile(r"\b(?:date of birth|d\.?o\.?b\.?|born on)\b\s*[:\-]?\s*(\d{1,2}[\s/.-](?:\d{1,2}|[A-Za-z]{3,9})[\s/.-]\d{2,4}|"
                    r"[A-Za-z]{3,9}\s+\d{1,2},?\s+\d{4})", re.I)


@dataclass
class Finding:
    kind: str
    start: int
    end: int
    value_sha256: str          # the value itself is never kept in a finding
    source: str = "builtin"


def _f(kind, m, group=0, source="builtin"):
    s, e = m.span(group)
    return Finding(kind, s, e, hashlib.sha256(m.group(group).encode()).hexdigest()[:16], source)


@dataclass
class PrivacyGuard:
    config: dict = field(default_factory=dict)

    def __post_init__(self):
        c = self.config or {}
        self.token = c.get("redact_token", "[redacted]")
        self.kinds = set(c.get("redact", ["aadhaar", "pan_individual", "mobile", "personal_email", "bank_account",
                                          "card_number", "passport", "date_of_birth"]))
        # a filed DRHP's promoter section states an individual promoter's PAN and date of birth (as the issuer's own documents
        # in the test set do): in a draft or an extraction of the issuer's own text these are disclosures, when a source holds them
        self.draft_allowed = set(c.get("allowed_in_drafts_if_in_source", ["pan_individual", "date_of_birth"]))
        self.personal_domains = {d.lower() for d in c.get("personal_email_domains", ["gmail.com", "yahoo.com", "hotmail.com",
                                                                                   "outlook.com", "rediffmail.com"])}
        self._presidio = None
        if c.get("backend") == "presidio":
            self._presidio = _presidio_analyzer()

    def scan(self, text):
        text = text or ""
        out = []
        for m in RE_AADHAAR.finditer(text):
            if verhoeff_ok("".join(m.groups())):
                out.append(_f("aadhaar", m))
        for m in RE_PAN.finditer(text):
            out.append(_f("pan_individual" if m.group(1) == "P" else "pan_entity", m))
        for m in RE_MOBILE.finditer(text):
            out.append(_f("mobile", m))
        for m in RE_EMAIL.finditer(text):
            out.append(_f("personal_email" if m.group(1).lower() in self.personal_domains else "business_email", m))
        for m in RE_ACCOUNT.finditer(text):
            digits = re.sub(r"\D", "", m.group(1))
            if 9 <= len(digits) <= 18:
                out.append(_f("bank_account", m, 1))
        for m in RE_CARD.finditer(text):
            digits = re.sub(r"\D", "", m.group(0))
            if 13 <= len(digits) <= 19 and luhn_ok(digits) and not RE_AADHAAR.fullmatch(m.group(0).strip()):
                out.append(_f("card_number", m))
        for m in RE_PASSPORT.finditer(text):
            out.append(_f("passport", m, 1))
        for m in RE_DOB.finditer(text):
            out.append(_f("date_of_birth", m, 1))
        if self._presidio is not None:
            out += _presidio_findings(self._presidio, text)
        return _dedupe(out)

    def redact(self, text):
        """(text with every finding of a redacted kind replaced, all findings)."""
        findings = self.scan(text)
        hits = sorted((f for f in findings if f.kind in self.kinds), key=lambda f: f.start, reverse=True)
        for f in hits:
            text = text[: f.start] + self.token + text[f.end:]
        return text, findings

    def leaked(self, output, sources=(), context="qa"):
        """Personal identifiers of a redacted kind in an output. In a Q&A answer none may appear, whatever the sources hold.
        In a draft or an extraction (context "draft" / "extraction"), the kinds in allowed_in_drafts_if_in_source may appear
        when a source holds the same value (the issuer's own disclosure); every other kind is still a leak."""
        src = " ".join([sources] if isinstance(sources, str) else list(sources or []))
        out = []
        for f in self.scan(output):
            if f.kind not in self.kinds:
                continue
            if context in ("draft", "extraction") and f.kind in self.draft_allowed and output[f.start:f.end] in src:
                continue
            out.append(f)
        return out

    def redact_leaks(self, text, sources=(), context="qa"):
        """(text with only the leaked identifiers replaced, leaked findings): the context-aware form of redact()."""
        hits = sorted(self.leaked(text, sources, context), key=lambda f: f.start, reverse=True)
        for f in hits:
            text = text[: f.start] + self.token + text[f.end:]
        return text, hits


def _dedupe(findings):
    findings = sorted(findings, key=lambda f: (f.start, -(f.end - f.start)))
    out, end = [], -1
    for f in findings:
        if f.start >= end:
            out.append(f)
            end = f.end
    return out


# ---------- optional Microsoft Presidio ----------
PRESIDIO_KINDS = {"EMAIL_ADDRESS": "personal_email", "PHONE_NUMBER": "mobile", "CREDIT_CARD": "card_number",
                  "IBAN_CODE": "bank_account", "IP_ADDRESS": "ip_address"}


def _presidio_analyzer():
    try:
        from presidio_analyzer import AnalyzerEngine, Pattern, PatternRecognizer
        from presidio_analyzer.nlp_engine import NlpEngineProvider
    except ImportError:
        return None
    try:
        nlp = NlpEngineProvider(nlp_configuration={"nlp_engine_name": "spacy",
                                                   "models": [{"lang_code": "en", "model_name": "en_core_web_sm"}]}).create_engine()
        engine = AnalyzerEngine(nlp_engine=nlp, supported_languages=["en"])
    except Exception:  # noqa: BLE001 - no spaCy model: Presidio is optional
        return None
    engine.registry.add_recognizer(PatternRecognizer(supported_entity="IN_AADHAAR", patterns=[
        Pattern("aadhaar", RE_AADHAAR.pattern, 0.5)]))
    engine.registry.add_recognizer(PatternRecognizer(supported_entity="IN_PAN", patterns=[Pattern("pan", RE_PAN.pattern, 0.6)]))
    return engine


def _presidio_findings(engine, text):
    out = []
    for r in engine.analyze(text=text, language="en", entities=list(PRESIDIO_KINDS)):
        kind = PRESIDIO_KINDS[r.entity_type]
        val = text[r.start:r.end]
        if kind == "personal_email" and val.split("@")[-1].lower() not in {"gmail.com", "yahoo.com", "hotmail.com",
                                                                        "outlook.com", "rediffmail.com"}:
            kind = "business_email"
        out.append(Finding(kind, r.start, r.end, hashlib.sha256(val.encode()).hexdigest()[:16], "presidio"))
    return out


# ---------- memorisation / extraction ----------
def _words(text):
    return re.findall(r"\w+", (text or "").lower())


class MemorisationIndex:
    """Hashed word n-grams of training targets, by issuer: shows whether an output reproduces training text verbatim, and
    whether that text belongs to another issuer (confidential-data leakage)."""

    SHARED = -1                    # a gram in the training text of two or more issuers: boilerplate, not confidential

    def __init__(self, n=12):
        self.n = n
        self.grams = {}

    @classmethod
    def from_jsonl(cls, path, n=12, skills=("drafting", "qa")):
        idx = cls(n)
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                if not line.strip():
                    continue
                r = json.loads(line)
                md = r.get("metadata", {})
                if skills and md.get("skill") not in skills:
                    continue
                idx.add(r["messages"][-1]["content"], md.get("doc_id"))
        return idx

    def _keys(self, words):
        for i in range(len(words) - self.n + 1):
            yield i, hashlib.blake2b(" ".join(words[i:i + self.n]).encode(), digest_size=8).digest()

    def add(self, text, doc_id):
        for _, k in self._keys(_words(text)):
            prev = self.grams.get(k)
            if prev is None:
                self.grams[k] = doc_id
            elif prev != doc_id:
                self.grams[k] = self.SHARED

    def longest_run(self, text, exclude_doc=None):
        """(length in words of the longest verbatim run shared with one other issuer's training text, that issuer). Wording
        found in two or more issuers' documents (standard DRHP boilerplate) does not count."""
        words = _words(text)
        best, best_doc, run, run_doc, last = 0, None, 0, None, -2
        for i, k in self._keys(words):
            doc = self.grams.get(k)
            if doc is None or doc == self.SHARED or (exclude_doc is not None and doc == exclude_doc):
                run, last = 0, -2
                continue
            run = run + 1 if i == last + 1 and doc == run_doc else 1
            run_doc, last = doc, i
            if run > best:
                best, best_doc = run, doc
        return (best + self.n - 1 if best else 0), best_doc


# ---------- tenant isolation ----------
@dataclass
class TenantGuard:
    tenant: str
    key: str = "project"

    def filter(self, items):
        """(items that belong to this tenant or carry no tenant, items that belong to another tenant)."""
        keep, foreign = [], []
        for it in items:
            owner = it.get(self.key) if isinstance(it, dict) else getattr(it, self.key, None)
            (keep if owner in (None, self.tenant) else foreign).append(it)
        return keep, foreign

    def check_path(self, path, root):
        """True if a workspace path lies inside this tenant's own folder."""
        import os
        base = os.path.realpath(os.path.join(root, self.tenant))
        return os.path.realpath(path).startswith(base + os.sep) or os.path.realpath(path) == base
