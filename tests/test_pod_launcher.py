"""App on a RunPod CPU pod: auto-stop (serve/idle.py), the pod settings (serve/pod.py) and the launcher (launcher/app.py),
with RunPod mocked."""
import importlib.util
import json
import time
from pathlib import Path

import httpx
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
    monkeypatch.setenv("POD_BODY", json.dumps({"name": "drhp-studio", "image": "x"}))
    spec = importlib.util.spec_from_file_location("launcher_app", ROOT / "launcher" / "app.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    state = {"pods": [{"id": "pod123", "name": "drhp-studio", "status": "EXITED"}], "calls": [], "host_full": False}

    def runpod(method, path, **kw):
        state["calls"].append(f"{method} {path.split('/')[-1] if 'action' in path else path}")
        if method == "GET":
            return list(state["pods"])
        if method == "POST" and path.endswith("/action"):
            if state["host_full"]:
                req = httpx.Request("POST", "https://x")
                raise httpx.HTTPStatusError("400", request=req, response=httpx.Response(400, request=req))
            state["pods"][0]["status"] = "RUNNING"
        elif method == "POST":
            state["pods"] = [{"id": "pod999", "name": "drhp-studio", "status": "RUNNING"}]
        elif method == "DELETE":
            state["pods"] = []
        return {}

    monkeypatch.setattr(mod, "_runpod", runpod)
    monkeypatch.setattr(mod, "_answers", lambda pod_id: True)
    return mod, state


def test_launcher_refuses_a_wrong_password_and_starts_the_pod_for_the_right_one(launcher):
    mod, state = launcher
    c = TestClient(mod.app, base_url="https://testserver")
    assert c.get("/status").status_code == 401
    r = c.post("/start", data={"password": "nope"})
    assert r.status_code == 401 and not any(x.startswith("POST") for x in state["calls"])
    r = c.post("/start", data={"password": "test-only-pw"})
    assert r.status_code == 200 and "POST action" in state["calls"] and "Starting DRHP Copilot" in r.text
    s = c.get("/status").json()
    assert s["ready"] and s["url"] == "https://pod123-7860.proxy.runpod.net"
    assert "k" not in json.dumps(s).replace("ready", "")      # the RunPod key never reaches the browser


def test_launcher_replaces_a_pod_whose_host_has_no_room(launcher):
    mod, state = launcher
    state["host_full"] = True
    c = TestClient(mod.app, base_url="https://testserver")
    assert c.post("/start", data={"password": "test-only-pw"}).status_code == 200
    assert "DELETE /pods/pod123" in state["calls"] and "POST /pods" in state["calls"]
    assert c.get("/status").json()["url"] == "https://pod999-7860.proxy.runpod.net"     # the new pod's address


def test_launcher_creates_a_pod_when_there_is_none(launcher):
    mod, state = launcher
    state["pods"] = []
    c = TestClient(mod.app, base_url="https://testserver")
    assert c.post("/start", data={"password": "test-only-pw"}).status_code == 200
    assert "POST /pods" in state["calls"] and "DELETE /pods/pod123" not in state["calls"]


def test_launcher_ignores_other_pods_and_a_running_pod_is_left_alone(launcher):
    mod, state = launcher
    state["pods"] = [{"id": "other", "name": "someone-else", "status": "EXITED"},
                     {"id": "pod123", "name": "drhp-studio", "status": "RUNNING"}]
    c = TestClient(mod.app, base_url="https://testserver")
    assert c.post("/start", data={"password": "test-only-pw"}).status_code == 200
    assert not any(x.startswith(("POST", "DELETE")) for x in state["calls"])


def test_launcher_locks_out_repeated_wrong_passwords(launcher):
    mod, _ = launcher
    c = TestClient(mod.app, base_url="https://testserver")
    for _ in range(mod.MAX_FAILS):
        c.post("/start", data={"password": "nope"})
    assert c.post("/start", data={"password": "test-only-pw"}).status_code == 429


def test_pod_start_replaces_a_pod_whose_host_is_full(monkeypatch):
    from serve import pod

    calls = []
    monkeypatch.setattr(pod, "pod_id", lambda: "old1")
    monkeypatch.setattr(pod, "pods_key", lambda: "k")
    monkeypatch.setattr(pod, "api", lambda m, p, k=None, **kw: {"status": "EXITED"})
    monkeypatch.setattr(pod, "load_state", lambda: {"pod_id": "old1"})
    monkeypatch.setattr(pod, "create", lambda a: calls.append("create"))
    monkeypatch.setattr(pod.httpx, "post", lambda *a, **kw: httpx.Response(
        400, json={"detail": "There are not enough free memory on the host machine to start this pod."}, request=httpx.Request("POST", "https://x")))
    monkeypatch.setattr(pod.httpx, "delete", lambda url, **kw: calls.append(f"delete {url.rsplit('/', 1)[-1]}") or httpx.Response(
        200, request=httpx.Request("DELETE", url)))
    pod.start(None)
    assert calls == ["delete old1", "create"]


def test_launcher_keeps_one_pod_when_two_visitors_created_two(launcher):
    mod, state = launcher
    state["pods"] = [{"id": "a", "name": "drhp-studio", "status": "RUNNING", "createdAt": "2026-11-19T09:00:00Z"},
                     {"id": "b", "name": "drhp-studio", "status": "PROVISIONING", "createdAt": "2026-11-19T09:00:05Z"},
                     {"id": "c", "name": "drhp-studio", "status": "EXITED", "createdAt": "2026-11-19T08:00:00Z"}]
    got = mod._current()
    assert got["id"] == "b" or got["id"] == "a"          # a live pod is kept
    deleted = {c.split("/")[-1] for c in state["calls"] if c.startswith("DELETE")}
    assert deleted == {"a", "b", "c"} - {got["id"]}


def test_a_sign_in_counts_as_use_but_the_sign_in_page_does_not():
    import asyncio

    from serve import idle

    class Req:
        def __init__(self, path, method):
            self.url = type("U", (), {"path": path})()
            self.method = method

    async def nxt(request):
        return None

    idle._last = 0.0
    asyncio.run(idle.touch(Req("/login", "GET"), nxt))
    assert idle._last == 0.0
    asyncio.run(idle.touch(Req("/login", "POST"), nxt))
    assert idle._last > 0.0


def test_pod_recipe_mounts_the_network_volume_the_way_runpods_schema_wants_it():
    body = pod_body("https://x/v1", "user/app", 10, {"id": "vol1", "dataCenter": "US-GA-2"})
    assert body["mounts"] == {"network": [{"volumeId": "vol1", "path": "/workspace"}]} and body["dataCenterIds"] == ["US-GA-2"]
    assert "networkVolumeId" not in body and body["env"]["DRHP_WORKSPACE"] == "/workspace/drhp"
    plain = pod_body("https://x/v1", "user/app", 10)
    assert "mounts" not in plain and plain["env"]["DRHP_WORKSPACE"] == "/app/workspace"        # without a volume the old path
