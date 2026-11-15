"""The figures in docs/reviews/2026-11-14-lookup-asks-request.md, re-derived
from the committed trace. Free: it reads one file and calls nothing.

    python docs/probes/lookup_asks_request_analysis.py \
        docs/traces/20261115T002323Z-lookup-asks-request-runs.jsonl

Per arm and request: in how many runs the search returned the passage that
states the answer (quoted), and in how many the quote check found it on its
page (found). Then every quote holding that passage, by site, file kind and
what the quote check said of it. The words that recognise the passage are
the preregistration's.
"""
from __future__ import annotations

import json
import re
import sys
from collections import Counter

MARKS = {"IA": r"actively engaged", "Q2": r"19\.5", "Q12": r"0\.010",
         "Q17": r"50 pounds", "Q22": r"6 months|14 hours"}
runs = [json.loads(line) for line in open(sys.argv[1], encoding="utf-8")]
for arm in ("now", "request_first"):
    mine = [r for r in runs if r["arm"] == arm]
    print(arm, "| passage quoted in", sum(r["passage_quoted"] for r in mine),
          "of", len(mine), "runs, found in", sum(r["passage_found"] for r in mine),
          "| cost", round(sum(r["cost"] for r in mine), 4))
    for name in MARKS:
        own = [r for r in mine if r["question"] == name]
        print("   ", name, "quoted", sum(r["passage_quoted"] for r in own),
              "found", sum(r["passage_found"] for r in own), "of", len(own))
sites: Counter[tuple[str, str, str]] = Counter()
for r in runs:
    for source in r["sources"]:
        for finding in source["findings"]:
            for q in finding["quotes"]:
                if re.search(MARKS[r["question"]], q.get("text", "")):
                    url = q.get("url", "")
                    host = re.sub(r"^https?://(www\.)?", "", url).split("/")[0]
                    kind = ("pdf" if ".pdf" in url else
                            "xml" if ".xml" in url else "html")
                    sites[(host, kind, q["status"]
                           + (f" ({q['reason']})" if q.get("reason") else ""))] += 1
print("quotes holding the passage:", sum(sites.values()))
for key in sorted(sites):
    print("   ", *key, sites[key])
