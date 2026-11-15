"""Replay recorded runs through the delivery as it is now. Free.

    python -I docs/probes/verified_by_source_replay.py REPO PHASES_FILE [...]

Each PHASES_FILE is a run's exported rows (…-phases-shard-N.jsonl). For
every completed run it rebuilds the delivery's vote, cautions and
confirmations from the stored rows with this tree's code, and prints the
cautions an answer carried before (rebuilt with no ask backed) and now,
the asks backed by a found passage, and any vote overruled.
"""
from __future__ import annotations

import json
import os
import sys
from collections import Counter
from pathlib import Path

REPO = Path(sys.argv[1]).resolve()
FILES = [str(Path(p).resolve()) for p in sys.argv[2:]]
sys.path.insert(0, str(REPO))
for tier in ("TRIAGE", "ENGINEERING", "ARCHITECTURE", "ESCALATION",
             "RESEARCH", "SEARCH"):
    os.environ[f"MODEL_{tier}"] = "placeholder/offline"
os.chdir("/")  # no .env here, so only the placeholders are read

from autornd.api import routes  # noqa: E402

total: Counter = Counter()
for path in FILES:
    rows = [json.loads(line) for line in open(path, encoding="utf-8")]
    for workflow in (r for r in rows if r["kind"] == "workflow"):
        if str(workflow["status"]).lower().split(".")[-1] != "completed":
            continue
        verdicts = [(r["phase"], json.loads(json.dumps(r["verdict"])))
                    for r in rows if r["kind"] == "phase"
                    and r["workflow_id"] == workflow["id"]]
        sources = [v for name, v in verdicts if name == "sources"]
        vote = next((v for name, v in reversed(verdicts)
                     if name == "recompute_vote"), None)
        vote = routes._settled(verdicts, vote, sources)
        results = next((v.get("results") for name, v in reversed(verdicts)
                        if name == "implement" and isinstance(v, dict)), None)
        asked = next((len(v.get("asks") or []) for name, v in reversed(verdicts)
                      if name == "asks" and isinstance(v, dict)), 0)
        before = routes._cautions(vote, sources, True)
        backed = routes._backed(results, sources)
        after_vote = routes._over_the_vote(vote, backed)
        after = routes._cautions(after_vote, sources, True, asked)
        overruled = (after_vote or {}).get("overruled_by_source") or []
        total["answers"] += 1
        total["cautions_before"] += len(before)
        total["cautions_now"] += len(after)
        total["no_caution_before"] += not before
        total["no_caution_now"] += not after
        total["asks"] += asked
        total["asks_backed"] += len(backed)
        total["answers_with_a_backed_ask"] += bool(backed)
        total["votes_overruled"] += bool(overruled)
        print(Path(path).name[-28:], workflow["id"], workflow["request"][:34],
              "| backed", backed, "of", asked, "| overruled", overruled,
              "| cautions", len(before), "->", len(after))
print(dict(total))
