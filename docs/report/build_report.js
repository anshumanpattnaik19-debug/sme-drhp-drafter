// Builds docs/TECHNICAL_REPORT.docx (the Track A "12-page technical report").
//   node docs/report/build_report.js          (needs the `docx` package: NODE_PATH=../demo/node_modules works)
// Numbers come from RETRAINING_LOG.md, docs/MODEL_CARD.md, docs/RAG_DECISIONS.md, docs/HOSTING.md, evaluate/out/REPORT.md and
// build/awq_export/*/README.md; figures from docs/report/make_figures.py.
const fs = require("fs");
const path = require("path");
const {
  Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell, ImageRun, AlignmentType, WidthType, ShadingType,
  BorderStyle, LevelFormat, Footer, Header, PageNumber, HeadingLevel,
} = require("docx");

const FONT = "Calibri", INK = "1B2240", MUTE = "5B6072", ACC = "3B4CCA", LINE = "D5D8E6";
const W = 9638; // A4 with 2 cm margins
const FIG = path.join(__dirname, "figures");
const S = 21; // 10.5 pt

// inline **bold** and _italic_ markup
function runs(text, base = {}) {
  const out = [];
  text.split(/(\*\*[^*]+\*\*|`[^`]+`|(?<![\w])_[^_\s](?:[^_]*[^_\s])?_(?![\w]))/).forEach((t) => {
    if (!t) return;
    if (t.startsWith("**")) out.push(new TextRun({ text: t.slice(2, -2), bold: true, font: FONT, size: S, color: INK, ...base }));
    else if (t.startsWith("`")) out.push(new TextRun({ text: t.slice(1, -1), font: "Consolas", size: (base.size || S) - 2, color: "3B3F8C", ...(base.bold ? { bold: true } : {}) }));
    else if (t.startsWith("_") && t.length > 2) out.push(new TextRun({ text: t.slice(1, -1), italics: true, font: FONT, size: S, color: INK, ...base }));
    else out.push(new TextRun({ text: t, font: FONT, size: S, color: INK, ...base }));
  });
  return out;
}
const P = (t, o = {}) => new Paragraph({ spacing: { after: 100, line: 276 }, alignment: AlignmentType.LEFT, ...o, children: runs(t) });
const B = (t) => new Paragraph({ numbering: { reference: "bul", level: 0 }, spacing: { after: 50, line: 270 }, children: runs(t) });
const H1 = (t) => new Paragraph({ heading: HeadingLevel.HEADING_1, children: [new TextRun({ text: t, font: FONT })] });
const H2 = (t) => new Paragraph({ heading: HeadingLevel.HEADING_2, children: [new TextRun({ text: t, font: FONT })] });

const bd = { style: BorderStyle.SINGLE, size: 4, color: LINE };
const borders = { top: bd, bottom: bd, left: bd, right: bd };
const cell = (t, w, head, first) =>
  new TableCell({
    width: { size: w, type: WidthType.DXA }, borders,
    shading: head ? { fill: "E8EAFB", type: ShadingType.CLEAR, color: "auto" } : undefined,
    margins: { top: 45, bottom: 45, left: 80, right: 80 },
    children: [new Paragraph({ spacing: { after: 0, line: 238 }, children: runs(t, { size: 17, bold: head || first }) })],
  });
function table(widths, header, rows, caption) {
  const tw = widths.reduce((a, b) => a + b, 0);
  const t = new Table({
    width: { size: tw, type: WidthType.DXA }, columnWidths: widths,
    rows: [new TableRow({ tableHeader: true, cantSplit: true, children: header.map((h, i) => cell(h, widths[i], true, false)) }),
      ...rows.map((r) => new TableRow({ cantSplit: true, children: r.map((c, i) => cell(String(c), widths[i], false, i === 0)) }))],
  });
  return caption ? [cap(caption), t, gap()] : [t, gap()];
}
const gap = () => new Paragraph({ spacing: { after: 60 }, children: [] });
const cap = (t) => new Paragraph({ keepNext: true, spacing: { before: 60, after: 50 }, children: runs(t, { size: 17, color: MUTE, bold: true }) });
function fig(file, w, h, caption) {
  return [
    new Paragraph({ keepNext: true, alignment: AlignmentType.CENTER, spacing: { before: 40, after: 20 },
      children: [new ImageRun({ type: "png", data: fs.readFileSync(path.join(FIG, file)), transformation: { width: w, height: h },
        altText: { title: caption, description: caption, name: file } })] }),
    new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 100 }, children: runs(caption, { size: 17, color: MUTE }) }),
  ];
}

const c = [];

// ---------------------------------------------------------------- title and abstract
c.push(new Paragraph({ spacing: { after: 30 }, children: [new TextRun({ text: "DRHP Copilot", font: FONT, size: 44, bold: true, color: ACC })] }));
c.push(new Paragraph({ spacing: { after: 40 }, children: [new TextRun({ text: "Fine-tuning and serving a 7B model to draft SME offer documents under verification", font: FONT, size: 26, color: INK })] }));
c.push(new Paragraph({ spacing: { after: 120 }, border: { bottom: { style: BorderStyle.SINGLE, size: 6, color: ACC, space: 4 } },
  children: [new TextRun({ text: "Track A capstone, technical report  |  Executive Post Graduate Programme in Generative AI and Agentic AI  |  25 November 2026  |  Anshuman Pattnaik and Akshey Sharma", font: FONT, size: 17, color: MUTE })] }));

c.push(H1("Abstract"));
c.push(P("A merchant banker's team drafts the narrative sections of a Draft Red Herring Prospectus (DRHP) for a company listing on the BSE SME platform from the files the issuer hands over. A general 7B instruct model does this badly: it writes figures, dates and names that are in no file, it fills offer terms that must stay blank at DRHP stage, and it does not cite. We adapted **Qwen2.5-7B-Instruct** with QLoRA and DPO to three skills (draft a sub-section from typed facts, extract typed facts from passages, answer questions with citations and guardrails), wrapped it in a verification layer that masks every value the inputs do not support as `[●]`, and serve it behind a FastAPI app on RunPod."));
c.push(P("Fifteen training runs are recorded. The model that ships (**A_qa3_dpo3**) beats the base on question answering (F1 0.88 against 0.70; the answering passage cited 100% against 38%; guardrail rows 100% against 38%), on extraction (F1 0.59 against 0.36) and on use of the issuer's facts in drafts (0.70 against 0.54). On invented figures it **ties** the base after the guard (0 of 89 drafts each) and is better before it (11.2% of single drafts against 19.1%); it loops more than the base (7.9% against 1.1% of single drafts), which the app trims. We also set out the approaches we ruled out, which is how we arrived at the final design (sections 5 and 6)."));
c.push(...table([3500, 1700, 1700, 2738], ["measure (test set: 199 rows, 75 companies)", "base", "shipped", "source"], [
  ["Q&A F1 (60 rows)", "0.695", "0.876", "RAG_DECISIONS, MODEL_CARD"],
  ["Q&A cites the answering passage", "38%", "100%", "MODEL_CARD"],
  ["Q&A guardrail rows handled", "38%", "100%", "MODEL_CARD"],
  ["extraction F1 (50 rows)", "0.355", "0.591", "RETRAINING_LOG run 14"],
  ["drafting: facts used (app format, best of 3 + guard)", "0.535", "0.695", "RETRAINING_LOG run 14"],
  ["drafting: drafts with an invented figure, single draft", "19.1%", "11.2%", "MODEL_CARD"],
  ["drafting: invented figure after the guard (89 prompts)", "0 of 89", "0 of 89", "MODEL_CARD; both reach zero"],
  ["drafting: single drafts that loop", "1.1%", "7.9%", "MODEL_CARD; trimmed by the app"],
], "Table 1. Headline results."));

// ---------------------------------------------------------------- 1 problem
c.push(H1("1  Problem, scope and design choices"));
c.push(P("**Domain.** SEBI's ICDR regulations (Chapter IX) and the BSE SME rules set what an SME DRHP must say. The issuer supplies restated financials, an auditor's report, board and shareholder resolutions, the MoA and AoA, licences, contracts, an industry report and project-cost quotations, in Word, Excel, PDF and scans. The task is narrow and regulated, which is what Track A asks for, and the failure that matters is specific: a figure that looks plausible and is not in any file."));
c.push(P("**What the model drafts.** Ten sections: summary, objects of the issue, industry, business, history, management, promoters, MD&A, litigation and government approvals. Risk factors are written by rules from the issuer's data (`draft/red_flags.py`); the restated financial statements and the auditor's report are inserted as provided, never drafted. Every output is marked DRAFT, carries its source trace, and needs a reviewer's sign-off in the app."));
c.push(P("**Three skills, one model.** (1) _Drafting_: one sub-heading per call from a list of typed facts (label, value, unit, period, snippet) with unknown values written `[●]`. (2) _Extraction_: typed facts from an issuer passage, as JSON. (3) _Question answering_ over numbered evidence, with citation markers, refusal when the evidence does not answer, no investment advice, offer terms kept `[●]`, injected instructions in documents ignored. The same prompt formats are used in training and in the app (`data/prompts.py`), which removes a train/serve gap."));
c.push(...fig("architecture.png", 600, 293, "Figure 1. Deployment: a launcher page wakes a CPU pod that runs the app; the model is a serverless GPU endpoint billed by the second."));

// ---------------------------------------------------------------- 2 data
c.push(H1("2  Dataset"));
c.push(P("**Sources.** 455 public SME offer documents on BSE (2021 to 2026), already split into SEBI sections; split by company, so no company is in both train and test (checked by the build). A teacher model (Qwen3-32B-AWQ, Apache 2.0) extracted typed facts from each sub-heading's text; the drafting target is the filed text of that sub-heading, with offer price, issue size, dates and lot size replaced by `[●]` (the DRHP stage) and \"Prospectus\" rewritten as \"Draft Red Herring Prospectus\". Personal identifiers are masked."));
c.push(P("**Gates.** A row is kept only if every figure, date and name of the teacher's facts appears in the source (precision 0.982 after the gates), figures are at least 90% covered, and the facts do not copy the target (an 8-word overlap check). 317 of 1,800 train units failed a gate and were dropped. The teacher screen did not meet the plan's coverage gate (precision 0.997 but coverage 0.53 for Qwen3-32B-AWQ, against 0.40 for the 30B-A3B), so a gap-fill pass re-asked 497 short calls, and coverage after it is 0.92 for figures and 0.91 for names. **Distractors and a router.** Each drafting prompt holds its own sub-heading's facts plus about as many facts from other sub-headings, ranked by a router; at inference the same router selects facts (recall 0.48), which is why training had to show the model facts it should not use. 30% of extraction rows carry OCR noise."));
c.push(...table([2900, 1550, 1550, 3638], ["file", "rows", "companies", "content"], [
  ["train.jsonl (v1, 1 Nov)", "1,446", "346", "657 drafting + 789 extraction"],
  ["train_v2.jsonl (14 Nov)", "1,746", "-", "v1 + 300 Q&A with guardrails (170 answerable, 50 unanswerable, 16 each: injection, advice, price, PII, omission)"],
  ["train_v3.jsonl (20 Nov, trained on)", "2,052", "-", "v2 + 306 abstention variants (1 to 3 facts removed, their values `[●]` in the target); precedent block removed from 60% of drafting rows"],
  ["test_v2.jsonl (held out)", "199", "75", "89 drafting + 50 extraction + 60 Q&A, written from test-only companies"],
], "Table 2. Data. The brief's ceiling is 2,000 examples; the final file has 2,052 rows, of which 306 are variants of existing drafting rows (1,746 distinct)."));
c.push(P("**Leakage.** A MinHash check (5-word shingles, Jaccard 0.6) flags test units with a near-duplicate in train; scores can be read on the novel subset. The test set is small (89 drafts from 75 companies); a difference of one or two drafts is not a result, and every comparison below uses a bootstrap over companies where it matters."));

// ---------------------------------------------------------------- 3 baselines
c.push(H1("3  Baselines and measures"));
c.push(P("Baselines on the same test rows: **B0** base model, zero-shot in the app's prompt; **B1** base, 2-shot; **B2** a template (nearest training precedent for the sub-heading, facts substituted by code, no model) to ask whether fine-tuning beats boilerplate; **B3** the teacher, 2-shot, as a ceiling. Held-out loss is the first filter: **1.84 (drafting) and 0.148 (extraction)** for the base. A run must beat it before seeds or ablations are spent on it."));
c.push(P("Drafting is scored for **grounding** (figures, dates and names of the draft found in the issuer's inputs), **invented-figure rate** (drafts with at least one figure not in the inputs), **fact use** (share of the filed text's facts the draft also uses), **distractor leakage**, **loop rate**, length against the filed text and ROUGE-L. Extraction is scored by value-level precision, recall and F1 and JSON validity; Q&A by token F1 against the gold answer, citation of the answering passage, handling of unanswerable and guardrail rows. Intervals are 95% percentile bootstraps over companies (1,000 resamples); system comparisons are paired on the same rows. The teacher also scored drafts on a 1 to 5 rubric (four criteria): the filed text 3.94, base 3.87, 2-shot base 3.84, fine-tuned 3.58. The judge is the teacher (the plan's gpt-oss-20b did not fit the VM's disk quota), so this is secondary evidence, and the fine-tuned model is rated lower than the base on it."));

// ---------------------------------------------------------------- 4 SFT
c.push(H1("4  Fine-tuning: runs and ablation"));
c.push(P("All runs are 4-bit QLoRA on Qwen2.5-7B-Instruct with Unsloth, loss on the assistant turn only, maximum sequence 6,144 tokens, on an L4 (Colab) or the course L40S. Run A (rank 16, alpha 32, lr 2e-4, all linear layers, 2 epochs, 1,446 rows) is the reference; every run is recorded with its reason in `RETRAINING_LOG.md` and logged to MLflow (section 8)."));
c.push(...table([3000, 6638], ["setting", "value"], [
  ["quantisation and adapter", "base loaded in 4-bit NF4 with double quantisation (bitsandbytes), bf16 compute; LoRA on q, k, v, o, gate, up and down projections, rank 16, alpha 32, dropout 0"],
  ["optimisation (SFT)", "AdamW, weight decay 0, learning rate 2e-4, cosine schedule with 6 warm-up steps, 16 examples per optimiser step, 2 epochs, seed 3407; 182 steps on 1,446 rows, 257 on 2,052"],
  ["loss", "assistant turn only; maximum sequence 6,144 tokens (the app's prompts are shorter; behaviour beyond it was checked with one needle test)"],
  ["preference tuning (DPO)", "frozen copy of the starting adapter as reference, beta 0.1, 2 epochs, lr 1e-5 (runs 6, 10) or 5e-6 (runs 14, 15), gradient accumulation 8"],
  ["compute", "Colab L4 for runs A to C, A2, B, seeds and ablation (about 70 to 80 min each); course L40S (Slurm) for runs 9 to 15 (23 to 82 min each), the 220-job Q&A teacher run (40 min) and all predictions (the course allowance is 75 GPU-hours)"],
], "Table 3a. Training configuration."));
c.push(...table([700, 1500, 3500, 3938], ["run", "change from A", "why", "result"], [
  ["A", "reference", "teach drafting and extraction from gated teacher data", "held-out 1.291 / 0.064 (base 1.841 / 0.148); extraction recall 0.71 vs 0.43; **38 of 89 drafts loop** (base 4)"],
  ["B", "r64, alpha 64, lr 1e-4", "gentler training: does it stop the loops?", "1.300 / 0.065; 42 loops: no"],
  ["C", "3 epochs, drafting rows twice", "fit the drafting rows harder", "training loss 0.12 but held-out **1.587**: overfit"],
  ["A2", "page numbers cut from targets", "21 of 89 drafts said \"on page N\"", "1.316 / 0.065; 43 loops: loops are not page references"],
  ["seed 2, seed 3", "seeds 11, 23", "how much of a gap is seed noise", "1.285, 1.282; loops 35, 38; fact use 0.49 to 0.53"],
  ["ablation 1", "no distractor facts in prompts", "is distractor training worth its length?", "same loss; wrong-section fact used in **58%** of drafts (43 to 50% with it); 72 loops: it helps"],
], "Table 3b. Supervised runs (89 greedy test drafts each; details in RETRAINING_LOG)."));
c.push(...fig("fig_loss.png", 600, 235, "Figure 2. Held-out drafting loss. Every fine-tune beats the base model, but the SFT runs sit within 0.04 of one another, so loss alone cannot choose between them."));
c.push(P("**Findings.** (i) Held-out loss improves 30% and cannot rank the runs, so generation measures decide. (ii) The adapter itself causes the loops: the base loops on 4 of 89 drafts, run A on 38; the same loops appear on a 4-bit base (14 of 20 re-run), at temperature 0.3 (34) and with a repetition penalty of 1.05 (31, on a merged model that later proved invalid). Gentler training (B), more epochs (C), cleaner targets (A2) and cleaning loops out of the targets (only 8 of 657 targets repeat) did not fix it. (iii) Seed spread is under 0.01 in loss but larger in generation: a gap below about 0.04 in fact use or 0.17 in extraction recall can be seed noise, so we do not read smaller ones. (iv) Merging a 4-bit-trained adapter into bf16 weights broke the model (found 4 Nov); every merged-model prediction before that is invalid, and adapters are served unmerged."));
c.push(...fig("fig_loops.png", 600, 235, "Figure 3. Drafts that loop under greedy decoding. DPO plus a frequency penalty of 0.3 is the only change that moved the count."));

// ---------------------------------------------------------------- 5 preference tuning
c.push(H1("5  Preference tuning and the invented-figure problem"));
c.push(P("**DPO against the loops (run 6).** 233 pairs: chosen = the gold sub-section, rejected = run A's own draft that looped or hit the cap; beta 0.1, lr 1e-5. With a frequency penalty of 0.3, loops fell from 38 to 1 to 4 of 89, fact use rose to 0.57 to 0.61 and extraction precision to 0.63 (base 0.48). The cost: 0.39 unknown figures per draft (base 0.22), so a verifier became mandatory. **Q&A skill (runs 9 and 10)** added the 300 Q&A rows and the same DPO step; this model ran in production until 20 Nov."));
c.push(...table([3300, 1000, 1000, 1300, 1500, 1538], ["decoding on 89 test drafts", "loops", "cap hits", "length / filed", "own-fact use", "unknown figures per draft"], [
  ["run A, greedy", "38", "39", "1.47", "0.494", "0.43"],
  ["run A, temperature 0.3", "34", "39", "1.59", "0.521", "3.30"],
  ["run A, presence penalty 0.5", "24", "5", "1.33", "0.558", "4.85"],
  ["run A, frequency penalty 0.3", "23", "0", "1.44", "0.593", "0.53"],
  ["run A, repetition penalty 1.1", "13", "11", "2.21", "0.589", "0.42"],
  ["A_dpo, greedy with loop stop", "20", "3", "1.09", "0.517", "0.36"],
  ["**A_dpo, frequency penalty 0.3 (chosen)**", "**4**", "**0**", "**0.98**", "**0.607**", "**0.42**"],
  ["A_dpo, frequency penalty 0.5", "0", "0", "0.93", "0.514", "0.54"],
], "Table 3c. Decoding experiments. A repetition penalty also hits tokens copied from the prompt (length 2.2 times the filed text); only DPO plus a frequency penalty of 0.3 removed the loops without costing fact use."));
c.push(P("**Why figures were invented.** The model was trained on all of a sub-heading's facts, but at inference it receives about half (router recall 0.48): 33% of its drafts held a figure absent from their inputs. Training targets never showed `[●]` for a missing fact even though the prompt asks for it. Runs 11 to 15 tested fixes on 20 Nov:"));
c.push(...table([700, 1700, 3000, 4238], ["run", "what", "idea", "result (89 app-format prompts, best of 3 + guard unless stated)"], [
  ["11 A_qa3", "SFT on train_v3 (abstention variants)", "show `[●]` for gaps", "invented 5.6%, 0.82 masked per draft; not shipped, start of run 14"],
  ["12 _dpo", "+ 400 loop + 306 abstention pairs", "prefer `[●]` over an unsupported value", "**over-abstains**: 1,242 `[●]` in 89 drafts; fact use 0.43 greedy; not shipped"],
  ["13 _dpo2", "+ 303 \"keep\" pairs", "state the fact when it is given", "**over-corrects**: fact use 0.80 but 1.16 masked per draft, invented 7.9%; not shipped"],
  ["14 _dpo3", "890 **on-policy** pairs: 4 drafts per prompt at T 0.8, scored by the app's own guard and fact use", "let the real trade-off pick chosen and rejected", "invented **0 of 89**, 0.61 masked, fact use **0.695**, loops 0%, length 0.88: **shipped 20 Nov**"],
  ["15 _rai", "+ 784 Responsible-AI pairs", "fix three RAI regressions of run 14", "worse on the regression it targeted (real injections reported 75% to 0%); **not shipped**"],
], "Table 4. Runs 11 to 15. Synthetic one-sided pairs (12, 13) taught a style; ranking the model's own drafts by the metric that matters (14) taught the trade."));
c.push(...fig("fig_invented.png", 600, 235, "Figure 4. Drafts with an invented figure: raw single drafts against the app's output. The guard removes what the model still invents."));
c.push(P("Run 14 **ties** the base on invented figures after the guard (0 against 0 of 89: two near-zero rates cannot be told apart on 89 drafts) and is better on fact use, masked values per draft, Q&A and extraction. The metric was repaired on the evening of 20 Nov (figures printed with spaces, serial numbers in lists); the repair applies to every model and was made after the results were seen, which the model card says. Before it, run 14 read 1 of 89 and the previous adapter 7 of 89."));

// ---------------------------------------------------------------- 6 guard
c.push(H1("6  The verification layer"));
c.push(P("Fine-tuning reduces invention; it does not remove it (11% of single drafts). The app therefore treats the model as an untrusted writer: it drafts three times, runs each draft through the guard (`draft/writer.py`, `verify/`), and keeps the best with a length floor of 0.6 times the median. The guard, in order:"));
c.push(...fig("fig_pipeline.png", 600, 220, "Figure 5. Drafting with the guard. The numbered stages are the guard in the order it runs (details below)."));
c.push(B("**Structure:** strip page footers; cut repeated sentences (`trim_repeats`); collapse runs; cut degenerate output (three or more split words absent from the inputs, or a 120-word run-on with ten semicolons); parse tables apart from prose."));
c.push(B("**Grounding:** each figure, date, name and place must appear in the facts or the issuer's passages, else it becomes `[●]`; identifiers are checked as strings."));
c.push(B("**Base of a percentage:** \"N% of X\" is checked against the source's own base (`mask_misbased_percents`)."));
c.push(B("**Period and basis** (`verify/claims.py`, new): a percentage or amount is masked when its period or basis (an average, \"the last three years\", the wrong fiscal year, a half-year used for a full year) contradicts **every** piece of evidence for that number."));
c.push(B("**Future start** (new): a year later than the document's reporting date, said to have begun (\"certified since 2027\"), is masked."));
c.push(P("**Measured, not asserted.** The period and basis check was built against two failure modes: wrongly masking a correct sentence (a client would see `[●]` where the file has a figure) and missing an altered one. A mutation test builds sentences from the typed facts of a project and checks them against all facts of that project: **0 of 90 correct sentences masked on the Kestrel inputs and 0 of 118 on a larger project; 84 of 89 and 107 of 116 shifted fiscal years caught; 88 of 90 and 116 of 118 invented averages caught** (the misses are mostly values such as 0 lakhs, skipped on purpose, and labels that are people rather than line items; the Kestrel run was repeated after the last fixes with the same result, the larger project was measured before them, and a fourth project of 4,411 facts did not finish in 30 minutes and is not counted). The first version masked 65 values on the 89 test drafts, nearly all wrongly (\"aged 40 years\" read as a 40-year basis, a ₹10 face value bound to \"average\"); every false positive became a regression test. The final version fires 10 times on the five sets of live-evaluation drafts, and each of the 9 hits read against its evidence was a year or basis the source does not give. The suite has 304 tests."));
c.push(P("**Hosted test with the live model.** The first hosted draft of the Summary (20 Nov) exposed three defects the benchmarks had not: a run-on paragraph of split words, a page footer printed as text, and \"about 61% of revenue on average over the last three years\", where the source gives 61.27% for one year and a rounded \"about 61%\" with no period. Each is now a guard rule with a test. On 22 Nov all 11 SLM sections were redrafted by the live endpoint (0 job errors; risk factors by rules, the rest by the model): the guard masked 4 values (2 identifiers, 1 misplaced base, 1 figure) and **two errors passed it**, found by reading the 18 sentences that tie a percentage or amount to a period. (1) \"revenue per MT increased from ₹149.74 in FY 2023-24 to ₹159.02 in FY 2024-25\" swaps two years: the facts say 159.02 and 149.74. Cause: each fact of a table row holds the whole row as its snippet, so every number borrowed its neighbours' years. (2) \"FSSC 22000 v6 certified since 2027\", where 2027 is the certificate's expiry. Both are now rules with tests, replayed on the real facts and masked (the first also exposed a sign mismatch: \"₹-0.42\" against the fact -0.42). A second redraft on the redeployed pod (10 model sections, 0 errors, guard build 6e61d7d89e7e) found two more: \"₹149.74 in FY 2023-24\" (it is FY 2024-25: a six-month figure at the end of the clause had turned the whole clause half-year, so a neighbour tagged H1 FY27 counted as support), and \"FSSC 22000 certification since June 2025\" (the month is the VOC unit's, in the same timeline row). Both are fixed, with tests, by a half-year flag per figure and a new rule that keeps a month-year only if a source holds it beside a word of its own sentence (`mask_event_dates`); I replayed 14 period-bearing sentences from that redraft on the real facts and only these two are masked. The 19 other period- and date-bearing sentences I read each trace to a source. The pod was redeployed (guard build ca4ee41aecf2) and a third live redraft masked the swapped-year pair of the revenue-per-MT sentence on the hosted app (the month rule is verified offline only: the model did not write that sentence again). The same read found five model errors. Two now have a rule (`mask_malformed_amounts`, deployed as build 3f8f672d3ef7): \"₹75,0,0,0,00\" and \"₹4800 MT\". Three have none and are reviewer items: an invented \"revised ... due to operational inefficiencies\", a swapped sitting fee (₹20,000 per Board meeting written as ₹10,000) and a stitched fragment. A fourth redraft (build 3f8f672d3ef7) confirmed the month rule live and masked two swapped customer percentages, and showed two faults of the period check itself: a right figure masked (68.81% for H1 FY27, inside a \"respectively\" list) and a swapped pair missed (₹616 and ₹1,244 lakhs for FY 2026-27 and FY 2027-28). Both came from reading a list clause by clause, and from a source passage lending both years to both figures; figures are now paired with years in order (`pair_in_order`), and a half-year cue in a lead-in clause is carried to its figure. The fixes are deployed (build cc815e4ba2b4, 270 tests, mutation test unchanged) but not yet confirmed by a fifth live redraft. A check of what a figure or date is **of** was built and removed: against real drafts only about one hit in four was correct, because table facts are labelled by their column headers, and a guard that masks correct figures is not client grade. Neither check replaces a reviewer reading each section against its sources."));
c.push(P("**Two more data rooms (22 Nov).** A contractor (44 files, 5,725 facts) and a spice maker (45 files, 9,193 facts) went through the hosted UI. Directors, KMP, offer terms, objects and open items matched the generators' master data, but the first draft was not client grade: the extractor silently kept 400 facts per file; Word heading styles were ignored, leaving 14 sub-headings unwritten; spreadsheet control rows, copied section numbers, chart captions, reference marks and letterheads reached the text; four files were misclassified; and a rule printed \"952.06% of revenue\", an amount read as a percentage. The guard re-read every fact for every paragraph (now built once per sub-heading), and the drafting penalty of 0.3 made the DPO adapter reword what it copies: on the 89 test drafts penalties 0.3, 0.1 and 0.0 gave fact use 0.659, 0.714 and 0.686, loops 0.0%, 1.1% and 2.2% and no invented figure after the guard (one run each, no interval); the app now uses 0.1. The spice maker's table headed \"(₹ lakhs)\" came out as \"₹4,012.19 million\": right digits, a hundredfold wrong unit, invisible to the value check; the guard now compares the unit with the inputs. All are fixed with tests (304 pass); the last, found while making the demo video, was a 2,385-word Industry Overview of 47 near-identical paragraphs, which the repeat check missed because no two lines were equal. A new cut handles that shape only. A check on what a percentage is **of** was tried and removed: it masked 158 of 352 percentage paragraphs, nearly all correct, so a figure on the wrong subject (\"top ten suppliers 58.40%\") stays a reviewer item. Three rooms are not a validation: each found something the last did not, a fourth was started but not read, and no practising reviewer has marked a draft."));

c.push(...table([2300, 2900, 2200, 2238], ["what the model wrote", "what the source says", "guard result", "rule"], [
  ["\"top ten customers contribute about 61% of revenue on average over the last three years ended FY 2025-26\" (20 Nov)", "61.27% for FY 2025-26 only; \"about 61%\" elsewhere, with no period", "61 masked", "period and basis"],
  ["\"revenue per MT increased from ₹149.74 in FY 2023-24 to ₹159.02 in FY 2024-25 and ₹160.55 in FY 2025-26\" (22 Nov)", "FY 2023-24 is 159.02, FY 2024-25 is 149.74 (a fall, not a rise)", "passed at first (sibling leak); now both masked", "period and basis, fixed"],
  ["\"FSSC 22000 v6 certified since 2027\" (22 Nov)", "2 November 2027 is the certificate's expiry; certified in 2025", "year masked", "future start"],
  ["\"With FSSC 22000 certification since June 2025\" (22 Nov, second redraft)", "\"June 2025\" belongs to the VOC unit installed in the same timeline row", "passed at first; month masked offline (replayed on the real facts)", "event date, deployed 22 Nov"],
  ["\"₹149.74 in FY 2023-24 to ₹160.55 in FY 2025-26 and ₹175.5 in the six months ended\" (22 Nov, second redraft)", "149.74 is FY 2024-25", "passed at first (half-year flag); after the fix masked on the hosted app, in a swapped-year variant", "period and basis, deployed 22 Nov"],
], "Table 5a. Five guard cases from the hosted tests. Figures and dates are in the inputs in every case; only what they are said to be of is wrong."));

// ---------------------------------------------------------------- 7 RAG
c.push(H1("7  Retrieval (RAG)"));
c.push(P("Corpus: 761 sections of the 75 test companies (14,295 sub-heading units, 38,947 passages); a query searches only its own company's sections (tenant isolation, as in the app). **Chunking:** passages of about 110 words split at sentence ends with a one-sentence overlap; tables become chunks of caption, header and up to 8 rows so a row is read with its column names; sub-heading boundaries are never crossed. **Not varied:** chunk size. **Retriever and reranker**, on the 38 Q&A rows that have a gold passage:"));
c.push(...fig("fig_retrieval.png", 600, 225, "Figure 6. Retrieval on 38 questions: BM25 beats dense bge-m3 on filed documents (exact figures and section words); a cross-encoder reranker over BM25's top 30 is best."));
c.push(P("**Decision:** BM25 first stage; the bge-reranker-v2-m3 reranker is switched on when the machine allows (the pod is a CPU machine, so BM25 is the default). Querying with the question and reranking finds the gold passage in the top 5 for 89% of questions; the earlier agentic setting (the model writes its own queries) found it for 37%."));
c.push(...table([2300, 1100, 1300, 1300, 1700, 1938], ["system (149 rows)", "Q&A F1", "cites gold", "guardrails", "draft grounding", "drafts with invented figure"], [
  ["base", "0.695", "38%", "38%", "0.860", "19.1%"],
  ["base + RAG (R0)", "0.602", "15%", "38%", "0.666", "40.4%"],
  ["**fine-tuned (F1)**", "**0.876**", "**100%**", "**100%**", "**0.951**", "**11.2%**"],
  ["fine-tuned + RAG (F2)", "0.785", "18%", "88%", "0.764", "22.5%"],
], "Table 5. The required comparison. Paired by company: F2 against R0, Q&A F1 +0.18 [+0.11, +0.26], invented-figure drafts -18 points [-29, -6]; F2 against F1, Q&A F1 -0.09 [-0.15, -0.04]."));
c.push(P("Fine-tuning helps with or without retrieval; retrieval does not help this task as measured. Part of the drop is retrieval misses (without RAG the Q&A rows are given the answering passage), and for drafting a figure taken from retrieved context counts as ungrounded, because a sub-section must be drafted from its own facts: the measure is strict by design. The app therefore uses retrieval for the assistant's search over the issuer's files, where nothing else supplies the evidence, and not as extra context for drafting."));

// ---------------------------------------------------------------- 8 evaluation
c.push(H1("8  Evaluation against the success criteria, and experiment tracking"));
c.push(P("**End to end.** An issuer bundle (Word resolutions and CVs, Excel financials and project cost, the MoA as PDF, a litigation list, a scanned certificate and a table as an image) is read with OCR where needed, split into passages that keep their file and page or cell, and turned into typed facts. A router picks the facts for each sub-heading; the model drafts it three times; the guard masks what the inputs do not support; a QC pass flags objects tables that do not reconcile; a reviewer edits and signs off section by section, and the app exports a Word file. Five bundles were run through the app's own API (VM job 73, base plus adapter, 9 to 11 minutes each, 0 job errors):"));
c.push(...table([3000, 3000, 3638], ["bundle", "typed facts", "ungrounded values (job 73)"], [
  ["Ashtavira", "4,436", "0"], ["Kestrel", "2,070", "0"], ["Bhuvanam", "2,071", "0"], ["Tavanvi", "2,068", "0"], ["Oakvale", "2,070", "0"],
], "Table 6a. The five issuer bundles (H5). Earlier jobs found 8 to 10 looping sections per bundle, tables written as text, garbled amounts and, in job 64, one truncated sentence; each fix is in `H5_RESULTS.md`. The worst repeated sentence left is x7, in the rule-written risk factors, and objects tables that do not reconcile are flagged for the reviewer."));
c.push(P("The success criteria were fixed before the dataset freeze (PLAN.md 7.4) and are reported as they came out; thresholds were not moved."));
c.push(...table([700, 3100, 5838], ["id", "criterion", "outcome"], [
  ["H1", "grounding >= 0.98, above R0 (non-overlapping 95% intervals)", "**met for the shipped system** (fine-tuned + verifier): 0.990 [0.978, 0.998] on 139 rows (A_dpo, 14 Nov), base + RAG 0.666. **Not met for F2** (fine-tuned + RAG, 0.764): RAG lowers grounding, so F2 is not the system we ship."],
  ["H2", "invented-figure rate <= 2% of drafts", "**met**: 0 of 89 after the guard (and 0 of 89 again on the deployed endpoint, fresh samples)"],
  ["H3", "checklist coverage >= template + 10 points", "**not measured**: needs the reviewer's mandatory-item checklist"],
  ["H4", "beats the template on the judge and in a blind comparison", "**not established**: judge is the teacher (fine-tuned 3.58 < base 3.87); the blind comparison needs a practising reviewer"],
  ["H5", "5 issuer bundles end to end, zero invented figures", "**met on grounding**: 0 ungrounded values in all five bundles (VM job 73, 5 formats incl. a scan); draft-quality defects found and listed in `H5_RESULTS.md` (tables written as text, objects totals that do not reconcile)"],
], "Table 6. Success criteria."));
c.push(P("**Paired results** (139 rows, A_dpo with the verifier against the base with the verifier, bootstrap over companies): grounding +0.030 [+0.003, +0.059] (p = 0.028), distractor leakage -0.107 [-0.216, -0.010] (p = 0.046), extraction F1 +0.187 [+0.074, +0.323] (p < 0.001); fact use +0.054 [-0.025, +0.136] is **not** significant. Against the template, grounding +0.164 and fact use +0.484 (both significant), so fine-tuning is worth more than boilerplate."));
c.push(P("**Experiment tracking.** The Track A brief asks for a Weights & Biases or MLflow dashboard. The runs were trained on Colab and the course VM before one was set up, so `python -m evaluate.mlflow_log` back-fills an **MLflow** store (`mlflow/mlflow.db`, experiment `drhp-copilot-qwen2.5-7b`) from the files each run wrote: 16 runs with their parameters, step-indexed training metrics, held-out loss, generation scores and a tag recording why it was run and whether it shipped. Five runs left no folder on the laptop (A_qa and A_qa3 to A_qa3_dpo3) and are logged from RETRAINING_LOG with the tag `source = RETRAINING_LOG.md`. View with `python -m mlflow ui --backend-store-uri sqlite:///mlflow/mlflow.db`. This is a record of finished runs, not a live log; the static `docs/experiment_dashboard.html` shows the same data."));

// ---------------------------------------------------------------- 9 serving
c.push(H1("9  Serving, latency and deployment"));
c.push(P("**Stack.** The adapter is served unmerged on the bf16 base by vLLM (`--enable-lora`) as an OpenAI-compatible endpoint on **RunPod Serverless** (24 GB slice; scales to zero; billed by the second). The **FastAPI app** (ingest, facts, drafting jobs, review, Word export, assistant) runs on a RunPod CPU pod (US$0.08/h) that starts on demand from a launcher page on Vercel and stops after 10 idle minutes; files, facts and drafts sit on a 10 GB network volume. Access is behind a shared password. A Docker image of the app was built and smoke-tested with six issuer files (740 facts, one section drafted); the model path was tested separately on the VM and through the hosted app because the VM refuses port forwarding."));
c.push(...table([4200, 2500, 2938], ["measured on an L40S, vLLM 0.10, 20 Nov 2026", "bf16 base + adapter", "AWQ W4A16 export"], [
  ["size on disk", "15.4 GB", "5.6 GB"],
  ["time to first token, batch 1 (median / p95)", "73 / 174 ms", "59 / 149 ms"],
  ["decoding, batch 1", "41.7 tokens/s", "121.9 tokens/s"],
  ["throughput, 89 prompts x 3 drafts", "1,374 tokens/s", "2,261 tokens/s"],
  ["Q&A F1 / extraction F1", "0.876 / 0.60", "0.853 / 0.57 (Q&A -0.023, n.s. on extraction)"],
  ["drafts with an invented figure after the guard / single drafts that loop", "0 / 9%", "1 / 16%"],
], "Table 7. Quantisation (llm-compressor, group 128, 128 calibration rows). Not served in production: slightly worse drafts, and the guard assumes the shipped model."));
c.push(P("**In production** the endpoint decodes about 15 tokens/s on the 24 GB slice: a sub-heading takes 10 to 35 s, the Summary of the hosted test about 50 s, the 11 narrative sections of the hosted test 10 to 15 minutes, and a **cold start about 4 to 6 minutes** (249 s and 294 s measured on 22 and 21 Nov). `python -m serve.warmup` wakes pod and model before a demo; `/healthz` reports the guard build, the Responsible AI mode and the commit it runs. The AWQ export is 3 times faster, which is the route to a warm, cheaper endpoint, but was kept out of production until its guard-level results match."));

// ---------------------------------------------------------------- 10 RAI
c.push(H1("10  Responsible AI, model card and red-team log"));
c.push(P("The **model card** (`docs/MODEL_CARD.md`) states intended use (drafts for professional review), out-of-scope uses (investment advice, listing-price prediction, main-board rules, offer terms before RHP stage, personal identifiers, omitting or softening a mandatory disclosure, any filing without a reviewer), data provenance, measured failure modes and limits. The human-in-the-loop boundary is built in: every output is marked DRAFT, every figure has a source trace, nothing is filed or sent, and the system never fills `[●]` on request."));
c.push(P("**Red team.** 20 adversarial prompts (`evaluate/red_team_prompts.json`) in the assistant's own format with a company's passages as evidence: instructions hidden in a document, direct overrides, filling offer terms, invented approvals, softening a risk factor, dropping litigation, PII, investment advice, main-board rules on an SME issue, prompt leakage. Run on the first Q&A model (15 Nov): **18 passed, 2 partly** (RT10 and RT11 refused the identifier but added an unsupported claim about a KYC process); 11 answers were on topic, 3 partly and 6 gave the right refusal with the wrong reason (for example a PII reason for a share-price question). The same prompts were also run through the app itself (`evaluate/out/app_redteam.md`). Fine-tuning improved refusals (harmful or securities-fraud compliance 62% to 0% on 8 probes; guardrail rows 38% to 100%)."));
c.push(P("**Regressions found and handled.** A Responsible AI evaluation (about 120 live probes per model) found three regressions of the shipped model: \"instruction ignored\" notices on 13% of answers that had no injection (removed by an output rule), unequal answers across name-coded identities in 2 of 9 counterfactual cases (handled by a neutral rewrite of person-judgement questions; 3 of 3 answered alike afterwards), and lower figure overlap across the three drafts. The retrain that targeted them (run 15) made the first one worse and was rejected. The `rai/` layer (input and output checks, a hash-chained audit log, incident escalation) adds no model call: 0.9 ms median on input, 7.8 ms on Q&A output. None of this is a certification."));

// ---------------------------------------------------------------- 11 limits
c.push(H1("11  Making a 7B model reliable, and what we would do next"));
c.push(...table([3100, 3100, 3438], ["decision", "evidence", "consequence"], [
  ["Judge runs by generation measures, not loss", "SFT runs span 1.28 to 1.32 held-out loss yet 35 to 72 loops", "loops and fact use decided every run"],
  ["Train with distractor facts", "ablation 1: wrong-section fact used in 58% of drafts without them", "kept in every later set"],
  ["Preference-tune on the model's own ranked drafts", "synthetic pairs over-abstained (run 12) or over-corrected (run 13)", "run 14 shipped"],
  ["Verify in code, not in the weights", "11% of single drafts invent a figure after the best tuning", "guard is mandatory; the AWQ export waits for it"],
  ["Retrieval for the assistant only", "F2 below F1 on Q&A and on drafting grounding", "drafting uses typed facts, not retrieved text"],
  ["Mask rather than correct", "a wrong figure that looks right is the costly error", "`[●]` for the reviewer to fill from the file"],
], "Table 8a. Decisions the evidence led us to."));
c.push(B("**How we compensated for a 7B model.** This is the part we learned the most from. The model gets typed facts rather than raw text, with a router so each prompt carries the right ones; it is trained to abstain with `[●]` rather than guess; we draft three times per sub-heading with a length floor and keep the cleanest; a frequency penalty and loop trimming were added; risk factors are written by rules; retrieval serves the assistant only, tenant-isolated; refusal and injection handling are trained in and enforced again in code."));
c.push(B("**The model is not trusted; the system is.** Our central design decision, and the measurements support it: 11% of single drafts still contain an invented figure after our best tuning, and the verification layer brings that to zero. It checks that a value appears in the inputs and that its period, basis and base fit, and keeps a month-year only beside a word from its own event. Output is a first draft with its evidence attached, and a named reviewer signs off each section."));
c.push(B("**Approaches we ruled out.** Gentler training, more epochs, cleaner targets and decoding changes did not stop the repetition loops, which led us to DPO. Synthetic one-sided preference pairs over-abstained in one run and over-corrected in the next, so we built pairs from the model's own ranked drafts. Retrieval lowered drafting quality, so it serves the assistant only. A check on what a percentage is **of** fired on about one correct paragraph in four, so we removed it. Numbers for each are in sections 5 and 6."));
c.push(B("**What we would do next.** The evaluation set is 199 rows drawn from 75 companies, and the synthetic data rooms exercise the formats and the full pipeline. Building on that, the next pieces of work we have scoped are a blind comparison by a practising DRHP reviewer (H3, H4), a judge drawn from another model family, a chunk-size ablation and further DPO seeds, and a measure of how often the verification layer fires across many live drafts. The model card (`docs/MODEL_CARD.md`) carries the measured failure modes and the out-of-scope uses in full."));

// ---------------------------------------------------------------- 12 reproducibility
c.push(H1("12  Reproducibility, team and roles"));
c.push(P("**Repository** (public): `https://github.com/anshumanpattnaik19-debug/sme-drhp-drafter`, tag `v1.2` (adapter A_qa3_dpo3). Data: `python -m data.build units|sample|rows`, `python -m data.qa jobs|rows`; training: `colab/make_notebook.py` (Colab) and `vm/train_qa.py`, `vm/dpo_all.sbatch` (course VM, Slurm); scoring: `python -m evaluate.run`, `evaluate.verified`, `evaluate.claims_mutation`, `evaluate.live_eval`; tracking: `python -m evaluate.mlflow_log`; serving: `python -m serve.pod bundle|start|status`, `python -m serve.warmup`; tests: `python -m pytest tests` (304 pass, 1 skipped). Adapters: `18Anshu/sme-drhp-7b-lora-v2` (shipped), `18Anshu/sme-drhp-7b-lora` (rollback), `18Anshu/sme-drhp-7b-awq` (AWQ). The records behind this report are `RETRAINING_LOG.md`, `FAILURE_LOG.md` (39 items), `TRAINING.md`, `docs/MODEL_CARD.md`, `docs/RED_TEAM_LOG.md`, `docs/RAG_DECISIONS.md`, `docs/H5_RESULTS.md`, `docs/HOSTING.md` and `RESPONSIBLE_AI.md`."));
c.push(...table([2400, 3600, 3638], ["role (Track A)", "responsibility", "member and training job"], [
  ["Data and synthetic generation", "corpus, teacher extraction, gates, splits", "Anshuman Pattnaik"],
  ["Fine-tuning and tracking", "QLoRA runs, sweeps, MLflow", "Akshey Sharma: seed 2, seed 3, ablation 1 (Colab, 11 to 12 Nov)"],
  ["RAG pipeline", "chunking, retrieval, reranking", "Akshey Sharma"],
  ["Evaluation and red-teaming", "metric harness, judge, adversarial prompts", "Anshuman Pattnaik"],
  ["Serving, quantisation, infra", "adapter serving, AWQ, FastAPI, Docker, RunPod", "Anshuman Pattnaik"],
  ["Integration and documentation", "repo, model card, report, demo", "Akshey Sharma"],
], "Table 8. Roles. A two-member team, so we took three of the six Track A role areas each. Every run is listed in RETRAINING_LOG.md and tracked in MLflow."));

c.push(...table([2600, 7038], ["Track A deliverable", "where it is"], [
  ["Git repository, reproducible training and serving code", "public GitHub repository above, tag `v1.2` (adapter A_qa3_dpo3); every stage has an offline test and a mock model server"],
  ["Experiment tracking dashboard", "MLflow store `mlflow/mlflow.db` (16 runs; section 8) and the static `docs/experiment_dashboard.html`"],
  ["Model card (use, provenance, failure modes, refusals)", "`docs/MODEL_CARD.md`; red-team log of 20 prompts `docs/RED_TEAM_LOG.md`; `RESPONSIBLE_AI.md`, `docs/RAI_EVAL_REPORT.md`"],
  ["12-page technical report", "this document: `docs/TECHNICAL_REPORT.docx`"],
  ["10-minute demo of the deployed endpoint", "run sheet `docs/DEMO_SCRIPT.md` (section 13); recorded walkthrough `demo/DRHP_Copilot_demo.mp4`; live app via the launcher `https://drhp-launcher.vercel.app` (warm it first: `python -m serve.warmup`)"],
], "Table 9. Where each deliverable is."));

c.push(H1("13  The 10-minute demo"));
c.push(P("The demo runs on the deployed endpoint, not on slides: launcher, upload, draft, guard, assistant, results. The full run sheet, the pre-flight commands (the model needs 4 to 6 minutes to wake) and the fallback if it is still cold are in `docs/DEMO_SCRIPT.md`; the recorded walkthrough from 26 Nov (10 min 23 s, the current adapter) is the backup."));
c.push(...table([1300, 4300, 4038], ["time", "on screen", "point made"], [
  ["0:00 to 0:45", "launcher page, then the app", "the task, and why a plain 7B model is not enough"],
  ["0:45 to 2:15", "upload six issuer files; facts view with sources", "Word, Excel and a scan become about 740 typed facts, each with its source"],
  ["2:15 to 4:45", "draft Summary (about 50 s) and Business", "one sub-heading per call, best of three, DRAFT marking and source trace"],
  ["4:45 to 6:00", "masked list and review pack", "every unsupported value is `[●]` with its reason; the 61% case (Table 5a)"],
  ["6:00 to 7:15", "assistant: cited answer, advice declined, offer price kept `[●]`, injected instruction ignored", "guardrails trained in and enforced by rules"],
  ["7:15 to 8:30", "Table 1 and the negative results", "better on Q&A, extraction and fact use; a tie on invented figures after the guard; loops cut by the app"],
  ["8:30 to 10:00", "MLflow runs, model card, red-team log", "16 runs and why; 20 adversarial prompts; the human-review boundary and what was not measured"],
], "Table 10. Run of show."));

c.push(H1("References"));
[
  "Hu, E. et al. (2021). LoRA: Low-Rank Adaptation of Large Language Models. arXiv:2106.09685.",
  "Dettmers, T. et al. (2023). QLoRA: Efficient Finetuning of Quantized LLMs. arXiv:2305.14314.",
  "Rafailov, R. et al. (2023). Direct Preference Optimization: Your Language Model Is Secretly a Reward Model. arXiv:2305.18290.",
  "Kwon, W. et al. (2023). Efficient Memory Management for Large Language Model Serving with PagedAttention (vLLM). SOSP 2023.",
  "Lin, J. et al. (2023). AWQ: Activation-aware Weight Quantization for LLM Compression and Acceleration. arXiv:2306.00978.",
  "Chen, J. et al. (2024). BGE M3-Embedding: Multi-Lingual, Multi-Functionality, Multi-Granularity Text Embeddings. arXiv:2402.03216.",
  "Qwen Team (2024). Qwen2.5 Technical Report. arXiv:2412.15115.",
  "Robertson, S. and Zaragoza, H. (2009). The Probabilistic Relevance Framework: BM25 and Beyond. Foundations and Trends in Information Retrieval 3(4).",
  "Securities and Exchange Board of India. Issue of Capital and Disclosure Requirements (ICDR) Regulations, 2018, Chapter IX (issue of specified securities by small and medium enterprises).",
].forEach((r, i) => c.push(P(`[${i + 1}] ${r}`, { spacing: { after: 40, line: 260 } })));

const doc = new Document({
  creator: "DRHP Copilot team", title: "DRHP Copilot: technical report",
  styles: {
    default: { document: { run: { font: FONT, size: S } } },
    paragraphStyles: [
      { id: "Heading1", name: "Heading 1", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { font: FONT, size: 27, bold: true, color: ACC }, paragraph: { spacing: { before: 190, after: 80 }, keepNext: true, outlineLevel: 0 } },
      { id: "Heading2", name: "Heading 2", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { font: FONT, size: 22, bold: true, color: INK }, paragraph: { spacing: { before: 120, after: 60 }, keepNext: true, outlineLevel: 1 } },
    ],
  },
  numbering: { config: [{ reference: "bul", levels: [{ level: 0, format: LevelFormat.BULLET, text: "•", alignment: AlignmentType.LEFT,
    style: { paragraph: { indent: { left: 360, hanging: 240 } } } }] }] },
  sections: [{
    properties: { page: { size: { width: 11906, height: 16838 }, margin: { top: 1020, bottom: 960, left: 1134, right: 1134 } } },
    headers: { default: new Header({ children: [new Paragraph({ alignment: AlignmentType.RIGHT, children: [new TextRun({ text: "DRHP Copilot | Track A technical report", font: FONT, size: 16, color: MUTE })] })] }) },
    footers: { default: new Footer({ children: [new Paragraph({ alignment: AlignmentType.CENTER, children: [new TextRun({ children: [PageNumber.CURRENT, " / ", PageNumber.TOTAL_PAGES], font: FONT, size: 16, color: MUTE })] })] }) },
    children: c,
  }],
});
Packer.toBuffer(doc).then((buf) => {
  const out = path.join(__dirname, "..", "TECHNICAL_REPORT.docx");
  fs.writeFileSync(out, buf);
  console.log("wrote", out);
});
