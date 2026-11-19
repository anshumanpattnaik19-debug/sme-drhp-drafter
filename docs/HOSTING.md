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
