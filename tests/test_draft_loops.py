"""Repetition loops in model drafts: the app cuts a loop, sends the drafting penalty, and reports the cut."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from data.prompts import trim_repeats  # noqa: E402
from serve import llm  # noqa: E402

LOOP = "The Company has a manufacturing unit at Sanand and sells flexible packaging to FMCG customers."


def test_trim_cuts_a_sentence_that_loops_and_keeps_one_copy():
    text = "Our Company was incorporated in 2010. " + " ".join([LOOP] * 40)
    out, cut = trim_repeats(text)
    assert cut is True
    assert out.count(LOOP) == 1
    assert out.startswith("Our Company was incorporated in 2010.")


def test_trim_leaves_a_sentence_repeated_twice_alone():
    text = f"{LOOP} The details are as set out below. {LOOP}"
    assert trim_repeats(text) == (text.strip(), False)


def test_make_chat_sends_frequency_penalty_only_when_given(monkeypatch):
    sent = []

    class Resp:
        def raise_for_status(self):
            pass

        def json(self):
            return {"choices": [{"message": {"content": "ok"}}]}

    def fake_post(url, json, headers, timeout):
        sent.append(json)
        return Resp()

    monkeypatch.setattr(llm.httpx, "post", fake_post)
    chat = llm.make_chat({"model_url": "http://127.0.0.1:8011/v1", "model_name": "sme-drhp-7b"})
    chat([{"role": "user", "content": "x"}], frequency_penalty=0.3)
    chat([{"role": "user", "content": "x"}])
    assert sent[0]["frequency_penalty"] == 0.3
    assert "frequency_penalty" not in sent[1]


def test_a_sentence_split_by_a_blank_line_is_one_paragraph_and_its_date_is_masked():
    from draft.writer import parse_markdown
    from verify.checks import mask_ungrounded

    text = "The registration is dated October 31,\n\n2017 issued by the Directorate.\n\nNext paragraph here."
    blocks = parse_markdown(text)
    assert [b["text"] for b in blocks] == ["The registration is dated October 31, 2017 issued by the Directorate.",
                                           "Next paragraph here."]
    masked, hits = mask_ungrounded(blocks[0]["text"], [], {}, "Test Company")
    assert "October 31, 2017" not in masked and hits and hits[0]["kind"] == "date"


def test_a_page_reference_split_by_a_blank_line_is_masked():
    from draft.writer import parse_markdown
    from verify.checks import mask_ungrounded

    text = "Details are in the chapter beginning on page no.\n\n99. Deployment Schedule follows."
    blocks = parse_markdown(text)
    assert len(blocks) == 1 and blocks[0]["text"].startswith("Details are in the chapter beginning on page no. 99.")
    masked, hits = mask_ungrounded(blocks[0]["text"], [], {}, "Test Company")
    assert "page no. 99" not in masked and "page no. [●]" in masked and hits


def test_plain_text_rows_with_a_blank_line_between_them_become_a_table():
    from draft.writer import parse_markdown

    text = ("1. Purchase and installation of plant and machinery 1,244.00 616.00 1,860.00\n\n"
            "2. Installation of a 1.20 MWp rooftop solar power plant - - 520.00\n\n"
            "Total - - 4,230.00")
    blocks = parse_markdown(text)
    assert blocks[0]["type"] == "table"
    assert blocks[0]["rows"][0] == ["1. Purchase and installation of plant and machinery", "1,244.00", "616.00", "1,860.00"]
    assert blocks[0]["rows"][1][1:] == ["-", "-", "520.00"]
    assert len(blocks) == 1 and len(blocks[0]["rows"]) == 3          # the total line is a row of the same table
    assert blocks[0]["rows"][2] == ["Total", "-", "-", "4,230.00"]


def test_a_sentence_ending_in_a_year_is_not_a_table():
    from draft.writer import parse_markdown

    text = "The Company was formed under the law in force as of 2010\n\nIt was registered again in 2012"
    assert [b["type"] for b in parse_markdown(text)] == ["paragraph", "paragraph"]


def test_write_section_trims_a_looping_draft_and_reports_it():
    from draft.builders import Ctx
    from draft.writer import DRAFT_FREQUENCY_PENALTY, write_section

    note = {"id": "f1", "name": "note.docx", "doc_type": "business_note", "format": "docx", "status": "processed"}
    ctx = Ctx(project={"name": "T", "offer": {}}, facts=[], files=[note], tables=[],
              blocks={"f1": [{"kind": "text", "loc": "p. 1", "text": "The offer document describes our business and the offer."}]})
    seen = []

    def looping_model(messages, frequency_penalty=0.0):
        seen.append(frequency_penalty)
        return "Our Company was incorporated in 2010. " + " ".join([LOOP] * 60), {}

    out = write_section("summary", ctx, looping_model)
    assert seen and all(p == DRAFT_FREQUENCY_PENALTY for p in seen)
    assert out["loop_trimmed"], "a looping sub-heading must be reported"
    # the summary has three sub-headings, each drafted from the same looping reply: one copy per paragraph
    assert max(b["text"].count(LOOP) for b in out["blocks"] if b.get("text")) == 1


def test_a_deployment_row_that_does_not_add_up_is_masked_not_stated():
    from draft.writer import _row_mismatch
    assert _row_mismatch(["Plant", "1,244.00", "616.00", "1,860.00"]) is False
    assert _row_mismatch(["Total", "1,244.00", "2586.00", "4,230.00"]) is True
    assert _row_mismatch(["Solar", "-", "-", "520.00"]) is True
    assert _row_mismatch(["Total", "[●]", "2586.00", "4,230.00"]) is False


def test_a_sub_heading_the_files_do_not_speak_to_is_not_written_by_the_model():
    from draft.builders import Ctx
    from draft.writer import write_section

    note = {"id": "f1", "name": "note.docx", "doc_type": "business_note", "format": "docx", "status": "processed"}
    ctx = Ctx(project={"name": "T", "offer": {}}, facts=[], files=[note], tables=[],
              blocks={"f1": [{"kind": "text", "loc": "p. 1", "text": "Business overview: we build substations and lay distribution lines for utilities."}]})
    called = []

    def model(messages, frequency_penalty=0.0):
        called.append(messages[-1]["content"])
        return "Invented prose.", {}

    out = write_section("business", ctx, model)
    assert not any("SUB-HEADING: Manufacturing Process" in c for c in called)           # nothing in the files about it
    assert "Manufacturing Process" in out["narrative_pending"]             # left as a brief for the reviewer
    assert any("we build substations" in c for c in called)                # the issuer's own passage reached the model


def test_our_business_uses_the_issuers_own_note_headings_and_nothing_static():
    from draft.builders import Ctx
    from draft.writer import write_section

    note = {"id": "f1", "name": "note.docx", "doc_type": "business_note", "format": "docx", "status": "processed"}
    blocks = [{"kind": "text", "loc": "para 1", "text": "1. Overview"},
              {"kind": "text", "loc": "para 2", "text": " ".join(["We are an electrical EPC contractor for substations."] * 8)},
              {"kind": "text", "loc": "para 3", "text": "2. Order book"},
              {"kind": "text", "loc": "para 4", "text": " ".join(["The order book is spread over several states."] * 8)}]
    ctx = Ctx(project={"name": "T", "offer": {}}, facts=[], files=[note], tables=[], blocks={"f1": blocks})
    asked = []

    def model(messages, frequency_penalty=0.0):
        asked.append(next(l for l in messages[-1]["content"].split("\n") if l.startswith("SUB-HEADING:")))
        return "Written from the note.", {}

    out = write_section("business", ctx, model)
    assert asked == ["SUB-HEADING: Overview", "SUB-HEADING: Order book"]
    heads = [b["text"] for b in out["blocks"] if b["type"] == "heading"]
    assert heads == ["Overview", "Order book"] and "Manufacturing Process" not in heads


def test_note_passages_end_where_a_sentence_ends_and_a_broken_line_is_joined():
    from draft.writer import _join_split_sentences, note_passages

    t = "The order book was large. It grew in the year; the pipeline is strong. A third sentence follows here."
    assert all(p.rstrip().endswith((".", ";")) for p in note_passages(t, words=8))
    got = _join_split_sentences([{"type": "paragraph", "text": "Margins depend on crews"},
                                 {"type": "paragraph", "text": "and timely billing."}])
    assert [b["text"] for b in got] == ["Margins depend on crews and timely billing."]


def test_a_figure_split_from_its_sentence_is_joined_back():
    from draft.writer import _join_split_sentences

    P = lambda t: {"type": "paragraph", "text": t}          # noqa: E731
    got = _join_split_sentences([P("In FY 2025-26 revenue was \u20b9 11,418.75 lakhs (FY 2023-24:"), P("\u20b9 7,215.60 lakhs), EBITDA 13%."),
                                 P("Borrowings were \u20b9"), P("2,612.00 lakhs."), P("The order book is large."), P("It grows.")])
    assert [b["text"] for b in got] == ["In FY 2025-26 revenue was \u20b9 11,418.75 lakhs (FY 2023-24: \u20b9 7,215.60 lakhs), EBITDA 13%.",
                                        "Borrowings were \u20b9 2,612.00 lakhs.", "The order book is large.", "It grows."]


def test_a_prompt_longer_than_the_window_loses_its_lowest_ranked_inputs_first():
    from draft.writer import est_tokens, fit_messages

    facts = [{"type": "short_text", "label": f"F{i}", "value": "x " * 400} for i in range(40)]
    passages = [{"type": "text", "label": f"P{i}", "value": "y " * 400} for i in range(6)]
    build = lambda ps, rs: [{"role": "user", "content": " ".join(f["value"] for f in ps + rs)}]            # noqa: E731
    msgs, dropped = fit_messages(build, passages, facts, budget=9000)
    assert dropped > 0 and sum(est_tokens(m["content"]) for m in msgs) <= 9000
    small, none = fit_messages(build, passages[:1], facts[:5], budget=9000)
    assert none == 0                                                      # what fits is left alone
    hopeless, _ = fit_messages(build, passages, facts, budget=10)
    assert len(hopeless[0]["content"].split()) == 400 * (5 + 1)           # the first passage and five facts always stay
