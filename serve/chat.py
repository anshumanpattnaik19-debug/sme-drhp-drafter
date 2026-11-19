"""Project assistant: commands run directly; questions go to the agentic RAG layer (rag/agent.py).

    respond(pid, ctx, question, history, settings, review, drafts, actions) -> iterator of events
        {"type": "meta" | "step" | "delta" | "action" | "done", ...}

Commands: "draft <section>", "redraft all / remaining", "fill offer details from the documents".
"""
from __future__ import annotations

import re
import threading
import time

from draft.outline import SECTION_BY_KEY
from rag.agent import Agent, _chunks, match_section
from rag.guardrails import screen
from rag.index import ProjectIndex

_INDEX: dict[str, tuple] = {}
_LOCK = threading.Lock()


def project_index(pid, ctx):
    """One index per project, rebuilt when a file is added, removed or reprocessed."""
    sig = tuple(sorted((f["id"], f.get("processed_at", "")) for f in ctx.files if f.get("status") == "processed"))
    with _LOCK:
        got = _INDEX.get(pid)
        if got and got[0] == sig:
            return got[1]
    idx = ProjectIndex(ctx)
    with _LOCK:
        _INDEX[pid] = (sig, idx)
    return idx


def detect_action(q):
    ql = q.lower().strip()
    if re.search(r"\b(fill|auto-?fill|populate|complete)\b.{0,30}\boffer\b", ql):
        return {"kind": "autofill"}
    m = re.match(r"^(please\s+|can you\s+|could you\s+)?(re-?draft|draft|write|regenerate)\b(.*)$", ql)
    if m and not re.match(r"\s*(that|this|it|a statement|as if)\b", m.group(3)):   # "write that X is true" is no command
        rest = m.group(3)
        if re.match(r"\s*(?:the\s+)?(?:all|everything|whole|entire|remaining)\b", rest):
            return {"kind": "draft", "keys": None, "remaining": bool(re.search(r"remaining", rest))}
        key = match_section(rest)
        if key:
            return {"kind": "draft", "keys": [key]}
    return None


def _run_action(act, actions):
    yield {"type": "meta", "engine": "action", "sources": []}
    if act["kind"] == "autofill":
        filled = actions["autofill"]()
        text = (f"Filled {len(filled)} empty offer detail(s) from the documents:\n" +
                "\n".join(f"- {k.replace('_', ' ').capitalize()}: **{v}**" for k, v in filled.items())
                if filled else "There was nothing new to fill: every offer detail I can find in the documents is already set.")
        yield {"type": "action", "action": {"kind": "autofill", "label": "Open Offer details", "filled": filled}}
    else:
        try:
            job = actions["draft"](act["keys"], act.get("remaining", False))
        except Exception as e:  # noqa: BLE001
            yield {"type": "delta", "text": f"I couldn't start drafting: {getattr(e, 'detail', e)}"}
            yield {"type": "done"}
            return
        names = [SECTION_BY_KEY[k]["title"] for k in (act["keys"] or [])]
        text = (f"Drafting **{names[0]}** now. It opens with its tables, sources and checks when it's done."
                if names else f"Drafting {job.get('total', 'all')} section(s) now. Progress shows in the sidebar.")
        yield {"type": "action", "action": {"kind": "draft", "label": f"Open {names[0]}" if names else "Open Draft",
                                            "section": act["keys"][0] if act["keys"] else None, "job": job}}
    for c in _chunks(text):
        yield {"type": "delta", "text": c}
        time.sleep(0.01)
    yield {"type": "done"}


def respond(pid, ctx, question, history, settings, review, drafts, actions):
    # guardrails first: "fill in the offer price" or "write that all approvals are obtained" is not a command
    act = None if screen(question) else detect_action(question)
    if act:
        yield from _run_action(act, actions)
        return
    if re.match(r"^\s*(hi|hello|hey|help)\b|what can you do", question.lower()):
        yield {"type": "meta", "engine": "offline", "sources": []}
        text = (f"I can help with the **{ctx.company()}** DRHP. I search the issuer's files, the draft and the review pack, "
                "and cite what I find. Try:\n- *What's still missing from the issuer?*\n- *Summarise the Objects of the Offer*\n"
                "- *What are the main risk factors?*\n- *What is the revenue from operations for FY 2025-26?*\n"
                "- *Draft Our Business* or *Fill offer details from the documents*")
        for c in _chunks(text):
            yield {"type": "delta", "text": c}
            time.sleep(0.01)
        yield {"type": "done"}
        return
    agent = Agent(ctx, project_index(pid, ctx), review, drafts)
    yield from agent.run(question, history, settings)
