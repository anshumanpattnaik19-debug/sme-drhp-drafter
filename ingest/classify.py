"""Stage 2: classify an issuer file by keyword rules on its name and first text (SLM fallback later).

    classify(filename, text) -> {"doc_type", "label", "category", "confidence", "matched"}
"""
from __future__ import annotations

import re

CATEGORIES = ["Corporate", "Financial", "Business", "People", "Legal & Approvals", "Offer", "Other"]

# doc_type: (label, category, filename keywords, text keywords). Order matters: first strong match wins.
DOC_TYPES = {
    "coi": ("Certificate of incorporation", "Corporate", ["certificate_of_incorporation", "coi"], ["certificate of incorporation"]),
    "moa": ("Memorandum of Association", "Corporate", ["memorandum"], ["memorandum of association"]),
    "aoa": ("Articles of Association", "Corporate", ["articles"], ["articles of association"]),
    "board_resolution": ("Board resolutions", "Corporate", ["board_resolution"], ["resolved that", "board of directors"]),
    "shareholder_resolution": ("Shareholder resolutions / EGM", "Corporate", ["egm", "agm", "special_resolution"], ["extra-ordinary general meeting", "special resolution"]),
    "share_capital": ("Share capital build-up", "Corporate", ["share_capital", "capital_buildup", "shareholding"], ["build-up", "cumulative", "shareholding pattern"]),
    "allotment": ("Allotment records", "Corporate", ["allotment", "pas-3", "pas3"], ["return of allotment"]),
    "restated_fs": ("Restated financial information", "Financial", ["restated_financial_information", "restated_fs"], ["restated financial information", "examination report"]),
    "restated_workings": ("Restated financials workings", "Financial", ["restated_financials_workings", "workings"], []),
    "audited_fs": ("Audited financial statements", "Financial", ["audited_fs", "audited"], ["independent auditor", "balance sheet as at"]),
    "borrowings": ("Statement of borrowings", "Financial", ["borrowings", "indebtedness"], ["sanctioned amount", "outstanding"]),
    "kpi": ("KPI certificate", "Financial", ["kpi"], ["key performance indicators"]),
    "working_capital": ("Working capital certificate", "Financial", ["working_capital"], ["working capital requirement"]),
    "funds_deployed": ("Funds deployed certificate", "Financial", ["funds_deployed"], ["funds deployed"]),
    "tax_benefits": ("Statement of special tax benefits", "Financial", ["tax_benefit"], ["special tax benefits"]),
    "sanction_letter": ("Bank sanction letter", "Financial", ["sanction_letter", "sanction"], ["sanction letter", "we are pleased to sanction"]),
    "business_note": ("Business information note", "Business", ["business_note", "company_profile"], ["our products", "manufacturing facility"]),
    "operational_data": ("Operational data", "Business", ["operational_data", "capacity_utilisation"], ["capacity utilisation"]),
    "process_flow": ("Process flow chart", "Business", ["process_flow", "flow_chart", "execution_flow"], []),
    "order_book": ("Order book certificate", "Business", ["order_book"], ["order book certificate", "certified order book"]),
    "work_completion": ("Work completion certificates", "Business", ["work_completion", "completion_certificate"], ["work completion certificate"]),
    "industry_report": ("Industry report", "Business", ["industry_report", "industry"], ["industry report", "market size"]),
    "insurance_ip": ("Insurance and IP register", "Business", ["insurance", "_ip_", "trademark"], ["insurance policy", "trade mark"]),
    "plant_photos": ("Plant photographs / layout", "Business", ["plant_photograph", "photographs"], []),
    "people_profiles": ("Promoter, director and KMP profiles", "People", ["promoter", "director_kmp", "kmp", "profiles"], ["key managerial personnel", "din"]),
    "director_declarations": ("Director consents and declarations", "People", ["director_consents", "declarations", "dir-2", "dir-8"], ["dir-8", "dir-2"]),
    "litigation": ("Litigation certificate", "Legal & Approvals", ["litigation"], ["outstanding litigation", "materiality"]),
    "approvals": ("Licences and approvals register", "Legal & Approvals", ["licences_and_approvals", "approvals"], ["validity", "licence"]),
    "lease": ("Lease / leave and licence", "Legal & Approvals", ["leave_and_licence", "lease", "rent"], ["leave and licence", "licensor"]),
    "licence": ("Licence / certificate", "Legal & Approvals", ["licence", "license", "noc", "consent_cca", "gst_registration", "gpcb", "bocw", "registration", "pollution_consent", "fssai"], ["registration certificate", "no objection"]),
    "group_rpt": ("Group companies and RPT", "Legal & Approvals", ["group_compan", "rpt", "related_part"], ["related party"]),
    "offer_note": ("Note on proposed issue", "Offer", ["note_on_proposed_issue", "proposed_issue", "offer_note"], ["proposed issue", "fresh issue"]),
    "objects_cost": ("Objects and project cost", "Offer", ["objects", "project_cost"], ["objects of the issue", "project cost"]),
    "quotation": ("Quotation", "Offer", ["quotation", "quote"], ["quotation", "validity of offer"]),
    "selling_shareholder_consent": ("Selling shareholder consent", "Offer", ["selling_shareholder"], ["offer for sale"]),
    "capacity_certificate": ("Chartered engineer certificate", "Offer", ["chartered_engineer", "capacity_certificate"], ["chartered engineer"]),
    "shareholder_agreement": ("Shareholders' agreement and waiver", "Corporate", ["shareholders_agreement", "shareholder_agreement", "waiver"], ["shareholders' agreement", "shareholders agreement"]),
    "revenue_certificate": ("Channel and category revenue certificate", "Financial", ["channel_and_category", "revenue_certificate", "category_revenue"], ["channel and category", "revenue by channel"]),
    "material_agreement": ("Distribution and other material agreements", "Business", ["distribution_and", "agreements_specimen", "material_agreement", "cf_agreement"], ["distributor agreement", "carrying and forwarding", "distribution agreement"]),
    "trademark_deed": ("Trade mark assignment deed", "Legal & Approvals", ["assignment_of_trade", "deed_of_assignment", "trade_mark_registration", "trademark_registration"], ["deed of assignment", "assignment of trade mark"]),
    "media_plan": ("Media plan / advertising agency", "Offer", ["media_plan", "advertising_agency"], ["media plan", "advertising agency"]),
    "document_index": ("Document index", "Other", ["document_index", "index"], []),
    "other": ("Other", "Other", [], []),
}


def _norm(s: str) -> str:
    return re.sub(r"[\s\-]+", "_", s.lower())


def classify(filename: str, text: str = "") -> dict:
    name = _norm(filename)
    head = text[:4000].lower()
    best, best_score, matched = "other", 0.0, []
    for key, (_label, _cat, fkw, tkw) in DOC_TYPES.items():
        if key == "other":
            continue
        hits_f = [k for k in fkw if _norm(k) in name]
        hits_t = [k for k in tkw if re.search(r'\b' + re.escape(k) + (r'\b' if len(k) <= 4 else ''), head)]   # "din" is not "building"
        score = 2.0 * len(hits_f) + 1.0 * len(hits_t)
        if score > best_score:
            best, best_score, matched = key, score, hits_f + hits_t
    label, category, _f, _t = DOC_TYPES[best]
    confidence = 0.0 if best == "other" else min(0.99, 0.55 + 0.15 * best_score)
    return {"doc_type": best, "label": label, "category": category, "confidence": round(confidence, 2),
            "matched": matched}


def doc_type_options() -> list[dict]:
    return [{"value": k, "label": v[0], "category": v[1]} for k, v in DOC_TYPES.items()]
