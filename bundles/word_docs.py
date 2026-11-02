"""Word documents an issuer hands to the lead manager: company profile, promoter and management profiles,
board and shareholder resolutions, legal counsel's litigation certificate, note on the proposed issue,
selling shareholder consent."""
from __future__ import annotations

from docx import Document
from docx.enum.section import WD_ORIENT
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

import issuer as I
from common import SYNTHETIC_FOOTER, SYNTHETIC_MARK, inr, num, pct


class Word:
    def __init__(self, title, font="Arial", size=10, header=None):
        self.d = Document()
        st = self.d.styles["Normal"]
        st.font.name = font
        st.font.size = Pt(size)
        st.element.rPr.rFonts.set(qn("w:eastAsia"), font)
        for name in ("Heading 1", "Heading 2", "Heading 3", "Title"):
            s = self.d.styles[name]
            s.font.name = font
            s.font.color.rgb = RGBColor(0x1F, 0x3A, 0x5F)
            s.element.rPr.rFonts.set(qn("w:eastAsia"), font)
        sec = self.d.sections[0]
        sec.page_width, sec.page_height = Cm(21.0), Cm(29.7)
        sec.left_margin = sec.right_margin = Cm(2.2)
        sec.top_margin = sec.bottom_margin = Cm(2.0)
        hp = sec.header.paragraphs[0]
        hp.text = (header or title) + "    |    " + SYNTHETIC_MARK
        hp.runs[0].font.size = Pt(7.5)
        hp.runs[0].font.color.rgb = RGBColor(0x80, 0x80, 0x80)
        fp = sec.footer.paragraphs[0]
        fp.text = SYNTHETIC_FOOTER + "   Page "
        fp.runs[0].font.size = Pt(7)
        self._page_field(fp)
        self.d.core_properties.title = title
        self.d.core_properties.author = "Synthetic bundle generator"
        self.d.core_properties.comments = SYNTHETIC_MARK

    @staticmethod
    def _page_field(p):
        r = p.add_run()
        for tag, text in (("begin", None), (None, "PAGE"), ("end", None)):
            if tag:
                e = OxmlElement("w:fldChar")
                e.set(qn("w:fldCharType"), tag)
                r._r.append(e)
            else:
                e = OxmlElement("w:instrText")
                e.set(qn("xml:space"), "preserve")
                e.text = text
                r._r.append(e)
        r.font.size = Pt(7)

    def title(self, t):
        p = self.d.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        r = p.add_run(t)
        r.bold = True
        r.font.size = Pt(15)
        r.font.color.rgb = RGBColor(0x1F, 0x3A, 0x5F)

    def h1(self, t):
        self.d.add_heading(t, level=1)

    def h2(self, t):
        self.d.add_heading(t, level=2)

    def h3(self, t):
        self.d.add_heading(t, level=3)

    def p(self, t, bold=False, italic=False, align=None, size=None):
        para = self.d.add_paragraph()
        r = para.add_run(t)
        r.bold, r.italic = bold, italic
        if size:
            r.font.size = Pt(size)
        if align == "center":
            para.alignment = WD_ALIGN_PARAGRAPH.CENTER
        elif align == "right":
            para.alignment = WD_ALIGN_PARAGRAPH.RIGHT
        else:
            para.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
        para.paragraph_format.space_after = Pt(5)
        return para

    def bullets(self, items):
        for t in items:
            para = self.d.add_paragraph(style="List Bullet")
            para.add_run(t)
            para.paragraph_format.space_after = Pt(2)

    def numbered(self, items):
        for t in items:
            para = self.d.add_paragraph(style="List Number")
            para.add_run(t)
            para.paragraph_format.space_after = Pt(3)

    def table(self, rows, widths_cm=None, num_cols=(), font_size=8.5, header=True):
        t = self.d.add_table(rows=len(rows), cols=len(rows[0]))
        t.style = "Table Grid"
        t.alignment = WD_TABLE_ALIGNMENT.CENTER
        for i, row in enumerate(rows):
            for j, val in enumerate(row):
                cell = t.cell(i, j)
                cell.text = ""
                par = cell.paragraphs[0]
                run = par.add_run("" if val is None else str(val))
                run.font.size = Pt(font_size)
                if i == 0 and header:
                    run.bold = True
                    shd = OxmlElement("w:shd")
                    shd.set(qn("w:val"), "clear")
                    shd.set(qn("w:fill"), "DCE3EC")
                    cell._tc.get_or_add_tcPr().append(shd)
                if j in num_cols and i > 0:
                    par.alignment = WD_ALIGN_PARAGRAPH.RIGHT
                if widths_cm:
                    cell.width = Cm(widths_cm[j])
        self.d.add_paragraph()
        return t

    def page_break(self):
        self.d.add_page_break()

    def save(self, path):
        self.d.save(str(path))
        return path


P4 = ["H1FY27", "FY26", "FY25", "FY24"]
P4L = ["H1 FY27", "FY26", "FY25", "FY24"]


# ------------------------------------------------------------------ company profile -------------
def company_profile(d, path):
    c, o, pl = d["company"], d["ops"], d["pl"]
    w = Word("Company Profile and Business Information Note", header=c["name"] + " - Business information note")
    w.title(c["name"].upper())
    w.p("Business Information Note for the Book Running Lead Manager", bold=True, align="center")
    w.p("Prepared by the management for the proposed SME IPO | Version 3.2 | 22 October 2026", align="center", italic=True)
    w.p("Prepared by: Amit Kumar Varma (Head - Sales and Marketing), Rakesh Govind Joshi (Plant Head) and Sanjay Prakash "
        "Khatri (CFO). Reviewed by: Hemant Ramniklal Desai (Chairman and Managing Director).", italic=True, size=8.5)
    w.h1("1. Overview")
    w.p(f"{c['name']} (formerly {c['former_name']}) is a {c['business']}. The Company operates a single integrated "
        f"manufacturing facility at Plot No. 214-216, GIDC Industrial Estate, Sanand-II, Ahmedabad, Gujarat, spread over "
        f"{num(c['plant_area_sqm'])} square metres of leasehold land with a built-up area of {num(c['built_up_sqm'])} square "
        "metres. The facility carries out the entire value chain of flexible packaging: three-layer blown film extrusion, "
        "pre-press and cylinder management, rotogravure printing in up to eight colours, solvent-based and solventless "
        "lamination, curing, slitting and pouch conversion.")
    w.p(f"The installed lamination capacity is {num(o['capacity_mtpa']['FY26'])} metric tonnes per annum (MTPA), following "
        "the commissioning of a solventless laminator in FY 2024-25 which increased capacity from 8,400 MTPA. Pouch "
        f"conversion capacity is {o['pouch_capacity_mn']['FY26']} million pieces per annum after the addition of two pouch "
        "making machines in FY 2025-26. In FY 2025-26 the Company produced "
        f"{num(o['production_mt']['FY26'])} MT of laminated output, a capacity utilisation of "
        f"{100 * o['production_mt']['FY26'] / o['capacity_mtpa']['FY26']:.2f}%, and served {o['customers']['FY26']} customers "
        f"across India and {len(o['export_countries'])} export markets.")
    w.p(f"Revenue from operations grew from ₹{inr(pl['FY24']['revenue'])} lakhs in FY 2023-24 to ₹{inr(pl['FY26']['revenue'])} "
        f"lakhs in FY 2025-26, and was ₹{inr(pl['H1FY27']['revenue'])} lakhs in the six months ended 30 September 2026. "
        f"EBITDA margin improved from {d['ratios']['FY24']['ebitda_margin_pct']:.2f}% to "
        f"{d['ratios']['FY26']['ebitda_margin_pct']:.2f}% over the same period, driven by a richer product mix (a higher share "
        "of stand-up, spouted and retort pouches) and lower solvent and adhesive consumption on the solventless laminator. "
        "(All financial figures in this note are from the restated financial information examined by the statutory auditors.)")
    w.h1("2. History and key milestones")
    w.table([["Year", "Milestone"],
             ["2012", "Incorporated as Ashtavira Flexipak Private Limited on 14 August 2012; allotted leasehold plot at GIDC Sanand-II on 12 December 2012"],
             ["2014", "Commercial production started in January 2014 with one 8-colour rotogravure press, one solvent-based laminator and three slitters"],
             ["2016", "Entered pouch conversion with three pouch making machines; first export order to the UAE"],
             ["2017", "Commissioned three-layer blown film plant for in-house LLDPE/LDPE sealant film; preferential allotment of 5,00,000 equity shares at ₹40"],
             ["2019", "Second 8-colour rotogravure press (1,300 mm); ISO 9001 and ISO 14001 certification"],
             ["2020", "Conversion of promoter loans of ₹550 lakhs into equity at ₹55 per share"],
             ["2021", "Shrink sleeve line commissioned; term loan TL-I of ₹600 lakhs sanctioned by Kalindi Bank"],
             ["2022", "Spout fixing machines installed; first retort pouch orders for ready-to-eat foods"],
             ["2023", "BRCGS Packaging Materials certification (Grade A); EPR registration as producer of plastic packaging (2024)"],
             ["2024", "Solventless laminator commissioned (TL-II ₹750 lakhs sanctioned; ₹720 lakhs disbursed); lamination capacity raised to 9,600 MTPA"],
             ["2025", "FSSC 22000 certification; revenue crossed ₹100 crore; activated-carbon VOC control unit installed (June 2025)"],
             ["2026", "Converted into a public limited company (2 July 2026); bonus issue 4:1 (5 August 2026); Board approved SME IPO (28 August 2026)"]],
            [2.0, 14.6])
    w.h1("3. Products")
    w.p("The Company supplies printed packaging in two broad forms: roll stock (printed laminated rolls that the customer "
        "runs on its own form-fill-seal machines) and pre-formed pouches (supplied ready for filling). Every order is "
        "made to the customer's artwork and structure specification; the Company does not sell standard catalogue items.")
    prod = [
        ("Printed laminated roll stock", "Two to four-layer laminates (for example PET/MET-PET/PE, BOPP/MET-BOPP, PET/Al-foil/PE) "
         "printed by rotogravure, supplied in reels for vertical and horizontal form-fill-seal machines. Main uses: snacks, "
         "namkeen, biscuits, tea, spices, detergents and agro-chemical sachets."),
        ("Stand-up and zipper pouches", "Bottom-gusseted pouches with reclosable zippers, tear notches, hang holes and "
         "windows. Main uses: premium snacks, dry fruits, pet food, dairy powders and personal care refills."),
        ("Centre-seal and 3-side seal pouches", "Pillow and flat pouches for single-serve and value packs, including "
         "sachets of 1 g to 50 g."),
        ("Spouted and retort pouches", "Pouches with fitted spouts for liquids (edible oil, liquid detergent, baby food) and "
         "four-layer retort pouches (PET/Al-foil/Nylon/CPP) that withstand sterilisation at 121°C for ready-to-eat foods. "
         "This is the fastest growing category and carries the highest contribution margin."),
        ("Shrink sleeves and labels", "PVC and PETG shrink sleeves printed in up to eight colours for bottles and jars."),
    ]
    for name, txt in prod:
        w.h3(name)
        w.p(txt)
    w.h2("3.1 Product-wise revenue (sale of products, ₹ lakhs)")
    rows = [["Product category"] + P4L]
    for k, mix in o["product_mix"].items():
        rows.append([k] + [inr(pl[p]["sale_of_products"] * mix[p] / 100) for p in P4])
    rows.append(["Total sale of products"] + [inr(pl[p]["sale_of_products"]) for p in P4])
    w.table(rows, [6.4, 2.5, 2.5, 2.5, 2.5], num_cols=(1, 2, 3, 4))
    w.h1("4. Manufacturing process")
    steps = [
        ("Artwork and pre-press", "Customer artwork is checked for colour separation, print repeat and barcode grading. "
         "Approved designs are sent to empanelled cylinder engravers; the Company holds a library of about 4,600 "
         "customer-owned and Company-owned cylinders."),
        ("Film extrusion", "LLDPE and LDPE granules are extruded on the three-layer blown film plant into sealant film of "
         "40 to 150 microns, tested for dart impact, coefficient of friction and seal strength."),
        ("Printing", "Reverse printing on PET or BOPP film on 8-colour rotogravure presses at up to 250 m/min, using "
         "solvent-based inks with electronic register control and online viewing systems."),
        ("Lamination", "Printed film is laminated with metallised film, foil or sealant film using solvent-based polyurethane "
         "adhesive (dry laminator) or solventless two-component adhesive (solventless laminator)."),
        ("Curing", "Laminated rolls are cured in temperature-controlled curing rooms for 24 to 72 hours depending on the "
         "adhesive system."),
        ("Slitting", "Cured rolls are slit to the customer's reel width and length on slitter-rewinders; splices are flagged."),
        ("Pouch making", "Rolls for pouches are converted on automatic pouch making machines; spouts and zippers are fitted "
         "in-line or on separate machines."),
        ("Quality control and dispatch", "Each lot is tested in the in-house laboratory (bond strength, seal strength, "
         "solvent retention by gas chromatography, oxygen and moisture transmission for barrier structures) and dispatched "
         "with a certificate of analysis."),
    ]
    for i, (h, t) in enumerate(steps, 1):
        w.p(f"Step {i} - {h}: {t}")
    w.p("A process flow chart is provided separately as an image file (03_Business/03_Process_Flow_Chart.png).", italic=True)
    w.h1("5. Infrastructure and capacity")
    w.h2("5.1 Plant and machinery")
    w.table([["Machine", "Number", "Year of installation"]] + [[m, str(n), str(y)] for m, n, y in o["machines"]],
            [10.5, 2.5, 3.6], num_cols=(1, 2))
    w.h2("5.2 Installed capacity, production and utilisation")
    rows = [["Particulars", "H1 FY27", "FY26", "FY25", "FY24"],
            ["Installed lamination capacity (MT)"] + [num(o["capacity_mtpa"][p]) for p in P4],
            ["Actual production (MT)"] + [num(o["production_mt"][p]) for p in P4],
            ["Capacity utilisation (%)"] + [f"{100 * o['production_mt'][p] / o['capacity_mtpa'][p]:.2f}" for p in P4],
            ["Installed pouch capacity (million pieces)"] + [str(o["pouch_capacity_mn"][p]) for p in P4],
            ["Pouch production (million pieces)"] + [str(o["pouch_production_mn"][p]) for p in P4],
            ["Pouch capacity utilisation (%)"] + [f"{100 * o['pouch_production_mn'][p] / o['pouch_capacity_mn'][p]:.2f}" for p in P4]]
    w.table(rows, [6.4, 2.5, 2.5, 2.5, 2.5], num_cols=(1, 2, 3, 4))
    w.p("Capacity is computed on three shifts of eight hours, 300 working days a year, at an average web speed of 180 "
        "m/min and an average laminate weight of 72 g/m² for a 1,000 mm web. The capacity and utilisation figures have been "
        "certified by a chartered engineer (Er. Bhavin S. Mehta, certificate dated 19 October 2026).")
    w.h2("5.3 Utilities")
    w.bullets([f"Power: HT connection with a sanctioned load of {num(c['sanctioned_load_kva'])} kVA; two diesel generator "
               f"sets with a combined capacity of {num(c['dg_backup_kva'])} kVA for backup. Power and fuel cost was "
               f"₹{inr(pl['FY26']['oe_detail']['Power and fuel'])} lakhs in FY 2025-26.",
               "Thermal energy: PNG-fired thermic fluid heater for laminator and dryer heating.",
               "Water: GIDC supply of about 22 KL per day, mainly for cooling towers and domestic use.",
               "Solvent recovery: not installed; the proposed 10-colour press will be recovery-ready.",
               "Effluent: zero liquid discharge; hazardous waste sent to a GPCB-authorised TSDF at Vatva."])
    w.h1("6. Quality, certifications and accreditations")
    w.table([["Certification", "Certifying body", "Valid till"]] + [list(x) for x in o["certifications"]], [7.0, 6.6, 3.0])
    w.p("The laboratory is equipped with a gas chromatograph, universal testing machine, oxygen and water vapour transmission "
        "rate analysers, spectrophotometer and seal tester. Customer complaints in FY 2025-26 were 0.42% of dispatches by "
        "value (FY 2024-25: 0.57%).")
    w.h1("7. Customers, sales and marketing")
    w.p(f"The Company sells directly to brand owners and contract packers. In FY 2025-26 it served {o['customers']['FY26']} "
        f"customers; the top customer accounted for {o['top1']['FY26']:.2f}%, the top five for {o['top5']['FY26']:.2f}% and the "
        f"top ten for {o['top10']['FY26']:.2f}% of revenue from operations. Customers are identified as 'Customer A' to "
        "'Customer J' below because supply agreements contain confidentiality clauses; names are available for inspection "
        "by the BRLM.")
    rows = [["Concentration (% of revenue from operations)", "H1 FY27", "FY26", "FY25", "FY24"],
            ["Top 1 customer"] + [f"{o['top1'][p]:.2f}" for p in P4],
            ["Top 5 customers"] + [f"{o['top5'][p]:.2f}" for p in P4],
            ["Top 10 customers"] + [f"{o['top10'][p]:.2f}" for p in P4],
            ["Number of customers served"] + [str(o["customers"][p]) for p in P4]]
    w.table(rows, [6.4, 2.5, 2.5, 2.5, 2.5], num_cols=(1, 2, 3, 4))
    w.table([["Customer", "Industry", "Relationship since", "Supply arrangement"],
             ["Customer A", "Snacks and namkeen (pan-India brand)", "2016", "Annual rate contract, 60-day credit"],
             ["Customer B", "Spices and staples", "2018", "Purchase orders, 75-day credit"],
             ["Customer C", "Dairy cooperative (powders and frozen desserts)", "2020", "Tender-based annual contract"],
             ["Customer D", "Home care (detergents)", "2019", "Master supply agreement till March 2028"],
             ["Customer E", "Agro-chemicals", "2017", "Purchase orders, 90-day credit"],
             ["Customer F", "Ready-to-eat foods (retort pouches)", "2022", "Annual rate contract"],
             ["Customers G to J", "Personal care, tea, bakery, edible oil", "2015-2021", "Purchase orders"]],
            [3.0, 6.0, 2.8, 4.8])
    w.h2("7.1 Geographical spread (% of domestic sale of products)")
    rows = [["State"] + P4L]
    for st, v in o["states"].items():
        rows.append([st] + [f"{v[p]:.1f}" for p in P4])
    w.table(rows, [6.4, 2.5, 2.5, 2.5, 2.5], num_cols=(1, 2, 3, 4))
    w.p(f"Exports were {o['export_share']['FY26']:.2f}% of sale of products in FY 2025-26, to "
        + ", ".join(o["export_countries"]) + ". Export sales are invoiced in US dollars and are not hedged.")
    w.h2("7.2 Order book")
    w.p(f"As on {o['order_book']['as_on']}, the Company had unexecuted purchase orders of ₹{inr(o['order_book']['amount'])} "
        f"lakhs from {o['order_book']['customers']} customers, deliverable within 60 days. Customers do not place long-term "
        "orders; the order book is therefore not a reliable indicator of future revenue.")
    w.h2("7.3 Sales organisation")
    w.p("The sales team of 16 persons operates from the Ahmedabad corporate office with regional executives in Mumbai, "
        "Indore and Jaipur. The Company participates in packaging trade fairs and works with brand owners' packaging "
        "development teams on new structures, which typically take three to six months from sample to commercial order.")
    w.h1("8. Raw materials and suppliers")
    w.p(f"Raw materials are BOPP, PET and metallised films, aluminium foil, LDPE/LLDPE granules, printing inks, solvents "
        f"(ethyl acetate, toluene-free systems), polyurethane adhesives, zippers and spouts. Raw materials were "
        f"{100 * pl['FY26']['comc'] / pl['FY26']['revenue']:.2f}% of revenue from operations in FY 2025-26. The top ten "
        f"suppliers accounted for {o['supplier_top10']['FY26']:.2f}% of purchases. Polymer granules and part of the BOPP and "
        "PET films are bought from Desai Polymers LLP, a promoter group entity, at prices benchmarked to the monthly price "
        "lists of the primary producers; purchases from Desai Polymers LLP were "
        f"₹{inr(d['rpt']['transactions'][('Purchase of polymer granules and films', 'Desai Polymers LLP')]['FY26'])} lakhs in "
        "FY 2025-26. Film and polymer prices track crude oil derivatives and change monthly; the Company passes on price "
        "changes to most customers with a lag of 30 to 60 days under its rate contracts.")
    w.h1("9. Competition")
    w.p("The flexible packaging industry in India is fragmented, with a few large integrated converters and several "
        "hundred small and mid-sized printers and laminators. The Company competes with regional converters in Gujarat, "
        "Maharashtra and Madhya Pradesh on price, print quality, delivery time and the ability to develop new structures. "
        "Large national converters compete for the largest FMCG accounts. The Company's management considers its "
        "competitive strengths to be its integrated facility (film to pouch under one roof), food-safety certifications, "
        "and its record in spouted and retort pouches.")
    w.h1("10. Strengths, weaknesses and strategy")
    w.h2("10.1 Strengths (management view)")
    w.bullets(["Integrated facility from film extrusion to pouch conversion, which shortens lead times to 12-15 days.",
               "Long relationships with key customers; eight of the top ten customers have bought for more than five years.",
               "Food-safety and quality certifications (FSSC 22000, BRCGS Grade A) required by large brand owners.",
               "Experienced promoter with 30 years in packaging and a professional second line of management."])
    w.h2("10.2 Weaknesses and risks (management view)")
    w.bullets(["Single manufacturing facility; any disruption at Sanand-II would stop production.",
               "Customer concentration: top ten customers contribute about 61% of revenue.",
               "Exposure to polymer and film price volatility and a lag in passing on increases.",
               "Regulatory exposure under plastic waste management and extended producer responsibility rules.",
               "Related-party purchases from Desai Polymers LLP and a warehouse licensed from a Promoter.",
               "Fire NOC for the factory expired on 20 September 2026; renewal is pending."])
    w.h2("10.3 Strategy")
    w.bullets(["Add a 10-colour rotogravure press with inline inspection to serve premium brand owners that require more "
               "colours and zero-defect supply (part of the Objects of the Issue).",
               "Increase the share of value-added pouches (stand-up, zipper, spouted and retort) from "
               f"{o['product_mix']['Stand-up and zipper pouches']['H1FY27'] + o['product_mix']['Spouted and retort pouches']['H1FY27']:.1f}% "
               "of sale of products in H1 FY27 towards 40% over three years.",
               "Install a 1.20 MWp rooftop solar plant to reduce power cost (part of the Objects of the Issue).",
               "Develop recyclable mono-material laminates (all-PE and all-PP structures) in anticipation of EPR targets.",
               "Reduce borrowings and finance costs by repaying part of TL-II from Issue proceeds."])
    w.h1("11. Human resources")
    rows = [["Department", "Number of employees as on 30 September 2026"]]
    rows += [[k, str(v)] for k, v in o["employees"].items()]
    rows.append(["Total", str(sum(o["employees"].values()))])
    w.table(rows, [10.6, 6.0], num_cols=(1,))
    w.p("There is no registered trade union. The Company has not experienced any strike or lock-out in the last three years. "
        "Contract workers are engaged through two licensed contractors for loading, housekeeping and security.")
    w.h1("12. Information technology")
    w.p("The Company uses an ERP (SAP Business One) for purchase, inventory, production and accounts, with a barcode-based "
        "warehouse module implemented in 2025. Production data from the presses is captured manually in shift registers.")
    w.h1("13. Environment, health and safety and CSR")
    w.p("The facility holds a consolidated consent and authorisation from the Gujarat Pollution Control Board valid till 15 "
        "March 2027. A show-cause notice dated 11 March 2025 regarding VOC emissions from the solvent-based laminator is "
        "pending closure after corrective action. The Company spent "
        f"₹{inr(pl['FY26']['csr'])} lakhs on CSR in FY 2025-26 on education and rural health projects in Sanand taluka.")
    w.h1("14. Properties, insurance and intellectual property")
    w.table([["Property", "Tenure", "Area", "Use", "Owner / lessor"]] + [list(x) for x in d["properties"]],
            [3.6, 3.6, 2.4, 2.8, 4.2], font_size=7.5)
    w.p("Insurance policies and trademark details are in the separate register "
        "03_Business/05_Insurance_and_IP_Register.xlsx.", italic=True)
    w.h1("15. Information not yet available")
    w.bullets(["Legal Entity Identifier (LEI): to be obtained.",
               "Market maker: to be appointed by the BRLM.",
               "Peer comparison: listed peers to be identified by the BRLM from the industry report.",
               "Fire NOC renewal: application pending with the Chief Fire Officer."])
    return w.save(path)


# ------------------------------------------------------------------ promoters and management -----
def people_profiles(d, path):
    c = d["company"]
    w = Word("Promoter, Director and KMP Profiles", header=c["name"] + " - Promoter and management profiles")
    w.title("PROFILES OF PROMOTERS, DIRECTORS, KEY MANAGERIAL PERSONNEL AND SENIOR MANAGEMENT")
    w.p(f"{c['name']}  |  Information as on 25 October 2026", align="center", italic=True)
    w.h1("Part A - Promoters")
    w.p("The Promoters of the Company are Hemant Ramniklal Desai and Kavita Hemant Desai. As on the date of this note, the "
        f"Promoters together hold {num(d['holdings']['pre_issue']['Hemant Ramniklal Desai'] + d['holdings']['pre_issue']['Kavita Hemant Desai'])} "
        f"equity shares, being {d['holdings']['pct_pre_issue']['Hemant Ramniklal Desai'] + d['holdings']['pct_pre_issue']['Kavita Hemant Desai']:.2f}% "
        "of the pre-issue paid-up equity share capital.")
    bios = {
        "Hemant Ramniklal Desai": ("Hemant Ramniklal Desai is the founder, Chairman and Managing Director of the Company. He holds a "
            "Bachelor's degree in Chemical Engineering from Gujarat University (1994). He began his career in 1996 as a "
            "production engineer with a Vadodara-based laminates manufacturer and later ran a polymer trading business "
            "before founding the Company in 2012. He has about 30 years of experience in polymers and flexible packaging "
            "and is responsible for strategy, customer relationships with key accounts, capital expenditure and finance. "
            "He is a designated partner of Desai Polymers LLP and a director of Ashtavira Packaging Solutions Private "
            "Limited. He is also the Selling Shareholder in the Offer for Sale."),
        "Kavita Hemant Desai": ("Kavita Hemant Desai is a Whole-time Director and co-founder. She holds a Bachelor's degree in Commerce "
            "from Gujarat University (1996). She has about 24 years of experience in administration, human resources and "
            "purchase, and oversees human resources, administration and vendor development. She is a director of "
            "Ashtavira Packaging Solutions Private Limited."),
    }
    for p in d["promoters"]:
        w.h2(p["name"])
        w.table([["Particulars", "Details"],
                 ["Date of birth / age", f"{p['dob']} / {p['age']} years"],
                 ["Designation", p["designation"]],
                 ["DIN", p["din"]], ["PAN", p["pan_masked"] + " (masked)"],
                 ["Residential address", p["address"]],
                 ["Educational qualification", p["qualification"]],
                 ["Experience", f"{p['experience_years']} years"],
                 ["Other directorships", ", ".join(p["other_directorships"]) or "Nil"],
                 ["Other ventures (LLP / partnership)", ", ".join(p["llp"]) or "Nil"],
                 ["Equity shares held (pre-issue)", f"{num(d['holdings']['pre_issue'][p['name']])} ({d['holdings']['pct_pre_issue'][p['name']]:.2f}%)"],
                 ["Average cost of acquisition per share (₹)", f"{d['holdings']['avg_cost'][p['name']]:.2f}"]],
                [5.5, 11.1])
        w.p(bios[p["name"]])
    w.h2("Promoter Group")
    w.p("The Promoter Group, in addition to the Promoters, comprises: Parth Hemant Desai (son of the Promoters), Hemant "
        "Ramniklal Desai HUF (Karta: Hemant Ramniklal Desai), Ramniklal Chhaganlal Desai (father of Hemant Desai, aged 81), "
        "Sarlaben Ramniklal Desai (mother of Hemant Desai), Nirav Ramniklal Desai (brother of Hemant Desai), Dipika Nirav "
        "Desai (wife of Nirav Desai), Bharatkumar Jayantilal Shah and Hansaben Bharatkumar Shah (parents of Kavita Desai), "
        "Rupal Ketan Parikh (sister of Kavita Desai), Desai Polymers LLP and Ashtavira Packaging Solutions Private Limited.")
    w.p("Note: Details of the relatives' other entities (if any) have been requested from the Promoter Group members and "
        "are awaited. The father of Hemant Desai holds a 15% partnership interest in a hardware trading firm, M/s R. C. "
        "Desai & Sons, which is to be confirmed.", italic=True)
    w.h2("Confirmations by the Promoters")
    w.bullets(["None of the Promoters has been identified as a wilful defaulter or a fraudulent borrower by any bank, "
               "financial institution or consortium.",
               "None of the Promoters has been declared a fugitive economic offender.",
               "None of the Promoters or members of the Promoter Group is debarred from accessing the capital markets by SEBI "
               "or any other authority.",
               "The Promoters have not been promoters or directors of any company that was struck off or compulsorily "
               "delisted in the last five years.",
               "There has been no change in the control of the Company in the last five years.",
               "The Promoters have given personal guarantees for the borrowings from Kalindi Bank Limited (see the "
               "borrowings statement)."])
    w.page_break()
    w.h1("Part B - Board of Directors")
    rows = [["Name, DIN, designation", "Age", "Category", "Date of appointment and term", "Qualification", "Other directorships"]]
    for x in d["directors"]:
        rows.append([f"{x['name']} (DIN {x['din']}), {x['designation']}", str(x["age"]), x["category"],
                     f"{x['appointed']}; {x['term']}", x["qualification"], ", ".join(x.get("other_directorships", [])) or "Nil"])
    w.table(rows, [3.9, 1.0, 2.4, 3.6, 3.0, 2.7], font_size=7.5)
    w.h2("Brief profiles of other directors")
    w.p("Parth Hemant Desai holds a B.Tech in Printing and Packaging Technology and an MBA in Operations. He joined the "
        "Company in 2021 and was appointed a director on 1 April 2023. He heads production planning and new product "
        "development, including spouted and retort pouches.")
    w.p("Mahesh Chandrakant Trivedi is a Chartered Accountant with 34 years of experience in audit, taxation and corporate "
        "advisory. He retired as a partner of a mid-sized Ahmedabad audit firm in 2024. He chairs the Audit Committee.")
    w.p("Dr. Ananya Srinivas Rao holds a Ph.D. in Polymer Science. She has 21 years of experience in research and teaching "
        "in polymer and packaging materials and is a visiting faculty at a packaging institute. She chairs the Nomination "
        "and Remuneration Committee.")
    w.p("Vikram Harish Sethi holds a B.E. in Mechanical Engineering and a PGDM in Marketing. He has 33 years of experience "
        "in sales and general management in the FMCG and packaging industries. He chairs the Stakeholders' Relationship "
        "Committee.")
    w.h2("Relationships between directors")
    w.p("Hemant Ramniklal Desai and Kavita Hemant Desai are spouses. Parth Hemant Desai is their son. None of the "
        "independent directors is related to any other director or KMP.")
    w.h2("Committees of the Board (constituted on 20 July 2026)")
    w.table([["Committee", "Chairperson", "Members"],
             ["Audit Committee", "Mahesh Chandrakant Trivedi", "Dr. Ananya Srinivas Rao, Hemant Ramniklal Desai"],
             ["Nomination and Remuneration Committee", "Dr. Ananya Srinivas Rao", "Mahesh Chandrakant Trivedi, Vikram Harish Sethi"],
             ["Stakeholders' Relationship Committee", "Vikram Harish Sethi", "Kavita Hemant Desai, Parth Hemant Desai"],
             ["Corporate Social Responsibility Committee", "Hemant Ramniklal Desai", "Kavita Hemant Desai, Mahesh Chandrakant Trivedi"],
             ["IPO Committee", "Hemant Ramniklal Desai", "Kavita Hemant Desai, Mahesh Chandrakant Trivedi"]], [5.4, 4.6, 6.6])
    w.h2("Remuneration of executive directors (₹ lakhs)")
    rows = [["Name"] + ["H1 FY27", "FY26", "FY25", "FY24"]]
    for n in ("Hemant Ramniklal Desai", "Kavita Hemant Desai", "Parth Hemant Desai"):
        rows.append([n] + [inr(d["remuneration"][n][p]) for p in P4])
    w.table(rows, [6.4, 2.5, 2.5, 2.5, 2.5], num_cols=(1, 2, 3, 4))
    w.p("Terms approved by the shareholders on 1 August 2026 for five years from 15 July 2026: Hemant Ramniklal Desai - "
        "₹6.00 lakhs per month; Kavita Hemant Desai - ₹3.50 lakhs per month; Parth Hemant Desai - ₹2.50 lakhs per month; "
        "each with annual increments of up to 10% as approved by the Nomination and Remuneration Committee. Independent "
        "directors receive sitting fees of ₹20,000 per Board meeting and ₹10,000 per committee meeting.")
    w.h2("Shareholding of directors (pre-issue)")
    rows = [["Director", "Equity shares", "% of pre-issue capital"]]
    for n in ("Hemant Ramniklal Desai", "Kavita Hemant Desai", "Parth Hemant Desai"):
        rows.append([n, num(d["holdings"]["pre_issue"][n]), f"{d['holdings']['pct_pre_issue'][n]:.2f}"])
    rows.append(["Independent directors", "Nil", "Nil"])
    w.table(rows, [8.0, 4.3, 4.3], num_cols=(1, 2))
    w.h2("Borrowing powers")
    w.p("By a special resolution passed on 1 August 2026 under Section 180(1)(c) of the Companies Act, 2013, the members "
        "authorised the Board to borrow up to ₹75,00,00,000 (Rupees seventy-five crore) in excess of the paid-up capital, "
        "free reserves and securities premium.")
    w.page_break()
    w.h1("Part C - Key Managerial Personnel and Senior Management")
    rows = [["Name", "Designation", "Category", "Age", "Qualification", "Experience (years)", "Date of joining", "Previous employment"]]
    for k in d["kmp"]:
        if k["name"] == "Hemant Ramniklal Desai":
            continue
        rows.append([k["name"], k["designation"], k["kind"], str(k["age"]), k["qualification"], str(k["experience_years"]),
                     k["joined"], k["previous"]])
    w.table(rows, [2.4, 2.4, 1.2, 0.9, 2.6, 1.4, 1.9, 3.8], font_size=7)
    rows = [["KMP / SMP remuneration (₹ lakhs)", "H1 FY27", "FY26", "FY25", "FY24"]]
    for n in ("Sanjay Prakash Khatri", "Nidhi Rajesh Purohit"):
        rows.append([n] + [inr(d["remuneration"][n][p]) for p in P4])
    rows.append(["Rakesh Govind Joshi", "9.30", "17.40", "16.10", "14.90"])
    rows.append(["Amit Kumar Varma", "10.20", "19.20", "17.60", "16.20"])
    rows.append(["Dr. Meera Krishnan Iyer", "8.10", "15.00", "13.80", "12.60"])
    w.table(rows, [6.4, 2.5, 2.5, 2.5, 2.5], num_cols=(1, 2, 3, 4))
    w.p("Rakesh Govind Joshi and Sanjay Prakash Khatri each hold 75,000 equity shares (0.75%) of the Company. No other KMP or "
        "member of senior management holds shares. None of the KMP or senior management is related to the Promoters or "
        "directors. There is no bonus or profit-sharing plan for KMP other than performance-linked incentives.")
    w.p("Changes in KMP in the last three years: Nidhi Rajesh Purohit appointed Company Secretary and Compliance Officer on "
        "15 July 2026 (first appointment); no other changes.")
    return w.save(path)


# ------------------------------------------------------------------ resolutions -----------------
def board_resolutions(d, path):
    c, a = d["company"], d["advisers"]
    w = Word("Board resolutions", font="Times New Roman", size=11, header=c["name"] + " - Certified true copies of Board resolutions")
    for meeting, items in [
        ("15 July 2026", [
            ("Appointment of Independent Directors", "RESOLVED THAT pursuant to Sections 149, 150, 152 and 161 read with "
             "Schedule IV of the Companies Act, 2013, Mr. Mahesh Chandrakant Trivedi (DIN 06614390), Dr. Ananya Srinivas Rao "
             "(DIN 08260517) and Mr. Vikram Harish Sethi (DIN 07390824) be and are hereby appointed as Additional Directors "
             "in the category of Non-Executive Independent Directors for a term of five consecutive years with effect from "
             "15 July 2026, subject to the approval of the members."),
            ("Re-designation of Managing Director and Whole-time Directors", "RESOLVED THAT subject to the approval of the "
             "members, Mr. Hemant Ramniklal Desai be re-designated as Chairman and Managing Director, and Mrs. Kavita Hemant "
             "Desai and Mr. Parth Hemant Desai as Whole-time Directors, for a period of five years with effect from 15 July "
             "2026, on the remuneration recommended by the Board."),
            ("Appointment of Company Secretary", "RESOLVED THAT Ms. Nidhi Rajesh Purohit (ICSI membership A58214) be and is "
             "hereby appointed as Company Secretary and Compliance Officer of the Company with effect from 15 July 2026."),
        ]),
        ("22 July 2026", [
            ("Increase in authorised share capital and bonus issue", "RESOLVED THAT subject to the approval of the members, "
             "the authorised share capital of the Company be increased from ₹2,50,00,000 divided into 25,00,000 equity shares "
             "of ₹10 each to ₹15,00,00,000 divided into 1,50,00,000 equity shares of ₹10 each; AND THAT a sum of "
             "₹8,00,00,000 out of the securities premium account (₹6,00,00,000) and the surplus in the statement of profit and "
             "loss (₹2,00,00,000) be capitalised and applied for the allotment of 80,00,000 fully paid-up equity shares of ₹10 "
             "each as bonus shares to the members in the proportion of four new equity shares for every one equity share held "
             "on the record date of 1 August 2026."),
        ]),
        ("28 August 2026", [
            ("Approval of the initial public offer", "RESOLVED THAT pursuant to Sections 23, 28, 42 and 62(1)(c) and other "
             "applicable provisions of the Companies Act, 2013, the SEBI (Issue of Capital and Disclosure Requirements) "
             "Regulations, 2018 and subject to the approval of the members and such other approvals as may be required, "
             "consent of the Board be and is hereby accorded to create, offer, issue and allot up to 36,00,000 equity shares of "
             "face value ₹10 each (the 'Fresh Issue'), and to an offer for sale of up to 4,00,000 equity shares by Mr. Hemant "
             "Ramniklal Desai (the 'Offer for Sale', together the 'Issue'), at such price as may be determined by the Board or "
             "the IPO Committee in consultation with the Book Running Lead Manager, and to list the equity shares on the SME "
             "Platform of BSE Limited."),
            ("Appointment of intermediaries", f"RESOLVED THAT {a['brlm']['name']} (SEBI Reg. No. {a['brlm']['sebi_reg']}) be "
             f"appointed as the Book Running Lead Manager, {a['registrar']['name']} (SEBI Reg. No. {a['registrar']['sebi_reg']}) "
             f"as the Registrar to the Issue, and {a['legal_counsel']['name']} as the legal counsel to the Issue, on the terms of "
             "their respective engagement letters."),
            ("Constitution of IPO Committee", "RESOLVED THAT an IPO Committee comprising Mr. Hemant Ramniklal Desai "
             "(Chairman), Mrs. Kavita Hemant Desai and Mr. Mahesh Chandrakant Trivedi be constituted and authorised to approve "
             "the draft red herring prospectus, the red herring prospectus and the prospectus, to finalise the issue price, "
             "price band, lot size and basis of allotment, and to do all acts necessary for the Issue."),
            ("Materiality policy", "RESOLVED THAT the policy for determination of (a) material outstanding litigation, (b) "
             "material creditors and (c) group companies, as placed before the Board, be and is hereby approved. Under the "
             "policy, outstanding civil litigation involving the Company, its Promoters or Directors shall be considered "
             "material if the amount involved exceeds the lower of: 2% of turnover, 2% of net worth, or 5% of the average "
             "of absolute profit after tax of the last three financial years, as per the latest restated financial "
             "information; creditors to whom the Company owes more than 5% of its total trade payables as per the latest "
             "restated financial information shall be considered material creditors; and group companies shall be those with "
             "which the Company had related party transactions in the periods covered by the restated financial information, "
             "together with companies considered material by the Board."),
            ("Adoption of corporate governance policies", "RESOLVED THAT the code of conduct for directors and senior "
             "management, the whistle-blower policy, the related party transactions policy, the policy on preservation of "
             "documents, the policy for determination of materiality of events, the code of fair disclosure under the "
             "insider trading regulations and the dividend distribution policy, as placed before the Board, be adopted with "
             "effect from the date of listing."),
        ]),
        ("24 October 2026", [
            ("Approval of restated financial information", "RESOLVED THAT the restated financial information of the Company "
             "for the six months ended 30 September 2026 and the years ended 31 March 2026, 31 March 2025 and 31 March 2024, "
             f"examined by {a['auditor']['name']}, Chartered Accountants, be and is hereby approved for inclusion in the draft "
             "red herring prospectus."),
        ]),
    ]:
        w.title("CERTIFIED TRUE COPY OF THE RESOLUTIONS PASSED BY THE BOARD OF DIRECTORS")
        w.p(f"of {c['name'].upper() if meeting != '15 July 2026' else c['name'].upper()} at its meeting held on {meeting} at "
            f"the registered office of the Company at {c['registered_office']}", align="center")
        for title, text in items:
            w.p(title.upper(), bold=True)
            w.p(text)
            w.p("RESOLVED FURTHER THAT any Director or the Company Secretary of the Company be and is hereby severally "
                "authorised to sign and file the necessary forms with the Registrar of Companies and to do all such acts, "
                "deeds and things as may be necessary to give effect to this resolution.")
        w.p("Certified true copy", bold=True)
        w.p(f"For {c['name']}")
        w.p("Sd/-")
        w.p("Nidhi Rajesh Purohit, Company Secretary (A58214)" if meeting != "22 July 2026" and meeting != "15 July 2026"
            else "Hemant Ramniklal Desai, Chairman and Managing Director (DIN 02718465)")
        w.page_break()
    return w.save(path)


def egm_resolutions(d, path):
    c = d["company"]
    w = Word("EGM notices and resolutions", font="Times New Roman", size=11, header=c["name"] + " - EGM notices and special resolutions")
    w.title("NOTICE OF EXTRAORDINARY GENERAL MEETING")
    w.p(f"NOTICE is hereby given that an Extraordinary General Meeting of the members of {c['name'].upper()} will be held at "
        "shorter notice on Friday, 25 September 2026 at 11:00 a.m. at the registered office of the Company to transact the "
        "following special business:")
    w.p("ITEM NO. 1: TO APPROVE THE INITIAL PUBLIC OFFER OF EQUITY SHARES", bold=True)
    w.p("To consider and, if thought fit, to pass the following resolution as a SPECIAL RESOLUTION:")
    w.p("\"RESOLVED THAT pursuant to Sections 23, 28, 42, 62(1)(c) and other applicable provisions of the Companies Act, 2013 "
        "and the rules made thereunder, the Securities and Exchange Board of India (Issue of Capital and Disclosure "
        "Requirements) Regulations, 2018, the Securities Contracts (Regulation) Rules, 1957, and subject to approvals, "
        "consents and sanctions as may be necessary, consent of the members be and is hereby accorded to the Board to "
        "create, offer, issue and allot up to 36,00,000 equity shares of face value ₹10 each by way of a fresh issue, and to "
        "an offer for sale of up to 4,00,000 equity shares by the Selling Shareholder, through an initial public offer on "
        "the SME Platform of BSE Limited at such price, including premium, as may be determined by the Board in consultation "
        "with the Book Running Lead Manager in accordance with the ICDR Regulations, to such categories of investors as may "
        "be permitted under applicable law, including a reservation for the market maker.\"")
    w.p("\"RESOLVED FURTHER THAT the equity shares so allotted shall rank pari passu in all respects with the existing equity "
        "shares of the Company, and the Board or the IPO Committee be authorised to do all acts necessary to give effect to "
        "this resolution, including utilisation of the proceeds of the Fresh Issue for the objects to be stated in the "
        "offer document.\"")
    w.p("ITEM NO. 2: REGULARISATION OF INDEPENDENT DIRECTORS", bold=True)
    w.p("\"RESOLVED THAT pursuant to Sections 149, 150 and 152 read with Schedule IV of the Companies Act, 2013, Mr. Mahesh "
        "Chandrakant Trivedi, Dr. Ananya Srinivas Rao and Mr. Vikram Harish Sethi, who were appointed as Additional Directors "
        "on 15 July 2026, be and are hereby appointed as Independent Directors for a term of five consecutive years from 15 July "
        "2026, not liable to retire by rotation.\"")
    w.h2("EXPLANATORY STATEMENT PURSUANT TO SECTION 102 OF THE COMPANIES ACT, 2013")
    w.p("Item No. 1: The Board of Directors, at its meeting held on 28 August 2026, approved the proposal to raise funds by "
        "way of an initial public offer and listing of the equity shares on the SME Platform of BSE Limited. The proceeds of "
        "the Fresh Issue are proposed to be used for (a) purchase of plant and machinery, (b) installation of a rooftop solar "
        "power plant, (c) repayment or prepayment of certain borrowings, (d) funding incremental working capital and (e) "
        "general corporate purposes, as will be detailed in the offer document. Section 62(1)(c) requires the approval of the "
        "members by special resolution for the issue of shares to persons other than existing shareholders. None of the "
        "directors or KMP or their relatives is interested in the resolution except to the extent of their shareholding and "
        "Mr. Hemant Ramniklal Desai as the Selling Shareholder.")
    w.p("Item No. 2: The independent directors meet the criteria of independence under Section 149(6). Their profiles are "
        "annexed. The Board recommends the resolution for approval.")
    w.p("By order of the Board, Sd/- Nidhi Rajesh Purohit, Company Secretary. Place: Ahmedabad. Date: 19 September 2026.")
    w.p("Result: Both resolutions were passed unanimously by the members present (holding 100% of the paid-up capital) on "
        "25 September 2026. Form MGT-14 filed vide SRN SYN-AB71234 on 3 October 2026.", italic=True)
    w.page_break()
    w.title("CERTIFIED TRUE COPY OF SPECIAL RESOLUTIONS - EGM OF 1 AUGUST 2026")
    w.p("1. Increase in authorised share capital and alteration of Clause V of the Memorandum of Association (ordinary "
        "resolution): authorised capital increased from ₹2,50,00,000 to ₹15,00,00,000 divided into 1,50,00,000 equity shares "
        "of ₹10 each.")
    w.p("2. Issue of bonus shares (ordinary resolution): capitalisation of ₹8,00,00,000 and allotment of 80,00,000 bonus "
        "equity shares in the ratio of 4:1 to members as on the record date of 1 August 2026. Allotment made by the Board on "
        "5 August 2026.")
    w.p("3. Approval of the terms of appointment and remuneration of the Chairman and Managing Director and the Whole-time "
        "Directors under Sections 196, 197 and 203 read with Schedule V (special resolution).")
    w.p("4. Borrowing powers under Section 180(1)(c) up to ₹75,00,00,000 and creation of charges under Section 180(1)(a) "
        "(special resolutions).")
    w.page_break()
    w.title("CERTIFIED TRUE COPY OF SPECIAL RESOLUTIONS - EGM OF 10 JUNE 2026")
    w.p("1. Conversion of the Company from a private limited company into a public limited company and change of name from "
        "'Ashtavira Flexipak Private Limited' to 'Ashtavira Flexipak Limited' under Sections 14 and 18 of the Companies Act, "
        "2013 (special resolution).")
    w.p("2. Adoption of a new set of Articles of Association and alteration of the Memorandum of Association consequent to the "
        "conversion (special resolution).")
    w.p("Sd/- Hemant Ramniklal Desai, Managing Director (DIN 02718465)")
    return w.save(path)


# ------------------------------------------------------------------ litigation certificate --------
def litigation_certificate(d, path):
    c, L, a = d["company"], d["litigation"], d["advisers"]
    mat = d["materiality"]
    w = Word("Litigation certificate", font="Times New Roman", size=10.5,
             header=a["legal_counsel"]["name"] + " - Advocates and Solicitors (fictitious)")
    w.p(a["legal_counsel"]["name"].upper(), bold=True, align="center", size=13)
    w.p("Advocates and Solicitors | " + a["legal_counsel"]["address"], align="center", size=8.5)
    w.p("Date: 27 October 2026", align="right")
    w.p(f"To,\nThe Board of Directors, {c['name']}\n{c['registered_office']}\n\n{a['brlm']['name']}\n{a['brlm']['address']}")
    w.p("Re: Certificate on outstanding litigation and material developments in connection with the proposed initial public "
        f"offer of equity shares of {c['name']} (the 'Company') on the SME Platform of BSE Limited", bold=True)
    w.p("1. We have been appointed as legal counsel to the Company in relation to the proposed Issue. We have examined the "
        "records made available to us by the Company, its Promoters, Directors and Group Companies, the certificates and "
        "undertakings furnished by them, searches on the websites of the e-Courts services, the National Company Law Tribunal, "
        "the Income-tax e-filing portal and the GST portal conducted between 12 and 24 October 2026, and the materiality "
        f"policy adopted by the Board on {mat['policy_adopted']}.")
    t = mat["litigation_thresholds"]
    w.p("2. Materiality threshold: In terms of the materiality policy, outstanding civil litigation is considered material if "
        f"the amount involved exceeds ₹{inr(mat['litigation_threshold'])} lakhs, being the lowest of: 2% of turnover (₹{inr(t['2% of turnover (FY 2025-26)'])} lakhs), "
        f"2% of net worth (₹{inr(t['2% of net worth (31 March 2026)'])} lakhs) and 5% of the average absolute profit after tax of the "
        f"last three financial years (₹{inr(t['5% of average absolute PAT (last three financial years)'])} lakhs), as per the restated financial information.")
    w.p("3. On the basis of the above, we certify the following outstanding proceedings as on the date of this certificate:")
    sec = 1

    def block(title, items, fields):
        nonlocal sec
        w.h3(f"3.{sec} {title}")
        sec += 1
        if not items:
            w.p("Nil")
            return
        rows = [["Sr."] + [f[0] for f in fields]]
        for i, it in enumerate(items, 1):
            rows.append([str(i)] + [("₹" + inr(it[f[1]]) + " lakhs" if f[1] == "amount" and it.get("amount") is not None else
                                     str(it.get(f[1], "-") if it.get(f[1]) is not None else "Not quantifiable")) for f in fields])
        w.table(rows, [0.8] + [15.8 / len(fields)] * len(fields), font_size=7.5)

    co = L["company"]
    w.h2("A. Litigation involving the Company")
    block("Criminal proceedings filed by the Company", co["criminal_by"],
          [("Case details", "case"), ("Forum", "forum"), ("Parties", "parties"), ("Amount involved", "amount"), ("Brief facts", "facts"), ("Status", "status")])
    block("Criminal proceedings against the Company", co["criminal_against"], [("Case", "case")])
    block("Actions by statutory or regulatory authorities against the Company", co["regulatory"],
          [("Notice", "case"), ("Authority", "forum"), ("Brief facts", "facts"), ("Amount", "amount"), ("Status", "status")])
    block("Direct tax proceedings", co["tax_direct"], [("Proceeding", "case"), ("Amount", "amount"), ("Brief facts", "facts"), ("Status", "status")])
    block("Indirect tax proceedings", co["tax_indirect"], [("Proceeding", "case"), ("Amount", "amount"), ("Brief facts", "facts"), ("Status", "status")])
    w.h3(f"3.{sec} Material civil litigation against the Company")
    sec += 1
    w.p("Nil. There is no civil proceeding against the Company where the amount involved exceeds the materiality threshold.")
    w.h3(f"3.{sec} Other civil litigation against the Company (below the materiality threshold, disclosed for completeness)")
    sec += 1
    block_items = co["civil_against"]
    rows = [["Sr.", "Case", "Forum", "Parties", "Amount", "Facts", "Status"]]
    for i, it in enumerate(block_items, 1):
        rows.append([str(i), it["case"], it["forum"], it["parties"], "₹" + inr(it["amount"]) + " lakhs", it["facts"], it["status"]])
    w.table(rows, [0.8, 2.4, 2.4, 3.0, 1.8, 3.6, 2.6], font_size=7.5)
    w.h2("B. Litigation involving the Promoters")
    w.p("Criminal proceedings: Nil. Actions by statutory or regulatory authorities: Nil. Disciplinary action by SEBI or a "
        "stock exchange in the last five years: Nil. Material civil litigation: Nil.")
    w.p("Tax proceedings: Hemant Ramniklal Desai - intimation under Section 143(1)(a) for AY 2023-24, demand of ₹2.14 lakhs; "
        "response filed; pending. Kavita Hemant Desai - Nil.")
    w.h2("C. Litigation involving the Directors (other than Promoters)")
    w.p("Nil in all categories, based on the declarations furnished by Parth Hemant Desai, Mahesh Chandrakant Trivedi, "
        "Dr. Ananya Srinivas Rao and Vikram Harish Sethi.")
    w.h2("D. Litigation involving the Group Companies which may have a material impact on the Company")
    w.p("Desai Polymers LLP - show-cause notice under Section 73 of the CGST Act, 2017 for FY 2022-23 for ₹3.85 lakhs; reply "
        "filed on 14 July 2026; pending. In our view this does not have a material impact on the Company. Ashtavira "
        "Packaging Solutions Private Limited - Nil.")
    w.h2("E. Outstanding dues to creditors as at 30 September 2026")
    cr = L["creditors_sep26"]
    rows = [["Type of creditor", "Number of creditors", "Amount (₹ lakhs)"],
            ["Micro, small and medium enterprises", str(cr["msme"]["count"]), inr(cr["msme"]["amount"])],
            [f"Material creditors (more than 5% of trade payables, i.e. above ₹{inr(mat['creditor_threshold'])} lakhs)", str(cr["material"]["count"]), inr(cr["material"]["amount"])],
            ["Other creditors", str(cr["others"]["count"]), inr(cr["others"]["amount"])],
            ["Total", str(cr["msme"]["count"] + cr["material"]["count"] + cr["others"]["count"]), inr(mat["trade_payables_sep26"])]]
    w.table(rows, [9.0, 3.6, 4.0], num_cols=(1, 2))
    w.p("Source: certificate of the statutory auditors dated 26 October 2026 on trade payables as per the restated financial "
        "information.", italic=True)
    w.h2("F. Other confirmations")
    w.bullets([L["wilful_defaulter"],
               "There are no proceedings initiated against the Company for economic offences.",
               "There are no material frauds committed against the Company in the last five years.",
               "No inquiry, inspection or investigation has been initiated or conducted under the Companies Act, 2013 or "
               "the Companies Act, 1956 against the Company in the last five years.",
               "There are no outstanding defaults in the repayment of deposits, debentures or loans.",
               "Material developments since 30 September 2026: none, other than the next hearing date fixed in the "
               "Section 138 complaint."])
    w.p("This certificate is issued at the request of the Company for inclusion in the offer documents and for submission to "
        "BSE Limited, and may be relied upon by the Book Running Lead Manager.")
    w.p(f"For {a['legal_counsel']['name']}\n\nSd/-\n{a['legal_counsel']['partner']}, Partner\nEnrolment No. G/2841/2009 (synthetic)")
    return w.save(path)


# ------------------------------------------------------------------ offer note ------------------
def offer_note(d, path):
    c, off, a = d["company"], d["offer"], d["advisers"]
    w = Word("Note on the proposed issue", header=c["name"] + " - Note on the proposed issue (Board-approved terms)")
    w.title("NOTE ON THE PROPOSED INITIAL PUBLIC OFFER")
    w.p(f"{c['name']}  |  Prepared by the CFO for the IPO Committee and the BRLM  |  28 October 2026", align="center", italic=True)
    w.h1("1. Issue structure (as approved by the Board on 28 August 2026 and members on 25 September 2026)")
    w.table([["Particulars", "Details"],
             ["Type of issue", "Initial public offer through the book-building process"],
             ["Platform", off["exchange"]],
             ["Fresh issue", f"Up to {num(off['fresh_issue_shares'])} equity shares of face value ₹10 each, aggregating up to ₹[●] lakhs"],
             ["Offer for sale", f"Up to {num(off['ofs_shares'])} equity shares by {off['selling_shareholder']} (Selling Shareholder), aggregating up to ₹[●] lakhs"],
             ["Total issue size", f"Up to {num(off['total_shares'])} equity shares aggregating up to ₹[●] lakhs"],
             ["Price band / issue price", "[●] - to be decided by the Board / IPO Committee with the BRLM"],
             ["Lot size", "[●]"],
             ["Market maker reservation", "[●] equity shares; market maker to be appointed"],
             ["Allocation among investor categories", "As per Regulation 253 of the ICDR Regulations and applicable SEBI circulars (to be confirmed by the BRLM)"],
             ["Pre-issue paid-up capital", f"{num(I.SHARES_PRE_ISSUE)} equity shares of ₹10 each (₹{inr(I.SHARES_PRE_ISSUE * 10 / 1e5)} lakhs)"],
             ["Post-issue paid-up capital", f"Up to {num(I.SHARES_PRE_ISSUE + off['fresh_issue_shares'])} equity shares of ₹10 each"],
             ["Board approval", off["board_approval"]],
             ["Shareholders' approval", off["shareholder_approval"]],
             ["Selling Shareholder's consent", off["ss_consent"]]], [5.0, 11.6])
    w.h1("2. Objects of the Fresh Issue (₹ lakhs)")
    rows = [["Sr.", "Object", "Estimated amount", "Deployment FY 2026-27", "Deployment FY 2027-28"]]
    for i, o in enumerate(d["objects"], 1):
        rows.append([str(i), o["object"], inr(o["amount"]), inr(o["fy27"]), inr(o["fy28"])])
    tot = sum(o["amount"] for o in d["objects"])
    rows.append([str(len(d["objects"]) + 1), "General corporate purposes", "[●]", "[●]", "[●]"])
    rows.append(["", "Total net proceeds", "[●]", "[●]", "[●]"])
    w.table(rows, [0.8, 8.4, 2.4, 2.5, 2.5], num_cols=(2, 3, 4))
    w.p(f"Total of the specific objects: ₹{inr(tot)} lakhs. General corporate purposes will not exceed the limit prescribed "
        "under the ICDR Regulations for SME issues (to be confirmed by the BRLM). Issue expenses will be estimated by the BRLM. "
        f"Funds deployed up to {d['funds_deployed']['as_on']}: ₹{inr(d['funds_deployed']['amount'])} lakhs from internal "
        "accruals (advance to Ravira Machines Private Limited), to be recouped from the Net Proceeds; certificate of the "
        "statutory auditor dated 27 October 2026 enclosed separately.")
    w.p("Repayment of borrowings: the Company proposes to prepay ₹400.00 lakhs of term loan TL-II from Kalindi Bank Limited "
        "(outstanding ₹468.00 lakhs as on 30 September 2026). The sanction letter permits prepayment out of equity without "
        "charges. The bank's no-objection for the Issue has been requested on 20 October 2026 and is awaited.")
    w.h1("3. Intermediaries")
    w.table([["Role", "Name", "Registration / address"],
             ["Book Running Lead Manager", a["brlm"]["name"], f"SEBI Reg. No. {a['brlm']['sebi_reg']}; {a['brlm']['address']}"],
             ["Registrar to the Issue", a["registrar"]["name"], f"SEBI Reg. No. {a['registrar']['sebi_reg']}; {a['registrar']['address']}"],
             ["Legal counsel to the Issue", a["legal_counsel"]["name"], a["legal_counsel"]["address"]],
             ["Statutory auditor and peer review auditor", a["auditor"]["name"], f"FRN {a['auditor']['frn']}; peer review certificate {a['auditor']['peer_review_cert']} valid till {a['auditor']['peer_review_valid_till']}"],
             ["Industry research", a["industry_research"]["name"], a["industry_research"]["address"]],
             ["Market maker", "[●]", "To be appointed"],
             ["Banker to the Issue / sponsor bank", "[●]", "To be appointed"],
             ["Banker to the Company", a["banker_to_company"], ""]], [4.4, 5.2, 7.0])
    w.h1("4. Indicative timeline (subject to change)")
    w.table([["Activity", "Target"],
             ["Filing of DRHP with BSE SME", "Mid-November 2026"],
             ["In-principle approval from BSE", "January 2027 (estimate)"],
             ["Filing of RHP with RoC", "[●]"],
             ["Issue opening / closing", "[●]"],
             ["Listing", "[●]"]], [10.0, 6.6])
    w.h1("5. Open items for the BRLM")
    w.bullets(["Fire NOC renewal for the factory is pending; confirm disclosure as a risk factor and in government approvals.",
               "GPCB show-cause notice of 11 March 2025 is pending closure.",
               "LEI not yet obtained.",
               "No-objection from Kalindi Bank Limited for the Issue (negative covenant on change in shareholding) awaited.",
               "Name change to be intimated to GIDC for the leasehold plot.",
               "Selection of listed peers for the basis for offer price.",
               "Promoters' contribution and lock-in computation to be prepared by the BRLM."])
    return w.save(path)


def ss_consent(d, path):
    c = d["company"]
    w = Word("Selling shareholder consent", font="Times New Roman", size=11, header="Consent letter of the Selling Shareholder")
    w.p("Date: 3 October 2026", align="right")
    w.p(f"To,\nThe Board of Directors, {c['name']}\n{c['registered_office']}\n\n{d['advisers']['brlm']['name']}")
    w.p("Sub: Consent to participate in the Offer for Sale in the proposed initial public offer of the Company", bold=True)
    w.p(f"I, Hemant Ramniklal Desai, holding {num(d['holdings']['pre_issue']['Hemant Ramniklal Desai'])} equity shares of face "
        f"value ₹10 each of the Company, being {d['holdings']['pct_pre_issue']['Hemant Ramniklal Desai']:.2f}% of the pre-issue "
        "paid-up equity share capital, hereby give my consent to offer up to 4,00,000 equity shares held by me in the Offer "
        "for Sale forming part of the proposed initial public offer of the Company on the SME Platform of BSE Limited.")
    w.p("I confirm that: (a) the equity shares offered are fully paid-up, held by me in dematerialised form and free from all "
        "encumbrances; (b) the equity shares offered have been held by me for a period of at least one year prior to the date "
        "of filing of the draft offer document, computed in accordance with the ICDR Regulations (bonus shares being reckoned "
        "with reference to the underlying shares, subject to confirmation by the BRLM); (c) I am not debarred from accessing "
        "the capital markets; and (d) I have not been declared a wilful defaulter or fugitive economic offender.")
    w.p("I authorise the Company and the BRLM to include my name and these particulars in the offer documents.")
    w.p("Yours faithfully,\n\nSd/-\nHemant Ramniklal Desai\nPAN: XXXXX4471X (masked)")
    return w.save(path)
