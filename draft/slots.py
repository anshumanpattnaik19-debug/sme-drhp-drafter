"""Facts the model is told it does not have.

    unknown_facts(sub, section_title, facts) -> [fact dicts whose value is [●]]

A model that is trained to put the issuer's facts into prose also learns that an office sub-heading states an address. When
the files give none, it writes a plausible one (19 Nov 2026 trace: "Plot No. 240, Ground Floor, Sector 11, Surat" for an
issuer whose address fact held only the label "Plot number", and an office in Pune for one with no address at all; address
details were 47% of the 74 invented figures). So when a sub-heading calls for a value and no fact supplies it, the facts
carry an explicit [●] for it, and the model copies the placeholder instead of filling the gap.
"""
from __future__ import annotations

import re

PH = "[●]"

# (sub-heading or section pattern, slot label, pattern a supplying fact's label or value must match)
SLOTS = [
    (r"registered office|corporate office|propert|premises|address|location of", "registered office address",
     r"address|registered office|business address|premises|office location"),
    (r"contact|compliance officer|company secretary|registrar|investor grievance", "telephone number", r"phone|tel\b|telephone|mobile|contact number"),
    (r"contact|compliance officer|company secretary|registrar|investor grievance", "e-mail address", r"e-?mail"),
    (r"contact|compliance officer|company secretary|registrar|investor grievance|website", "website", r"website|web site|url"),
]


def _supplied(facts, pattern):
    rx = re.compile(pattern, re.I)
    for f in facts:
        val = str(f.get("value", "")).strip()
        if val and val != PH and (rx.search(str(f.get("label", ""))) or (f.get("type") == "text" and rx.search(val))):
            return True
    return False


def unknown_facts(sub, section_title, facts):
    """Explicit [●] facts for the values this sub-heading calls for and `facts` (the facts and passages the model will see)
    do not supply. A passage counts as supplying a value when its text names it."""
    out = []
    for when, label, has in SLOTS:
        if not re.search(when, f"{sub} {section_title}", re.I):
            continue
        if _supplied(facts, has):
            continue
        out.append({"id": f"u{len(out)}", "type": "short_text", "label": label, "value": PH, "origin": "unknown"})
    return out
