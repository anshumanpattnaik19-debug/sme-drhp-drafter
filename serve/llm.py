"""OpenAI-compatible chat client for the fine-tuned SLM behind vLLM (or any compatible server)."""
from __future__ import annotations

import json
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


def make_chat(settings):
    url = settings["model_url"].rstrip("/")

    def chat(messages):
        body = {"model": settings["model_name"], "messages": messages,
                "temperature": float(settings.get("temperature", 0.2)), "max_tokens": int(settings.get("max_tokens", 3000))}
        try:
            r = httpx.post(f"{url}/chat/completions", json=body, headers=_headers(settings), timeout=600)
            r.raise_for_status()
        except httpx.HTTPError as e:
            raise ModelError(f"model server error: {e}") from e
        out = r.json()
        return out["choices"][0]["message"]["content"] or "", out.get("usage") or {}

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
