"""Shared-password gate for a hosted app (the Hugging Face Space, docs/HOSTING.md). Off unless APP_PASSWORD is set, so
a local run is unchanged.

Every request needs a session cookie: pages without one are sent to /login, /api/* gets 401. The login page is plain
HTML served here, so nothing of the UI or the API is reachable before the password. The cookie holds an expiry and an
HMAC of it, never the password. Failed logins are limited per client address. The password is read from the
environment only and is never logged.
"""
from __future__ import annotations

import hashlib
import hmac
import html
import os
import secrets
import threading
import time
from urllib.parse import parse_qs, quote

from fastapi import Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

COOKIE = "drhp_session"
MAX_AGE = 12 * 3600
MAX_FAILS, WINDOW = 5, 600                  # 5 wrong passwords per client in 10 minutes, then 429 until the window ends
OPEN = ("/login", "/logout", "/favicon.svg")

_fails: dict[str, list[float]] = {}
_lock = threading.Lock()


def password():
    return os.environ.get("APP_PASSWORD", "")


def _secret():
    s = os.environ.get("APP_SESSION_SECRET")
    if not s:                                # a fresh secret per start: a restart signs everyone out
        s = os.environ["APP_SESSION_SECRET"] = secrets.token_hex(32)
    return s.encode()


def _sign(exp):
    return hmac.new(_secret(), str(exp).encode(), hashlib.sha256).hexdigest()


def make_cookie():
    exp = int(time.time()) + MAX_AGE
    return f"{exp}.{_sign(exp)}"


def valid(cookie):
    try:
        exp, sig = cookie.split(".", 1)
        return int(exp) > time.time() and hmac.compare_digest(sig, _sign(int(exp)))
    except (AttributeError, ValueError):
        return False


def _client(request):
    fwd = request.headers.get("x-forwarded-for", "")
    return fwd.split(",")[0].strip() or (request.client.host if request.client else "?")


def _locked(ip):
    with _lock:
        now = time.time()
        _fails[ip] = [t for t in _fails.get(ip, []) if now - t < WINDOW]
        return len(_fails[ip]) >= MAX_FAILS


def _fail(ip):
    with _lock:
        _fails.setdefault(ip, []).append(time.time())


def _secure(request):
    return request.headers.get("x-forwarded-proto", request.url.scheme) == "https"


PAGE = """<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>DRHP Studio · sign in</title><style>
:root{{color-scheme:light dark;--bg:#f6f7f9;--card:#fff;--text:#111827;--muted:#6b7280;--line:#d1d5db;--accent:#4f46e5;--err:#b91c1c}}
@media (prefers-color-scheme:dark){{:root{{--bg:#0f1115;--card:#171a21;--text:#e5e7eb;--muted:#9ca3af;--line:#2d333d;--accent:#818cf8;--err:#f87171}}}}
*{{box-sizing:border-box}}body{{margin:0;min-height:100vh;display:grid;place-items:center;background:var(--bg);color:var(--text);
font:15px/1.5 system-ui,-apple-system,Segoe UI,Roboto,sans-serif;padding:16px}}
form{{width:100%;max-width:360px;background:var(--card);border:1px solid var(--line);border-radius:12px;padding:28px}}
h1{{font-size:18px;margin:0 0 4px}}p{{color:var(--muted);margin:0 0 20px;font-size:14px}}
label{{display:block;font-size:13px;margin-bottom:6px}}input{{width:100%;padding:10px 12px;border:1px solid var(--line);border-radius:8px;
background:transparent;color:inherit;font:inherit}}button{{margin-top:16px;width:100%;padding:10px;border:0;border-radius:8px;
background:var(--accent);color:#fff;font:inherit;font-weight:600;cursor:pointer}}.err{{color:var(--err);font-size:13px;margin-top:12px}}
</style></head><body><form method="post" action="/login"><h1>DRHP Studio</h1><p>Enter the shared password to continue.</p>
<label for="pw">Password</label><input id="pw" name="password" type="password" autocomplete="current-password" autofocus required>
<input type="hidden" name="next" value="{next}"><button type="submit">Sign in</button>{error}</form></body></html>"""


def login_page(next_="/", error="", status=200):
    err = f'<div class="err" role="alert">{html.escape(error)}</div>' if error else ""
    return HTMLResponse(PAGE.format(next=html.escape(next_, quote=True), error=err), status_code=status,
                        headers={"Cache-Control": "no-store"})


def _safe_next(n):
    return n if n.startswith("/") and not n.startswith("//") and not n.startswith("/login") else "/"


async def gate(request: Request, call_next):
    if not password():
        return await call_next(request)
    path = request.url.path
    if path == "/login" and request.method == "POST":
        ip = _client(request)
        if _locked(ip):
            return login_page(error="Too many attempts. Try again in a few minutes.", status=429)
        form = parse_qs((await request.body()).decode("utf-8", "replace"))
        given = (form.get("password") or [""])[0]
        nxt = _safe_next((form.get("next") or ["/"])[0])
        if not hmac.compare_digest(given.encode(), password().encode()):
            _fail(ip)
            return login_page(nxt, "Wrong password.", status=401)
        r = RedirectResponse(nxt, status_code=303)
        sec = _secure(request)
        r.set_cookie(COOKIE, make_cookie(), max_age=MAX_AGE, httponly=True, secure=sec,
                     samesite="none" if sec else "lax", path="/")
        return r
    if path == "/login":
        return login_page(_safe_next(request.query_params.get("next", "/")))
    if path == "/logout":
        r = RedirectResponse("/login", status_code=303)
        r.delete_cookie(COOKIE, path="/")
        return r
    if valid(request.cookies.get(COOKIE)) or path in OPEN:
        return await call_next(request)
    if path.startswith("/api/"):
        return JSONResponse({"detail": "sign in required"}, status_code=401)
    return RedirectResponse(f"/login?next={quote(path)}", status_code=303)
