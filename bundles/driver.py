"""Build one issuer bundle: about 42 files an issuer hands to its BRLM, all rendered from issuer.build().

    python driver.py <out_dir> <folder_name>

Run from a directory that holds the (possibly retargeted) generator modules. The folder name is written into the
document index. Re-running with the same inputs gives the same files.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import fitz  # noqa: E402

import excel_docs as X  # noqa: E402
import extra_docs as E  # noqa: E402
import fin_docs as F  # noqa: E402
import issuer as I  # noqa: E402
import legal_docs as L  # noqa: E402
import word_docs as W  # noqa: E402
from scan import image_to_scan_jpg, scan_page_to_jpg, scan_pdf  # noqa: E402

# (file name, kind, builder). kind: pdf | docx | xlsx | png | scan_pdf | scan_jpg
SPEC = [
    ("01_Certificate_of_Incorporation_2012.jpg", "scan_jpg", lambda d, p: L.coi(d, p, fresh=False)),
    ("01_Company_Profile_Business_Note.docx", "docx", W.company_profile),
    ("01_Litigation_Certificate_Legal_Counsel.docx", "docx", W.litigation_certificate),
    ("01_Note_on_Proposed_Issue.docx", "docx", W.offer_note),
    ("01_Promoter_Director_KMP_Profiles.docx", "docx", W.people_profiles),
    ("01_Restated_Financial_Information.pdf", "pdf", F.restated_pdf),
    ("02_Director_Consents_and_Declarations.pdf", "pdf", E.director_consents),
    ("02_Fresh_COI_on_Conversion_2026.pdf", "pdf", lambda d, p: L.coi(d, p, fresh=True)),
    ("02_Licences_and_Approvals.xlsx", "xlsx", X.licences),
    ("02_Objects_Project_Cost.xlsx", "xlsx", X.objects),
    ("02_Operational_Data.xlsx", "xlsx", X.operational),
    ("02_Restated_Financials_Workings.xlsx", "xlsx", X.fin_workings),
    ("03_Audited_FS_FY2025-26.pdf", "pdf", lambda d, p: F.audited_pdf(d, "FY26", p)),
    ("03_Factory_Licence.jpg", "scan_jpg", lambda d, p: L.licence_page(d, p, "factory")),
    ("03_Machinery_Quotations.pdf", "pdf", L.quotation_pages),
    ("03_Memorandum_of_Association.pdf", "pdf", L.moa),
    ("03_Process_Flow_Chart.png", "png", lambda d, p: E.flow_chart(p)),
    ("04_Articles_of_Association.pdf", "pdf", L.aoa),
    ("04_Audited_FS_FY2024-25.pdf", "scan_pdf", lambda d, p: F.audited_pdf(d, "FY25", p)),
    ("04_GPCB_Consent_CCA.jpg", "scan_jpg", lambda d, p: L.licence_page(d, p, "cca")),
    ("04_Industry_Report_Arthaveda.pdf", "pdf", E.industry_report),
    ("04_Solar_EPC_Quotation.pdf", "pdf", L.solar_quotation),
    ("05_Audited_FS_FY2023-24.pdf", "scan_pdf", lambda d, p: F.audited_pdf(d, "FY24", p)),
    ("05_Board_Resolutions_Certified_Copies.docx", "docx", W.board_resolutions),
    ("05_Fire_NOC_Expired.jpg", "scan_jpg", lambda d, p: L.licence_page(d, p, "fire")),
    ("05_Insurance_and_IP_Register.xlsx", "xlsx", X.insurance_ip),
    ("05_Selling_Shareholder_Consent.docx", "docx", W.ss_consent),
    ("06_Chartered_Engineer_Capacity_Certificate.pdf", "pdf", E.ce_certificate),
    ("06_EGM_Notices_and_Special_Resolutions.docx", "docx", W.egm_resolutions),
    ("06_GST_Registration_Certificate.pdf", "pdf", L.gst_certificate),
    ("06_Plant_Photographs_Captioned.pdf", "pdf", E.plant_photos),
    ("06_Statement_of_Borrowings.xlsx", "xlsx", X.borrowings),
    ("07_KPI_Certificate.pdf", "pdf", F.kpi_certificate),
    ("07_Leave_and_Licence_Warehouse.pdf", "pdf", L.leave_licence),
    ("07_Share_Capital_Buildup.xlsx", "xlsx", X.share_capital),
    ("08_Group_Companies_and_RPT.xlsx", "xlsx", X.group_rpt),
    ("08_Working_Capital_Certificate.pdf", "pdf", F.wc_certificate),
    ("08_Allotment_Records_PAS-3_Particulars.pdf", "pdf", L.allotment_records),
    ("09_Funds_Deployed_Certificate.pdf", "pdf", F.funds_deployed_certificate),
    ("10_Statement_of_Special_Tax_Benefits.pdf", "pdf", F.tax_benefits_statement),
    ("11_Sanction_Letter_Kalindi_Bank.pdf", "pdf", L.sanction_letter),
]


def _pages(path: Path) -> int | None:
    if path.suffix.lower() == ".pdf" or path.suffix.lower() in (".jpg", ".png"):
        if path.suffix.lower() == ".pdf":
            with fitz.open(str(path)) as doc:
                return doc.page_count
        return 1
    return None


def build(out_dir: Path, folder: str) -> list[dict]:
    out_dir.mkdir(parents=True, exist_ok=True)
    tmp = out_dir / "_work"
    tmp.mkdir(exist_ok=True)
    d = I.build()
    manifest = []
    for name, kind, fn in SPEC:
        dst = out_dir / name
        if kind == "scan_jpg":
            raw = tmp / (name + ".pdf")
            fn(d, raw)
            scan_page_to_jpg(raw, dst)
        elif kind == "scan_pdf":
            raw = tmp / name
            fn(d, raw)
            scan_pdf(raw, dst)
        elif kind == "png":
            fn(d, dst)
        else:
            fn(d, dst)
        manifest.append({"folder": folder, "file": name, "format": dst.suffix.lstrip(".").lower(),
                         "pages": _pages(dst), "kb": round(dst.stat().st_size / 1024), "desc": name.rsplit(".", 1)[0].split("_", 1)[1].replace("_", " ")})
    idx =[{"folder": folder, "file": "00_Document_Index.xlsx", "format": "xlsx", "pages": None, "kb": 0,
            "desc": "Document index"}] + manifest
    X.index(idx, out_dir / "00_Document_Index.xlsx")
    idx[0]["kb"] = round((out_dir / "00_Document_Index.xlsx").stat().st_size / 1024)
    (out_dir / "_manifest.json").write_text(json.dumps(idx, indent=1), encoding="utf-8")
    return idx


if __name__ == "__main__":
    out = Path(sys.argv[1]).resolve()
    folder = sys.argv[2] if len(sys.argv) > 2 else "issuer"
    res = build(out, folder)
    print("FILES", len(res), "PAGES", sum(r["pages"] or 0 for r in res), flush=True)
