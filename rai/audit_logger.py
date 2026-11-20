"""Accountability: an append-only, hash-chained audit log of model interactions, training runs, model and dataset versions,
safety evaluations and incidents, with a human-escalation queue.

    log = AuditLogger("workspace/audit/rai_audit.jsonl", "workspace/audit/incidents.jsonl")
    log.interaction(tenant="7c0c669d53", model="sme-drhp-7b@A_qa3_dpo3", kind="qa", input_text=q, output_text=a,
                    decision="allow", flags=["unsupported_claim"])
    log.incident("high", "data_exfiltration", "asked for another issuer's files", tenant="7c0c669d53")
    ok, bad = log.verify_chain()       # False and the first broken record if a line was edited or removed

Each record carries the hash of the previous one, so editing or deleting a line breaks the chain from that point. This shows
tampering; it does not prevent it (the file is still writable by whoever runs the app). Raw prompts and answers are never stored:
only their SHA-256 and, if the policy allows, a short preview with personal identifiers redacted.
"""
from __future__ import annotations

import hashlib
import json
import os
import threading
import time
import uuid

GENESIS = "0" * 64
SEVERITIES = ("low", "medium", "high", "critical")


def sha256_text(text):
    return hashlib.sha256((text or "").encode("utf-8")).hexdigest()


def file_sha256(path, chunk=1 << 20):
    """SHA-256 of a file, or None if it does not exist (dataset and model versioning)."""
    if not path or not os.path.isfile(path):
        return None
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(chunk), b""):
            h.update(block)
    return h.hexdigest()


def _canonical(rec):
    return json.dumps(rec, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


class AuditLogger:
    def __init__(self, path, incidents_path=None, redact=None, store_text="redacted_preview", preview_chars=300):
        self.path = path
        self.incidents_path = incidents_path or os.path.join(os.path.dirname(path) or ".", "incidents.jsonl")
        self.redact = redact or (lambda t: t)
        self.store_text = store_text
        self.preview_chars = preview_chars
        self._lock = threading.Lock()
        self._head = None                  # (last hash, record count, file size): the file is read once, not on every write

    # ---- core ----
    def _last_hash(self):
        if not os.path.isfile(self.path):
            return GENESIS, 0
        last, n = None, 0
        with open(self.path, encoding="utf-8") as fh:
            for line in fh:
                if line.strip():
                    last, n = line, n + 1
        return (json.loads(last)["hash"], n) if last else (GENESIS, 0)

    def log(self, event, **fields):
        with self._lock:
            os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
            size = os.path.getsize(self.path) if os.path.isfile(self.path) else 0
            if self._head is None or self._head[2] != size:     # first write, or another process wrote: read the chain head
                self._head = (*self._last_hash(), size)
            prev, n, _ = self._head
            rec = {"seq": n, "ts": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "event": event, **fields, "prev_hash": prev}
            rec["hash"] = hashlib.sha256((prev + _canonical(rec)).encode("utf-8")).hexdigest()
            with open(self.path, "a", encoding="utf-8") as fh:
                fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
            self._head = (rec["hash"], n + 1, os.path.getsize(self.path))
            return rec

    def verify_chain(self):
        """(True, None) if every record links to the one before and its hash matches; else (False, seq of the first bad one)."""
        if not os.path.isfile(self.path):
            return True, None
        prev = GENESIS
        with open(self.path, encoding="utf-8") as fh:
            for i, line in enumerate(l for l in fh if l.strip()):
                rec = json.loads(line)
                got = rec.pop("hash", None)
                if rec.get("prev_hash") != prev or rec.get("seq") != i:
                    return False, i
                if hashlib.sha256((prev + _canonical(rec)).encode("utf-8")).hexdigest() != got:
                    return False, i
                prev = got
        return True, None

    def records(self, event=None):
        if not os.path.isfile(self.path):
            return []
        with open(self.path, encoding="utf-8") as fh:
            recs = [json.loads(l) for l in fh if l.strip()]
        return [r for r in recs if event is None or r["event"] == event]

    # ---- typed events ----
    def _text(self, text):
        out = {"sha256": sha256_text(text), "chars": len(text or "")}
        if self.store_text == "redacted_preview" and text:
            out["preview"] = self.redact(text[: self.preview_chars])
        return out

    def interaction(self, tenant, model, kind, input_text, output_text, decision, flags=(), sources=(), latency_ms=None):
        return self.log("interaction", tenant=tenant, model=model, kind=kind, input=self._text(input_text),
                        output=self._text(output_text), decision=decision, flags=sorted(set(flags)),
                        sources=list(sources)[:20], latency_ms=latency_ms)

    def model_version(self, name, base, adapter, adapter_repo, datasets):
        """datasets: {name: path}; each is recorded with its SHA-256 (None if the file is not on this machine)."""
        return self.log("model_version", name=name, base=base, adapter=adapter, adapter_repo=adapter_repo,
                        datasets={k: {"path": p, "sha256": file_sha256(p)} for k, p in (datasets or {}).items()})

    def training_run(self, run, base, method, dataset_path, hyperparameters=None, result=None, status=None):
        return self.log("training_run", run=run, base=base, method=method,
                        dataset={"path": dataset_path, "sha256": file_sha256(dataset_path)},
                        hyperparameters=hyperparameters or {}, result=result or {}, status=status)

    def safety_eval(self, model, results, report_path=None):
        return self.log("safety_eval", model=model, results=results, report=report_path)

    def incident(self, severity, category, description, tenant=None, escalate=True, evidence=None):
        """An incident is logged in the chain and, when escalated, queued for a human reviewer."""
        if severity not in SEVERITIES:
            raise ValueError(f"severity must be one of {SEVERITIES}")
        iid = uuid.uuid4().hex[:12]
        rec = self.log("incident", incident_id=iid, severity=severity, category=category,
                       description=self.redact(description)[:500], tenant=tenant, escalated=escalate,
                       evidence=self._text(evidence) if evidence else None)
        if escalate:
            with self._lock:
                os.makedirs(os.path.dirname(self.incidents_path) or ".", exist_ok=True)
                with open(self.incidents_path, "a", encoding="utf-8") as fh:
                    fh.write(json.dumps({"incident_id": iid, "ts": rec["ts"], "severity": severity, "category": category,
                                         "description": rec["description"], "tenant": tenant, "status": "open",
                                         "audit_seq": rec["seq"]}, ensure_ascii=False) + "\n")
        return rec

    def open_incidents(self):
        if not os.path.isfile(self.incidents_path):
            return []
        with open(self.incidents_path, encoding="utf-8") as fh:
            items = [json.loads(l) for l in fh if l.strip()]
        closed = {r["incident_id"] for r in self.records("incident_closed")}
        return [i for i in items if i["incident_id"] not in closed]

    def close_incident(self, incident_id, reviewer, resolution):
        """A human closes an incident; the closure is itself a chained record."""
        return self.log("incident_closed", incident_id=incident_id, reviewer=reviewer, resolution=resolution[:500])


def mlflow_log(run_name, params, metrics, tags=None, tracking_uri=None):
    """Log one evaluation to MLflow when it is installed; returns the run id, or None when MLflow is not available."""
    try:
        import mlflow
    except ImportError:
        return None
    if tracking_uri:
        mlflow.set_tracking_uri(tracking_uri)
    mlflow.set_experiment("drhp-responsible-ai")
    with mlflow.start_run(run_name=run_name) as run:
        mlflow.log_params({k: str(v)[:250] for k, v in (params or {}).items()})
        mlflow.log_metrics({k: float(v) for k, v in (metrics or {}).items() if isinstance(v, (int, float))})
        if tags:
            mlflow.set_tags(tags)
        return run.info.run_id
