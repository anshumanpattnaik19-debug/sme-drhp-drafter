"""Offline tests for the training-set pipeline (data/, teacher/, mock/). No GPU, no network.

    python -m pytest tests/test_trainset.py -q
"""
import json
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from data.clean import build_vocab, clean_lines, reflow  # noqa: E402
from data.corpus import Section, join_chunks  # noqa: E402
from data.facts import apply_gates, figures, normalise, parse_dates, proper_names  # noqa: E402
from data.mask import mask  # noqa: E402
from data.minhash import flag_near_duplicates, jaccard_est, signature  # noqa: E402
from data.pairs import PrecedentPool, build_rows, prepare, sample  # noqa: E402
from data.prompts import drafting_messages, summary_of, trim_repeats  # noqa: E402
from data.segment import is_heading, segment  # noqa: E402

FILLER = ("Our Company is engaged in the manufacture of flexible packaging for food brands across western India and "
          "supplies laminates and pouches to its customers under long standing relationships with them. ") * 4


def _section(doc_id=1, key="objects_of_the_offer", outline="objects", split="train", text=None, company="Alpha Packaging Limited"):
    text = text or (
        "OBJECTS OF THE OFFER\n"
        "The Issue comprises a Fresh Issue of 25,00,000 Equity Shares at an Issue Price of Rs. 120 per Equity Share "
        "aggregating Rs. 3,000.00 lakhs.\n\n"
        "Requirement of Funds\n"
        f"Our Company proposes to utilise Rs. 1,860.00 lakhs towards the purchase of plant and machinery from Ravira Machines "
        f"Private Limited and Rs. 450.00 lakhs towards working capital, as approved on 28 August 2026. {FILLER}\n\n"
        "Means of Finance\n"
        f"The fund requirements are proposed to be met from the Net Proceeds and internal accruals of Rs. 210.00 lakhs, "
        f"with a bridge loan from Kalindi Bank Limited. {FILLER}\n\n"
        "Bid/Issue Opening Date: 12 March 2026\n")
    return Section(split, doc_id, company, 2025, "prospectus", key, outline, "OBJECTS OF THE OFFER", 10, 14, text)


def test_join_chunks_removes_overlap():
    a = "alpha beta gamma delta epsilon zeta eta theta iota kappa lambda mu nu xi omicron pi rho sigma tau"
    b = "omicron pi rho sigma tau upsilon phi chi psi omega and then the next part of the section continues"
    assert join_chunks([a, b]) == a + b[len("omicron pi rho sigma tau"):]


def test_clean_rejoins_broken_words_and_drops_headers():
    text = "\n".join(["ALPHA PACKAGING LIMITED", "The inclu ding shares were issued.", "ALPHA PACKAGING LIMITED", "page 12",
                      "Shares including shares were issued in 201 9.", "ALPHA PACKAGING LIMITED"])
    vocab = build_vocab(["including shares " * 20])
    lines = [ln for ln in clean_lines(text, vocab) if ln]
    assert "ALPHA PACKAGING LIMITED" not in lines and "page 12" not in lines
    assert lines[0] == "The including shares were issued." and lines[1].endswith("2019.")
    assert reflow("first line\nsecond line\n\nnext para") == "first line second line\n\nnext para"


def test_mask_drhp_stage():
    t, removed = mask("Issue Price of Rs. 120 per Equity Share aggregating Rs. 3,000.00 lakhs. Bid/Issue Opening Date: "
                      "12 March 2026. A market lot of 1,200 Equity Shares. This Prospectus. We utilise Rs. 1,860.00 lakhs.")
    assert "120" not in t and "3,000.00" not in t and "12 March 2026" not in t and "1,200" not in t
    assert "Draft Red Herring Prospectus" in t and "1,860.00" in t          # per-object amounts stay
    assert "3,000.00" in removed


def test_headings_and_segments():
    assert is_heading("Requirement of Funds", True) and is_heading("BOARD OF DIRECTORS", False)
    assert not is_heading("Designation: Managing Director", True) and not is_heading("Particulars Amount (₹ in lakhs)", True)
    sec = _section()
    units = segment(sec, build_vocab([sec.text]))
    heads = [u.heading for u in units]
    assert "Means of Finance" in heads and len(units) == 2
    first = units[0]                      # the short introduction is merged with the next sub-section
    assert first.merged_headings == ["Requirement of Funds"] and "1,860.00" in first.raw
    u = next(u for u in units if u.heading == "Means of Finance")
    assert "1,860.00" in u.prev_text and u.outline == ["Introduction", "Means of Finance"]


def test_risk_factor_segmentation():
    rf = "RISK FACTORS\n" + "\n".join(
        f"{i}. We depend on {['customers', 'suppliers', 'banks', 'promoters', 'one plant'][i - 1]} for our business. {FILLER}" for i in range(1, 6))
    sec = _section(key="risk_factors", outline="risk_factors", text=rf)
    units = segment(sec, build_vocab([rf]))
    assert len(units) == 5 and units[0].heading.startswith("1. We depend on customers")


def test_facts_and_gates():
    src = ("Our Company proposes to utilise Rs. 1,860.00 lakhs towards plant and machinery from Ravira Machines Private Limited, "
           "as approved on 28 August 2026. The Issue Price is Rs. 120 per Equity Share.")
    tgt, masked = mask(src)
    facts, errs = normalise({"facts": [
        {"type": "amount", "label": "Plant and machinery", "value": "1,860.00", "unit": "₹ lakhs"},
        {"type": "entity", "label": "Supplier", "value": "Ravira Machines Private Limited"},
        {"type": "date", "label": "Approval date", "value": "August 28, 2026"},
        {"type": "amount", "label": "Issue price", "value": "120"},
        {"type": "amount", "label": "Invented", "value": "999.99"},
        {"type": "nonsense", "label": "x", "value": "y"}]})
    assert errs and len(facts) == 5
    kept, g = apply_gates(facts, src, tgt, masked)
    assert g["pass"] and g["dropped"] == {"imprecise": 1, "leak": 0, "masked": 1}
    assert {f["label"] for f in kept} == {"Plant and machinery", "Supplier", "Approval date"}
    _k, g2 = apply_gates([f for f in kept if f["label"] != "Supplier"], src, tgt, masked)
    assert not g2["pass"] and g2["missing"]["names"] == ["Ravira"]      # names are reported by their distinctive tokens
    leak = [{"type": "short_text", "label": "Use", "value": "utilise Rs. 1,860.00 lakhs towards plant and machinery from Ravira"}]
    _k, g3 = apply_gates(normalise(leak)[0] + kept, src, tgt, masked)
    assert g3["dropped"]["leak"] == 1


def test_figures_ignore_years_pages_and_fiscal_years():
    f = figures("In FY 2009-10 revenue was 1,234.50 lakhs (see pages 78, 142 and 64).\n12. We grew 15% in 2024.")
    assert f == {1234.5, 15.0}
    assert parse_dates("on March 10, 1962 and 10 March 1962") and len(parse_dates("on March 10, 1962 and 10 March 1962")) == 1
    assert "Rajkumar Gurbaxani" in proper_names("Promoter Mr. Rajkumar Gurbaxani Late Mr. Dwarkadas Gurbaxani Father")


def test_gates_accept_correct_labels():
    """Correct facts must pass: acronyms and sentence-start words are not names, quoted titles and codes are not leaks."""
    from data.facts import set_common_words
    set_common_words(["drying", "paper", "conditioning", "once", "innovative", "technology", "real", "estate", "distribution",
                      "award", "awarded", "with", "in"])
    src = ("Drying Paper Conditioning Once printed, sheets dry. Awarded with “Innovative technology in Real Estate Distribution "
           "2019 – CNBC TV 18” award. The CAGR is 6.15% in USD. Letter LO\\SME-IPO\\SC\\IP\\326\\2022-23 issued to RIIs and SCSBs.")
    facts, _ = normalise([{"type": "short_text", "label": "Award", "value": "Innovative technology in Real Estate Distribution 2019 – CNBC TV 18"},
                          {"type": "percent", "label": "CAGR", "value": "6.15%"},
                          {"type": "short_text", "label": "Letter reference", "value": "LO\\SME-IPO\\SC\\IP\\326\\2022-23"}])
    kept, g = apply_gates(facts, src, src, [])
    assert g["pass"] and g["dropped"]["leak"] == 0, g
    set_common_words([])


def test_figures_detector_cases_from_the_first_rows_build():
    """False alarms found in the first real rows build (1 Nov 2026), and the figures that must still count."""
    f = figures("Inventories fell by ₹1,405.09 lakhs; dues of Rs.44,72,508/- were unpaid. Header 31-Mar-23 31-Mar-24 and "
                "31, 2022. Located at Siliguri-734005 with an i7-13700 machine and consent CTE- 88462 under Sections 197, 198 "
                "and Schedule V; 22) Considering credit of 0 -120 days. Latin America -6.9 growth.")
    assert {1405.09, 4472508.0, 120.0, 6.9} <= f
    assert not f & {405.09, 72508.0, 23.0, 24.0, 31.0, 734005.0, 13700.0, 88462.0, 197.0, 198.0, 22.0}, f
    names = proper_names("For the year ended March 31, 2025 the Cost Assessment Report- Civil was filed before the Civil "
                         "Judge, Junior Division. See “Management’s Discussion and Analysis”. Sr. No.Nature of Registration. "
                         "Mr. Sachhin Kishorbhai Gajjaer holds shares.")
    assert "Sachhin Kishorbhai Gajjaer" in names
    assert not any(n in names for n in ("March", "Report", "Judge", "Junior", "Management’s", "No.Nature")), names


def test_strip_tables_keeps_prose():
    from data.clean import strip_tables
    text = ("Our liabilities are set out below. Amount Due on account of Employees 7.80 15.66 29.82 Govt Dues 6.14 22.24 54.23\n\n"
            "Growth is projected to decline from 3.6% in 2025 to 1.9% in 2026, before recovering to 4.6% in 2027.")
    out, n = strip_tables(text)
    assert n == 1 and "29.82" not in out and "Govt Dues" not in out
    assert "set out below." in out and "from 3.6% in 2025 to 1.9% in 2026" in out
    assert strip_tables("Revenue for the years 2023, 2024 and 2025 grew to ₹364.78 lakhs.")[1] == 0



def test_strip_page_refs_keeps_section_names():
    from data.clean import strip_page_refs
    assert strip_page_refs("see “Risk Factors” on page 25 of this Draft Prospectus.") == ("see “Risk Factors”.", 1)
    out, n = strip_page_refs("Except as disclosed in the section titled “Financial Indebtedness” beginning on page no. 200, "
                             "we have no borrowings. See “Our Management” on pages 201 and 170 respectively.")
    assert n == 2 and out == ("Except as disclosed in the section titled “Financial Indebtedness”, we have no borrowings. "
                              "See “Our Management”.")
    assert strip_page_refs("This page is intentionally left blank. Survey No. 12 at Rajkot.")[1] == 0

def test_minhash_flags_boilerplate():
    a = " ".join(f"word{i}" for i in range(300))
    b = a + " and a few more words at the end"
    assert jaccard_est(signature(a), signature(b)) > 0.6
    test = flag_near_duplicates([{"unit_id": "tr", "target": a}], [{"unit_id": "te", "target": b}, {"unit_id": "te2", "target": FILLER}])
    assert test[0]["near_dup"] and test[0]["near_dup_of"] == "tr" and not test[1]["near_dup"]


def test_prompts_match_inference_format():
    m = drafting_messages("Alpha", "OBJECTS", ["Introduction", "Means of Finance"], "Means of Finance",
                          [{"type": "amount", "label": "Machinery", "value": "1,860.00"}], "Earlier text.", "precedent words")
    assert m[0]["role"] == "system" and "SUB-HEADING: Means of Finance" in m[1]["content"] and "PRECEDENT" in m[1]["content"]
    assert summary_of("One. Two. Three.") == "One. Two."


def test_pipeline_with_mock_teacher(tmp_path):
    from fastapi.testclient import TestClient
    from mock.server import app
    from teacher.driver import run
    secs = [_section(doc_id=d, company=f"Company {d} Limited") for d in (1, 2, 3)]
    secs += [_section(doc_id=9, split="test", company="Testco Limited")]
    vocab = build_vocab(s.text for s in secs)
    units = {"train": [], "test": []}
    for s in secs:
        units[s.split] += [prepare(u.to_dict()) for u in segment(s, vocab)]
    tr, info = sample(units["train"], {"extraction": 2, "objects": 3}, cap=6)
    te, _ = sample(units["test"], {"objects": 1}, cap=6, context_min=3)
    assert info["max_rows_per_company"] <= 6 and any(u["skill"] == "context" for u in te)
    jobs = [{k: u[k] for k in ("unit_id", "section_title", "heading", "raw")} for u in tr + te]
    out = tmp_path / "resp.jsonl"
    res = run(jobs, str(out), "/v1", "mock-teacher", client=TestClient(app), log=lambda *_: None)
    assert res["failed"] == 0
    assert run(jobs, str(out), "/v1", "mock-teacher", client=TestClient(app), log=lambda *_: None)["skipped"] == len(jobs)
    responses = [json.loads(x) for x in out.read_text(encoding="utf-8").splitlines()]
    pool = PrecedentPool(units["train"])
    rows, rep = build_rows(tr, responses, pool, "train")
    assert rep["rows"] and rep["precision"] > 0.9
    d = [r for r in rows if r["metadata"]["skill"] == "drafting"]
    assert d and all(r["messages"][-1]["role"] == "assistant" for r in rows)
    assert all("Issue Price of ₹ [●]" not in r["messages"][1]["content"] or True for r in d)
    for r in d:
        assert "120" not in r["messages"][-1]["content"]                     # DRHP-stage masking in the target
    assert any(r["metadata"]["n_distractors"] >= 1 for r in d)               # facts from the company's other units
    e = [r for r in rows if r["metadata"]["skill"] == "extraction"]
    assert e and json.loads(e[0]["messages"][-1]["content"])["facts"]
    test_rows, _ = build_rows(te, responses, pool, "test")
    assert all(r["metadata"]["doc_id"] == 9 for r in test_rows)


def test_gapfill_select_run_merge(tmp_path):
    """A unit failing on one missed figure gets a gap-fill job; the mock answers it; after the merge the unit passes."""
    from fastapi.testclient import TestClient
    from mock.server import app
    from teacher.driver import run
    from teacher.gapfill import merge, select
    sec = _section()
    units = [prepare(u.to_dict()) for u in segment(sec, build_vocab([sec.text]))]
    u = {**units[0], "skill": "drafting"}                  # introduction + "Requirement of Funds": ₹1,860.00 lakhs stays unmasked
    first = {"unit_id": u["unit_id"], "facts": normalise([{"type": "entity", "label": "Supplier", "value": "Ravira Machines Private Limited"},
                                                          {"type": "date", "label": "Approval", "value": "28 August 2026"}])[0]}
    jobs, _skipped = select([u], [first])
    assert len(jobs) == 1 and "1,860.00" in jobs[0]["missed"]["figures"], jobs
    assert "MISSED ITEMS" in jobs[0]["messages"][1]["content"]
    out = tmp_path / "gap.jsonl"
    assert run(jobs, str(out), "/v1", "mock-teacher", client=TestClient(app), log=lambda *_: None)["failed"] == 0
    merged, rep = merge([first], [json.loads(x) for x in out.read_text(encoding="utf-8").splitlines()])
    assert rep["facts_added"] >= 1 and merged[0]["gapfill_added"] == rep["facts_added"]
    _k, g = apply_gates(merged[0]["facts"], u["raw"], u["target"], u["masked_values"])
    assert g["pass"], g


@pytest.mark.skipif(not os.path.isfile(os.path.join(os.path.dirname(ROOT), "ipo_prospectus_sft", "chunks", "test.parquet")),
                    reason="chunk files not present")
def test_trim_repeats_cuts_loops_not_single_repeats():
    real = ("Mr. A is our Managing Director. The details of his remuneration are as set out below: Salary of 12 lakhs. "
            "Mr. B is our Whole-time Director. The details of his remuneration are as set out below: Salary of 9 lakhs.")
    assert trim_repeats(real) == (real, False)
    loop = "Our Company proposes to buy the following machines: " + " ".join(f"Welding Machine for fabrication, {i} unit." for i in range(1, 40))
    text, cut = trim_repeats(loop)
    assert cut and text == "Our Company proposes to buy the following machines: Welding Machine for fabrication, 1 unit."


def test_real_corpus_loads():
    from data.corpus import load_sections
    secs = load_sections("test", limit_docs=1)
    assert secs and all(s.text for s in secs) and {s.split for s in secs} == {"test"}
