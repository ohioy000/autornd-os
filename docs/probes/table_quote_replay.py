"""Replay the lookup test's recorded quotes through the quote check as it is now.

    python -I docs/probes/table_quote_replay.py REPO TRACE

Free of model calls: it fetches each quoted page again and asks nothing of a
model. For every quote the trace recorded as not_found it prints whether the
check finds it now, and whether the quote is a grid of cells. It also re-checks
every quote recorded as found, which must stay found.
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path

REPO, TRACE = Path(sys.argv[1]).resolve(), Path(sys.argv[2]).resolve()
sys.path.insert(0, str(REPO))
for tier in ("TRIAGE", "ENGINEERING", "ARCHITECTURE", "ESCALATION",
             "RESEARCH", "SEARCH"):
    os.environ[f"MODEL_{tier}"] = "placeholder/offline"
os.chdir("/")  # no .env here, so only the placeholders are read

from autornd.knowledge.fetch import fetch_source  # noqa: E402
from autornd.knowledge.research import _table_rows, quote_found  # noqa: E402


async def main() -> None:
    rows = [json.loads(line) for line in TRACE.open(encoding="utf-8")]
    quotes = [(r["question"], r["arm"], r["repeat"], q)
              for r in rows for s in r["sources"] for f in s["findings"]
              for q in f["quotes"] if q["status"] in ("found", "not_found")]
    urls = sorted({q["url"] for *_, q in quotes})
    pages = {}
    for url in urls:  # one at a time: a polite replay, not a load test
        pages[url] = await fetch_source(url)
    tally = {"found": [0, 0], "grid": [0, 0], "prose": [0, 0]}
    unread = 0
    for question, arm, repeat, q in quotes:
        page = pages[q["url"]]
        if not page.fetched:
            unread += 1
            continue
        now = quote_found(q["text"], page.text)
        kind = ("found" if q["status"] == "found"
                else "grid" if _table_rows(q["text"]) else "prose")
        tally[kind][0] += now
        tally[kind][1] += 1
        if kind != "found" and now:
            print("now found:", question, arm, repeat, q["url"])
        if kind == "found" and not now:
            print("NO LONGER FOUND:", question, arm, repeat, q["url"])
    print(json.dumps({"recorded found, found now": tally["found"],
                      "recorded not_found grids, found now": tally["grid"],
                      "recorded not_found prose, found now": tally["prose"],
                      "page not read on replay": unread}))


asyncio.run(main())
