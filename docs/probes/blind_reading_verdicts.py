"""Join blind readers' verdicts to the runs they came from. Free.

    python -I docs/probes/blind_reading_verdicts.py REPO CODES_JSON VERDICTS_GLOB [CODE ...]

CODES_JSON is the file blind_reading_packets.py kept back from the readers.
VERDICTS_GLOB matches the readers' files, each a JSON object of
code -> {"verdict": right | wrong | partly | unclear, "stated", "evidence",
"note"}. It prints, for each question and each arm, the answers right of
those delivered; every answer not marked right with its arm, its run and
the cautions its delivery carried; every answer where the reader and the
free figure check disagree; and a random dozen marked right, for the second
reader. With CODEs it prints those answers' first 1,500 characters.

An arm is the part of a run's directory name after the last hyphen.
The reading is two readers (D50): the blind reader's verdict, and a second
reader on every answer not marked right, every disagreement with the figure
check, and the sample.
"""
from __future__ import annotations

import glob
import json
import random
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

REPO = Path(sys.argv[1]).resolve()
codes = json.loads(Path(sys.argv[2]).read_text())
SHOW = set(sys.argv[4:])
verdicts: dict = {}
for path in sorted(glob.glob(sys.argv[3])):
    verdicts.update(json.loads(Path(path).read_text()))
keys = {q["id"]: q for name in ("questions.json", "hard-questions.json",
                                "misleading-questions.json")
        for q in json.loads((REPO / "evals/professional" / name).read_text())["questions"]}
NUMBER = re.compile(r"\d[\d,]*(?:\.\d+)?")
_units: dict[str, list] = {}


def unit(source: str) -> dict:
    path, n = source.rsplit("#", 1)
    if path not in _units:
        _units[path] = [json.loads(line) for line in open(path, encoding="utf-8")]
    return _units[path][int(n)]


def arm(source: str) -> str:
    return Path(source.rsplit("#", 1)[0]).parent.name.rsplit("-", 1)[-1]


def numbers(text: str) -> list[str]:
    return list(dict.fromkeys(n.replace(",", "").rstrip(".") for n in NUMBER.findall(text)))


def holds(number: str, text: str) -> bool:
    return re.search(rf"(?<![\d.]){re.escape(number)}(?!\d|\.\d)",
                     text.replace(",", "")) is not None


table: dict = defaultdict(Counter)
not_right, disagree, right = [], [], []
for code, meta in codes.items():
    where = (meta["question"], arm(meta["source"]))
    if not meta["delivered"]:
        table[where]["undelivered"] += 1
        continue
    verdict = (verdicts.get(code) or {}).get("verdict", "MISSING")
    table[where][verdict] += 1
    u = unit(meta["source"])
    key = [n for item in keys[meta["question"]]["key"] for n in numbers(item["answer"])]
    pointer = all(holds(n, u["answer"]) for n in key)
    if verdict == "right":
        right.append(code)
    else:
        not_right.append((code, meta, verdict, u))
    if (verdict == "right") != pointer:
        disagree.append((meta["question"], code, verdict,
                         [n for n in key if not holds(n, u["answer"])]))
    if code in SHOW:
        print(f"\n===== {code} {meta['question']} {verdict} | "
              f"{(verdicts.get(code) or {}).get('stated')}")
        print(u["answer"][:1500])

arms = sorted({a for _, a in table})
questions = sorted({q for q, _ in table}, key=lambda q: (q[0], int(q[1:])))
print("question | " + " | ".join(arms) + "   (right of delivered)")
totals: Counter = Counter()
for q in questions:
    cells = []
    for a in arms:
        row = table[(q, a)]
        delivered = sum(v for k, v in row.items() if k != "undelivered")
        totals[a, "right"] += row["right"]
        totals[a, "delivered"] += delivered
        totals[a, "undelivered"] += row["undelivered"]
        cells.append(f"{row['right']}/{delivered}"
                     + (f" (+{row['undelivered']} undelivered)" if row["undelivered"] else ""))
    print(q, "|", " | ".join(cells))
print("ALL |", " | ".join(
    f"{totals[a, 'right']}/{totals[a, 'delivered']}"
    + (f" (+{totals[a, 'undelivered']} undelivered)" if totals[a, "undelivered"] else "")
    for a in arms))
print("verdicts missing:", [c for c, m in codes.items() if m["delivered"] and c not in verdicts])
for code, meta, verdict, u in not_right:
    print(f"\nNOT RIGHT {meta['question']} {arm(meta['source'])} r{meta['repeat']} "
          f"{code} {verdict} | {(verdicts.get(code) or {}).get('stated', '')[:160]}")
    for caution in u.get("cautions") or []:
        print("    caution:", caution[:260])
print("\nreader and figure check disagree:", len(disagree))
for item in disagree:
    print("  ", item)
random.seed(sys.argv[2])
print("sample for the second reader:", " ".join(random.sample(right, min(12, len(right)))))
