"""Counterfactual bias test with the input-side mitigation (rai.bias_evaluator.neutralise_person_judgement): the 9 cases x 6
people of counterfactual_cases(), each question passed through ResponsibleAI.check_input first, sent to a model on the endpoint.

    python -m rai.bias_mitigation_check [--models sme-drhp-7b,Qwen/Qwen2.5-7B-Instruct] [--out evaluate/out/rai_bias_mitigated.json]
"""
import argparse
import copy
import json
import os

from .bias_evaluator import BiasEvaluator, counterfactual_cases
from .responsible_ai import ResponsibleAI, load_config

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--models", default="sme-drhp-7b,Qwen/Qwen2.5-7B-Instruct")
    ap.add_argument("--out", default=os.path.join(ROOT, "evaluate", "out", "rai_bias_mitigated.json"))
    a = ap.parse_args(argv)
    cfg = load_config()
    cfg["audit"] = {**cfg.get("audit", {}), "path": "evaluate/out/rai_eval_audit.jsonl", "incidents_path": "evaluate/out/rai_eval_incidents.jsonl"}
    rai = ResponsibleAI(cfg)
    from serve import llm, runpod
    runpod.load_env_file()
    st = runpod.load_state()
    cases = counterfactual_cases()
    for c in cases:
        for v in c["variants"]:
            msgs = copy.deepcopy(v["messages"])
            user = msgs[-1]["content"]
            ev, _, q = user.partition("\n\nQUESTION: ")
            verdict = rai.check_input(q, tenant="eval")
            if verdict.action == "rewrite":
                msgs[-1]["content"] = ev + "\n\nQUESTION: " + verdict.text
            v["messages"] = msgs
    from evaluate.metrics import RE_REFUSAL  # noqa: F401
    from .rai_eval import declined
    res = {}
    for m in a.models.split(","):
        chat = llm.make_chat({"model_url": st["model_url"], "api_key": os.environ.get("RUNPOD_API_KEY", ""), "model_name": m,
                              "max_tokens": 300, "temperature": 0})
        out = BiasEvaluator(cfg.get("bias", {})).evaluate(lambda msgs: chat(msgs)[0], cases, refused=declined)
        res[m] = out
        print(m, json.dumps(out["summary"]), flush=True)
    json.dump(res, open(a.out, "w", encoding="utf-8"), indent=1, ensure_ascii=False)


if __name__ == "__main__":
    main()
