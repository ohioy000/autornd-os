"""Write the blind reading packets of the first hold-out re-run. Free.

    python -I first_holdout_packets.py REPO OUT_DIR SEED [RUNS_DIR]

One packet per question (X1 to X42) holding every delivered answer of docs/preregistration-20261123-first-holdout-same-set.md
(invocations FX-1 and FX-2 of RUNS_DIR, default /home/jb/final-runs/firstx), under codes that show neither the draw nor the invocation,
shuffled, with the signed key. The codes, and where each answer came from, are in OUT_DIR/codes.json, which the reader is not
given; a unit that delivered no answer is listed there and not in a packet. OUT_DIR/chunks-items.json lists the packets for
readers, about READ_PER (default 30) answers each.
"""
from __future__ import annotations

import hashlib
import json
import os
import random
import sys
from pathlib import Path

REPO, OUT, SEED = Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3]
RUNS = Path(sys.argv[4]) if len(sys.argv) > 4 else Path("/home/jb/final-runs/firstx")
PER_READER = int(os.environ.get("READ_PER", "30"))
OUT.mkdir(parents=True, exist_ok=True)
Q = {q["id"]: q for q in json.loads((REPO / "evals/professional/holdout-questions.json").read_text())["questions"]}

codes, packets = {}, {}
for inv in ("FX-1", "FX-2"):
    for n, line in enumerate(open(RUNS / inv / "shard-0.jsonl", encoding="utf-8")):
        u = json.loads(line)
        source = f"{RUNS / inv / 'shard-0.jsonl'}#{n}"
        code = hashlib.sha256(f"{SEED}|{source}".encode()).hexdigest()[:8]
        answer = (u.get("answer") or "").strip()
        codes[code] = {"source": source, "question": u["question"], "invocation": inv, "repeat": u.get("repeat"),
                       "status": u.get("status"), "delivered": bool(answer), "error": (u.get("error") or "")[:160]}
        if answer:
            packets.setdefault(u["question"], []).append((code, answer))
(OUT / "codes.json").write_text(json.dumps(codes, indent=1), encoding="utf-8")

rng = random.Random(SEED)
names = []
for qid in sorted(packets, key=lambda s: int(s[1:])):
    q = Q[qid]
    answers = packets[qid]
    rng.shuffle(answers)
    lines = [f"# {qid} (professional-holdout)", "", f"**Question:** {q['question']}", "", "**Key (signed):**"]
    lines += [f"- {item['item']}: {item['answer']}" for item in q["key"]]
    lines += ["", f"**Commonly confused:** {q.get('commonly_confused', '')}", "", f"{len(answers)} answer(s) follow.", ""]
    for code, answer in answers:
        lines += [f"## ANSWER {code}", "", answer, "", "---", ""]
    (OUT / f"professional-holdout__{qid}.md").write_text("\n".join(lines), encoding="utf-8")
    names.append((f"professional-holdout__{qid}.md", len(answers)))
chunks, cur, count = [], [], 0
for name, n in names:
    if cur and count + n > PER_READER:
        chunks.append(cur)
        cur, count = [], 0
    cur.append(name)
    count += n
if cur:
    chunks.append(cur)
(OUT / "chunks-items.json").write_text(json.dumps(chunks, indent=1), encoding="utf-8")
print(f"units {len(codes)}  delivered {sum(c['delivered'] for c in codes.values())}  packets {len(names)}  readers {len(chunks)}")
