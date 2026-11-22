"""Figures for docs/TECHNICAL_REPORT: python docs/report/make_figures.py (reads drive/ and the numbers in docs/RAG_DECISIONS.md)."""
import json
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUT = os.path.join(ROOT, "docs", "report", "figures")
INK, MUTE, ACC, RED, GRY = "#1b2240", "#5b6072", "#3b4cca", "#c0392b", "#aab0c6"
plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 9, "axes.edgecolor": MUTE, "axes.labelcolor": INK, "text.color": INK,
                     "xtick.color": INK, "ytick.color": INK, "axes.spines.top": False, "axes.spines.right": False})


def load(p):
    return json.load(open(os.path.join(ROOT, p), encoding="utf-8"))


# 1. held-out loss
runs = ["A", "B", "C", "A2", "seed2", "seed3", "ablation1", "A_dpo"]
loss = [load(f"drive/runs/{r}/heldout_loss.json")["drafting"]["adapter"] for r in runs]
base = load("drive/runs/A/heldout_loss.json")["drafting"]["base"]
fig, ax = plt.subplots(figsize=(6.4, 2.5))
cols = [RED if r == "C" else ACC for r in runs]
b = ax.bar(runs, loss, color=cols, width=0.62)
ax.axhline(base, color=MUTE, ls="--", lw=1)
ax.text(len(runs) - 0.5, base + 0.03, f"base model {base:.2f}", ha="right", color=MUTE, fontsize=8)
for rect, v in zip(b, loss):
    ax.text(rect.get_x() + rect.get_width() / 2, v + 0.03, f"{v:.2f}", ha="center", fontsize=8)
ax.set_ylim(0, 2.1)
ax.set_ylabel("held-out drafting loss (lower is better)")
fig.tight_layout()
fig.savefig(os.path.join(OUT, "fig_loss.png"), dpi=200)
plt.close(fig)

# 2. loops per 89 greedy drafts
sc = {}
for f in ("SCORES_4NOV.json", "SCORES_6NOV.json", "SCORES_12NOV.json"):
    sc.update(load("drive/" + f))
pick = [("base", "B0_greedy"), ("A", "A_greedy"), ("B (gentler)", "B_greedy"), ("A2 (no page nos.)", "A2_nov4"), ("seed 2", "seed2_greedy"),
        ("seed 3", "seed3_greedy"), ("no distractors", "ablation1_greedy"), ("A + DPO\n+ freq. 0.3", "A_dpo_f03")]
labs, vals = [p[0] for p in pick], [sc[p[1]]["loops"] for p in pick]
fig, ax = plt.subplots(figsize=(6.4, 2.5))
b = ax.bar(labs, vals, color=[GRY if l == "base" else (ACC if "DPO" in l else RED) for l in labs], width=0.62)
for rect, v in zip(b, vals):
    ax.text(rect.get_x() + rect.get_width() / 2, v + 1.2, str(v), ha="center", fontsize=8)
ax.set_ylabel("drafts that loop (of 89)")
ax.set_ylim(0, 82)
plt.setp(ax.get_xticklabels(), fontsize=7.5)
fig.tight_layout()
fig.savefig(os.path.join(OUT, "fig_loops.png"), dpi=200)
plt.close(fig)

# 3. invented figures: raw single draft, then after the guard (best of 3)
import numpy as np
systems = ["base", "A_qa_dpo\n(first model)", "A_qa3_dpo3\n(shipped)"]
raw, guarded = [19.1, 32.6, 11.2], [0.0, 6.7, 0.0]
x = np.arange(3)
fig, ax = plt.subplots(figsize=(6.4, 2.5))
ax.bar(x - 0.19, raw, 0.36, color=GRY, label="single draft, no guard (199-row test set)")
ax.bar(x + 0.19, guarded, 0.36, color=ACC, label="as the app makes it: best of 3 + guard (89 prompts)")
for i in range(3):
    ax.text(x[i] - 0.19, raw[i] + 0.8, f"{raw[i]:.1f}%", ha="center", fontsize=8)
    ax.text(x[i] + 0.19, guarded[i] + 0.8, f"{guarded[i]:.1f}%", ha="center", fontsize=8)
ax.set_xticks(x, systems)
ax.set_ylabel("drafts with an invented figure (%)")
ax.set_ylim(0, 48)
ax.legend(frameon=False, fontsize=7.5, loc="upper right")
fig.tight_layout()
fig.savefig(os.path.join(OUT, "fig_invented.png"), dpi=200)
plt.close(fig)

# 4. retrieval
names = ["BM25", "bge-m3\ndense", "hybrid\n(RRF)", "BM25 +\nreranker", "hybrid +\nreranker"]
r1, r5 = [0.658, 0.474, 0.553, 0.684, 0.658], [0.789, 0.737, 0.763, 0.895, 0.895]
x = np.arange(5)
fig, ax = plt.subplots(figsize=(6.4, 2.4))
ax.bar(x - 0.19, r1, 0.36, color=GRY, label="recall@1")
ax.bar(x + 0.19, r5, 0.36, color=ACC, label="recall@5")
for i in range(5):
    ax.text(x[i] - 0.19, r1[i] + 0.02, f"{r1[i]:.2f}", ha="center", fontsize=7.5)
    ax.text(x[i] + 0.19, r5[i] + 0.02, f"{r5[i]:.2f}", ha="center", fontsize=7.5)
ax.set_xticks(x, names)
ax.set_ylim(0, 1.08)
ax.set_ylabel("recall (38 questions)")
ax.legend(frameon=False, fontsize=8, loc="lower right")
fig.tight_layout()
fig.savefig(os.path.join(OUT, "fig_retrieval.png"), dpi=200)
plt.close(fig)
print("figures written to", OUT)

# 5. the drafting pipeline with the guard stages
from matplotlib.patches import FancyBboxPatch
fig, ax = plt.subplots(figsize=(6.4, 2.35))
ax.set_xlim(0, 100)
ax.set_ylim(0, 40)
ax.axis("off")


def box(x, y, w, h, title, sub="", fc="#eef0fd", ec=ACC, tc=INK):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.3,rounding_size=1.2", fc=fc, ec=ec, lw=1))
    ax.text(x + w / 2, y + h * (0.64 if sub else 0.5), title, ha="center", va="center", fontsize=6.6, weight="bold", color=tc)
    if sub:
        ax.text(x + w / 2, y + h * 0.27, sub, ha="center", va="center", fontsize=5.2, color=MUTE)


def arrow(x1, y1, x2, y2):
    ax.annotate("", xy=(x2, y2), xytext=(x1, y1), arrowprops=dict(arrowstyle="-|>", color=MUTE, lw=0.9))


top = [("Issuer files", "Word, Excel, PDF"), ("Typed facts", "value, period, source"), ("Router", "facts per sub-heading"),
       ("Model x3", "QLoRA + DPO")]
for i, (t, sb) in enumerate(top):
    box(1 + i * 24.5, 27, 21, 10, t, sb)
    if i:
        arrow(1 + i * 24.5 - 3.4, 32, 1 + i * 24.5 - 0.2, 32)
steps = [("1 structure", "footers, loops"), ("2 grounding", "figure, date, name"), ("3 base of %", "N% of X"),
         ("4 period, basis", "year, average"), ("5 future start", "since 2027")]
for i, (t, sb) in enumerate(steps):
    box(1 + i * 19.6, 8.5, 17, 10, t, sb, fc="#fdf1ee", ec=RED)
    if i:
        arrow(1 + i * 19.6 - 2.5, 13.5, 1 + i * 19.6 - 0.2, 13.5)
ax.plot([86, 86, 9.5], [27, 22.6, 22.6], color=MUTE, lw=0.9)
arrow(9.5, 22.6, 9.5, 18.7)
ax.text(50, 24.2, "each of the 3 drafts goes through the guard, in order", fontsize=6.2, color=RED, ha="center", weight="bold")
box(1, 0.8, 98, 5.8, "best of 3 (length floor)  >  DRAFT, unsupported values masked  >  reviewer  >  Word", "", fc="#eef0fd")
arrow(50, 8.3, 50, 6.8)
fig.tight_layout(pad=0.3)
fig.savefig(os.path.join(OUT, "fig_pipeline.png"), dpi=200)
plt.close(fig)
print("pipeline figure written")
