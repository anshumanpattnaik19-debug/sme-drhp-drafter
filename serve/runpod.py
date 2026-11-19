"""Host the drafting model on a RunPod Serverless endpoint that is billed only while a worker runs (docs/RUNPOD.md).

    python -m serve.runpod upload     # the A_qa_dpo adapter -> a private Hugging Face repo        (needs HF_TOKEN)
    python -m serve.runpod create     # vLLM endpoint: base + adapter, no always-on workers        (RUNPOD_API_KEY, HF_TOKEN)
    python -m serve.runpod check      # the app's own calls against it: models, drafting, extraction, streaming
    python -m serve.runpod smoke      # the whole app against it: upload issuer files, process, draft a section
    python -m serve.runpod delete     # remove the endpoint

Keys come from the environment, or from `.runpod.env` in the project folder (KEY=value lines, gitignored); they are
never printed or written anywhere else. The endpoint's id and URL are kept in build/runpod_endpoint.json, the check
results in build/runpod_check.json.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from pathlib import Path

import httpx

from serve import llm

ROOT = Path(__file__).resolve().parent.parent
STATE = ROOT / "build" / "runpod_endpoint.json"
ADAPTER = ROOT / "build" / "hf_upload" / "adapter"
API = "https://api.runpod.io/v2"
# RunPod's vLLM worker v2.30.3 runs vLLM 0.32.0, the version the adapters were served with on Colab and the VM; its
# image needs CUDA 13.0 on the host
IMAGE = "runpod/worker-v1-vllm:v2.30.3"
MIN_CUDA = "13.0"
BASE = "Qwen/Qwen2.5-7B-Instruct"
SERVED = "sme-drhp-7b"                      # the app's default model name (serve/store.py)
HF_SECRET = "sme_drhp_hf_token"             # RunPod secret holding HF_TOKEN, so the private adapter can be downloaded
DEFAULT_RATE = 0.00021                      # USD per second, 24 GB tier, if the catalog gave no price


ENV_FILE = ROOT / ".runpod.env"


def load_env_file():
    """KEY=value lines from .runpod.env into the environment, without overriding what is already set."""
    if ENV_FILE.is_file():
        for line in ENV_FILE.read_text(encoding="utf-8-sig").splitlines():
            k, sep, v = line.partition("=")
            if sep and k.strip() and not k.lstrip().startswith("#"):
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def key(name):
    load_env_file()
    v = os.environ.get(name, "").strip()
    if not v:
        sys.exit(f"{name} is not set: put it in .runpod.env or this terminal's environment (docs/RUNPOD.md, step 2)")
    return v


def load_state():
    return json.loads(STATE.read_text(encoding="utf-8")) if STATE.is_file() else {}


def save_state(**kw):
    s = {**load_state(), **kw}
    STATE.parent.mkdir(exist_ok=True)
    STATE.write_text(json.dumps(s, indent=1), encoding="utf-8")
    return s


def runpod(method, path, **kw):
    r = httpx.request(method, API + path, headers={"Authorization": f"Bearer {key('RUNPOD_API_KEY')}"}, timeout=60, **kw)
    if r.status_code >= 400 and r.status_code != 409:
        sys.exit(f"RunPod {method} {path} failed: HTTP {r.status_code} {r.text[:400]}")
    return r


# --- upload -------------------------------------------------------------------------------------------------------

def upload(args):
    from huggingface_hub import HfApi
    api = HfApi(token=key("HF_TOKEN"))
    repo_id = args.repo if "/" in args.repo else f"{api.whoami()['name']}/{args.repo}"
    api.create_repo(repo_id, private=True, exist_ok=True)
    api.upload_folder(repo_id=repo_id, folder_path=str(ADAPTER), commit_message="A_qa_dpo adapter")
    save_state(adapter_repo=repo_id)
    print(f"adapter uploaded to the private repo {repo_id} ({sum(f.stat().st_size for f in ADAPTER.iterdir()) // 2**20} MB)")


# --- create -------------------------------------------------------------------------------------------------------

def pick_pools(gpus):
    """The cheapest serverless pool with 24 GB, then the cheapest with 48 GB as the fallback when 24 GB cards are
    taken. Returns [(pool, memory, price per hour, names)]."""
    pools = {}
    for g in gpus:
        p, price = g.get("pool"), (g.get("price") or {}).get("serverless")
        if not p or price is None or g.get("manufacturer", "NVIDIA") != "NVIDIA":
            continue
        e = pools.setdefault(p, [g["memory"], price, []])
        e[0], e[1] = min(e[0], g["memory"]), max(e[1], price)
        e[2].append(g.get("name") or g["id"])
    out = []
    for mem in (24, 48):
        cands = sorted((v[1], k, v) for k, v in pools.items() if v[0] == mem)
        if cands:
            _, p, (m, price, names) = cands[0]
            out.append((p, m, price, names))
    if not out:
        sys.exit("no 24 GB or 48 GB serverless GPU pool in RunPod's catalog")
    return out


def endpoint_body(pools, repo_id, args):
    env = {"MODEL_NAME": BASE, "MAX_MODEL_LEN": "6144", "GPU_MEMORY_UTILIZATION": "0.9",
           "ENABLE_LORA": "true", "MAX_LORA_RANK": "16", "MAX_LORAS": "1",
           "LORA_MODULES": json.dumps([{"name": SERVED, "path": repo_id}]),
           "HF_TOKEN": "{{ RUNPOD_SECRET_%s }}" % HF_SECRET}
    return {"name": args.name, "image": IMAGE, "type": "QUEUE", "disk": 40, "env": env,
            "gpu": {"pools": [p[0] for p in pools], "count": 1, "minCudaVersion": MIN_CUDA},
            # no always-on worker, one at most: nothing is billed while no request is running
            "workers": {"min": 0, "max": 1, "idleTimeout": args.idle},
            "scaling": {"type": "QUEUE_DELAY", "queueDelay": 4},
            "flashboot": "FLASHBOOT", "timeout": 600_000}


def create(args):
    repo_id = args.repo or load_state().get("adapter_repo")
    if not repo_id:
        sys.exit("no adapter repo: run `python -m serve.runpod upload` first, or pass --repo user/name")
    if args.dry_run:
        pools = [("<24 GB pool>", 24, 0.75, []), ("<48 GB pool>", 48, 1.22, [])]
        print(json.dumps(endpoint_body(pools, repo_id, args), indent=1))
        return
    r = runpod("POST", "/account/secrets", json={"name": HF_SECRET, "value": key("HF_TOKEN"),
                                                 "description": "Hugging Face token for the SME DRHP adapter"})
    print("Hugging Face token stored as a RunPod secret" if r.status_code != 409 else
          f"RunPod secret {HF_SECRET} already exists; kept (delete it in the console if the token changed)")
    pools = pick_pools(runpod("GET", "/catalog/gpus").json()["gpus"])
    for p, mem, price, names in pools:
        print(f"GPU pool {p}: {mem} GB, ${price}/h, {', '.join(names)}")
    ep = runpod("POST", "/serverless", json=endpoint_body(pools, repo_id, args)).json()
    s = save_state(endpoint_id=ep["id"], name=ep.get("name"), model_url=f"https://api.runpod.ai/v2/{ep['id']}/openai/v1",
                   rate_per_s=pools[0][2] / 3600, image=IMAGE, adapter_repo=repo_id)
    print(f"endpoint {s['endpoint_id']} created: 0 always-on workers, at most 1, idle timeout {args.idle} s")
    print(f"model_url for the app's Settings: {s['model_url']}")


def delete(args):
    eid = args.endpoint or load_state().get("endpoint_id")
    if not eid:
        sys.exit("no endpoint id")
    runpod("DELETE", f"/serverless/{eid}")
    st = load_state()
    for k in ("endpoint_id", "model_url"):
        st.pop(k, None)
    STATE.write_text(json.dumps(st, indent=1), encoding="utf-8")
    print(f"endpoint {eid} deleted")


# --- check --------------------------------------------------------------------------------------------------------

def test_rows(n):
    """n drafting rows and one extraction row from the test split (prompts exactly as the app builds them)."""
    path = ROOT / "trainset" / "out" / "test.jsonl"
    if not path.is_file():
        from data.prompts import drafting_messages, extraction_messages
        facts = [{"type": "amount", "label": "Revenue from operations FY2024-25", "value": "₹ 48.62 crore"},
                 {"type": "date", "label": "Date of incorporation", "value": "March 14, 2011"}]
        d = drafting_messages("Example Industries Limited", "Our Business", ["Overview"], "Overview", facts)
        e = extraction_messages("Our revenue from operations was ₹ 48.62 crore in FY2024-25.")
        return [d] * n, e
    rows = [json.loads(line) for line in path.open(encoding="utf-8")]
    drafts = [r["messages"][:-1] for r in rows if r["metadata"]["skill"] == "drafting"][:n]
    ext = next(r["messages"][:-1] for r in rows if r["metadata"]["skill"] == "extraction")
    return drafts, ext


def check(args):
    from data.prompts import trim_repeats
    from draft.writer import DRAFT_FREQUENCY_PENALTY
    st = load_state()
    url = args.url or st.get("model_url")
    if not url:
        sys.exit("no endpoint: run `python -m serve.runpod create` first, or pass --url")
    load_env_file()
    settings = {"model_url": url, "model_name": args.model, "api_key": os.environ.get("RUNPOD_API_KEY", ""),
                "temperature": 0.2, "max_tokens": 2200}
    res, ok, gpu_s = {"url": url}, True, 0.0

    # 1. the model list; the first call starts a worker (cold start), so wait for it
    t0 = time.perf_counter()
    while True:
        m = llm.check(settings, timeout=90)
        if m["reachable"] or time.perf_counter() - t0 > args.wait:
            break
        print(f"  waiting for a worker ({int(time.perf_counter() - t0)} s): {m['error']}")
        time.sleep(10)
    res["first_response_s"] = round(time.perf_counter() - t0, 1)
    res["models"] = m["models"]
    served = args.model in m["models"]
    ok &= served
    print(f"[{'ok' if served else 'FAIL'}] models {m['models']} after {res['first_response_s']} s "
          f"(cold start included); '{args.model}' {'served' if served else 'NOT served'}")
    if not m["reachable"]:
        print(f"[FAIL] no answer within {args.wait} s: {m['error']}")
        res["error"] = m["error"]
        return finish(res, False, time.perf_counter() - t0, st)

    # 2. the app's own reachability check (4 s timeout) now that a worker is up
    app = llm.check(settings)
    res["app_check"] = app
    print(f"[{'ok' if app['reachable'] else 'warn'}] the app's 4 s check: "
          f"{'reachable, ' + str(app['latency_ms']) + ' ms' if app['reachable'] else app['error']}")

    chat = llm.make_chat(settings)
    drafts, ext = test_rows(args.drafts)

    # 3. drafting, as draft/writer.py calls it
    res["drafts"] = []
    for i, msgs in enumerate(drafts, 1):
        t = time.perf_counter()
        try:
            text, usage = chat(msgs, frequency_penalty=DRAFT_FREQUENCY_PENALTY)
        except llm.ModelError as e:
            print(f"[FAIL] draft {i}: {e}")
            ok = False
            continue
        s = time.perf_counter() - t
        gpu_s += s
        toks = usage.get("completion_tokens") or 0
        looped = trim_repeats(text)[1]
        res["drafts"].append({"seconds": round(s, 1), "completion_tokens": toks, "words": len(text.split()),
                              "loop": looped})
        print(f"[ok] draft {i}: {len(text.split())} words, {toks} tokens in {s:.1f} s "
              f"({toks / s:.0f} tokens/s){', LOOPED (the app trims it)' if looped else ''}")

    # 4. extraction: valid JSON with a facts list
    t = time.perf_counter()
    try:
        text, _ = chat(ext)
        gpu_s += time.perf_counter() - t
        raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip())
        facts = json.loads(raw)["facts"]
        res["extraction"] = {"facts": len(facts), "seconds": round(time.perf_counter() - t, 1)}
        print(f"[ok] extraction: {len(facts)} facts, valid JSON")
    except (llm.ModelError, ValueError, KeyError, TypeError) as e:
        res["extraction"] = {"error": str(e)[:200]}
        ok = False
        print(f"[FAIL] extraction: {str(e)[:200]}")

    # 5. streaming, as the assistant panel uses it (rag/agent.py)
    t, first, parts = time.perf_counter(), None, []
    try:
        for d in llm.stream_chat(settings, [{"role": "user", "content": "In one sentence, what is a DRHP?"}],
                                 max_tokens=80):
            first = first or time.perf_counter() - t
            parts.append(d)
    except llm.ModelError as e:
        print(f"[FAIL] streaming: {e}")
    gpu_s += time.perf_counter() - t
    streamed = bool(parts)
    ok &= streamed
    res["streaming"] = {"chunks": len(parts), "first_token_s": round(first, 2) if first else None}
    print(f"[{'ok' if streamed else 'FAIL'}] streaming: {len(parts)} chunks"
          + (f", first after {first:.1f} s" if first else ""))
    return finish(res, ok, res["first_response_s"] + gpu_s, st)


def finish(res, ok, seconds, st):
    rate = st.get("rate_per_s", DEFAULT_RATE)
    res["billed_estimate_usd"] = round(seconds * rate, 4)
    res["ok"] = bool(ok)
    out = ROOT / "build" / "runpod_check.json"
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\n{'ALL CHECKS PASSED' if ok else 'SOME CHECKS FAILED'}: about {seconds:.0f} s of worker time, "
          f"about ${res['billed_estimate_usd']:.3f} plus the idle timeout; results in {out.relative_to(ROOT)}")
    return 0 if ok else 1


def smoke(args):
    """vm/docker_smoke.py against a running app (source run or Docker container), with the endpoint as its model."""
    import importlib.util
    load_env_file()
    url = args.url or load_state().get("model_url")
    if not url:
        sys.exit("no endpoint: run `python -m serve.runpod create` first, or pass --url")
    spec = importlib.util.spec_from_file_location("docker_smoke", ROOT / "vm" / "docker_smoke.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    mod.main(args.app, url, ROOT / args.bundle)


def main(argv=None):
    ap = argparse.ArgumentParser(prog="python -m serve.runpod", description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("upload", help="upload the adapter to a private Hugging Face repo")
    p.add_argument("--repo", default="sme-drhp-7b-lora", help="repo name, or user/name")
    p = sub.add_parser("create", help="create the serverless endpoint")
    p.add_argument("--repo", help="Hugging Face repo of the adapter (default: the one uploaded)")
    p.add_argument("--name", default="sme-drhp-7b")
    p.add_argument("--idle", type=int, default=30, help="seconds a worker stays up after its last request (billed)")
    p.add_argument("--dry-run", action="store_true", help="print the request body and stop")
    p = sub.add_parser("check", help="run the app's calls against the endpoint")
    p.add_argument("--url", help="OpenAI-compatible base URL (default: the endpoint created)")
    p.add_argument("--model", default=SERVED)
    p.add_argument("--drafts", type=int, default=3)
    p.add_argument("--wait", type=int, default=600, help="seconds to wait for a cold start")
    p = sub.add_parser("smoke", help="the whole app against the endpoint (vm/docker_smoke.py)")
    p.add_argument("--app", default="http://127.0.0.1:8765", help="the running app (source run or Docker container)")
    p.add_argument("--url", help="model URL (default: the endpoint created)")
    p.add_argument("--bundle", default="bundles/out/kestrel_flexipak")
    p = sub.add_parser("delete", help="delete the endpoint")
    p.add_argument("--endpoint")
    args = ap.parse_args(argv)
    return {"upload": upload, "create": create, "check": check, "smoke": smoke, "delete": delete}[args.cmd](args) or 0


if __name__ == "__main__":
    sys.exit(main())
