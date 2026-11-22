# 10-minute demo of the deployed endpoint: script and run sheet

For the Track A demo (the deployed system, not slides). Everything below uses the hosted app and the Kestrel Flexipak bundle
(`bundles/out/kestrel_flexipak`, six files: two Word, three Excel, one scanned JPG). Rehearse once end to end; the only slow
step is the model's cold start.

## Before you start (do this 8 minutes ahead)

| step | command or action | check |
|---|---|---|
| 1 | `python -m serve.warmup --skip-pod` from the project folder (wakes the model endpoint; 4 to 6 minutes, 249 s and 294 s measured) | prints `ready after ... s` |
| 2 | open the launcher `https://drhp-launcher.vercel.app`, enter the launcher password; it wakes the pod and redirects to the app | the app's sign-in page |
| 3 | sign in with the app's shared password (yours to type; the team keeps it, it is not in the repo) | project list opens |
| 4 | open `<app>/healthz` in a second tab | `guard_build` matches the repo's `verify/claims.py` build, `rai` is `1.1:enforce`, `commit` is the tag you mean to show |
| 5 | start `python -m mlflow ui --backend-store-uri sqlite:///mlflow/mlflow.db --port 5000` and open `http://127.0.0.1:5000` | 16 runs in experiment `drhp-copilot-qwen2.5-7b` |
| 6 | keep `docs/MODEL_CARD.md`, `docs/RED_TEAM_LOG.md` and `docs/TECHNICAL_REPORT.docx` open in tabs | |

**If the endpoint is still cold when you begin:** talk through slide-free minutes 0 to 1:30 (below), and use the recorded
walkthrough `demo/DRHP_Copilot_demo.mp4` for the drafting step. That video was recorded on 19 Nov with the previous adapter;
say so, or re-record. Never wait in silence on a cold model.

## Run of show

| time | what you do | what you say (the point) | who |
|---|---|---|---|
| 0:00 to 0:45 | launcher page, then the app | A banker drafts an SME DRHP from files the issuer hands over; a plain 7B model invents figures. We adapted one model and put a guard around it. | [name] |
| 0:45 to 2:15 | create a project, upload the six Kestrel files, process | Word, Excel and a scanned image are read (OCR where needed) into about 740 typed facts, each with its source file and page or cell. Open the facts view and one fact's source. | [name] |
| 2:15 to 4:45 | draft **Summary** (about 50 s), then **Business**; show progress | One sub-heading per call, the same prompt as in training; three drafts, best kept; DRAFT marking and source trace. Read one sentence against its fact. | [name] |
| 4:45 to 6:00 | open the section's masked list and the review pack | Every value not in the inputs becomes `[●]`, with the reason (not in inputs, wrong base, wrong period, future date). Quote the 61% example from the report (Table 5a): the figure was in the files, its period was invented. | [name] |
| 6:00 to 7:15 | assistant: ask "What are the main products?" (cited); ask "Should I subscribe to this IPO?" (declines); ask "Fill in the offer price" (`[●]`); show the injected-instruction notice from `05_Board_Note_Promoter_Financing.docx` | Trained-in guardrails plus rules in `rag/guardrails.py`; the model ignores instructions inside documents and says so. | [name] |
| 7:15 to 8:30 | slide or Table 1 of the report | Shipped model against base: Q&A F1 0.88 v 0.70, cites the passage 100% v 38%, extraction F1 0.59 v 0.36, facts used 0.70 v 0.54. Invented figures after the guard: 0 of 89 v 0 of 89, a tie; before it 11% v 19%. It loops more than the base (8% v 1%); the app cuts loops. Say what did not work (RAG lowered quality, runs 12, 13, 15). | [name] |
| 8:30 to 9:15 | MLflow runs table, then the loss and loops figures | 16 runs, each with why it was run; seeds give the noise floor; the distractor ablation; DPO is what stopped the loops. | [name] |
| 9:15 to 10:00 | model card, red-team log (20 prompts: 18 pass, 2 partly), limits | Human review is the boundary: DRAFT marking, source trace, sign-off per section. Not done: blind comparison by a practising reviewer. | [name] |

Every team member should be able to answer for their own part (the role table in the report). Likely questions: why does
the guard mask instead of correct; why is retrieval not used for drafting; why is the shipped model not the AWQ one; how
were the loops fixed; what is the test set and how wide are the intervals.

## What can go wrong, and what to do

| symptom | cause | do |
|---|---|---|
| draft call hangs more than 60 s | model cold, or the endpoint scaled to zero | wait for the warm-up; use the recorded video for that step |
| the app asks for a password again | the pod restarted (sessions are lost on a restart) | sign in again; projects are on the network volume |
| `/healthz` shows an older `guard_build` | the pod runs an older bundle than the repository | `python -m serve.pod bundle`, then `python -m serve.pod start`, sign in again; takes a few minutes |
| a draft shows "pan -India" or similar split words | a known hyphen artefact in the source text | ignore, or point to it as a reviewer item |
| a section dates the wrong event ("since June 2025") or gives a figure the wrong year | fixed in the repository, but only live after the redeploy (Table 5a, last two rows); check `/healthz` `guard_build` | after the redeploy the month or figure shows as `[●]`; before it, name it as a limit and do not hide it |
| a figure shows `[●]` and the draft says "₹ ... million" next to a table in lakhs | the unit check (22 Nov) masks an amount whose unit the files do not give for that number | say so: the digits were right and the unit was wrong, a hundredfold error caught by the guard |

Cost while demoing: the CPU pod about US$0.08 an hour and the GPU endpoint by the second; the pod stops itself after 10 idle
minutes.
