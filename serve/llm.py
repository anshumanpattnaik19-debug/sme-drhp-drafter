"""OpenAI-compatible chat client for the fine-tuned SLM behind vLLM (or any compatible server)."""
from __future__ import annotations

import json
import re
import time

import httpx


class ModelError(RuntimeError):
    pass


def _headers(s):
    h = {"Content-Type": "application/json"}
    if s.get("api_key"):
        h["Authorization"] = f"Bearer {s['api_key']}"
    return h


def check(settings, timeout=4.0):
    """{"reachable", "models", "latency_ms", "error"}"""
    url = settings["model_url"].rstrip("/")
    t0 = time.perf_counter()
    try:
        r = httpx.get(f"{url}/models", headers=_headers(settings), timeout=timeout)
        r.raise_for_status()
        models = [m.get("id") for m in r.json().get("data", [])]
        return {"reachable": True, "models": models, "latency_ms": round((time.perf_counter() - t0) * 1000), "error": None}
    except Exception as e:  # noqa: BLE001
        return {"reachable": False, "models": [], "latency_ms": None, "error": str(e)[:200]}


RE_RUNPOD = re.compile(r"^(https://api\.runpod\.ai/v2/[^/]+)/openai/v1$")


def status(settings, timeout=4.0):
    """check() for the app's periodic status (the UI polls every 30 s). A RunPod Serverless endpoint is asked for its
    /health, which starts no worker: a /models call is a billed job that wakes a worker, and polling it would keep one
    running while the app is merely open (docs/RUNPOD.md)."""
    m = RE_RUNPOD.match(settings["model_url"].rstrip("/"))
    if not m:
        return check(settings, timeout)
    t0 = time.perf_counter()
    try:
        r = httpx.get(f"{m.group(1)}/health", headers=_headers(settings), timeout=timeout)
        r.raise_for_status()
        w = r.json().get("workers", {})
        return {"reachable": True, "models": [settings["model_name"]], "latency_ms": round((time.perf_counter() - t0) * 1000),
                "error": None, "serverless": True, "workers_running": w.get("running", 0)}   # only running ones are billed
    except Exception as e:  # noqa: BLE001
        return {"reachable": False, "models": [], "latency_ms": None, "error": str(e)[:200]}


def make_chat(settings):
    """chat(messages, frequency_penalty=0.0, n=1, temperature=None) -> (text, usage). A positive frequency_penalty is sent to
    the server (vLLM, OpenAI-compatible); 0 leaves it out, so Q&A and other callers keep the server's default. With n > 1 the
    server writes n samples of the same prompt in one request and the first value is a list of n texts (best-of-n drafting)."""
    url = settings["model_url"].rstrip("/")

    def chat(messages, frequency_penalty=0.0, n=1, temperature=None):
        body = {"model": settings["model_name"], "messages": messages,
                "temperature": float(settings.get("temperature", 0.2) if temperature is None else temperature),
                "max_tokens": int(settings.get("max_tokens", 3000))}
        if frequency_penalty:
            body["frequency_penalty"] = float(frequency_penalty)
        if n > 1:
            body["n"] = int(n)
        try:
            r = httpx.post(f"{url}/chat/completions", json=body, headers=_headers(settings), timeout=600)
            r.raise_for_status()
        except httpx.HTTPError as e:
            raise ModelError(f"model server error: {e}") from e
        out = r.json()
        if n > 1:
            return [ch["message"]["content"] or "" for ch in out["choices"]], out.get("usage") or {}
        return out["choices"][0]["message"]["content"] or "", out.get("usage") or {}

    chat.supports_n = True
    return chat


def stream_chat(settings, messages, max_tokens=1200):
    """Yield text deltas from an OpenAI-compatible streaming chat completion (server-sent events)."""
    url = settings["model_url"].rstrip("/")
    body = {"model": settings["model_name"], "messages": messages, "stream": True,
            "temperature": float(settings.get("temperature", 0.2)), "max_tokens": max_tokens}
    try:
        with httpx.stream("POST", f"{url}/chat/completions", json=body, headers=_headers(settings), timeout=600) as r:
            r.raise_for_status()
            for line in r.iter_lines():
                if not line.startswith("data:"):
                    continue
                data = line[5:].strip()
                if data == "[DONE]":
                    break
                try:
                    delta = json.loads(data)["choices"][0].get("delta", {}).get("content")
                except (ValueError, KeyError, IndexError):
                    continue
                if delta:
                    yield delta
    except httpx.HTTPError as e:
        raise ModelError(f"model server error: {e}") from e
