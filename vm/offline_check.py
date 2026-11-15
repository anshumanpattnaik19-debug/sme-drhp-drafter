"""Offline check of the upload path: a scanned issuer file is uploaded and processed with no network access.

Run inside the container started with --network none:
    docker run --rm --network none -v <bundle_dir>:/data/bundle:ro drhp-studio python /app/vm/offline_check.py
"""
import os
import sys

sys.path.insert(0, "/app")
os.environ.setdefault("DRHP_WORKSPACE", "/tmp/offline_ws")

from fastapi.testclient import TestClient  # noqa: E402

from serve.app import app  # noqa: E402

c = TestClient(app)
print("health:", c.get("/api/health").json().get("ocr_available"), flush=True)
pid = c.post("/api/projects", json={"name": "Offline check Co", "board": "bse_sme"}).json()["id"]
name = "01_Certificate_of_Incorporation_2012.jpg"
with open(f"/data/bundle/{name}", "rb") as fh:
    up = c.post(f"/api/projects/{pid}/files", files=[("files", (name, fh.read(), "image/jpeg"))], data={"paths": [name]})
print("uploaded:", up.json().get("added", [{}])[0].get("name") if up.json().get("added") else up.json(), flush=True)
c.post(f"/api/projects/{pid}/process", json={})
import time  # noqa: E402
for _ in range(120):
    jobs = c.get(f"/api/projects/{pid}/jobs").json()
    jobs = jobs.get("jobs", jobs) if isinstance(jobs, dict) else jobs
    if not any(j["status"] == "running" for j in jobs):
        break
    time.sleep(1)
f = c.get(f"/api/projects/{pid}").json()["files"][0]
print("status:", f["status"], "| ocr_pages:", f.get("ocr_pages"), "| blocks:", f.get("blocks"), "| facts:", f.get("facts"),
      "| needs_ocr_pages:", f.get("needs_ocr_pages"), "| error:", f.get("error"), flush=True)
