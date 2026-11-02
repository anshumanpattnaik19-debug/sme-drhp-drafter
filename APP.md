# DRHP Studio: the drafter's web UI

A local web app in front of the pipeline in PLAN.md: upload the issuer's files, check the extracted facts,
fill the offer details, draft the SME DRHP section by section, resolve the review pack, export a `.docx`.

## Run

```
cd sme_drhp_drafter
pip install -r requirements-app.txt
python -m uvicorn serve.app:app --port 8765
```

Open http://localhost:8765. The built UI in `ui/dist` is served by the same process.

To change the UI (React + TypeScript + Tailwind, in `ui/`):

```
cd ui
npm install
npm run dev        # http://localhost:5173, proxies /api to port 8765
npm run build      # writes ui/dist
```

## Screens

| screen | what the user does |
|---|---|
| Assistant | chat about the project (Claude-style); also a panel on every screen (**Ask** button or Ctrl+J). Answers cite the issuer's files; commands such as *draft Our Business* or *fill offer details from the documents* run directly |
| Projects | create one project per issuer (name, BSE SME / NSE Emerge, lead manager) |
| Documents | drag files or a whole folder; each file is read (PDF, scanned PDF, Word, Excel, images), classified and its facts extracted; preview, extracted text with page/cell, reclassify, reprocess |
| Offer details | board-approved terms and parties, filled automatically from the note on the proposed issue, intermediaries and KMP schedules after processing (each value shows its file); DRHP-stage fields stay `[●]` |
| Facts | every typed fact with file and location; search and filter, edit inline, add facts, mark reviewed |
| Draft | 35 sections in SME order; ICDR-format tables built from the issuer's schedules, risk factors from red flags, drafting briefs where prose is still needed; edit; checks per section; **sign-off** by the reviewer |
| Review | missing inputs, ungrounded figures, checklist gaps, cross-file mismatches, unread pages, disclosure flags |
| Export | `.docx` with cover, TOC, DRAFT header, source comments and the review pack annexure |

## Who writes what

| part | writer | file |
|---|---|---|
| tables (offer structure, capital structure, objects, financials, borrowings, litigation, approvals, board, KMP, RPT…) | code, from the issuer's Excel and Word schedules | `draft/builders.py` |
| risk factors | rules: one per red flag found in the files (expired approvals, lender consent, customer concentration, RPT, litigation, contingent liabilities, IP, EoM, forex…) | `draft/red_flags.py` |
| narrative sub-headings | the fine-tuned SLM when connected; otherwise a **drafting brief** (the routed facts with sources), never invented prose | `draft/writer.py` |
| boilerplate | templates | `draft/writer.py` |

Checks (`verify/checks.py`): each figure is *traced in place* (in the facts or schedule its block cites), *weak*
(only found elsewhere) or *not found*; checklist items are *covered* only when a builder produced them, *to confirm*
when prose merely mentions them. A section counts as done only after the reviewer signs it off; editing or
redrafting withdraws the sign-off.

## Assistant and agentic RAG (`rag/`, `serve/chat.py`)

* **Index** (`rag/index.py`): every issuer file chunked with provenance (~110-word passages that do not cross PDF
  pages; each schedule as caption + header + up to 8 rows). BM25; dense retrieval fused by RRF when
  `DRHP_DENSE_MODEL` names an installed sentence-transformers model (e.g. `BAAI/bge-m3` on the GPU box).
* **Agent** (`rag/agent.py`): plan (sub-questions, section match) → tools (`search_documents`, `find_table`,
  `search_facts`, `read_section`, `review_issues`) → reflect (broaden the query when evidence is thin) → answer with
  numbered citations → verify (every figure in the answer must appear in the cited evidence). With a model
  connected, the model chooses further tool calls (JSON, at most 4) and writes the answer; offline, a rule-based
  planner and an extractive answer are used and labelled as such. The steps stream to the UI as a "Researched" trace.

## Model

Settings (gear icon): **offline** (default, no GPU) or a **fine-tuned SLM endpoint** (any OpenAI-compatible server,
e.g. vLLM serving the merged Qwen2.5-7B adapter, PLAN.md section 8). The endpoint writes narrative sub-headings and
assistant answers; tables, risk factors and templates are built the same way either way.

## What is a stand-in

| stage | here | production (PLAN.md) |
|---|---|---|
| reading | PyMuPDF, python-docx, openpyxl, RapidOCR on CPU | docling, PaddleOCR, Qwen2.5-VL for image tables |
| fact extraction | rules (`extract/rules.py`), same typed-fact schema | fine-tuned SLM, skill 1 |
| SLM narrative | drafting briefs or the endpoint | fine-tuned SLM + RAG precedent |
| retrieval | BM25 over the project's files | + bge-m3 dense, bge-reranker, train-split precedents |
| checklist | placeholder items in `draft/outline.py` | the reviewer's list from Week 0 |
| `.docx` | python-docx | `drhp_template/lib.js` styling |

Data stays on this machine in `sme_drhp_drafter/workspace/` (one folder per project).

## Tests

```
python -m pytest tests -q
```
