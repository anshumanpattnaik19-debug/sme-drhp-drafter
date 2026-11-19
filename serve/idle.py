"""Auto-stop for the app on a RunPod CPU pod (docs/HOSTING.md): stop the pod after POD_IDLE_MINUTES without use, so a
forgotten pod cannot run down the credit. Off unless the app runs on a pod (RUNPOD_POD_ID, set by RunPod) with
POD_IDLE_MINUTES and a key that may stop pods (RUNPOD_PODS_KEY).

Use is any request except the UI's 30-second status poll (/api/health) and the sign-in page, plus any job still
running (processing or drafting): an open but unused browser tab does not keep the pod alive.
"""
from __future__ import annotations

import os
import threading
import time

import httpx

IGNORED = ("/api/health", "/login", "/favicon.svg")
_last = time.time()


def minutes():
    try:
        return float(os.environ.get("POD_IDLE_MINUTES", "0"))
    except ValueError:
        return 0.0


async def touch(request, call_next):
    global _last
    if request.url.path not in IGNORED:
        _last = time.time()
    return await call_next(request)


def idle_for(now=None, busy=False):
    """Seconds without use; 0 while a job is running."""
    return 0.0 if busy else (now or time.time()) - _last


def stop_pod():
    pod, key = os.environ.get("RUNPOD_POD_ID"), os.environ.get("RUNPOD_PODS_KEY")
    r = httpx.post(f"https://api.runpod.io/v2/pods/{pod}/action", json={"action": "stop"},
                   headers={"Authorization": f"Bearer {key}"}, timeout=30)
    print(f"auto-stop: pod {pod} idle for {minutes():g} min, stop requested (HTTP {r.status_code})", flush=True)


def watch(jobs_running, check_every=60):
    """Start the watchdog thread when the app runs on a pod with auto-stop configured. jobs_running() -> bool."""
    if not (minutes() > 0 and os.environ.get("RUNPOD_POD_ID") and os.environ.get("RUNPOD_PODS_KEY")):
        return None

    def loop():
        while True:
            time.sleep(check_every)
            if idle_for(busy=jobs_running()) >= minutes() * 60:
                try:
                    stop_pod()
                except httpx.HTTPError as e:
                    print(f"auto-stop failed: {e}", flush=True)
                time.sleep(300)                  # the pod is stopping; do not ask again at once

    t = threading.Thread(target=loop, name="idle-stop", daemon=True)
    t.start()
    print(f"auto-stop: pod stops after {minutes():g} min without use", flush=True)
    return t
