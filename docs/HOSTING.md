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

