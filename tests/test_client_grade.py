"""Fixes from the Vidyunmaya data-room test (22 Nov 2026): headings, the fact cap, helper rows, fragments the model copies,
classification, rule-based risk factors, ratio tables."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import docx  # noqa: E402

from draft.builders import Ctx, protect_abbrev  # noqa: E402
from draft.writer import clean_fragments, dedupe_paragraphs, passage_facts, write_section  # noqa: E402
from extract import rules  # noqa: E402
from ingest.classify import classify  # noqa: E402
from ingest.readers import read_file  # noqa: E402


# ---- the reader keeps Word heading styles; the business note is cut at them ----

def _note(tmp_path):
    d = docx.Document()
    from docx.enum.style import WD_STYLE_TYPE
    for name in ("TOC Heading", "toc 1"):
        if name not in [x.name for x in d.styles]:
            d.styles.add_style(name, WD_STYLE_TYPE.PARAGRAPH)
    d.add_paragraph("Contents", style="TOC Heading")
    d.add_paragraph("1.\tOverview\t2", style="toc 1")
    d.add_heading("Overview", level=1)
    d.add_paragraph("The Company is an EPC contractor for substations. " * 8)
    d.add_heading("Strengths", level=1)
    d.add_paragraph("Experienced team and a long record with state utilities. " * 8)
    p = tmp_path / "business_note.docx"
    d.save(p)
    return p


def test_reader_marks_headings_and_contents_lines(tmp_path):
    blocks = read_file(str(_note(tmp_path)))["blocks"]
    assert [b["text"] for b in blocks if b.get("heading")] == ["Overview", "Strengths"]
    assert "Overview" in " ".join(b["text"] for b in blocks if b.get("toc"))
    assert not any(b.get("heading") and b.get("toc") for b in blocks)


def test_note_sections_follow_word_headings_not_numbers(tmp_path):
    blocks = read_file(str(_note(tmp_path)))["blocks"]
    note = {"id": "f1", "name": "business_note.docx", "doc_type": "business_note", "status": "processed"}
    ctx = Ctx(project={"name": "T", "offer": {}}, facts=[], files=[note], tables=[], blocks={"f1": blocks})
    assert [h for h, _ in ctx.note_sections()] == ["Overview", "Strengths"]


# ---- the fact cap, helper rows ----

def test_a_file_past_the_cap_reports_what_it_dropped(monkeypatch):
    monkeypatch.setattr(rules, "MAX_FACTS_PER_FILE", 5)
    blocks = [{"kind": "row", "loc": f"S!{i}", "text": f"Item {i} label | {i + 100}", "sheet": "S", "page": None} for i in range(12)]
    facts, dropped = rules.extract_facts_ex(blocks)
    assert len(facts) == 5 and dropped == 7


def test_spreadsheet_check_rows_and_check_sheets_are_not_facts():
    rows = [{"kind": "row", "loc": "PL!1", "text": "Revenue from operations | 100 | 200", "sheet": "PL", "page": None},
            {"kind": "row", "loc": "PL!2", "text": "Check: revenue - as reported | 0 | 0", "sheet": "PL", "page": None},
            {"kind": "row", "loc": "Checks!3", "text": "Total of all checks | 0", "sheet": "Checks", "page": None}]
    labels = [f["label"] for f in rules.extract_facts(rows)]
    assert any("Revenue" in x for x in labels)
    assert not any("heck" in x for x in labels)


# ---- what the model copies besides prose ----

def _p(t):
    return {"type": "paragraph", "text": t, "facts": []}


def test_clean_fragments_drops_section_numbers_captions_and_dumps():
    dump = "Table 2: Power supply Indicator FY16 FY18 " + " ".join(f"{i},{100 + i}" for i in range(20))
    out = clean_fragments([_p("India's demand has grown over the past decade."), _p("3.2 Electricity demand"),
                           _p("Chart 1: Real GDP growth (%)"), _p("Source: IMF update"), _p(dump),
                           _p("No. of Equity Shares % of Capital No. of Equity Shares % of Capital"),
                           _p("Check: net working capital - certificate | 0 | 0 | 0")])
    assert [b["text"] for b in out] == ["India's demand has grown over the past decade."]


def test_clean_fragments_strips_report_reference_marks_and_keeps_a_table_source():
    out = clean_fragments([_p("Peak demand reached a record in May 2026[5]."),
                           {"type": "table", "rows": [["a", "b"]], "text": ""}, _p("Source: Ministry of Power")])
    assert out[0]["text"] == "Peak demand reached a record in May 2026."
    assert out[-1]["text"] == "Source: Ministry of Power"


def test_clean_fragments_drops_a_title_copied_as_a_paragraph():
    out = clean_fragments([_p("Power Sector at a Glance ALL INDIA [4]."), _p("Short statements such as None are kept."),
                           _p("Not applicable."), _p("Mr. Aditya Jangid")])      # a name or a heading without a reference mark stays
    assert [b["text"] for b in out] == ["Short statements such as None are kept.", "Not applicable.", "Mr. Aditya Jangid"]


def test_a_paragraph_repeated_in_a_section_is_kept_once():
    t = "India's electricity demand has grown steadily over the past decade, supported by economic expansion."
    assert len(dedupe_paragraphs([_p(t), _p("Other."), _p(t.upper())])) == 2


# ---- sub-headings the files do speak to are written; the ones they do not stay missing ----

def _ctx_with_note(tmp_path, extra_blocks=()):
    blocks = read_file(str(_note(tmp_path)))["blocks"] + list(extra_blocks)
    note = {"id": "f1", "name": "business_note.docx", "doc_type": "business_note", "status": "processed"}
    return Ctx(project={"name": "T", "offer": {}}, facts=[], files=[note], tables=[], blocks={"f1": blocks})


def test_a_structural_heading_is_supported_by_its_synonym(tmp_path):
    hist = [{"kind": "text", "loc": "p9", "text": "The Company was incorporated on 6 May 2011 and converted to a public company in 2026."}]
    ctx = _ctx_with_note(tmp_path, hist)
    sec = {"key": "history", "query": "company incorporated converted public", "needs": ["business_note"]}
    _, supported = passage_facts(ctx, "Brief History", sec)
    assert supported


def test_a_sub_heading_with_no_matching_content_is_marked_missing_not_listed_with_facts(tmp_path):
    ctx = _ctx_with_note(tmp_path)
    called = []

    def model(messages, frequency_penalty=0.0):
        called.append(messages[-1]["content"])
        return "Prose.", {}

    out = write_section("history", ctx, model)
    missing = [b for b in out["blocks"] if b["type"] == "brief" and b.get("missing")]
    assert missing and all(not b["items"] for b in missing)
    assert "Changes in Registered Office" in [b["sub"] for b in missing]


# ---- classification ----

def test_files_the_data_room_named_are_classified_by_name():
    assert classify("12_Order_Book_Certificate.pdf")["doc_type"] == "order_book"
    assert classify("07_Work_Completion_Certificates.pdf")["doc_type"] == "work_completion"
    assert classify("03_Project_Execution_Flow_Chart.png", "borrowings outstanding")["doc_type"] == "process_flow"
    assert classify("05_BOCW_Registration.jpg", "building and other construction holding")["doc_type"] == "licence"


def test_a_short_keyword_matches_a_word_not_a_part_of_one():
    assert classify("scan.jpg", "the building holding company")["doc_type"] == "other"
    assert classify("profiles.docx", "Director DIN 01234567")["doc_type"] == "people_profiles"


# ---- sentences are not cut at abbreviations ----

def test_abbreviations_do_not_end_a_sentence():
    s = protect_abbrev("As certified by S R Pande & Co. (certificate ref. SRP/VIL/26-27/C-05 dated 19 October 2026), the Company has deployed it.")
    assert "Co. (" not in s and "ref. S" not in s


# ---- ratio tables ----

def test_ratio_table_drops_the_restated_copy_and_the_difference_columns():
    import re
    from draft.builders import RATIO_DROP, last_period_col
    from extract.tables import Table
    header = ["Ratio", "FY24", "FY25", "H1 FY27", "", "RFI FY24", "RFI FY25", "Diff. FY24", "Definition"]
    kept = [h for h in header if h and not re.search(RATIO_DROP, h.strip(), re.I)]
    assert kept == ["Ratio", "FY24", "FY25", "H1 FY27", "Definition"]
    t = Table.__new__(Table)
    t.header = header
    assert header[last_period_col(t)] == "H1 FY27"      # RFI and Diff columns are not periods


# ---- rule-based risk factors ----

def test_customer_risk_does_not_read_an_amount_column_as_a_percentage():
    from draft.red_flags import rule_customers
    from extract.tables import Table

    t = Table.__new__(Table)
    t.header, t.rows = ["Customer", "FY 2025-26 (₹ lakhs)", "H1 FY27 ₹ lakhs"], [["Client A", "900.00", "952.06"]]
    t.file_id, t.file_name, t.loc, t.row_locs, t.caption = "f", "ops.xlsx", "S", ["S!2"], "customers"
    ctx = Ctx(project={"name": "T", "offer": {}}, facts=[], files=[], tables=[t], blocks={})
    import draft.red_flags as rf
    orig = rf.find
    rf.find = lambda tables, *a, **k: t
    try:
        out = rule_customers(ctx)
    finally:
        rf.find = orig
    assert not out or "952.06%" not in out[0]["body"]


def test_lender_risk_reads_sentences_not_loan_rows():
    from draft.red_flags import rule_lender
    rows = [{"kind": "row", "loc": "B!2", "sheet": "B",
             "text": "Pranavati Bank Limited | Term loan II | Secured | 600 | 324 | 54.00% | consent of the bank pending"}]
    f = {"id": "f1", "name": "borrowings.xlsx", "doc_type": "borrowings", "status": "processed"}
    ctx = Ctx(project={"name": "T", "offer": {}}, facts=[], files=[f], tables=[], blocks={"f1": rows})
    assert rule_lender(ctx) == []


# ---- a table the model wrote as a run of words, and pipe lines without leading bars ----

def test_a_run_of_words_with_period_headers_is_read_back_as_a_table():
    from draft.writer import parse_markdown
    t = ("FY 2023-24 FY 2024-25 FY 2025-26 H1 FY 2026-27 Tenders / enquiries bid (number) 58 66 79 37 "
         "Value of bids submitted (₹ lakhs) 41,600.00 52,300.00 63,900.00 29,800.00 Orders won (number) 21 25 [●] 12")
    (blk,) = parse_markdown(t)
    assert blk["type"] == "table"
    assert blk["rows"][0] == ["", "FY 2023-24", "FY 2024-25", "FY 2025-26", "H1 FY 2026-27"]
    assert blk["rows"][2][0] == "Value of bids submitted (₹ lakhs)" and blk["rows"][3][3] == "[●]"


def test_a_sentence_that_mentions_two_years_stays_a_paragraph():
    from draft.writer import parse_markdown
    (blk,) = parse_markdown("Revenue grew in FY 2024-25 and FY 2025-26 because of more solar work, which rose 40 per cent.")
    assert blk["type"] == "paragraph"


def test_lines_with_pipes_but_no_leading_bar_are_a_table():
    from draft.writer import parse_markdown
    (blk,) = parse_markdown("Certification | Body | Valid till\nISO 9001:2015 | Assurex | 22 May 2027\nISO 14001:2015 | Assurex | 22 May 2027")
    assert blk["type"] == "table" and blk["rows"][1] == ["ISO 9001:2015", "Assurex", "22 May 2027"]


# ---- sub-headings about an event need a source that states one ----

def test_changes_in_registered_office_needs_a_stated_change(tmp_path):
    lease = [{"kind": "text", "loc": "p1", "text": "The registered office is at Ramdaspeth, Nagpur, under a leave and licence of 60 months."}]
    ctx = _ctx_with_note(tmp_path, lease)
    sec = {"key": "history", "query": "registered office", "needs": ["business_note"]}
    _, supported = passage_facts(ctx, "Changes in Registered Office", sec)
    assert not supported
    moved = [{"kind": "text", "loc": "p2", "text": "The registered office was shifted from Pune to Nagpur by a special resolution in 2019."}]
    _, supported = passage_facts(_ctx_with_note(tmp_path, moved), "Changes in Registered Office", sec)
    assert supported


def test_litigation_heading_is_supported_by_a_passage_about_litigation(tmp_path):
    lit = [{"kind": "text", "loc": "p3", "text": "Outstanding litigation: one criminal complaint by the Company is pending before the Magistrate."}]
    ctx = _ctx_with_note(tmp_path, lit)
    sec = {"key": "litigation", "query": "litigation proceedings", "needs": ["business_note"]}
    _, supported = passage_facts(ctx, "Outstanding Litigation and Material Developments", sec)
    assert supported


def test_rows_run_together_with_the_text_after_them_become_a_table_and_a_paragraph():
    from draft.writer import parse_markdown
    t = ("FY 2023-24 FY 2024-25 FY 2025-26 H1 FY 2026-27 Tenders bid (number) 58 66 79 37 Value of bids (₹ lakhs) 41,600.00 52,300.00 63,900.00 29,800.00 "
         "EMD and bank guarantee cycle A utility contract typically requires a bid security.")
    blocks = parse_markdown(t)
    assert [b["type"] for b in blocks] == ["table", "paragraph"]
    assert len(blocks[0]["rows"]) == 3 and blocks[1]["text"].startswith("EMD and bank guarantee cycle")


def test_a_one_line_header_and_the_rows_that_follow_in_a_paragraph_become_one_table():
    from draft.writer import parse_markdown
    t = ("₹ lakhs | FY 2023-24 | FY 2024-25\n\nSubstations 2,622.05 3,097.23 Distribution network strengthening (HT/LT) 2,848.56 3,412.06 "
         "Revenue from operations 7,215.60 8,962.40")
    (tbl,) = parse_markdown(t)
    assert tbl["type"] == "table" and tbl["rows"][0] == ["₹ lakhs", "FY 2023-24", "FY 2024-25"] and len(tbl["rows"]) == 4


def test_a_check_column_is_not_a_fact():
    rows = [{"kind": "row", "loc": "S!1", "sheet": "S", "page": None, "text": "Object | Estimated amount | Check (amount - deployment)"},
            {"kind": "row", "loc": "S!2", "sheet": "S", "page": None, "text": "Working capital | 2450 | 0"}]
    labels = [f["label"] for f in rules.extract_facts(rows)]
    assert any("Estimated amount" in x for x in labels) and not any("Check" in x for x in labels)


def test_a_shops_act_row_that_mentions_a_change_of_name_is_not_a_change_of_registered_office(tmp_path):
    row = [{"kind": "text", "loc": "p5", "text": "Registration under the Shops and Establishments Act - registered office; obtained; change of name intimated 20 July 2026."}]
    ctx = _ctx_with_note(tmp_path, row)
    sec = {"key": "history", "query": "registered office", "needs": ["business_note"]}
    _, supported = passage_facts(ctx, "Changes in Registered Office", sec)
    assert not supported


def test_a_letterhead_copied_from_a_certificate_is_not_prose():
    head = ("SYNTHETIC TEST DOCUMENT S R PANDE & CO. Chartered Accountants 501, Shriram Towers, Kingsway, Nagpur - 440 001 "
            "Tel: +91 712 663 4410 | Email: audit@example.test | FRN: 124518W | Peer Review Certificate No. 015842")
    out = clean_fragments([_p(head), _p("As certified by S R Pande & Co. (UDIN 26138462BKUPJX4417), the Company has deployed the amounts.")])
    assert [b["text"][:12] for b in out] == ["As certified"]


def test_new_document_types_are_recognised():
    assert classify("09_Shareholders_Agreement_and_Waiver.pdf")["doc_type"] == "shareholder_agreement"
    assert classify("12_Channel_and_Category_Revenue_Certificate.pdf")["doc_type"] == "revenue_certificate"
    assert classify("07_Distribution_and_CF_Agreements_Specimen.pdf")["doc_type"] == "material_agreement"
    assert classify("07_Deed_of_Assignment_of_Trade_Marks.pdf")["doc_type"] == "trademark_deed"


def test_a_count_row_in_a_percentage_column_is_not_a_percentage():
    from draft.builders import table_block
    from extract.tables import Table
    t = Table.__new__(Table)
    t.header, t.caption, t.file_id, t.file_name, t.loc = ["Metric", "% FY24", "% FY25"], "", "f", "o.xlsx", "S"
    t.rows, t.row_locs = [["Top client share", "21.40", "19.85"], ["Number of customers billed", "291", "322"]], []
    t.source = lambda: {"file_name": "o.xlsx", "loc": "S"}
    blk = table_block(t)
    assert blk["rows"][2][1:] == ["291", "322"] and blk["rows"][1][1].endswith("%")


def test_a_section_with_only_its_own_title_is_written_when_a_passage_exists(tmp_path):
    ctx = _ctx_with_note(tmp_path)
    sec = {"key": "industry", "title": "Industry Overview", "query": "contractor substations", "needs": ["business_note"], "subheads": []}
    _, supported = passage_facts(ctx, "Industry Overview", sec)
    assert supported


# ---- the unit of a rupee amount ----

def _facts_in_lakhs():
    rows = [{"label": "Madhya Pradesh", "value": "3,615.36 (45.6)", "snippet": "Madhya Pradesh | 3,241.22 (47.8) | 3,615.36 (45.6) | 4,012.19 (43.2)", "type": "short_text"}]
    rows += [{"label": f"Item {i}", "value": f"{100 + i}.00", "snippet": f"Revenue of ₹ {100 + i}.00 lakhs in FY 2025-26", "type": "amount"} for i in range(12)]
    rows += [{"label": "E-commerce", "value": "484.34", "snippet": "sold ₹ 484.34 million through platforms", "type": "amount"}]
    return rows


def test_a_unit_the_inputs_do_not_give_is_masked():
    from verify.claims import mask_unit_claims
    text, hits = mask_unit_claims("Madhya Pradesh: ₹4,012.19 million (43.2% of sales) in FY 2025-26.", _facts_in_lakhs())
    assert "[●]" in text and hits and hits[0]["kind"] == "unit_mismatch"


def test_a_unit_the_inputs_give_is_kept():
    from verify.claims import mask_unit_claims
    facts = _facts_in_lakhs()
    for t in ("Revenue was ₹ 101.00 lakhs in FY 2025-26.", "E-commerce sold ₹484.34 million through platforms.", "A figure nobody holds: ₹ 99,999 crore."):
        assert mask_unit_claims(t, facts)[1] == []


def test_templated_run_is_cut():
    """A model draft whose lines all open with the same six words (47 'The industry is also responding to ...' paragraphs) is cut."""
    from draft.writer import cut_templated_run
    head = "The industry is fragmented, with a few national brands and a long tail of regional players."
    body = "\n\n".join(f"The industry is also responding to topic{i} pressures by doing thing {i}." for i in range(12))
    out, cut = cut_templated_run(head + "\n\n" + body)
    assert cut and out.count("also responding") == 2 and out.startswith(head)


def test_templated_run_keeps_openings_the_inputs_use():
    from draft.writer import cut_templated_run
    lines = "\n\n".join(f"The Company has entered into an agreement with party{i} for supply of goods." for i in range(8))
    assert cut_templated_run(lines, "The Company has entered into an agreement with")[1] is False
    assert cut_templated_run("short one.\n\nAnother line here.")[1] is False


def test_templated_run_is_counted_as_a_loop():
    from draft.writer import guard_draft
    raw = "\n\n".join(f"The industry is also responding to topic{i} pressures by doing thing {i}." for i in range(12))
    blocks, _, looped, _ = guard_draft(raw, "Industry", [], {}, "Rasoiyana Foods Limited", "")
    assert looped and len([b for b in blocks if b["type"] == "paragraph"]) <= 2
