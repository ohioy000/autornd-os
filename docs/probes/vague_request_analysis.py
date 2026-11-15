"""Re-derive the vague-request test's figures from its trace. Free.

    python docs/probes/vague_request_analysis.py TRACE
"""
from __future__ import annotations

import json
import sys
from collections import defaultdict

found: dict = defaultdict(lambda: [0, 0])
cost = 0.0
for line in open(sys.argv[1], encoding="utf-8"):
    r = json.loads(line)
    cost += r["cost"]
    for key in ((r["arm"], r["question"]), (r["arm"], "all")):
        found[key][0] += bool(r.get("passage_found"))
        found[key][1] += 1
for (arm, name), (hit, runs) in sorted(found.items()):
    print(f"{arm:13} {name:4} {hit} of {runs}")
print(f"cost {cost:.3f}")
