"""The figures in docs/reviews/2026-11-14-claims-shadow.md, re-derived from
the committed traces. Free: it reads files and calls nothing.

    python docs/probes/claims_shadow_analysis.py \
        docs/traces/20261114T173049Z-claims-shadow

PREFIX-phases-shard-N.jsonl is each shard's database exported a row per line
(docs/probes/export_shard_db.py). For every unit it prints each claim the
claims node listed, whether claims_named kept it, the three samples' values
and what the claim vote said of it: agreed, flagged, no consensus, not
comparable, or not answered by two samples. A claim counts as a number when
the answer's value is one. Whether a value is right is the hand reading in
the report, not this probe (D50).
"""
from __future__ import annotations

import glob
import json
import sys
from collections import Counter

PREFIX = sys.argv[1]
totals: Counter[str] = Counter()
cost = 0.0
for path in sorted(glob.glob(f"{PREFIX}-phases-shard-*.jsonl")):
    rows = [json.loads(line) for line in open(path, encoding="utf-8")]
    units = [json.loads(line) for line in
             open(path.replace("-phases-shard-", "-shard-"), encoding="utf-8")]
    for wid, unit in enumerate(units, start=1):
        phase = {}
        for r in rows:
            if r["kind"] == "phase" and r["workflow_id"] == wid:
                phase.setdefault(r["phase"], r["verdict"])
                if r["phase"].startswith("claims"):
                    cost += r["cost"]
        named, vote = phase["claims_named"], phase["claims_vote"]
        samples = phase["claims_recompute"].get("samples") or []
        kept = {a["number"] for a in named["asks"]}
        flagged = {d["ask"] for d in vote.get("disagreements") or []}
        print(f"== {unit['question']} r{unit['repeat']}: listed "
              f"{len(phase['claims']['claims'])}, kept {len(kept)}, dropped "
              f"{ {k: v for k, v in named['dropped'].items() if v} }, samples "
              f"read {vote.get('samples_parsed')} unreadable "
              f"{vote.get('samples_unreadable')}; delivery cautions "
              f"{len(unit['cautions'])}, none from the claim check: "
              f"{not any('claim' in c for c in unit['cautions'])}")
        for number, claim in enumerate(phase["claims"]["claims"], start=1):
            values = [next((f"{x.get('value')} {x.get('unit') or ''}".strip()
                            for x in (s.get("results") or [])
                            if x.get("ask") == number), "-")
                      for s in samples if isinstance(s, dict)]
            if number not in kept:
                state = "dropped"
            elif not vote.get("checked"):
                state = "vote compared nothing"
            elif number in flagged:
                state = "flagged"
            elif number in (vote.get("no_consensus") or []):
                state = "no consensus"
            elif number in (vote.get("not_comparable") or []):
                state = "not comparable"
            elif sum(v != "-" for v in values) < 2:
                state = "not answered"
            else:
                state = "agreed"
            kind = ("number" if isinstance(claim["value"], (int, float))
                    else "text")
            totals[f"{kind} {state}"] += 1
            print(f"  {number:2} {kind:6} {state:22} {claim['name'][:55]:55} "
                  f"= {str(claim['value'])[:24]} {claim['unit'][:6]} | "
                  f"{[v[:20] for v in values]}")
print(json.dumps(dict(sorted(totals.items())), indent=1))
print("claim nodes cost", round(cost, 5))
