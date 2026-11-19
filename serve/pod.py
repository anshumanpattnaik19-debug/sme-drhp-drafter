"""The app on a RunPod CPU pod, started and stopped through the RunPod API (docs/HOSTING.md).

    python -m serve.pod bundle        # upload the app (code and built UI) to a private Hugging Face repo
    python -m serve.pod create        # create the pod once (2 vCPU, 8 GB); it starts at once
    python -m serve.pod start         # start a stopped pod, wait until the app answers, print the link
    python -m serve.pod stop          # stop it: compute billing ends, the link stays the same
    python -m serve.pod status        # pod state, hourly rate while running, whether the app answers
    python -m serve.pod launcher      # deploy the launcher page (a public Hugging Face Space, no app code)

The pod runs a public Python image and, at each start, downloads the app bundle with the Hugging Face token held as a
RunPod secret, so no image registry is needed. Its link is https://<pod id>-7860.proxy.runpod.net; a stopped pod
resumes on the same host, so the link only changes if the pod is terminated and created again. The app stops its own
pod after POD_IDLE_MINUTES without use (serve/idle.py).

Keys come from the environment or .runpod.env and are never printed: RUNPOD_PODS_KEY (Pods read/write) for the pod,
RUNPOD_API_KEY (the model endpoint, Secrets) and HF_TOKEN. In the pod they are RunPod secrets.
"""
from __future__ import annotations

import argparse
import secrets
import shutil
import sys
import time

import httpx

from serve.runpod import API, HF_SECRET, ROOT, key, load_state, save_state

NAME = "drhp-studio"
CPU = {"id": "cpu3g", "vcpuCount": 2}            # General Purpose: 2 vCPU, 8 GB, $0.08/h while running
PORT = 7860
IDLE_MINUTES = 30
BUNDLE_REPO = "drhp-studio-app"
SECRETS = {"drhp_app_password": "APP_PASSWORD", "drhp_model_key": "RUNPOD_API_KEY", "drhp_pods_key": "RUNPOD_PODS_KEY"}
START = """set -e
apt-get update -qq && apt-get install -y -qq --no-install-recommends libgl1 libglib2.0-0 libxcb1 >/dev/null
pip install -q --no-cache-dir --root-user-action=ignore huggingface_hub
python -c "import os; from huggingface_hub import snapshot_download; snapshot_download(os.environ['APP_BUNDLE'], local_dir='/app', token=os.environ['HF_TOKEN'])"
unset HF_TOKEN
cd /app && pip install -q --no-cache-dir --root-user-action=ignore -r requirements-app.txt
mkdir -p /app/workspace
exec python -m uvicorn serve.app:app --host 0.0.0.0 --port 7860
"""


def pods_key():
    return key("RUNPOD_PODS_KEY")


def api(method, path, k=None, **kw):
    r = httpx.request(method, API + path, headers={"Authorization": f"Bearer {k or pods_key()}"}, timeout=60, **kw)
    if r.status_code >= 400:
        sys.exit(f"RunPod {method} {path}: HTTP {r.status_code} {r.text[:300]}")
    return r.json() if r.content else {}


def app_url(pod_id):
    return f"https://{pod_id}-{PORT}.proxy.runpod.net"


def pod_id():
    pid = load_state().get("pod_id")
    if not pid:
        sys.exit("no pod yet: run `python -m serve.pod create`")
    return pid


def app_answers(url, timeout=8):
    try:
        return httpx.get(f"{url}/login", timeout=timeout).status_code == 200
    except httpx.HTTPError:
        return False


# --- bundle and secrets ----------------------------------------------------------------------------------------------

def bundle(args):
    """The app code and the built UI to a private Hugging Face repo, read by the pod at start."""
    from huggingface_hub import HfApi
    from serve.space import STAGE, stage
    n = stage()
    for p in ("Dockerfile", "README.md"):
        (STAGE / p).unlink(missing_ok=True)
    shutil.copytree(ROOT / "ui" / "dist", STAGE / "ui" / "dist")
    hf = HfApi(token=key("HF_TOKEN"))
    repo = f"{hf.whoami()['name']}/{BUNDLE_REPO}"
    hf.create_repo(repo, private=True, exist_ok=True)
    hf.upload_folder(repo_id=repo, folder_path=str(STAGE), commit_message="app bundle", delete_patterns=["*"])
    save_state(app_bundle=repo)
    print(f"app bundle uploaded to the private repo {repo} ({n} code files and the built UI)")


def put_secret(name, value):
    """Create or update a RunPod secret (the account key with Secrets access)."""
    k = key("RUNPOD_API_KEY")
    r = httpx.post(f"{API}/account/secrets", json={"name": name, "value": value},
                   headers={"Authorization": f"Bearer {k}"}, timeout=60)
    if r.status_code == 409:
        have = api("GET", "/account/secrets", k)
        sid = next(s["id"] for s in (have.get("secrets") or have.get("data") or have) if s["name"] == name)
        api("PATCH", f"/account/secrets/{sid}", k, json={"value": value})
    elif r.status_code >= 400:
        sys.exit(f"RunPod secret {name}: HTTP {r.status_code} {r.text[:200]}")


# --- pod -------------------------------------------------------------------------------------------------------------

def pod_body(model_url, bundle_repo, idle_minutes=IDLE_MINUTES):
    ref = "{{ RUNPOD_SECRET_%s }}"
    env = {"APP_PASSWORD": ref % "drhp_app_password", "RUNPOD_API_KEY": ref % "drhp_model_key",
           "RUNPOD_PODS_KEY": ref % "drhp_pods_key", "HF_TOKEN": ref % HF_SECRET,
           "APP_SESSION_SECRET": ref % "drhp_session_secret", "DRHP_MODEL_URL": model_url,
           "DRHP_MODEL_NAME": "sme-drhp-7b", "APP_BUNDLE": bundle_repo, "POD_IDLE_MINUTES": str(idle_minutes),
           "DRHP_WORKSPACE": "/app/workspace", "PYTHONUNBUFFERED": "1"}
    return {"name": NAME, "image": "python:3.12-slim", "cloud": "SECURE", "cpu": CPU, "disk": 20,
            "ports": [f"{PORT}/http"], "env": env, "entrypoint": ["bash", "-c"], "cmd": [START]}


def create(args):
    st = load_state()
    if not st.get("app_bundle"):
        sys.exit("no app bundle: run `python -m serve.pod bundle` first")
    for name, var in SECRETS.items():
        put_secret(name, key(var))
    put_secret("drhp_session_secret", secrets.token_hex(32))
    pod = api("POST", "/pods", json=pod_body(st["model_url"], st["app_bundle"], args.idle))
    save_state(pod_id=pod["id"], app_url=app_url(pod["id"]))
    print(f"pod {pod['id']} created (${pod.get('cost', '?')}/h while running, auto-stop after {args.idle} min idle)")
    wait_ready(pod["id"])


def wait_ready(pid, limit=900):
    url, t0 = app_url(pid), time.time()
    while time.time() - t0 < limit:
        p = api("GET", f"/pods/{pid}")
        if p["status"] in ("EXITED", "ERROR", "TERMINATED"):
            sys.exit(f"pod {pid} is {p['status']}")
        if p["status"] == "RUNNING" and app_answers(url):
            print(f"app ready after {time.time() - t0:.0f} s: {url}")
            return url
        time.sleep(10)
    sys.exit(f"the app did not answer within {limit} s; see the pod's logs in the RunPod console")


def start(args):
    pid = pod_id()
    p = api("GET", f"/pods/{pid}")
    if p["status"] in ("EXITED", "ERROR"):
        api("POST", f"/pods/{pid}/action", json={"action": "start"})
        print(f"pod {pid} starting (installs the app, about 3–4 minutes)")
    wait_ready(pid)


def stop(args):
    pid = pod_id()
    p = api("GET", f"/pods/{pid}")
    if p["status"] in ("RUNNING", "PROVISIONING", "STARTING"):
        api("POST", f"/pods/{pid}/action", json={"action": "stop"})
    print(f"pod {pid} stopped: no compute billing; the link stays {app_url(pid)}")


def status(args):
    pid = pod_id()
    p = api("GET", f"/pods/{pid}")
    up = p["status"] == "RUNNING" and app_answers(app_url(pid))
    billing = f"billing ${p.get('cost')}/h" if p["status"] in ("RUNNING", "PROVISIONING", "STARTING") else "not billed"
    print(f"pod {pid}: {p['status']} ({billing}) | app {'answers' if up else 'not answering'} | {app_url(pid)}")


def launcher(args):
    from huggingface_hub import HfApi
    pid = pod_id()
    hf = HfApi(token=key("HF_TOKEN"))
    repo = f"{hf.whoami()['name']}/{args.name}"
    hf.create_repo(repo, repo_type="space", space_sdk="docker", private=False, exist_ok=True)
    for name, var in (("APP_PASSWORD", "APP_PASSWORD"), ("RUNPOD_PODS_KEY", "RUNPOD_PODS_KEY")):
        hf.add_space_secret(repo, name, key(var))
    hf.add_space_secret(repo, "LAUNCHER_SECRET", secrets.token_hex(32))
    hf.add_space_variable(repo, "POD_ID", pid)
    hf.upload_folder(repo_id=repo, repo_type="space", folder_path=str(ROOT / "launcher"), commit_message="launcher",
                     delete_patterns=["*"], ignore_patterns=["__pycache__/*", "*.pyc"])
    save_state(launcher=f"https://{repo.replace('/', '-').lower()}.hf.space")
    print(f"launcher Space {repo}: https://{repo.replace('/', '-').lower()}.hf.space (builds for a few minutes)")


def main(argv=None):
    ap = argparse.ArgumentParser(prog="python -m serve.pod", description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    for c in ("bundle", "start", "stop", "status"):
        sub.add_parser(c)
    p = sub.add_parser("create")
    p.add_argument("--idle", type=int, default=IDLE_MINUTES, help="minutes without use before the app stops the pod")
    p = sub.add_parser("launcher")
    p.add_argument("--name", default="drhp-launcher")
    args = ap.parse_args(argv)
    return {"bundle": bundle, "create": create, "start": start, "stop": stop, "status": status,
            "launcher": launcher}[args.cmd](args) or 0


if __name__ == "__main__":
    sys.exit(main())
