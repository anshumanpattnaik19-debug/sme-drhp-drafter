# Hosting the model on RunPod Serverless (billed only while it runs)

The app (DRHP Studio) stays on the laptop or in its Docker container. Only the model runs on RunPod: Qwen2.5-7B-Instruct
with the A_qa_dpo LoRA adapter, behind RunPod's vLLM worker, which speaks the same OpenAI-compatible API as
`serve/llm.py`. Everything here is done by `python -m serve.runpod` (`serve/runpod.py`).

## Cost

Serverless has no subscription. You prepay credit and pay per second while a worker runs (RunPod docs, Serverless
pricing): "A worker that has scaled down ... is not billed".

| | billed? |
|---|---|
| no requests (worker scaled down) | no |
| image pull and model download before a worker starts | no |
| cold start (loading the model, about 30–90 s) | yes |
| answering requests | yes |
| idle timeout after the last request (set to 30 s) | yes |
| always-on workers | none are created (`workers.min = 0`) |
| network volume | none is created |

The endpoint uses the cheapest 24 GB pool (L4 / A5000 / 3090, listed at about $0.75 per hour), with the cheapest 48 GB
pool as the fallback. Expect about $0.003 per drafted sub-section, about $0.01–0.02 per cold start, and at most $0.75 for
an hour of continuous use. `check` prints the estimate for its own run.

## Steps

1. **Account and credit (you).** Sign up at https://console.runpod.io/signup and add credit at
   https://console.runpod.io/user/billing (Other → $10 is enough to start; credit is not refundable). Leave auto-pay off
   and turn on the low-balance alert.
2. **Keys (you).**
   - RunPod: console → Settings → API Keys → create a key with read/write access.
   - Hugging Face: https://huggingface.co/settings/tokens → a token with **write** access (it creates the private
     adapter repo; RunPod uses it to download the adapter).

   Put both in a file `.runpod.env` in the project folder (gitignored, kept out of the Docker image):

   ```
   RUNPOD_API_KEY=...
   HF_TOKEN=...
   ```

   The script reads them from there or from the environment, and never prints or writes them anywhere else.
3. **Upload the adapter** (161 MB, `build/hf_upload/adapter`) to a private Hugging Face repo:
   `python -m serve.runpod upload` (repo `<your user>/sme-drhp-7b-lora`).
4. **Create the endpoint:** `python -m serve.runpod create`. It stores the Hugging Face token as a RunPod secret,
   picks the GPU pools from RunPod's catalog and prints the endpoint's `model_url`. `--dry-run` prints the request
   without calling RunPod.

   | setting | value |
   |---|---|
   | image | `runpod/worker-v1-vllm:v2.30.3` (vLLM 0.32.0, needs CUDA 13.0) |
   | model | `Qwen/Qwen2.5-7B-Instruct`, adapter served as `sme-drhp-7b` |
   | context | 6,144 tokens, GPU memory 0.9 |
   | workers | min 0, max 1, idle timeout 30 s, FlashBoot on, job timeout 10 min |
5. **Check the endpoint:** `python -m serve.runpod check`. The first call starts a worker (cold start). It then runs
   the app's own calls: the model list (is `sme-drhp-7b` served), the app's 4-second reachability check, three test
   drafts with frequency penalty 0.3 (speed, loops), one extraction (valid JSON) and a streamed answer. Results in
   `build/runpod_check.json`.
6. **Test the whole app:** start it (`python -m uvicorn serve.app:app --port 8765`, or the Docker container on port
   8765), then `python -m serve.runpod smoke`. It sets the app's model to the endpoint, uploads six issuer files from
   `bundles/out/kestrel_flexipak`, processes them and drafts the `summary` section with the model
   (`build/docker_smoke.json`). Run `check` first so a worker is warm: the app's own model test times out after 6 s.
7. **Use it in the app:** Settings → model URL = the `model_url` printed in step 4
   (`https://api.runpod.ai/v2/<ENDPOINT_ID>/openai/v1`), model name `sme-drhp-7b`, API key = the RunPod key.
8. **Stop paying entirely:** `python -m serve.runpod delete` removes the endpoint; delete the Hugging Face repo and the
   RunPod secret in their consoles if they are no longer needed.

## First deployment (19 Nov 2026)

Endpoint `d76m7tnejfo38z`, adapter `18Anshu/sme-drhp-7b-lora` (private). Workers were placed on a 24 GB slice of an
RTX PRO 6000 (EUR-IS-2).

| check | result |
|---|---|
| first start | about 4 minutes (image, model load, vLLM compile); later starts reuse FlashBoot |
| `check` | all passed: `sme-drhp-7b` served, the app's 4 s check reachable, 3 drafts at 14–16 tokens/s with no loop, extraction valid JSON, streaming first token after 1.4 s; about 330 s of worker time, about $0.07 |
| `smoke` (the app) | 6 issuer files processed (740 facts); `summary` drafted by the model in 196 s: 67 blocks, 0 ungrounded figures, 18 values masked by the verifier, one sub-heading trimmed at a loop |
| app red team (`evaluate/app_redteam.py`) | 23 pass, 2 reviewed by hand, 0 fail after the fixes (docs/RED_TEAM_LOG.md) |
| idle | 0 running workers, $0.00000/s; the app's status poll starts no worker |

Spend for the whole first deployment, including the failed first start, the runaway draft and both red-team runs: $0.31 ($10.00 to $9.69).

## Known limits

- After an idle spell the first request waits for a cold start (30–90 s); the app's 4-second model check shows the
  model as unreachable until a worker is up.
- RunPod's docs do not say how LoRA adapter names appear in `/models`; `check` reports it. If `sme-drhp-7b` is missing
  there, set the app's model name to the name `check` lists.
- The optional vision OCR model is not hosted; RapidOCR (offline) is used.
- RunPod's worker docs show `LORA_MODULES` as a JSON list; vLLM 0.32 needs one JSON object, otherwise `vllm serve` exits
  with code 2 and the worker crash-loops. `serve/runpod.py` writes the object form.
- A request stays queued on RunPod after the app gives up on it (a cancelled drafting job, a restarted app) and would
  still run. `python -m serve.runpod purge` drops them and shows the endpoint's jobs and workers.
- The app's status (polled by the UI every 30 s) asks RunPod's `/health`, which starts no worker. Asking `/models`
  would be a billed job that keeps a worker awake while the app is merely open.
- Workers on a 24 GB MIG slice write about 15 tokens/s, so a sub-heading takes 10–35 s; a full set of narrative
  sections is roughly 30–60 minutes of worker time (about $0.40–0.75).
