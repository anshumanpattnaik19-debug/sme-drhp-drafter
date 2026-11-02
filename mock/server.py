"""OpenAI-compatible mock server: schema-valid responses so every stage runs on the laptop before GPU time.

    python -m uvicorn mock.server:app --port 8001          # then --endpoint http://localhost:8001/v1

Teacher calls (fact extraction) get facts found by rules: every figure, date and proper name in the passage, so the
gates can be exercised end to end. Drafting calls get the facts restated as sentences. It is a harness, not a
model: its output says nothing about the teacher's or the student's quality.
"""
from __future__ import annotations

import json
import re
import time

from fastapi import FastAPI
from pydantic import BaseModel

from data.facts import RE_DATES, RE_FIG, RE_REF, proper_names

app = FastAPI(title="mock OpenAI-compatible server")
MODEL = "mock-teacher"


class ChatIn(BaseModel):
    model: str = MODEL
    messages: list[dict]
    max_tokens: int | None = None
    temperature: float | None = None
    stream: bool | None = False
    chat_template_kwargs: dict | None = None


def _label(text, start, words=5):
    toks = re.findall(r"[A-Za-z][A-Za-z&'/-]*", text[max(0, start - 120):start])
    return " ".join(toks[-words:]) or "Value"


def mock_facts(passage):
    facts, seen = [], set()
    for rx in RE_DATES:
        for m in rx.finditer(passage):
            v = m.group(0)
            if v not in seen:
                seen.add(v)
                facts.append({"type": "date", "label": _label(passage, m.start()) or "Date", "value": v})
    for m in RE_FIG.finditer(passage):
        v = m.group(0).strip("()")
        if v in seen or RE_REF.search(passage[max(0, m.start() - 14):m.start()]):
            continue
        seen.add(v)
        typ = "percent" if v.endswith("%") else "amount" if ("." in v or "," in v) else "count"
        facts.append({"type": typ, "label": _label(passage, m.start()), "value": v})
    for n in sorted(proper_names(passage)):
        typ = "entity" if re.search(r"(Limited|LLP|Bank|Ltd|Pvt)\.?$", n) else "person"
        facts.append({"type": typ, "label": "Name", "value": n})
    return facts


@app.get("/v1/models")
def models():
    return {"object": "list", "data": [{"id": MODEL, "object": "model"}]}


@app.post("/v1/chat/completions")
def chat(body: ChatIn):
    system = next((m["content"] for m in body.messages if m["role"] == "system"), "")
    user = body.messages[-1]["content"]
    if "extract" in system.lower():
        passage = user.split("PASSAGE:", 1)[-1]
        content = json.dumps({"facts": mock_facts(passage)}, ensure_ascii=False)
    else:
        m = re.search(r"FACTS: (\[.*?\])\n", user, re.S)
        facts = json.loads(m.group(1)) if m else []
        content = " ".join(f"The {f.get('label', 'value').lower()} is {f.get('value')}." for f in facts[:8]) or "[●]"
    return {"id": f"mock-{int(time.time() * 1000)}", "object": "chat.completion", "model": body.model,
            "choices": [{"index": 0, "message": {"role": "assistant", "content": content}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": len(user) // 4, "completion_tokens": len(content) // 4}}
