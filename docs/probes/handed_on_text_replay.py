"""Replay recorded runs through the delivery as it is now. Free.

    python -I docs/probes/handed_on_text_replay.py REPO PHASES_FILE [...]

Each PHASES_FILE is a run's exported rows (…-phases-shard-N.jsonl). For
every completed run it rebuilds the delivery's cautions and confirmations
from the stored rows with this tree's code and prints them beside the
figures the answer gave, so each can be read against the key by hand. A
line that starts with `!` carries a caution about a figure or about pages
that differ. The totals are per file name without its shard.

The recorded rows keep the first 600 characters of each quote, so a figure
that stood past that point reads here as not confirmed. A lower bound for
the lookup that reads the documents, whose excerpts run to 1,200.
"""
from __future__ import annotations

import json
import os
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

REPO = Path(sys.argv[1]).resolve()
FILES = [str(Path(p).resolve()) for p in sys.argv[2:]]
sys.path.insert(0, str(REPO))
for tier in ("TRIAGE", "ENGINEERING", "ARCHITECTURE", "ESCALATION",
             "RESEARCH", "SEARCH"):
    os.environ[f"MODEL_{tier}"] = "placeholder/offline"
os.chdir("/")  # no .env here, so only the placeholders are read

from autornd.api import routes  # noqa: E402

totals: dict[str, Counter] = defaultdict(Counter)
for path in FILES:
    run = re.sub(r"-phases-shard-\d+\.jsonl$", "", Path(path).name)
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
        differing = routes._differing(sources)
        backed, unconfirmed = routes._checked_figures(results, sources, differing)
        if vote is not None and backed:
            vote = dict(vote, backed_by_source=backed)
        cautions = routes._cautions(vote, sources, True, asked, unconfirmed,
                                    differing)
        confirmations = routes._confirmations(backed, True)
        total = totals[run]
        total["answers"] += 1
        total["no_caution"] += not cautions
        total["cautions"] += len(cautions)
        total["with_a_confirmation"] += bool(confirmations)
        total["pages_differ"] += bool(differing)
        total["figure_not_confirmed"] += bool(unconfirmed)
        total["nothing_read"] += any("so nothing in this answer was checked"
                                     in c for c in cautions)
        total["vote_disagrees"] += any("vote disagrees" in c for c in cautions)
        figures = [(r.get("ask"), r.get("value"), r.get("unit"))
                   for r in results or [] if isinstance(r, dict)]
        print("!" if differing or unconfirmed else " ", run[-22:],
              workflow["id"], workflow["request"][:44].replace("\n", " "),
              "| backed", backed, "of", asked, "|", str(figures)[:150])
        for caution in cautions:
            print("      caution:", caution[:330])
for run, total in totals.items():
    print(run, dict(total))
