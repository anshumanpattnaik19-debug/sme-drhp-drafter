"""Sampling plan and training rows (PLAN.md 5.4-5.6).

    sample(units, quotas, cap=6, seed) -> [unit with skill]       at most `cap` rows per company, 2025-26 weighted x2
    build_rows(sampled, all_units, responses, precedent_pool, split, seed) -> (rows, report)

Drafting rows: input = section outline, sub-heading, previous-unit summary, the router's facts from ALL of the
company's units (own facts plus distractors) and, in half the rows, one precedent (same section, another train
company); target = the masked sub-section text. Extraction rows: input = the raw passage (30% OCR-noised);
target = the precise facts as JSON.
"""
from __future__ import annotations

import json
import random
import re
import zlib
from collections import Counter, defaultdict

from draft.outline import SECTION_BY_KEY
from draft.router import route
from rag.index import BM25

from .clean import strip_page_refs, strip_tables
from .corpus import BUDGET_GROUP, CORE
from .facts import apply_gates, normalise, precise, _num, parse_dates, _tokens
from .mask import mask
from .noise import ocr_noise
from .prompts import EXTRACT_SYSTEM, drafting_messages, extraction_messages, summary_of
from .segment import tokens

TRAIN_QUOTAS = {"extraction": 800, "risk_factors": 150, "business": 150, "objects": 150, "management": 150,
                "promoters_history": 150, "industry": 50, "mdna": 50, "litigation": 50, "approvals": 50, "summary": 50}
TEST_QUOTAS = {"extraction": 50, "risk_factors": 30, "business": 30, "objects": 30, "management": 30, "promoters_history": 30}
MAX_SEQ = 6144
ROUTER_K = 40          # reported router recall: share of the unit's own facts in the router's top 40
MAX_OWN = 40           # a unit with more facts than this is not used for drafting (it would not fit with distractors)
MAX_INPUT = 60         # facts in one drafting input: own + distractors (data/prompts.MAX_FACTS)
MIN_DRAFT_WORDS = 40   # a drafting target with fewer words once its tables are cut was mostly a table: not a row


def bucket(u):
    return BUDGET_GROUP.get(u["outline_key"], u["outline_key"])


def prepare(unit):
    """Unit dict + DRHP-stage target, masked values and the previous-unit summary."""
    target, masked = mask(unit["raw"])
    prev = mask(unit["prev_text"])[0] if unit.get("prev_text") else ""
    return {**unit, "target": target, "masked_values": masked, "prev_summary": summary_of(prev) if prev else ""}


def sample(units, quotas, cap=6, seed=13, context_min=0):
    rnd = random.Random(seed)
    w = lambda u: 2.0 if u["listing_year"] >= 2025 else 1.0  # noqa: E731
    pools = defaultdict(list)
    for u in units:
        if u["outline_key"] in ("risk_factors",) and u["heading"] == "Introduction":
            continue                                    # boilerplate opening paragraph
        pools[bucket(u)].append(u)
    for k in pools:                                     # weighted shuffle (Efraimidis-Spirakis keys)
        pools[k].sort(key=lambda u: -rnd.random() ** (1 / w(u)))
    used, per_co, picked = set(), Counter(), []
    need = {k: v for k, v in quotas.items() if k != "extraction"}
    ptr = defaultdict(int)
    progress = True
    while progress and any(need.values()):
        progress = False
        for k in list(need):
            if need[k] <= 0:
                continue
            pool = pools.get(k, [])
            while ptr[k] < len(pool):
                u = pool[ptr[k]]
                ptr[k] += 1
                if u["unit_id"] not in used and per_co[u["doc_id"]] < cap - 1:   # keep one slot for extraction
                    used.add(u["unit_id"])
                    per_co[u["doc_id"]] += 1
                    picked.append({**u, "skill": "drafting"})
                    need[k] -= 1
                    progress = True
                    break
    ext_pool = [u for k in pools for u in pools[k] if u["unit_id"] not in used]
    ext_pool.sort(key=lambda u: -rnd.random() ** (1 / w(u)))
    n_ext = quotas.get("extraction", 0)
    for u in ext_pool:
        if n_ext <= 0:
            break
        if per_co[u["doc_id"]] < cap:
            used.add(u["unit_id"])
            per_co[u["doc_id"]] += 1
            picked.append({**u, "skill": "extraction"})
            n_ext -= 1
    # context units: teacher facts only, used as distractors, for companies with few sampled units (no rows)
    n_ctx = 0
    if context_min:
        have = Counter(u["doc_id"] for u in picked)
        for u in ext_pool:
            if u["unit_id"] not in used and have[u["doc_id"]] and have[u["doc_id"]] < context_min:
                used.add(u["unit_id"])
                have[u["doc_id"]] += 1
                picked.append({**u, "skill": "context"})
                n_ctx += 1
    short = {k: v for k, v in need.items() if v > 0}
    return picked, {"short_of_quota": short, "extraction_short": max(0, n_ext), "companies": len(per_co),
                    "max_rows_per_company": max(per_co.values()) if per_co else 0, "context_units": n_ctx}


class PrecedentPool:
    """Train-split units by section, searched by sub-heading (BM25) for a same-heading precedent from another company."""

    def __init__(self, train_units):
        self.by_sec = defaultdict(list)
        for u in train_units:
            self.by_sec[u["outline_key"]].append(u)
        self.bm = {k: BM25([f"{u['heading']} {u['heading']} {u['raw'][:300]}" for u in us]) for k, us in self.by_sec.items() if us}

    def find(self, unit):
        us = self.by_sec.get(unit["outline_key"], [])
        if not us:
            return None
        sc = self.bm[unit["outline_key"]].scores(unit["heading"])
        order = sorted(range(len(us)), key=lambda i: -sc[i])
        for i in order[:50]:
            if us[i]["doc_id"] != unit["doc_id"] and sc[i] > 0:
                return mask(us[i]["raw"])[0]
        return None


def _approx_tokens(messages):
    return sum(tokens(m["content"]) for m in messages)


def build_rows(sampled, responses, precedents: PrecedentPool, split, seed=13, ocr_share=0.3, precedent_share=0.5):
    rnd = random.Random(seed + (1 if split == "test" else 0))
    resp = {r["unit_id"]: r for r in responses}
    report = {"units": sum(u["skill"] != "context" for u in sampled), "context_units": sum(u["skill"] == "context" for u in sampled), "no_response": 0, "parse_failed": 0, "gate_failed": 0, "gate_fail_reasons": Counter(),
              "rows": Counter(), "router_recall": [], "distractor_share": [], "precision": [], "coverage_figures": [],
              "coverage_names": [], "dropped": Counter(), "truncated": 0, "facts_in": 0, "tables_stripped": 0, "page_refs_stripped": 0, "table_only": 0}
    kept_by_unit, gates = {}, {}
    for u in sampled:
        r = resp.get(u["unit_id"])
        if not r:
            report["no_response"] += 1
            continue
        if r.get("facts") is None:
            report["parse_failed"] += 1
            continue
        if u["skill"] == "drafting":
            target, n_tables = strip_tables(u["target"])
            target, n_pages = strip_page_refs(target)
            if n_tables:
                report["tables_stripped"] += 1
                if len(re.findall(r"[A-Za-z]{2,}", target)) < MIN_DRAFT_WORDS:
                    report["table_only"] += 1
                    continue
            if n_pages:
                report["page_refs_stripped"] += 1
            if n_tables or n_pages:
                u = {**u, "target": target}
        facts, _errs = normalise(r["facts"])
        kept, g = apply_gates(facts, u["raw"], u["target"], u["masked_values"])
        if u["skill"] == "context":                   # distractor source only: precise facts, no row
            for f in kept:
                f["_unit"] = u["unit_id"]
            kept_by_unit[u["unit_id"]] = (u, kept, facts)
            continue
        gates[u["unit_id"]] = g
        report["facts_in"] += g["facts_in"]
        report["coverage_figures"].append(g["coverage_figures"])
        report["coverage_names"].append(g["coverage_names"])
        for k, v in g["dropped"].items():
            report["dropped"][k] += v
        if u["skill"] == "drafting" and not g["pass"]:
            report["gate_failed"] += 1
            for k in ("figures", "dates", "names"):
                if g["missing"][k]:
                    report["gate_fail_reasons"][k] += 1
            if not g["facts_kept"]:
                report["gate_fail_reasons"]["no_facts"] += 1      # pure boilerplate: templates cover it
            continue
        for f in kept:
            f["_unit"] = u["unit_id"]
        kept_by_unit[u["unit_id"]] = (u, kept, facts)
    pool_by_co = defaultdict(list)
    for uid, (u, kept, _f) in kept_by_unit.items():
        for i, f in enumerate(kept):
            pool_by_co[u["doc_id"]].append({**f, "id": f"{uid}#{i}", "file_id": uid, "snippet": ""})
    rows, ablation = [], []
    for uid, (u, kept, facts) in kept_by_unit.items():
        if u["skill"] == "context":
            continue
        meta = {"skill": u["skill"], "split": split, "unit_id": uid, "doc_id": u["doc_id"], "company": u["company"],
                "listing_year": u["listing_year"], "section": u["outline_key"], "section_bucket": bucket(u),
                "heading": u["heading"], "core": u["section_key"] in CORE, "gates": gates.get(uid)}
        if u["skill"] == "extraction":
            src_nums = {k for k in (_num(x) for x in re.findall(r"\d[\d,]*(?:\.\d+)?", u["raw"])) if k is not None}
            target_facts = [f for f in facts if precise(f, u["raw"], src_nums, parse_dates(u["raw"]), set(_tokens(u["raw"])))]
            noisy = rnd.random() < ocr_share
            text = ocr_noise(u["raw"], seed=zlib.crc32(uid.encode())) if noisy else u["raw"]
            msgs = extraction_messages(text, u["section_title"])
            out = json.dumps({"facts": [{k: f[k] for k in ("type", "label", "value", "unit", "period") if f.get(k)} for f in target_facts]},
                             ensure_ascii=False)
            meta.update(ocr_noise=noisy, n_facts=len(target_facts))
        else:
            sec = SECTION_BY_KEY[u["outline_key"]]
            pool = pool_by_co[u["doc_id"]]
            query = f"{u['heading']} {sec['query']}"
            routed = route(pool, query, k=ROUTER_K)
            own_ids = {f"{uid}#{i}" for i in range(len(kept))}
            if len(own_ids) > MAX_OWN:                 # too fact-dense for one input without losing coverage
                report["too_many_facts"] = report.get("too_many_facts", 0) + 1
                continue
            recall = len(own_ids & {f["id"] for f in routed}) / len(own_ids) if own_ids else 1.0
            # about half distractors: the router's best-ranked facts from the company's other units (hard negatives)
            own = [f for f in pool if f["id"] in own_ids][:MAX_OWN]
            ranked = route(pool, query, k=len(pool))
            n_dis = min(len(own), MAX_INPUT - len(own))
            dis = [f for f in ranked if f["id"] not in own_ids][:n_dis]
            if len(dis) < n_dis:                       # the router found too few: fill with the company's other facts
                rest = [f for f in pool if f["id"] not in own_ids and f not in dis]
                rnd.shuffle(rest)
                dis += rest[:n_dis - len(dis)]
            inputs = own + dis
            rnd.shuffle(inputs)                        # position must not reveal which facts are the unit's own
            n_dis = sum(f["id"] not in own_ids for f in inputs)
            prec = precedents.find(u) if rnd.random() < precedent_share else None
            msgs = drafting_messages(u["company"], u["section_title"], u["outline"], u["heading"], inputs, u["prev_summary"], prec)
            out = u["target"]
            # ablation 1 (PLAN.md 7.7): the same row without distractor facts
            own_only = [f for f in inputs if f["id"] in own_ids]
            ablation.append({"id": f"{split}-{uid}-dra-nodis", "metadata": {**meta, "ablation": "no_distractors"},
                             "messages": drafting_messages(u["company"], u["section_title"], u["outline"], u["heading"], own_only,
                                                           u["prev_summary"], prec) + [{"role": "assistant", "content": out}]})
            if _approx_tokens(msgs) + tokens(out) > MAX_SEQ and prec:
                msgs = drafting_messages(u["company"], u["section_title"], u["outline"], u["heading"], inputs, u["prev_summary"], None)
                prec = None
                report["truncated"] += 1
            report["router_recall"].append(recall)
            report["distractor_share"].append(n_dis / len(inputs) if inputs else 0)
            meta.update(n_facts=len(inputs), n_own=len(own_ids), n_distractors=n_dis, router_recall=round(recall, 3),
                        precedent=bool(prec), continuation=u.get("continuation", False))
        msgs = msgs + [{"role": "assistant", "content": out}]
        meta["n_tokens_est"] = _approx_tokens(msgs)
        if meta["n_tokens_est"] > MAX_SEQ:
            report["truncated"] += 1
            continue
        report["rows"][u["skill"] if u["skill"] == "extraction" else bucket(u)] += 1
        rows.append({"id": f"{split}-{uid}-{u['skill'][:3]}", "messages": msgs, "metadata": meta})
    avg = lambda xs: round(sum(xs) / len(xs), 3) if xs else None  # noqa: E731
    for k in ("router_recall", "distractor_share", "coverage_figures", "coverage_names"):
        report[k] = avg(report[k])
    # per fact, not averaged per unit: a unit with no facts has no precision (it used to count as 0)
    report["precision"] = round(1 - report["dropped"]["imprecise"] / report["facts_in"], 3) if report["facts_in"] else None
    report["rows"] = dict(report["rows"])
    report["gate_fail_reasons"] = dict(report["gate_fail_reasons"])
    report["dropped"] = dict(report["dropped"])
    report["extract_system"] = EXTRACT_SYSTEM[:60]
    report["ablation_rows"] = ablation
    return rows, report
