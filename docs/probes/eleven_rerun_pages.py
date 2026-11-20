"""Pages read by the harness's lookups in the eleven-question rerun. Free.

    python -I docs/probes/eleven_rerun_pages.py RUN_PREFIX CODES_JSON "VERDICTS_GLOB" [SECOND_READING_JSON]

RUN_PREFIX is the start of the file names of the shard records
(RUN_PREFIXshard-N.jsonl, from short_workflows_measurement.py) and of the phase
rows exported from each shard's database (RUN_PREFIXphases-shard-N.jsonl, from
export_shard_db.py): "docs/traces/20261119T-eleven-rerun-" for the kept copies. CODES_JSON, VERDICTS_GLOB and the
optional SECOND_READING_JSON are the files eleven_rerun_analysis.py takes; an
answer whose source path holds "pass" belongs to the frontier arm and is left
out here.

It repeats the method of holdout_miss_classification.py on the new run: for
every unit that made an answer, how many pages its lookup read and how many it
could not (and why), then the not-right rate for a lookup that read three
pages or fewer against four or more with a one-sided Fisher exact test, and
the pages that gave no answer in time for each lookup, beside the first run's
50 in 126. A unit that ended on a provider 402 made no lookup and is left out,
as in eleven_rerun_analysis.py. A unit blocked by the harness's own checks
made one and counts as not right.

The join of a shard's record to its workflow row is by order: a shard runs its
units one at a time and each unit writes one workflow row. The script stops if
a row's request is not the question's text.
"""
from __future__ import annotations

import collections
import glob
import json
import math
import statistics
import sys
from pathlib import Path

RUN = sys.argv[1]
codes = json.loads(Path(sys.argv[2]).read_text())
blind: dict = {}
for path in sorted(glob.glob(sys.argv[3])):
    blind.update(json.loads(Path(path).read_text()))
second = json.loads(Path(sys.argv[4]).read_text()) if len(sys.argv) > 4 else {}
second = {k: v for k, v in second.items() if isinstance(v, dict)}
questions = {q["id"]: q["question"] for q in json.loads(
    Path("evals/professional/holdout-questions.json").read_text())["questions"]}
FIRST_RUN = {"timeouts": 50, "lookups": 126}

verdict: dict[tuple[str, int], str] = {}
for code, meta in codes.items():
    if "pass" in Path(meta["source"].split("#")[0]).stem or code not in blind:
        continue  # the frontier arm's, or a unit that delivered nothing
    verdict[(meta["question"], meta["repeat"])] = (
        second.get(code, {}).get("verdict") or blind[code]["verdict"])

units = []
for shard in (0, 1, 2):
    rows = [json.loads(line) for line in
            Path(f"{RUN}shard-{shard}.jsonl").read_text().splitlines()
            if json.loads(line).get("status") != "not_started"]
    phases = [json.loads(line) for line in
              Path(f"{RUN}phases-shard-{shard}.jsonl").read_text().splitlines()]
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
        if "402" in str(row.get("error") or ""):
            continue
        pages: dict[str, tuple[bool, str]] = {}
        for phase in by_workflow[workflow["id"]]:
            if phase["phase"] == "sources":
                for finding in phase["verdict"].get("findings", []):
                    for doc in finding.get("documents", []):
                        pages[doc["url"]] = (bool(doc.get("read")), doc.get("reason") or "")
        read = sum(1 for ok, _ in pages.values() if ok)
        why = collections.Counter(
            ("no answer in time" if "no answer within" in reason
             else "HTTP 403" if "403" in reason
             else "over the size limit" if "larger than" in reason
             else reason[:24] or "unread")
            for ok, reason in pages.values() if not ok)
        key = (row["question"], row["repeat"])
        outcome = verdict.get(key, "blocked" if not row.get("delivered") else None)
        if outcome is None:
            sys.exit(f"no verdict for {key}")
        units.append({"q": row["question"], "r": row["repeat"], "outcome": outcome,
                      "read": read, "unread": len(pages) - read, "why": why})

not_right = [u for u in units if u["outcome"] != "right"]
print(f"== {len(units)} answers made, {len(not_right)} not right ==")
for u in sorted(not_right, key=lambda u: (int(u["q"][1:]), u["r"])):
    print(f"{u['q']:>4} draw {u['r']}  {u['outcome']:<8} pages read {u['read']}, "
          f"unread {u['unread']} {dict(u['why'])}")

print("\n== pages read, across the answers made ==")
low = [u for u in units if u["read"] <= 3]
high = [u for u in units if u["read"] >= 4]
a, b = sum(u["outcome"] != "right" for u in low), sum(u["outcome"] == "right" for u in low)
c, d = sum(u["outcome"] != "right" for u in high), sum(u["outcome"] == "right" for u in high)
total, row1, col1 = a + b + c + d, a + b, a + c
fisher = sum(math.comb(row1, x) * math.comb(total - row1, col1 - x) / math.comb(total, col1)
             for x in range(a, min(row1, col1) + 1)) if row1 and col1 else float("nan")
print(f"lookup read 3 pages or fewer: {len(low):3d} units, {a} not right")
print(f"lookup read 4 pages or more : {len(high):3d} units, {c} not right "
      f"({100 * c / len(high):.0f}%)")
print(f"one-sided Fisher exact p = {fisher:.4f}")
print(f"mean pages read: right "
      f"{statistics.mean(u['read'] for u in units if u['outcome'] == 'right'):.1f}, "
      f"not right {statistics.mean(u['read'] for u in not_right):.1f}")

why_all = collections.Counter()
for u in units:
    why_all.update(u["why"])
timeouts = why_all["no answer in time"]
print("pages not read, by reason:", dict(why_all.most_common()))
print(f"pages that gave no answer in time: {timeouts} in {len(units)} lookups = "
      f"{timeouts / len(units):.2f} a lookup; first run {FIRST_RUN['timeouts']} in "
      f"{FIRST_RUN['lookups']} = {FIRST_RUN['timeouts'] / FIRST_RUN['lookups']:.2f}")
print(f"pages read an answer: mean {statistics.mean(u['read'] for u in units):.1f}")
