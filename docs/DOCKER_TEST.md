# Docker test of the app

Run: 15 Nov 2026, laptop with Docker Desktop 29.9.3.

## What was built and run

- Image: `docker build -f docker/Dockerfile.app -t drhp-studio .` (built from the current code, after the table, date
  and OCR changes of this round).
- Container: `docker run -d --name drhp-smoke -p 8765:8765 drhp-studio`.
- Smoke test: `python vm/docker_smoke.py http://127.0.0.1:8765 offline bundles/out/kestrel_flexipak`, which goes through
  the app's own API: health, settings, a new project, six issuer files uploaded (two Word, three Excel, one scanned JPG),
  processing, and one drafted section (`summary`).

## Result

| Step | Result |
|---|---|
| Health | `status ok`, OCR available |
| Upload and processing | 6 files, processed, 739 facts |
| Drafting (offline drafter, no model server) | `summary` drafted: engine `brief`, 10 blocks |

The OCR of the scanned JPG ran inside the container with RapidOCR (offline), so the image has its OCR models.

## Re-run on 15 November 2026 (after the final fixes)

The image was rebuilt from the latest code. The container starts and answers `/api/health` with OCR available, and the
same smoke test passed (740 facts, one section drafted with the offline drafter). The smoke test's polling was fixed to
retry a dropped keep-alive connection; the app itself was not at fault.

## What was not tested, and why

**The drafting model inside the container was not tested.** The course VM's SSH server refuses port forwarding for
this account ("administratively prohibited"), so the laptop could not reach the vLLM server on the VM. This is a
server policy, not a fault in the app, and it was not worked around. The model path was tested on the VM through the
app's own source run (H5, see `docs/H5_RESULTS.md`), which uses the same API.

**The compose file's vLLM service was not run.** It needs an NVIDIA GPU on the same Docker host, and the laptop has
none. `docker compose config` is valid.

To test the model in Docker, run the container on a GPU host, or on a host whose model server the laptop can reach
directly, and point the Settings at it.

## Hosting the model with vLLM for the container (attempted)

The model was served on the VM with vLLM (base model plus the A_qa_dpo adapter), on all interfaces, behind an API key
(`vm/serve_api.sbatch`). The server answered on the VM. The laptop could not reach it: a connection to the VM's port
8011 fails ("Unable to connect"), and only SSH is reachable from outside. The VM's SSH also refuses port forwarding. The
network allows no route from the laptop to the model, so the container could not use it. The job was cancelled and the
API key removed from both machines.

## The container with the live model (20 Nov 2026)

The earlier blocker (no port forwarding from the course VM) does not apply to the RunPod endpoint, which is reachable over
HTTPS. Image `drhp-studio:ac98415` (built with `--build-arg GIT_COMMIT=...`, 1.43 GB, now including `rai/`, which the
Dockerfiles had not copied: an image built before this fix ran without the Responsible AI layer and said so in the chat
steps) was run on the laptop as `docker run -p 8780:8765 drhp-studio:ac98415`, the model woken with
`python -m serve.warmup --skip-pod`, and `python -m serve.runpod smoke --app http://127.0.0.1:8780` run against it.

| Step | Result |
|---|---|
| `/healthz` of the container | `commit ac98415bcede`, `rai 1.1:enforce`, guard `cf30665405c3` |
| Model woken | 140 s (cold start) |
| Settings test from inside the container | endpoint reachable, `sme-drhp-7b` listed |
| Upload and processing | 6 issuer files, 740 facts |
| `summary` drafted **by the model** | 14 blocks, 0 values masked, 0 ungrounded figures, no loop, grounding 0.818 |

The container and the model work together; the compose file's local vLLM service is still untested (no GPU on the laptop).
