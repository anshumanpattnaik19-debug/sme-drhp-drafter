"""Experiment dashboard back-filled from the run folders and score files: one self-contained HTML page.

    python -m evaluate.dashboard            # writes docs/experiment_dashboard.html

Reads drive/runs/<run>/train_summary.json and heldout_loss.json and drive/SCORES_*.json. It is a record of finished runs, not
a live Weights & Biases or MLflow project (no run was logged to either).
"""
from __future__ import annotations

import html
import json
import os
from datetime import date

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RUNS = os.path.join(ROOT, "drive", "runs")
OUT = os.path.join(ROOT, "docs", "experiment_dashboard.html")


def load(path):
    try:
        return json.load(open(path, encoding="utf-8"))
    except (OSError, ValueError):
        return None


def runs_table():
    rows = []
    for d in sorted(os.listdir(RUNS)):
        ts, hl = load(os.path.join(RUNS, d, "train_summary.json")), load(os.path.join(RUNS, d, "heldout_loss.json"))
        if not ts:
            continue
        method = ts.get("method") or ("DPO" if "pairs" in ts else "QLoRA")
        rows.append({
            "run": ts.get("run", d), "method": method.upper() if method == "dpo" else method,
            "rank": ts.get("r", ""), "alpha": ts.get("alpha", ""), "lr": ts.get("lr", ""), "epochs": ts.get("epochs", ""),
            "data": ts.get("data") or (f"{ts['pairs']} preference pairs" if "pairs" in ts else ""), "seed": ts.get("seed", ""),
            "draft": hl["drafting"]["adapter"] if hl else None, "ext": hl["extraction"]["adapter"] if hl else None,
            "base_draft": hl["drafting"]["base"] if hl else None,
        })
    order = {"A": 0, "B": 1, "C": 2, "A2": 3, "seed2": 4, "seed3": 5, "ablation1": 6, "A_dpo": 7, "A_qa_dpo": 8}
    return sorted(rows, key=lambda r: order.get(r["run"], 99))


def scores():
    merged = {}
    for f in ("SCORES_4NOV.json", "SCORES_6NOV.json", "SCORES_12NOV.json"):
        merged.update(load(os.path.join(ROOT, "drive", f)) or {})
    return merged


PICK = [("base model", "B0_greedy"), ("A", "A_greedy"), ("B", "B_greedy"), ("A2 (no page numbers)", "A2_nov4"), ("seed2", "seed2_greedy"),
        ("seed3", "seed3_greedy"), ("ablation1 (no distractors)", "ablation1_greedy"), ("A_dpo + frequency 0.3", "A_dpo_f03")]
DECODING = [("greedy", "A_greedy"), ("temperature 0.3", "A_t03"), ("presence 0.5", "A_dt_presence05"), ("frequency 0.3", "A_dt_frequency03"),
            ("repetition 1.1", "A_dt_rep11"), ("A_dpo greedy", "Adpo_dt_greedy_loopstop"), ("A_dpo + frequency 0.3", "Adpo_dt_frequency03"),
            ("A_dpo + frequency 0.5", "Adpo_dt_frequency05")]


def bars(items, width=860, unit="", fmt="{:.2f}", ref=None, ref_label=""):
    """Horizontal SVG bar chart: items = [(label, value)]."""
    h, gap, left = 30, 10, 250
    mx = max([v for _, v in items] + ([ref] if ref else [])) * 1.12 or 1
    H = len(items) * (h + gap) + 18
    out = [f"<svg viewBox='0 0 {width} {H}' width='100%' role='img'>"]
    for i, (lab, v) in enumerate(items):
        y = 8 + i * (h + gap)
        w = (width - left - 90) * v / mx
        out.append(f"<text x='{left - 12}' y='{y + 20}' text-anchor='end' class='lab'>{html.escape(lab)}</text>")
        out.append(f"<rect x='{left}' y='{y}' width='{max(w, 1):.1f}' height='{h}' rx='5' class='bar'/>")
        out.append(f"<text x='{left + w + 8:.1f}' y='{y + 20}' class='val'>{fmt.format(v)}{unit}</text>")
    if ref:
        x = left + (width - left - 90) * ref / mx
        out.append(f"<line x1='{x:.1f}' y1='0' x2='{x:.1f}' y2='{H - 12}' class='ref'/><text x='{x + 6:.1f}' y='{H - 2}' class='refl'>{html.escape(ref_label)}</text>")
    out.append("</svg>")
    return "".join(out)


def table(head, rows):
    th = "".join(f"<th>{html.escape(h)}</th>" for h in head)
    tr = "".join("<tr>" + "".join(f"<td>{html.escape(str(c))}</td>" for c in r) + "</tr>" for r in rows)
    return f"<table><thead><tr>{th}</tr></thead><tbody>{tr}</tbody></table>"


def build():
    runs, sc = runs_table(), scores()
    f2 = lambda v: "not saved" if v is None else f"{v:.3f}"  # noqa: E731
    base = next((r["base_draft"] for r in runs if r["base_draft"]), None)
    reg = table(["run", "method", "rank", "alpha", "lr", "epochs", "data", "seed", "held-out drafting loss", "held-out extraction loss"],
                [[r["run"], r["method"], r["rank"], r["alpha"], r["lr"], r["epochs"], r["data"], r["seed"], f2(r["draft"]), f2(r["ext"])] for r in runs])
    loss = bars([(r["run"], r["draft"]) for r in runs if r["draft"]], fmt="{:.3f}", ref=base, ref_label=f"base model {base:.2f}" if base else "")
    loops = bars([(lab, sc[k]["loops"]) for lab, k in PICK if k in sc], fmt="{:.0f}", unit=" of 89 drafts")
    qual = table(["system (greedy unless stated)", "loops", "cap hits", "length / gold", "own-fact use", "distractor use", "unknown figures / draft", "extraction precision", "extraction recall"],
                 [[lab, sc[k].get("loops"), sc[k].get("caps"), f"{sc[k].get('len_ratio', 0):.2f}", f"{sc[k].get('own_fact_use', 0):.3f}", f"{sc[k].get('distractor_use', 0):.3f}",
                   f"{sc[k].get('unknown_figures', 0):.2f}", f"{sc[k]['precision']:.3f}" if "precision" in sc[k] else "", f"{sc[k]['recall']:.3f}" if "recall" in sc[k] else ""]
                  for lab, k in PICK if k in sc])
    dec = bars([(lab, sc[k]["loops"]) for lab, k in DECODING if k in sc], fmt="{:.0f}", unit=" of 89 drafts")
    return f"""<!doctype html><html lang='en'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>
<title>DRHP Copilot: experiment dashboard</title><style>
:root{{--bg:#f6f7fb;--card:#fff;--ink:#1b2240;--mute:#5b6072;--acc:#4f46e5;--line:#dfe2ee}}
@media(prefers-color-scheme:dark){{:root{{--bg:#0f1220;--card:#171b2e;--ink:#eef0fb;--mute:#a4abc7;--acc:#8f95ff;--line:#2b3250}}}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--ink);font:15px/1.5 'Segoe UI',system-ui,sans-serif}}
main{{max-width:1040px;margin:0 auto;padding:28px 18px 60px}}h1{{font-size:26px;margin:0 0 4px}}h2{{font-size:18px;margin:0 0 4px}}
.sub{{color:var(--mute);margin:0 0 18px}}section{{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:18px 18px 16px;margin:16px 0}}
.note{{color:var(--mute);font-size:13px;margin:6px 0 12px}}.tw{{overflow-x:auto}}table{{border-collapse:collapse;width:100%;font-size:13.5px}}
th,td{{padding:7px 10px;border-bottom:1px solid var(--line);text-align:left;white-space:nowrap}}th{{color:var(--mute);font-weight:600}}
.bar{{fill:var(--acc)}}.lab{{fill:var(--ink);font-size:15px}}.val{{fill:var(--ink);font-size:14px;font-weight:600}}.ref{{stroke:#e0536a;stroke-width:2;stroke-dasharray:6 5}}.refl{{fill:#e0536a;font-size:13px}}
</style></head><body><main>
<h1>Experiment dashboard</h1>
<p class='sub'>DRHP Copilot: every fine-tuning run on Qwen2.5-7B-Instruct, back-filled {date.today():%d %B %Y} from the run folders and score files. A record of finished runs, not a live Weights &amp; Biases or MLflow project. Why each run was done: RETRAINING_LOG.md.</p>
<section><h2>Runs and settings</h2><p class='note'>Held-out loss on the test rows; lower is better. A_qa (SFT on the 1,746-row set with Q&amp;A, 219 steps) has no summary file in drive/runs; it is recorded in RETRAINING_LOG.md. No held-out-loss file was saved for A_qa_dpo.</p><div class='tw'>{reg}</div></section>
<section><h2>Held-out drafting loss by run</h2><p class='note'>Every fine-tune beats the base model (dashed line); run C overfit; the SFT runs sit within 0.03 of each other, so loss alone does not choose between them.</p>{loss}</section>
<section><h2>Drafts that loop under greedy decoding (of 89)</h2><p class='note'>The adapter caused the loops: the base model loops on 4; gentler training (B), cleaner data (A2) and no distractors (ablation1) did not fix it; DPO plus a frequency penalty did. A_dpo is from the 6 Nov full test run (1 loop); the 4 Nov stage-5 test gave 4.</p>{loops}</section>
<section><h2>Generation quality by run</h2><p class='note'>Own-fact use: higher is better. Distractor use and unknown figures: lower is better.</p><div class='tw'>{qual}</div></section>
<section><h2>Decoding experiments on run A and on A_dpo</h2><p class='note'>Loops per 89 drafts. A_dpo with frequency 0.3 was chosen: 4 loops and the highest own-fact use (0.607). Frequency 0.5 removes the loops but lowers own-fact use to 0.514 and raises unknown figures to 0.54.</p>{dec}</section>
</main></body></html>"""


if __name__ == "__main__":
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    open(OUT, "w", encoding="utf-8").write(build())
    print("wrote", OUT)
