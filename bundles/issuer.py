"""Master data for a fictitious SME issuer and a three-statement financial model that ties.

Every document in the bundle is rendered from the dict returned by ``build()``, so a figure that
appears in two files is the same figure. Everything here is synthetic: the company, people,
banks, auditors, suppliers, customers and all numbers are invented. Identifiers (CIN, DIN, GSTIN,
FRN, UDIN, licence numbers) follow the real formats but are random and were not checked against
any registry.

Units: Rs lakhs, 2 decimals, Indian GAAP (Schedule III Division I), as most SME issuers report.
"""
from __future__ import annotations

import copy
import math

TAX_RATE = 0.25168          # section 115BAA incl. surcharge and cess
SHARES_PRE_BONUS = 20_00_000
BONUS_RATIO = 4             # 4 bonus shares for every 1 held (allotted 05-Aug-2026)
SHARES_PRE_ISSUE = SHARES_PRE_BONUS * (1 + BONUS_RATIO)     # 1,00,00,000
FACE_VALUE = 10

# internal periods: FY23 exists only to give the audited FY24 statements their comparatives
PERIODS = ["FY23", "FY24", "FY25", "FY26", "H1FY27"]
RESTATED_PERIODS = ["FY24", "FY25", "FY26", "H1FY27"]
OPEN = {"FY23": "Mar22", "FY24": "Mar23", "FY25": "Mar24", "FY26": "Mar25", "H1FY27": "Mar26"}
CLOSE = {"FY23": "Mar23", "FY24": "Mar24", "FY25": "Mar25", "FY26": "Mar26", "H1FY27": "Sep26"}
DAYS = {"FY23": 365, "FY24": 366, "FY25": 365, "FY26": 365, "H1FY27": 183}
FRAC = {p: (0.5 if p == "H1FY27" else 1.0) for p in PERIODS}
PERIOD_LABEL = {"FY23": "Year ended 31 March 2023", "FY24": "Year ended 31 March 2024",
                "FY25": "Year ended 31 March 2025", "FY26": "Year ended 31 March 2026",
                "H1FY27": "Six months ended 30 September 2026"}
PERIOD_SHORT = {"FY23": "FY 2022-23", "FY24": "FY 2023-24", "FY25": "FY 2024-25", "FY26": "FY 2025-26",
                "H1FY27": "H1 FY 2026-27"}
DATE_LABEL = {"Mar22": "31 March 2022", "Mar23": "31 March 2023", "Mar24": "31 March 2024",
              "Mar25": "31 March 2025", "Mar26": "31 March 2026", "Sep26": "30 September 2026"}


def r2(x: float) -> float:
    return round(x + 0.0, 2)


# ------------------------------------------------------------------ company profile -----------
COMPANY = {
    "name": "Ashtavira Flexipak Limited",
    "former_name": "Ashtavira Flexipak Private Limited",
    "short": "Ashtavira",
    "cin": "U22220GJ2012PLC071846",
    "former_cin": "U22220GJ2012PTC071846",
    "incorporated_on": "14 August 2012",
    "roc": "Registrar of Companies, Gujarat at Ahmedabad",
    "converted_on": "2 July 2026",
    "conversion_egm": "10 June 2026",
    "registered_office": "Plot No. 214-216, GIDC Industrial Estate, Sanand-II, Ahmedabad - 382 110, Gujarat, India",
    "factory": "Plot No. 214-216, GIDC Industrial Estate, Sanand-II, Ahmedabad - 382 110, Gujarat, India",
    "warehouse": "Shed No. 7, Shree Hari Logistics Park, Changodar, Ahmedabad - 382 213, Gujarat, India",
    "corporate_office": "Office No. 902, Iscon Elegance, S.G. Highway, Prahlad Nagar, Ahmedabad - 380 015, Gujarat, India",
    "telephone": "+91 79 4890 2214",
    "email": "investors@ashtavira-synthetic.example",
    "website": "www.ashtavira-synthetic.example",
    "gstin": "24AAKCA4718M1Z6",
    "pan": "AAKCA4718M",
    "iec": "0812018734",
    "udyam": "UDYAM-GJ-01-0047218",
    "lei": None,      # not yet obtained: an input gap the drafter should flag
    "nic_code": "22220",
    "business": ("manufacturer of printed multi-layer flexible packaging (laminated roll stock and "
                 "pre-formed pouches) for food, FMCG, agro-chemical and personal-care brands"),
    "plant_area_sqm": 14_850,
    "built_up_sqm": 9_420,
    "sanctioned_load_kva": 1_650,
    "dg_backup_kva": 1_250,
}

PROMOTERS = [
    {"name": "Hemant Ramniklal Desai", "short": "Hemant Desai", "age": 54, "din": "02718465",
     "dob": "17 February 1972", "designation": "Chairman and Managing Director",
     "qualification": "Bachelor of Engineering (Chemical), Gujarat University (1994)",
     "experience_years": 30, "address": "Bungalow No. 12, Shivalik Greens, Bodakdev, Ahmedabad - 380 054",
     "pan_masked": "XXXXX4471X", "promoter": True, "selling_shareholder": True,
     "other_directorships": ["Ashtavira Packaging Solutions Private Limited"],
     "llp": ["Desai Polymers LLP (designated partner)"]},
    {"name": "Kavita Hemant Desai", "short": "Kavita Desai", "age": 50, "din": "02718472",
     "dob": "3 September 1976", "designation": "Whole-time Director",
     "qualification": "Bachelor of Commerce, Gujarat University (1996)",
     "experience_years": 24, "address": "Bungalow No. 12, Shivalik Greens, Bodakdev, Ahmedabad - 380 054",
     "pan_masked": "XXXXX9132X", "promoter": True, "selling_shareholder": False,
     "other_directorships": ["Ashtavira Packaging Solutions Private Limited"], "llp": []},
]

DIRECTORS = [
    {**PROMOTERS[0], "category": "Executive, Promoter", "appointed": "14 August 2012 (re-designated 15 July 2026)",
     "term": "Five years from 15 July 2026, liable to retire by rotation"},
    {**PROMOTERS[1], "category": "Executive, Promoter", "appointed": "14 August 2012 (re-designated 15 July 2026)",
     "term": "Five years from 15 July 2026, liable to retire by rotation"},
    {"name": "Parth Hemant Desai", "short": "Parth Desai", "age": 27, "din": "09841276", "dob": "21 April 1999",
     "designation": "Whole-time Director", "category": "Executive, Promoter Group",
     "qualification": "B.Tech (Printing and Packaging Technology), MBA (Operations)",
     "experience_years": 5, "appointed": "1 April 2023 (re-designated 15 July 2026)",
     "term": "Five years from 15 July 2026, liable to retire by rotation",
     "address": "Bungalow No. 12, Shivalik Greens, Bodakdev, Ahmedabad - 380 054",
     "other_directorships": [], "llp": ["Desai Polymers LLP (designated partner)"]},
    {"name": "Mahesh Chandrakant Trivedi", "short": "Mahesh Trivedi", "age": 61, "din": "06614390",
     "dob": "9 November 1964", "designation": "Independent Director", "category": "Non-Executive, Independent",
     "qualification": "Chartered Accountant (ICAI), B.Com", "experience_years": 34,
     "appointed": "15 July 2026", "term": "Five years from 15 July 2026, not liable to retire by rotation",
     "address": "A-41, Satyagrah Chhavani, Satellite, Ahmedabad - 380 015", "other_directorships": [], "llp": []},
    {"name": "Dr. Ananya Srinivas Rao", "short": "Ananya Rao", "age": 47, "din": "08260517",
     "dob": "12 June 1979", "designation": "Independent Director", "category": "Non-Executive, Independent",
     "qualification": "Ph.D. (Polymer Science), M.Sc. (Chemistry)", "experience_years": 21,
     "appointed": "15 July 2026", "term": "Five years from 15 July 2026, not liable to retire by rotation",
     "address": "C-1104, Applewoods Township, Shela, Ahmedabad - 380 058", "other_directorships": [], "llp": []},
    {"name": "Vikram Harish Sethi", "short": "Vikram Sethi", "age": 58, "din": "07390824",
     "dob": "28 January 1968", "designation": "Independent Director", "category": "Non-Executive, Independent",
     "qualification": "B.E. (Mechanical), PGDM (Marketing)", "experience_years": 33,
     "appointed": "15 July 2026", "term": "Five years from 15 July 2026, not liable to retire by rotation",
     "address": "12, Sindhu Bhavan Marg, Thaltej, Ahmedabad - 380 059", "other_directorships": [], "llp": []},
]

KMP = [
    {"name": "Hemant Ramniklal Desai", "designation": "Chairman and Managing Director", "kind": "KMP"},
    {"name": "Sanjay Prakash Khatri", "designation": "Chief Financial Officer", "kind": "KMP", "age": 44,
     "qualification": "Chartered Accountant", "experience_years": 19, "joined": "1 June 2019",
     "previous": "Finance controller at a Vadodara-based specialty films manufacturer (2011-2019)"},
    {"name": "Nidhi Rajesh Purohit", "designation": "Company Secretary and Compliance Officer", "kind": "KMP",
     "age": 31, "qualification": "Company Secretary (ICSI membership A58214), LL.B.", "experience_years": 7,
     "joined": "15 July 2026", "previous": "Assistant company secretary at a listed textile company (2021-2026)"},
    {"name": "Rakesh Govind Joshi", "designation": "Plant Head", "kind": "SMP", "age": 49,
     "qualification": "Diploma in Printing Technology", "experience_years": 26, "joined": "3 January 2014",
     "previous": "Production manager, rotogravure converting (1999-2013)"},
    {"name": "Amit Kumar Varma", "designation": "Head - Sales and Marketing", "kind": "SMP", "age": 42,
     "qualification": "MBA (Marketing)", "experience_years": 18, "joined": "10 August 2018",
     "previous": "Regional sales manager for a packaging films distributor (2008-2018)"},
    {"name": "Dr. Meera Krishnan Iyer", "designation": "Head - Quality Assurance", "kind": "SMP", "age": 39,
     "qualification": "Ph.D. (Food Technology)", "experience_years": 13, "joined": "1 February 2021",
     "previous": "Quality and food-safety lead at a dairy cooperative (2013-2021)"},
]

REMUNERATION = {   # Rs lakhs, per period (H1 is six months)
    "Hemant Ramniklal Desai": {"FY23": 42.00, "FY24": 48.00, "FY25": 54.00, "FY26": 60.00, "H1FY27": 36.00},
    "Kavita Hemant Desai": {"FY23": 24.00, "FY24": 30.00, "FY25": 33.00, "FY26": 36.00, "H1FY27": 21.00},
    "Parth Hemant Desai": {"FY23": 0.00, "FY24": 18.00, "FY25": 20.40, "FY26": 24.00, "H1FY27": 15.00},
    "Sanjay Prakash Khatri": {"FY23": 21.60, "FY24": 23.40, "FY25": 25.80, "FY26": 28.20, "H1FY27": 15.60},
    "Nidhi Rajesh Purohit": {"FY23": 0.00, "FY24": 0.00, "FY25": 0.00, "FY26": 0.00, "H1FY27": 2.95},
}

ADVISERS = {
    "brlm": {"name": "Meridian Capital Advisors Private Limited", "sebi_reg": "INM000013472",
             "address": "1201, Shapath-V, S.G. Highway, Ahmedabad - 380 054", "contact": "Rohan Mehta"},
    "registrar": {"name": "Lakshya Registry Services Private Limited", "sebi_reg": "INR000004918",
                  "address": "B-302, Sakar Complex, Ashram Road, Ahmedabad - 380 009"},
    "legal_counsel": {"name": "Kanoria Sharma & Partners", "address": "604, Venus Atlantis, Prahlad Nagar, Ahmedabad - 380 015",
                      "partner": "Adv. Ritika Kanoria"},
    "auditor": {"name": "N K Bhatt & Co.", "frn": "118742W", "partner": "CA Nirav K. Bhatt",
                "membership": "112684", "peer_review_cert": "016271",
                "peer_review_valid_till": "31 January 2029",
                "address": "305, Abhijeet-III, Mithakhali Six Roads, Ahmedabad - 380 006",
                "appointed": "AGM of 30 September 2022 for five years (FY 2022-23 to FY 2026-27)"},
    "previous_auditor": {"name": "R J Kothari & Associates", "frn": "131904W",
                         "until": "AGM of 30 September 2022 (completion of term)"},
    "industry_research": {"name": "Arthaveda Research & Advisory Private Limited",
                          "address": "8th Floor, Mondeal Square, S.G. Highway, Ahmedabad - 380 015"},
    "market_maker": None,   # not yet appointed at DRHP stage
    "banker_to_company": "Kalindi Bank Limited, Navrangpura Branch, Ahmedabad",
}

# ------------------------------------------------------------------ share capital -------------
SHAREHOLDERS = ["Hemant Ramniklal Desai", "Kavita Hemant Desai", "Parth Hemant Desai",
                "Hemant Ramniklal Desai HUF", "Jignesh Natvarlal Shah", "Pooja Dinesh Mehta",
                "Rakesh Govind Joshi", "Sanjay Prakash Khatri"]
SH_CATEGORY = {"Hemant Ramniklal Desai": "Promoter", "Kavita Hemant Desai": "Promoter",
               "Parth Hemant Desai": "Promoter Group", "Hemant Ramniklal Desai HUF": "Promoter Group",
               "Jignesh Natvarlal Shah": "Public", "Pooja Dinesh Mehta": "Public",
               "Rakesh Govind Joshi": "Public (employee)", "Sanjay Prakash Khatri": "Public (employee)"}

ALLOTMENTS = [
    {"date": "14 August 2012", "nature": "Subscription to the Memorandum of Association", "consideration": "Cash",
     "price": 10.00, "allottees": {"Hemant Ramniklal Desai": 5_000, "Kavita Hemant Desai": 5_000}},
    {"date": "31 March 2014", "nature": "Rights issue", "consideration": "Cash", "price": 10.00,
     "allottees": {"Hemant Ramniklal Desai": 2_95_000, "Kavita Hemant Desai": 1_95_000}},
    {"date": "15 February 2017", "nature": "Private placement (preferential allotment)", "consideration": "Cash",
     "price": 40.00, "allottees": {"Hemant Ramniklal Desai": 2_20_000, "Kavita Hemant Desai": 1_50_000,
                                   "Parth Hemant Desai": 1_00_000, "Hemant Ramniklal Desai HUF": 30_000}},
    {"date": "28 March 2020", "nature": "Conversion of unsecured loans (private placement)",
     "consideration": "Other than cash (conversion of loan)", "price": 55.00,
     "allottees": {"Hemant Ramniklal Desai": 6_00_000, "Kavita Hemant Desai": 2_50_000,
                   "Parth Hemant Desai": 60_000, "Hemant Ramniklal Desai HUF": 30_000,
                   "Jignesh Natvarlal Shah": 15_000, "Pooja Dinesh Mehta": 15_000,
                   "Rakesh Govind Joshi": 15_000, "Sanjay Prakash Khatri": 15_000}},
    {"date": "5 August 2026", "nature": "Bonus issue in the ratio of 4:1 (capitalisation of securities premium "
     "and retained earnings)", "consideration": "Other than cash (bonus)", "price": 0.00, "allottees": "BONUS"},
]

AUTHORISED_CAPITAL = [   # date, authorised capital (Rs), shares
    ("14 August 2012", 5_00_000, 50_000),
    ("20 March 2014", 50_00_000, 5_00_000),
    ("10 February 2017", 1_00_00_000, 10_00_000),
    ("20 March 2020", 2_50_00_000, 25_00_000),
    ("1 August 2026", 15_00_00_000, 1_50_00_000),
]

OFFER = {
    "fresh_issue_shares": 36_00_000,
    "ofs_shares": 4_00_000,
    "selling_shareholder": "Hemant Ramniklal Desai",
    "total_shares": 40_00_000,
    "price": None,               # [●] at DRHP stage
    "lot_size": None,            # [●]
    "market_maker_reservation": None,
    "exchange": "SME Platform of BSE Limited (BSE SME)",
    "board_approval": "28 August 2026",
    "shareholder_approval": "25 September 2026 (EGM, special resolution under Section 62(1)(c) of the Companies Act, 2013)",
    "ss_consent": "3 October 2026",
    "ipo_committee": "28 August 2026",
    "drhp_board_approval_target": "November 2026",
}

OBJECTS = [
    {"key": "pm", "object": "Funding capital expenditure towards purchase of plant and machinery for the existing "
     "manufacturing facility at Sanand-II", "amount": 1_860.00, "fy27": 1_244.00, "fy28": 616.00},
    {"key": "solar", "object": "Funding capital expenditure towards installation of a 1.20 MWp grid-connected "
     "rooftop solar power plant", "amount": 520.00, "fy27": 0.00, "fy28": 520.00},
    {"key": "debt", "object": "Repayment and/or prepayment, in full or in part, of certain outstanding "
     "borrowings availed by the Company", "amount": 400.00, "fy27": 400.00, "fy28": 0.00},
    {"key": "wc", "object": "Funding incremental working capital requirements", "amount": 1_450.00,
     "fy27": 0.00, "fy28": 1_450.00},
]
FUNDS_DEPLOYED = {"amount": 186.00, "as_on": "15 October 2026", "source": "Internal accruals",
                  "detail": "Advance paid to Ravira Machines Private Limited against the 10-colour rotogravure "
                            "printing machine (quotation RMPL/Q/2026/0912)"}

MACHINERY = [   # quotation-level detail, Rs lakhs
    {"item": "10-colour electronic line shaft rotogravure printing machine, 1,300 mm web width, 300 m/min, "
             "with automatic register control, ESA and solvent recovery-ready hood",
     "qty": 1, "supplier": "Ravira Machines Private Limited", "place": "Vadodara, Gujarat",
     "quote_no": "RMPL/Q/2026/0912", "quote_date": "12 September 2026", "valid_till": "11 March 2027",
     "currency": "INR", "unit_price": 1_145.00, "amount": 1_145.00, "delivery": "26 weeks from advance"},
    {"item": "Automatic high-speed pouch making machine (stand-up, zipper and 3-side seal), 120 strokes/min",
     "qty": 2, "supplier": "Sumedh Converting Systems Private Limited", "place": "Vasai, Maharashtra",
     "quote_no": "SCS/26-27/Q-0417", "quote_date": "18 September 2026", "valid_till": "17 December 2026",
     "currency": "INR", "unit_price": 186.00, "amount": 372.00, "delivery": "16 weeks from purchase order"},
    {"item": "Duplex slitter-rewinder, 1,300 mm, 500 m/min, with automatic tension control",
     "qty": 1, "supplier": "Ravira Machines Private Limited", "place": "Vadodara, Gujarat",
     "quote_no": "RMPL/Q/2026/0913", "quote_date": "12 September 2026", "valid_till": "11 March 2027",
     "currency": "INR", "unit_price": 148.50, "amount": 148.50, "delivery": "14 weeks from advance"},
    {"item": "100% inline print inspection and defect detection system with camera array and rewind integration",
     "qty": 1, "supplier": "Optiscan Vision GmbH", "place": "Germany",
     "quote_no": "OSV-IN-26-0388", "quote_date": "24 September 2026", "valid_till": "23 December 2026",
     "currency": "EUR", "unit_price_fx": 2_10_000, "fx_rate": 92.62, "unit_price": 194.50, "amount": 194.50,
     "delivery": "12 weeks ex-works; customs duty and freight included in the Rs estimate"},
]
SOLAR = {"supplier": "Suryamitra Renewables Private Limited", "place": "Gandhinagar, Gujarat",
         "quote_no": "SRPL/EPC/2026/221", "quote_date": "30 September 2026", "valid_till": "29 December 2026",
         "capacity_mwp": 1.20, "amount": 520.00, "annual_generation_mwh": 1_752,
         "items": [("Mono PERC bifacial modules, 545 Wp (2,202 nos.)", 268.40),
                   ("String inverters, 110 kW (10 nos.)", 61.20),
                   ("Module mounting structure (hot-dip galvanised) and civil work", 72.80),
                   ("DC and AC cabling, junction boxes, earthing and lightning protection", 48.60),
                   ("Net-metering, transformer augmentation and liaison", 31.50),
                   ("Installation, testing, commissioning and 5-year O&M", 37.50)]}

# ------------------------------------------------------------------ operations -----------------
OPS = {
    "capacity_mtpa": {"FY24": 8_400, "FY25": 9_600, "FY26": 9_600, "H1FY27": 4_800},
    "production_mt": {"FY24": 5_712, "FY25": 7_104, "FY26": 7_776, "H1FY27": 3_984},
    "pouch_capacity_mn": {"FY24": 420, "FY25": 420, "FY26": 540, "H1FY27": 270},
    "pouch_production_mn": {"FY24": 302, "FY25": 319, "FY26": 432, "H1FY27": 229},
    "customers": {"FY24": 214, "FY25": 238, "FY26": 266, "H1FY27": 251},
    "top1": {"FY24": 15.82, "FY25": 14.91, "FY26": 14.18, "H1FY27": 13.64},
    "top5": {"FY24": 42.11, "FY25": 40.63, "FY26": 39.84, "H1FY27": 39.12},
    "top10": {"FY24": 58.42, "FY25": 59.71, "FY26": 61.27, "H1FY27": 60.83},
    "supplier_top10": {"FY24": 72.40, "FY25": 70.86, "FY26": 69.52, "H1FY27": 68.81},
    "export_share": {"FY24": 7.21, "FY25": 8.12, "FY26": 9.04, "H1FY27": 9.37},
    "product_mix": {   # % of sale of products
        "Printed laminated roll stock": {"FY24": 58.10, "FY25": 55.40, "FY26": 52.20, "H1FY27": 50.30},
        "Stand-up and zipper pouches": {"FY24": 18.20, "FY25": 19.90, "FY26": 22.10, "H1FY27": 23.00},
        "Centre-seal and 3-side seal pouches": {"FY24": 13.90, "FY25": 14.10, "FY26": 13.80, "H1FY27": 13.60},
        "Spouted and retort pouches": {"FY24": 4.00, "FY25": 4.80, "FY26": 6.00, "H1FY27": 7.10},
        "Shrink sleeves and labels": {"FY24": 5.80, "FY25": 5.80, "FY26": 5.90, "H1FY27": 6.00},
    },
    "end_use": {   # % of sale of products
        "Snacks, namkeen and bakery": {"FY24": 31.4, "FY25": 30.2, "FY26": 29.1, "H1FY27": 28.6},
        "Spices, tea and staples": {"FY24": 22.6, "FY25": 22.9, "FY26": 23.4, "H1FY27": 23.8},
        "Dairy and frozen foods": {"FY24": 12.8, "FY25": 13.6, "FY26": 14.2, "H1FY27": 14.5},
        "Personal and home care": {"FY24": 14.1, "FY25": 14.3, "FY26": 14.6, "H1FY27": 14.8},
        "Agro-chemicals and seeds": {"FY24": 12.3, "FY25": 12.1, "FY26": 11.8, "H1FY27": 11.6},
        "Pharma, nutraceuticals and others": {"FY24": 6.8, "FY25": 6.9, "FY26": 6.9, "H1FY27": 6.7},
    },
    "states": {   # % of domestic sale of products
        "Gujarat": {"FY24": 41.2, "FY25": 39.8, "FY26": 38.5, "H1FY27": 37.9},
        "Maharashtra": {"FY24": 21.6, "FY25": 22.4, "FY26": 23.1, "H1FY27": 23.5},
        "Madhya Pradesh": {"FY24": 11.3, "FY25": 11.6, "FY26": 11.9, "H1FY27": 12.0},
        "Rajasthan": {"FY24": 9.7, "FY25": 9.9, "FY26": 10.2, "H1FY27": 10.3},
        "Other states": {"FY24": 16.2, "FY25": 16.3, "FY26": 16.3, "H1FY27": 16.3},
    },
    "export_countries": ["United Arab Emirates", "Kenya", "Bangladesh", "Oman", "Tanzania", "Nepal"],
    "employees": {"Production": 142, "Quality control and laboratory": 18, "Maintenance and utilities": 21,
                  "Pre-press and design": 9, "Stores, purchase and logistics": 24, "Sales and marketing": 16,
                  "Finance, accounts and secretarial": 11, "Human resources and administration": 13,
                  "Contract workers (through licensed contractors)": 58},
    "order_book": {"as_on": "30 September 2026", "amount": 1_842.60, "customers": 94},
    "certifications": [
        ("ISO 9001:2015 (quality management)", "Certified by Veritrust Assurance Services (synthetic)", "14 March 2027"),
        ("ISO 14001:2015 (environmental management)", "Certified by Veritrust Assurance Services (synthetic)", "14 March 2027"),
        ("FSSC 22000 v6 (food-safety management for packaging manufacture)", "Certified by Nutrisafe Certification (synthetic)", "2 November 2027"),
        ("BRCGS Packaging Materials Issue 6, Grade A", "Audited by Nutrisafe Certification (synthetic)", "18 January 2027"),
    ],
    "machines": [
        ("8-colour rotogravure printing machine, 1,250 mm", 1, 2014),
        ("8-colour rotogravure printing machine, 1,300 mm", 1, 2019),
        ("Solvent-based dry laminator", 1, 2014),
        ("Solventless laminator, 1,300 mm, 400 m/min", 1, 2024),
        ("Three-layer blown film plant (LLDPE/LDPE)", 1, 2017),
        ("Slitter-rewinder", 3, 2014),
        ("Pouch making machines (3-side seal, centre-seal, stand-up)", 7, 2016),
        ("Spout fixing machine", 2, 2022),
        ("Shrink sleeve seaming and cutting machines", 2, 2021),
    ],
}

# ------------------------------------------------------------------ financial drivers ----------
REV = {"FY23": 8_012.60, "FY24": 9_240.50, "FY25": 10_815.30, "FY26": 12_688.75, "H1FY27": 7_105.40}
SCRAP = {"FY23": 131.20, "FY24": 152.40, "FY25": 171.85, "FY26": 196.30, "H1FY27": 108.65}
EXPORT_INCENTIVE = {"FY23": 3.90, "FY24": 4.85, "FY25": 6.20, "FY26": 8.15, "H1FY27": 4.70}
MAT_PCT = {"FY23": 0.7020, "FY24": 0.6990, "FY25": 0.6920, "FY26": 0.6870, "H1FY27": 0.6840}
EMP_PCT = {"FY23": 0.0570, "FY24": 0.0560, "FY25": 0.0550, "FY26": 0.0540, "H1FY27": 0.0550}
OE_PCT = {"FY23": 0.1355, "FY24": 0.1340, "FY25": 0.1310, "FY26": 0.1290, "H1FY27": 0.1270}
OTHER_INCOME = {"FY23": 31.80, "FY24": 38.20, "FY25": 45.60, "FY26": 52.10, "H1FY27": 31.40}
RM_DAYS = {"FY23": 39, "FY24": 38, "FY25": 37, "FY26": 36, "H1FY27": 36}
FGW_DAYS = {"FY23": 14, "FY24": 14, "FY25": 14, "FY26": 13, "H1FY27": 13}
DEBTOR_DAYS = {"FY23": 82, "FY24": 84, "FY25": 85, "FY26": 83, "H1FY27": 84}
CREDITOR_DAYS = {"FY23": 55, "FY24": 53, "FY25": 50, "FY26": 48, "H1FY27": 48}
STORES = {"Mar22": 74.00, "Mar23": 80.00, "Mar24": 85.00, "Mar25": 92.00, "Mar26": 104.00, "Sep26": 110.00}
OCA_PCT = 0.031
OCL_PCT = 0.024
DEPOSITS = {"Mar22": 44.00, "Mar23": 46.00, "Mar24": 48.00, "Mar25": 51.50, "Mar26": 51.50, "Sep26": 53.00}
CWIP = {"Mar22": 0.00, "Mar23": 0.00, "Mar24": 0.00, "Mar25": 35.00, "Mar26": 145.00, "Sep26": 210.00}
CAP_ADV = {"Mar22": 0.00, "Mar23": 0.00, "Mar24": 0.00, "Mar25": 0.00, "Mar26": 60.00, "Sep26": 186.00}
GRATUITY = {"Mar22": 42.00, "Mar23": 52.00, "Mar24": 76.60, "Mar25": 92.80, "Mar26": 110.40, "Sep26": 121.90}
GRATUITY_PAID = {"FY23": 3.10, "FY24": 4.00, "FY25": 4.60, "FY26": 5.10, "H1FY27": 2.80}
TAX_LIAB = {"Mar22": 12.80, "Mar23": 15.20, "Mar24": 18.40, "Mar25": 22.60, "Mar26": 27.90, "Sep26": 41.30}
FD_LIEN = {"Mar22": 75.00, "Mar23": 80.00, "Mar24": 80.00, "Mar25": 85.00, "Mar26": 90.00, "Sep26": 90.00}
CASH_ON_HAND = {"Mar22": 5.10, "Mar23": 6.40, "Mar24": 4.85, "Mar25": 7.20, "Mar26": 5.65, "Sep26": 6.10}
BANK_CHARGES = {"FY23": 16.40, "FY24": 18.00, "FY25": 24.50, "FY26": 21.00, "H1FY27": 11.80}
HIST_PROFIT = {"FY20": 290.00, "FY21": 352.00, "FY22": 418.00}   # section 198 net profit, pre-FY23
OPEN_DTL = 150.00
OPEN_SC = 200.00

BORROW = {   # Rs lakhs outstanding
    "TL0": {"Mar22": 600.00, "Mar23": 480.00, "Mar24": 360.00, "Mar25": 240.00, "Mar26": 120.00, "Sep26": 60.00},
    "TL1": {"Mar22": 0.00, "Mar23": 0.00, "Mar24": 0.00, "Mar25": 684.00, "Mar26": 540.00, "Sep26": 468.00},
    "VEH": {"Mar22": 68.00, "Mar23": 52.00, "Mar24": 71.40, "Mar25": 47.80, "Mar26": 44.60, "Sep26": 36.20},
    "CC": {"Mar22": 1_105.00, "Mar23": 1_240.00, "Mar24": 1_320.00, "Mar25": 1_325.00, "Mar26": 1_560.00, "Sep26": 1_705.00},
    "UNSEC": {"Mar22": 120.00, "Mar23": 150.00, "Mar24": 180.00, "Mar25": 210.00, "Mar26": 160.00, "Sep26": 140.00},
}
CUR_MAT = {   # current maturities of long-term debt, by date
    "TL0": {"Mar22": 120.00, "Mar23": 120.00, "Mar24": 120.00, "Mar25": 120.00, "Mar26": 120.00, "Sep26": 60.00},
    "TL1": {"Mar22": 0.00, "Mar23": 0.00, "Mar24": 0.00, "Mar25": 144.00, "Mar26": 144.00, "Sep26": 144.00},
    "VEH": {"Mar22": 22.40, "Mar23": 19.60, "Mar24": 24.80, "Mar25": 21.20, "Mar26": 17.90, "Sep26": 16.40},
}
RATES = {"TL0": 0.0925, "TL1": 0.0925, "VEH": 0.0980, "CC": 0.0960, "UNSEC": 0.0900}
LOANS = {
    "TL0": {"lender": "Kalindi Bank Limited", "facility": "Term loan (TL-I) for plant and machinery",
            "sanctioned": 600.00, "sanction_date": "18 June 2021", "rate": "Repo rate + 3.75% (9.25% p.a. at 30 Sep 2026)",
            "tenure": "60 months including 6 months moratorium; 54 equated monthly instalments of Rs 11.11 lakhs",
            "security": "Hypothecation of plant and machinery funded; extension of equitable mortgage on factory land and building at Sanand-II; personal guarantees of Hemant Desai and Kavita Desai"},
    "TL1": {"lender": "Kalindi Bank Limited", "facility": "Term loan (TL-II) for solventless laminator",
            "sanctioned": 750.00, "sanction_date": "26 June 2024", "rate": "Repo rate + 3.75% (9.25% p.a. at 30 Sep 2026)",
            "tenure": "72 months including 12 months moratorium; 60 equated monthly principal instalments of Rs 12.00 lakhs from January 2025",
            "security": "Exclusive hypothecation of the solventless laminator; extension of equitable mortgage on factory land and building; personal guarantees of Hemant Desai and Kavita Desai"},
    "VEH": {"lender": "Vasundhara Finserv Limited (NBFC)", "facility": "Vehicle loans (5 loans)",
            "sanctioned": 96.00, "sanction_date": "Various, 2021 to 2025", "rate": "9.40% to 10.25% p.a.",
            "tenure": "36 to 60 monthly instalments", "security": "Hypothecation of the respective vehicles"},
    "CC": {"lender": "Kalindi Bank Limited", "facility": "Cash credit (fund-based working capital)",
           "sanctioned": 2_200.00, "sanction_date": "14 August 2025 (renewal; enhanced from Rs 1,800 lakhs)",
           "rate": "Repo rate + 4.10% (9.60% p.a. at 30 Sep 2026)", "tenure": "12 months, renewable",
           "security": "First hypothecation charge on current assets (present and future); collateral as for TL-I and TL-II; personal guarantees of Hemant Desai and Kavita Desai"},
    "UNSEC": {"lender": "Hemant Ramniklal Desai (Promoter)", "facility": "Unsecured loan",
              "sanctioned": None, "sanction_date": "Various", "rate": "9.00% p.a.",
              "tenure": "Repayable after 36 months; lender has undertaken not to demand repayment before listing",
              "security": "Unsecured"},
}
NON_FUND = {"bank_guarantee": 45.00, "letter_of_credit": 120.00}

PPE_CLASSES = ["Leasehold land", "Buildings", "Plant and machinery", "Electrical installations",
               "Furniture and fixtures", "Vehicles", "Computers"]
PPE_RATE = {"Leasehold land": 0.0101, "Buildings": 0.0317, "Plant and machinery": 0.0633,
            "Electrical installations": 0.1000, "Furniture and fixtures": 0.0950, "Vehicles": 0.1188,
            "Computers": 0.3167}
PPE_OPEN = {  # Mar22: (gross, accumulated depreciation)
    "Leasehold land": (210.00, 16.78), "Buildings": (1_180.00, 222.60), "Plant and machinery": (3_340.00, 1_075.00),
    "Electrical installations": (310.00, 144.00), "Furniture and fixtures": (34.00, 28.00),
    "Vehicles": (118.00, 38.00), "Computers": (26.00, 22.00)}
PPE_ADD = {
    "FY23": {"Plant and machinery": 300.00, "Furniture and fixtures": 30.00, "Computers": 20.00},
    "FY24": {"Plant and machinery": 360.00, "Computers": 18.00, "Vehicles": 42.00},
    "FY25": {"Plant and machinery": 820.00, "Buildings": 120.00, "Electrical installations": 40.00},
    "FY26": {"Plant and machinery": 480.00, "Buildings": 60.00, "Furniture and fixtures": 20.00,
             "Computers": 25.00, "Vehicles": 25.00},
    "H1FY27": {"Plant and machinery": 190.00, "Electrical installations": 30.00, "Computers": 20.00},
}
PPE_DEL = {"FY25": {"Vehicles": (38.00, 31.20, 9.50)}}   # gross, accumulated, sale proceeds

RESTATEMENT = {"FY24": 14.20}   # gratuity under-provided in audited FY24, recognised in audited FY25

# opening balance sheet, Mar22 (other equity is the balancing figure)
OPEN_BS = {"rm": 540.00, "wip": 110.00, "fg": 170.00, "receivables": 1_520.00, "payables": 985.00,
           "oca": 228.00, "ocl": 182.00}


# ------------------------------------------------------------------ the model -----------------
def _avg(d, p):
    return (d[OPEN[p]] + d[CLOSE[p]]) / 2


def _ppe_schedule():
    sched = {}
    gross = {c: PPE_OPEN[c][0] for c in PPE_CLASSES}
    acc = {c: PPE_OPEN[c][1] for c in PPE_CLASSES}
    for p in PERIODS:
        rows = {}
        for c in PPE_CLASSES:
            add = PPE_ADD.get(p, {}).get(c, 0.0)
            dg, da, proceeds = PPE_DEL.get(p, {}).get(c, (0.0, 0.0, 0.0))
            base = gross[c] + add / 2 - dg / 2
            dep = r2(PPE_RATE[c] * base * FRAC[p])
            cap = 0.95 * (gross[c] + add - dg) - (acc[c] - da)
            dep = r2(max(0.0, min(dep, cap)))
            rows[c] = {"gross_open": r2(gross[c]), "add": r2(add), "del": r2(dg), "gross_close": r2(gross[c] + add - dg),
                       "acc_open": r2(acc[c]), "dep": dep, "acc_del": r2(da), "acc_close": r2(acc[c] + dep - da),
                       "proceeds": proceeds}
            rows[c]["nbv_open"] = r2(rows[c]["gross_open"] - rows[c]["acc_open"])
            rows[c]["nbv_close"] = r2(rows[c]["gross_close"] - rows[c]["acc_close"])
            gross[c] = rows[c]["gross_close"]
            acc[c] = rows[c]["acc_close"]
        sched[p] = rows
    return sched


def _csr(profit: dict, p: str):
    """CSR obligation: 2% of the average net profit of the three preceding years, if the preceding
    year's net profit exceeded Rs 500 lakhs (simplified Section 135 test)."""
    order = ["FY20", "FY21", "FY22", "FY23", "FY24", "FY25", "FY26"]
    if p == "H1FY27":
        prev3 = ["FY24", "FY25", "FY26"]
        if profit["FY26"] <= 500:
            return 0.0, 0.0
        return r2(0.02 * sum(profit[x] for x in prev3) / 3 * 0.5), r2(0.02 * sum(profit[x] for x in prev3) / 3)
    i = order.index(p)
    prev3 = order[i - 3:i]
    if profit[order[i - 1]] <= 500:
        return 0.0, 0.0
    ob = r2(0.02 * sum(profit[x] for x in prev3) / 3)
    return ob, ob


def build() -> dict:
    ppe = _ppe_schedule()
    profit = dict(HIST_PROFIT)
    bs = {"Mar22": {}}
    o = bs["Mar22"]
    o.update(OPEN_BS)
    o["stores"] = STORES["Mar22"]
    pl = {}
    for p in PERIODS:
        op, cl = OPEN[p], CLOSE[p]
        d = DAYS[p]
        x = {}
        x["revenue"] = REV[p]
        x["scrap"] = SCRAP[p]
        x["export_incentive"] = EXPORT_INCENTIVE[p]
        x["sale_of_products"] = r2(REV[p] - SCRAP[p] - EXPORT_INCENTIVE[p])
        x["exports"] = r2(x["sale_of_products"] * OPS["export_share"].get(p, 6.9) / 100)
        x["domestic"] = r2(x["sale_of_products"] - x["exports"])
        x["comc"] = r2(REV[p] * MAT_PCT[p])
        c = bs.setdefault(cl, {})
        c["rm"] = r2(x["comc"] * RM_DAYS[p] / d)
        fgw = r2(REV[p] * FGW_DAYS[p] / d)
        c["wip"] = r2(fgw * 0.4)
        c["fg"] = r2(fgw - c["wip"])
        c["stores"] = STORES[cl]
        x["rm_purchases"] = r2(x["comc"] + c["rm"] - bs[op]["rm"])
        x["inv_change"] = r2((bs[op]["wip"] + bs[op]["fg"]) - (c["wip"] + c["fg"]))
        x["emp"] = r2(REV[p] * EMP_PCT[p])
        x["gratuity_exp"] = r2(GRATUITY[cl] - GRATUITY[op] + GRATUITY_PAID[p])
        csr_spent, csr_ob = _csr(profit, p)
        x["csr"] = csr_spent
        x["csr_obligation"] = csr_ob
        x["oe"] = r2(REV[p] * OE_PCT[p])
        # other expenses, line items (the last one balances)
        f = FRAC[p]
        oe = {
            "Power and fuel": r2(REV[p] * 0.0412),
            "Consumption of stores and spares": r2(REV[p] * 0.0091),
            "Freight and forwarding (outward)": r2(REV[p] * 0.0262),
            "Job work and printing cylinder charges": r2(REV[p] * 0.0121),
            "Packing materials consumed": r2(REV[p] * 0.0089),
            "Repairs and maintenance - plant and machinery": r2(REV[p] * 0.0055),
            "Repairs and maintenance - building": r2(REV[p] * 0.0012),
            "Repairs and maintenance - others": r2(REV[p] * 0.0010),
            "Rent": r2((15.00 + 3.60) * f),
            "Rates and taxes": r2(REV[p] * 0.0008),
            "Insurance": r2(REV[p] * 0.0016),
            "Travelling and conveyance": r2(REV[p] * 0.0019),
            "Legal and professional fees": r2(REV[p] * 0.0017),
            "Payment to auditors": r2({"FY23": 5.00, "FY24": 5.50, "FY25": 6.00, "FY26": 7.25, "H1FY27": 4.00}[p]),
            "Sales promotion and commission": r2(REV[p] * 0.0024),
            "Corporate social responsibility expenditure": csr_spent,
            "Sitting fees to independent directors": r2(1.20 if p == "H1FY27" else 0.0),
        }
        oe["Miscellaneous expenses"] = r2(x["oe"] - sum(oe.values()))
        assert oe["Miscellaneous expenses"] > 0, (p, oe["Miscellaneous expenses"])
        x["oe_detail"] = oe
        x["ebitda"] = r2(REV[p] - x["comc"] - x["inv_change"] - x["emp"] - x["oe"])
        x["dep"] = r2(sum(ppe[p][k]["dep"] for k in PPE_CLASSES))
        # finance cost
        intr = {k: r2(_avg(BORROW[k], p) * RATES[k] * FRAC[p]) for k in BORROW}
        x["interest"] = intr
        x["bank_charges"] = BANK_CHARGES[p]
        x["fin"] = r2(sum(intr.values()) + BANK_CHARGES[p])
        # other income
        fd_int = r2(_avg(FD_LIEN, p) * 0.0675 * FRAC[p])
        profit_sale = r2(sum(v[2] - (v[0] - v[1]) for v in PPE_DEL.get(p, {}).values()))
        x["oi_detail"] = {"Interest on fixed deposits": fd_int, "Profit on sale of property, plant and equipment": profit_sale,
                          "Foreign exchange gain (net)": r2(x["exports"] * 0.0038),
                          "Interest on security deposits and income-tax refund": r2(1.10 * FRAC[p])}
        x["oi_detail"]["Miscellaneous income"] = r2(OTHER_INCOME[p] - sum(x["oi_detail"].values()))
        assert x["oi_detail"]["Miscellaneous income"] >= 0, p
        x["oi"] = OTHER_INCOME[p]
        x["fd_interest"] = fd_int
        x["profit_on_sale"] = profit_sale
        x["pbt"] = r2(x["ebitda"] + x["oi"] - x["dep"] - x["fin"])
        if p != "H1FY27":
            profit[p] = x["pbt"]
        x["tax_total"] = r2((x["pbt"] + x["csr"]) * TAX_RATE)
        x["tax_deferred"] = r2(x["dep"] * 0.12 * TAX_RATE - (GRATUITY[cl] - GRATUITY[op]) * TAX_RATE)
        x["tax_current"] = r2(x["tax_total"] - x["tax_deferred"])
        x["pat"] = r2(x["pbt"] - x["tax_total"])
        pl[p] = x

        # balance sheet at close
        c["receivables"] = r2(REV[p] * DEBTOR_DAYS[p] / d)
        c["payables"] = r2((x["rm_purchases"] + x["oe"]) * CREDITOR_DAYS[p] / d)
        c["oca"] = r2(REV[p] / FRAC[p] * OCA_PCT)
        c["ocl"] = r2(REV[p] / FRAC[p] * OCL_PCT)
    # assemble balance sheets
    for k in ["Mar22"] + [CLOSE[p] for p in PERIODS]:
        b = bs[k]
        b["_key"] = k
        b["ppe_gross"] = r2(sum((PPE_OPEN[c][0] if k == "Mar22" else ppe[_period_closing(k)][c]["gross_close"]) for c in PPE_CLASSES))
        b["ppe_acc"] = r2(sum((PPE_OPEN[c][1] if k == "Mar22" else ppe[_period_closing(k)][c]["acc_close"]) for c in PPE_CLASSES))
        b["ppe_net"] = r2(b["ppe_gross"] - b["ppe_acc"])
        b["cwip"] = CWIP[k]
        b["cap_adv"] = CAP_ADV[k]
        b["deposits"] = DEPOSITS[k]
        b["inventories"] = r2(b["rm"] + b["wip"] + b["fg"] + b["stores"])
        for name in BORROW:
            b["b_" + name] = BORROW[name][k]
        b["cur_mat"] = r2(sum(CUR_MAT[n][k] for n in CUR_MAT))
        b["lt_borrowings"] = r2(sum(BORROW[n][k] for n in ("TL0", "TL1", "VEH", "UNSEC")) - b["cur_mat"])
        b["st_borrowings"] = r2(BORROW["CC"][k] + b["cur_mat"])
        b["gratuity_nc"] = r2(GRATUITY[k] * 0.9)
        b["gratuity_c"] = r2(GRATUITY[k] - b["gratuity_nc"])
        b["tax_liab"] = TAX_LIAB[k]
        b["fd_lien"] = FD_LIEN[k]
        b["cash_on_hand"] = CASH_ON_HAND[k]
    # equity and deferred tax roll-forward; cash is the balancing item
    sc = {"Mar22": OPEN_SC}
    dtl = {"Mar22": OPEN_DTL}
    sp = {"Mar22": 600.00}
    for p in PERIODS:
        op, cl = OPEN[p], CLOSE[p]
        dtl[cl] = r2(dtl[op] + pl[p]["tax_deferred"])
        if p == "H1FY27":
            sc[cl] = r2(sc[op] + 800.00)
            sp[cl] = 0.00
        else:
            sc[cl] = sc[op]
            sp[cl] = sp[op]
    oe_open = None
    for k in ["Mar22"] + [CLOSE[p] for p in PERIODS]:
        b = bs[k]
        b["share_capital"] = sc[k]
        b["dtl"] = dtl[k]
        b["securities_premium"] = sp[k]
    # Mar22: fix cash, derive other equity
    b = bs["Mar22"]
    b["cash_total"] = 165.30
    b["other_equity"] = r2(_assets(b) - _liabs_ex_equity(b) - b["share_capital"])
    oe_open = b["other_equity"]
    oe = {"Mar22": oe_open}
    for p in PERIODS:
        op, cl = OPEN[p], CLOSE[p]
        oe[cl] = r2(oe[op] + pl[p]["pat"] - (800.00 if p == "H1FY27" else 0.0))
        b = bs[cl]
        b["other_equity"] = oe[cl]
        b["cash_total"] = r2(b["share_capital"] + b["other_equity"] + _liabs_ex_equity(b) - _assets_ex_cash(b))
    for k, b in bs.items():
        b["retained_earnings"] = r2(b["other_equity"] - b["securities_premium"])
        b["net_worth"] = r2(b["share_capital"] + b["other_equity"])
        b["bank_balance"] = r2(b["cash_total"] - b["fd_lien"] - b["cash_on_hand"])
        b["total_assets"] = r2(_assets(b))
        b["total_liabilities"] = r2(b["net_worth"] + _liabs_ex_equity(b))
        b["total_debt"] = r2(b["lt_borrowings"] + b["st_borrowings"])
    cf = {p: _cash_flow(pl[p], bs[OPEN[p]], bs[CLOSE[p]], ppe[p], p) for p in PERIODS}
    data = {"company": COMPANY, "promoters": PROMOTERS, "directors": DIRECTORS, "kmp": KMP,
            "remuneration": REMUNERATION, "advisers": ADVISERS, "allotments": ALLOTMENTS,
            "authorised_capital": AUTHORISED_CAPITAL, "shareholders": SHAREHOLDERS, "sh_category": SH_CATEGORY,
            "offer": OFFER, "objects": OBJECTS, "funds_deployed": FUNDS_DEPLOYED, "machinery": MACHINERY,
            "solar": SOLAR, "ops": OPS, "loans": LOANS, "non_fund": NON_FUND,
            "pl": pl, "bs": bs, "cf": cf, "ppe": ppe, "profit_history": profit}
    data["holdings"] = holdings()
    data["ratios"] = {p: ratios(data, p) for p in PERIODS}
    data["restatement"] = restatement_effects(data)
    data["audited"] = {p: audited(data, p) for p in ["FY24", "FY25", "FY26"]}
    data["materiality"] = materiality(data)
    data["rpt"] = related_parties(data)
    data["contingent"] = contingent_liabilities()
    data["litigation"] = litigation()
    data["licences"] = licences()
    data["group_companies"] = group_companies()
    data["working_capital"] = working_capital(data)
    data["kpi"] = kpis(data)
    data["insurance"] = insurance()
    data["ip"] = intellectual_property()
    data["properties"] = properties()
    return data


def _period_closing(k):
    for p, c in CLOSE.items():
        if c == k:
            return p
    raise KeyError(k)


def _assets_ex_cash(b):
    return (b["ppe_net"] + b["cwip"] + b["cap_adv"] + b["deposits"] + b["inventories"] + b["receivables"] + b["oca"])


def _assets(b):
    return _assets_ex_cash(b) + b["cash_total"]


def _liabs_ex_equity(b):
    return (b["lt_borrowings"] + b["st_borrowings"] + b["dtl"] + b["gratuity_nc"] + b["gratuity_c"] + b["payables"]
            + b["ocl"] + b["tax_liab"])


def _cash_flow(x, o, c, ppe_p, p):
    cf = {}
    cf["pbt"] = x["pbt"]
    cf["dep"] = x["dep"]
    cf["fin"] = x["fin"]
    cf["interest_income"] = -x["fd_interest"]
    cf["profit_on_sale"] = -x["profit_on_sale"]
    cf["op_before_wc"] = r2(sum(cf.values()))
    cf["d_inventories"] = r2(o["inventories"] - c["inventories"])
    cf["d_receivables"] = r2(o["receivables"] - c["receivables"])
    cf["d_oca"] = r2((o["oca"] + o["deposits"]) - (c["oca"] + c["deposits"]))
    cf["d_payables"] = r2(c["payables"] - o["payables"])
    cf["d_ocl"] = r2(c["ocl"] - o["ocl"])
    cf["d_provisions"] = r2((c["gratuity_nc"] + c["gratuity_c"]) - (o["gratuity_nc"] + o["gratuity_c"]))
    cf["cash_generated"] = r2(cf["op_before_wc"] + cf["d_inventories"] + cf["d_receivables"] + cf["d_oca"]
                              + cf["d_payables"] + cf["d_ocl"] + cf["d_provisions"])
    cf["tax_paid"] = -r2(x["tax_current"] - (c["tax_liab"] - o["tax_liab"]))
    cf["cfo"] = r2(cf["cash_generated"] + cf["tax_paid"])
    adds = sum(v["add"] for v in ppe_p.values())
    cf["capex"] = -r2(adds + (c["cwip"] - o["cwip"]) + (c["cap_adv"] - o["cap_adv"]))
    cf["sale_proceeds"] = r2(sum(v["proceeds"] for v in ppe_p.values()))
    cf["interest_received"] = x["fd_interest"]
    cf["d_fd_lien"] = r2(o["fd_lien"] - c["fd_lien"])
    cf["cfi"] = r2(cf["capex"] + cf["sale_proceeds"] + cf["interest_received"] + cf["d_fd_lien"])
    lt_o = o["b_TL0"] + o["b_TL1"] + o["b_VEH"]
    lt_c = c["b_TL0"] + c["b_TL1"] + c["b_VEH"]
    cf["lt_proceeds"] = r2(max(0.0, lt_c - lt_o + _lt_repaid(o, c)))
    cf["lt_repaid"] = -r2(_lt_repaid(o, c))
    cf["d_cc"] = r2(c["b_CC"] - o["b_CC"])
    cf["d_unsec"] = r2(c["b_UNSEC"] - o["b_UNSEC"])
    cf["fin_paid"] = -x["fin"]
    cf["cff"] = r2(cf["lt_proceeds"] + cf["lt_repaid"] + cf["d_cc"] + cf["d_unsec"] + cf["fin_paid"])
    cf["net_change"] = r2(cf["cfo"] + cf["cfi"] + cf["cff"])
    cf["cash_open"] = r2(o["cash_total"] - o["fd_lien"])
    cf["cash_close"] = r2(c["cash_total"] - c["fd_lien"])
    return cf


def _lt_repaid(o, c):
    """Scheduled repayments of term and vehicle loans (new vehicle loans are the residual)."""
    rep = (o["b_TL0"] - c["b_TL0"])
    if c["b_TL1"] > 0 and o["b_TL1"] > 0:
        rep += o["b_TL1"] - c["b_TL1"]
    elif c["b_TL1"] > 0:
        rep += 720.00 - c["b_TL1"]
    veh_new = {"Mar24": 42.00, "Mar26": 20.00}.get(_close_key(c), 0.0)
    rep += o["b_VEH"] + veh_new - c["b_VEH"]
    return rep


def _close_key(b):
    return b.get("_key")


def holdings():
    """Pre-bonus holdings, post-bonus (pre-issue) holdings, and the cost of acquisition per holder."""
    pre = {}
    cost = {}
    for a in ALLOTMENTS:
        if a["allottees"] == "BONUS":
            continue
        for k, v in a["allottees"].items():
            pre[k] = pre.get(k, 0) + v
            cost[k] = cost.get(k, 0.0) + v * a["price"]
    post = {k: v * (1 + BONUS_RATIO) for k, v in pre.items()}
    assert sum(pre.values()) == SHARES_PRE_BONUS and sum(post.values()) == SHARES_PRE_ISSUE
    avg = {k: round(cost[k] / post[k], 2) for k in post}
    return {"pre_bonus": pre, "pre_issue": post, "avg_cost": avg,
            "pct_pre_issue": {k: round(100 * v / SHARES_PRE_ISSUE, 2) for k, v in post.items()}}


def ratios(d, p):
    x, b, o = d["pl"][p], d["bs"][CLOSE[p]], d["bs"][OPEN[p]]
    ann = 1 / FRAC[p]
    avg_nw = (b["net_worth"] + o["net_worth"]) / 2
    cur_assets = b["inventories"] + b["receivables"] + b["oca"] + b["cash_total"]
    cur_liabs = b["st_borrowings"] + b["payables"] + b["ocl"] + b["tax_liab"] + b["gratuity_c"]
    cap_employed = b["net_worth"] + b["total_debt"] + b["dtl"]
    debt_service = x["fin"] + _scheduled_principal(d, p)
    r = {
        "current_ratio": round(cur_assets / cur_liabs, 2),
        "debt_equity": round(b["total_debt"] / b["net_worth"], 2),
        "dscr": round((x["pat"] + x["dep"] + x["fin"]) / debt_service, 2),
        "roe_pct": round(100 * x["pat"] / avg_nw, 2),
        "inventory_turnover": round((x["comc"] + x["inv_change"]) / ((b["inventories"] + o["inventories"]) / 2), 2),
        "receivables_turnover": round(x["revenue"] / ((b["receivables"] + o["receivables"]) / 2), 2),
        "payables_turnover": round((x["rm_purchases"] + x["oe"]) / ((b["payables"] + o["payables"]) / 2), 2),
        "net_capital_turnover": round(x["revenue"] / (cur_assets - cur_liabs), 2),
        "net_profit_pct": round(100 * x["pat"] / x["revenue"], 2),
        "roce_pct": round(100 * (x["pbt"] + x["fin"]) / cap_employed, 2),
        "ebitda_margin_pct": round(100 * x["ebitda"] / x["revenue"], 2),
        "eps": round(x["pat"] * 1e5 / SHARES_PRE_ISSUE, 2),
        "nav_per_share": round(b["net_worth"] * 1e5 / SHARES_PRE_ISSUE, 2),
        "ronw_pct": round(100 * x["pat"] / b["net_worth"], 2),
        "net_debt": r2(b["total_debt"] - b["cash_total"]),
        "not_annualised": FRAC[p] != 1.0,
    }
    r["net_debt_ebitda"] = round(r["net_debt"] / (x["ebitda"] * ann), 2)
    return r


def _scheduled_principal(d, p):
    o, c = d["bs"][OPEN[p]], d["bs"][CLOSE[p]]
    return max(0.0, (o["b_TL0"] - c["b_TL0"]) + max(0.0, o["b_TL1"] - c["b_TL1"]) + max(0.0, o["b_VEH"] - c["b_VEH"]))


def restatement_effects(d):
    adj = RESTATEMENT["FY24"]
    tax = r2(adj * TAX_RATE)
    return {"FY24": {"gratuity": -adj, "deferred_tax": tax, "pat": -r2(adj - tax)},
            "FY25": {"gratuity": adj, "deferred_tax": -tax, "pat": r2(adj - tax)},
            "FY26": {"gratuity": 0.0, "deferred_tax": 0.0, "pat": 0.0},
            "H1FY27": {"gratuity": 0.0, "deferred_tax": 0.0, "pat": 0.0},
            "note": ("Gratuity liability for FY 2023-24 was not actuarially valued in the audited financial "
                     "statements; the shortfall of Rs 14.20 lakhs was recognised in FY 2024-25. In the restated "
                     "financial information it is recognised in FY 2023-24, the year to which it relates, with the "
                     "related deferred tax.")}


def audited(d, p):
    """Audited figures differ from restated only through the FY24 gratuity adjustment."""
    pl = copy.deepcopy(d["pl"][p])
    bs_close = copy.deepcopy(d["bs"][CLOSE[p]])
    adj = RESTATEMENT["FY24"]
    tax = r2(adj * TAX_RATE)
    if p == "FY24":
        pl["emp"] = r2(pl["emp"] - adj)
        pl["gratuity_exp"] = r2(pl["gratuity_exp"] - adj)
        pl["tax_deferred"] = r2(pl["tax_deferred"] + tax)
        bs_close["gratuity_nc"] = r2(bs_close["gratuity_nc"] - adj)
        bs_close["dtl"] = r2(bs_close["dtl"] + tax)
        bs_close["other_equity"] = r2(bs_close["other_equity"] + adj - tax)
    elif p == "FY25":
        pl["emp"] = r2(pl["emp"] + adj)
        pl["gratuity_exp"] = r2(pl["gratuity_exp"] + adj)
        pl["tax_deferred"] = r2(pl["tax_deferred"] - tax)
    else:
        return {"pl": pl, "bs": bs_close}
    pl["ebitda"] = r2(pl["revenue"] - pl["comc"] - pl["inv_change"] - pl["emp"] - pl["oe"])
    pl["pbt"] = r2(pl["ebitda"] + pl["oi"] - pl["dep"] - pl["fin"])
    pl["tax_total"] = r2(pl["tax_current"] + pl["tax_deferred"])
    pl["pat"] = r2(pl["pbt"] - pl["tax_total"])
    for k in ("retained_earnings", "net_worth", "total_liabilities"):
        pass
    bs_close["retained_earnings"] = r2(bs_close["other_equity"] - bs_close["securities_premium"])
    bs_close["net_worth"] = r2(bs_close["share_capital"] + bs_close["other_equity"])
    bs_close["total_liabilities"] = r2(bs_close["net_worth"] + _liabs_ex_equity(bs_close))
    return {"pl": pl, "bs": bs_close}


def materiality(d):
    turnover = d["pl"]["FY26"]["revenue"]
    nw = d["bs"]["Mar26"]["net_worth"]
    avg_pat = sum(abs(d["pl"][p]["pat"]) for p in ("FY24", "FY25", "FY26")) / 3
    t = {"2% of turnover (FY 2025-26)": r2(0.02 * turnover), "2% of net worth (31 March 2026)": r2(0.02 * nw),
         "5% of average absolute PAT (last three financial years)": r2(0.05 * avg_pat)}
    pay = d["bs"]["Sep26"]["payables"]
    return {"litigation_thresholds": t, "litigation_threshold": min(t.values()),
            "policy_adopted": "28 August 2026",
            "creditor_threshold_pct": 5.0, "creditor_threshold": r2(0.05 * pay), "trade_payables_sep26": pay}


def related_parties(d):
    pl = d["pl"]
    rp = {
        "parties": [
            ("Hemant Ramniklal Desai", "Key managerial personnel (Chairman and Managing Director); Promoter"),
            ("Kavita Hemant Desai", "Key managerial personnel (Whole-time Director); Promoter"),
            ("Parth Hemant Desai", "Whole-time Director; Promoter Group (son of Promoters)"),
            ("Sanjay Prakash Khatri", "Key managerial personnel (Chief Financial Officer)"),
            ("Nidhi Rajesh Purohit", "Key managerial personnel (Company Secretary), from 15 July 2026"),
            ("Hemant Ramniklal Desai HUF", "Promoter Group (HUF of Promoter)"),
            ("Desai Polymers LLP", "Entity in which KMP and relatives are partners (Group Company)"),
            ("Ashtavira Packaging Solutions Private Limited", "Entity in which KMP are directors (Group Company)"),
        ],
        "transactions": {},
    }
    t = rp["transactions"]
    for name, vals in REMUNERATION.items():
        t[("Remuneration", name)] = vals
    t[("Rent paid", "Kavita Hemant Desai")] = {p: r2(15.00 * FRAC[p]) for p in PERIODS}
    t[("Purchase of polymer granules and films", "Desai Polymers LLP")] = {
        "FY23": 366.10, "FY24": 412.30, "FY25": 498.75, "FY26": 560.20, "H1FY27": 301.15}
    t[("Interest on unsecured loan", "Hemant Ramniklal Desai")] = {p: pl[p]["interest"]["UNSEC"] for p in PERIODS}
    t[("Unsecured loan taken / (repaid), net", "Hemant Ramniklal Desai")] = {
        p: r2(BORROW["UNSEC"][CLOSE[p]] - BORROW["UNSEC"][OPEN[p]]) for p in PERIODS}
    t[("Sitting fees", "Independent directors")] = {p: (1.20 if p == "H1FY27" else 0.0) for p in PERIODS}
    rp["balances"] = {
        ("Unsecured loan payable", "Hemant Ramniklal Desai"): {k: BORROW["UNSEC"][k] for k in BORROW["UNSEC"]},
        ("Trade payable", "Desai Polymers LLP"): {"Mar23": 41.80, "Mar24": 48.25, "Mar25": 57.10, "Mar26": 63.40, "Sep26": 70.85},
        ("Remuneration payable", "Directors and KMP"): {"Mar23": 6.20, "Mar24": 7.85, "Mar25": 8.90, "Mar26": 9.95, "Sep26": 12.40},
        ("Rent deposit receivable", "Kavita Hemant Desai"): {"Mar23": 5.00, "Mar24": 5.00, "Mar25": 5.00, "Mar26": 5.00, "Sep26": 5.00},
    }
    return rp


def contingent_liabilities():
    return {
        "Bank guarantees issued on behalf of the Company (to Gujarat Pollution Control Board and DGVCL)": {
            "Mar24": 35.00, "Mar25": 35.00, "Mar26": 45.00, "Sep26": 45.00},
        "Letters of credit outstanding": {"Mar24": 64.20, "Mar25": 88.50, "Mar26": 102.75, "Sep26": 118.40},
        "Goods and Services Tax demand for FY 2021-22 under appeal (excluding interest and penalty)": {
            "Mar24": 0.00, "Mar25": 0.00, "Mar26": 18.62, "Sep26": 18.62},
        "Income-tax demand for AY 2024-25 under rectification": {"Mar24": 0.00, "Mar25": 0.00, "Mar26": 6.21, "Sep26": 6.21},
        "Export obligation under EPCG licence (duty saved)": {"Mar24": 21.40, "Mar25": 46.85, "Mar26": 46.85, "Sep26": 38.10},
    }


def litigation():
    return {
        "company": {
            "criminal_by": [
                {"case": "Criminal Case No. 4518 of 2025", "forum": "Chief Judicial Magistrate, Ahmedabad (Rural), Mirzapur",
                 "parties": "Ashtavira Flexipak Private Limited v. Shreeji Snacks and Namkeen (proprietor Mr. Bhavesh Patel)",
                 "law": "Section 138 read with Section 141 of the Negotiable Instruments Act, 1881",
                 "amount": 23.86, "filed": "21 May 2025",
                 "facts": "Four cheques issued towards supply of printed laminates were dishonoured for 'funds insufficient'. "
                          "Statutory notice dated 3 April 2025 was not complied with.",
                 "status": "Pending; next hearing 19 November 2026 for recording of complainant's evidence."}],
            "criminal_against": [],
            "regulatory": [
                {"case": "Show-cause notice No. GPCB/AHD-R/2025/1147 dated 11 March 2025",
                 "forum": "Gujarat Pollution Control Board, Regional Office, Ahmedabad (Rural)",
                 "facts": "Stack monitoring on 18 February 2025 recorded volatile organic compound emissions above the consented "
                          "limit at the solvent-based laminator. The Company replied on 27 March 2025, installed an activated-"
                          "carbon adsorption unit (commissioned 30 June 2025) and submitted fresh monitoring results.",
                 "amount": None, "status": "Pending; no closure communication received as on the date of this certificate."}],
            "tax_direct": [
                {"case": "Intimation under Section 143(1)(a) of the Income-tax Act, 1961 for AY 2024-25", "amount": 6.21,
                 "facts": "Disallowance of employer's contribution to provident fund deposited after the due date and a TDS credit mismatch.",
                 "status": "Rectification application under Section 154 filed on 9 January 2026; pending."}],
            "tax_indirect": [
                {"case": "Order-in-original No. ZA2402260198765 under Section 73 of the CGST Act, 2017 for FY 2021-22",
                 "amount": 18.62, "facts": "Input tax credit availed in GSTR-3B in excess of GSTR-2A; demand of Rs 18.62 lakhs "
                 "plus applicable interest and penalty of Rs 1.86 lakhs.",
                 "status": "Appeal filed before the Joint Commissioner (Appeals), Ahmedabad on 12 May 2026 with pre-deposit of Rs 1.86 lakhs; pending."}],
            "civil_against": [
                {"case": "Commercial Civil Suit No. 211 of 2026", "forum": "Commercial Court, Ahmedabad (Rural)",
                 "parties": "Precision Inks and Coatings v. Ashtavira Flexipak Private Limited",
                 "amount": 12.40, "facts": "Recovery of Rs 12.40 lakhs claimed as dues for printing inks supplied in 2024; "
                 "the Company disputes the claim on account of rejected batches.",
                 "status": "Pending; written statement filed 2 August 2026."}],
            "civil_by": [],
        },
        "promoters": {
            "Hemant Ramniklal Desai": {"tax_direct": [{"case": "Intimation under Section 143(1)(a) for AY 2023-24",
                                                         "amount": 2.14, "status": "Response filed; pending."}]},
            "Kavita Hemant Desai": {},
        },
        "directors": {},
        "group_companies": {
            "Desai Polymers LLP": {"tax_indirect": [{"case": "Show-cause notice under Section 73 of the CGST Act for FY 2022-23",
                                                     "amount": 3.85, "status": "Reply filed 14 July 2026; pending."}]}},
        "creditors_sep26": {"msme": {"count": 47, "amount": None}, "material": {"count": 3, "amount": None},
                            "others": {"count": 168, "amount": None}},
        "sebi_actions": "None",
        "wilful_defaulter": "None of the Company, its Promoters or Directors is identified as a wilful defaulter or fraudulent borrower.",
    }


def licences():
    return [
        ("Certificate of Incorporation", "Registrar of Companies, Gujarat", "U22220GJ2012PTC071846", "14 August 2012", "Perpetual", "Valid"),
        ("Fresh Certificate of Incorporation on conversion to public company", "Registrar of Companies, Gujarat (Central Processing Centre)", "U22220GJ2012PLC071846", "2 July 2026", "Perpetual", "Valid"),
        ("GST registration (Gujarat)", "Goods and Services Tax Network", "24AAKCA4718M1Z6", "1 July 2017", "Until cancelled", "Valid"),
        ("Importer-Exporter Code", "Directorate General of Foreign Trade", "0812018734", "9 October 2012", "Until cancelled (annual update done 18 April 2026)", "Valid"),
        ("Udyam registration (medium enterprise)", "Ministry of MSME", "UDYAM-GJ-01-0047218", "22 September 2020", "Until cancelled", "Valid"),
        ("Factory licence", "Directorate of Industrial Safety and Health, Gujarat", "AHD/R/25418/2014", "3 January 2014", "31 December 2026", "Valid; renewal to be applied in December 2026"),
        ("Consolidated Consent and Authorisation (CC&A) under Water Act, Air Act and Hazardous Waste Rules", "Gujarat Pollution Control Board", "AWH-118274", "16 March 2022", "15 March 2027", "Valid"),
        ("Fire safety certificate (NOC)", "Chief Fire Officer, Sanand Nagarpalika / GIDC fire station", "FSC/SND/2023/0816", "21 September 2023", "20 September 2026", "Expired; renewal applied 20 September 2026 (application FSC/REN/26/4471), pending"),
        ("Registration under the Contract Labour (R&A) Act, 1970", "Office of the Deputy Commissioner of Labour, Ahmedabad", "CLRA/AHD/2016/1127", "11 May 2016", "Until amended", "Valid"),
        ("Employees' Provident Fund registration", "Employees' Provident Fund Organisation", "GJAHD1574192000", "1 March 2013", "Until cancelled", "Valid"),
        ("Employees' State Insurance registration", "Employees' State Insurance Corporation", "37000741820001099", "1 March 2013", "Until cancelled", "Valid"),
        ("Professional tax registration (employer)", "Sanand Nagarpalika", "PEC/SND/0024719", "4 April 2013", "Until cancelled", "Valid"),
        ("Legal Metrology registration as packer (packaged commodities)", "Controller of Legal Metrology, Gujarat", "LM/GJ/PKR/2019/1882", "6 June 2019", "Until cancelled", "Valid"),
        ("EPR registration as brand owner/producer of plastic packaging", "Central Pollution Control Board (EPR portal)", "PWP-GJ-ID-24-7731", "12 February 2024", "31 March 2027", "Valid"),
        ("EPCG authorisation (zero duty) for solventless laminator", "Directorate General of Foreign Trade, Ahmedabad", "0830017442", "8 July 2024", "Export obligation period till 7 July 2030", "Valid"),
        ("Electricity connection, HT (1,650 kVA)", "Uttar Gujarat Vij Company Limited / DGVCL", "HT-SND-02281", "14 January 2014 (load enhanced 9 May 2024)", "Until disconnected", "Valid"),
        ("Legal Entity Identifier (LEI)", "Legal Entity Identifier India Limited", "-", "-", "-", "Not yet obtained; to be applied before the Offer"),
    ]


def group_companies():
    return {
        "Desai Polymers LLP": {"llpin": "AAB-7316", "incorporated": "2 February 2016",
                               "office": "Shed No. 22, Phase-I, GIDC Vatva, Ahmedabad - 382 445",
                               "business": "Trading of polyolefin granules, BOPP and PET films",
                               "partners": "Hemant Ramniklal Desai (60%), Parth Hemant Desai (40%)",
                               "financials": {"FY24": {"turnover": 1_284.60, "pat": 21.45, "net_worth": 312.80},
                                              "FY25": {"turnover": 1_402.15, "pat": 24.10, "net_worth": 336.90},
                                              "FY26": {"turnover": 1_538.70, "pat": 27.85, "net_worth": 364.75}},
                               "conflict": "Supplies raw materials to the Company; transactions are at arm's length and approved by the Audit Committee."},
        "Ashtavira Packaging Solutions Private Limited": {"cin": "U74999GJ2019PTC109342", "incorporated": "11 July 2019",
                               "office": "Plot No. 214, GIDC Industrial Estate, Sanand-II, Ahmedabad - 382 110",
                               "business": "Incorporated to provide packaging design services; has not commenced business",
                               "directors": "Hemant Ramniklal Desai, Kavita Hemant Desai",
                               "financials": {"FY24": {"turnover": 0.00, "pat": -0.42, "net_worth": 0.58},
                                              "FY25": {"turnover": 0.00, "pat": -0.38, "net_worth": 0.20},
                                              "FY26": {"turnover": 0.00, "pat": -0.35, "net_worth": -0.15}},
                               "conflict": "None; the Board proposes to strike off the company after the Offer."},
    }


def working_capital(d):
    """Working capital assessment certified by the statutory auditor: actuals and estimates."""
    rows, holding = {}, {"Inventories (days of cost of goods sold)": {}, "Trade receivables (days of revenue)": {},
                         "Trade payables (days of purchases and expenses)": {}}
    for p, k in (("FY24", "Mar24"), ("FY25", "Mar25"), ("FY26", "Mar26")):
        b, x = d["bs"][k], d["pl"][p]
        ca = {"Inventories": b["inventories"], "Trade receivables": b["receivables"],
              "Other current assets": b["oca"], "Cash and bank balances": b["cash_total"]}
        cl = {"Trade payables": b["payables"], "Other current liabilities and provisions": r2(b["ocl"] + b["gratuity_c"] + b["tax_liab"])}
        rows[p] = {"revenue": x["revenue"], "ca": ca, "cl": cl}
        cogs = x["comc"] + x["inv_change"]
        holding["Inventories (days of cost of goods sold)"][p] = round(b["inventories"] / cogs * DAYS[p])
        holding["Trade receivables (days of revenue)"][p] = round(b["receivables"] / x["revenue"] * DAYS[p])
        holding["Trade payables (days of purchases and expenses)"][p] = round(b["payables"] / (x["rm_purchases"] + x["oe"]) * DAYS[p])
    est = {"FY27E": {"revenue": 14_920.00, "inv": 62, "rec": 84, "pay": 48},
           "FY28E": {"revenue": 18_150.00, "inv": 62, "rec": 84, "pay": 40}}
    for k, e in est.items():
        rev = e["revenue"]
        cogs = rev * 0.684
        purch = rev * (0.684 + 0.127)
        ca = {"Inventories": r2(cogs * e["inv"] / 365), "Trade receivables": r2(rev * e["rec"] / 365),
              "Other current assets": r2(rev * 0.031), "Cash and bank balances": r2(rev * 0.016)}
        cl = {"Trade payables": r2(purch * e["pay"] / 365), "Other current liabilities and provisions": r2(rev * 0.026)}
        rows[k] = {"revenue": rev, "ca": ca, "cl": cl}
        holding["Inventories (days of cost of goods sold)"][k] = e["inv"]
        holding["Trade receivables (days of revenue)"][k] = e["rec"]
        holding["Trade payables (days of purchases and expenses)"][k] = e["pay"]
    for k, v in rows.items():
        v["gross_ca"] = r2(sum(v["ca"].values()))
        v["total_cl"] = r2(sum(v["cl"].values()))
        v["wc_gap"] = r2(v["gross_ca"] - v["total_cl"])
    for p, k in (("FY24", "Mar24"), ("FY25", "Mar25"), ("FY26", "Mar26")):
        cc = BORROW["CC"][k]
        rows[p]["funding"] = {"Borrowings (cash credit)": cc, "Issue proceeds": 0.00,
                              "Internal accruals / net worth": r2(rows[p]["wc_gap"] - cc)}
    rows["FY27E"]["funding"] = {"Borrowings (cash credit)": 2_200.00, "Issue proceeds": 0.00,
                                "Internal accruals / net worth": r2(rows["FY27E"]["wc_gap"] - 2_200.00)}
    rows["FY28E"]["funding"] = {"Borrowings (cash credit)": 2_200.00, "Issue proceeds": 1_450.00,
                                "Internal accruals / net worth": r2(rows["FY28E"]["wc_gap"] - 2_200.00 - 1_450.00)}
    for v in rows.values():
        assert v["funding"]["Internal accruals / net worth"] > 0, v
    return {"rows": rows, "holding": holding,
            "justification": [
                "Trade payable days are reduced from 48 to 40 in FY 2027-28 because the Company intends to avail "
                "early-payment discounts of 1.0% to 1.5% from BOPP and PET film suppliers once Issue proceeds are available.",
                "Inventory holding is maintained at about 62 days of cost of goods sold to support the additional "
                "10-colour printing capacity and the larger share of multi-SKU pouch orders.",
                "Receivable holding is assumed at 84 days of revenue, in line with the six months ended 30 September 2026."]}


def kpis(d):
    out = {}
    for p in RESTATED_PERIODS:
        x, r = d["pl"][p], d["ratios"][p]
        prev = {"FY24": "FY23", "FY25": "FY24", "FY26": "FY25"}.get(p)
        g = round(100 * (x["revenue"] / d["pl"][prev]["revenue"] - 1), 2) if prev else None
        out[p] = {"Revenue from operations (Rs lakhs)": x["revenue"], "Growth in revenue from operations (%)": g,
                  "EBITDA (Rs lakhs)": x["ebitda"], "EBITDA margin (%)": r["ebitda_margin_pct"],
                  "Profit after tax (Rs lakhs)": x["pat"], "PAT margin (%)": r["net_profit_pct"],
                  "Return on net worth (%)": r["ronw_pct"], "Return on capital employed (%)": r["roce_pct"],
                  "Debt-equity ratio (times)": r["debt_equity"], "Net debt / EBITDA (times)": r["net_debt_ebitda"],
                  "Net asset value per share (Rs)": r["nav_per_share"], "Basic and diluted EPS (Rs)": r["eps"],
                  "Capacity utilisation - lamination (%)": round(100 * OPS["production_mt"][p] / OPS["capacity_mtpa"][p], 2),
                  "Number of customers served": OPS["customers"][p],
                  "Revenue from top 10 customers (%)": OPS["top10"][p],
                  "Export share of sale of products (%)": OPS["export_share"][p]}
    return out


def insurance():
    return [
        ("Standard fire and special perils (building, plant and machinery, stocks)", "Abhayam General Insurance Limited (synthetic)",
         "AGI/SFSP/26/118842", 7_850.00, "18 April 2027"),
        ("Burglary and housebreaking (stocks and movables)", "Abhayam General Insurance Limited (synthetic)", "AGI/BUR/26/031177", 2_400.00, "18 April 2027"),
        ("Marine cargo open policy (inland and export transit)", "Abhayam General Insurance Limited (synthetic)", "AGI/MOP/26/007421", 1_500.00, "31 March 2027"),
        ("Group mediclaim (employees)", "Abhayam General Insurance Limited (synthetic)", "AGI/GMC/26/002918", 312.00, "30 June 2027"),
        ("Employees' compensation", "Abhayam General Insurance Limited (synthetic)", "AGI/WC/26/014560", 0.00, "30 June 2027"),
        ("Motor (5 vehicles)", "Abhayam General Insurance Limited (synthetic)", "Various", 96.40, "Various, 2027"),
        ("Directors' and officers' liability", "-", "-", 0.00, "Not taken; proposed before listing"),
    ]


def intellectual_property():
    return [
        ("ASHTAVIRA (word mark)", "Class 16", "5218437", "17 November 2021", "Registered", "Valid till 17 November 2031"),
        ("ASHTAVIRA FLEXIPAK with device (logo)", "Class 16", "6012984", "8 March 2024", "Objected", "Reply to examination report filed 22 August 2024; hearing awaited"),
        ("SPOUTPRO (word mark)", "Class 16", "6533071", "14 May 2025", "Accepted and advertised", "Opposition period over; registration certificate awaited"),
        ("Domain name ashtavira-synthetic.example", "-", "-", "2 March 2013", "Registered", "Renewed till 2 March 2028"),
    ]


def properties():
    return [
        ("Factory, Plot No. 214-216, GIDC Industrial Estate, Sanand-II", "Leasehold (99-year lease from GIDC from 12 December 2012)",
         "14,850 sq m land; 9,420 sq m built-up", "Manufacturing facility and registered office", "Gujarat Industrial Development Corporation"),
        ("Warehouse, Shed No. 7, Shree Hari Logistics Park, Changodar", "Leave and licence (11 months, renewable; current term 1 April 2026 to 28 February 2027)",
         "1,860 sq m", "Finished-goods warehouse", "Kavita Hemant Desai (Promoter) - related party; rent Rs 1.25 lakhs per month"),
        ("Office No. 902, Iscon Elegance, S.G. Highway, Prahlad Nagar", "Leave and licence (36 months from 1 May 2024)",
         "186 sq m", "Corporate and sales office", "Mr. Kunal Shah (unrelated); rent Rs 0.30 lakhs per month"),
    ]


if __name__ == "__main__":
    d = build()
    for p in PERIODS:
        x = d["pl"][p]
        print(p, "rev", x["revenue"], "EBITDA", x["ebitda"], f"({d['ratios'][p]['ebitda_margin_pct']}%)",
              "PBT", x["pbt"], "PAT", x["pat"], "CSR", x["csr"])
    for k in ["Mar22", "Mar23", "Mar24", "Mar25", "Mar26", "Sep26"]:
        b = d["bs"][k]
        print(k, "cash", b["cash_total"], "NW", b["net_worth"], "debt", b["total_debt"], "TA", b["total_assets"],
              "TL", b["total_liabilities"], "OE", b["other_equity"])
    for p in PERIODS:
        cf = d["cf"][p]
        print(p, "CFO", cf["cfo"], "CFI", cf["cfi"], "CFF", cf["cff"], "net", cf["net_change"],
              "dcash", round(cf["cash_close"] - cf["cash_open"], 2))
