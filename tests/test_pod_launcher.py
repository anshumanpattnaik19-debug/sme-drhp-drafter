"""App on a RunPod CPU pod: auto-stop (serve/idle.py), the pod settings (serve/pod.py) and the launcher (launcher/app.py),
with RunPod mocked."""
import importlib.util
import json
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from serve import idle
from serve.pod import pod_body

ROOT = Path(__file__).resolve().parent.parent


def test_idle_clock_ignores_the_status_poll_and_running_jobs_keep_the_pod():
    idle._last = time.time() - 3600
    assert idle.idle_for() >= 3599 and idle.idle_for(busy=True) == 0.0
    assert "/api/health" in idle.IGNORED and "/login" in idle.IGNORED


def test_watchdog_is_off_unless_on_a_pod_with_a_limit(monkeypatch):
    monkeypatch.delenv("RUNPOD_POD_ID", raising=False)
    monkeypatch.setenv("POD_IDLE_MINUTES", "30")
    monkeypatch.setenv("RUNPOD_PODS_KEY", "k")
    assert idle.watch(lambda: False) is None


def test_pod_holds_secret_references_not_secrets():
    body = pod_body("https://api.runpod.ai/v2/abc/openai/v1", "user/drhp-studio-app", 30)
    env = body["env"]
    for var in ("APP_PASSWORD", "RUNPOD_API_KEY", "RUNPOD_PODS_KEY", "HF_TOKEN", "APP_SESSION_SECRET"):
        assert env[var].startswith("{{ RUNPOD_SECRET_"), var
    assert env["POD_IDLE_MINUTES"] == "30" and body["ports"] == ["7860/http"] and body["cpu"]["vcpuCount"] == 2
    assert "unset HF_TOKEN" in body["cmd"][0]                  # the app process never sees the Hugging Face token


@pytest.fixture()
def launcher(monkeypatch):
    monkeypatch.setenv("APP_PASSWORD", "test-only-pw")
    monkeypatch.setenv("RUNPOD_PODS_KEY", "k")
    monkeypatch.setenv("LAUNCHER_SECRET", "s")
    monkeypatch.setenv("POD_ID", "pod123")
    spec = importlib.util.spec_from_file_location("launcher_app", ROOT / "launcher" / "app.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    state = {"status": "EXITED", "actions": []}

    def runpod(method, path, **kw):
        if method == "POST":
            state["actions"].append(kw["json"]["action"])
            state["status"] = "RUNNING"
        return {"status": state["status"]}

    monkeypatch.setattr(mod, "_runpod", runpod)
    monkeypatch.setattr(mod, "_answers", lambda: state["status"] == "RUNNING")
    return mod, state


def test_launcher_refuses_a_wrong_password_and_starts_the_pod_for_the_right_one(launcher):
    mod, state = launcher
    c = TestClient(mod.app, base_url="https://testserver")
    assert c.get("/status").status_code == 401
    r = c.post("/start", data={"password": "nope"})
    assert r.status_code == 401 and state["actions"] == []
    r = c.post("/start", data={"password": "test-only-pw"})
    assert r.status_code == 200 and state["actions"] == ["start"] and "Starting DRHP Studio" in r.text
    s = c.get("/status").json()
    assert s["ready"] and s["url"] == "https://pod123-7860.proxy.runpod.net"
    assert "k" not in json.dumps(s).replace("ready", "")      # the RunPod key never reaches the browser


def test_launcher_locks_out_repeated_wrong_passwords(launcher):
    mod, _ = launcher
    c = TestClient(mod.app, base_url="https://testserver")
    for _ in range(mod.MAX_FAILS):
        c.post("/start", data={"password": "nope"})
    assert c.post("/start", data={"password": "test-only-pw"}).status_code == 429
