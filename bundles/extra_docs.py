"""Renderers for the five bundle files that the first generator did not cover.

Director consents, Chartered Engineer certificate, plant photographs, industry report and process flow chart.
Every figure comes from the master data (issuer.build()); the industry report uses labelled illustrative
market figures, because no source document for the market is available to the generator.
"""
from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from PIL import Image, ImageDraw, ImageFont  # noqa: E402

import issuer as I  # noqa: E402
from common import inr, num  # noqa: E402
from reportlab.lib.units import mm  # noqa: E402
from reportlab.platypus import Image as RLImage  # noqa: E402

from pdfkit import Doc  # noqa: E402


def director_consents(d, path):
    c = d["company"]
    doc = Doc(path, "Director consents and declarations", letterhead=(c["name"], c["registered_office"], "Director consents"))
    doc.title("Consents to act as director and declarations (Companies Act, 2013)")
    doc.p("Each person below has given the written consent required under Section 152(5) of the Companies Act, 2013 to act as "
          "director, and the declaration required under Section 164(2) and Rule 14 of the Companies (Appointment and "
          "Qualification of Directors) Rules, 2014, in the form set out below. The originals are kept at the registered office.")
    rows = [["Name", "DIN", "Designation", "Consent dated", "Declaration (Section 164(2))"]]
    for p in I.DIRECTORS:
        rows.append([p["name"], p["din"], p["designation"], "25 October 2026", "Not disqualified; signed"])
    doc.table(rows, [48, 22, 46, 26, 32], num_cols=())
    doc.space(3)
    doc.p("<b>Form of consent (extract, for " + I.DIRECTORS[0]["name"] + ")</b>")
    doc.p(f"I, {I.DIRECTORS[0]['name']}, do hereby give my consent to act as Director of {c['name']} and to hold the office of "
          f"{I.DIRECTORS[0]['designation']}; I further declare that I am not disqualified under Section 164 of the Companies Act, 2013, "
          "and that the particulars given in my declaration are correct.")
    doc.p("Sd/- " + I.DIRECTORS[0]["name"] + "<br/>Date: 25 October 2026<br/>Place: Ahmedabad", "left")
    doc.p("<b>Independent directors</b>")
    doc.p("Each independent director has confirmed under Section 149(6) that he or she meets the criteria of independence, and "
          "has registered with the Indian Institute of Corporate Affairs databank under Rule 6 of the Companies (Appointment "
          "and Qualification of Directors) Rules, 2014. Registration numbers are held by the Company Secretary; they are to be "
          "confirmed by the BRLM before filing.")
    doc.p("<b>Not in any debarment list</b>: The Company has checked the names of the directors against the list of "
          "disqualified directors and the SEBI debarment orders as on 25 October 2026. None appears on either list.")
    doc.p("Sd/- Nidhi Rajesh Purohit<br/>Company Secretary and Compliance Officer", "left")
    return doc.build()


def ce_certificate(d, path):
    c = d["company"]
    ops = d["ops"]
    doc = Doc(path, "Chartered Engineer capacity certificate", letterhead=(c["name"], c["factory"], "Capacity certificate"))
    doc.title("Certificate of installed and utilised capacity")
    doc.p("To,<br/>The Board of Directors, " + c["name"] + "<br/>and " + d["advisers"]["brlm"]["name"] + " (the BRLM)", "left")
    doc.p("1. I, the undersigned Chartered Engineer (registration CE/2009/0417, Institution of Engineers (India)), have "
          "inspected the Company's manufacturing facility at " + c["factory"] + " on 19 October 2026 and examined the production "
          "records for the years ended 31 March 2024, 31 March 2025, 31 March 2026 and the six months ended 30 September 2026.")
    rows = [["Particulars", "FY 2023-24", "FY 2024-25", "FY 2025-26", "H1 FY 2026-27"]]
    rows.append(["Installed lamination capacity (MT per annum; H1 is six months)"] + [num(ops["capacity_mtpa"][p]) for p in ("FY24", "FY25", "FY26", "H1FY27")])
    rows.append(["Actual lamination production (MT)"] + [num(ops["production_mt"][p]) for p in ("FY24", "FY25", "FY26", "H1FY27")])
    rows.append(["Installed pouch capacity (million numbers)"] + [num(ops["pouch_capacity_mn"][p]) for p in ("FY24", "FY25", "FY26", "H1FY27")])
    rows.append(["Actual pouch production (million numbers)"] + [num(ops["pouch_production_mn"][p]) for p in ("FY24", "FY25", "FY26", "H1FY27")])
    util = [round(100 * ops["production_mt"][p] / ops["capacity_mtpa"][p], 2) for p in ("FY24", "FY25", "FY26", "H1FY27")]
    rows.append(["Capacity utilisation, lamination (%)"] + [f"{u:.2f}" for u in util])
    doc.table(rows, [70, 26, 26, 26, 26], num_cols=(1, 2, 3, 4))
    doc.p("2. The installed capacity is computed on two shifts of 24 working days a month for the lamination lines and on "
          "single-shift working for the pouch machines, as stated in the Company's plant records. The capacity figures are "
          "consistent with the machinery specifications in the quotations supplied to the Company.")
    doc.p("3. The installed capacity has not been revalued or re-rated since the date of the last capacity expansion. "
          "Expansion of lamination capacity to 12,000 MT per annum is proposed out of the Issue proceeds; the timeline and "
          "costs are set out in the Objects of the Issue (chapter 'Objects of the Issue').")
    doc.p("4. This certificate is issued for inclusion in the Draft Red Herring Prospectus and for submission to BSE Limited.")
    doc.p("Sd/-<br/>Chartered Engineer, CE/2009/0417<br/>Date: 19 October 2026<br/>Place: Ahmedabad", "left")
    doc.p("<i>Synthetic specimen. The registration number and the engineer are fictitious.</i>", "small")
    return doc.build()


def _photo(text, idx, path):
    w, h = 1200, 800
    img = Image.new("RGB", (w, h), (205 + idx * 6 % 40, 214, 226))
    dr = ImageDraw.Draw(img)
    dr.rectangle([80, 260, 1120, 640], fill=(120 + idx * 9 % 60, 130, 145), outline=(60, 60, 70), width=6)
    for k in range(6):
        x0 = 140 + k * 160
        dr.rectangle([x0, 320, x0 + 110, 580], fill=(70 + k * 12, 92, 130 + k * 5), outline=(30, 30, 40), width=3)
    try:
        f = ImageFont.truetype("C:/Windows/Fonts/arialbd.ttf", 34)
        g = ImageFont.truetype("C:/Windows/Fonts/arial.ttf", 26)
    except OSError:
        f = g = ImageFont.load_default()
    dr.text((80, 60), text, fill=(20, 30, 50), font=f)
    dr.text((80, 700), "SYNTHETIC TEST DOCUMENT - illustrative image, not a photograph of the facility", fill=(90, 30, 30), font=g)
    img.save(path, "PNG")
    return path


def plant_photos(d, path):
    c = d["company"]
    doc = Doc(path, "Plant photographs (captioned)", letterhead=(c["name"], c["factory"], "Plant photographs"))
    doc.title("Photographs of the manufacturing facility (captioned)")
    captions = [
        "Lamination line 1 (solventless), bay A", "Printing press (rotogravure, 8 colour), bay B",
        "Slitting and rewinding, bay C", "Pouch-making machine line 2", "Quality laboratory, sample testing",
        "Warehouse racking, finished goods",
    ]
    tmp = Path(path).parent / "_photos"
    tmp.mkdir(exist_ok=True)
    for i, cap in enumerate(captions):
        img = _photo(cap, i, tmp / f"photo_{i + 1}.png")
        doc.p(f"<b>Figure {i + 1}.</b> {cap}.", "small")
        doc.story.append(RLImage(str(img), width=150 * mm, height=100 * mm))
        doc.space(3)
    return doc.build()


def industry_report(d, path):
    c = d["company"]
    doc = Doc(path, "Industry report (extract)", letterhead=(I.ADVISERS["industry_research"]["name"], I.ADVISERS["industry_research"]["address"], "Industry report"))
    doc.title("Indian flexible packaging: market overview, 2021 to 2026 (extract)")
    doc.p("Prepared for " + c["name"] + " and " + d["advisers"]["brlm"]["name"] + " (the BRLM). Synthetic research extract: the "
          "market figures in this report are illustrative, set so that they are internally consistent, and are not "
          "published statistics.")
    doc.h2("1. Market size and growth")
    doc.p("The Indian flexible packaging market is estimated at around ₹38,500 crore in FY 2025-26 on illustrative assumptions, "
          "growing at a compound annual rate of 9.2 per cent over FY 2021-22 to FY 2025-26. Food and beverages, personal care "
          "and agro-chemicals together account for about 71 per cent of demand. Demand for printed laminated roll stock is "
          "closely tied to the volumes of branded packaged foods and FMCG personal care.")
    doc.h2("2. Demand drivers")
    doc.ps([
        "Organised FMCG distribution and the shift from loose to pre-packed goods in tier-2 and tier-3 towns.",
        "Stand-up and zipper pouches replacing rigid containers for snacks, spices and personal-care sachets.",
        "Food-safety rules that require barrier laminates and traceable print on the pack.",
    ], "body")
    doc.h2("3. Competitive structure")
    doc.p("The market is fragmented. The top ten converters hold an estimated 28 per cent of organised volume; most small "
          "converters serve one or two regional brands. Entry barriers are the cost of solventless lamination and gravure "
          "capacity, qualification with brand owners, and the working capital needed for raw films and inks.")
    doc.h2("4. Raw material trends")
    doc.p("Polymer films and aluminium foil account for the largest share of material cost. Prices moved within a band of "
          "±8 per cent in the review period; converters with pass-through clauses in their contracts recovered most of the "
          "movement with a lag of one to two months.")
    doc.h2("5. Outlook")
    doc.p("Illustrative base case: 8 to 10 per cent growth in volume for organised converters through FY 2029-30. Risks "
          "include raw-material volatility, regulatory changes on single-use plastics and concentration of customers.")
    doc.p("Assumptions, sources and limitations are set out in the full report, which is not reproduced here. The BRLM should "
          "confirm any figure before it is used in the Draft Red Herring Prospectus.", "small")
    return doc.build()


def flow_chart(path):
    fig, ax = plt.subplots(figsize=(10, 4.6), dpi=170)
    ax.set_axis_off()
    steps = ["Raw films and\ninks (stores)", "Printing\n(gravure)", "Solventless\nlamination",
             "Slitting and\nrewinding", "Pouch making\n(optional)", "Quality\ntesting", "Dispatch"]
    xs = [0.02 + i * 0.145 for i in range(len(steps))]
    for x, s in zip(xs, steps):
        ax.add_patch(plt.Rectangle((x, 0.38), 0.11, 0.26, fill=True, fc="#E8EEFB", ec="#2F4FD8", lw=1.4))
        ax.text(x + 0.055, 0.51, s, ha="center", va="center", fontsize=8.2, color="#1F2A44")
    for x0, x1 in zip(xs[:-1], xs[1:]):
        ax.annotate("", xy=(x1 - 0.005, 0.51), xytext=(x0 + 0.115, 0.51), arrowprops=dict(arrowstyle="->", color="#2F4FD8", lw=1.3))
    ax.text(0.5, 0.92, "Process flow: printed laminated roll stock and pouches", ha="center", fontsize=11, weight="bold", color="#1F2A44")
    ax.text(0.5, 0.12, "SYNTHETIC TEST DOCUMENT - illustrative flow chart for model testing", ha="center", fontsize=8.5, color="#8A2B2B")
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)
    return path
