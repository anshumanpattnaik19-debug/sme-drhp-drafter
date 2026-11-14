"""Offline tests for the verifier (verify/checks.py): the cases FAILURE_LOG 25 found on A_dpo's test drafts.

    python -m pytest tests/test_verify.py -q
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from draft.writer import attach_citations  # noqa: E402
from verify.checks import Known, mask_ungrounded, scan, verify_section  # noqa: E402

FACTS = [{"id": "a", "type": "amount", "label": "Revenue", "value": "1,440.00", "unit": "₹ lakhs", "period": "FY25"},
         {"id": "b", "type": "person", "label": "Managing Director", "value": "Ramesh Kumar Gupta"},
         {"id": "c", "type": "count", "label": "Age", "value": "52 years"},
         {"id": "d", "type": "date", "label": "Appointed", "value": "April 1, 2021"}]


def _kinds(text):
    return [(f["kind"], f["raw"], f["grounded"]) for f in scan(text, Known(FACTS))]


def test_page_references_are_not_figures():
    found = _kinds("Except as disclosed in the section titled 'Financial Indebtedness' beginning on page 200 of this DRHP.")
    assert found == [("page_ref", "page 200", False)]
    assert _kinds("see pages 119 to 124")[0][0] == "page_ref"


def test_small_numbers_in_ages_experience_percentages_amounts():
    found = _kinds("Mr. Ramesh Kumar Gupta, aged 52, has 15 years of experience and holds 12% of shares worth ₹ 5 lakhs.")
    small = [(r, g) for k, r, g in found if k == "small"]
    assert small == [("52", True), ("15", False), ("12", False), ("5", False)]


def test_dates_checked_in_every_format():
    found = _kinds("He was appointed on April 1, 2021 and born on 14.08.1971; the Board met on 3rd June 2022.")
    dates = [(r, g) for k, r, g in found if k == "date"]
    assert sorted(dates) == [("14.08.1971", False), ("3rd June 2022", False), ("April 1, 2021", True)]
    assert not [f for f in found if f[0] == "figure"]      # date digits are not figures


def test_names_after_an_honorific():
    found = _kinds("Mr. Ramesh Kumar Gupta and Mrs. Sunita Rao are our Promoters.")
    assert [(r, g) for k, r, g in found if k == "name"] == [("Ramesh Kumar Gupta", True), ("Sunita Rao", False)]


def test_years_and_grounded_figures_are_fine():
    assert _kinds("In 2023 revenue was ₹ 1,440.00 lakhs.") == [("figure", "1,440.00", True)]
    assert _kinds("Due to COVID-19, in FY 2023-24 our 1-2 key clients paused orders.") == []


def test_identifiers_addresses_counts_and_spaced_ordinals():
    text = ("FSSAI License No. EIC/1105/18/000299 dated 27 th October 2018 for the plant at Plot No. 28/29, Sector - 18. "
            "We intend to hire 10 personnel.")
    found = {(k, r) for k, r, g in _kinds(text) if not g}
    assert found == {("identifier", "EIC/1105/18/000299"), ("date", "27 th October 2018"), ("address", "28/29"),
                     ("address", "18"), ("small", "10")}
    facts = FACTS + [{"id": "e", "type": "short_text", "label": "FSSAI licence", "value": "EIC/1105/18/000299"}]
    assert ("identifier", "EIC/1105/18/000299", True) in [(f["kind"], f["raw"], f["grounded"]) for f in scan(text, Known(facts))]


def test_mask_ungrounded():
    text = ("Mrs. Sunita Rao, aged 45, joined on 3rd June 2022. Revenue was ₹ 1,440.00 lakhs against ₹ 2,750.00 lakhs, "
            "as set out on page 119.")
    out, masked = mask_ungrounded(text, FACTS)
    assert out == "Mrs. [●], aged [●], joined on [●]. Revenue was ₹ 1,440.00 lakhs against ₹ [●] lakhs, as set out on page [●]."
    assert sorted(m["kind"] for m in masked) == ["date", "figure", "name", "page_ref", "small"]
    again, more = mask_ungrounded(out, FACTS)
    assert again == out and not more                         # masking is idempotent


def test_context_text_counts_as_a_source():
    out, masked = mask_ungrounded("Mr. Anil Shah founded Shah Polymers Limited.", [], context="Shah Polymers Limited Anil")
    assert out.startswith("Mr. Anil Shah") and not masked


def test_verify_section_reports_new_kinds_and_page_refs():
    draft = {"blocks": [{"type": "paragraph", "text": "Mrs. Sunita Rao, aged 45, is a Director (see page 119). "
                                                      "Revenue was ₹ 1,440.00 lakhs.", "facts": ["a"]}]}
    v = verify_section("risk_factors", draft, FACTS, {})
    assert sorted((u["kind"], u["figure"]) for u in v["ungrounded"]) == [("name", "Sunita Rao"), ("small", "45")]
    assert [p["figure"] for p in v["page_refs"]] == ["page 119"]
    assert v["grounded"] == 1 and not v["weak"]


def test_rare_places_and_organisations_without_honorific():
    text = ("Our plant is at Village Kandiveli, Taluka Dahanu, District Thane. We supply Ddev Plastiks and our Monthly "
            "Rent is paid to the Lessor under a Bill of Lading. Our Board of Directors and SEBI approved the GFRP line.")
    rare = [r for k, r, g in _kinds(text) if k == "name" and not g]
    assert rare == ["Kandiveli", "Dahanu", "Ddev Plastiks"]
    out, _ = mask_ungrounded(text, FACTS)
    assert "Village [●], Taluka [●], District Thane" in out and "supply [●] and" in out


def test_family_table_names_stop_at_relationship_words():
    facts = [{"id": "x", "type": "person", "label": "Promoter", "value": "Sandeep Dhurka"}]
    out, masked = mask_ungrounded("Mr. Sandeep Dhurka Spouse’s Father Mr. Ravi Menon", facts)
    assert out == "Mr. Sandeep Dhurka Spouse’s Father Mr. [●]" and [m["raw"] for m in masked] == ["Ravi Menon"]


def test_spaced_plot_list_is_one_address():
    out, masked = mask_ungrounded("facility at Plot No. 28/29/36 / 37 / 38, Sector - 18,", [])
    assert out == "facility at Plot No. [●], Sector - [●]," and [m["kind"] for m in masked] == ["address", "address"]


def test_rare_words_in_the_inputs_are_kept():
    facts = FACTS + [{"id": "p", "type": "place", "label": "Plant", "value": "Village Kandiveli, Taluka Dahanu"}]
    out, masked = mask_ungrounded("Our plant is at Village Kandiveli, Taluka Dahanu.", facts, context="Ddev Plastiks Limited")
    assert out == "Our plant is at Village Kandiveli, Taluka Dahanu." and not masked
    assert mask_ungrounded("Ddev Plastiks’ products", [], context="Ddev Plastiks Limited")[1] == []


def test_citations_match_numbers_by_value():
    blocks = attach_citations([{"type": "paragraph", "text": "Revenue was ₹ 1440 lakhs.", "facts": []}], FACTS)
    assert blocks[0]["facts"] == ["a"]
