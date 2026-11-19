"""Where the harness's hold-out misses fell, and what went with them. Free.

    python -I docs/probes/holdout_miss_classification.py [TRACES_DIR]

Reads the byte-identical traces of the hold-out run of 2026-11-17 in
docs/traces/ (the shards, the phase rows exported from each shard's database,
the readers' codes, the blind verdicts and the executor's second reading) and
prints three things.

1. Whether the misses cluster on questions or scatter across draws: the
   observed number of questions with 0, 1, 2 and 3 not-right answers, beside
   the number independent draws at the run's own miss rate would give.
2. For each not-right answer, how many pages its lookup read and how many it
   could not, and why; and how many asks its answer valued, beside the most
   any draw of the same question valued.
3. Across all units, the not-right rate for a lookup that read three pages or
   fewer against one that read four or more, with a one-sided Fisher exact
   test, and the reasons pages went unread.

The join of a shard's record to its workflow row is by order: a shard runs
its units one at a time, and each unit writes one workflow row. The script
stops if a row's request is not the question's text.
"""
from __future__ import annotations

import collections
import glob
import json
import math
import statistics
import sys
from pathlib import Path

TRACES = Path(sys.argv[1] if len(sys.argv) > 1 else "docs/traces")
STEM = "20261117T-holdout-"

codes = json.loads((TRACES / f"{STEM}reading-codes.json").read_text())
blind: dict = {}
for path in sorted(glob.glob(str(TRACES / f"{STEM}reading-blind-verdicts-*.json"))):
    blind.update(json.loads(Path(path).read_text()))
second = json.loads((TRACES / f"{STEM}reading-second-reading.json").read_text())
questions = {q["id"]: q["question"] for q in json.loads(
    Path("evals/professional/holdout-questions.json").read_text())["questions"]}

outcome: dict[tuple[str, int], str] = {}
for code, meta in codes.items():
    if not meta["delivered"]:
        outcome[(meta["question"], meta["repeat"])] = "blocked"
    else:
        outcome[(meta["question"], meta["repeat"])] = (
            second.get(code, {}).get("verdict") or blind[code]["verdict"])

units = []
for shard in (0, 1, 2):
    rows = [r for r in (json.loads(line) for line in
                        (TRACES / f"{STEM}shard-{shard}.jsonl").read_text().splitlines())
            if r.get("status") != "not_started"]
    phases = [json.loads(line) for line in
              (TRACES / f"{STEM}phases-shard-{shard}.jsonl").read_text().splitlines()]
    workflows = sorted((p for p in phases if p.get("kind") == "workflow"),
                       key=lambda p: p["id"])
    by_workflow = collections.defaultdict(list)
    for p in phases:
        if p.get("kind") == "phase":
            by_workflow[p["workflow_id"]].append(p)
    assert len(rows) == len(workflows), (shard, len(rows), len(workflows))
    for row, workflow in zip(rows, workflows):
        if workflow["request"] != questions[row["question"]]:
            sys.exit(f"shard {shard}: workflow {workflow['id']} is not {row['question']}")
        pages: dict[str, tuple[bool, str]] = {}
        asked = 0
        for phase in by_workflow[workflow["id"]]:
            if phase["phase"] == "sources":
                for finding in phase["verdict"].get("findings", []):
                    for doc in finding.get("documents", []):
                        pages[doc["url"]] = (bool(doc.get("read")), doc.get("reason") or "")
            if phase["phase"] == "implement":
                asked = len(phase["verdict"].get("results") or [])
        read = sum(1 for ok, _ in pages.values() if ok)
        why = collections.Counter(
            ("no answer in time" if "no answer within" in reason
             else "HTTP 403" if "403" in reason
             else "over the size limit" if "larger than" in reason
             else reason[:24] or "unread")
            for ok, reason in pages.values() if not ok)
        units.append({"q": row["question"], "r": row["repeat"],
                      "outcome": outcome[(row["question"], row["repeat"])],
                      "read": read, "unread": len(pages) - read, "why": why,
                      "asked": asked})

not_right = [u for u in units if u["outcome"] != "right"]
per_question = collections.Counter()
for u in not_right:
    per_question[u["q"]] += 1
n_questions = len({u["q"] for u in units})
p = len(not_right) / len(units)
print(f"== 1. {len(not_right)} of {len(units)} answers not right (p = {p:.3f}) on "
      f"{len(per_question)} of {n_questions} questions ==")
observed = [n_questions - len(per_question)] + [
    sum(1 for c in per_question.values() if c == k) for k in (1, 2, 3)]
expected = [n_questions * math.comb(3, k) * p ** k * (1 - p) ** (3 - k) for k in range(4)]
print("questions with 0, 1, 2, 3 not-right answers")
print("  observed                      ", observed)
print("  if every draw failed alone    ", [round(e, 1) for e in expected])
rest = sum(c - 1 for c in per_question.values())
print(f"not-right among the other draws of the {len(per_question)} questions: "
      f"{rest} of {2 * len(per_question)}")

print("\n== 2. each not-right answer ==")
most_asks = collections.defaultdict(int)
for u in units:
    most_asks[u["q"]] = max(most_asks[u["q"]], u["asked"])
for u in sorted(not_right, key=lambda u: (int(u["q"][1:]), u["r"])):
    print(f"{u['q']:>4} draw {u['r']}  {u['outcome']:<8} pages read {u['read']}, "
          f"unread {u['unread']} {dict(u['why'])}; values given {u['asked']} "
          f"(most in any draw {most_asks[u['q']]})")

print("\n== 3. pages read, across all units ==")
low = [u for u in units if u["read"] <= 3]
high = [u for u in units if u["read"] >= 4]
a, b = sum(u["outcome"] != "right" for u in low), sum(u["outcome"] == "right" for u in low)
c, d = sum(u["outcome"] != "right" for u in high), sum(u["outcome"] == "right" for u in high)
total, row1, col1 = a + b + c + d, a + b, a + c
fisher = sum(math.comb(row1, x) * math.comb(total - row1, col1 - x) / math.comb(total, col1)
             for x in range(a, min(row1, col1) + 1))
print(f"lookup read 3 pages or fewer: {len(low):3d} units, {a} not right ({100 * a / len(low):.0f}%)")
print(f"lookup read 4 pages or more : {len(high):3d} units, {c} not right ({100 * c / len(high):.0f}%)")
print(f"one-sided Fisher exact p = {fisher:.4f}")
print("mean pages read: right "
      f"{statistics.mean(u['read'] for u in units if u['outcome'] == 'right'):.1f}, "
      f"not right {statistics.mean(u['read'] for u in not_right):.1f}")
why_all = collections.Counter()
for u in units:
    why_all.update(u["why"])
print("pages not read, by reason:", dict(why_all.most_common()))
