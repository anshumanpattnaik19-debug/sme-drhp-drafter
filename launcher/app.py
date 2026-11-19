"""Launcher for DRHP Studio (docs/HOSTING.md): a small always-on page, free on a Hugging Face Space, that starts the
app's RunPod CPU pod when someone with the shared password asks, waits until the app answers, and sends them to it.
The pod itself stops after its idle time (serve/idle.py), so it bills only while it is used.

Environment (Space secrets and variables): APP_PASSWORD, RUNPOD_PODS_KEY (a RunPod key with Pods access),
LAUNCHER_SECRET, POD_ID. The key never reaches the browser; the visitor needs the password here and again in the app.
"""
from __future__ import annotations

import hashlib
import hmac
import html
import os
import threading
import time
from urllib.parse import parse_qs

import httpx
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse

API = "https://api.runpod.io/v2"
COOKIE, MAX_AGE = "drhp_launcher", 3600
MAX_FAILS, WINDOW = 5, 600
app = FastAPI(title="DRHP Studio launcher", docs_url=None, redoc_url=None, openapi_url=None)
_fails: dict[str, list[float]] = {}
_lock = threading.Lock()


def pod_id():
    return os.environ["POD_ID"]


def app_url():
    return f"https://{pod_id()}-7860.proxy.runpod.net"


def _sign(exp):
    return hmac.new(os.environ["LAUNCHER_SECRET"].encode(), str(exp).encode(), hashlib.sha256).hexdigest()


def _valid(c):
    try:
        exp, sig = c.split(".", 1)
        return int(exp) > time.time() and hmac.compare_digest(sig, _sign(int(exp)))
    except (AttributeError, ValueError):
        return False


def _client(request):
    return request.headers.get("x-forwarded-for", "").split(",")[0].strip() or (request.client.host if request.client else "?")


def _runpod(method, path, **kw):
    r = httpx.request(method, API + path, headers={"Authorization": f"Bearer {os.environ['RUNPOD_PODS_KEY']}"},
                      timeout=30, **kw)
    r.raise_for_status()
    return r.json() if r.content else {}


def _answers():
    try:
        return httpx.get(f"{app_url()}/login", timeout=6).status_code == 200
    except httpx.HTTPError:
        return False


STYLE = """:root{color-scheme:light dark;--bg:#f6f7f9;--card:#fff;--text:#111827;--muted:#6b7280;--line:#d1d5db;--accent:#4f46e5;--err:#b91c1c}
@media (prefers-color-scheme:dark){:root{--bg:#0f1115;--card:#171a21;--text:#e5e7eb;--muted:#9ca3af;--line:#2d333d;--accent:#818cf8;--err:#f87171}}
*{box-sizing:border-box}body{margin:0;min-height:100vh;display:grid;place-items:center;background:var(--bg);color:var(--text);
font:15px/1.5 system-ui,-apple-system,Segoe UI,Roboto,sans-serif;padding:16px}
.card{width:100%;max-width:380px;background:var(--card);border:1px solid var(--line);border-radius:12px;padding:28px}
h1{font-size:18px;margin:0 0 4px}p{color:var(--muted);margin:0 0 20px;font-size:14px}label{display:block;font-size:13px;margin-bottom:6px}
input{width:100%;padding:10px 12px;border:1px solid var(--line);border-radius:8px;background:transparent;color:inherit;font:inherit}
button{margin-top:16px;width:100%;padding:10px;border:0;border-radius:8px;background:var(--accent);color:#fff;font:inherit;font-weight:600;cursor:pointer}
.err{color:var(--err);font-size:13px;margin-top:12px}.bar{height:6px;border-radius:3px;background:var(--line);overflow:hidden;margin:16px 0 8px}
.bar i{display:block;height:100%;width:30%;background:var(--accent);animation:s 1.4s ease-in-out infinite}@keyframes s{0%{margin-left:-30%}100%{margin-left:100%}}"""

FORM = """<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>DRHP Studio</title><style>{style}</style></head><body><form class="card" method="post" action="/start"><h1>DRHP Studio</h1>
<p>Enter the shared password. The app starts if it is asleep (about 3–4 minutes), then opens.</p>
<label for="pw">Password</label><input id="pw" name="password" type="password" autofocus required>
<button type="submit">Open DRHP Studio</button>{error}</form></body></html>"""

WAIT = """<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Starting DRHP Studio</title><style>{style}</style></head><body><div class="card"><h1>Starting DRHP Studio</h1>
<p id="msg">Waking the app. This takes about 3–4 minutes after a long pause; you will be taken there when it is ready.</p>
<div class="bar"><i></i></div><p id="st" style="margin:0;font-size:13px"></p></div>
<script>
async function poll(){{try{{const r=await fetch('/status');const s=await r.json();
document.getElementById('st').textContent='Status: '+s.state;
if(s.ready){{location.href=s.url;return}} if(s.error){{document.getElementById('msg').textContent=s.error;return}}}}catch(e){{}}
setTimeout(poll,5000)}} poll();
</script></body></html>"""


def page(error="", status=200):
    err = f'<div class="err" role="alert">{html.escape(error)}</div>' if error else ""
    return HTMLResponse(FORM.format(style=STYLE, error=err), status_code=status, headers={"Cache-Control": "no-store"})


@app.get("/")
def index():
    return page()


@app.post("/start")
async def start(request: Request):
    ip = _client(request)
    with _lock:
        _fails[ip] = [t for t in _fails.get(ip, []) if time.time() - t < WINDOW]
        locked = len(_fails[ip]) >= MAX_FAILS
    if locked:
        return page("Too many attempts. Try again in a few minutes.", 429)
    given = (parse_qs((await request.body()).decode("utf-8", "replace")).get("password") or [""])[0]
    if not hmac.compare_digest(given.encode(), os.environ.get("APP_PASSWORD", "").encode()) or not os.environ.get("APP_PASSWORD"):
        with _lock:
            _fails.setdefault(ip, []).append(time.time())
        return page("Wrong password.", 401)
    try:
        if _runpod("GET", f"/pods/{pod_id()}")["status"] in ("EXITED", "ERROR"):
            _runpod("POST", f"/pods/{pod_id()}/action", json={"action": "start"})
    except httpx.HTTPError:
        return page("The app could not be started. Please try again in a minute.", 502)
    exp = int(time.time()) + MAX_AGE
    r = HTMLResponse(WAIT.format(style=STYLE), headers={"Cache-Control": "no-store"})
    r.set_cookie(COOKIE, f"{exp}.{_sign(exp)}", max_age=MAX_AGE, httponly=True, secure=True, samesite="none")
    return r


@app.get("/status")
def status(request: Request):
    if not _valid(request.cookies.get(COOKIE)):
        return JSONResponse({"detail": "sign in required"}, status_code=401)
    try:
        st = _runpod("GET", f"/pods/{pod_id()}")["status"]
    except httpx.HTTPError:
        return {"state": "unknown", "ready": False}
    if st in ("TERMINATED",):
        return {"state": st, "ready": False, "error": "The app's server was removed. Please contact the owner."}
    ready = st == "RUNNING" and _answers()
    return {"state": "ready" if ready else st.lower(), "ready": ready, "url": app_url() if ready else None}
