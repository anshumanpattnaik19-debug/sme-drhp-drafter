"""Teacher driver: one call per unit to an OpenAI-compatible server (vLLM on Colab, the mock offline).

    python -m teacher.driver --jobs work/teacher_jobs.jsonl --out work/teacher_responses.jsonl \
        --endpoint http://localhost:8000/v1 --model Qwen/Qwen3-32B-AWQ

Resumable: units already in --out are skipped. Every response keeps the model id, timestamp, latency and the
parsed facts (or the parse error). The script refuses to run without --endpoint; nothing is filled in by code.
Qwen3 thinking blocks are stripped and thinking is switched off through the chat template where supported.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from data.facts import normalise  # noqa: E402
from teacher.prompts import teacher_messages  # noqa: E402


def strip_think(text):
    return re.sub(r"<think>.*?</think>\s*", "", text or "", flags=re.DOTALL).strip()


def parse_json(text):
    t = strip_think(text)
    t = re.sub(r"^```(?:json)?\s*|\s*```$", "", t.strip())
    m = re.search(r"\{.*\}", t, re.S)
    if not m:
        raise ValueError("no JSON object in the response")
    return json.loads(m.group(0))


def call(client, endpoint, model, messages, max_tokens=4096, temperature=0.0):
    body = {"model": model, "messages": messages, "max_tokens": max_tokens, "temperature": temperature,
            "chat_template_kwargs": {"enable_thinking": False}}
    r = client.post(endpoint.rstrip("/") + "/chat/completions", json=body, timeout=600)
    r.raise_for_status()
    data = r.json()
    return data["choices"][0]["message"]["content"] or "", data.get("usage") or {}


def run(jobs, out_path, endpoint, model, client=None, limit=None, log=print):
    import httpx
    client = client or httpx.Client()
    done = set()
    if os.path.isfile(out_path):
        with open(out_path, encoding="utf-8") as fh:
            recs = [json.loads(ln) for ln in fh if ln.strip()]
        good = [r for r in recs if "error" not in r]
        if len(good) < len(recs):   # failed units are retried: drop their records so the rerun does not duplicate them
            with open(out_path, "w", encoding="utf-8") as fh:
                fh.writelines(json.dumps(r, ensure_ascii=False) + "\n" for r in good)
        done = {r["unit_id"] for r in good}
    todo = [j for j in jobs if j["unit_id"] not in done][:limit]
    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    ok = bad = 0
    with open(out_path, "a", encoding="utf-8") as out:
        for i, job in enumerate(todo, 1):
            t0 = time.perf_counter()
            rec = {"unit_id": job["unit_id"], "model": model, "endpoint": endpoint, "at": time.strftime("%Y-%m-%dT%H:%M:%S")}
            try:
                text, usage = call(client, endpoint, model, job.get("messages") or teacher_messages(job))
                facts, errors = normalise(parse_json(text))
                rec.update(response=text, facts=facts, schema_errors=errors, usage=usage)
                ok += 1
            except Exception as e:  # noqa: BLE001 - keep going, record the failure
                rec.update(response=None, facts=None, error=str(e)[:300])
                bad += 1
            rec["latency_s"] = round(time.perf_counter() - t0, 2)
            out.write(json.dumps(rec, ensure_ascii=False) + "\n")
            out.flush()
            if i % 25 == 0 or i == len(todo):
                log(f"teacher: {i}/{len(todo)} done ({ok} parsed, {bad} failed)")
    return {"done": ok, "failed": bad, "skipped": len(done)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--jobs", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--endpoint", required=True, help="OpenAI-compatible base URL, e.g. http://localhost:8000/v1")
    ap.add_argument("--model", required=True)
    ap.add_argument("--limit", type=int)
    a = ap.parse_args()
    with open(a.jobs, encoding="utf-8") as fh:
        jobs = [json.loads(ln) for ln in fh if ln.strip()]
    print(run(jobs, a.out, a.endpoint, a.model, limit=a.limit))


if __name__ == "__main__":
    main()
