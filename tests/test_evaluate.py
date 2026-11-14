"""Offline tests for the evaluation harness (evaluate/). No GPU, no network.

    python -m pytest tests/test_evaluate.py -q
"""
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from data.prompts import drafting_messages  # noqa: E402
from evaluate.metrics import draft_record, extraction_record, rouge_l, source_text  # noqa: E402
from evaluate.stats import bootstrap, paired, point  # noqa: E402
from evaluate.template import fill, pick_template, build_index  # noqa: E402

FACTS = [{"type": "amount", "label": "revenue", "value": "1,440.00", "unit": "lakhs"},
         {"type": "person", "label": "promoter", "value": "Ramesh Kumar Gupta"},
         {"type": "date", "label": "incorporation", "value": "12 March 2015"}]


def _row(gold, precedent=None, doc_id=1, bucket="business", heading="Our Business", rid="r1", company="Alpha Foods Limited"):
    msgs = drafting_messages(company, "OUR BUSINESS", ["Overview", heading], heading, FACTS, "", precedent=precedent)
    return {"id": rid, "messages": msgs + [{"role": "assistant", "content": gold}],
            "metadata": {"skill": "drafting", "doc_id": doc_id, "section_bucket": bucket, "heading": heading, "company": company}}


def test_rouge_l():
    assert rouge_l("the cat sat on the mat", "the cat sat on the mat") == 1.0
    assert rouge_l("", "anything") == 0.0
    assert 0 < rouge_l("the cat sat", "the dog sat") < 1


def test_precedent_is_not_a_source():
    row = _row("Revenue was ₹1,440.00 lakhs.", precedent="Revenue was ₹2,750.00 lakhs for Beta Mills Limited.")
    assert "2,750.00" in row["messages"][1]["content"]
    assert "2,750.00" not in source_text(row)
    rec = draft_record(row, {"prediction": "Revenue was ₹2,750.00 lakhs, and ₹1,440.00 lakhs before."})
    assert rec["invented_figure"] and rec["invented_figures"] == [2750.0]
    assert rec["figures"] == 2 and rec["figures_grounded"] == 1


def test_grounded_draft_and_fact_use():
    gold = "Our Company was incorporated on 12 March 2015. Revenue was ₹1,440.00 lakhs. Ramesh Kumar Gupta is our Promoter."
    rec = draft_record(_row(gold), {"prediction": "Mr. Ramesh Kumar Gupta promoted our Company, incorporated on 12 March 2015."})
    assert not rec["invented_figure"] and not rec["invented_date"]
    assert rec["names"] >= 1 and rec["names_grounded"] == rec["names"]
    assert rec["own_total"] == 3 and rec["own_used"] == 2


def test_extraction_record_strips_fences():
    row = {"messages": [{}, {}, {"role": "assistant", "content": '{"facts": [{"value": "10%"}, {"value": "Pune"}]}'}]}
    rec = extraction_record(row, {"prediction": '```json\n{"facts": [{"value": "10%"}, {"value": "Delhi"}]}\n```'})
    assert rec == {"valid": True, "tp": 1, "n_pred": 2, "n_gold": 2}
    assert extraction_record(row, {"prediction": "not json"})["valid"] is False


def _recs(n_co, inv_every):
    return [{"id": f"{c}-{i}", "company": c, "skill": "drafting", "figures": 2, "figures_grounded": 2, "dates": 0,
             "dates_grounded": 0, "names": 0, "names_grounded": 0, "invented_figure": (c * 2 + i) % inv_every == 0,
             "invented_date": False, "own_used": 1, "own_total": 2, "distractor_used": None, "rouge_l": 0.5,
             "loop": False, "len_ratio": 1.0} for c in range(n_co) for i in range(2)]


def test_bootstrap_interval_contains_point_and_is_deterministic():
    recs = _recs(20, 3)
    b1, b2 = bootstrap(recs, n=200), bootstrap(recs, n=200)
    assert b1 == b2
    v, lo, hi = b1["invented_fig_rate"]
    assert lo <= v <= hi and lo < hi
    assert b1["grounding"][0] == 1.0 and b1["fact_use"][0] == 0.5
    assert b1["extract_f1"] == (None, None, None)


def test_paired_difference_sign():
    a, b = _recs(20, 100), _recs(20, 2)          # a invents far less than b
    d = paired(a, b, n=200)["invented_fig_rate"]
    assert d[0] < 0 and d[2] < 0 and d[3] < 0.05
    assert paired(a, a, n=200)["invented_fig_rate"][0] == 0


def test_point_is_pooled_not_averaged():
    recs = [{"company": 1, "skill": "drafting", "figures": 1, "figures_grounded": 1, "dates": 0, "dates_grounded": 0, "names": 0, "names_grounded": 0},
            {"company": 2, "skill": "drafting", "figures": 9, "figures_grounded": 0, "dates": 0, "dates_grounded": 0, "names": 0, "names_grounded": 0}]
    assert point(recs)["grounding"] == 0.1


def test_template_fills_company_and_masks_foreign_values():
    tmpl = ("Beta Mills Limited was incorporated on 3 June 2001. Mr. Suresh Patel is the Managing Director. "
            "Revenue was ₹2,750.00 lakhs, against ₹1,440.00 lakhs earlier.")
    row = _row("gold text")
    out = fill(tmpl, "Beta Mills Limited", row)
    assert "Alpha Foods Limited was incorporated" in out
    assert "Beta" not in out and "Suresh" not in out and "Patel" not in out
    assert "3 June 2001" not in out and "2,750.00" not in out
    assert "1,440.00" in out                       # in the issuer's facts, so kept
    assert not draft_record(row, {"prediction": out})["invented_figure"]


def test_template_picks_same_bucket_other_company_closest_heading():
    test_row = _row("x", heading="Plant and Machinery", doc_id=1)
    train = [_row("a", heading="Plant and Machinery details", doc_id=1, rid="same-company"),
             _row("b", heading="Plant and Machinery", doc_id=2, rid="good"),
             _row("c", heading="Human Resources", doc_id=3, rid="other-heading"),
             _row("d", heading="Plant and Machinery", doc_id=4, bucket="objects", rid="other-bucket")]
    assert pick_template(test_row, build_index(train))["id"] == "good"


def test_run_writes_report(tmp_path):
    from evaluate import run
    rows = {"r1": _row("Revenue was ₹1,440.00 lakhs.", rid="r1", doc_id=1),
            "r2": _row("Ramesh Kumar Gupta is our Promoter.", rid="r2", doc_id=2)}
    import evaluate.metrics as M
    orig = M.load_rows
    M.load_rows = lambda name='test.jsonl': rows
    try:
        for name, preds in (("B2", ["Revenue was ₹[●] lakhs.", "[●] is our Promoter."]),
                            ("SYS", ["Revenue was ₹1,440.00 lakhs.", "Ramesh Kumar Gupta is our Promoter."])):
            with open(tmp_path / f"{name}.jsonl", "w", encoding="utf-8") as fh:
                for rid, p in zip(("r1", "r2"), preds):
                    fh.write(json.dumps({"id": rid, "prediction": p, "finish": "stop"}) + "\n")
        run.main([f"B2={tmp_path / 'B2.jsonl'}", f"SYS={tmp_path / 'SYS.jsonl'}", "--system", "SYS", "--compare", "B2",
                  "--out", str(tmp_path / "out")])
    finally:
        M.load_rows = orig
    text = (tmp_path / "out" / "REPORT.md").read_text(encoding="utf-8")
    assert "| H2 | pass |" in text and "| H3 | pending |" in text
    assert json.loads((tmp_path / "out" / "scores.json").read_text())["system"] == "SYS"
