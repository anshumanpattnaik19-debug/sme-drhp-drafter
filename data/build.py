"""Build the DRHP training set, stage by stage (each stage reads the previous stage's files).

    python -m data.build units                    # sections -> cleaned, masked sub-section units (both splits)
    python -m data.build sample                   # sampling plan -> work/sampled_{split}.jsonl + work/teacher_jobs.jsonl
    python -m teacher.driver --jobs work/teacher_jobs.jsonl --out work/teacher_responses.jsonl --endpoint ... --model ...
    python -m data.build rows                     # gates, router, distractors, precedents, MinHash -> out/
    python -m data.build dry-run --n 20           # all of the above on 20 units with the in-process mock teacher

Outputs (out/): train.jsonl, test.jsonl (chat rows with metadata), MANIFEST.json, GATES_REPORT.md.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from collections import Counter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from data.clean import build_vocab  # noqa: E402
from data.corpus import load_sections  # noqa: E402
from data.facts import set_common_words  # noqa: E402
from data.minhash import flag_near_duplicates  # noqa: E402
from data.pairs import TEST_QUOTAS, TRAIN_QUOTAS, PrecedentPool, build_rows, prepare, sample  # noqa: E402
from data.segment import segment  # noqa: E402

WORK = os.path.join(ROOT, "trainset", "work")
OUT = os.path.join(ROOT, "trainset", "out")


def _w(path, rows):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")


def _r(path):
    if not os.path.isfile(path):
        return []
    with open(path, encoding="utf-8") as fh:
        return [json.loads(ln) for ln in fh if ln.strip()]


def write_common_words(texts, path, min_count=25):
    """Words written in lower case at least `min_count` times: the name detector treats them as ordinary words."""
    import re
    c = Counter()
    for t in texts:
        c.update(re.findall(r"\b[a-z][a-z'-]+\b", t))
    words = sorted(w for w, n in c.items() if n >= min_count)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(words, fh)
    return len(words)


def stage_units(work=WORK, limit_docs=None, log=print):
    stats = {}
    for split in ("train", "test"):
        t0 = time.time()
        secs = load_sections(split, limit_docs=limit_docs)
        vocab = build_vocab(s.text for s in secs)
        units = []
        for s in secs:
            units += [prepare(u.to_dict()) for u in segment(s, vocab)]
        _w(os.path.join(work, f"units_{split}.jsonl"), units)
        if split == "train":
            n = write_common_words((s.text for s in secs), os.path.join(work, "common_words.json"))
            set_common_words(json.load(open(os.path.join(work, "common_words.json"), encoding="utf-8")))
            log(f"common words: {n}")
        by = Counter(u["outline_key"] for u in units)
        stats[split] = {"sections": len(secs), "docs": len({s.doc_id for s in secs}), "units": len(units), "by_section": dict(by),
                        "masked_units": sum(bool(u["masked_values"]) or "[●]" in u["target"] for u in units)}
        log(f"units {split}: {len(units)} from {len(secs)} sections of {stats[split]['docs']} documents ({time.time() - t0:.0f}s)")
    with open(os.path.join(work, "units_stats.json"), "w", encoding="utf-8") as fh:
        json.dump(stats, fh, indent=1)
    return stats


def stage_sample(work=WORK, quotas=None, seed=13, log=print):
    plan = {}
    jobs = []
    for split, q in (("train", TRAIN_QUOTAS), ("test", TEST_QUOTAS)):
        units = _r(os.path.join(work, f"units_{split}.jsonl"))
        picked, info = sample(units, (quotas or {}).get(split, q), seed=seed, context_min=3 if split == "test" else 0)
        _w(os.path.join(work, f"sampled_{split}.jsonl"), picked)
        jobs += [{k: u[k] for k in ("unit_id", "section_title", "heading", "raw")} for u in picked]
        plan[split] = {"rows_planned": len(picked), **info, "by_skill": dict(Counter(u["skill"] for u in picked))}
        log(f"sample {split}: {len(picked)} units, {info['companies']} companies, short of quota: {info['short_of_quota'] or 'none'}")
    _w(os.path.join(work, "teacher_jobs.jsonl"), jobs)
    with open(os.path.join(work, "sample_plan.json"), "w", encoding="utf-8") as fh:
        json.dump(plan, fh, indent=1)
    log(f"teacher jobs: {len(jobs)} -> {os.path.join(work, 'teacher_jobs.jsonl')}")
    return plan


def stage_rows(work=WORK, out=OUT, responses_path=None, seed=13, log=print):
    responses = _r(responses_path or os.path.join(work, "teacher_responses.jsonl"))
    train_units = _r(os.path.join(work, "units_train.jsonl"))
    pool = PrecedentPool(train_units)
    reports, all_rows = {}, {}
    for split in ("train", "test"):
        sampled = _r(os.path.join(work, f"sampled_{split}.jsonl"))
        rows, rep = build_rows(sampled, responses, pool, split, seed=seed)
        ablation = rep.pop("ablation_rows")
        if split == "train":   # ablation 1: drafting rows without distractors, extraction rows unchanged
            _w(os.path.join(out, "train_no_distractors.jsonl"),
               [r for r in rows if r["metadata"]["skill"] == "extraction"] + ablation)
        all_rows[split], reports[split] = rows, rep
    # near-duplicate flags: test drafting targets against every train unit
    test_draft = [{"unit_id": r["metadata"]["unit_id"], "target": r["messages"][-1]["content"], "row": r}
                  for r in all_rows["test"] if r["metadata"]["skill"] == "drafting"]
    flag_near_duplicates([{"unit_id": u["unit_id"], "target": u["target"]} for u in train_units], test_draft)
    for t in test_draft:
        t["row"]["metadata"].update(near_dup=t["near_dup"], near_dup_of=t["near_dup_of"], near_dup_j=t["near_dup_j"])
    leak = Counter((t["row"]["metadata"]["section_bucket"], t["near_dup"]) for t in test_draft)
    train_cos = {r["metadata"]["doc_id"] for r in all_rows["train"]}
    test_cos = {r["metadata"]["doc_id"] for r in all_rows["test"]}
    assert not train_cos & test_cos, "a company is in both splits"
    for split in ("train", "test"):
        _w(os.path.join(out, f"{split}.jsonl"), all_rows[split])
    manifest = {
        "built_at": time.strftime("%Y-%m-%dT%H:%M:%S"), "seed": seed,
        "teacher_models": sorted({r.get("model") for r in responses if r.get("model")}),
        "splits": {s: {"rows": len(all_rows[s]), "companies": len({r["metadata"]['doc_id'] for r in all_rows[s]}),
                       "by_skill": dict(Counter(r["metadata"]["skill"] for r in all_rows[s])),
                       "by_bucket": dict(Counter(r["metadata"]["section_bucket"] for r in all_rows[s] if r["metadata"]["skill"] == "drafting")),
                       "max_tokens_est": max((r["metadata"]["n_tokens_est"] for r in all_rows[s]), default=0),
                       "precedent_rows": sum(bool(r["metadata"].get("precedent")) for r in all_rows[s])} for s in all_rows},
        "gates": {s: {k: v for k, v in reports[s].items() if k != "extract_system"} for s in reports},
        "near_duplicates_test": {f"{b}|{'near_dup' if d else 'novel'}": n for (b, d), n in sorted(leak.items())},
        "companies_overlap": 0,
    }
    with open(os.path.join(out, "MANIFEST.json"), "w", encoding="utf-8") as fh:
        json.dump(manifest, fh, indent=1, ensure_ascii=False)
    write_report(manifest, os.path.join(out, "GATES_REPORT.md"))
    for s in ("train", "test"):
        g = reports[s]
        log(f"rows {s}: {len(all_rows[s])} · gate failures {g['gate_failed']} of {g['units']} · precision {g['precision']} · "
            f"router recall {g['router_recall']} · distractor share {g['distractor_share']}")
    return manifest


def write_report(m, path):
    L = ["# Training set: gates and composition", "", f"Built {m['built_at']} · teacher: {', '.join(m['teacher_models']) or 'none'}", ""]
    L += ["| split | rows | companies | extraction | drafting | precedent rows | max tokens (est.) |", "|---|---|---|---|---|---|---|"]
    for s, v in m["splits"].items():
        L.append(f"| {s} | {v['rows']} | {v['companies']} | {v['by_skill'].get('extraction', 0)} | {v['by_skill'].get('drafting', 0)} | "
                 f"{v['precedent_rows']} | {v['max_tokens_est']} |")
    L += ["", "## Gates", "", "| split | units | no response | parse failed | gate failed | precision | figure coverage | name coverage | router recall | distractor share |",
          "|---|---|---|---|---|---|---|---|---|---|"]
    for s, g in m["gates"].items():
        L.append(f"| {s} | {g['units']} | {g['no_response']} | {g['parse_failed']} | {g['gate_failed']} | {g['precision']} | "
                 f"{g['coverage_figures']} | {g['coverage_names']} | {g['router_recall']} | {g['distractor_share']} |")
    L += ["", "Gate failures by missing kind: " + "; ".join(f"{s}: {g['gate_fail_reasons']}" for s, g in m["gates"].items()),
          "", "Facts dropped: " + "; ".join(f"{s}: {g['dropped']}" for s, g in m["gates"].items()),
          "", "Precision is per fact (share of the teacher's facts found in the source).",
          "", "Drafting targets with flattened tables cut out (the app builds tables in code): " +
          "; ".join(f"{s}: {g.get('tables_stripped', 0)} (of which {g.get('table_only', 0)} mostly table, not rows)"
                    for s, g in m["gates"].items()), "",
          "## Drafting rows by section", ""]
    for s, v in m["splits"].items():
        L.append(f"- {s}: " + ", ".join(f"{k} {n}" for k, n in sorted(v["by_bucket"].items())))
    L += ["", "## Near-duplicate test targets (MinHash, Jaccard >= 0.6 to a train unit)", ""]
    L += [f"- {k}: {n}" for k, n in m["near_duplicates_test"].items()] or ["- none"]
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(L) + "\n")


def dry_run(n=20, limit_docs=6, work=None, out=None, log=print):
    """20 units end to end with the in-process mock teacher: proves every stage runs and the gates behave."""
    from fastapi.testclient import TestClient
    from mock.server import app
    from teacher.driver import run
    work = work or os.path.join(ROOT, "trainset", "dry_run", "work")
    out = out or os.path.join(ROOT, "trainset", "dry_run", "out")
    stage_units(work, limit_docs=limit_docs, log=log)
    per = max(1, n // 10)
    quotas = {"train": {"extraction": per * 3, "risk_factors": per, "business": per, "objects": per, "management": per, "promoters_history": per},
              "test": {"extraction": per, "risk_factors": per, "business": per, "objects": per}}
    stage_sample(work, quotas=quotas, log=log)
    jobs = _r(os.path.join(work, "teacher_jobs.jsonl"))
    resp_path = os.path.join(work, "teacher_responses.jsonl")
    if os.path.exists(resp_path):
        os.remove(resp_path)
    run(jobs, resp_path, "/v1", "mock-teacher", client=TestClient(app), log=log)
    return stage_rows(work, out, resp_path, log=log)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("stage", choices=["units", "sample", "rows", "dry-run"])
    ap.add_argument("--n", type=int, default=20)
    ap.add_argument("--limit-docs", type=int)
    ap.add_argument("--responses")
    a = ap.parse_args()
    if a.stage == "units":
        stage_units(limit_docs=a.limit_docs)
    elif a.stage == "sample":
        stage_sample()
    elif a.stage == "rows":
        stage_rows(responses_path=a.responses)
    else:
        m = dry_run(a.n, limit_docs=a.limit_docs or 6)
        print(json.dumps(m["splits"], indent=1))


if __name__ == "__main__":
    main()
