"""The second reading's screen for the final tally: which answers to read first, and a seeded sample. Free.

    python -I docs/probes/final_tally_screen.py REPO CODES_JSON VERDICTS_GLOB SEED [N_SAMPLE]

A screen is never the result (D50): the two readings are. For every delivered answer the blind readers marked right it
says whether the answer's text carries a number of each key item (a figure the key gives and the answer never states),
whether a key item that says the document states no such figure is matched by an answer that says so (analysis only:
the words are looked for here to choose what to read, no verdict is made from them), and it draws N_SAMPLE more
right answers at random (default 30, seeded). The executor reads every answer not right, every flagged answer and the
sample, against the keys, and records code -> {"verdict": ...} in the final file.
"""
from __future__ import annotations

import glob
import json
import random
import re
import sys
from pathlib import Path

REPO, CODES = Path(sys.argv[1]), json.loads(Path(sys.argv[2]).read_text())
SEED = sys.argv[4]
N_SAMPLE = int(sys.argv[5]) if len(sys.argv) > 5 else 30
verdicts: dict = {}
for path in sorted(glob.glob(sys.argv[3])):
    verdicts.update({k: v for k, v in json.loads(Path(path).read_text()).items() if isinstance(v, dict)})

PRO = {"professional": "questions.json", "professional-hard": "hard-questions.json",
       "professional-misleading": "misleading-questions.json", "professional-holdout": "holdout-questions.json",
       "professional-holdout-2": "holdout2-questions.json"}
KEYS = {(s, q["id"]): q for s, f in PRO.items()
        for q in json.loads((REPO / "evals/professional" / f).read_text())["questions"]}
NUM = re.compile(r"(?<![\w.])\d[\d,]*(?:\.\d+)?")
ABSENT_KEY = re.compile(r"\b(none|no such|not stated|states no|does not state|no figure|no value|not specified)\b", re.I)
ABSENT_ANSWER = re.compile(r"(not stated|does not state|do not state|states no|no such|none stated|not specified|not provided|"
                           r"does not (?:specify|provide|give|contain|set)|no (?:figure|value|limit|rule|requirement))", re.I)


def numbers(text: str) -> set[str]:
    return {n.replace(",", "").rstrip(".") for n in NUM.findall(text)}


def answer_of(source: str) -> str:
    path, n = source.rsplit("#", 1)
    return (json.loads(open(path, encoding="utf-8").read().splitlines()[int(n)]).get("answer") or "")


rights = [(c, m) for c, m in CODES.items() if m["delivered"] and "403" not in (m.get("error") or "")
          and verdicts.get(c, {}).get("verdict") == "right"]
flagged = []
for code, meta in rights:
    q = KEYS.get((meta["set"], meta["question"]))
    if q is None:
        continue          # tier 2, golden and tier 4 have keys of other shapes; they are read in full
    text = answer_of(meta["source"])
    have = numbers(text)
    why = []
    for item in q["key"]:
        key_text = str(item["answer"])
        if ABSENT_KEY.search(key_text) and not re.search(r"\d", key_text):
            if not ABSENT_ANSWER.search(text):
                why.append(f"trap item '{item['item']}': no statement that it is absent")
        else:
            need = numbers(key_text)
            if need and not (need & have):
                why.append(f"item '{item['item']}': none of {sorted(need)[:4]} in the answer text")
    if why:
        flagged.append((code, meta["set"], meta["question"], why))
print(f"right answers by the blind readers (made by the tally and arm E): {len(rights)}")
print(f"FLAGGED by the screen ({len(flagged)}), to be read first:")
for code, s, q, why in flagged:
    print(f"  {s} {q} {code}: {'; '.join(why)[:200]}")
rng = random.Random(SEED)
pool = [c for c, _ in rights if c not in {f[0] for f in flagged}]
sample = rng.sample(pool, min(N_SAMPLE, len(pool)))
print(f"SEEDED SAMPLE ({len(sample)} of the {len(pool)} unflagged right answers, seed {SEED}):")
print("  " + " ".join(sample))
