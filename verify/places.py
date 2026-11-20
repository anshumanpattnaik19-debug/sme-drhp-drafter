"""Place-name gate: a city, district or state in model prose that no issuer file mentions is an invention.

    mask_unknown_places(text, corpus, context="") -> (text with each such place as [●], what was masked)

19 Nov 2026 trace of the shipped model's test drafts: a registered office in "Pune" and a property in "Surat" were
written for issuers whose files give no such address. Both words are ordinary English-vocabulary words for the
name check in verify/checks.py (verify/vocab.txt is built from offer documents, which name those cities), so neither was
masked. This gate checks a gazetteer of Indian states and towns against the issuer's own text (Ctx.corpus(): every file,
fact and offer detail, compacted to lower-case letters and digits, as the organisation-name check uses).

A place that stock-exchange and regulator boilerplate names ("BSE Limited ... Mumbai") is allowed when an institution word
stands just before it, since the issuer's files need not repeat that address.
"""
from __future__ import annotations

import re

PH = "[●]"

STATES = (
    "Andhra Pradesh", "Arunachal Pradesh", "Assam", "Bihar", "Chhattisgarh", "Goa", "Gujarat", "Haryana", "Himachal Pradesh",
    "Jharkhand", "Karnataka", "Kerala", "Madhya Pradesh", "Maharashtra", "Manipur", "Meghalaya", "Mizoram", "Nagaland",
    "Odisha", "Orissa", "Punjab", "Rajasthan", "Sikkim", "Tamil Nadu", "Telangana", "Tripura", "Uttar Pradesh", "Uttarakhand",
    "West Bengal", "Jammu and Kashmir", "Ladakh", "Chandigarh", "Puducherry", "Pondicherry", "Andaman and Nicobar",
    "Dadra and Nagar Haveli", "Daman and Diu", "Lakshadweep",
)
CITIES = (
    "Mumbai", "Navi Mumbai", "Thane", "Pune", "Nagpur", "Nashik", "Aurangabad", "Kolhapur", "Solapur", "Amravati", "Latur",
    "Delhi", "New Delhi", "Noida", "Greater Noida", "Gurugram", "Gurgaon", "Faridabad", "Ghaziabad", "Meerut", "Agra", "Kanpur",
    "Lucknow", "Varanasi", "Allahabad", "Prayagraj", "Mathura", "Bareilly", "Aligarh", "Moradabad", "Dehradun", "Haridwar",
    "Ahmedabad", "Surat", "Vadodara", "Baroda", "Rajkot", "Bhavnagar", "Jamnagar", "Gandhinagar", "Anand", "Morbi", "Bharuch",
    "Ankleshwar", "Vapi", "Valsad", "Mehsana", "Mahesana", "Jaipur", "Jodhpur", "Udaipur", "Kota", "Ajmer", "Bikaner",
    "Indore", "Bhopal", "Gwalior", "Jabalpur", "Ujjain", "Raipur", "Bilaspur", "Bhilai", "Ranchi", "Jamshedpur", "Dhanbad",
    "Patna", "Gaya", "Kolkata", "Howrah", "Siliguri", "Durgapur", "Asansol", "Bhubaneswar", "Cuttack", "Guwahati", "Shillong",
    "Hyderabad", "Secunderabad", "Warangal", "Visakhapatnam", "Vijayawada", "Guntur", "Tirupati", "Bengaluru", "Bangalore",
    "Mysuru", "Mysore", "Mangaluru", "Mangalore", "Hubballi", "Belagavi", "Chennai", "Coimbatore", "Madurai", "Tiruchirappalli",
    "Salem", "Tiruppur", "Erode", "Vellore", "Kochi", "Cochin", "Thiruvananthapuram", "Kozhikode", "Thrissur", "Panaji",
    "Chandigarh", "Ludhiana", "Amritsar", "Jalandhar", "Mohali", "Panchkula", "Jammu", "Srinagar", "Shimla", "Solan", "Baddi",
    "Dubai", "Sharjah", "Singapore", "London", "Hong Kong",
)
PLACES = sorted(set(STATES + CITIES), key=lambda s: (-len(s), s))
RE_PLACE = re.compile(r"(?<![A-Za-z])(" + "|".join(re.escape(p) for p in PLACES) + r")(?![A-Za-z])")
# "BSE Limited, ... Mumbai", "SEBI ... Mumbai", "Registrar of Companies, ... Mumbai": the regulators' own addresses
INSTITUTION = re.compile(r"\b(?:BSE|NSE|SEBI|Stock Exchange|Depositor\w*|CDSL|NSDL|Registrar of Companies|RoC|RBI|"
                         r"Reserve Bank|Ministry|Government of India)\b", re.I)


def _compact(s):
    return re.sub(r"[^a-z0-9]", "", s.lower())


def mask_unknown_places(text, corpus, context=""):
    """Replace each gazetteer place that is neither in the issuer's corpus nor beside an institution name by [●].
    Returns (text, masked) like verify.checks.mask_ungrounded: masked = [{"kind": "place", "raw", "context"}]."""
    hits = []
    for m in RE_PLACE.finditer(text):
        name = m.group(1)
        if _compact(name) in corpus or _compact(context) and _compact(name) in _compact(context):
            continue
        if INSTITUTION.search(text[max(0, m.start() - 90):m.start()]):
            continue
        hits.append((m.start(1), m.end(1), name))
    masked = [{"kind": "place", "raw": n, "context": text[max(0, s - 60):e + 40]} for s, e, n in hits]
    for s, e, _ in reversed(hits):
        text = text[:s] + PH + text[e:]
    return text, masked
