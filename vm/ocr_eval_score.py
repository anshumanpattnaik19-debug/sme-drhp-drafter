"""Score OCR on the test set: character error rate against the digital text of each page.

Both engines read the same images: the vision model's transcript (from vm/ocr_eval_vllm.py) and the offline RapidOCR
engine the app falls back to (run here, on the laptop, through ingest/readers.py). Whitespace and table bars are
removed from both sides first, so layout is not scored: only the characters are. CER = edit distance / true length.

    python vm/ocr_eval_score.py build/ocr_eval build/ocr_eval/transcripts_qwen_vl.json
"""
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ingest import readers  # noqa: E402


def norm(s: str) -> str:
    return re.sub(r"[\s|]+", "", s)


def token_recall(text: str, truth_text: str) -> float:
    """Share of the true words (whitespace-split, multiset) that the OCR text contains, whatever their order. This
    isolates reading errors from reading order: a text layer that lists table cells column by column is not penalised
    for the order a row is read in."""
    from collections import Counter
    have, want = Counter(re.findall(r"\w+", text)), Counter(re.findall(r"\w+", truth_text))
    total = sum(want.values())
    return round(sum(min(have[t], n) for t, n in want.items()) / max(1, total), 4)


def edit_distance(a: str, b: str) -> int:
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i] + [0] * len(b)
        for j, cb in enumerate(b, 1):
            cur[j] = min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb))
        prev = cur
    return prev[-1]


def main(eval_dir: Path, transcripts: Path):
    manifest = json.loads((eval_dir / "manifest.json").read_text(encoding="utf-8"))
    qwen = {r["id"]: r["text"] for r in json.loads(transcripts.read_text(encoding="utf-8"))}
    rapid_path = eval_dir / "rapidocr.json"
    if rapid_path.exists():
        rapid = json.loads(rapid_path.read_text(encoding="utf-8"))
    else:
        rapid = {}
        for m in manifest:
            png = (eval_dir / "images" / f"{m['id']}.png").read_bytes()
            rapid[m["id"]] = readers._ocr_image_bytes(png) or ""
            print("rapidocr", m["id"], flush=True)
        rapid_path.write_text(json.dumps(rapid, ensure_ascii=False, indent=1), encoding="utf-8")
    rows, tot = [], {"qwen": [0, 0], "rapid": [0, 0]}
    recall = {"qwen": [0, 0], "rapid": [0, 0]}
    for m in manifest:
        raw_truth = (eval_dir / "truth" / f"{m['id']}.txt").read_text(encoding="utf-8")
        truth = norm(raw_truth)
        row = {"id": m["id"], "chars": len(truth)}
        for name, text in (("qwen", qwen.get(m["id"], "")), ("rapid", rapid.get(m["id"], ""))):
            d = edit_distance(norm(text), truth)
            row[name] = round(d / max(1, len(truth)), 4)
            row[name + "_word_recall"] = token_recall(text, raw_truth)
            tot[name][0] += d
            tot[name][1] += len(truth)
            recall[name][0] += round(row[name + "_word_recall"] * len(re.findall(r"\w+", raw_truth)))
            recall[name][1] += len(re.findall(r"\w+", raw_truth))
        rows.append(row)
        print(f"{m['id']:45s} chars={row['chars']:6d} cer qwen={row['qwen']:.4f} rapid={row['rapid']:.4f}"
              f"  word_recall qwen={row['qwen_word_recall']:.4f} rapid={row['rapid_word_recall']:.4f}", flush=True)
    summary = {name: round(d / max(1, n), 4) for name, (d, n) in tot.items()}
    word = {name: round(d / max(1, n), 4) for name, (d, n) in recall.items()}
    out = {"pages": rows, "overall_cer": summary, "overall_word_recall": word}
    (eval_dir / "results.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
    print("OVERALL CER", summary, "WORD RECALL", word)


if __name__ == "__main__":
    main(Path(sys.argv[1]), Path(sys.argv[2]))
