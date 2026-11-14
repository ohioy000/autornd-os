"""Was the passage that matters among the quotes, in each recorded answer to
the inspection-authorization question? Free: it reads the committed traces
and calls nothing.

    python docs/probes/ia_quotes_vs_errors.py

For every completed IA unit in docs/traces/2026111[34]*, it prints whether
the golden screen's item IA.2 holds (the actively-engaged 2-year period,
14 CFR 65.91(c)(2)), how many quoted passages the quote check found on
their pages, and how many of those contain the words "actively engaged".
The figures in docs/reviews/2026-11-14-prose-errors-are-retrieval.md come
from this. The screen is a screen (D50); each answer's sentence is printed
beside it so the reading can be checked.
"""
from __future__ import annotations

import glob
import json
import re
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
table: Counter[tuple[bool, bool]] = Counter()
for path in sorted(glob.glob(str(ROOT / "docs/traces/2026111[34]*-phases-shard-*.jsonl"))):
    units_path = Path(path.replace("-phases-shard-", "-shard-"))
    if not units_path.exists():
        continue
    rows = [json.loads(line) for line in open(path, encoding="utf-8")]
    for wid, line in enumerate(open(units_path, encoding="utf-8"), start=1):
        unit = json.loads(line)
        if unit.get("question") != "IA" or unit.get("status") != "completed":
            continue
        found = [q for r in rows if r["kind"] == "phase"
                 and r["workflow_id"] == wid and r["phase"] == "sources"
                 for f in r["verdict"].get("findings") or []
                 for q in f.get("quotes") or [] if q.get("status") == "found"]
        with_it = sum("actively engaged" in q.get("text", "") for q in found)
        right = bool(unit["scorer"]["golden"].get("IA.2"))
        table[(right, bool(with_it))] += 1
        said = re.search(r"actively engaged[^.\n]{0,110}", unit.get("answer") or "")
        print(f"{Path(path).name[:16]} r{unit['repeat']} "
              f"{'right' if right else 'WRONG'}  found quotes {len(found)}, "
              f"with the passage {with_it} | "
              f"{said.group(0) if said else 'no mention'}")
print("right, passage found:    ", table[(True, True)])
print("right, passage not found:", table[(True, False)])
print("wrong, passage found:    ", table[(False, True)])
print("wrong, passage not found:", table[(False, False)])
