"""What reading a bare-result sample changes, replayed on the recorded runs.
Free: it reads the committed traces and calls nothing.

    python docs/probes/bare_sample_replay.py

For every recorded unit of 2026-11-13 and 14 that has a recompute and its
vote (docs/traces/2026111[34]*-phases-shard-*.jsonl), it rebuilds the
anchored asks from the stored asks row and runs the vote as it is now over
the stored answer results and samples. It prints each unit whose vote
differs from the stored one, and the totals. A unit with no bare-result
sample must give the stored vote again; any that does not is listed as
UNEXPLAINED.
"""
from __future__ import annotations

import glob
import json
import os
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))
for tier in ("TRIAGE", "ENGINEERING", "ARCHITECTURE", "ESCALATION",
             "RESEARCH", "SEARCH"):
    os.environ[f"MODEL_{tier}"] = "placeholder/offline"

from autornd.graph.checks import get_check  # noqa: E402

KEYS = ("flagged", "checked", "samples_parsed", "samples_unreadable")
totals: Counter[str] = Counter()
for path in sorted(glob.glob(str(ROOT / "docs/traces/2026111[34]*-phases-shard-*.jsonl"))):
    rows = [json.loads(line) for line in open(path, encoding="utf-8")]
    requests = {r["id"]: r["request"] for r in rows if r["kind"] == "workflow"}
    for wid, request in requests.items():
        phase = {}
        for r in rows:
            if r["kind"] == "phase" and r["workflow_id"] == wid:
                phase[r["phase"]] = r["verdict"]      # the last row of each
        if not all(k in phase for k in ("asks", "implement", "recompute",
                                        "recompute_vote")):
            continue
        stored = phase["recompute_vote"]
        if stored.get("skipped"):
            continue
        samples = phase["recompute"].get("samples") or []
        bare = sum(1 for s in samples if isinstance(s, dict)
                   and "results" not in s and "ask" in s and "value" in s)
        anchored = get_check("asks_anchored")(
            asks=phase["asks"].get("asks") or [], request=request).data["anchored"]
        now = get_check("recompute_vote")(
            results=phase["implement"].get("results") or [], samples=samples,
            asks=anchored, request=request).data
        totals["units"] += 1
        totals["units with a bare sample"] += bool(bare)
        was = {k: stored.get(k) for k in KEYS}
        new = {k: now.get(k) for k in KEYS}
        if {k: was[k] for k in ("flagged", "checked")} == \
                {k: new[k] for k in ("flagged", "checked")}:
            continue
        if not bare:
            totals["UNEXPLAINED"] += 1
        totals["votes changed"] += 1
        totals[f"checked {was['checked']} -> {new['checked']}, "
               f"flagged {was['flagged']} -> {new['flagged']}"] += 1
        print(Path(path).name.replace("-phases", ""), wid, "bare", bare,
              "|", was, "->", new,
              "| disagreements", [(d["ask"], str(d["answer"])[:40], str(d["majority"])[:40])
                                  for d in now.get("disagreements") or []])
print(json.dumps(dict(totals), indent=1))
