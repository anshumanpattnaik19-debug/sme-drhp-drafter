"""Smoke test of the running app (the Docker container or a source run) through its own API.

Sets the drafting model to the address given, uploads a few issuer files, processes them, drafts one section with the
model, and checks the result. Writes build/docker_smoke.json.

    python vm/docker_smoke.py http://127.0.0.1:8765 http://host.docker.internal:18011/v1 bundles/out/kestrel_flexipak
"""
import json
import sys
import time
from pathlib import Path

import httpx

FILES = ["01_Company_Profile_Business_Note.docx", "01_Promoter_Director_KMP_Profiles.docx",
         "02_Objects_Project_Cost.xlsx", "02_Licences_and_Approvals.xlsx", "02_Operational_Data.xlsx",
         "05_Fire_NOC_Expired.jpg"]


def wait(client, job_id, limit=900):
    t0 = time.time()
    while time.time() - t0 < limit:
        j = client.get(f"/api/jobs/{job_id}").json()
        if j.get("status") in ("done", "done_with_errors", "cancelled"):
            return j
        time.sleep(5)
    raise TimeoutError(job_id)


def main(base: str, model_url: str, bundle: Path):
    out = {}
    with httpx.Client(base_url=base, timeout=60) as c:
        out["health"] = c.get("/api/health").json()
        if model_url == "offline":
            c.put("/api/settings", json={"use_model": False}).raise_for_status()
            out["model_test"] = "offline drafter (no model server)"
        else:
            c.put("/api/settings", json={"use_model": True, "model_url": model_url, "model_name": "sme-drhp-7b"}).raise_for_status()
            out["model_test"] = c.post("/api/settings/test").json()
        pid = c.post("/api/projects", json={"name": "Docker smoke test", "board": "bse_sme"}).json()["id"]
        files = [("files", (n, (bundle / n).read_bytes(), "application/octet-stream")) for n in FILES]
        c.post(f"/api/projects/{pid}/files", files=files).raise_for_status()
        job = c.post(f"/api/projects/{pid}/process", json={}).json()
        out["process"] = wait(c, job["id"])
        job = c.post(f"/api/projects/{pid}/draft", json={"keys": ["summary"]}).json()
        out["draft"] = wait(c, job["id"])
        d = (c.get(f"/api/projects/{pid}/sections/summary").json().get("draft") or {})
        blocks = d.get("blocks", [])
        out["section"] = {"engine": d.get("engine"), "blocks": len(blocks), "loop_trimmed": d.get("loop_trimmed"),
                          "masked": sum(len(b.get("masked") or []) for b in blocks),
                          "verification": d.get("verification", {}).get("summary") if isinstance(d.get("verification"), dict) else None}
        out["facts"] = len(c.get(f"/api/projects/{pid}/facts").json())
    Path("build").mkdir(exist_ok=True)
    Path("build/docker_smoke.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({k: out[k] for k in ("health", "model_test", "section", "facts")}, ensure_ascii=False, indent=1))
    print("process status:", out["process"].get("status"), "| draft status:", out["draft"].get("status"))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], Path(sys.argv[3]))
