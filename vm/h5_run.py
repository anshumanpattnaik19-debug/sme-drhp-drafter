"""H5: run the app end to end on the five issuer bundles, with the drafting model served by vLLM.

The app is driven in-process through its own HTTP routes (FastAPI TestClient), so the code path is the one the
UI uses: create project, upload files, process (extraction), draft every section, review. The model is the
merged A_qa_dpo served by `vllm serve` on 127.0.0.1:8011 (see vm/h5.sbatch). Outputs are written per bundle to
~/sme/h5/<bundle>/ for the measurement step (vm/h5_measure.py).

    DRHP_WORKSPACE=~/sme/h5_workspace python vm/h5_run.py
"""
import json
import mimetypes
import os
import sys
import time
from pathlib import Path

HOME = Path(os.path.expanduser("~"))
os.environ.setdefault("DRHP_WORKSPACE", str(HOME / "sme" / "h5_workspace"))
sys.path.insert(0, str(HOME / "sme" / "app"))

from fastapi.testclient import TestClient  # noqa: E402

from serve import app as appmod  # noqa: E402

BUNDLES = [
    ("ashtavira_flexipak", "Ashtavira Flexipak Limited"),
    ("kestrel_flexipak", "Kestrel Flexipak Limited"),
    ("bhuvanam_flexipak", "Bhuvanam Flexipak Limited"),
    ("tavanvi_flexipak", "Tavanvi Flexipak Limited"),
    ("oakvale_flexipak", "Oakvale Flexipak Limited"),
]
MODEL_URL = os.environ.get("H5_MODEL_URL", "http://127.0.0.1:8011/v1")
OUT = HOME / "sme" / "h5"

client = TestClient(appmod.app)


def wait_jobs(pid, timeout=7200):
    t0 = time.time()
    while time.time() - t0 < timeout:
        jobs = client.get(f"/api/projects/{pid}/jobs").json()
        jobs = jobs.get("jobs", jobs) if isinstance(jobs, dict) else jobs
        if not any(j["status"] == "running" for j in jobs):
            return jobs
        time.sleep(3)
    raise TimeoutError(f"jobs still running for {pid}")


def main():
    r = client.put("/api/settings", json={"use_model": True, "model_url": MODEL_URL, "model_name": "sme-drhp-7b",
                                           "temperature": 0.0, "max_tokens": 1500})
    r.raise_for_status()
    print("settings", {k: r.json().get(k) for k in ("use_model", "model_url", "model_name")}, flush=True)
    health = client.get("/api/health").json()
    print("health", json.dumps(health.get("model", health), ensure_ascii=False)[:300], flush=True)

    summary = []
    for folder, company in BUNDLES:
        src = HOME / "sme" / "bundles" / folder
        t0 = time.time()
        p = client.post("/api/projects", json={"name": company, "board": "bse_sme", "offer": {"company_name": company}})
        p.raise_for_status()
        pid = p.json()["id"]
        files = sorted(f for f in src.iterdir() if f.name[:2].isdigit())
        handles = [("files", (f.name, f.read_bytes(), mimetypes.guess_type(f.name)[0] or "application/octet-stream"))
                   for f in files]
        up = client.post(f"/api/projects/{pid}/files", files=handles, data={"paths": [f.name for f in files]})
        up.raise_for_status()
        print(folder, "uploaded", len(files), "rejected", up.json().get("rejected", [])[:3], flush=True)
        client.post(f"/api/projects/{pid}/process", json={}).raise_for_status()
        proc_jobs = wait_jobs(pid)
        proj = client.get(f"/api/projects/{pid}").json()
        statuses = {}
        for f in proj["files"]:
            statuses[f["status"]] = statuses.get(f["status"], 0) + 1
        print(folder, "processed", statuses, round(time.time() - t0), "s", flush=True)
        client.post(f"/api/projects/{pid}/draft", json={}).raise_for_status()
        draft_jobs = wait_jobs(pid)
        facts = client.get(f"/api/projects/{pid}/facts").json()
        sections = client.get(f"/api/projects/{pid}/sections").json()
        review = client.get(f"/api/projects/{pid}/review").json()
        d = OUT / folder
        d.mkdir(parents=True, exist_ok=True)
        (d / "project.json").write_text(json.dumps(proj, ensure_ascii=False, indent=1), encoding="utf-8")
        (d / "facts.json").write_text(json.dumps(facts, ensure_ascii=False, indent=1), encoding="utf-8")
        (d / "sections.json").write_text(json.dumps(sections, ensure_ascii=False, indent=1), encoding="utf-8")
        (d / "review.json").write_text(json.dumps(review, ensure_ascii=False, indent=1), encoding="utf-8")
        (d / "jobs.json").write_text(json.dumps({"process": proc_jobs, "draft": draft_jobs}, ensure_ascii=False, indent=1),
                                     encoding="utf-8")
        row = {"bundle": folder, "pid": pid, "files": len(files), "statuses": statuses,
               "facts": len(facts) if isinstance(facts, list) else facts.get("count"),
               "sections": len(sections) if isinstance(sections, list) else None,
               "minutes": round((time.time() - t0) / 60, 1),
               "job_errors": sum(len(j.get("errors", [])) for j in proc_jobs + draft_jobs)}
        summary.append(row)
        print("DONE", json.dumps(row, ensure_ascii=False), flush=True)
    (OUT / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=1), encoding="utf-8")
    print("H5_RUN_DONE", flush=True)


if __name__ == "__main__":
    main()
