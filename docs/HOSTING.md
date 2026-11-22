# Hosting the app at a public link, behind a shared password

The app (FastAPI backend and the built UI) runs on a free Hugging Face Docker Space; the model runs on the RunPod
Serverless endpoint (docs/RUNPOD.md). Everyone with the link sees a sign-in page first.

## How it is protected

- **Shared password on everything** (`serve/auth.py`): with `APP_PASSWORD` set, every page and every `/api/` route
  needs a session cookie; without one, pages go to `/login` and the API answers 401. The cookie holds an expiry and an
  HMAC, never the password. Five wrong passwords from one address in ten minutes give 429 until the window ends.
- **The RunPod key stays on the server** (`serve/store.pinned`): `DRHP_MODEL_URL` and the key (`RUNPOD_API_KEY`) come
  from the Space's settings. Settings in the app cannot change the model address or the key, the Settings "Test" button
  always uses the pinned address, and the key is never written to the workspace.
- **Secrets are Space secrets**: `RUNPOD_API_KEY`, `APP_PASSWORD` and `APP_SESSION_SECRET` are set through the Hub API by
  `python -m serve.space deploy`, from `.runpod.env`. They are not in the repository, the image or any log.
- **Cost cap**: the RunPod endpoint has at most one worker and none always on; the app's status poll starts no worker.

## Deploy

1. `.runpod.env` holds `HF_TOKEN` (write access), `RUNPOD_API_KEY` and `APP_PASSWORD`.
2. `python -m serve.space deploy` creates or updates the Space `<user>/drhp-studio`, sets its secrets and variables, and
   uploads the code with `docker/Dockerfile.space` (port 7860, user 1000). The build takes a few minutes.
3. `python -m serve.space status` shows the build or run state and the app address `https://<user>-drhp-studio.hf.space`.

## Limits

- The Space is public so the link works without a Hugging Face account: its source code (not data, not keys) is
  readable on the Space page.
- Free Spaces sleep after 48 hours without visits and wake on the next visit (a minute or two); uploaded files and drafts
  are kept only until the Space restarts.
- After the model has been idle, the first answer waits for a RunPod cold start (about 4–5 minutes in the test).

## Tested locally (19 Nov 2026)

The Space image (`docker/Dockerfile.space`) built and ran as user 1000 on port 7860 with the key passed in from the
environment: `/` redirected to sign-in, `/api/projects` gave 401 for reads and writes, a wrong password gave 401, the
right one loaded the UI, Settings showed the RunPod URL with the key hidden, and the assistant answered from two uploaded
issuer files with the model (330 s including the cold start). The password did not appear in the container log.
Tests: `tests/test_auth.py`.

## On a RunPod CPU pod, started on demand (chosen 19 Nov 2026)

A client link needs no RunPod key, so the app runs on a CPU pod (a load-balancing serverless endpoint would need the
RunPod key on every request). `serve/pod.py` drives it through the RunPod API; nothing is always on:

| piece | where it runs | cost |
|---|---|---|
| the app (password gate, UI, API) | RunPod CPU pod, 2 vCPU, 8 GB (`cpu3g`) | $0.08 per hour while running; $0 when stopped |
| the model | RunPod Serverless endpoint (docs/RUNPOD.md) | per second while answering; $0 idle |
| the launcher page | free Hugging Face Space (`launcher/`, no app code) | $0 |

- **Start, stop, status:** `python -m serve.pod start | stop | status` (also `bundle` and `create` for the first setup).
  The pod's link is `https://<pod id>-7860.proxy.runpod.net`. A stopped pod resumes on the same host, so the link stays
  the same; it changes only if the pod is terminated and created again.
- **Without a terminal:** the launcher page asks for the same password, starts the pod if it is stopped, shows progress
  while the app installs (about 3–4 minutes) and then opens the app. It holds a RunPod key that can manage pods, never
  shown to the browser.
- **Auto-stop:** the app stops its own pod after `POD_IDLE_MINUTES` (10 by default; `create --idle N`) without use. The
  UI's status poll and the sign-in page do not count as use, and a running job (processing, drafting) keeps the pod up.
- **Code delivery:** the pod runs the public `python:3.12-slim` image and at each start downloads the app bundle (code
  and built UI) from a private Hugging Face repo with the token held as a RunPod secret; the token is removed from the
  environment before the app starts.
- **Keys:** `RUNPOD_PODS_KEY` (a RunPod key with Pods read/write) is separate from the model key. In the pod both are
  RunPod secrets; on the launcher Space the pods key and the password are Space secrets.

## Run on 19 Nov 2026

- Pod `bhywyk4u8scf6a` created (2 vCPU, 8 GB, $0.08/h while running, auto-stop after 30 idle minutes). Link:
  `https://bhywyk4u8scf6a-7860.proxy.runpod.net`; it stays the same across stop and start. Tested live: no password gives a
  redirect (pages) or 401 (API), a wrong password 401, the right one 200; the pod reaches the model endpoint.
- `python -m serve.pod launcher` failed: Hugging Face now returns 402 for a Docker Space on free cpu-basic ("requires a PRO
  subscription"); only Static Spaces are free, and a static page cannot hold the pods key. So there is no launcher link yet:
  start the pod yourself with `python -m serve.pod start` before the client opens the link. Options: HF PRO, or the launcher
  on another free host (not set up).

### Launcher on Vercel (19 Nov 2026)

Hugging Face now wants PRO for a Docker Space, so the launcher (`launcher/`, a small FastAPI page, the only thing hosted
there) runs on Vercel's free Hobby plan: Vercel finds the FastAPI `app` in `launcher/app.py` and `launcher/requirements.txt`;
`launcher/vercel.json` sets the function time limit to 60 s. The app itself stays on the RunPod pod. `launcher/Dockerfile`
is for a Space and is not used by Vercel.

Environment variables on the Vercel project: `APP_PASSWORD`, `RUNPOD_PODS_KEY`, `LAUNCHER_SECRET` (any long random string),
and the two non-secret ones printed by `python -m serve.pod launcher-env` (`POD_NAME`, `POD_BODY`). Deploy from the `launcher`
folder (`vercel --prod`). Check Deployment Protection in the project settings: the production address must be open to
visitors (the launcher asks for the password itself). The wrong-password lockout is kept in memory per function instance, so
it is a speed bump here, not a hard limit.

**A stopped pod may not restart.** On 19 Nov 2026 RunPod answered `400 There are not enough free memory on the host machine
to start this pod` for a stopped pod, three times in a minute; a few minutes later the same pod started fine. A stopped pod
only resumes on its own host, so the launcher finds the pod by name (`POD_NAME`), starts it, and if RunPod refuses with a 4xx
it deletes that pod and creates a new one from `POD_BODY`. The app's address can then change (the launcher sends people to the
current one), and anything saved in the old pod is lost. Tests: `tests/test_pod_launcher.py`. Not yet run on Vercel.

### Deployed on Vercel (19 Nov 2026)

Project `drhp-launcher` in the team `anshumanpattnaik19-debugs-projects` (Hobby plan), production address
`https://drhp-launcher.vercel.app`. Deployed from `launcher/` with `vercel deploy --prod`; variables `APP_PASSWORD`,
`RUNPOD_PODS_KEY`, `LAUNCHER_SECRET`, `POD_NAME`, `POD_BODY` are production secrets. Tested through a protection-bypass
secret (revoked afterwards): page 200, wrong password 401, `/status` without a cookie 401. The right-password path (wake
the pod, redirect to the app) was run only against RunPod from the laptop and in tests, not yet from Vercel.

New projects start with Vercel Authentication on for every address, so a visitor without a Vercel login is redirected to
Vercel's sign-in (HTTP 302). It has to be switched off in the project's Deployment Protection settings before a client can
open the link; the launcher asks for its own password. The access token is `VERCEL_TOKEN` in `.runpod.env`, scoped to the
team, 7 days (to 26 Nov 2026); delete it at vercel.com/account/tokens when the deployment is final.

Vercel Authentication was switched off for `drhp-launcher` on 19 Nov 2026 at the owner's request; the public address then answered 200 without any Vercel login, a wrong password 401, `/status` without a cookie 401.

### Storage (19 Nov 2026)

The pod's container disk is wiped whenever the pod stops, so the workspace (uploads, facts, drafts, chat) lives on a **10 GB RunPod
network volume**, `fckwcjlswd` in **US-GA-2**, mounted at `/workspace` (`DRHP_WORKSPACE=/workspace/drhp`); about $0.70 a month,
billed whether or not a pod runs. It is attached through `mounts.network` in the pod-create body (`networkVolumeId` is not accepted).
Pods must be created in the volume's data center (`dataCenterIds`), so if US-GA-2 has no free CPU pod a new one cannot start until
it does; moving the volume means copying the workspace, since a volume cannot change data center. Deleting a pod never deletes
the volume.

Proof, with the open `/healthz` start counter kept on the volume: 1 at the first start, 2 after the pod stopped itself (10 idle
minutes, measured: stopped 10 min after the app started) and was started again, 3 on a brand-new pod after the old one was deleted.
`/healthz` shows counts only: boot count, number of projects, idle seconds and the idle limit.


## Before a demo (20 Nov 2026)

`python -m serve.warmup` starts the app pod (re-creating it on another host if its own has no room, which changes its
address: the launcher finds it by name) and sends the model one 1-token request, which starts a worker. Measured on 20 Nov
2026: pod ready in 29 s, model answered after **389 s**, although RunPod's `/health` reported a worker as "idle/ready"
beforehand, so `/health` does not show whether a worker has the model loaded. Run it at least 10 minutes before a demo;
`--keep-warm 30` then keeps one worker up for 30 minutes (one tiny request every 20 s, about $0.75 an hour, capped at
120 minutes, stops by itself). It changes no endpoint setting.

## Which code is live

`/healthz` (open, counts only) reports `guard_build` (a hash of the guard's source), `rai` (Responsible AI policy version and
mode) and `commit`: the git commit the bundle or image was built from, with `+N` when N files differed from it. The bundle
records it in `BUILD_INFO.json` (`serve/pod.py`); the Docker images take it as a build argument
(`--build-arg GIT_COMMIT=$(git rev-parse HEAD)`).

## Hosted test with the live model (20 Nov 2026)

Signed in to the hosted app (`rb55yds7dwuxsg`, commit `f066c0f`, guard `cf30665405c3`, Responsible AI `1.1:enforce`) in
Chrome, created a project, uploaded the six issuer files of the container test (two Word, three Excel, one scanned JPG) and
drafted `Summary of the Offer Document` with the fine-tuned model behind the endpoint.

| Step | Result |
|---|---|
| Model warm-up (`python -m serve.warmup --skip-pod`) | answered after 311 s (cold start); `/health` again showed a worker "ready" beforehand |
| Upload and processing | 6 of 6 read, 740 facts, OCR on the JPG |
| Drafting | finished in about 50 s; offer table and objects table built from the files; prose under Industry |
| Checks panel | 6 figures traced in place, 1 weak (found elsewhere: "22000" of FSSC 22000), 0 not found, 12 placeholders, 2 sub-headings left as briefs, mandatory items 6 of 9 |

Defects seen in the prose (failure log #39): the last paragraph degenerates into a run-on list of risks with split words
("t o write-off s"); a page footer "13 | P a g e" appears in the prose; and 68.70% is stated as the share of adhesives, zippers
and spouts in raw material cost, where the file gives it as raw materials over revenue from operations in FY 2025-26. The
guard checks that each value appears in the inputs, not what it is attached to, so all three pass it.

### Fix and re-test (20 Nov 2026, same evening)

Three guard rules were added (`draft/writer.py`, `verify/checks.py`, tests in `tests/test_degenerate_and_base.py`):
`cut_degenerate` cuts a draft before the first sentence with three or more split words that the inputs do not themselves hold
(a PDF can read "Technologie s"), or with more than 120 words and ten or more semicolons, and counts it as a loop for
best-of-3; `strip_page_footers` removes "13 | P a g e" and "Page 4 of 120"; `mask_misbased_percents` masks a percentage whose
base after "% of" shares no word with the base its source gives for that figure (revenue, income, turnover and sales count
as one word; a source without a "% of" base is not checked).

On the 89 app-format test drafts (best-of-3 file, live file and the base) every measure is unchanged: 0 of 89 after the
guard, the same masked values, fact use and loops. The rules fire on none of those drafts (one false cut on a source-held
split word was found and fixed before this), so the test set says nothing about how often these failures happen.

Redeployed (`guard_build` 4e9194a8b366, commit `f066c0f+5`: uncommitted) and redrafted the same section on the hosted app
(Draft 2, a fresh sample): no run-on text, no footer, and the guard masked "68.70% of cost of goods sold" as
`misplaced_base`. The same sample also wrote "about 61% of revenue on average over the last three years" where the file gives
61.27% for FY 2025-26 and, in another paragraph, a rounded "about 61%" with no period. (Corrected on 21 Nov: the rounding is the
source's own; what the model invented was the period, "on average over the last three years". The next section closes that.)

## Period and basis of a figure (21 Nov 2026)

`verify/claims.py` (`mask_period_claims`, wired into `guard_draft` beside the "% of" rule) checks what a percentage or money
amount in prose is stated FOR. It looks the number up in the evidence (typed facts: label, snippet, typed period; passages: the
sentence that holds it) and masks it as `[●]` (`period_basis`) only when EVERY piece of evidence contradicts the clause:

- **basis:** "on average", "over the last three years", CAGR, a "five-year" window, when no evidence says so; "average" binds only
  a figure within 30 characters (15 before it), a window phrase within 90, and not a clause that names its own year, nor a
  sentence that lists two or more years (a per-year list is not an average);
- **fiscal year:** the year a figure is given for ("... for FY 2024", "₹x lakh (FY 2024)", a lead-in "In FY 2025-26,"), else the
  clause's years, against the source's: its typed period, else the year label nearest the figure in its text. A source silent
  about its year does not lend a distinctive figure (3 or more digits) to another year; for 1 to 2 digit values it still counts,
  because a value like 25% recurs for unrelated things;
- **half-year or quarter** against a full year.

Also closed in `verify/checks.py`: "17 per cent" and "17 percent" are read like "17%", and "87 people" like "87 employees".

**Measured** (`python -m evaluate.claims_mutation workspace/*/facts.json`, 56 percentage and money facts of the Kestrel projects,
each tested in its project's 2,170 facts):

| Test | Result |
|---|---|
| A correct sentence from the fact ("In FY 2025-26, the X was 61.27%") masked | 0 of 90 on the Kestrel inputs, 0 of 118 on the larger project (23 Nov numbers; 0 of 57 on the earlier sample, see below) |
| The same with the year moved by two | 84 of 89 and 107 of 116 caught (47 of 57 on the earlier, smaller sample) |
| "On average over the last three years, ..." added to a single-year figure | 88 of 90 and 116 of 118 caught (57 of 57 on the earlier sample) |

The 8 misses are values of 0 to 2 digits (₹0 lakhs, ₹-50 lakhs, ₹0.2 lakhs), skipped on purpose. On the real model drafts of the 89
test prompts the rule fired 8 times in all: 0 on the shipped adapter's best-of-3 file, 1 on its live run, 1 on the base model, 6 on an
earlier fine-tuned adapter. I read every one against its evidence and each is a real period error (FY 2024's revenue stated for
FY 2023, a customer count shown as "123%", FY 2025-26 growth given as a FY 2026-27 forecast). Scores of the 89 drafts are
unchanged for the three models scored (0 of 89 after the guard; masked values and fact use identical, the base gains one masked
value). 251 tests pass. The test prompts are mostly tables and few sentences name a year, so 8 firings do not say how often the
live app needs the rule.

While tuning, the first version masked 65 values in the 89 drafts, nearly all wrong ("aged 40 years" counted as a three-year
window; a per-year list read as an average; "face value of ₹10" bound to "weighted average cost of acquisition"; a year in
parentheses attached to the next figure). Each is now a regression test in `tests/test_claims.py`. A first sentence splitter also
dropped every sentence containing a decimal such as "61.27"; fixed.

**Tried and not shipped: what a figure is OF** (a figure under another line item's label, "EBITDA stood at ₹5,181.90 lakh" for
revenue). A clause-versus-label word match caught 44 of 52 swaps made up from the facts, but on real drafts nearly every hit
was a correct figure ("Underwriting commission 224 52.01%": a table fact's label is its column header; "holds 16,42,570 shares
representing 9.64%": a count and its percentage in one clause). Precision was about 1 in 4, so it was removed. Only the
"N% of X" basis rule remains. A fix needs the table row and column of each fact, which the facts do not carry.

**Not covered:** the subject of a figure beyond "N% of X"; a period the draft leaves out; claims in tables (those have the
column and row checks); numbers written in words. The check is rules on text, not an understanding of the document: a reviewer
still reads every section against its sources.

### Live re-check and two fixes (22 Nov 2026)

All 11 SLM sections of the hosted project (Kestrel Flexipak, 740 facts) were redrafted by the live endpoint (warm-up 249 s; 0 job
errors; risk factors by rules, the other ten by the model). The guard masked 4 values (2 identifiers in the business section, 1
misplaced base in the promoters section, 1 figure in the MD&A) and no `period_basis` hit fired. Reading the 18 sentences that tie
a percentage or amount to a period, and every year after "since", found two errors the guard let through:

1. **Swapped years in a table row.** "Revenue per MT of laminated output increased from ₹149.74 in FY 2023-24 to ₹159.02 in FY
   2024-25 and ₹160.55 in FY 2025-26". The facts say 159.02 is FY 2023-24 and 149.74 is FY 2024-25. Cause: every fact of a table
   row carries the whole row as its snippet, so `_evidence` added each neighbouring number to each fact with the fact's own typed
   period, and 149.74 found "FY 2023-24" in a sibling's evidence. Fix: a number beside the fact in its snippet takes its year from
   the snippet only (silent when the snippet names none). The same re-run exposed a second defect, a sign mismatch ("₹-0.42 lakhs"
   against the fact -0.42), fixed by matching on magnitude. Both are regression tests (`test_a_sibling_in_the_same_row_does_not_lend_its_year`,
   `test_a_negative_value_is_matched_by_its_magnitude`); replayed on the real facts, 149.74 and 159.02 are masked and 160.55 kept.
2. **A certificate's expiry read as a start.** "FSSC 22000 v6 certified since 2027": the licence table gives 2 November 2027 as the
   expiry (the history says certified in 2025). New rule `mask_future_dates` (`verify/claims.py`): a calendar year later than the
   latest reporting date in the inputs ("ended", "as at", "as of"; here 2026), after "since" or a verb of beginning, becomes
   `[●]` (kind `future_date`). It does nothing when the inputs name no reporting date. It matched 7 times in 1,585 training and
   test rows (filed prose), none after 2025.

**Measured again** after the first two fixes (earlier, smaller sample): mutation test 0 of 57 correct sentences masked, 47 of 57 shifted years caught, 57 of 57 invented
averages caught; the rule now fires 10 times on the five sets of live-evaluation drafts (1 on A_qa3_dpo3 best-of-3, 6 on the earlier
adapter, 1 + 2 on the base; the two new ones are a quarterly claim ("8.6% in Q3 FY25") against full-year evidence); 257 tests pass.
I read 9 of the 10 against their evidence and each is a real year or basis error; the tenth ("123%") I did not read in full.

**Still open:** "pan -India" style split hyphens; a figure whose subject is wrong while its period is right.
The fixes are in the repository (uncommitted at the time of writing) and the pod runs them after the next redeploy
(`python -m serve.pod bundle`, then `start`; the pod's session is lost on a restart).

### Second live re-check, on guard build 6e61d7d89e7e (22 Nov 2026)

The ten model-written sections were redrafted again on the redeployed pod (job `je0a1509405`; 10 of 10 done, 0 errors, about 8
minutes; Business alone took about 4). The guard masked 8 values (3 dates, 2 figures, 2 identifiers, 1 misplaced base) and again no
`period_basis` hit fired. I read the 21 sentences that tie a percentage or an amount to a period and the 58 that hold a date
against the facts. Two errors got through again, both in code that was live:

1. **Revenue per MT, wrong year.** "Revenue per MT of laminated output (₹ per kg) increased from ₹149.74 in FY 2023-24 to
   ₹160.55 in FY 2025-26 and was ₹175.5 in the six months ended 30 September 2026." The facts: 149.74 is FY 2024-25 (159.02 is
   FY 2023-24). Reproduced offline on the real facts (three copies of the bundle) and traced to the half-year flag: the clause
   ends with a six-month figure, and the guard applied "half-year" to every figure of the clause, so a neighbour tagged "H1 FY27"
   (whose snippet carries the whole row) counted as support for 149.74. Fix (`verify/claims.py`): a figure with its own year label
   is half-year only when the words after it say so; a number that sits beside a fact in its snippet takes its half-year flag from
   the snippet, as it already took its year; a year label belonging to another figure of the clause is not lent to a figure
   without one. Regression test `test_a_six_month_figure_in_the_clause_does_not_make_the_year_figures_half_year`.
2. **A month taken from the wrong event.** "With FSSC 22000 certification since June 2025": the history row reads "2025 | FSSC
   22000 certification; revenue crossed ₹100 crore; activated-carbon VOC control unit installed (June 2025)", so June 2025 is the
   VOC unit's. New rule `mask_event_dates` (kind `event_date`): a month-year without a day is kept only if some source holds it
   beside at least one content word (first four letters) of the words leading into it; the sources' items are cut at ";", "|"
   and line ends, so a date in brackets stays with the item it closes. It does nothing when no source holds the month-year
   (that is `mask_ungrounded`'s case) or when the date has a day. The Kestrel inputs hold 8 month-year items, the four test
   bundles 8 to 26; a source item read back as a sentence is never masked (0 of 64), and the rule masks the FSSC sentence and
   keeps "commissioned in June 2025" for the VOC unit. Four tests in `tests/test_claims.py`.

The other 19 sentences I checked each trace to a source (complaints 0.42% / 0.57%, raw materials 68.70%, utilisation 81.00%, 540
million pieces, the capex split, promoter loans of ₹550 lakhs in 2020, the CFO's joining date, and so on). One imprecision the
guard cannot see: the summary says revenue "crossing ₹100 crore in FY 2025-26"; the history row gives 2025 and FY 2024-25 revenue
was already ₹108 crore, so the milestone probably belongs to the year before. A reviewer item. 262 tests pass.

**Redeployed the same day** (`serve.pod bundle`, `stop`, `start`; the pod had already idled to a stop, 30 s to come up): `/healthz`
shows guard build ca4ee41aecf2, boot 20, commit f066c0f6bdbc+16 (uncommitted). The session was lost on the restart. A third live
redraft on this build was run after sign-in (job `j53df867b3b`, 10 of 10 sections, 0 errors).

**Third live redraft, on guard build ca4ee41aecf2.** The guard masked 18 values (3 `period_basis`, 4 names, 4 entities, 2
identifiers, 3 page references, 1 misplaced base, 1 figure). What it did:

- **Revenue per MT.** The model wrote the swapped-year version ("₹149.74 in FY 2023-24 to ₹159.02 in FY 2024-25 and ₹160.55 in
  FY 2025-26"). Both wrong figures are masked and ₹160.55 in FY 2025-26 is kept. This is the period fix working on the hosted
  app, on a variant of the sentence rather than the identical one.
- **FSSC "since June 2025".** The model did not write that sentence this time, so `mask_event_dates` is verified offline only
  (the sentence from the earlier draft, replayed on the real facts, and four tests).
- **One masked figure to explain.** ₹9,240.50 was masked in a paragraph that the model cut off mid-year ("...in FY 20"; the guard
  reads "FY 20" as FY 2020). The value was right, the sentence is broken either way, and the reviewer sees `[●]` in a truncated
  sentence. Not changed.
- Every other sentence tying a figure to a period, and every month-year without a day, traced to a source.

**Problems of a different kind, found in the same read and not covered by any rule:**

1. *Invented explanation.* "The actual production for H1 FY27 has been revised from ₹4800 MT to ₹3984 MT due to operational
   inefficiencies" (and the same for pouches, 540 to 229 million). 4,800 is the installed capacity and 3,984 the actual
   production; nothing says "revised" or "inefficiencies". The figures are in the inputs, the claim about them is the model's.
2. *Swapped fee.* "sitting fees of ₹10,000 per Board meeting and ₹20,000 per year for attending Committee meetings"; the source says
   ₹20,000 per Board meeting and ₹10,000 per committee meeting. A subject-of-figure error (the class tried and removed).
3. *Garbled number.* "₹75,0,0,0,00" for ₹75,00,00,000, in a duplicate of a correct bullet; the value check does not read it.
4. *Stitched fragment.* "For adhesives zippers and spouts Raw materials were served customers the top customer accounted for
   14.18% of sale of products in H FY towards 40% of sale of products in H FY towards 9.37%" in the Business section.
5. "₹4800 MT": a rupee sign in front of a quantity.

These five came from the model and are for a reviewer; the guard checks that a value is in the inputs and that its period, basis,
base and month fit, not what the sentence says about it. Rules for 3 and 5 were written the same day (below); 1, 2 and 4 are
not covered.

### Mutation test after the half-year fix (22 Nov 2026, one run per project)

`python -m evaluate.claims_mutation workspace/<id>/facts.json`, run separately because the largest project is slow (about 100 s for 739
facts, over 30 min for 2,170 in one process). Correct sentences wrongly masked: **0 of 90** (Kestrel, 739 facts; the second copy of
that bundle gives the same) and **0 of 118** (2,170 facts). Shifted fiscal year caught: 84 of 89 and 107 of 116. Invented average caught:
88 of 90 and 116 of 118. The fourth bundle (4,411 facts) had not finished after 30 minutes and is not counted. The samples are larger
than the 57 reported before because the test skips a figure whose source speaks of a half-year, and a row's neighbours no longer
inherit an "H1" label from the fact they sit beside, so the skip applies to fewer figures. The misses are values such as 0 lakhs
(skipped on purpose) and "Dr. Nandini Krishnan Menon, ₹13.80 lakhs" (a label that is a person, not a line item).

### Rules for the garbled amount and the rupee sign before a quantity (22 Nov 2026)

`mask_malformed_amounts` (`verify/claims.py`, kind `malformed_amount`, applied to prose after the period and date checks) masks the
number only, in two cases that no source writes: (a) an amount after ₹, Rs or INR whose comma groups are neither Western (1,234,567)
nor Indian (12,34,567), such as ₹75,0,0,0,00; (b) a rupee sign directly before a unit that is not money (MT, MTPA, kg, sq m, million
pieces, employees, years, %), such as ₹4800 MT. A form that the facts themselves contain is left alone (a typo in a source is the
source's: the training data has "₹25,00,0000/-"). Scan of 22,851 real texts (fact snippets and values of four projects, the stored
drafts, the filed training and test drafts): no draft is touched; the remaining hits are source snippets cut off at the character limit
("₹3,96") and that one source typo. A first version matched "Rs" inside words ("inverters 5 years", "hours 5,598.72MT"); a
word-boundary check removed that, and it is a test. Four tests in `tests/test_claims.py`; 266 pass. Deployed as guard build
3f8f672d3ef7 (boot 21, commit f066c0f6bdbc+16, uncommitted).

Still not covered: the invented explanation ("revised ... due to operational inefficiencies"), the swapped sitting fee, the stitched
fragment.

### Fourth live redraft and the pairing fixes (22 Nov 2026)

Job `je31eeb8f1f` on guard build 3f8f672d3ef7 (10 of 10 sections, 0 errors; the first section waited for a cold endpoint). The guard
masked 12 values (5 `period_basis`, 1 `event_date`, 3 dates, 2 misplaced bases, 1 identifier). Read against the facts:

- **Month from the wrong event, live.** "FSSC 22000 certification since June 2025" was masked by `mask_event_dates` on the hosted app.
- **Largest customer.** The draft gave 14.91% for FY 2025-26 and 14.18% for FY 2024-25; the facts say 14.18 and 14.91 (swapped). Both masked.
- **Top-ten suppliers**, "72.40%, 70.86%, 70.86% and 68.81% ... in FY 2023-24, FY 2024-25, FY 2025-26 and H1 FY 2027 respectively":
  the third figure is wrong (69.52 is FY 2025-26) and was masked, **but the fourth, 68.81% for H1 FY27, is right and was masked
  too**: the guard read the list clause by clause and gave 68.81 the year "FY 2023-24".
- **Capex.** "₹616 lakhs were funded during FY 2026-27 and ₹1244 lakhs ... during FY 2027-28" is swapped (the source says ₹1,244
  lakhs in FY 2026-27) and **was not masked**: both years sit in one clause, and the source passage ("... ₹1,244 lakhs and ₹616
  lakhs respectively" under "FY 2026-27 and FY 2027-28") lent both years to both figures.
- **Exports.** "In H1 FY27, exports accounted for approximately 9.37%" was masked although 9.37% is the H1 FY27 figure: the half-year
  cue sat in the lead-in clause and, unlike the year, was not carried to the figure's clause.
- Malformed amounts: none written this time (the two rules are checked by tests only). The rest of the period and date sentences
  traced to a source; the revenue "crossing ₹100 crore in FY 2025-26" is the imprecision noted before.

Three fixes in `verify/claims.py`, each with a test (270 pass):

1. `pair_in_order`: a sentence with as many figures as fiscal-year labels is read pairwise, either when it says "respectively" or when
   figures and labels strictly alternate ("₹616 lakhs ... FY 2026-27 and ₹1244 lakhs ... FY 2027-28"). It is used for the claim and
   for source passages, so a passage that says "respectively" no longer lends both years to both figures. Result on the sentences
   above: the correct 68.81% is kept, the wrong 70.86% is masked, the swapped capex pair is masked, the right order is kept.
2. A half-year cue in a number-free lead-in ("In H1 FY27, ...") is carried to the figure after it, like the year.
3. (Earlier, same day) the per-figure half-year flag.

Mutation test after the fixes, Kestrel inputs: 0 of 90 correct sentences masked, 84 of 89 shifted years and 88 of 90 averages caught
(unchanged). Redeployed as guard build cc815e4ba2b4 (boot 22, commit f066c0f6bdbc+16, uncommitted); the pod had been idle 473 s with no
job running. The fixes of items 1 and 2 are not yet confirmed by a fifth live redraft (the session was lost on the restart).

The larger project's mutation run (2,170 facts) on the final code was still running when this was written; its figures above predate the
pairing fixes and the lead-in carry.

## Second data room (Vidyunmaya Infraprojects, 44 files): test and fixes, 22 Nov 2026

A second, larger synthetic data room (44 files in 6 folders: Word, Excel, text PDFs, scanned PDFs, JPG and PNG; a different business, an
EPC contractor for electrical substations, with an expired licence and an exchange, NSE Emerge, that differs from the form's default) was
run through the hosted UI on guard build cc815e4ba2b4: 42 files uploaded (two 14 to 15 MB scans exceed the browser tool's 10 MB limit;
the app takes 200 MB), 5,725 facts, 35 of 35 sections drafted with 0 errors. Reading the draft against the generator's master data
found the figures that matter right (directors and DINs, the offer, promoter holdings, revenue, the order book, funds deployed, the
expired Indore licence flagged) and these faults, all fixed in code on the same day, each with a test (`tests/test_client_grade.py`;
286 pass):

| fault | cause | fix |
|---|---|---|
| 8 files lost their running text (the business note kept 400 of 1,216 facts) | `MAX_FACTS_PER_FILE = 400`, applied silently; rows come first, so prose was cut | cap 3,000; a file past it carries a warning ("N facts beyond the first 3000 were not kept") shown in its drawer |
| 14 narrative sub-headings left as drafting briefs (Products, Capacity, Strengths, Brief History, ...) | the Word reader dropped heading styles, so the business note was never split into its sections; the "is this sub-heading in the files" test wanted the word "brief" or "history" in a passage | the reader keeps Word heading levels and contents lines; the note's own headings become the Business sub-headings; standard sub-headings are supported by synonyms; History, MD&A, Approvals and Summary draw on the note's matching section |
| a sub-heading the files do not speak to listed eight unrelated facts (rent lines under "Changes in Registered Office") | the brief showed the router's top facts | it says "[●] not stated in the issuer's files; to be provided", and lists only facts that carry its own terms |
| "Check (amount - deployment)", "Check: total - revenue" in the Objects and MD&A text | spreadsheet control rows and "Checks" / "Index" sheets read as data | dropped at the reader and in the extractor |
| "3.2 Electricity demand" as a paragraph, "Chart 1" with no chart, a lone "Source:" line, report marks "[5]", a table flattened into fifty numbers, a header row printed twice, one paragraph twice | the model reproduces the layout of its source documents | `clean_fragments` and `dedupe_paragraphs` in the guard. A first version also dropped title-like lines and cost 0.08 of fact use on the 89 test drafts (0.659 to 0.580); that rule is now limited to lines carrying a reference mark, and the score is 0.659 with 0 of 89 invented figures, as before |
| order book certificate read as a board resolution, flow chart as borrowings, BOCW registration as people profiles | classification by substring ("din" in "building"); no type for these files | whole-word matching for short keywords; types `order_book`, `work_completion`; name keywords for flow charts and BOCW |
| "largest customer accounted for 952.06% of revenue"; a loan row printed as a covenant; "1 (31.20)" with no unit; a forex risk quoting a quotation row | the rule took the last column of a table whatever its header; rules read table rows as sentences | share columns only, 0 to 100; prose-only sentences for the lender, customer, lease and forex rules; cases and amount read from "1 (31.20)" with the unit from the certificate |
| the accounting-ratio table printed every ratio three times | the workings sheet holds the recomputed, restated ("RFI ...") and difference columns | only the first set of periods and the definition are kept |
| sentences cut at "Co." and "ref." ("SRP/VIL/2026-27/C-05 dated ..." as the start of a sentence) | the sentence splitter | abbreviations are protected |
| exchange left at BSE SME although the files say NSE Emerge | the platform is a creation-time choice; the review pack raised it, the draft did not | while the files name the other platform and nobody has switched, the draft prints [●] for the platform |

Seven more faults showed only once the sub-headings above were actually written by the model (second to fifth redraft, same day; 296 tests):

| fault | cause | fix |
|---|---|---|
| a section took tens of minutes on the pod | every guard check re-read all 7,700 facts for every paragraph (7 s of 9 s per paragraph; the per-paragraph cost fell to 0.9 s) | what a check derives from the facts is built once per sub-heading (`verify/memo.py`, and a per-fact cache of the evidence); results unchanged (291 tests, the 89-draft scores) |
| the model dropped small words and added details the note does not have ("technical commercial comparison utilities inspect transformers switchgear"; "baseline schedules established at contract inception") | drafting penalty 0.3, chosen for the first adapter which looped in 19% of drafts, makes the DPO adapter reword what it copies | 89 test drafts, one run each, penalty 0.3 / 0.1 / 0.0: fact use after the guard 0.659 / 0.714 / 0.686, loops 0.0% / 1.1% / 2.2%, drafts with an invented figure after the guard 0 / 0 / 0 of 89, seconds per draft 18 / 19 / 34. The app now uses 0.1 (`DRAFT_FREQUENCY_PENALTY`); `trim_repeats` cuts the loops that remain. One run each, no interval: the direction agrees across 0.1 and 0.0, the size of the gain is not established |
| five tables written as one run of words ("FY 2023-24 FY 2024-25 ... Tenders bid (number) 58 66 79 37 ...") and pipe lines without leading bars shown as paragraphs | the model writes tables the way its source documents print them | a header of two or more period labels followed by rows of a label and as many values is read back into a table, only when the rows account for the whole text; pipe lines become a table (`_flat_table`); both go through the cell-by-cell figure check |
| "The Company has not changed its registered office since incorporation" (no file says so), with a second, empty "Changes in Registered Office" | the sub-heading counted as supported because a lease passage mentions the registered office | sub-headings about an event are written only from a source that states one (`REQUIRES_EVENT`); otherwise "[●] not stated in the issuer's files" |
| "• Check (amount - deployment): ₹ 0" in the Objects text after the control rows were dropped | the check was a column header of the objects summary, so each row produced a fact "Object - Check (amount - deployment)" | control columns (header "Check", "Difference") are skipped when facts are read |
| the funds-deployed certificate's letterhead ("SYNTHETIC TEST DOCUMENT S R PANDE & CO. Chartered Accountants ... Tel: ... FRN: ... Peer Review Certificate No.") written as a paragraph of Objects | the model copies a passage that starts with a letter's head | a paragraph with three letterhead markers (Tel:, Email:, FRN:, Chartered Accountants, The Board of Directors, Sub:, UDIN:, Peer Review Certificate) is dropped |
| "Changes in Registered Office" supported again by a Shops Act row that mentions "change of name" | the event test matched "change" anywhere near "registered office" | the test needs a change **of the registered office** (shifted, relocated, "change in registered office"); a change of name does not count |

Not fixed, and not hidden: a figure that is in the files but attached to the wrong subject ("the top ten suppliers accounted for 58.40% of
purchases"; 58.40% is one state's revenue share in another year). A check that compares the words around a percentage with the label of
every fact holding that value was built and tried on the 89 test drafts; it masked 158 of 352 percentage paragraphs, nearly all correct
(share tables, generic labels such as "Percentage of total shareholding"), so it was removed. Reviewers must still read what each
percentage is of.

### Result on the same data room after the fixes (guard build 8ed81d12d335, boot 32, commit f066c0f6bdbc+27, uncommitted)

All 42 files read (the two 14 to 15 MB scans were not uploaded by the browser tool, whose limit is 10 MB; the app takes 200 MB); 7,954 facts
(was 5,725 under the 400 cap); the four misclassified files are now order book, process flow, work completion and licence; 35 of 35 sections
drafted, 0 job errors; every sub-heading that was a stub (14 before) is written except "Changes in Registered Office", for which no file states a
change (it lists the facts that carry its own words). Counted over all 35 drafts: duplicate paragraphs 0 (was 4), section numbers and chart
captions as paragraphs 0 (4), report reference marks 0 (2), spreadsheet "Check" lines 0 (3), percentages over 100 0 (1), letterhead copied
into Objects 0; 424 paragraphs, 91 tables, 7 values masked as [●]; the Word export builds (142 KB). Time: Business, 14 sub-headings of
three drafts each, takes about 10 minutes on the pod; the whole 35 sections about 35 minutes (the model, not the guard).

Still open, and visible to a reviewer: (1) a figure attached to the wrong subject (see above); (2) a few tables the model writes without
a period header ("Client A State power distribution utility Maharashtra 2012 21.40 19.85 ...", "Equipment Number Year of purchase ...") stay
as one run of words; their figures are checked, only the layout is not repaired; (3) the model still writes generic strengths and strategy
bullets in places (they follow the issuer's note, but a reviewer should confirm each); (4) the exchange is left at the form's BSE SME while the
files say NSE Emerge: the draft prints [●] for the platform and the Offer page raises "Switch platform", which a person must press;
(5) the two large scans (FY 2024-25 and FY 2023-24 audited statements) were not read.

## Third data room (Rasoiyana Foods, 45 files incl. 15 scans): test and fixes, 22 Nov 2026

Run on the hosted app on guard build 2e61f3d6c7cd, then 65b3c20d423e. A spice and snacks maker (Indore) with a selling investor, a trade-mark
assignment and an Unit II expansion. 45 files uploaded (the two 16 MB audited-statement scans were left out, as before), all read,
9,193 facts, Offer details filled from the files (13 fields, including the BRLM, registrar, counsel and resolution dates), 35 of 35
sections drafted with 0 errors. Checked against the generator's master data: all 6 directors with DINs, all 5 KMP, the offer (30,00,000
fresh and 4,00,000 offer for sale shares), the four objects with amounts, the three advisers, the litigation case, the CIN and the
incorporation date are in the draft; the five open items are in the risk factors. Faults found, each fixed with a test (301 pass):

| fault | fix |
|---|---|
| "₹4,012.19 million (43.2% of sales)" where the source table is headed "(₹ lakhs; %)": right digits, wrong unit (a hundredfold misstatement); the value check keeps it | `mask_unit_claims`: the unit of a rupee amount must be one the inputs give for that number, or not one they hardly use for rupee amounts; the number is masked. No change on the 89 test drafts |
| six data-room file types classified as "other", a board resolution or approvals (shareholders' agreement, channel revenue certificate, distribution agreements, trade-mark deed, media plan) | new types, name keywords, and `needs` entries |
| "Industry Overview" left as a stub (the report says "market", not "industry") | a section whose only sub-heading is its own title is written when any passage exists |
| "Number of customers billed | 291.00% | 322.00%" | a count row in a column of percentages is not formatted as one |
| "Material Agreements" unsupported although two agreement files were given | passages of the files of agreement types answer it (`DOC_FOR_SUB`) |
| trade-mark risk factor with "(application no. )" empty; "top-10 customers contributed 28.10%" with no period; the Promoter-group conflict (a partnership of the Promoter's brother) missing | the register's "Registration no." column is read; the period is taken from the source sentence; the conflict rule also reads "partnership" and "firm" and no longer asserts a non-compete |

After the redraft: no rupee-million sentence, no empty registration number, 16 values masked (27 before the unit rule and the wording fixes),
the only sub-heading left as a brief is "Changes in Registered Office" (no source states a change). The pod stopped itself after a finished
draft because I did not poll within 10 minutes; nothing was lost (drafts are on the volume).
