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
    "ocr_page_limit": 12,
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

def get_settings():
    with LOCK:
        return {**DEFAULT_SETTINGS, **_read(os.path.join(ROOT, "settings.json"), {})}


def save_settings(patch):
    with LOCK:
        s = get_settings()
        s.update({k: v for k, v in patch.items() if k in DEFAULT_SETTINGS})
        _write(os.path.join(ROOT, "settings.json"), s)
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


def save_draft(pid, key, draft):
    with LOCK:
        d = get_drafts(pid)
        if draft is None:
            d.pop(key, None)
        else:
            d[key] = draft
        _write(os.path.join(pdir(pid), "drafts.json"), d)
        p = get_project(pid)
        save_project(p)
