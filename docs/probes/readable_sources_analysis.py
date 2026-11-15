"""Re-derive the readable-sources sweep's figures from its traces. Free.

    python docs/probes/readable_sources_analysis.py docs/traces [ARM ...]

For each arm it reads the answers (20261115T-readable-<arm>-<set>-shard-N.jsonl)
and the run rows exported beside them (…-phases-shard-N.jsonl), where each
lookup's quotes are. The arms are now, avoid, avoid_withhold and recheck.
An answer passes when its screen does: tier-2's verdict, or golden's holds.
For the inspection-authorization request it also prints whether a quote
found on its page holds the sentence of 14 CFR 65.91(c)(2).
"""
from __future__ import annotations

import glob
import json
import sys
from collections import Counter, defaultdict

ROOT = sys.argv[1]
ARMS = sys.argv[2:] or ["now", "avoid", "avoid_withhold", "recheck"]


def passed(record: dict) -> bool:
    scorer = record.get("scorer") or {}
    if "golden_holds" in scorer:
        return bool(scorer["golden_holds"])
    return scorer.get("verdict") == "PASS"


for arm in ARMS:
    stats: Counter = Counter()
    by_q: dict = defaultdict(lambda: [0, 0])
    for path in sorted(glob.glob(f"{ROOT}/20261115T-readable-{arm}-*-shard-*.jsonl")):
        if "-phases-" in path:
            continue
        records = [json.loads(line) for line in open(path, encoding="utf-8")]
        rows = [json.loads(line) for line in open(
            path.replace("-shard-", "-phases-shard-"), encoding="utf-8")]
        ids = [r["id"] for r in rows if r["kind"] == "workflow"]
        for wid, record in zip(ids, records):
            ok = passed(record)
            findings = [f for r in rows if r["kind"] == "phase"
                        and r["workflow_id"] == wid and r["phase"] == "sources"
                        for f in r["verdict"].get("findings") or []]
            quotes = [q for f in findings for q in f.get("quotes") or []]
            again = [f for f in findings if f.get("round", 1) > 1]
            held = [f for f in findings if f.get("withheld")]
            stats["answers"] += 1
            stats["cost"] += record["cost"]
            stats["passed"] += ok
            by_q[record["question"]][0] += ok
            by_q[record["question"]][1] += 1
            stats["quotes"] += len(quotes)
            stats["unread"] += sum(q["status"] == "unfetched" for q in quotes)
            stats["unread_osha"] += sum(q["status"] == "unfetched"
                                        and "osha.gov" in q["url"] for q in quotes)
            stats["found"] += sum(q["status"] == "found" for q in quotes)
            stats["answers_with_a_found_quote"] += any(
                q["status"] == "found" for q in quotes)
            stats["asked_again"] += bool(again)
            stats["withheld_findings"] += len(held)
            if findings and len(held) == len(findings):
                stats["all_withheld"] += 1
                stats["all_withheld_passed"] += ok
            if record["question"] == "IA":
                has = any(q["status"] == "found" and "actively engaged" in q["text"]
                          for q in quotes)
                print(f"  {arm} IA {record['repeat']}: screen "
                      f"{'pass' if ok else 'FAIL'}, passage found {has}")
    stats["cost"] = round(stats["cost"], 3)
    print(arm, dict(stats))
    print("   ", {q: f"{a}/{b}" for q, (a, b) in sorted(by_q.items())})
