"""The 19 Nov 2026 invented-figure fixes (docs/INVENTED_FIGURES_FIX_PLAN.md, phase 1)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from draft.derive import computed_shares, derive_facts  # noqa: E402
from draft.slots import unknown_facts  # noqa: E402
from verify.checks import mask_ungrounded, misplaced_cells  # noqa: E402
from verify.places import mask_unknown_places  # noqa: E402


# ---- 1.1 explicit unknowns ----

def test_a_missing_address_becomes_an_explicit_placeholder_fact():
    out = unknown_facts("Our Properties", "Our Business", [{"type": "amount", "label": "Plot number", "value": ""}])
    assert [f["label"] for f in out] == ["registered office address"] and out[0]["value"] == "[●]"


def test_an_address_the_files_give_is_not_replaced():
    facts = [{"type": "short_text", "label": "Registered office address", "value": "Plot 5, MIDC, Nagpur"}]
    assert unknown_facts("Changes in our Registered Office", "Our History", facts) == []


def test_a_passage_that_names_the_address_counts_as_supplying_it():
    facts = [{"type": "text", "label": "note", "value": "Our registered office address is at Nagpur."}]
    assert unknown_facts("Our Properties", "Our Business", facts) == []


def test_contact_sub_headings_ask_for_phone_email_and_website_only_when_missing():
    out = unknown_facts("Contact details of the Company Secretary", "General", [{"type": "short_text", "label": "e-mail", "value": "cs@x.in"}])
    assert [f["label"] for f in out] == ["telephone number", "website"]


def test_an_unrelated_sub_heading_gets_no_unknown_facts():
    assert unknown_facts("Competitive Strengths", "Our Business", []) == []


# ---- 1.2 computed and unknown ratios ----

LINES = [{"type": "amount", "label": "Fees to the BRLM", "value": "288.34", "unit": "₹ Lakhs"},
         {"type": "amount", "label": "Fees to the Registrar", "value": "2.65", "unit": "₹ Lakhs"},
         {"type": "amount", "label": "Advertising", "value": "100.00", "unit": "₹ Lakhs"},
         {"type": "amount", "label": "Total estimated expenses", "value": "391", "unit": "₹ Lakhs"}]


def test_shares_are_computed_only_when_the_lines_add_up_to_the_total():
    out = computed_shares(LINES)
    assert {c["label"].split(" as % of")[0]: c["value"] for c in out}["Fees to the BRLM"] == "73.74"
    assert all(c["formula"] for c in out)
    off = [dict(f) for f in LINES]
    off[3]["value"] = "900"                              # the lines do not sum to this total: nothing is computed
    assert computed_shares(off) == []


def test_ratios_to_the_offer_size_are_unknown_at_drhp_stage():
    out = derive_facts([], "Offer related expenses", "Objects of the Offer")
    labels = {f["label"]: f["value"] for f in out}
    assert labels["offer expenses as % of gross proceeds"] == "[●]" and labels["gross proceeds of the Offer"] == "[●]"


def test_a_ratio_the_files_do_give_is_not_replaced_by_a_placeholder():
    facts = [{"type": "percent", "label": "Offer expenses as % of gross proceeds", "value": "7.89"}]
    out = derive_facts(facts, "Offer related expenses", "Objects of the Offer")
    assert "offer expenses as % of gross proceeds" not in {f["label"] for f in out}


def test_computed_facts_are_grounded_for_the_verifier():
    facts = [dict(f, id=f"x{i}") for i, f in enumerate(derive_facts(LINES, "x", "x"))]
    text, hits = mask_ungrounded("The BRLM fee is 73.74% of the total.", LINES + facts, {}, "")
    assert "73.74" in text and not hits


# ---- 1.4 a real number on the wrong row ----

F = [{"label": "Total estimated offer expenses", "value": "912.07", "type": "amount"},
     {"label": "Fees payable to the BRLM (inclusive underwriting commission)", "value": "288.34", "type": "amount"}]


def test_a_total_written_against_a_specific_row_is_flagged():
    assert misplaced_cells(["Fees payable to the Registrar to the Offer", "912.07", "100%"], F) == [1]


def test_a_number_on_its_own_row_and_a_total_row_pass():
    assert misplaced_cells(["Fees payable to the BRLM", "288.34"], F) == []
    assert misplaced_cells(["Total", "912.07"], F) == []


def test_a_number_that_is_in_no_input_is_not_this_checks_business():
    assert misplaced_cells(["Advertising", "128.56"], F) == []


# ---- 1.5 places ----

def test_a_city_the_files_never_mention_is_masked_and_one_they_do_is_kept():
    text = "Our registered office is at Plot 3, Pune. Our unit is in Nagpur."
    out, hits = mask_unknown_places(text, "ourunitisinnagpur", "")
    assert "Pune" not in out and "Nagpur" in out and [h["raw"] for h in hits] == ["Pune"]


def test_a_regulators_own_city_is_allowed():
    out, hits = mask_unknown_places("BSE Limited, Phiroze Jeejeebhoy Towers, Dalal Street, Mumbai.", "", "")
    assert "Mumbai" in out and not hits


def test_the_company_name_can_ground_a_place():
    out, hits = mask_unknown_places("The unit at Surat.", "", "Surat Textiles Limited Overview")
    assert "Surat" in out and not hits


# ---- the verifier's own gaps found by the same trace ----

def test_a_page_reference_inside_bars_is_masked():
    out, _ = mask_ungrounded("beginning on page no. |55| of this DRHP.", [], {}, "")
    assert "55" not in out and "[●]" in out


def test_a_percentage_needs_a_percentage_in_the_inputs():
    facts = [{"type": "date", "label": "d", "value": "22 March 2024"}]       # a 22 that is not a percentage
    out, _ = mask_ungrounded("Expenses are 22% of the Issue Size.", facts, {}, "")
    assert "22%" not in out
    out, _ = mask_ungrounded("Expenses are 22% of the Issue Size.", [{"type": "percent", "label": "x", "value": "22"}], {}, "")
    assert "22%" in out


def test_a_head_count_and_a_distance_are_checked():
    out, _ = mask_ungrounded("We have 48 (i.e., about 9%) of our employees on contract.", [], {}, "")
    assert "48" not in out
    out, _ = mask_ungrounded("within a radius of 50 Kms from any unit.", [], {}, "")
    assert "50" not in out


# ---- parsing and layout ----

def test_a_bullet_ending_in_a_date_is_not_split_into_table_cells():
    from draft.writer import parse_markdown
    text = "• Resumption of directorship from December 17, 2025\n\n• End of directorship from April 09, 2026"
    blocks = parse_markdown(text)
    assert [b["type"] for b in blocks] == ["paragraph", "paragraph"] and "December 17, 2025" in blocks[0]["text"]


def test_a_short_line_repeated_without_end_is_cut():
    from draft.writer import collapse_runs
    text = "Total\n\n" + "\n\n".join(["Rs."] * 30)
    out, cut = collapse_runs(text)
    assert cut and out.count("Rs.") == 3


def test_dates_split_by_table_bars_are_joined_before_checking():
    from draft.writer import guard_draft
    facts = [{"type": "date", "label": "d", "value": "December 17, 2025"}]
    blocks, n, _, _ = guard_draft("From December | 17, | 2025 he served.", "Management", facts, {}, "Co", "")
    assert n == 0 and "December 17, 2025" in blocks[0]["text"]


def test_precedent_figures_and_identifiers_can_be_scrubbed():
    from data.prompts import drafting_messages, scrub_precedent
    assert "20070074174" not in scrub_precedent("Driving License No: MH01 20070074174 and Rs. 912.07 Lakhs")
    msgs = drafting_messages("Co", "Sec", ["A"], "A", [], precedent="Licence 20070074174 for 2 Directors", scrub=True)
    assert "20070074174" not in msgs[1]["content"] and "2 Directors" in msgs[1]["content"]
    keep = drafting_messages("Co", "Sec", ["A"], "A", [], precedent="Licence 20070074174")
    assert "20070074174" in keep[1]["content"]              # the training format is unchanged


# ---- 1.3 best of n, and the new facts reach the model ----

def _ctx():
    from draft.builders import Ctx
    note = {"id": "f1", "name": "note.docx", "doc_type": "business_note", "format": "docx", "status": "processed"}
    blocks = [{"kind": "text", "loc": "p1", "text": "1. Overview"},
              {"kind": "text", "loc": "p2", "text": " ".join(["We are an electrical EPC contractor in Nagpur."] * 8)}]
    return Ctx(project={"name": "T", "offer": {}}, facts=[], files=[note], tables=[], blocks={"f1": blocks})


def test_best_of_n_keeps_the_draft_with_the_fewest_masked_values():
    from draft.writer import write_section
    calls = []

    def model(messages, frequency_penalty=0.0, n=1, temperature=None):
        calls.append(n)
        return ["We are an EPC contractor with 4,812 staff in Surat.",
                "We are an electrical EPC contractor in Nagpur.",
                "We are an EPC contractor with 99,999 staff."], {}
    model.supports_n = True
    out = write_section("business", _ctx(), model)
    assert calls == [3]
    text = " ".join(b.get("text", "") for b in out["blocks"])
    assert "Nagpur" in text and "4,812" not in text and "99,999" not in text


def test_a_client_without_n_support_still_writes_one_draft():
    from draft.writer import write_section
    calls = []

    def model(messages, frequency_penalty=0.0):
        calls.append(1)
        return "We are an electrical EPC contractor in Nagpur.", {}
    write_section("business", _ctx(), model)
    assert calls == [1]


def test_unknown_and_computed_facts_are_in_the_prompt(monkeypatch):
    import draft.writer as w
    monkeypatch.setattr(w, "unknown_facts", lambda sub, title, facts: [{"id": "u0", "type": "short_text", "label": "registered office address", "value": "[●]"}])
    seen = []

    def model(messages, frequency_penalty=0.0):
        seen.append(messages[-1]["content"])
        return "We are an electrical EPC contractor in Nagpur.", {}
    w.write_section("business", _ctx(), model)
    assert seen and '"label":"registered office address","value":"[●]"' in seen[0]


def test_make_chat_asks_the_server_for_n_samples(monkeypatch):
    from serve import llm
    sent = []

    class R:
        def raise_for_status(self):
            pass

        def json(self):
            return {"choices": [{"message": {"content": "a"}}, {"message": {"content": "b"}}], "usage": {}}

    monkeypatch.setattr(llm.httpx, "post", lambda url, json=None, **kw: (sent.append(json), R())[1])
    chat = llm.make_chat({"model_url": "http://x/v1", "model_name": "m", "temperature": 0.2})
    texts, _ = chat([{"role": "user", "content": "x"}], frequency_penalty=0.3, n=2, temperature=0.3)
    assert texts == ["a", "b"] and sent[0]["n"] == 2 and sent[0]["temperature"] == 0.3 and chat.supports_n


def test_a_server_that_refuses_n_still_gets_one_draft():
    from draft.writer import write_section
    from serve.llm import ModelError
    calls = []

    def model(messages, frequency_penalty=0.0, n=1, temperature=None):
        calls.append(n)
        if n > 1:
            raise ModelError("n not supported")
        return "We are an electrical EPC contractor in Nagpur.", {}
    model.supports_n = True
    out = write_section("business", _ctx(), model)
    assert calls == [3, 1] and "Nagpur" in " ".join(b.get("text", "") for b in out["blocks"])


def test_best_of_n_prefers_a_draft_that_does_not_loop_then_the_one_using_more_facts(monkeypatch):
    import draft.writer as w
    facts = [{"id": "a", "type": "short_text", "label": "city", "value": "Nagpur"},
             {"id": "b", "type": "short_text", "label": "kind", "value": "EPC contractor"}]
    ctx = _ctx()
    ctx.facts = facts
    monkeypatch.setattr(w, "route", lambda *a, **k: facts)

    def model(messages, frequency_penalty=0.0, n=1, temperature=None):
        loop = "We work in Nagpur. " + " ".join(["We build substations for utilities and electric boards."] * 9)
        return [loop, "We are an EPC contractor.", "We are an EPC contractor in Nagpur."], {}
    model.supports_n = True
    out = w.write_section("business", ctx, model)
    text = " ".join(b.get("text", "") for b in out["blocks"])
    assert "EPC contractor in Nagpur" in text and "substations" not in text


def test_a_slash_separated_reference_number_must_be_in_the_inputs():
    out, _ = mask_ungrounded("vide S.O No. S.O.(SEBI)-34/97/98-III of the Board.", [], {}, "")
    assert "34/97/98" not in out
    out, _ = mask_ungrounded("Dated 31/03/2024 as stated.", [{"type": "date", "label": "d", "value": "31/03/2024"}], {}, "")
    assert "31/03/2024" in out
