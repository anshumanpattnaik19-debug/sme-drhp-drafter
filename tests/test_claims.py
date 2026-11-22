"""Period and basis check (verify/claims.py) and the small gaps closed in verify/checks.py, 21 Nov 2026.

Every case below came from a real draft or from the audit of the checker itself: the hosted draft of 20 Nov 2026, and the false
positives found while tuning on the 89 test drafts (each is a regression test: "aged 40 years", "face value of ₹10", a per-year
list, a year in parentheses, a lead-in "In FY 2025-26,")."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from draft.writer import guard_draft  # noqa: E402
from verify.checks import mask_ungrounded  # noqa: E402
from verify.claims import cues, fiscal_years, mask_period_claims  # noqa: E402

CONC = {"type": "percent", "label": "five for and the top ten for", "value": "61.27", "unit": "%", "period": "",
        "snippet": "In FY 2025-26 it served 266 customers; the top customer accounted for 14.18%, the top five for 39.84% and "
                   "the top ten for 61.27% of revenue from operations."}
ABOUT = {"type": "text", "origin": "passage", "label": "note", "value": "Customer concentration: top ten customers contribute "
         "about 61% of revenue. Long relationships with key customers."}
COMPLAINTS = {"type": "percent", "label": "Customer complaints", "value": "0.42", "unit": "%", "period": "FY 2025-26",
              "snippet": "Customer complaints in FY 2025-26 were 0.42% of dispatches by value (FY 2024-25: 0.57%)."}
FACTS = [CONC, ABOUT, COMPLAINTS]


def masked(text, facts=FACTS):
    out, hits = mask_period_claims(text, facts)
    return out, [h["raw"] for h in hits]


def test_fiscal_years_are_read_as_the_year_they_end():
    assert fiscal_years("In FY 2025-26 and FY26 and fiscal 2024 and 2020-31 and FY 2026-27") == {2024, 2026, 2027}
    assert cues("six months ended 30 September 2026")["half"] and cues("on average over the last three years")["multi"]
    assert not cues("aged 40 years with 7 years of experience, the previous year")["multi"]


def test_the_hosted_draft_of_20_nov_is_masked():
    out, raws = masked("Our top ten customers contribute about 61% of revenue on average over the last three years ended FY 2025-26.")
    assert raws == ["61"] and "[●]% of revenue" in out


def test_the_same_figure_for_its_own_year_or_without_a_period_is_kept():
    for t in ["In FY 2025-26 the top ten customers accounted for 61.27% of revenue from operations.",
              "Top ten customers contribute about 61% of revenue.",
              "The top ten customers accounted for 61.27% of revenue from operations in FY 2025-26."]:
        assert masked(t) == (t, [])


def test_a_figure_stated_for_another_year_is_masked():
    assert masked("In FY 2024-25 the top ten customers accounted for 61.27% of revenue.")[1] == ["61.27"]
    assert masked("The top ten customers accounted for 61.27% of revenue in FY 2027-28.")[1] == ["61.27"]


def test_one_sentence_may_give_two_years_and_each_keeps_its_own():
    t = "Customer complaints were 0.42% in FY 2025-26 and 0.57% in FY 2024-25."
    assert masked(t) == (t, [])
    assert masked("Customer complaints were 0.42% in FY 2024-25 and 0.57% in FY 2025-26.")[1] == ["0.42", "0.57"]


def test_a_per_year_list_under_a_multi_year_frame_is_not_an_average():
    facts = [{"type": "amount", "label": "EBITDA", "value": "710.04", "period": "FY 2024", "snippet": "EBITDA FY 2024"},
             {"type": "amount", "label": "EBITDA", "value": "323.46", "period": "FY 2023", "snippet": "EBITDA FY 2023"}]
    t = "Consistent EBITDA performance over the last few fiscal years: ₹710.04 lakh for FY 2024 and ₹323.46 lakh for FY 2023."
    assert masked(t, facts) == (t, [])
    t = "EBITDA of ₹710.04 lakh (FY 2024), ₹323.46 lakh (FY 2023) over the last three years."
    assert masked(t, facts) == (t, [])                    # a year in parentheses labels the figure before it
    assert masked("EBITDA was ₹323.46 lakh (FY 2024).", facts)[1] == ["323.46"]


def test_a_lead_in_year_governs_the_clause_after_it():
    assert masked("In FY 2025-26, the customer complaints were 0.42% of dispatches.") == (
        "In FY 2025-26, the customer complaints were 0.42% of dispatches.", [])
    assert masked("In FY 2024-25, the customer complaints were 0.42% of dispatches.")[1] == ["0.42"]
    # the multi-year frame of one clause does not reach a clause that names its own year
    t = "Over the last three years, revenue grew steadily, and in FY 2025-26 complaints were 0.42%."
    assert masked(t) == (t, [])


def test_an_average_the_source_does_not_state_is_masked_but_one_it_states_is_kept():
    assert masked("On average, complaints were 0.42% of dispatches.")[1] == ["0.42"]
    facts = [{"type": "percent", "label": "Average attrition", "value": "12.50", "unit": "%", "snippet": "average attrition 12.50%"}]
    t = "On average, attrition was 12.50% of employees."
    assert masked(t, facts) == (t, [])


def test_numbers_that_are_not_percentages_or_money_are_not_read_as_claims():
    facts = [{"type": "number", "label": "Age of director", "value": "40"},
             {"type": "amount", "label": "Face value per Equity Share", "value": "10", "unit": "₹"},
             {"type": "text", "label": "address", "value": "Thane-421601, India"}]
    for t in ["Mr X, aged 40 years, has over 40 years of experience, on average of the last three years.",
              "The weighted average cost of acquisition of Equity Shares of face value of ₹10 each is high.",
              "Thane-421601 with an average production capacity of 2600 MT."]:
        assert masked(t, facts) == (t, [])


def test_a_figure_with_no_evidence_is_left_to_the_value_check():
    t = "In FY 2025-26 export sales were 77.31% of revenue."
    assert masked(t) == (t, [])
    assert "[●]" in mask_ungrounded(t, FACTS)[0]


def test_a_distinctive_figure_stated_for_a_year_is_not_lent_to_another_by_a_silent_source():
    facts = [{"type": "amount", "label": "Capex", "value": "1244", "period": "FY 2026-27", "snippet": "Capex FY 2026-27"},
             {"type": "amount", "label": "Capex total", "value": "1244", "snippet": "Capex total"}]
    assert masked("In FY 2029-30 the capex was ₹1244 lakhs.", facts)[1] == ["1244"]
    common = [{"type": "percent", "label": "Margin", "value": "25", "unit": "%", "period": "FY 2026-27"},
              {"type": "percent", "label": "Margin cap", "value": "25", "unit": "%"}]
    t = "In FY 2029-30 the cap was 25%."
    assert masked(t, common) == (t, [])                    # a common value stays lenient: it recurs for unrelated things


def test_a_half_year_figure_is_not_stated_for_a_full_year():
    facts = [{"type": "amount", "label": "Revenue", "value": "5181.90", "snippet": "Revenue for the six months ended 30 September 2026"}]
    assert masked("Revenue for FY 2025-26 was ₹5181.90 lakhs.", facts)[1] == ["5181.90"]
    t = "Revenue for the six months ended 30 September 2026 was ₹5181.90 lakhs."
    assert masked(t, facts) == (t, [])


def test_a_decimal_point_does_not_end_the_sentence():
    # the first splitter dropped every sentence with "61.27": its period and basis were never read
    assert masked("In FY 2024-25 the top ten customers accounted for 61.27% of revenue. Next sentence.")[1] == ["61.27"]


def test_the_guard_applies_it_to_prose_and_not_to_a_table():
    raw = ("Our top ten customers contribute about 61% of revenue on average over the last three years ended FY 2025-26.\n\n"
           "| Year | Share |\n|---|---|\n| FY 2024-25 | 61.27% |")
    blocks, n, _, _ = guard_draft(raw, "Customers", FACTS, {}, "Kestrel Limited", "")
    prose = " ".join(b.get("text", "") for b in blocks if b["type"] == "paragraph")
    assert "[●]% of revenue" in prose
    assert any(h["kind"] == "period_basis" for b in blocks for h in b.get("masked", []))


def test_per_cent_and_people_are_checked_like_the_symbol_and_employees():
    facts = [{"type": "percent", "label": "Exports", "value": "17.50", "unit": "%"}, {"type": "number", "label": "Employees", "value": "412"}]
    assert "17 per cent" not in mask_ungrounded("Exports were 17 per cent of sales.", facts)[0]
    assert "87 people" not in mask_ungrounded("We employ 87 people across plants.", facts)[0]
    assert mask_ungrounded("Exports were 17.50 per cent of sales.", facts)[0] == "Exports were 17.50 per cent of sales."


# --- a year after the document's own date, said to have begun (hosted draft of 22 Nov 2026) --------------------------------
from verify.claims import mask_future_dates, reporting_year  # noqa: E402

DATED = [{"type": "amount", "label": "Revenue", "value": "7105.40", "period": "six months ended 30 September 2026",
          "snippet": "Revenue from operations in the six months ended 30 September 2026"},
         {"type": "date", "label": "FSSC 22000 v6 expiry", "value": "2 November 2027", "snippet": "FSSC 22000 v6 | Nutrisafe | 2 November 2027"}]


def test_the_reporting_date_is_the_latest_one_the_inputs_call_so():
    assert reporting_year(DATED) == 2026               # the 2027 expiry date is not a reporting date
    assert reporting_year([{"label": "Licence valid till 15 March 2027"}]) is None


def test_certified_since_a_year_after_the_document_is_masked():
    out, hits = mask_future_dates("quality certifications (FSSC 22000 v6 certified since 2027), EPR registration since 2024", DATED)
    assert "certified since [●]" in out and "since 2024" in out and [h["raw"] for h in hits] == ["2027"] and hits[0]["kind"] == "future_date"
    assert mask_future_dates("incorporated in 2031 and operating since 2026.", DATED)[0] == "incorporated in [●] and operating since 2026."


def test_a_later_year_in_other_words_is_left_alone():
    for t in ["The authorisation is valid till 15 March 2027.", "Capex is planned in 2027.", "FY 2026-27 deployment is ₹1,644 lakhs.",
              "Certified since FY 2026-27 under the scheme.", "Registered since 2027/28."]:
        assert mask_future_dates(t, DATED) == (t, [])
    assert mask_future_dates("certified since 2027", [{"label": "no dated fact", "value": "1"}]) == ("certified since 2027", [])


def test_the_guard_applies_it():
    raw = "FSSC 22000 v6 certified since 2027 and ISO 9001:2015 since 2020."
    blocks, *_ = guard_draft(raw, "Industry", DATED, {}, "Kestrel Limited", "")
    prose = " ".join(b.get("text", "") for b in blocks if b["type"] == "paragraph")
    assert "since [●]" in prose and "since 2020" in prose
    assert any(h["kind"] == "future_date" for b in blocks for h in b.get("masked", []))


# --- a table row whose snippet is the whole row (hosted draft of 22 Nov 2026) ----------------------------------------------
ROW = "Revenue per MT of laminated output (Rs per kg) | 175.5 | 160.55 | 149.74 | 159.02"
PERMT = [{"type": "amount", "label": "Revenue per MT of laminated output", "value": v, "unit": "", "period": p, "snippet": ROW}
         for v, p in (("175.5", "H1 FY27"), ("160.55", "FY 2025-26"), ("149.74", "FY 2024-25"), ("159.02", "FY 2023-24"))]


def test_a_sibling_in_the_same_row_does_not_lend_its_year():
    # the draft swapped two years: 149.74 is FY 2024-25 and 159.02 FY 2023-24; every fact of the row holds the whole row
    t = "Revenue per MT increased from ₹149.74 in FY 2023-24 to ₹159.02 in FY 2024-25 and ₹160.55 in FY 2025-26."
    out, raws = masked(t, PERMT)
    assert raws == ["149.74", "159.02"] and "₹160.55 in FY 2025-26" in out
    ok = "Revenue per MT moved from ₹159.02 in FY 2023-24 to ₹149.74 in FY 2024-25 and ₹160.55 in FY 2025-26."
    assert masked(ok, PERMT) == (ok, [])


def test_a_negative_value_is_matched_by_its_magnitude():
    facts = [{"type": "amount", "label": "Profit after tax", "value": "-0.42", "unit": "₹ lakhs", "period": "FY 2023-24",
              "snippet": "Profit after tax | -0.42 | -0.38"},
             {"type": "percent", "label": "Complaints", "value": "0.42", "unit": "%", "period": "FY 2025-26", "snippet": "complaints 0.42%"}]
    t = "In FY 2023-24 the profit after tax was ₹-0.42 lakhs."
    assert masked(t, facts) == (t, [])


def test_a_six_month_figure_in_the_clause_does_not_make_the_year_figures_half_year():
    # hosted draft of 22 Nov 2026, redraft: 149.74 is FY 2024-25 but the draft put it in FY 2023-24; the clause also ends with a
    # six-month figure, which used to turn every figure of the clause into a half-year one that H1-tagged neighbours supported
    tail = " and was ₹175.5 in the six months ended 30 September 2026."
    bad = "Revenue per MT increased from ₹149.74 in FY 2023-24 to ₹160.55 in FY 2025-26" + tail
    out, raws = masked(bad, PERMT)
    assert raws == ["149.74"] and "₹160.55 in FY 2025-26" in out and "₹175.5 in the six months" in out
    ok = "Revenue per MT increased from ₹159.02 in FY 2023-24 to ₹160.55 in FY 2025-26" + tail
    assert masked(ok, PERMT) == (ok, [])
    half = "Revenue per MT was ₹175.5 in H1 FY27 and ₹160.55 in FY 2025-26."
    assert masked(half, PERMT) == (half, [])


# --- a month taken from another event of the same list (hosted draft of 22 Nov 2026) -----------------------------------------
from verify.claims import mask_event_dates  # noqa: E402

TIMELINE = [{"type": "short_text", "label": "2025", "value": "FSSC 22000 certification; revenue crossed ₹100 crore; activated-carbon "
             "VOC control unit installed (June 2025)", "snippet": "2025 | FSSC 22000 certification; revenue crossed ₹100 crore; "
             "activated-carbon VOC control unit installed (June 2025)"},
            {"type": "short_text", "label": "2014", "value": "Commercial production started in January 2014 with one press",
             "snippet": "2014 | Commercial production started in January 2014 with one press"}]


def test_a_month_that_belongs_to_another_event_of_the_list_is_masked():
    out, hits = mask_event_dates("With FSSC 22000 certification since June 2025 and growth in FY 2025-26.", TIMELINE)
    assert "since [●] and" in out and [h["raw"] for h in hits] == ["June 2025"] and hits[0]["kind"] == "event_date"


def test_the_month_beside_its_own_event_is_kept_however_it_is_worded():
    for t in ["The VOC control unit was commissioned in June 2025.", "Commercial production commenced in January 2014.",
              "Activated-carbon unit installed June 2025 to cut emissions."]:
        assert mask_event_dates(t, TIMELINE) == (t, []), t


def test_a_month_no_source_states_or_a_date_with_a_day_is_left_to_the_other_checks():
    for t in ["Certification since May 2024.", "FSSC 22000 certification since 14 June 2025.", "Since June 2025."]:
        assert mask_event_dates(t, TIMELINE) == (t, []), t


def test_the_guard_masks_a_misplaced_month():
    blocks, *_ = guard_draft("With FSSC 22000 certification since June 2025 we serve brand owners.", "Industry", TIMELINE, {},
                             "Kestrel Limited", "")
    prose = " ".join(b.get("text", "") for b in blocks if b["type"] == "paragraph")
    assert "since [●]" in prose and any(h["kind"] == "event_date" for b in blocks for h in b.get("masked", []))


# --- malformed amounts (hosted draft of 22 Nov 2026, third redraft) ----------------------------------------------------------
from verify.claims import mask_malformed_amounts  # noqa: E402


def test_a_rupee_amount_with_broken_comma_groups_is_masked():
    out, hits = mask_malformed_amounts("borrow up to ₹75,0,0,0,00 (Rupees seventy-five crore).")
    assert out == "borrow up to ₹[●] (Rupees seventy-five crore)." and hits[0]["kind"] == "malformed_amount"


def test_western_and_indian_grouping_and_plain_amounts_pass():
    for t in ["₹75,00,00,000", "Rs 5,00,000 and ₹1,23,45,678.50", "₹1,244 lakhs and ₹616 lakhs", "₹10,000/- per meeting",
              "Rs. 12.00 lakhs per month", "₹160.55 per kg", "INR 1,234,567", "540 million pieces", "inverters 5 years, hours 5,598.72MT"]:
        assert mask_malformed_amounts(t) == (t, []), t


def test_a_rupee_sign_before_a_quantity_is_masked():
    out, hits = mask_malformed_amounts("revised from ₹4800 MT to ₹3984 MT; ₹229 million pieces; ₹312 employees")
    assert out == "revised from ₹[●] MT to ₹[●] MT; ₹[●] million pieces; ₹[●] employees" and len(hits) == 4


def test_a_form_the_inputs_write_themselves_is_left_alone_and_the_guard_applies_the_rule():
    src = [{"type": "amount", "label": "Annual remuneration", "value": "₹25,00,0000/-", "snippet": "₹25,00,0000/- per annum"}]
    assert mask_malformed_amounts("pay of ₹25,00,0000/- a year", src)[1] == []
    blocks, *_ = guard_draft("The Board may borrow up to ₹75,0,0,0,00 in total.", "Industry", src, {}, "Kestrel Limited", "")
    prose = " ".join(b.get("text", "") for b in blocks if b["type"] == "paragraph")
    assert "₹[●]" in prose and any(h["kind"] == "malformed_amount" for b in blocks for h in b.get("masked", []))


# --- several figures, several years (hosted draft of 22 Nov 2026, fourth redraft) ----------------------------------------------
SUPP = [{"type": "percent", "label": "Top 10 suppliers (% of purchases)", "value": v, "unit": "%", "period": p,
         "snippet": "Top 10 suppliers (% of purchases) | 68.81% | 69.52% | 70.86% | 72.40%"}
        for v, p in (("68.81", "H1 FY27"), ("69.52", "FY 2025-26"), ("70.86", "FY 2024-25"), ("72.40", "FY 2023-24"))]
CAPEX = [{"type": "amount", "label": "Funding capital expenditure", "value": v, "unit": "₹ lakhs", "period": p,
          "snippet": "Funding capital expenditure | 1860 | 1244 | 616"} for v, p in (("1244", "FY 2026-27"), ("616", "FY 2027-28"))]
CAPEX.append({"type": "text", "origin": "passage", "label": "note", "value": "In FY 2026-27 and FY 2027-28, our Company funded capital "
              "expenditure through internal accruals of ₹1,244 lakhs and ₹616 lakhs respectively."})


def test_respectively_pairs_each_figure_with_its_own_year():
    ok = "The top ten suppliers accounted for 72.40%, 70.86%, 69.52% and 68.81% of purchases in FY 2023-24, FY 2024-25, FY 2025-26 and H1 FY 2027 respectively."
    assert masked(ok, SUPP) == (ok, [])                      # the last one is a half-year figure and must not be masked
    bad = ok.replace("69.52%", "70.86%")
    assert masked(bad, SUPP)[1] == ["70.86"]


def test_figures_and_years_that_alternate_are_paired_and_a_swap_is_masked():
    ok = "Of this, ₹1244 lakhs were funded during FY 2026-27 and ₹616 lakhs are proposed during FY 2027-28."
    assert masked(ok, CAPEX) == (ok, [])
    assert masked(ok.replace("1244", "616", 1).replace("₹616 lakhs are", "₹1244 lakhs are"), CAPEX)[1] == ["616", "1244"]
    assert masked("In FY 2026-27 and FY 2027-28, funding was ₹616 lakhs and ₹1,244 lakhs respectively.", CAPEX)[1] == ["616", "1,244"]


def test_a_passage_that_says_respectively_does_not_lend_both_years_to_both_figures():
    from verify.claims import pair_in_order
    assert list(pair_in_order("In FY 2026-27 and FY 2027-28: ₹1,244 lakhs and ₹616 lakhs respectively.").values()) == [({2027}, False), ({2028}, False)]
    assert pair_in_order("In FY 2025-26 revenue was ₹5 lakhs and profit ₹2 lakhs; in FY 2024-25 ₹4 lakhs.") == {}


def test_a_half_year_cue_in_the_lead_in_belongs_to_the_figure_after_it():
    # "In H1 FY27, exports accounted for 9.37%": the cue is in the number-free lead-in clause, as the year is
    h1 = [{"type": "percent", "label": "Exports (% of sale of products)", "value": v, "unit": "%", "period": p,
           "snippet": "Exports (% of sale of products) | 9.37% | 9.04%"} for v, p in (("9.37", "H1 FY27"), ("9.04", "FY 2025-26"))]
    ok = "In H1 FY27, exports accounted for approximately 9.37% of our sale of products."
    assert masked(ok, h1) == (ok, [])
    assert masked("In FY 2025-26, exports accounted for approximately 9.37% of our sale of products.", h1)[1] == ["9.37"]
