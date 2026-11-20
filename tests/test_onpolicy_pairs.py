"""data/onpolicy_pairs.py: the best and worst of several drafts, by what the guard and the prompt's facts say."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from data.onpolicy_pairs import pairs, prompts, utility  # noqa: E402

TRAIN = Path(__file__).resolve().parents[1] / "trainset" / "out" / "train_v3.jsonl"


def _row(tmp_path):
    out = tmp_path / "app.jsonl"
    prompts(str(TRAIN), str(out))
    for line in out.read_text(encoding="utf-8").splitlines():
        r = json.loads(line)
        if "[●]" not in r["messages"][-1]["content"] and len(r["messages"][-1]["content"]) > 400:
            return out, r
    raise AssertionError("no row")


def test_a_draft_that_invents_a_figure_scores_below_the_gold(tmp_path):
    _, r = _row(tmp_path)
    gold = r["messages"][-1]["content"]
    bad = gold + " Our turnover grew by 73.41% to Rs. 9,876.54 lakhs over 17 offices."
    assert utility(gold, r)[0] > utility(bad, r)[0]


def test_pairs_prefer_the_better_draft_and_skip_close_calls(tmp_path):
    out, r = _row(tmp_path)
    gold = r["messages"][-1]["content"]
    bad = gold + " Our turnover grew by 73.41% to Rs. 9,876.54 lakhs over 17 offices."
    cands = tmp_path / "c.jsonl"
    cands.write_text(json.dumps({"id": r["id"], "candidates": [gold, bad]}) + "\n"
                     + json.dumps({"id": r["id"], "candidates": [gold, gold + " ."]}) + "\n", encoding="utf-8")
    pf = tmp_path / "p.jsonl"
    info = pairs(str(cands), str(pf), rows_path=str(out))
    assert info["pairs"] == 1
    p = json.loads(pf.read_text(encoding="utf-8").splitlines()[0])
    assert p["chosen"][0]["content"] == gold and p["rejected"][0]["content"] == bad
