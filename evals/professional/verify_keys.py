"""Check every passage of the professional set against its live page.

    python -I evals/professional/verify_keys.py REPO [FILE]

Free of model calls: it fetches each source with the harness's own fetch and
looks for the passage with the harness's own quote check. It also checks
that each key answer's figures are in the page. A page that has changed
since the keys were frozen shows here.
"""
from __future__ import annotations

import asyncio
import json
import os
import re
import sys
from pathlib import Path

REPO = Path(sys.argv[1]).resolve()
sys.path.insert(0, str(REPO))
for tier in ("TRIAGE", "ENGINEERING", "ARCHITECTURE", "ESCALATION",
             "RESEARCH", "SEARCH"):
    os.environ[f"MODEL_{tier}"] = "placeholder/offline"
os.chdir("/")  # no .env here, so only the placeholders are read

from autornd.knowledge.fetch import fetch_source  # noqa: E402
from autornd.knowledge.research import _normalise, quote_found  # noqa: E402


async def main() -> None:
    name = sys.argv[2] if len(sys.argv) > 2 else "questions.json"
    draft = json.loads((REPO / "evals/professional" / name).read_text())
    bad = 0
    for q in draft["questions"]:
        sources = q.get("sources") or [{"url": q["source"], "passage": q["passage"]}]
        notes, text = [], ""
        for source in sources:
            page = await fetch_source(source["url"])
            if not page.fetched:
                notes.append(f"unread: {page.reason}")
                continue
            text += " " + _normalise(page.text).replace(",", "")
            if not quote_found(source["passage"], page.text):
                notes.append("passage not found")
            await asyncio.sleep(1)
        # A key item marked derived is worked out from the sources (a sum, a
        # unit conversion, an absence), so its figures need not be on a page.
        figures = [n.replace(",", "") for item in q["key"] if not item.get("derived")
                   for n in re.findall(r"\d[\d.,/]*\d|\d", item["answer"])]
        missing = [n for n in figures if n.casefold() not in text]
        if missing:
            notes.append(f"figures not on page: {missing}")
        # A stale source is a live page that still prints the figure the
        # question is commonly answered with. It is not a key: it shows the
        # question's premise still holds, so it is said when one has gone.
        for stale in q.get("stale_sources") or []:
            page = await fetch_source(stale["url"])
            if not page.fetched:
                notes.append(f"stale source unread: {page.reason}")
            elif not quote_found(stale["passage"], page.text):
                notes.append("stale source no longer says it")
            await asyncio.sleep(1)
        bad += bool(notes)
        print(q["id"], "ok" if not notes else "CHANGED", "; ".join(notes))
    print(f"{len(draft['questions']) - bad} of {len(draft['questions'])} hold")


asyncio.run(main())
