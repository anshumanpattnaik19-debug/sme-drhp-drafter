"""Log every fine-tuning run to a local MLflow store (the Track A deliverable "experiment tracking dashboard").

    python -m evaluate.mlflow_log            # fills mlflow/mlflow.db from drive/runs/ and the score files
    python -m mlflow ui --backend-store-uri sqlite:///mlflow/mlflow.db --port 5000

What goes in, per run: the settings (`train_summary.json`), the training curve (loss, learning rate, gradient norm and, for
DPO, reward accuracy and margin at every logged step), the held-out loss on the test rows (adapter and base model) and the
generation scores from `drive/SCORES_*.json`. Five runs (A_qa, A_qa3, A_qa3_dpo, A_qa3_dpo2, A_qa3_dpo3) left no run
folder on this laptop; they are logged from RETRAINING_LOG.md with the tag `source = RETRAINING_LOG.md` so nobody
reads them as measured here.

The runs were trained on Colab and the course VM before MLflow was set up, so this is a back-fill from the files each run
wrote, not a live log. New runs can log themselves with `log_run(...)` below.
"""
from __future__ import annotations

import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RUNS = os.path.join(ROOT, "drive", "runs")
STORE = os.path.join(ROOT, "mlflow")
URI = "sqlite:///" + os.path.join(STORE, "mlflow.db").replace("\\", "/")
EXPERIMENT = "drhp-copilot-qwen2.5-7b"

# which key of the SCORES files holds each run's greedy generation scores
SCORE_KEY = {"B0": "B0_greedy", "A": "A_greedy", "B": "B_greedy", "A2": "A2_nov4", "seed2": "seed2_greedy", "seed3": "seed3_greedy",
             "ablation1": "ablation1_greedy", "A_dpo": "A_dpo_f03"}

WHY = {
    "A": "first real fine-tune (QLoRA r16): the SFT configuration every later run is compared with",
    "B": "gentler training (r64, lr 1e-4) to test whether it stops the loops: it did not",
    "C": "3 epochs and drafting rows twice: overfit (held-out 1.587)",
    "A2": "page numbers cut from targets: loops are not caused by page references",
    "seed2": "seed 11: measures seed noise", "seed3": "seed 23: measures seed noise",
    "ablation1": "no distractor facts in the prompts: distractor training helps",
    "A_dpo": "DPO against run A's own looping drafts: loops 38 to 1-4 of 89",
    "A_qa": "run A's settings on train_v2 (adds 300 Q&A rows with guardrails)",
}

# two folders hold a summary whose own "run" field is wrong (rai15 was trained with the name left from the earlier DPO script)
FOLDER_NAME = {"A_qa": "A_qa_dpo", "rai15": "A_qa3_rai"}

# runs with no folder on this laptop: settings and results as written in RETRAINING_LOG.md
FROM_LOG = [
    {"run": "A_qa", "method": "qlora", "r": 16, "alpha": 32, "lr": 2e-4, "epochs": 2, "data": "train_v2.jsonl (1,746 rows)", "steps": 219,
     "metrics": {"qa_f1": 0.877, "qa_guardrails": 1.0, "invented_figure_rate_raw": 0.281, "loop_rate": 0.303, "fact_use_greedy": 0.588},
     "why": "run A's settings plus 300 Q&A rows with guardrails (no held-out-loss file was saved for this run)"},
    {"run": "A_qa_dpo", "method": "dpo", "from": "A_qa", "beta": 0.1, "lr": 1e-5, "epochs": 2, "pairs": 223, "steps": 56,
     "metrics": {"reward_accuracy": 0.98, "qa_f1": 0.870, "qa_guardrails": 1.0, "invented_figure_rate_raw": 0.326, "loop_rate": 0.191},
     "why": "DPO on A_qa (loops, run 10); the production model until 20 Nov"},
    {"run": "A_qa3", "method": "qlora", "r": 16, "alpha": 32, "lr": 2e-4, "epochs": 2, "data": "train_v3.jsonl (2,052 rows)", "steps": 257,
     "metrics": {"qa_f1": 0.872, "extraction_f1": 0.531, "invented_figure_rate_raw": 0.191, "loop_rate": 0.157},
     "why": "adds 306 abstention variants ([●] for a missing fact) and removes the precedent block from 60% of drafting rows"},
    {"run": "A_qa3_dpo", "method": "dpo", "from": "A_qa3", "pairs": 706, "metrics": {"fact_use_greedy": 0.43, "invented_after_guard": 0.034},
     "why": "loop pairs + 306 abstention pairs: over-abstains (1,242 [●] in 89 drafts)", "shipped": False},
    {"run": "A_qa3_dpo2", "method": "dpo", "from": "A_qa3", "metrics": {"fact_use": 0.804, "invented_after_guard": 0.079},
     "why": "adds 303 keep pairs: over-corrects (1.16 masked values per draft)", "shipped": False},
    {"run": "A_qa3_dpo3", "method": "dpo", "from": "A_qa3", "beta": 0.1, "lr": 5e-6, "epochs": 2, "pairs": 890, "steps": 223,
     "metrics": {"reward_accuracy": 0.80, "invented_after_guard": 0.0, "masked_per_draft": 0.61, "fact_use": 0.695, "loop_rate": 0.0,
                 "qa_f1": 0.876, "extraction_f1": 0.591, "qa_guardrails": 1.0},
     "why": "on-policy pairs ranked by the app's guard and fact use; SHIPPED 20 Nov 2026", "shipped": True},
    {"run": "A_qa3_rai", "method": "dpo", "from": "A_qa3_dpo3", "beta": 0.1, "lr": 5e-6, "epochs": 2, "pairs": 784, "steps": 196,
     "metrics": {"reward_accuracy": 0.87, "qa_f1": 0.869, "extraction_f1": 0.589, "fact_use": 0.651},
     "why": "Responsible AI pairs: worse on the regression it targeted, not shipped", "shipped": False},
]


def _load(path):
    try:
        return json.load(open(path, encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _num(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def log_run(mlflow, name, params=None, metrics=None, curve=None, tags=None, artifacts=()):
    """One MLflow run: params, final metrics, a step-indexed curve [{step, loss, ...}], tags and files."""
    with mlflow.start_run(run_name=name):
        mlflow.log_params({k: v for k, v in (params or {}).items() if v not in (None, "")})
        for k, v in (metrics or {}).items():
            if _num(v):
                mlflow.log_metric(k, float(v))
        for row in curve or []:
            step = row.get("step")
            if step is None:
                continue
            for k, v in row.items():
                if k not in ("step", "epoch") and _num(v):
                    mlflow.log_metric(k.replace("/", "_"), float(v), step=int(step))
        mlflow.set_tags(tags or {})
        for p in artifacts:
            if os.path.exists(p):
                mlflow.log_artifact(p)


def main():
    import mlflow

    os.makedirs(STORE, exist_ok=True)
    mlflow.set_tracking_uri(URI)
    mlflow.set_experiment(EXPERIMENT)
    scores = {}
    for f in ("SCORES_4NOV.json", "SCORES_6NOV.json", "SCORES_12NOV.json"):
        scores.update(_load(os.path.join(ROOT, "drive", f)) or {})
    done = {r.info.run_name for r in mlflow.search_runs(output_format="list")} if mlflow.get_experiment_by_name(EXPERIMENT) else set()
    n = 0
    for d in sorted(os.listdir(RUNS)):
        folder = os.path.join(RUNS, d)
        ts, hl = _load(os.path.join(folder, "train_summary.json")), _load(os.path.join(folder, "heldout_loss.json"))
        name = FOLDER_NAME.get(d) or (ts or {}).get("run", d)
        if name in done or not (ts or hl or SCORE_KEY.get(name) in scores):
            continue
        ts = ts or {}
        params = {k: ts.get(k) for k in ("method", "from", "r", "alpha", "lr", "epochs", "data", "seed", "beta", "pairs", "base")}
        params["method"] = params["method"] or ("dpo" if "pairs" in ts else "qlora")
        metrics = {}
        if hl:
            metrics.update({"heldout_drafting_loss": hl["drafting"]["adapter"], "heldout_extraction_loss": hl["extraction"]["adapter"],
                            "base_drafting_loss": hl["drafting"]["base"], "base_extraction_loss": hl["extraction"]["base"]})
        sc = scores.get(SCORE_KEY.get(name, ""), {})
        metrics.update({f"gen_{k}": v for k, v in sc.items() if _num(v)})
        extra = next((r for r in FROM_LOG if r["run"] == name), None)          # results recorded in RETRAINING_LOG.md
        if extra:
            metrics.update(extra["metrics"])
            params["method"] = extra["method"]
            params["from"] = extra.get("from")
        log_run(mlflow, name, params, metrics, [r for r in ts.get("log", []) if "step" in r],
                {"source": "drive/runs", "why": WHY.get(name) or (extra or {}).get("why", ""), "base_model": "Qwen2.5-7B-Instruct"},
                [os.path.join(folder, "train_summary.json"), os.path.join(folder, "heldout_loss.json")])
        done.add(name)
        n += 1
    for r in FROM_LOG:
        if r["run"] in done:
            continue
        params = {k: r.get(k) for k in ("method", "from", "r", "alpha", "lr", "epochs", "data", "beta", "pairs", "steps")}
        log_run(mlflow, r["run"], params, r["metrics"], None,
                {"source": "RETRAINING_LOG.md", "why": r["why"], "shipped": str(r.get("shipped", "")), "base_model": "Qwen2.5-7B-Instruct"})
        n += 1
    print(f"logged {n} new runs to {URI}")
    print("view them (from the project folder):  python -m mlflow ui --backend-store-uri sqlite:///mlflow/mlflow.db --port 5000")


if __name__ == "__main__":
    sys.exit(main())
