"""Get the hosted system ready before a demo, and keep the model awake during it.

    python -m serve.warmup                     # start the app pod, wake a model worker, print the links and timings
    python -m serve.warmup --keep-warm 30      # then keep one worker awake for 30 minutes (one tiny request every 20 s)

Why: after an idle spell the model endpoint needs 4–6 minutes to start a worker (image, model load, compile), and the app pod
about 30–45 s (it may also be re-created on another host, which changes its address). Run this 10 minutes before a demo.

What it costs: a worker is billed per second while it runs (about $0.75 an hour on the 24 GB slice); --keep-warm is capped at
120 minutes and stops by itself, after which the endpoint scales back to zero within its 30 s idle timeout. The app pod stops
itself after 10 idle minutes. Nothing here changes the endpoint's settings.
"""
from __future__ import annotations

import argparse
import os
import sys
import time

import httpx

from serve import pod, runpod

MAX_KEEP_MIN = 120
PING_EVERY_S = 20


def endpoint_health(st):
    """RunPod's /health: worker counts, not a billed job."""
    r = httpx.get(f"https://api.runpod.ai/v2/{st['endpoint_id']}/health",
                  headers={"Authorization": f"Bearer {os.environ['RUNPOD_API_KEY']}"}, timeout=20)
    r.raise_for_status()
    return r.json()


def ping(st, timeout=600):
    """One 1-token chat request to the served model; it starts a worker if none is up. Returns seconds taken."""
    t0 = time.time()
    r = httpx.post(st["model_url"].rstrip("/") + "/chat/completions",
                   headers={"Authorization": f"Bearer {os.environ['RUNPOD_API_KEY']}"},
                   json={"model": runpod.SERVED, "messages": [{"role": "user", "content": "ok"}], "max_tokens": 1,
                         "temperature": 0}, timeout=timeout)
    r.raise_for_status()
    return time.time() - t0


def main(argv=None):
    ap = argparse.ArgumentParser(prog="python -m serve.warmup")
    ap.add_argument("--keep-warm", type=int, default=0, help=f"minutes to keep one worker awake after warming (max {MAX_KEEP_MIN})")
    ap.add_argument("--skip-pod", action="store_true", help="only wake the model")
    a = ap.parse_args(argv)
    runpod.load_env_file()
    st = runpod.load_state()
    if not st.get("model_url"):
        sys.exit("no endpoint in build/runpod_endpoint.json: run `python -m serve.runpod create` first")
    t0 = time.time()
    if not a.skip_pod:
        print("== app pod")
        pod.start(argparse.Namespace())
        st = runpod.load_state()                     # the pod may have been re-created with a new address
    print("== model endpoint")
    h = endpoint_health(st)
    print(f"workers before: {h.get('workers')}")
    for attempt in range(1, 4):                      # the first request may time out while the image downloads
        try:
            s = ping(st)
            print(f"model answered in {s:.0f} s ({'cold start' if s > 30 else 'warm'})")
            break
        except httpx.HTTPError as e:
            print(f"attempt {attempt}: {str(e)[:120]}; retrying")
    else:
        sys.exit("the model did not answer; see `python -m serve.runpod purge` and the RunPod console")
    print(f"\nready after {time.time() - t0:.0f} s")
    print(f"  app:      {st.get('app_url')}")
    print("  launcher: https://drhp-launcher.vercel.app")
    print(f"  workers:  {endpoint_health(st).get('workers')}")
    minutes = min(max(0, a.keep_warm), MAX_KEEP_MIN)
    if minutes:
        print(f"\nkeeping one worker awake for {minutes} min (Ctrl+C to stop early)")
        end = time.time() + minutes * 60
        try:
            while time.time() < end:
                time.sleep(PING_EVERY_S)
                ping(st, timeout=120)
        except KeyboardInterrupt:
            pass
        print("keep-warm ended; the endpoint scales back to zero after its idle timeout")


if __name__ == "__main__":
    main()
