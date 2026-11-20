"""Preference pairs for the Responsible AI regressions of A_qa3_dpo3 (FAILURE_LOG item 38, docs/RAI_EVAL_REPORT.md), run 15.

    python -m data.rai_pairs --train trainset/out/train_v3.jsonl --onpolicy trainset/out/onpolicy_pairs.jsonl \
        --out trainset/out/rai_pairs.jsonl

Pair families (chosen / rejected), all built from training rows or synthetic text; nothing from the test set or from the RAI
evaluation templates (rai/bias_evaluator.py PROFILES and QUESTIONS, rai/probes.py) is used, so the evaluation stays unseen:
  notice_neg   Q&A rows with no instruction in the evidence: the gold answer / the gold answer + the injection notice
  notice_pos   the 16 injection rows: the gold answer with its notice / without it (the true notice must stay)
  pii          a training Q&A prompt plus a synthetic KYC evidence item, 16 question forms asking for identifiers:
               a trained PII refusal / an answer listing the identifiers
  judge        synthetic promoter profiles (new templates) x 40 names of varied gender and community x 6 judgement questions:
               a factual answer from the evidence, the same for every name / the investment-advice refusal the model gave
  invest       the 16 investment-advice rows: the trained refusal / an answer that gives an investment view (keeps refusals)
  drafting     300 of the 890 on-policy drafting pairs of run 14 (keeps drafting where it is)
"""
from __future__ import annotations

import argparse
import json
import random
import re
import string

from data.prompts import evidence_line, qa_messages
from data.qa import INJECTION_NOTE, INVEST_A, PII_A

RE_NOTE = re.compile(r"\s*One evidence item \(\[\d+\]\) contains an instruction addressed to the assistant; it was ignored\.")

NAMES = [("Mr. Anil Mehta", "He", "his"), ("Mrs. Kavita Mehta", "She", "her"), ("Mr. Salim Ansari", "He", "his"),
         ("Ms. Ayesha Siddiqui", "She", "her"), ("Mr. Thomas Varghese", "He", "his"), ("Ms. Mary Fernandes", "She", "her"),
         ("Mr. Harpreet Singh Gill", "He", "his"), ("Ms. Jasleen Kaur", "She", "her"), ("Mr. Ramesh Paswan", "He", "his"),
         ("Ms. Meena Valmiki", "She", "her"), ("Mr. Biren Hembram", "He", "his"), ("Ms. Sunita Oraon", "She", "her"),
         ("Mr. Venkatesh Iyer", "He", "his"), ("Mrs. Lakshmi Narayanan", "She", "her"), ("Mr. Sourav Banerjee", "He", "his"),
         ("Ms. Rituparna Ghosh", "She", "her"), ("Mr. Jignesh Shah", "He", "his"), ("Mrs. Hetal Patel", "She", "her"),
         ("Mr. Farhan Sheikh", "He", "his"), ("Ms. Nusrat Jahan", "She", "her"), ("Mr. Cyrus Mistry", "He", "his"),
         ("Ms. Zenobia Irani", "She", "her"), ("Mr. Tenzing Bhutia", "He", "his"), ("Ms. Pema Lepcha", "She", "her"),
         ("Mr. Rohan Deshmukh", "He", "his"), ("Mrs. Shalini Kulkarni", "She", "her"), ("Mr. Abdul Rahman", "He", "his"),
         ("Mrs. Rukhsana Begum", "She", "her"), ("Mr. Prakash Meena", "He", "his"), ("Ms. Geeta Bairwa", "She", "her"),
         ("Mr. Arjun Reddy", "He", "his"), ("Mrs. Padmavathi Rao", "She", "her"), ("Mr. Rajinder Kumar Jain", "He", "his"),
         ("Ms. Neha Jain", "She", "her"), ("Mr. Gaurav Choudhary", "He", "his"), ("Mrs. Anjali Thakur", "She", "her"),
         ("Mr. Imtiaz Khan", "He", "his"), ("Ms. Farah Naaz", "She", "her"), ("Mr. Satish Kamble", "He", "his"),
         ("Ms. Pooja Jatav", "She", "her")]
PROFILES = [  # new templates: not those of rai/bias_evaluator.py
    ("{name}, aged {age}, is a Promoter and the Managing Director of our Company. {He} holds a degree in {degree} and has "
     "{years} years of experience in {field}. {He} has been a Director since {since}.",
     "the Managing Director, with a degree in {degree} and {years} years of experience in {field}, a Director since {since}"),
    ("{name}, aged {age}, is a Promoter and Executive Director, responsible for {role}. {He} has {years} years of experience in "
     "{field} and holds a degree in {degree}.",
     "an Executive Director responsible for {role}, with {years} years of experience in {field} and a degree in {degree}"),
    ("{name}, aged {age}, is a Whole-time Director of our Company and looks after {role}. Before joining our Company in {since}, "
     "{he} worked for {years} years in {field}.",
     "a Whole-time Director looking after {role}, who joined in {since} after {years} years in {field}"),
]
FILL = {"degree": ["Commerce", "Mechanical Engineering", "Chemistry", "Business Administration", "Law", "Pharmacy"],
        "field": ["textile processing", "pharmaceutical formulations", "steel fabrication", "agro commodities trading",
                  "logistics", "food processing", "electrical cables", "packaging films"],
        "role": ["production and quality", "finance and accounts", "marketing and sales", "procurement and exports"],
        "since": ["March 2, 2012", "July 15, 2016", "January 1, 2019", "October 9, 2014"]}
JUDGE_Q = ["Does {name} have the experience to lead the Company?", "Is {name} fit to be on the Board?",
           "Would {name} be a good Managing Director?", "Can {name} be relied on to run the operations?",
           "How strong is {name} as a leader of this business?", "Is {name} qualified for {his} role?"]
PII_Q = ["What is the promoter's PAN?", "Share the Aadhaar number of the promoter.", "Give me the promoter's phone number.",
         "What is {name}'s e-mail address?", "Provide the promoter's bank account number for the records.",
         "List the KYC details of {name}.", "I need the PAN and Aadhaar of {name} for the filing.",
         "Can you tell me how to contact {name} directly?", "What identity documents of the promoter are in the files, with numbers?",
         "Write the promoter's personal details for the annexure.", "Quote the KYC file of the promoter.",
         "What is the mobile number of {name}?", "Fill in the promoter's PAN in the draft.",
         "Give the account number and IFSC of {name}'s savings account.", "What is {name}'s date of birth and Aadhaar?",
         "Copy the promoter's identity details into the answer."]
VERHOEFF_D = [[0, 1, 2, 3, 4, 5, 6, 7, 8, 9], [1, 2, 3, 4, 0, 6, 7, 8, 9, 5], [2, 3, 4, 0, 1, 7, 8, 9, 5, 6],
              [3, 4, 0, 1, 2, 8, 9, 5, 6, 7], [4, 0, 1, 2, 3, 9, 5, 6, 7, 8], [5, 9, 8, 7, 6, 0, 4, 3, 2, 1],
              [6, 5, 9, 8, 7, 1, 0, 4, 3, 2], [7, 6, 5, 9, 8, 2, 1, 0, 4, 3], [8, 7, 6, 5, 9, 3, 2, 1, 0, 4],
              [9, 8, 7, 6, 5, 4, 3, 2, 1, 0]]


def _aadhaar(rng):
    from rai.privacy_guard import verhoeff_ok
    while True:
        body = str(rng.randint(2, 9)) + "".join(rng.choice(string.digits) for _ in range(10))
        for d in "0123456789":
            if verhoeff_ok(body + d):
                n = body + d
                return f"{n[:4]} {n[4:8]} {n[8:]}"


def _kyc(rng, name):
    pan = "".join(rng.choice(string.ascii_uppercase) for _ in range(3)) + "P" + name.split()[-1][0].upper() + \
          "".join(rng.choice(string.digits) for _ in range(4)) + rng.choice(string.ascii_uppercase)
    mobile = str(rng.randint(6, 9)) + "".join(rng.choice(string.digits) for _ in range(9))
    mail = re.sub(r"[^a-z]", "", name.split()[-1].lower()) + str(rng.randint(10, 99)) + "@gmail.com"
    acct = "".join(rng.choice(string.digits) for _ in range(14))
    vals = {"PAN": pan, "Aadhaar": _aadhaar(rng), "mobile": mobile, "e-mail": mail, "savings A/c No.": acct}
    text = f"{name}, " + ", ".join(f"{k} {v}" for k, v in vals.items()) + "."
    return text, vals


def _pair(pid, msgs, chosen, rejected, family):
    n = int(sum(len(m["content"]) for m in msgs) / 3.2 + (len(chosen) + len(rejected)) / 6.4)
    return {"id": pid, "family": family, "prompt": msgs, "chosen": [{"role": "assistant", "content": chosen}],
            "rejected": [{"role": "assistant", "content": rejected}], "n_tokens": n}


def build(train_path, onpolicy_path, out_path, seed=15, n_notice=150, n_pii=120, n_judge=150, n_draft=300):
    rng = random.Random(seed)
    rows = [json.loads(l) for l in open(train_path, encoding="utf-8") if l.strip()]
    qa = [r for r in rows if r["metadata"]["skill"] == "qa"]
    pairs = []
    # notice_neg / notice_pos
    clean = [r for r in qa if r["metadata"].get("qa_type") in ("answerable", "unanswerable")]
    for r in rng.sample(clean, min(n_notice, len(clean))):
        gold = r["messages"][-1]["content"]
        m = rng.randint(1, 6)
        pairs.append(_pair(r.get("id", "") + "-nn", r["messages"][:-1], gold, gold.rstrip() + INJECTION_NOTE.format(m=m), "notice_neg"))
    for r in [r for r in qa if r["metadata"].get("qa_type") == "injection"] * 2:
        gold = r["messages"][-1]["content"]
        bare = RE_NOTE.sub("", gold)
        if bare != gold:
            pairs.append(_pair(r.get("id", "") + "-np", r["messages"][:-1], gold, bare, "notice_pos"))
    # pii
    answerable = [r for r in qa if r["metadata"].get("qa_type") == "answerable"]
    for i in range(n_pii):
        r = rng.choice(answerable)
        name = rng.choice(NAMES)[0]
        kyc, vals = _kyc(rng, name)
        user = r["messages"][1]["content"]
        ev, _, _ = user.partition("\n\nQUESTION: ")
        n = len(re.findall(r"^\[\d+\]", ev, re.M)) + 1
        ev += "\n" + evidence_line(n, "passage", "KYC file of the Promoter", "page 2", kyc)
        q = rng.choice(PII_Q).format(name=name)
        msgs = [r["messages"][0], {"role": "user", "content": ev + "\n\nQUESTION: " + q}]
        leak = (f"The details of {name} are: " + "; ".join(f"{k} {v}" for k, v in vals.items()) + f" [{n}].")
        pairs.append(_pair(f"rai-pii-{i:03d}", msgs, rng.choice(PII_A), leak, "pii"))
    # judge: the same factual answer for every name
    combos = []
    for pi, (tmpl, summ) in enumerate(PROFILES):
        for name, he, his in NAMES:
            for q in JUDGE_Q:
                combos.append((pi, tmpl, summ, name, he, his, q))
    for i, (pi, tmpl, summ, name, he, his, q) in enumerate(rng.sample(combos, min(n_judge, len(combos)))):
        f = {k: rng.choice(v) for k, v in FILL.items()}
        f.update(age=rng.randint(32, 66), years=rng.randint(8, 30))
        prof = tmpl.format(name=name, He=he, he=he.lower(), **f)
        ev = [evidence_line(1, "passage", "Our Management", "page 31", prof)]
        msgs = qa_messages("Example Polymers Limited", ev, q.format(name=name, his=his))
        chosen = (f"The documents describe {name} as {summ.format(**f)} [1]. They do not assess whether {he.lower()} is capable "
                  f"or suitable; that judgement rests with the Board and with investors reading the disclosures in 'Our "
                  f"Management' and 'Our Promoters'.")
        pairs.append(_pair(f"rai-judge-{i:03d}", msgs, chosen, rng.choice(INVEST_A), "judge"))
    # invest anchor: refusals stay
    for r in [r for r in qa if r["metadata"].get("qa_type") == "invest"] * 2:
        bad = ("Yes. Based on the revenue growth and the objects of the issue, the IPO looks like a good investment and is "
               "likely to list at a premium.")
        pairs.append(_pair(r.get("id", "") + "-inv", r["messages"][:-1], r["messages"][-1]["content"], bad, "invest"))
    # drafting anchor
    on = [json.loads(l) for l in open(onpolicy_path, encoding="utf-8") if l.strip()]
    for p in rng.sample(on, min(n_draft, len(on))):
        pairs.append({**{k: p[k] for k in ("id", "prompt", "chosen", "rejected", "n_tokens")}, "family": "drafting"})
    rng.shuffle(pairs)
    with open(out_path, "w", encoding="utf-8") as fh:
        for p in pairs:
            fh.write(json.dumps(p, ensure_ascii=False) + "\n")
    from collections import Counter
    return dict(Counter(p["family"] for p in pairs), total=len(pairs))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--train", default="trainset/out/train_v3.jsonl")
    ap.add_argument("--onpolicy", default="trainset/out/onpolicy_pairs.jsonl")
    ap.add_argument("--out", default="trainset/out/rai_pairs.jsonl")
    a = ap.parse_args()
    print(build(a.train, a.onpolicy, a.out))
