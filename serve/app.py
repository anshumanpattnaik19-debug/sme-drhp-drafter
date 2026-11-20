"""SME DRHP Drafter: local web service behind the UI.

    python -m uvicorn serve.app:app --port 8765          # from sme_drhp_drafter/; then open http://localhost:8765

The built UI (ui/dist) is served at "/", the API at "/api". With no model endpoint configured, SLM sections
are drafted by the offline mock writer and labelled as such; point Settings at the vLLM endpoint of the
fine-tuned model to draft with it.
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import threading
from pathlib import Path
import time
import traceback
from concurrent.futures import ThreadPoolExecutor

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from ingest import readers as _readers
from pydantic import BaseModel

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from assemble.docx_export import build_docx  # noqa: E402
from draft.outline import PARTS, SECTION_BY_KEY, SECTIONS, WRITERS  # noqa: E402
from draft.builders import offer_terms  # noqa: E402
from draft.writer import make_ctx, write_section  # noqa: E402
from extract.canonical import mark_superseded  # noqa: E402
from extract.rules import extract_facts  # noqa: E402
from ingest.classify import CATEGORIES, DOC_TYPES, classify, doc_type_options  # noqa: E402
from ingest.readers import FORMATS, file_format, ocr_available, read_file  # noqa: E402
from serve import chat as assistant  # noqa: E402
from serve import auth, idle, llm, store  # noqa: E402
from verify.checks import review_pack, verify_section  # noqa: E402

app = FastAPI(title="SME DRHP Drafter", version="0.1",
              description="First-draft DRHP generator for SME issues. Drafts for review by the BRLM and legal counsel only.")
# the last middleware added runs first: the password gate, then the use clock, so unsigned visitors are not use
app.middleware("http")(idle.touch)
app.middleware("http")(auth.gate)          # shared password on every page and route when APP_PASSWORD is set

EXEC = ThreadPoolExecutor(max_workers=2)
JOBS: dict[str, dict] = {}
JOBS_LOCK = threading.Lock()
idle.watch(lambda: any(j["status"] == "running" for j in list(JOBS.values())))   # auto-stop on a RunPod pod


def _boot_count():
    """How many times the app has started on this workspace. On a RunPod pod the workspace is a network volume, so the
    number keeps counting across pod stops and replacements; on a disk that is wiped it would start again at 1."""
    p = os.path.join(store.ROOT, ".boot_count")
    try:
        n = int(open(p).read().strip() or 0) + 1
    except (OSError, ValueError):
        n = 1
    try:
        open(p, "w").write(str(n))
    except OSError:
        pass
    return n


BOOT_COUNT = _boot_count()


def _guard_build():
    """A short hash of the guard's source (draft writer, checks, figure rules): shows which guard a deployed app runs."""
    import hashlib
    root = Path(__file__).resolve().parents[1]
    h = hashlib.sha256()
    for rel in ("draft/writer.py", "verify/checks.py", "data/facts.py"):
        try:
            h.update((root / rel).read_bytes().replace(b"\r\n", b"\n"))
        except OSError:
            h.update(rel.encode())
    return h.hexdigest()[:12]


GUARD_BUILD = _guard_build()


def _commit():
    """The git commit the running code comes from: BUILD_INFO.json in a deployed bundle (serve/pod.py), else git here.
    A trailing "+N" counts files that differed from the commit when the bundle was made."""
    root = Path(__file__).resolve().parents[1]
    try:
        info = json.loads((root / "BUILD_INFO.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        import subprocess
        try:
            run = lambda *a: subprocess.run(["git", *a], cwd=root, capture_output=True, text=True, timeout=5).stdout.strip()  # noqa: E731
            info = {"commit": run("rev-parse", "HEAD"), "dirty": len(run("status", "--porcelain").splitlines())}
        except (OSError, subprocess.SubprocessError):
            return "unknown"
    c = (info.get("commit") or "unknown")[:12]
    return c + (f"+{info['dirty']}" if info.get("dirty") else "")


COMMIT = _commit()


@app.get("/healthz")
def healthz():
    """Open to anyone, counts only: lets the launcher, the owner and the tests see that the app is up, that the
    auto-stop clock is running, and that the workspace survived (boot count, number of projects)."""
    return {"ok": True, "boot_count": BOOT_COUNT, "projects": len(store.list_projects()),
            "idle_seconds": round(idle.idle_for(busy=any(j["status"] == "running" for j in list(JOBS.values())))),
            "idle_limit_minutes": idle.minutes(), "guard_build": GUARD_BUILD, "rai": _rai_status(), "commit": COMMIT}


def _rai_status():
    """Policy version and mode of the Responsible AI layer the assistant runs (rai/), or "off" if it did not load."""
    from rag.agent import _rai
    r = _rai()
    return f"{r.config.get('version')}:{r.mode}" if r is not None else "off"
MAX_UPLOAD_MB = 200


# ---------- jobs ----------

def _job(pid, kind, total, label):
    job = {"id": store.new_id("j"), "project_id": pid, "kind": kind, "label": label, "status": "running",
           "done": 0, "total": total, "message": "Starting…", "started_at": time.time(), "finished_at": None,
           "errors": [], "cancel": False}
    with JOBS_LOCK:
        JOBS[job["id"]] = job
    return job


def _public(job):
    return {k: v for k, v in job.items() if k != "cancel"}


def _run(job, fn):
    def wrapper():
        try:
            fn(job)
            job["status"] = "cancelled" if job["cancel"] else ("done" if not job["errors"] else "done_with_errors")
        except Exception as e:  # noqa: BLE001
            traceback.print_exc()
            job["status"], job["message"] = "failed", str(e)
        job["finished_at"] = time.time()
    EXEC.submit(wrapper)
    return _public(job)


def _active_job(pid, kind):
    with JOBS_LOCK:
        return next((j for j in JOBS.values() if j["project_id"] == pid and j["kind"] == kind and j["status"] == "running"), None)


# ---------- helpers ----------

def _ocr_cfg(s):
    """Vision model for OCR, from Settings. None means RapidOCR (offline) only."""
    if s.get("ocr_backend") == "rapidocr" or not s.get("ocr_model_url"):
        return None
    return {"url": s["ocr_model_url"], "model": s.get("ocr_model_name") or "", "api_key": s.get("ocr_api_key") or ""}


def _project(pid):
    try:
        return store.get_project(pid)
    except KeyError:
        raise HTTPException(404, "project not found")


def _file(p, fid):
    f = next((f for f in p["files"] if f["id"] == fid), None)
    if f is None:
        raise HTTPException(404, "file not found")
    return f


def _summary(p):
    files = p["files"]
    facts = store.get_facts(p["id"])
    drafts = store.get_drafts(p["id"])
    return {**{k: v for k, v in p.items() if k != "files"},
            "stats": {"files": len(files), "processed": sum(f["status"] == "processed" for f in files),
                      "failed": sum(f["status"] == "failed" for f in files),
                      "pending": sum(f["status"] in ("queued", "processing") for f in files),
                      "facts": len(facts), "reviewed_facts": sum(bool(f.get("reviewed")) for f in facts),
                      "sections": len(SECTIONS), "drafted": len(drafts),
                      "pages": sum(f.get("pages") or 0 for f in files)}}


# ---------- meta & settings ----------

@app.get("/api/health")
def health():
    s = store.get_settings()
    model = llm.status(s) if s["use_model"] else {"reachable": None}    # wakes no serverless worker
    return {"status": "ok", "ocr_available": ocr_available(), "ocr_error": _readers._ocr_error, "use_model": s["use_model"], "model": model,
            "model_name": s["model_name"], "model_url": s["model_url"]}


@app.get("/api/meta")
def meta():
    return {"doc_types": doc_type_options(), "categories": CATEGORIES, "parts": PARTS, "writers": WRITERS,
            "sections": SECTIONS, "formats": sorted(FORMATS)}


class SettingsPatch(BaseModel):
    use_model: bool | None = None
    model_url: str | None = None
    model_name: str | None = None
    api_key: str | None = None
    temperature: float | None = None
    max_tokens: int | None = None
    ocr_enabled: bool | None = None
    ocr_page_limit: int | None = None
    ocr_backend: str | None = None
    ocr_model_url: str | None = None
    ocr_model_name: str | None = None
    ocr_api_key: str | None = None


def _public_settings(s):
    return {**s, "api_key": "", "api_key_set": bool(s.get("api_key"))}


@app.get("/api/settings")
def get_settings():
    return _public_settings(store.get_settings())


@app.put("/api/settings")
def put_settings(patch: SettingsPatch):
    data = {k: v for k, v in patch.model_dump().items() if v is not None}
    if data.get("api_key") == "":
        data.pop("api_key")
    return _public_settings(store.save_settings(data))


@app.post("/api/settings/test")
def test_model(patch: SettingsPatch):
    s = {**store.get_settings(), **{k: v for k, v in patch.model_dump().items() if v not in (None, "")}}
    return llm.check({**s, **store.pinned()}, timeout=6.0)   # a pinned key is never sent to another address


# ---------- projects ----------

class ProjectIn(BaseModel):
    name: str
    board: str = "bse_sme"
    offer: dict | None = None


class ProjectPatch(BaseModel):
    name: str | None = None
    offer: dict | None = None


@app.get("/api/projects")
def projects():
    return [_summary(p) for p in store.list_projects()]


@app.post("/api/projects")
def create_project(body: ProjectIn):
    if not body.name.strip():
        raise HTTPException(422, "name is required")
    return _summary(store.create_project(body.name.strip(), body.board, body.offer))


@app.get("/api/projects/{pid}")
def get_project(pid: str):
    p = _project(pid)
    return {**_summary(p), "files": p["files"]}


@app.patch("/api/projects/{pid}")
def patch_project(pid: str, body: ProjectPatch):
    p = _project(pid)
    if body.name is not None and body.name.strip():
        p["name"] = body.name.strip()
    if body.offer is not None:
        p["offer"] = {**(p.get("offer") or {}), **body.offer}
    store.save_project(p)
    return {**_summary(p), "files": p["files"]}


@app.delete("/api/projects/{pid}")
def delete_project(pid: str):
    _project(pid)
    store.delete_project(pid)
    return {"ok": True}


# ---------- files ----------

@app.post("/api/projects/{pid}/files")
async def upload(pid: str, files: list[UploadFile] = File(...), paths: list[str] = Form(default=[])):
    p = _project(pid)
    added, rejected = [], []
    for i, uf in enumerate(files):
        rel = paths[i] if i < len(paths) and paths[i] else uf.filename or "file"
        name = store.safe_name(rel)
        if file_format(name) is None:
            rejected.append({"name": name, "reason": "unsupported type"})
            continue
        fid = store.new_id("f")
        stored = f"{fid}__{name}"
        dest = os.path.join(store.pdir(pid), "files", stored)
        size = 0
        with open(dest, "wb") as out:
            while chunk := await uf.read(1 << 20):
                size += len(chunk)
                if size > MAX_UPLOAD_MB << 20:
                    break
                out.write(chunk)
        if size > MAX_UPLOAD_MB << 20:
            os.remove(dest)
            rejected.append({"name": name, "reason": f"larger than {MAX_UPLOAD_MB} MB"})
            continue
        folder = os.path.dirname(rel.replace("\\", "/")).split("/")[-1] if "/" in rel.replace("\\", "/") else ""
        guess = classify(name)
        added.append({"id": fid, "name": name, "stored": stored, "folder": folder, "size": size,
                      "ext": os.path.splitext(name)[1].lower().lstrip("."), "format": file_format(name),
                      "status": "queued", "uploaded_at": store.now(), "doc_type": guess["doc_type"],
                      "doc_label": guess["label"], "category": guess["category"], "confidence": guess["confidence"],
                      "doc_type_locked": False})
    with store.LOCK:
        p = store.get_project(pid)
        p["files"].extend(added)
        store.save_project(p)
    return {"added": added, "rejected": rejected}


@app.get("/api/projects/{pid}/files/{fid}")
def file_detail(pid: str, fid: str):
    p = _project(pid)
    f = _file(p, fid)
    blocks = store.get_blocks(pid, fid)
    facts = [x for x in store.get_facts(pid) if x.get("file_id") == fid]
    return {**f, "blocks": (blocks or {}).get("blocks", []), "facts": facts}


@app.get("/api/projects/{pid}/files/{fid}/raw")
def file_raw(pid: str, fid: str):
    p = _project(pid)
    f = _file(p, fid)
    path = store.file_path(pid, f)
    if not os.path.isfile(path):
        raise HTTPException(404, "file missing on disk")
    return FileResponse(path, filename=f["name"], content_disposition_type="inline")


class FilePatch(BaseModel):
    doc_type: str | None = None


@app.patch("/api/projects/{pid}/files/{fid}")
def patch_file(pid: str, fid: str, body: FilePatch):
    p = _project(pid)
    _file(p, fid)
    if body.doc_type:
        if body.doc_type not in DOC_TYPES:
            raise HTTPException(422, "unknown doc_type")
        label, cat, _a, _b = DOC_TYPES[body.doc_type]
        f = store.update_file(pid, fid, doc_type=body.doc_type, doc_label=label, category=cat, confidence=1.0,
                              doc_type_locked=True)
        with store.LOCK:
            facts = store.get_facts(pid)
            for x in facts:
                if x.get("file_id") == fid:
                    x["doc_type"], x["doc_label"] = body.doc_type, label
            store.save_facts(pid, facts)
        return f
    return _file(p, fid)


@app.delete("/api/projects/{pid}/files/{fid}")
def delete_file(pid: str, fid: str):
    with store.LOCK:
        p = _project(pid)
        f = _file(p, fid)
        try:
            os.remove(store.file_path(pid, f))
        except OSError:
            pass
        p["files"] = [x for x in p["files"] if x["id"] != fid]
        store.save_project(p)
        store.save_facts(pid, [x for x in store.get_facts(pid) if x.get("file_id") != fid])
    return {"ok": True}


@app.post("/api/projects/{pid}/files/clear-queue")
def clear_queue(pid: str):
    """Reset an upload: remove the files that were never read (queued) or could not be read (failed), with their stored
    copies. Files already read stay. Refused while a processing run is going; cancel it first."""
    if _active_job(pid, "process"):
        raise HTTPException(409, "cancel the processing run first")
    with store.LOCK:
        p = _project(pid)
        gone = [f for f in p["files"] if f.get("status") in ("queued", "failed", "processing")]
        for f in gone:
            try:
                os.remove(store.file_path(pid, f))
            except OSError:
                pass
        ids = {f["id"] for f in gone}
        p["files"] = [x for x in p["files"] if x["id"] not in ids]
        store.save_project(p)
        store.save_facts(pid, [x for x in store.get_facts(pid) if x.get("file_id") not in ids])
    return {"removed": len(gone)}


class ProcessIn(BaseModel):
    file_ids: list[str] | None = None
    force: bool = False


@app.post("/api/projects/{pid}/process")
def process(pid: str, body: ProcessIn):
    p = _project(pid)
    if _active_job(pid, "process"):
        raise HTTPException(409, "files are already being processed")
    if body.file_ids:
        todo = [f for f in p["files"] if f["id"] in body.file_ids]
    else:
        todo = [f for f in p["files"] if body.force or f["status"] in ("queued", "failed")]
    if not todo:
        raise HTTPException(422, "nothing to process")
    for f in todo:
        store.update_file(pid, f["id"], status="queued", error=None)
    settings = store.get_settings()
    job = _job(pid, "process", len(todo), f"Processing {len(todo)} file(s)")

    def work(job):
        _readers.set_llm_ocr(_ocr_cfg(settings))
        for f in todo:
            if job["cancel"]:
                store.update_file(pid, f["id"], status="queued")
                continue
            job["message"] = f["name"]
            store.update_file(pid, f["id"], status="processing", started_at=store.now())
            try:
                def prog(msg, name=f["name"]):
                    job["message"] = f"{name} · {msg}"
                res = read_file(store.file_path(pid, f), ocr=settings["ocr_enabled"],
                                ocr_limit=settings["ocr_page_limit"], progress=prog)
                store.save_blocks(pid, f["id"], res)
                text = "\n".join(b["text"] for b in res["blocks"][:30])
                cur = store.get_project(pid)
                cur_f = next((x for x in cur["files"] if x["id"] == f["id"]), f)
                cls = None if cur_f.get("doc_type_locked") else classify(f["name"], text)
                doc_type = cur_f["doc_type"] if cls is None else cls["doc_type"]
                doc_label = DOC_TYPES[doc_type][0]
                # the document index lists files, not issuer facts; keep it out of the fact store
                facts = [] if doc_type == "document_index" else extract_facts(res["blocks"])
                for n, x in enumerate(facts):
                    x.update({"id": f"{f['id']}-{n}", "file_id": f["id"], "file_name": f["name"], "doc_type": doc_type,
                              "doc_label": doc_label, "origin": "rules", "reviewed": False})
                store.replace_file_facts(pid, f["id"], facts)
                patch = {"status": "processed", "format": res["format"], "pages": res["pages"], "blocks": len(res["blocks"]),
                         "chars": res["chars"], "ocr_pages": len(res["ocr_pages"]), "warnings": res["warnings"],
                         "needs_ocr_pages": sum(b["kind"] == "needs_ocr" for b in res["blocks"]),
                         "facts": len(facts), "processed_at": store.now()}
                if cls:
                    patch.update(doc_type=doc_type, doc_label=doc_label, category=cls["category"],
                                 confidence=cls["confidence"])
                store.update_file(pid, f["id"], **patch)
            except Exception as e:  # noqa: BLE001
                traceback.print_exc()
                job["errors"].append({"file": f["name"], "error": str(e)})
                store.update_file(pid, f["id"], status="failed", error=str(e)[:300])
            job["done"] += 1
        job["message"] = "Checking facts and offer details…"
        with store.LOCK:
            store.save_facts(pid, mark_superseded(store.get_facts(pid)))
        filled = _autofill(pid)
        job["message"] = f"Finished · {len(filled)} offer detail(s) filled from the documents" if filled else "Finished"

    return _run(job, work)


def _ctx(pid):
    p = store.get_project(pid)
    return make_ctx(p, store.get_facts(pid), p["files"], lambda fid: store.get_blocks(pid, fid))


def _autofill(pid, overwrite=False):
    """Fill empty Offer details from the issuer's files; remember where each value came from."""
    terms = offer_terms(_ctx(pid))
    with store.LOCK:
        p = store.get_project(pid)
        offer, sources, filled = p.get("offer") or {}, p.get("offer_sources") or {}, {}
        for k, v in terms.items():
            if overwrite or not str(offer.get(k) or "").strip():
                offer[k] = v["value"]
                sources[k] = v["source"]
                filled[k] = v["value"]
        p["offer"], p["offer_sources"] = offer, sources
        store.save_project(p)
    return filled


class AutofillIn(BaseModel):
    overwrite: bool = False


@app.post("/api/projects/{pid}/offer/autofill")
def autofill(pid: str, body: AutofillIn):
    _project(pid)
    filled = _autofill(pid, body.overwrite)
    p = store.get_project(pid)
    return {"filled": filled, "offer": p["offer"], "offer_sources": p.get("offer_sources", {})}


# ---------- facts ----------

class FactIn(BaseModel):
    type: str = "short_text"
    label: str
    value: str
    unit: str = ""
    period: str = ""
    file_id: str | None = None
    note: str = ""


class FactPatch(BaseModel):
    type: str | None = None
    label: str | None = None
    value: str | None = None
    unit: str | None = None
    period: str | None = None
    reviewed: bool | None = None
    note: str | None = None


@app.get("/api/projects/{pid}/facts")
def facts(pid: str):
    _project(pid)
    used = {}
    for key, d in store.get_drafts(pid).items():
        for b in d.get("blocks", []):
            for fid in b.get("facts", []):
                used.setdefault(fid, []).append(key)
    return [{**f, "used_in": sorted(set(used.get(f["id"], [])))} for f in store.get_facts(pid)]


@app.post("/api/projects/{pid}/facts")
def add_fact(pid: str, body: FactIn):
    p = _project(pid)
    src = next((f for f in p["files"] if f["id"] == body.file_id), None)
    fact = {**body.model_dump(), "id": store.new_id("u"), "origin": "user", "reviewed": True, "loc": "entered by user",
            "page": None, "snippet": body.note, "file_id": src["id"] if src else None,
            "file_name": src["name"] if src else "Entered by user", "doc_type": src["doc_type"] if src else None,
            "doc_label": src["doc_label"] if src else "User input"}
    with store.LOCK:
        store.save_facts(pid, store.get_facts(pid) + [fact])
    return fact


@app.patch("/api/projects/{pid}/facts/{fact_id}")
def patch_fact(pid: str, fact_id: str, body: FactPatch):
    _project(pid)
    with store.LOCK:
        facts = store.get_facts(pid)
        f = next((x for x in facts if x["id"] == fact_id), None)
        if f is None:
            raise HTTPException(404, "fact not found")
        upd = {k: v for k, v in body.model_dump().items() if v is not None}
        if any(k in upd for k in ("value", "label", "type", "unit", "period")):
            f["edited"] = True
        f.update(upd)
        store.save_facts(pid, facts)
    return f


@app.delete("/api/projects/{pid}/facts/{fact_id}")
def delete_fact(pid: str, fact_id: str):
    _project(pid)
    with store.LOCK:
        store.save_facts(pid, [x for x in store.get_facts(pid) if x["id"] != fact_id])
    return {"ok": True}


# ---------- drafting ----------

@app.get("/api/projects/{pid}/sections")
def sections(pid: str):
    _project(pid)
    drafts = store.get_drafts(pid)
    out = []
    for s in SECTIONS:
        d = drafts.get(s["key"])
        v = (d or {}).get("verification") or {}
        out.append({**s, "status": "drafted" if d else "not_started", "engine": (d or {}).get("engine"),
                    "updated_at": (d or {}).get("updated_at"), "edited": (d or {}).get("edited", False),
                    "version": (d or {}).get("version"), "versions": len(store.get_versions(pid, s["key"])) if d else 0,
                    "placeholders": v.get("placeholders"), "ungrounded": len(v.get("ungrounded", [])) if d else None,
                    "checklist_coverage": v.get("checklist_coverage"), "grounding": v.get("grounding"),
                    "weak": len(v.get("weak", [])) if d else None, "narrative_pending": v.get("narrative_pending"),
                    "review": (d or {}).get("review") or {"status": "unreviewed"}})
    return out


@app.get("/api/projects/{pid}/sections/{key}")
def section(pid: str, key: str):
    _project(pid)
    if key not in SECTION_BY_KEY:
        raise HTTPException(404, "unknown section")
    return {"section": SECTION_BY_KEY[key], "draft": store.get_drafts(pid).get(key), "versions": _version_list(pid, key)}


def _version_list(pid, key):
    out = []
    for v in store.get_versions(pid, key):
        d = v["draft"]
        ver = d.get("verification") or {}
        out.append({"n": v["n"], "created_at": v.get("created_at"), "engine": d.get("engine"), "edited": d.get("edited", False),
                    "model_name": d.get("model_name"), "words": sum(len((b.get("text") or "").split()) for b in d.get("blocks", [])),
                    "placeholders": ver.get("placeholders"), "ungrounded": len(ver.get("ungrounded", [])),
                    "review": (d.get("review") or {}).get("status", "unreviewed"),
                    "selected": v["n"] == (store.get_drafts(pid).get(key) or {}).get("version")})
    return out


class VersionIn(BaseModel):
    version: int


@app.post("/api/projects/{pid}/sections/{key}/select")
def select_draft_version(pid: str, key: str, body: VersionIn):
    _project(pid)
    d = store.select_version(pid, key, body.version)
    if d is None:
        raise HTTPException(404, "no such draft version")
    return {"section": SECTION_BY_KEY[key], "draft": d, "versions": _version_list(pid, key)}


@app.delete("/api/projects/{pid}/sections/{key}/versions/{n}")
def delete_draft_version(pid: str, key: str, n: int):
    _project(pid)
    if not store.delete_version(pid, key, n):
        raise HTTPException(422, "cannot delete the only draft, or it does not exist")
    return {"section": SECTION_BY_KEY[key], "draft": store.get_drafts(pid).get(key), "versions": _version_list(pid, key)}


class DraftIn(BaseModel):
    keys: list[str] | None = None
    skip_drafted: bool = False


def _draft_one(pid, key, settings, ctx):
    chat = llm.make_chat(settings) if settings["use_model"] else None
    d = write_section(key, ctx, chat)
    d["verification"] = verify_section(key, d, ctx.facts, ctx.offer)
    d["review"] = {"status": "unreviewed"}
    d["updated_at"] = store.now()
    d["edited"] = False
    d["model_name"] = settings["model_name"] if d["engine"] == "model" else None
    store.save_draft(pid, key, d, new_version=True)      # a redraft is Draft N+1; the earlier drafts stay
    return d


@app.post("/api/projects/{pid}/draft")
def draft(pid: str, body: DraftIn):
    _project(pid)
    if _active_job(pid, "draft"):
        raise HTTPException(409, "a drafting job is already running")
    keys = body.keys or [s["key"] for s in SECTIONS]
    bad = [k for k in keys if k not in SECTION_BY_KEY]
    if bad:
        raise HTTPException(422, f"unknown sections: {bad}")
    if body.skip_drafted:
        have = store.get_drafts(pid)
        keys = [k for k in keys if k not in have]
    if not keys:
        raise HTTPException(422, "all sections already drafted")
    settings = store.get_settings()
    job = _job(pid, "draft", len(keys), f"Drafting {len(keys)} section(s)")
    job["keys"] = keys

    def work(job):
        job["message"] = "Reading the issuer's schedules…"
        ctx = _ctx(pid)
        for k in keys:
            if job["cancel"]:
                break
            job["message"] = SECTION_BY_KEY[k]["title"]
            job["current"] = k
            try:
                _draft_one(pid, k, settings, ctx)
            except Exception as e:  # noqa: BLE001
                traceback.print_exc()
                job["errors"].append({"section": k, "error": str(e)[:300]})
            job["done"] += 1
        job["current"] = None
        job["message"] = "Finished"

    return _run(job, work)


class BlocksIn(BaseModel):
    blocks: list[dict]


@app.put("/api/projects/{pid}/sections/{key}")
def edit_section(pid: str, key: str, body: BlocksIn):
    p = _project(pid)
    if key not in SECTION_BY_KEY:
        raise HTTPException(404, "unknown section")
    d = store.get_drafts(pid).get(key) or {"writer": SECTION_BY_KEY[key]["writer"], "engine": "user", "routed": []}
    d["blocks"] = body.blocks
    d["edited"] = True
    d["updated_at"] = store.now()
    d["narrative_pending"] = [b.get("sub") for b in body.blocks if b.get("type") == "brief"]
    d["verification"] = verify_section(key, d, store.get_facts(pid), p.get("offer"))
    d["review"] = {"status": "unreviewed"}           # an edit needs a fresh sign-off
    store.save_draft(pid, key, d)
    return d


class SignoffIn(BaseModel):
    reviewed: bool = True
    reviewer: str = ""
    note: str = ""


@app.post("/api/projects/{pid}/sections/{key}/signoff")
def signoff(pid: str, key: str, body: SignoffIn):
    _project(pid)
    d = store.get_drafts(pid).get(key)
    if not d:
        raise HTTPException(422, "draft the section before signing it off")
    d["review"] = ({"status": "reviewed", "by": body.reviewer.strip() or "Reviewer", "at": store.now(), "note": body.note}
                   if body.reviewed else {"status": "unreviewed"})
    store.save_draft(pid, key, d)
    return d


@app.delete("/api/projects/{pid}/sections/{key}")
def clear_section(pid: str, key: str):
    _project(pid)
    store.save_draft(pid, key, None)
    return {"ok": True}


# ---------- jobs ----------

@app.get("/api/jobs/{job_id}")
def job(job_id: str):
    j = JOBS.get(job_id)
    if not j:
        raise HTTPException(404, "job not found")
    return _public(j)


@app.get("/api/projects/{pid}/jobs")
def project_jobs(pid: str):
    with JOBS_LOCK:
        js = [j for j in JOBS.values() if j["project_id"] == pid]
    js.sort(key=lambda j: j["started_at"], reverse=True)
    return [_public(j) for j in js[:10]]


@app.post("/api/jobs/{job_id}/cancel")
def cancel(job_id: str):
    j = JOBS.get(job_id)
    if not j:
        raise HTTPException(404, "job not found")
    j["cancel"] = True
    j["message"] = ("Cancelling: stops after the file being read" if j.get("kind") == "process"
                    else "Cancelling: stops after the section being drafted")
    return _public(j)


# ---------- assistant (agentic RAG chat) ----------

class ChatIn(BaseModel):
    message: str


@app.get("/api/projects/{pid}/chat")
def chat_history(pid: str):
    _project(pid)
    return {"messages": store.get_chat(pid)}


@app.delete("/api/projects/{pid}/chat")
def chat_clear(pid: str):
    _project(pid)
    store.save_chat(pid, [])
    return {"ok": True}


@app.post("/api/projects/{pid}/chat")
def chat(pid: str, body: ChatIn):
    p = _project(pid)
    q = body.message.strip()
    if not q:
        raise HTTPException(422, "message is empty")
    settings = store.get_settings()
    ctx = _ctx(pid)
    drafts = store.get_drafts(pid)
    review_ = review_pack(p, p["files"], ctx.facts, drafts)
    history = store.get_chat(pid)
    user = {"id": store.new_id("m"), "role": "user", "content": q, "created_at": store.now()}
    store.save_chat(pid, history + [user])
    actions = {
        "draft": lambda keys, remaining: draft(pid, DraftIn(keys=keys, skip_drafted=remaining)),
        "autofill": lambda: _autofill(pid),
    }

    def gen():
        msg = {"id": store.new_id("m"), "role": "assistant", "content": "", "sources": [], "steps": [], "actions": [],
               "engine": None, "created_at": store.now()}
        yield json.dumps({"type": "start", "id": msg["id"], "user_id": user["id"]}) + "\n"
        try:
            for ev in assistant.respond(pid, ctx, q, [{"role": m["role"], "content": m["content"]} for m in history],
                                        settings, review_, drafts, actions):
                if ev["type"] == "delta":
                    msg["content"] += ev["text"]
                elif ev["type"] == "meta":
                    msg["engine"], msg["sources"] = ev.get("engine"), ev.get("sources", [])
                    msg["retrieval"], msg["model"] = ev.get("retrieval"), ev.get("model")
                elif ev["type"] == "step":
                    msg["steps"].append({k: ev[k] for k in ("id", "label", "detail", "status")})
                elif ev["type"] == "action":
                    msg["actions"].append(ev["action"])
                yield json.dumps(ev, ensure_ascii=False, default=str) + "\n"
        except Exception as e:  # noqa: BLE001
            traceback.print_exc()
            msg["content"] += f"\n\n_Something went wrong: {e}_"
            yield json.dumps({"type": "delta", "text": f"\n\n_Something went wrong: {e}_"}) + "\n"
            yield json.dumps({"type": "done"}) + "\n"
        store.save_chat(pid, store.get_chat(pid) + [msg])

    return StreamingResponse(gen(), media_type="application/x-ndjson")


# ---------- review & export ----------

@app.get("/api/projects/{pid}/review")
def review(pid: str):
    p = _project(pid)
    return review_pack(p, p["files"], store.get_facts(pid), store.get_drafts(pid))


@app.get("/api/projects/{pid}/export.docx")
def export(pid: str, include_review: bool = True, include_sources: bool = True):
    p = _project(pid)
    facts = store.get_facts(pid)
    drafts = store.get_drafts(pid)
    if not drafts:
        raise HTTPException(422, "draft at least one section before exporting")
    rv = review_pack(p, p["files"], facts, drafts)
    name = "".join(c for c in (p.get("offer") or {}).get("company_name", p["name"]) if c.isalnum() or c in " _-").strip().replace(" ", "_")
    path = os.path.join(tempfile.gettempdir(), f"drhp_{pid}_{int(time.time())}.docx")
    build_docx(p, drafts, facts, rv, path, include_review=include_review, include_sources=include_sources)
    return FileResponse(path, filename=f"{name or 'DRHP'}_DRHP_draft.docx",
                        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document")


# ---------- UI ----------

DIST = os.environ.get("DRHP_UI_DIST") or os.path.join(ROOT, "ui", "dist")


@app.exception_handler(404)
async def spa_fallback(request, exc):
    if not request.url.path.startswith("/api") and os.path.isfile(os.path.join(DIST, "index.html")):
        return FileResponse(os.path.join(DIST, "index.html"))
    return JSONResponse({"detail": getattr(exc, "detail", "Not found")}, status_code=404)


if os.path.isdir(DIST):
    app.mount("/", StaticFiles(directory=DIST, html=True), name="ui")
