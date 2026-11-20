"""data/abstain.py: training rows that show the model a gap."""
import json
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from data.abstain import PH, build, drop_facts, eligible_own, facts_of  # noqa: E402

FACTS = [{"type": "date", "label": "Date of incorporation", "value": "March 14, 2011"},
         {"type": "count", "label": "Employees", "value": "148"},
         {"type": "short_text", "label": "Nature", "value": "EPC contractor"},
         {"type": "amount", "label": "Offer price", "value": "250"}]
TARGET = "Our Company was incorporated on March 14, 2011. We have 148 employees and are an EPC contractor priced at 250."


def row(precedent=True):
    user = ("COMPANY: T\nSECTION: S\nSUB-HEADING: H\nFACTS: " + json.dumps(FACTS, separators=(",", ":"))
            + ("\nPRECEDENT (same sub-heading in another company's offer document; for structure and tone only, never for figures or names):\n"
               "Incorporated on May 1, 1999 with 20 staff." if precedent else "") + "\nDraft the sub-section now.")
    return {"id": "tr-1-x", "messages": [{"role": "system", "content": "s"}, {"role": "user", "content": user},
                                          {"role": "assistant", "content": TARGET}],
            "metadata": {"skill": "drafting", "unit_id": "tr-1-x", "n_facts": 4, "n_own": 4}}


def test_offer_terms_are_never_dropped_and_values_must_be_in_the_target():
    labels = {f["label"] for f in eligible_own(row())}
    assert "Offer price" not in labels and {"Date of incorporation", "Employees"} <= labels


def test_a_dropped_fact_leaves_the_prompt_and_becomes_a_placeholder_in_the_target():
    v = drop_facts(row(), random.Random(1))
    left = {f["label"] for f in facts_of(v)}
    gone = {"Date of incorporation", "Employees", "Nature"} - left
    assert gone and v["metadata"]["variant"] == "abstain"
    t = v["messages"][-1]["content"]
    assert PH in t
    for label in gone:
        value = {f["label"]: f["value"] for f in FACTS}[label]
        assert value not in t


def test_nothing_is_dropped_from_a_row_whose_target_states_no_fact():
    r = row()
    r["messages"][-1]["content"] = "Our Company is described below."
    assert drop_facts(r, random.Random(1)) is None


def test_build_writes_variants_pairs_and_removes_most_precedents(tmp_path):
    src, out, pairs = tmp_path / "t.jsonl", tmp_path / "o.jsonl", tmp_path / "p.jsonl"
    rows = []
    for i in range(40):
        r = row()
        r["id"] = r["metadata"]["unit_id"] = f"tr-{i}-x"
        rows.append(r)
    src.write_text("\n".join(json.dumps(r) for r in rows), encoding="utf-8")
    info = build(str(src), str(out), str(pairs), share=0.5, seed=3)
    assert info["abstain_variants"] == info["pairs"] > 0 and info["rows_out"] == 40 + info["abstain_variants"]
    p = json.loads(pairs.read_text(encoding="utf-8").splitlines()[0])
    assert PH in p["chosen"][0]["content"] and PH not in p["rejected"][0]["content"] and p["rejected"][0]["content"] == TARGET
    assert p["chosen"][0]["role"] == "assistant" and p["n_tokens"] > 0
    kept = sum("PRECEDENT" in json.loads(l)["messages"][1]["content"] for l in out.read_text(encoding="utf-8").splitlines())
    assert kept < 0.6 * info["rows_out"]


def test_keep_pairs_prefer_the_target_that_states_the_fact(tmp_path):
    from data.abstain import keep_pairs
    src, out = tmp_path / "t.jsonl", tmp_path / "k.jsonl"
    rows = []
    for i in range(40):
        r = row()
        r["id"] = r["metadata"]["unit_id"] = f"tr-{i}-x"
        rows.append(r)
    src.write_text("\n".join(json.dumps(r) for r in rows), encoding="utf-8")
    info = keep_pairs(str(src), str(out), share=0.5, seed=3)
    assert info["keep_pairs"] > 0
    p = json.loads(out.read_text(encoding="utf-8").splitlines()[0])
    assert p["chosen"][0]["content"] == TARGET and PH in p["rejected"][0]["content"]
    assert "March 14, 2011" in p["prompt"][1]["content"] or "148" in p["prompt"][1]["content"]
