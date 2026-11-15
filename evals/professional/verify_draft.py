"""Check every passage of the professional draft set against its live page.

    python -I evals/professional/verify_draft.py REPO

Free of model calls: it fetches each source with the harness's own fetch and
looks for the passage with the harness's own quote check. It also checks
that each key answer's figures are in the page. A draft key whose passage is
not on its page is not ready for sign-off.
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
    draft = json.loads((REPO / "evals/professional/draft-questions.json").read_text())
    bad = 0
    for q in draft["questions"]:
        page = await fetch_source(q["source"])
        text = _normalise(page.text) if page.fetched else ""
        passage = page.fetched and quote_found(q["passage"], page.text)
        figures = [n for item in q["key"]
                   for n in re.findall(r"\d[\d.,/]*\d|\d", item["answer"])]
        missing = [n for n in figures if n.casefold() not in text]
        ok = passage and not missing
        bad += not ok
        print(q["id"], "ok" if ok else "NOT READY",
              "" if page.fetched else f"unread: {page.reason}",
              "" if passage or not page.fetched else "passage not found",
              f"figures not on page: {missing}" if missing else "")
        await asyncio.sleep(1)
    print(f"{len(draft['questions']) - bad} of {len(draft['questions'])} ready")


asyncio.run(main())
