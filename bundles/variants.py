"""Build the four additional issuer bundles (2-5) from the Ashtavira generator.

Each variant is a retargeted copy of the generator: the company, its group company, its people, its identifiers
(CIN, GSTIN, PAN, IEC, UDYAM, DIN), its plot and shed numbers, its bank, auditor, BRLM, legal counsel and research
firm are replaced. The sector, city, state, estate and the financial model are shared with bundle 1, so the
figures in each bundle tie across its own files, but the four bundles carry the same financial numbers.
This is stated in the bundle index and in docs/BUNDLES.md. Licence numbers are not retargeted.

    python variants.py            # build all four into bundles/out/
    python variants.py kestrel    # build one
"""
from __future__ import annotations

import re
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE / "out"

# Source names that appear in the Ashtavira generator (old -> replaced per variant).
PEOPLE_OLD = [
    "Hemant Ramniklal Desai", "Hemant Ramniklal Desai HUF", "Hemant Desai", "Kavita Hemant Desai", "Kavita Desai",
    "Parth Hemant Desai", "Parth Desai", "Mahesh Chandrakant Trivedi", "Mahesh Trivedi",
    "Dr. Ananya Srinivas Rao", "Ananya Rao", "Vikram Harish Sethi", "Vikram Sethi", "Sanjay Prakash Khatri",
    "Nidhi Rajesh Purohit", "Rakesh Govind Joshi", "Amit Kumar Varma", "Dr. Meera Krishnan Iyer",
    "Jignesh Natvarlal Shah", "Pooja Dinesh Mehta", "Kunal Shah", "Rohan Mehta", "Adv. Ritika Kanoria",
    "Ritika Kanoria", "CA Nirav K. Bhatt", "Nirav K. Bhatt", "Nilesh K. Bhatt", "Jayesh R. Parmar",
    "Rupal Ketan Parikh", "Rupal Parikh", "Desai Polymers LLP",
]
SURNAMES_OLD = ["Desai", "Trivedi", "Sethi", "Khatri", "Purohit", "Joshi", "Varma", "Iyer", "Shah", "Mehta",
                "Rao", "Kanoria", "Bhatt", "Parikh", "Parmar"]

VARIANTS = {
    "kestrel": {
        "folder": "kestrel_flexipak", "short": "Kestrel",
        "company": "Kestrel Flexipak Limited", "former": "Kestrel Flexipak Private Limited",
        "group": "Kestrel Packaging Solutions Private Limited",
        "domain": "kestrel-synthetic",
        "cin": "U22220GJ2014PLC083591", "former_cin": "U22220GJ2014PTC083591", "group_cin": "U74999GJ2017PTC096348",
        "gstin": "24AAJCK3390L1Z2", "pan": "AAJCK3390L", "iec": "0814027653", "udyam": "UDYAM-GJ-01-0061934",
        "phone_tail": "4890 5518", "plots": ["Plot No. 37-39", "Plot No. 41,", "Shed No. 12,", "Office No. 611,"],
        "dins": ["03486127", "03486133", "09526481", "06278139", "08113276", "07118402"],
        "masked": ["XXXXX3107X", "XXXXX5860X"],
        "bank": "Vindhya Bank Limited", "bank_file": "Vindhya",
        "auditor": "R P Mehrotra & Co.", "auditor_short": "R P Mehrotra", "frn": "121560C",
        "brlm": "Tulsi Capital Advisors Private Limited", "brlm_short": "Tulsi Capital", "brlm_sebi": "INM000018821",
        "legal": "Sheth Dave & Associates", "research": "Kaleido Research & Advisory Private Limited",
        "research_short": "Kaleido", "research_file": "Kaleido",
        "people": {
            "Hemant Ramniklal Desai": "Jitendra Ramesh Pathak", "Hemant Ramniklal Desai HUF": "Jitendra Ramesh Pathak HUF",
            "Hemant Desai": "Jitendra Pathak", "Kavita Hemant Desai": "Sunita Jitendra Pathak", "Kavita Desai": "Sunita Pathak",
            "Parth Hemant Desai": "Yash Jitendra Pathak", "Parth Desai": "Yash Pathak",
            "Mahesh Chandrakant Trivedi": "Girish Chandrakant Oza", "Mahesh Trivedi": "Girish Oza",
            "Dr. Ananya Srinivas Rao": "Dr. Lata Srinivasan Nair", "Ananya Rao": "Lata Nair",
            "Vikram Harish Sethi": "Rohit Harish Bedi", "Vikram Sethi": "Rohit Bedi",
            "Sanjay Prakash Khatri": "Sandeep Prakash Mistry", "Nidhi Rajesh Purohit": "Pallavi Rajesh Sheth",
            "Rakesh Govind Joshi": "Dinesh Govind Rana", "Amit Kumar Varma": "Kiran Kumar Bhatia",
            "Dr. Meera Krishnan Iyer": "Dr. Nandini Krishnan Menon", "Jignesh Natvarlal Shah": "Bharat Natwarlal Gandhi",
            "Pooja Dinesh Mehta": "Hetal Dinesh Thakkar", "Kunal Shah": "Mayur Doshi", "Rohan Mehta": "Aditya Kulkarni",
            "Adv. Ritika Kanoria": "Adv. Sneha Kapadia", "Ritika Kanoria": "Sneha Kapadia",
            "CA Nirav K. Bhatt": "CA Ashok R. Mehrotra", "Nirav K. Bhatt": "Ashok R. Mehrotra",
            "Nilesh K. Bhatt": "Nilesh R. Dave", "Jayesh R. Parmar": "Jayesh M. Solanki",
            "Rupal Ketan Parikh": "Ruchi Ketan Shroff", "Rupal Parikh": "Ruchi Shroff",
            "Desai Polymers LLP": "Pathak Polymers LLP",
        },
        "surnames": {"Desai": "Pathak", "Trivedi": "Oza", "Sethi": "Bedi", "Khatri": "Mistry", "Purohit": "Sheth",
                     "Joshi": "Rana", "Varma": "Bhatia", "Iyer": "Menon", "Shah": "Doshi", "Mehta": "Thakkar",
                     "Rao": "Nair", "Kanoria": "Kapadia", "Bhatt": "Mehrotra", "Parikh": "Shroff", "Parmar": "Solanki"},
    },
    "bhuvanam": {
        "folder": "bhuvanam_flexipak", "short": "Bhuvanam",
        "company": "Bhuvanam Flexipak Limited", "former": "Bhuvanam Flexipak Private Limited",
        "group": "Bhuvanam Packaging Solutions Private Limited",
        "domain": "bhuvanam-synthetic",
        "cin": "U22220GJ2016PLC091204", "former_cin": "U22220GJ2016PTC091204", "group_cin": "U74999GJ2019PTC109771",
        "gstin": "24AAHCB7142M1Z9", "pan": "AAHCB7142M", "iec": "0816032458", "udyam": "UDYAM-GJ-01-0074508",
        "phone_tail": "4890 7731", "plots": ["Plot No. 58-60", "Plot No. 62,", "Shed No. 4,", "Office No. 418,"],
        "dins": ["07612345", "07612358", "09915027", "08440613", "06902287", "07730954"],
        "masked": ["XXXXX7042X", "XXXXX1369X"],
        "bank": "Nilgiri Bank Limited", "bank_file": "Nilgiri",
        "auditor": "S R Ganesan & Co.", "auditor_short": "S R Ganesan", "frn": "104937S",
        "brlm": "Coromandel Merchant Advisors Private Limited", "brlm_short": "Coromandel Merchant",
        "brlm_sebi": "INM000021605",
        "legal": "Pandian Law Chambers", "research": "Tamarind Research & Analytics Private Limited",
        "research_short": "Tamarind", "research_file": "Tamarind",
        "people": {
            "Hemant Ramniklal Desai": "Venkatesh Ramanathan Iyengar", "Hemant Ramniklal Desai HUF": "Venkatesh Ramanathan Iyengar HUF",
            "Hemant Desai": "Venkatesh Iyengar", "Kavita Hemant Desai": "Padmavathi Venkatesh Iyengar", "Kavita Desai": "Padmavathi Iyengar",
            "Parth Hemant Desai": "Karthik Venkatesh Iyengar", "Parth Desai": "Karthik Iyengar",
            "Mahesh Chandrakant Trivedi": "Murugan Shanmugam Pillai", "Mahesh Trivedi": "Murugan Pillai",
            "Dr. Ananya Srinivas Rao": "Dr. Revathi Sundaram", "Ananya Rao": "Revathi Sundaram",
            "Vikram Harish Sethi": "Arun Kumar Naidu", "Vikram Sethi": "Arun Naidu",
            "Sanjay Prakash Khatri": "Senthil Kumar Raja", "Nidhi Rajesh Purohit": "Divya Rajesh Krishnan",
            "Rakesh Govind Joshi": "Selvam Govindaraj", "Amit Kumar Varma": "Prakash Kumar Subramanian",
            "Dr. Meera Krishnan Iyer": "Dr. Anitha Rajagopal", "Jignesh Natvarlal Shah": "Jagadeesh Natarajan",
            "Pooja Dinesh Mehta": "Lakshmi Sivakumar", "Kunal Shah": "Vijay Sankar", "Rohan Mehta": "Ajith Menon",
            "Adv. Ritika Kanoria": "Adv. Kavitha Subbiah", "Ritika Kanoria": "Kavitha Subbiah",
            "CA Nirav K. Bhatt": "CA Sathish R. Ganesan", "Nirav K. Bhatt": "Sathish R. Ganesan",
            "Nilesh K. Bhatt": "Mohan Kumar Rajan", "Jayesh R. Parmar": "Ravi Pandian",
            "Rupal Ketan Parikh": "Meenakshi Ketan Gopal", "Rupal Parikh": "Meenakshi Gopal",
            "Desai Polymers LLP": "Iyengar Polymers LLP",
        },
        "surnames": {"Desai": "Iyengar", "Trivedi": "Pillai", "Sethi": "Naidu", "Khatri": "Raja", "Purohit": "Krishnan",
                     "Joshi": "Govindaraj", "Varma": "Subramanian", "Iyer": "Rajagopal", "Shah": "Natarajan",
                     "Mehta": "Sivakumar", "Rao": "Sundaram", "Kanoria": "Subbiah", "Bhatt": "Ganesan",
                     "Parikh": "Gopal", "Parmar": "Pandian"},
    },
    "tavanvi": {
        "folder": "tavanvi_flexipak", "short": "Tavanvi",
        "company": "Tavanvi Flexipak Limited", "former": "Tavanvi Flexipak Private Limited",
        "group": "Tavanvi Packaging Solutions Private Limited",
        "domain": "tavanvi-synthetic",
        "cin": "U22220GJ2013PLC076318", "former_cin": "U22220GJ2013PTC076318", "group_cin": "U74999GJ2018PTC101462",
        "gstin": "24AAOTV5819K1Z4", "pan": "AAOTV5819K", "iec": "0813065291", "udyam": "UDYAM-GJ-01-0052093",
        "phone_tail": "4890 3364", "plots": ["Plot No. 9-11", "Plot No. 15,", "Shed No. 21,", "Office No. 302,"],
        "dins": ["02389417", "02389426", "09330768", "07054521", "08677150", "06129834"],
        "masked": ["XXXXX6218X", "XXXXX8803X"],
        "bank": "Saraswati Bank Limited", "bank_file": "Saraswati",
        "auditor": "M K Pancholi & Associates", "auditor_short": "M K Pancholi", "frn": "132480W",
        "brlm": "Harbour Capital Markets Private Limited", "brlm_short": "Harbour Capital", "brlm_sebi": "INM000027193",
        "legal": "Vakil Patel & Co.", "research": "Meadow Market Intelligence Private Limited",
        "research_short": "Meadow", "research_file": "Meadow",
        "people": {
            "Hemant Ramniklal Desai": "Bhargav Ashwin Vyas", "Hemant Ramniklal Desai HUF": "Bhargav Ashwin Vyas HUF",
            "Hemant Desai": "Bhargav Vyas", "Kavita Hemant Desai": "Heena Bhargav Vyas", "Kavita Desai": "Heena Vyas",
            "Parth Hemant Desai": "Mihir Bhargav Vyas", "Parth Desai": "Mihir Vyas",
            "Mahesh Chandrakant Trivedi": "Ashok Dhirubhai Mankad", "Mahesh Trivedi": "Ashok Mankad",
            "Dr. Ananya Srinivas Rao": "Dr. Shruti Hemant Jani", "Ananya Rao": "Shruti Jani",
            "Vikram Harish Sethi": "Pratik Harish Shukla", "Vikram Sethi": "Pratik Shukla",
            "Sanjay Prakash Khatri": "Nikhil Prakash Desale", "Nidhi Rajesh Purohit": "Riya Rajesh Dwivedi",
            "Rakesh Govind Joshi": "Ramesh Govind Thakur", "Amit Kumar Varma": "Sameer Kumar Agarwal",
            "Dr. Meera Krishnan Iyer": "Dr. Falguni Ramesh Brahmbhatt", "Jignesh Natvarlal Shah": "Dhaval Natvarlal Modi",
            "Pooja Dinesh Mehta": "Kavita Dinesh Soni", "Kunal Shah": "Naresh Lodha", "Rohan Mehta": "Kartik Nayak",
            "Adv. Ritika Kanoria": "Adv. Tejal Bhatt", "Ritika Kanoria": "Tejal Bhatt",
            "CA Nirav K. Bhatt": "CA Jignesh D. Pancholi", "Nirav K. Bhatt": "Jignesh D. Pancholi",
            "Nilesh K. Bhatt": "Chirag Nilesh Dhruva", "Jayesh R. Parmar": "Kamlesh R. Rawal",
            "Rupal Ketan Parikh": "Shweta Ketan Bhavsar", "Rupal Parikh": "Shweta Bhavsar",
            "Desai Polymers LLP": "Vyas Polymers LLP",
        },
        "surnames": {"Desai": "Vyas", "Trivedi": "Mankad", "Sethi": "Shukla", "Khatri": "Desale", "Purohit": "Dwivedi",
                     "Joshi": "Thakur", "Varma": "Agarwal", "Iyer": "Brahmbhatt", "Shah": "Modi", "Mehta": "Soni",
                     "Rao": "Jani", "Kanoria": "Bhatt", "Bhatt": "Pancholi", "Parikh": "Bhavsar", "Parmar": "Rawal"},
    },
    "oakvale": {
        "folder": "oakvale_flexipak", "short": "Oakvale",
        "company": "Oakvale Flexipak Limited", "former": "Oakvale Flexipak Private Limited",
        "group": "Oakvale Packaging Solutions Private Limited",
        "domain": "oakvale-synthetic",
        "cin": "U22220GJ2015PLC080445", "former_cin": "U22220GJ2015PTC080445", "group_cin": "U74999GJ2020PTC114703",
        "gstin": "24AAGOF2608P1Z5", "pan": "AAGOF2608P", "iec": "0815049172", "udyam": "UDYAM-GJ-01-0068129",
        "phone_tail": "4890 6640", "plots": ["Plot No. 103-105", "Plot No. 107,", "Shed No. 16,", "Office No. 204,"],
        "dins": ["05294813", "05294827", "09702650", "07885219", "06346071", "08239164"],
        "masked": ["XXXXX2295X", "XXXXX4061X"],
        "bank": "Ganga Bank Limited", "bank_file": "Ganga",
        "auditor": "J P Shroff & Co.", "auditor_short": "J P Shroff", "frn": "116305W",
        "brlm": "Lakeshore Securities Advisors Private Limited", "brlm_short": "Lakeshore Securities",
        "brlm_sebi": "INM000024618",
        "legal": "Kothari Mody & Partners", "research": "Pinecrest Research & Consulting Private Limited",
        "research_short": "Pinecrest", "research_file": "Pinecrest",
        "people": {
            "Hemant Ramniklal Desai": "Narendra Shantilal Bhagat", "Hemant Ramniklal Desai HUF": "Narendra Shantilal Bhagat HUF",
            "Hemant Desai": "Narendra Bhagat", "Kavita Hemant Desai": "Rekha Narendra Bhagat", "Kavita Desai": "Rekha Bhagat",
            "Parth Hemant Desai": "Dhruv Narendra Bhagat", "Parth Desai": "Dhruv Bhagat",
            "Mahesh Chandrakant Trivedi": "Yogesh Chandulal Parekh", "Mahesh Trivedi": "Yogesh Parekh",
            "Dr. Ananya Srinivas Rao": "Dr. Madhavi Umesh Kher", "Ananya Rao": "Madhavi Kher",
            "Vikram Harish Sethi": "Sunil Harish Sanghvi", "Vikram Sethi": "Sunil Sanghvi",
            "Sanjay Prakash Khatri": "Kunal Prakash Ruparel", "Nidhi Rajesh Purohit": "Neha Rajesh Gosalia",
            "Rakesh Govind Joshi": "Mukesh Govind Panchal", "Amit Kumar Varma": "Sunny Kumar Chokshi",
            "Dr. Meera Krishnan Iyer": "Dr. Jyoti Krishnan Mistry", "Jignesh Natvarlal Shah": "Pankaj Natvarlal Bhayani",
            "Pooja Dinesh Mehta": "Nisha Dinesh Maru", "Kunal Shah": "Harish Kapadia", "Rohan Mehta": "Sumit Vora",
            "Adv. Ritika Kanoria": "Adv. Pooja Ruparel", "Ritika Kanoria": "Pooja Ruparel",
            "CA Nirav K. Bhatt": "CA Pranav J. Shroff", "Nirav K. Bhatt": "Pranav J. Shroff",
            "Nilesh K. Bhatt": "Deepak N. Joshi", "Jayesh R. Parmar": "Milan R. Vaidya",
            "Rupal Ketan Parikh": "Sonal Ketan Bakshi", "Rupal Parikh": "Sonal Bakshi",
            "Desai Polymers LLP": "Bhagat Polymers LLP",
        },
        "surnames": {"Desai": "Bhagat", "Trivedi": "Parekh", "Sethi": "Sanghvi", "Khatri": "Ruparel", "Purohit": "Gosalia",
                     "Joshi": "Panchal", "Varma": "Chokshi", "Iyer": "Mistry", "Shah": "Bhayani", "Mehta": "Maru",
                     "Rao": "Kher", "Kanoria": "Ruparel", "Bhatt": "Shroff", "Parikh": "Bakshi", "Parmar": "Vaidya"},
    },
}

# Company-level replacements shared by every variant. Each entry is (source text, key) where key names a field
# of VARIANTS[v]; the replacement is the variant's value. Longer source strings are applied first.
COMPANY_SOURCE = [
    ("Ashtavira Flexipak Private Limited", "former"),
    ("Ashtavira Flexipak Limited", "company"),
    ("Ashtavira Packaging Solutions Private Limited", "group"),
    ("Ashtavira Packaging Solutions", "group_short"),
    ("Ashtavira Flexipak", "company_short"),
    ("Ashtavira", "short"),
    ("ashtavira_flexipak", "folder"),
    ("ashtavira-synthetic", "domain"),
    ("U22220GJ2012PLC071846", "cin"),
    ("U22220GJ2012PTC071846", "former_cin"),
    ("U74999GJ2019PTC109342", "group_cin"),
    ("24AAKCA4718M1Z6", "gstin"),
    ("AAKCA4718M", "pan"),
    ("0812018734", "iec"),
    ("UDYAM-GJ-01-0047218", "udyam"),
    ("4890 2214", "phone_tail"),
    ("Plot No. 214-216", "plot1"),
    ("Plot No. 214,", "plot2"),
    ("Shed No. 7,", "plot3"),
    ("Office No. 902,", "plot4"),
    ("XXXXX4471X", "masked0"),
    ("XXXXX9132X", "masked1"),
    ("N K Bhatt & Co.", "auditor"),
    ("N K Bhatt", "auditor_short"),
    ("118742W", "frn"),
    ("Meridian Capital Advisors Private Limited", "brlm"),
    ("Meridian Capital", "brlm_short"),
    ("INM000013472", "brlm_sebi"),
    ("Kanoria Sharma & Partners", "legal"),
    ("Arthaveda Research & Advisory Private Limited", "research"),
    ("Arthaveda", "research_short"),
    ("Kalindi Bank Limited", "bank"),
    ("Kalindi", "bank_short"),
]
DIN_OLD = ["02718465", "02718472", "09841276", "06614390", "08260517", "07390824"]


def _mapping(v: str) -> list[tuple[str, str]]:
    cfg = VARIANTS[v]
    pairs: dict[str, str] = {}
    for src, key in COMPANY_SOURCE:
        val = {
            "group_short": cfg["group"].rsplit(" Private Limited", 1)[0],
            "company_short": cfg["company"].rsplit(" Limited", 1)[0],
            "short": cfg["short"],
            "bank_short": cfg["bank_file"],
            "folder": cfg["folder"],
            "plot1": cfg["plots"][0], "plot2": cfg["plots"][1], "plot3": cfg["plots"][2], "plot4": cfg["plots"][3],
            "masked0": cfg["masked"][0], "masked1": cfg["masked"][1],
            "auditor_short": cfg["auditor_short"], "brlm_short": cfg["brlm_short"], "research_short": cfg["research_short"],
            "bank": cfg["bank"], "research": cfg["research"],
        }.get(key) or cfg.get(key)
        if val is None:
            raise KeyError(f"{v}: no value for {key}")
        pairs[src] = val
    for old, new in zip(DIN_OLD, cfg["dins"]):
        pairs[old] = new
    for old in PEOPLE_OLD:
        pairs[old] = cfg["people"][old]
    for old in SURNAMES_OLD:
        pairs[old] = cfg["surnames"][old]
    # first names used on their own in the text (for example "Hemant and Kavita")
    for first, full in (("Hemant", "Hemant Ramniklal Desai"), ("Kavita", "Kavita Hemant Desai"), ("Parth", "Parth Hemant Desai")):
        pairs[first] = cfg["people"][full].split()[0]
    # the filename token of the research firm and the bank in file names
    pairs.setdefault("Kalindi_Bank", cfg["bank_file"] + "_Bank")
    pairs.setdefault("Arthaveda_", cfg["research_file"] + "_")
    ordered = sorted(pairs.items(), key=lambda kv: -len(kv[0]))
    return ordered


def retarget_source(v: str, dst: Path) -> None:
    """Replace every source name in one pass, so a replacement is never replaced again (for example, a new
    surname that happens to equal another source name)."""
    dst.mkdir(parents=True, exist_ok=True)
    table = dict(_mapping(v))
    alt = "|".join(re.escape(k) for k in sorted(table, key=len, reverse=True))
    rx = re.compile(r"(?<![A-Za-z0-9])(" + alt + r")(?![A-Za-z0-9])")
    for f in HERE.glob("*.py"):
        text = f.read_text(encoding="utf-8")
        (dst / f.name).write_text(rx.sub(lambda m: table[m.group(1)], text), encoding="utf-8")


def build_variant(v: str) -> None:
    cfg = VARIANTS[v]
    src = OUT / "_src" / v
    if src.exists():
        shutil.rmtree(src)
    retarget_source(v, src)
    bundle = OUT / cfg["folder"]
    if bundle.exists():
        shutil.rmtree(bundle)
    subprocess.run([sys.executable, str(src / "driver.py"), str(bundle), cfg["folder"]], check=True,
                   env={**__import__("os").environ, "PYTHONUTF8": "1"})


if __name__ == "__main__":
    names = sys.argv[1:] or list(VARIANTS)
    for n in names:
        build_variant(n)
        print("built", n, flush=True)
