"""Score the input filter on the held-out prompts (rai/heldout_prompts.json), which were never used to tune the rules.

    python -m rai.heldout_check            -> refused share of the 'refuse' items, wrongly refused share of the 'allow' items
"""
import json
import os

from .safety_guard import SafetyGuard

HERE = os.path.dirname(os.path.abspath(__file__))


def score(guard=None):
    d = json.load(open(os.path.join(HERE, "heldout_prompts.json"), encoding="utf-8"))
    g = guard or SafetyGuard({})
    caught = [(cat, q, g.check_input(q).action == "refuse") for cat, q in d["refuse"]]
    wrong = [(q, g.check_input(q).action == "refuse") for q in d["allow"]]
    return {"refuse_items": len(caught), "caught": sum(c for *_, c in caught),
            "missed": [q for _, q, c in caught if not c],
            "allow_items": len(wrong), "over_refused": [q for q, w in wrong if w]}


if __name__ == "__main__":
    print(json.dumps(score(), indent=1))
