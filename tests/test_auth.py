"""Shared-password gate (serve/auth.py) and model settings pinned by the host (serve/store.pinned), as on the Space."""
import os
import tempfile

os.environ.setdefault("DRHP_WORKSPACE", tempfile.mkdtemp(prefix="drhp_ws_"))

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from serve import auth, store  # noqa: E402
from serve.app import app  # noqa: E402

PW = "test-only-pw"


@pytest.fixture()
def client(monkeypatch):
    monkeypatch.setenv("APP_PASSWORD", PW)
    auth._fails.clear()
    return TestClient(app)


def test_nothing_is_reachable_without_the_password(client):
    assert client.get("/api/projects").status_code == 401
    assert client.get("/api/settings").status_code == 401
    assert client.post("/api/projects", json={"name": "x"}).status_code == 401
    r = client.get("/", follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"].startswith("/login")
    assert "password" in client.get("/login").text


def test_wrong_password_is_refused_and_the_right_one_signs_in(client):
    r = client.post("/login", data={"password": "nope", "next": "/"}, follow_redirects=False)
    assert r.status_code == 401 and "Wrong password" in r.text and auth.COOKIE not in r.cookies
    r = client.post("/login", data={"password": PW, "next": "/projects"}, follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == "/projects"
    assert PW not in r.headers.get("set-cookie", "")              # the cookie never holds the password
    assert client.get("/api/projects").status_code == 200
    client.get("/logout")
    assert client.get("/api/projects").status_code == 401


def test_repeated_wrong_passwords_are_locked_out(client):
    for _ in range(auth.MAX_FAILS):
        client.post("/login", data={"password": "nope"})
    assert client.post("/login", data={"password": PW}).status_code == 429


def test_open_redirect_after_login_is_refused(client):
    r = client.post("/login", data={"password": PW, "next": "//evil.example"}, follow_redirects=False)
    assert r.headers["location"] == "/"


def test_gate_is_off_without_a_password(monkeypatch):
    monkeypatch.delenv("APP_PASSWORD", raising=False)
    assert TestClient(app).get("/api/meta").status_code == 200


def test_pinned_model_settings_cannot_be_changed_or_sent_elsewhere(monkeypatch):
    monkeypatch.setenv("DRHP_MODEL_URL", "https://api.runpod.ai/v2/abc/openai/v1")
    monkeypatch.setenv("RUNPOD_API_KEY", "secret-key")
    monkeypatch.delenv("APP_PASSWORD", raising=False)
    c = TestClient(app)
    r = c.put("/api/settings", json={"model_url": "https://attacker.example/v1", "api_key": "x"}).json()
    assert r["model_url"] == "https://api.runpod.ai/v2/abc/openai/v1" and r["api_key"] == "" and r["api_key_set"]
    assert "secret-key" not in open(os.path.join(store.ROOT, "settings.json"), encoding="utf-8").read()
    seen = []
    monkeypatch.setattr("serve.llm.check", lambda s, timeout=4.0: seen.append(s["model_url"]) or {"reachable": False})
    c.post("/api/settings/test", json={"model_url": "https://attacker.example/v1"})
    assert seen == ["https://api.runpod.ai/v2/abc/openai/v1"]
