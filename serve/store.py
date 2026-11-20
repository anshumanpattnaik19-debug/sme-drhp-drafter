"""Workspace on disk, one folder per DRHP project:

    workspace/settings.json
    workspace/<pid>/project.json   name, board, offer details, file list with status
    workspace/<pid>/files/<fid>__<name>
    workspace/<pid>/blocks/<fid>.json
    workspace/<pid>/facts.json
    workspace/<pid>/drafts.json

JSON files are written atomically under one process-wide lock; enough for a single-user local service.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import re
import shutil
import threading
import time
import uuid

ROOT = os.environ.get("DRHP_WORKSPACE", os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "workspace"))
LOCK = threading.RLock()

DEFAULT_SETTINGS = {
    "use_model": False,
    "model_url": "http://localhost:8000/v1",
    "model_name": "sme-drhp-7b",
    "api_key": "",
    "temperature": 0.2,
    "max_tokens": 3000,
    "ocr_enabled": True,
    "ocr_page_limit": 40,
    # "auto": a vision model when ocr_model_url is set, otherwise RapidOCR; "llm": vision model only; "rapidocr": offline
    "ocr_backend": "auto",
    "ocr_model_url": "",
    "ocr_model_name": "qwen2.5-vl-7b-instruct",
    "ocr_api_key": "",
}


def now():
    return dt.datetime.now().isoformat(timespec="seconds")


def new_id(prefix=""):
    return prefix + uuid.uuid4().hex[:10]


def _read(path, default):
    # under the lock: on Windows an open reader makes a concurrent os.replace fail with "Access is denied"
    with LOCK:
        if not os.path.isfile(path):
            return default
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)


def _write(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with LOCK:
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(data, fh, ensure_ascii=False, indent=1)
        for attempt in range(6):          # antivirus or the indexer can hold the file briefly
            try:
                os.replace(tmp, path)
                return
            except PermissionError:
                if attempt == 5:
                    raise
                time.sleep(0.05 * (attempt + 1))


def pdir(pid):
    if not re.fullmatch(r"[a-z0-9]{6,20}", pid or ""):
        raise KeyError(pid)
    return os.path.join(ROOT, pid)


# ---------- settings ----------

def pinned():
    """Model settings fixed by the host's environment (the Hugging Face Space, docs/HOSTING.md): DRHP_MODEL_URL, with
    DRHP_MODEL_NAME and the key in DRHP_MODEL_API_KEY or RUNPOD_API_KEY. A user cannot change them in Settings, so
    the key can never be sent to another address."""
    url = os.environ.get("DRHP_MODEL_URL", "").strip()
    if not url:
        return {}
    return {"use_model": True, "model_url": url, "model_name": os.environ.get("DRHP_MODEL_NAME", "sme-drhp-7b"),
            "api_key": os.environ.get("DRHP_MODEL_API_KEY") or os.environ.get("RUNPOD_API_KEY", "")}


def get_settings():
    with LOCK:
        return {**DEFAULT_SETTINGS, **_read(os.path.join(ROOT, "settings.json"), {}), **pinned()}


def save_settings(patch):
    with LOCK:
        s = get_settings()
        pin = pinned()
        s.update({k: v for k, v in patch.items() if k in DEFAULT_SETTINGS and k not in pin})
        _write(os.path.join(ROOT, "settings.json"), {k: v for k, v in s.items() if k not in pin})   # no key on disk
        return s


# ---------- projects ----------

def list_projects():
    out = []
    if not os.path.isdir(ROOT):
        return out
    for pid in os.listdir(ROOT):
        p = os.path.join(ROOT, pid, "project.json")
        if os.path.isfile(p):
            out.append(_read(p, {}))
    out.sort(key=lambda p: p.get("updated_at", ""), reverse=True)
    return out


def get_project(pid):
    p = _read(os.path.join(pdir(pid), "project.json"), None)
    if p is None:
        raise KeyError(pid)
    return p


def save_project(p):
    with LOCK:
        p["updated_at"] = now()
        _write(os.path.join(pdir(p["id"]), "project.json"), p)
        return p


def create_project(name, board="bse_sme", offer=None):
    pid = new_id()
    p = {"id": pid, "name": name, "created_at": now(), "updated_at": now(), "files": [],
         "offer": {"company_name": name, "board": board, **(offer or {})}}
    os.makedirs(os.path.join(pdir(pid), "files"), exist_ok=True)
    return save_project(p)


def delete_project(pid):
    with LOCK:
        shutil.rmtree(pdir(pid), ignore_errors=True)


def update_file(pid, fid, **patch):
    with LOCK:
        p = get_project(pid)
        for f in p["files"]:
            if f["id"] == fid:
                f.update(patch)
                save_project(p)
                return f
        raise KeyError(fid)


def file_path(pid, f):
    return os.path.join(pdir(pid), "files", f["stored"])


def safe_name(name):
    base = os.path.basename(name.replace("\\", "/"))
    return re.sub(r"[^\w.\- ()&]", "_", base)[:140] or "file"


# ---------- blocks, facts, drafts ----------

def get_blocks(pid, fid):
    return _read(os.path.join(pdir(pid), "blocks", f"{fid}.json"), None)


def save_blocks(pid, fid, data):
    _write(os.path.join(pdir(pid), "blocks", f"{fid}.json"), data)


def get_facts(pid):
    return _read(os.path.join(pdir(pid), "facts.json"), [])


def save_facts(pid, facts):
    with LOCK:
        _write(os.path.join(pdir(pid), "facts.json"), facts)


def replace_file_facts(pid, fid, new_facts):
    """Drop machine facts of a file (keeping user edits and reviewed ones), then add new_facts."""
    with LOCK:
        facts = get_facts(pid)
        kept = [f for f in facts if f.get("file_id") != fid or f.get("origin") == "user" or f.get("reviewed")]
        save_facts(pid, kept + new_facts)


def get_chat(pid):
    return _read(os.path.join(pdir(pid), "chat.json"), [])


def save_chat(pid, messages):
    with LOCK:
        _write(os.path.join(pdir(pid), "chat.json"), messages[-200:])


def get_drafts(pid):
    return _read(os.path.join(pdir(pid), "drafts.json"), {})


MAX_VERSIONS = 3         # the last three drafts of a section are kept; the oldest goes when a fourth is saved


def _versions_path(pid):
    return os.path.join(pdir(pid), "draft_versions.json")


def get_versions(pid, key):
    """The saved drafts of a section, oldest first: [{"n", "created_at", "draft"}]. A draft saved before versions existed
    is Draft 1."""
    vs = _read(_versions_path(pid), {}).get(key)
    if vs is None:
        cur = get_drafts(pid).get(key)
        return [{"n": cur.get("version", 1), "created_at": cur.get("updated_at"), "draft": cur}] if cur else []
    return vs


def save_draft(pid, key, draft, new_version=False):
    """Save a section's draft. new_version=True (a fresh draft from the writer) adds Draft N+1 and selects it; otherwise
    the selected version is updated in place (an edit, a sign-off). draft None clears the section and all its versions."""
    with LOCK:
        d = get_drafts(pid)
        allv = _read(_versions_path(pid), {})
        if draft is None:
            d.pop(key, None)
            allv.pop(key, None)
        else:
            vs = allv.get(key) or get_versions(pid, key)
            if new_version or not vs:
                n = max([v["n"] for v in vs] + [0]) + 1
                draft["version"] = n
                vs.append({"n": n, "created_at": draft.get("updated_at"), "draft": draft})
                while len(vs) > MAX_VERSIONS:
                    drop = next(v for v in vs if v["n"] != n)
                    vs.remove(drop)
            else:
                n = draft.get("version") or (d.get(key) or {}).get("version") or 1
                draft["version"] = n
                for v in vs:
                    if v["n"] == n:
                        v["draft"] = draft
                        break
                else:
                    vs.append({"n": n, "created_at": draft.get("updated_at"), "draft": draft})
            allv[key] = vs
            d[key] = draft
        _write(os.path.join(pdir(pid), "drafts.json"), d)
        _write(_versions_path(pid), allv)
        p = get_project(pid)
        save_project(p)


def select_version(pid, key, n):
    """Make Draft n the section's current draft (what the review, the export and the assistant use)."""
    with LOCK:
        vs = get_versions(pid, key)
        pick = next((v for v in vs if v["n"] == n), None)
        if not pick:
            return None
        d = get_drafts(pid)
        d[key] = pick["draft"]
        _write(os.path.join(pdir(pid), "drafts.json"), d)
        allv = _read(_versions_path(pid), {})
        allv[key] = vs
        _write(_versions_path(pid), allv)
        save_project(get_project(pid))
        return pick["draft"]


def delete_version(pid, key, n):
    """Remove Draft n unless it is the only one; if it was selected, the newest remaining draft is selected."""
    with LOCK:
        vs = get_versions(pid, key)
        if len(vs) <= 1 or not any(v["n"] == n for v in vs):
            return False
        vs = [v for v in vs if v["n"] != n]
        allv = _read(_versions_path(pid), {})
        allv[key] = vs
        _write(_versions_path(pid), allv)
        d = get_drafts(pid)
        if (d.get(key) or {}).get("version") == n:
            d[key] = vs[-1]["draft"]
            _write(os.path.join(pdir(pid), "drafts.json"), d)
        save_project(get_project(pid))
        return True
