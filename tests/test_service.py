"""Offline tests for the UI service: readers, classifier, rule extractor, verifier and the API end to end.

    python -m pytest tests -q          # from sme_drhp_drafter/
"""
import io
import os
import sys
import tempfile
import time

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.environ["DRHP_WORKSPACE"] = tempfile.mkdtemp(prefix="drhp_ws_")

from extract.rules import extract_facts, infer_type  # noqa: E402
from ingest.classify import classify  # noqa: E402
from ingest.readers import read_file  # noqa: E402
from verify.checks import verify_section  # noqa: E402


@pytest.fixture(scope="module")
def sample_files(tmp_path_factory):
    import docx
    import fitz
    import openpyxl
    d = tmp_path_factory.mktemp("bundle")
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "BS"
    ws.append(["Restated balance sheet (₹ in lakhs)"])
    ws.append(["Particulars", "FY 2023-24", "FY 2024-25", "FY 2025-26"])
    ws.append(["Revenue from operations", 8123.45, 9234.56, 10345.67])
    ws.append(["Profit after tax", 412.1, 518.2, 640.3])
    wb.save(d / "02_Restated_Financials_Workings.xlsx")
    doc = docx.Document()
    doc.add_paragraph("Note on proposed issue")
    doc.add_paragraph("Registered office: Plot 12, GIDC Sanand, Ahmedabad 382110")
    t = doc.add_table(rows=2, cols=2)
    t.cell(0, 0).text, t.cell(0, 1).text = "Lead manager", "Test Capital Advisors Private Limited"
    t.cell(1, 0).text, t.cell(1, 1).text = "Face value", "₹ 10"
    doc.add_paragraph("2. Issue structure")
    t = doc.add_table(rows=4, cols=2)
    for i, (k, v) in enumerate([("Particulars", "Details"),
                                ("Fresh Issue", "Up to 35,00,000 equity shares of face value ₹ 10 each aggregating ₹ [●] lakhs"),
                                ("Pre-issue equity shares", "1,00,00,000"), ("Post-issue equity shares (if fully subscribed)", "1,35,00,000")]):
        t.cell(i, 0).text, t.cell(i, 1).text = k, v
    doc.add_paragraph("The top-10 customers contributed 61.20% of revenue in FY 2025-26.")
    doc.save(d / "01_Note_on_Proposed_Issue.docx")
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Summary"
    ws.append(["Objects of the Issue (₹ lakhs)"])
    ws.append([])
    ws.append(["Object", "Estimated amount", "Deployment FY 2026-27", "Check (amount - deployment)"])
    ws.append(["Purchase and installation of plant and machinery", 1860, 1860, 0])
    ws.append(["General corporate purposes", "[●]"])
    wb.save(d / "02_Objects_Project_Cost.xlsx")
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Approvals"
    ws.append(["Register of licences and approvals"])
    ws.append(["#", "Category", "Approval", "Number", "Valid up to", "Status"])
    ws.append([1, "Plant", "Fire No-Objection Certificate", "FSC/1", "20 September 2026", "EXPIRED; renewal applied"])
    ws.append([2, "Tax", "GST registration", "24AAKCA4718M1Z6", "Until cancelled", "Obtained"])
    ws["C7"] = 0.56
    ws["C7"].number_format = "0.00%"
    wb.save(d / "02_Licences_and_Approvals.xlsx")
    pdf = fitz.open()
    page = pdf.new_page()
    page.insert_text((72, 72), "Outstanding litigation certificate. There are 3 tax proceedings involving Rs 12.50 lakhs.\n"
                               "The materiality threshold is 5% of profit after tax. CIN U22220GJ2012PLC071846.", fontsize=10)
    pdf.new_page()  # blank page: no text layer
    pdf.save(d / "01_Litigation_Certificate_Legal_Counsel.pdf")
    return d


def test_readers_keep_provenance(sample_files):
    x = read_file(str(sample_files / "02_Restated_Financials_Workings.xlsx"))
    assert x["format"] == "xlsx" and x["blocks"][0]["loc"] == "BS!1"
    w = read_file(str(sample_files / "01_Note_on_Proposed_Issue.docx"))
    assert any(b["kind"] == "table" for b in w["blocks"])
    p = read_file(str(sample_files / "01_Litigation_Certificate_Legal_Counsel.pdf"), ocr=False)
    assert p["pages"] == 2 and p["blocks"][0]["loc"] == "p. 1"
    assert p["blocks"][1]["kind"] == "needs_ocr" and p["format"] == "pdf_mixed"
    assert "OCR is switched off" in p["warnings"][0]


def test_excel_percent_cells_read_as_percent(sample_files):
    x = read_file(str(sample_files / "02_Licences_and_Approvals.xlsx"))
    assert any("56.00%" in b["text"] for b in x["blocks"])


def test_tables_and_builders(sample_files):
    from draft.builders import Ctx, build, offer_terms
    from extract.tables import tables_from_blocks
    files, blocks, tables = [], {}, []
    for n, dt in [("01_Note_on_Proposed_Issue.docx", "offer_note"), ("02_Objects_Project_Cost.xlsx", "objects_cost"),
                  ("02_Licences_and_Approvals.xlsx", "approvals")]:
        f = {"id": n[:6], "name": n, "doc_type": dt, "status": "processed"}
        files.append(f)
        blocks[f["id"]] = read_file(str(sample_files / n))["blocks"]
        tables += tables_from_blocks(blocks[f["id"]], f)
    ctx = Ctx(project={"name": "T", "offer": {}}, facts=[], files=files, tables=tables, blocks=blocks)
    terms = {k: v["value"] for k, v in offer_terms(ctx).items()}
    assert terms["fresh_issue_shares"] == "35,00,000" and terms["pre_issue_shares"] == "1,00,00,000" and terms["face_value"] == "10"
    ctx.project["offer"] = terms
    obj = build("objects", ctx)
    t = next(b for s, bl in obj.parts for b in bl if b["type"] == "table")
    assert t["rows"][0][:2] == ["Object", "Estimated amount"] and t["rows"][1][1] == "1,860.00"
    assert all("Check" not in h for h in t["rows"][0]) and t["sources"][0]["file_name"] == "02_Objects_Project_Cost.xlsx"
    assert "fund requirement table" in obj.covered
    assert any(m[0].startswith("Schedule of implementation") for m in obj.missing)
    offer = build("the_offer", ctx)
    assert "35,00,000" in str(offer.parts)

    from draft.red_flags import risk_factors
    rf_blocks, flags = risk_factors(ctx)
    keys = {f["key"] for f in flags}
    assert "approvals_expired" in keys and "customers" in keys
    rf = next(b for b in rf_blocks if b.get("flag") == "approvals_expired")
    assert "Fire No-Objection Certificate" in rf["text"] and rf["sources"][0]["file_name"] == "02_Licences_and_Approvals.xlsx"


def test_agentic_rag_offline(sample_files):
    from draft.builders import Ctx
    from extract.tables import tables_from_blocks
    from rag.agent import Agent, decompose, match_section
    from rag.index import ProjectIndex
    files, blocks, tables = [], {}, []
    for n, dt in [("01_Note_on_Proposed_Issue.docx", "offer_note"), ("02_Licences_and_Approvals.xlsx", "approvals"),
                  ("01_Litigation_Certificate_Legal_Counsel.pdf", "litigation")]:
        f = {"id": n[:6], "name": n, "doc_type": dt, "status": "processed", "format": n.rsplit(".", 1)[1]}
        files.append(f)
        blocks[f["id"]] = read_file(str(sample_files / n), ocr=False)["blocks"]
        tables += tables_from_blocks(blocks[f["id"]], f)
    ctx = Ctx(project={"name": "T", "offer": {}}, facts=[], files=files, tables=tables, blocks=blocks)
    idx = ProjectIndex(ctx)
    hits = idx.search("fire no-objection certificate expired")
    assert hits and hits[0].chunk.file_name == "02_Licences_and_Approvals.xlsx"
    assert match_section("Summarise the objects of the offer") == "objects"
    assert decompose("Who is the CS and what is the CIN?") == ["Who is the CS", "what is the CIN"]
    review = {"issues": [], "summary": {"high": 0, "medium": 0, "placeholders": 0, "sections_drafted": 0, "sections_total": 35}}
    evs = list(Agent(ctx, idx, review, {}).run("How many tax proceedings are there?", [], {"use_model": False}))
    steps = [e for e in evs if e["type"] == "step"]
    text = "".join(e["text"] for e in evs if e["type"] == "delta")
    meta = next(e for e in evs if e["type"] == "meta")
    assert steps[0]["label"] == "Planning" and steps[-1]["label"] == "Checking the answer"
    assert "[1]" in text or "[2]" in text
    assert any(s["file_name"] == "01_Litigation_Certificate_Legal_Counsel.pdf" for s in meta["sources"])


def test_superseded_cin():
    from extract.canonical import current, mark_superseded
    facts = [{"type": "identifier", "label": "CIN", "unit": "CIN", "value": "U22220GJ2012PTC071846"},
             {"type": "identifier", "label": "CIN", "unit": "CIN", "value": "U22220GJ2012PLC071846"}]
    mark_superseded(facts)
    assert facts[0].get("superseded") and current(facts, unit="CIN")["value"].endswith("PLC071846")


def test_figure_placement():
    facts = [{"id": "a", "type": "amount", "label": "Revenue", "value": "10,345.67", "unit": "₹ lakhs", "period": "FY26", "file_id": "f"},
             {"id": "b", "type": "amount", "label": "EBITDA", "value": "1,999.00", "unit": "₹ lakhs", "period": "FY26", "file_id": "f"}]
    draft = {"blocks": [{"type": "paragraph", "text": "Revenue was ₹ 10,345.67 lakhs and EBITDA was ₹ 1,999.00 lakhs.", "facts": ["a"]},
                        {"type": "table", "rows": [["P", "FY26"], ["Revenue", "10,345.67"]], "sources": [{"file_name": "x"}], "facts": []}],
             "covered": ["outstanding litigation"]}
    v = verify_section("risk_factors", draft, facts, {})
    assert v["grounded"] == 2 and [u["figure"] for u in v["weak"]] == ["1,999.00"] and not v["ungrounded"]
    st = {c["item"]: c["status"] for c in v["checklist"]}
    assert st["outstanding litigation"] == "covered" and st["contingent liabilities"] == "missing"


def test_classifier():
    assert classify("07_Leave_and_Licence_Warehouse.pdf")["doc_type"] == "lease"
    assert classify("03_Factory_Licence.jpg")["doc_type"] == "licence"
    assert classify("random.pdf", "This is the Memorandum of Association of the company")["doc_type"] == "moa"
    assert classify("scan_0001.pdf")["doc_type"] == "other"


def test_extractor_types_and_periods(sample_files):
    facts = extract_facts(read_file(str(sample_files / "02_Restated_Financials_Workings.xlsx"))["blocks"])
    rev = [f for f in facts if f["label"] == "Revenue from operations"]
    assert len(rev) == 3 and rev[0]["period"] == "FY 2023-24" and rev[0]["unit"] == "₹ lakhs"
    kv = extract_facts(read_file(str(sample_files / "01_Note_on_Proposed_Issue.docx"))["blocks"])
    assert any(f["label"] == "Lead manager" and f["type"] == "entity" for f in kv)
    txt = extract_facts(read_file(str(sample_files / "01_Litigation_Certificate_Legal_Counsel.pdf"), ocr=False)["blocks"])
    assert any(f["type"] == "identifier" and f["value"] == "U22220GJ2012PLC071846" for f in txt)
    assert any(f["type"] == "amount" and f["value"] == "12.50" and f["unit"] == "₹ lakhs" for f in txt)
    assert infer_type("18.5%")[0] == "percent" and infer_type("14 August 2012")[0] == "date"


def test_verifier_flags_invented_figures_and_prices():
    facts = [{"id": "a", "type": "amount", "label": "Revenue", "value": "10,345.67", "unit": "₹ lakhs", "period": "FY26", "file_id": "f"}]
    draft = {"blocks": [{"type": "paragraph", "text": "Revenue was ₹ 10,345.67 lakhs and EBITDA was ₹ 1,999.00 lakhs. "
                                                     "The price band of ₹ 120 per equity share is final.", "facts": []}]}
    v = verify_section("risk_factors", draft, facts, {})
    assert [u["figure"] for u in v["ungrounded"]] == ["1,999.00", "120"]
    # the block cites no facts, so a figure that exists elsewhere is only weakly grounded
    assert v["grounded"] == 0 and [u["figure"] for u in v["weak"]] == ["10,345.67"]
    assert "price band stated" in v["drhp_stage"]


def test_store_rejects_bad_ids():
    from serve import store
    with pytest.raises(KeyError):
        store.pdir("../etc")


def test_api_end_to_end(sample_files):
    from fastapi.testclient import TestClient
    from serve import store
    from serve.app import app
    store.save_settings({"ocr_enabled": False, "use_model": False})
    c = TestClient(app)
    p = c.post("/api/projects", json={"name": "Test Issuer Limited", "board": "nse_emerge"}).json()
    pid = p["id"]
    names = sorted(os.listdir(sample_files))
    files = [("files", (n, open(sample_files / n, "rb"))) for n in names] + [("files", ("evil.exe", io.BytesIO(b"MZ")))]
    r = c.post(f"/api/projects/{pid}/files", files=files, data={"paths": [f"bundle/{n}" for n in names] + ["evil.exe"]}).json()
    assert len(r["added"]) == 5 and r["rejected"][0]["name"] == "evil.exe"
    job = c.post(f"/api/projects/{pid}/process", json={}).json()
    for _ in range(200):
        if c.get(f"/api/jobs/{job['id']}").json()["status"] != "running":
            break
        time.sleep(0.05)
    proj = c.get(f"/api/projects/{pid}").json()
    assert proj["stats"]["processed"] == 5 and proj["stats"]["facts"] > 5
    assert {f["doc_type"] for f in proj["files"]} == {"restated_workings", "offer_note", "litigation", "objects_cost", "approvals"}
    # Offer details are filled from the note on the proposed issue when processing finishes
    assert proj["offer"]["fresh_issue_shares"] == "35,00,000" and proj["offer_sources"]["fresh_issue_shares"]["file_name"] == "01_Note_on_Proposed_Issue.docx"

    fact = c.post(f"/api/projects/{pid}/facts", json={"label": "Installed capacity", "value": "7,200", "unit": "MTPA", "type": "count"}).json()
    assert fact["origin"] == "user" and fact["reviewed"]
    assert c.patch(f"/api/projects/{pid}/facts/{fact['id']}", json={"value": "7,500"}).json()["edited"]

    job = c.post(f"/api/projects/{pid}/draft", json={}).json()
    for _ in range(400):
        j = c.get(f"/api/jobs/{job['id']}").json()
        if j["status"] != "running":
            break
        time.sleep(0.05)
    assert j["status"] == "done", j["errors"]
    secs = c.get(f"/api/projects/{pid}/sections").json()
    assert all(s["status"] == "drafted" for s in secs)
    rf = c.get(f"/api/projects/{pid}/sections/risk_factors").json()["draft"]
    assert rf["engine"] == "rules" and rf["verification"]["drhp_stage"] == []
    assert any(b.get("flag") == "approvals_expired" for b in rf["blocks"])
    offer_tbl = next(b for b in c.get(f"/api/projects/{pid}/sections/the_offer").json()["draft"]["blocks"] if b["type"] == "table")
    assert "35,00,000" in str(offer_tbl["rows"])
    biz = c.get(f"/api/projects/{pid}/sections/business").json()["draft"]
    assert biz["engine"] == "brief" and any(b["type"] == "brief" for b in biz["blocks"])

    signed = c.post(f"/api/projects/{pid}/sections/risk_factors/signoff", json={"reviewer": "A. Banker"}).json()
    assert signed["review"]["status"] == "reviewed" and signed["review"]["by"] == "A. Banker"
    blocks = rf["blocks"] + [{"type": "paragraph", "text": "Turnover was ₹ 77,777.77 lakhs.", "facts": []}]
    edited = c.put(f"/api/projects/{pid}/sections/risk_factors", json={"blocks": blocks}).json()
    assert edited["edited"] and any(u["figure"] == "77,777.77" for u in edited["verification"]["ungrounded"])
    assert edited["review"]["status"] == "unreviewed"            # editing withdraws the sign-off

    rv = c.get(f"/api/projects/{pid}/review").json()
    assert rv["summary"]["by_kind"]["ungrounded"] >= 1 and rv["summary"]["by_kind"]["ocr"] == 1
    assert rv["summary"]["by_kind"]["narrative"] >= 1 and rv["summary"]["sections_signed_off"] == 0
    used = [f for f in c.get(f"/api/projects/{pid}/facts").json() if f["used_in"]]
    assert used

    import json as _json
    evs = [_json.loads(x) for x in c.post(f"/api/projects/{pid}/chat", json={"message": "What's still missing from the issuer?"}).text.splitlines() if x]
    assert evs[0]["type"] == "start" and evs[-1]["type"] == "done" and any(e["type"] == "step" for e in evs)
    hist = c.get(f"/api/projects/{pid}/chat").json()["messages"]
    assert [m["role"] for m in hist] == ["user", "assistant"] and hist[1]["steps"] and hist[1]["content"]
    evs = [_json.loads(x) for x in c.post(f"/api/projects/{pid}/chat", json={"message": "fill offer details from the documents"}).text.splitlines() if x]
    assert any(e["type"] == "action" and e["action"]["kind"] == "autofill" for e in evs)
    out = c.get(f"/api/projects/{pid}/export.docx")
    assert out.status_code == 200 and out.content[:2] == b"PK"
    import docx
    d = docx.Document(io.BytesIO(out.content))
    text = "\n".join(par.text for par in d.paragraphs)
    assert "RISK FACTORS" in text and "ANNEXURE — REVIEW PACK" in text
    assert c.get(f"/api/projects/{pid}/settings").status_code == 404
    assert c.delete(f"/api/projects/{pid}").json()["ok"]
