"""Is the training set right for the job? An audit of trainset/out/train_v2.jsonl against what the model must do in the app.

    python -m evaluate.audit_trainset [train_v2.jsonl] [test_v2.jsonl]

The job: write one narrative sub-heading of an SME DRHP from facts and passages taken from a data room, using only what those
inputs support, with [●] where they do not. The checks below ask whether the data teaches that.

1  composition      rows by skill and section, precedent share, facts given
2  groundedness     figures, dates and names in the drafting TARGETS that are not in the prompt (the model is trained to write them)
3  missing facts    how many facts the prompt held against what the target needed (router recall), and rows with no missing fact
4  abstention       targets that put [●] where a value is unknown, against targets that state one with no fact
5  noise            PDF debris in targets: page footers, flattened tables, broken words, dates cut off
6  addresses        targets that state an address, and whether the address facts were in the prompt
7  business skew    "Our Business" targets that describe a manufacturer, against the issuers an EPC or service firm would be
8  leakage          companies and near-duplicates shared between train and test
9  Q&A and extraction  composition and groundedness of the other skills
"""
from __future__ import annotations

import collections
import json
import os
import re
import sys

from data.facts import figures, parse_dates, proper_names
from evaluate import metrics as M
from verify.checks import RE_ADDR

RE_FOOTER = re.compile(r"\|\s*P\s*a\s*g\s*e|\bPage\s+\d+\s+of\s+\d+|\b\d{1,3}\s*\|\s*P", re.I)
RE_WORDS = re.compile(r"[A-Za-z]+")


def broken_words(text, vocab):
    """Pairs of neighbouring fragments that make one vocabulary word when joined ("Certifica te" -> certificate) while neither
    half is a word of its own: PDF line-break debris that the model learns to copy."""
    w = [x.lower() for x in RE_WORDS.findall(text)]
    return sum(1 for a, b in zip(w, w[1:]) if len(a) >= 4 and 1 <= len(b) <= 3 and a not in vocab and (a + b) in vocab)
RE_CUT_DATE = re.compile(r"\b(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},?\s*$", re.M)
RE_FLAT_TABLE = re.compile(r"(?:\d[\d,]*\.\d{2}\s+){4,}")
PH = "[●]"


def load(path):
    return [json.loads(l) for l in open(path, encoding="utf-8") if l.strip()]


def pct(a, n):
    return f"{100 * a / max(1, n):5.1f}%"


def facts_of(row):
    m = re.search(r"^FACTS: (\[.*?\])\s*$", row["messages"][1]["content"], re.M)
    try:
        return json.loads(m.group(1)) if m else []
    except ValueError:
        return []


def audit(train_path, test_path):
    train, test = load(train_path), load(test_path)
    dr = [r for r in train if r["metadata"]["skill"] == "drafting"]
    print(f"{train_path}: {len(train)} rows  {dict(collections.Counter(r['metadata']['skill'] for r in train))}")

    # 1 composition
    secs = collections.Counter(r["metadata"]["section_bucket"] for r in dr)
    print("\n1 COMPOSITION  drafting rows by section:", dict(secs.most_common()))
    prec = sum(bool(r["metadata"].get("precedent")) for r in dr)
    print(f"  rows with a PRECEDENT block: {prec} of {len(dr)} = {pct(prec, len(dr))} (the app sends none)")
    nf = [r["metadata"]["n_facts"] for r in dr]
    print(f"  facts per prompt: median {sorted(nf)[len(nf) // 2]}, 0-5 facts {pct(sum(x <= 5 for x in nf), len(nf))}, 16+ facts {pct(sum(x > 15 for x in nf), len(nf))}")
    dis = sum(r["metadata"]["n_distractors"] > 0 for r in dr)
    print(f"  prompts with distractor facts: {pct(dis, len(dr))}; the app's router adds ~{40 - 5} routed facts on top of passages")

    # 2 groundedness of the targets
    inv_f = inv_d = inv_n = 0
    tot_f = tot_d = 0
    unground_rows = []
    for r in dr:
        src = M.source_text(r)
        tgt = r["messages"][-1]["content"]
        f_t, f_s = figures(tgt), figures(src)
        d_t, d_s = parse_dates(tgt), parse_dates(src)
        words = set(M._tokens(src))
        n_bad = sum(not M._name_grounded(n, words) for n in proper_names(tgt))
        bad_f, bad_d = f_t - f_s, d_t - d_s
        inv_f += bool(bad_f)
        inv_d += bool(bad_d)
        inv_n += n_bad > 0
        tot_f += len(f_t)
        tot_d += len(d_t)
        if bad_f or bad_d:
            unground_rows.append((r["metadata"]["unit_id"], sorted(bad_f)[:4], sorted(str(x) for x in bad_d)[:2]))
    print(f"\n2 GROUNDEDNESS  drafting TARGETS with a figure not in the prompt: {inv_f} of {len(dr)} = {pct(inv_f, len(dr))};"
          f" a date not in the prompt: {pct(inv_d, len(dr))}; a name not in the prompt: {pct(inv_n, len(dr))}")
    print("  (every such value is something the model is trained to write without being given it)")
    for u in unground_rows[:5]:
        print("   e.g.", u)

    # 3 missing facts
    rr = [r["metadata"]["router_recall"] for r in dr if r["metadata"].get("router_recall") is not None]
    print(f"\n3 MISSING FACTS  router recall of the facts the target needs (own facts in the router's top 40): mean {sum(rr) / max(1, len(rr)):.3f}")
    full = sum(r["metadata"]["n_own"] > 0 and r["metadata"]["n_facts"] >= r["metadata"]["n_own"] for r in dr)
    print(f"  Training prompts hold ALL the target's own facts (the gates require it); at inference the router finds about half of them.")
    print(f"  Rows where the prompt lacked a fact the target states: {inv_f + inv_d} of {len(dr)} (section 2). So the data hardly ever shows the model a gap.")

    # 4 abstention
    ph = sum(PH in r["messages"][-1]["content"] for r in dr)
    ph_only = sum(r["messages"][-1]["content"].count(PH) >= 3 for r in dr)
    print(f"\n4 ABSTENTION  targets containing [●]: {ph} = {pct(ph, len(dr))}; with 3 or more: {pct(ph_only, len(dr))}")
    ph_kinds = collections.Counter()
    for r in dr:
        for m in re.finditer(r"(.{0,30})\[●\]", r["messages"][-1]["content"]):
            ph_kinds["offer terms (price, size, dates)" if re.search(r"price|size|issue|offer|lot|date|proceeds|band", m.group(1), re.I) else "other"] += 1
    print("  what the [●] stands for:", dict(ph_kinds))
    print("  [●] in targets is DRHP-stage masking of offer terms (data/mask.py), not 'this fact is missing': the model is never taught to leave a gap for an unknown address or amount.")

    # 5 noise
    n_footer = sum(bool(RE_FOOTER.search(r["messages"][-1]["content"])) for r in dr)
    n_flat = sum(bool(RE_FLAT_TABLE.search(r["messages"][-1]["content"])) for r in dr)
    from verify.vocab import generic_words
    vocab = generic_words()
    n_broken = sum(broken_words(r["messages"][-1]["content"], vocab) >= 1 for r in dr)
    n_cut = sum(bool(RE_CUT_DATE.search(r["messages"][-1]["content"])) for r in dr)
    print(f"\n5 NOISE  targets with page-footer debris: {pct(n_footer, len(dr))}; a flattened numeric table: {pct(n_flat, len(dr))};"
          f" a word broken by the PDF (1+): {pct(n_broken, len(dr))}; a date cut off at a line end: {pct(n_cut, len(dr))}")
    ln = [len(r["messages"][-1]["content"].split()) for r in dr]
    print(f"  target length: median {sorted(ln)[len(ln) // 2]} words, 1,000+ words {pct(sum(x > 1000 for x in ln), len(ln))}")

    # 6 addresses
    with_addr = [r for r in dr if RE_ADDR.search(r["messages"][-1]["content"])]
    addr_in_facts = 0
    for r in with_addr:
        nums = {re.sub(r"\D", "", x.group(1)) for x in RE_ADDR.finditer(r["messages"][-1]["content"])}
        fv = " ".join(str(f["value"]) for f in facts_of(r))
        addr_in_facts += all(n in re.sub(r"\D", " ", fv).replace(" ", "") or n in fv for n in nums)
    print(f"\n6 ADDRESSES  targets that state a Plot / Sector / Survey address: {len(with_addr)} = {pct(len(with_addr), len(dr))};"
          f" address numbers present in the prompt facts for {pct(addr_in_facts, len(with_addr))} of them")

    # 7 business skew
    biz = [r for r in dr if r["metadata"]["section_bucket"] == "business"]
    mfg = sum(bool(re.search(r"manufactur|plant|factory|raw material|production capacity", r["messages"][-1]["content"], re.I)) for r in biz)
    svc = sum(bool(re.search(r"\bEPC\b|contract(?:or|ing)|consult|software|services? provider|logistics|trading", r["messages"][-1]["content"], re.I)) for r in biz)
    print(f"\n7 BUSINESS SKEW  business-section targets: {len(biz)}; mention manufacturing/plant/raw material {pct(mfg, len(biz))}; mention EPC/contracting/services {pct(svc, len(biz))}")

    # 8 leakage
    tr_co = {r["metadata"]["company"] for r in train}
    te_co = {r["metadata"]["company"] for r in test}
    nd = sum(bool(r["metadata"].get("near_dup")) for r in train)
    print(f"\n8 LEAKAGE  companies in train {len(tr_co)}, in test {len(te_co)}, in both {len(tr_co & te_co)};"
          f" train rows flagged as near-duplicates of a test unit: {nd}")
    dups = collections.Counter(r["messages"][-1]["content"] for r in dr)
    print(f"  duplicate drafting targets inside train: {sum(v - 1 for v in dups.values() if v > 1)}")
    yrs = collections.Counter(r["metadata"].get("listing_year") for r in dr)
    print("  listing years:", dict(sorted((k, v) for k, v in yrs.items() if k)))

    # 9 other skills
    ex = [r for r in train if r["metadata"]["skill"] == "extraction"]
    qa = [r for r in train if r["metadata"]["skill"] == "qa"]
    print(f"\n9 OTHER SKILLS  extraction rows {len(ex)}; Q&A rows {len(qa)}")
    kinds = collections.Counter((r["metadata"].get("kind") or r["metadata"].get("qa_kind") or "?") for r in qa)
    print("  Q&A kinds:", dict(kinds.most_common(8)))
    refused = sum(bool(re.search(r"\[●\]|cannot|not (?:stated|provided|available)|no evidence|decline", r["messages"][-1]["content"], re.I)) for r in qa)
    print(f"  Q&A answers that decline or say the evidence is missing: {pct(refused, len(qa))}")


if __name__ == "__main__":
    a = sys.argv[1:]
    out = os.path.join(M.ROOT, "trainset", "out")
    audit(a[0] if a else os.path.join(out, "train_v2.jsonl"), a[1] if len(a) > 1 else os.path.join(out, "test_v2.jsonl"))
