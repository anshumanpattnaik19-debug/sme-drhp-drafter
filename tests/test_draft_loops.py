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

    ctx = Ctx(project={"name": "T", "offer": {}}, facts=[], files=[], tables=[], blocks={})
    seen = []

    def looping_model(messages, frequency_penalty=0.0):
        seen.append(frequency_penalty)
        return "Our Company was incorporated in 2010. " + " ".join([LOOP] * 60), {}

    out = write_section("summary", ctx, looping_model)
    assert seen and all(p == DRAFT_FREQUENCY_PENALTY for p in seen)
    assert out["loop_trimmed"], "a looping sub-heading must be reported"
    # the summary has three sub-headings, each drafted from the same looping reply: one copy per paragraph
    assert max(b["text"].count(LOOP) for b in out["blocks"] if b.get("text")) == 1
