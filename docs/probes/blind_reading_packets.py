"""Write blind reading packets for a run on a professional set. Free.

    python -I blind_reading_packets.py REPO SET_FILE OUT_DIR SEED UNITS_GLOB [UNITS_GLOB ...]

For each question it writes OUT_DIR/<id>.md: the question, the signed key,
the commonly confused figure, and every delivered answer under a code that
does not show which arm or run it came from, in a shuffled order. The codes
are kept in OUT_DIR/codes.json, which the reader is not given. A unit that
delivered no answer is listed in codes.json and not in a packet.
"""
from __future__ import annotations

import glob
import hashlib
import json
import random
import sys
from pathlib import Path

REPO, SET_FILE, OUT, SEED = Path(sys.argv[1]), sys.argv[2], Path(sys.argv[3]), sys.argv[4]
OUT.mkdir(parents=True, exist_ok=True)
keys = {}
for name in SET_FILE.split(","):
    for q in json.loads((REPO / "evals/professional" / name).read_text())["questions"]:
        keys[q["id"]] = q
units = []
for pattern in sys.argv[5:]:
    for path in sorted(glob.glob(pattern)):
        if "phases" in path:
            continue
        for n, line in enumerate(open(path, encoding="utf-8")):
            unit = json.loads(line)
            unit["_source"] = f"{path}#{n}"
            units.append(unit)
codes = {}
by_question: dict[str, list] = {}
for unit in units:
    code = hashlib.sha256(f"{SEED}|{unit['_source']}".encode()).hexdigest()[:8]
    answer = unit.get("answer") or ""
    # A harness unit names its question under "question"; a frontier-direct
    # row (frontier_direct_probe.py) names it under "id".
    qid = unit.get("question") or unit.get("id")
    codes[code] = {"source": unit["_source"], "question": qid,
                   "repeat": unit.get("repeat"), "status": unit.get("status"),
                   "delivered": bool(answer)}
    if answer and qid in keys:
        by_question.setdefault(qid, []).append((code, answer))
(OUT / "codes.json").write_text(json.dumps(codes, indent=1))
rng = random.Random(SEED)
for qid, answers in by_question.items():
    q = keys[qid]
    rng.shuffle(answers)
    lines = [f"# {qid}", "", f"**Question:** {q['question']}", "", "**Key (signed):**"]
    lines += [f"- {item['item']}: {item['answer']}" for item in q["key"]]
    lines += ["", f"**Commonly confused:** {q.get('commonly_confused', '')}", "",
              f"{len(answers)} answers follow.", ""]
    for code, answer in answers:
        lines += [f"## ANSWER {code}", "", answer.strip(), "", "---", ""]
    (OUT / f"{qid}.md").write_text("\n".join(lines))
    print(qid, len(answers), "answers", (OUT / f"{qid}.md").stat().st_size, "bytes")
