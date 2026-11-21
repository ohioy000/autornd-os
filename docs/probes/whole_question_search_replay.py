"""Does putting the whole question first make the search name the right family of pages?
A probe of one step: the search request that names the documents. No page is fetched and
no answer is written, so nothing here says an answer is right.

    python docs/probes/whole_question_search_replay.py INPUTS            # free dry run
    python docs/probes/whole_question_search_replay.py INPUTS OUT MAX_SPEND

INPUTS is docs/traces/20261121T-whole-question-smoke-inputs.json: for three X12 draws, the
scoped lookup question the run sent and the same question with the whole request put first.
The dry run rebuilds each whole-first question with lookup_questions and checks it against
the file, so a change to the code that the file does not hold is caught before any spend;
it also needs the six MODEL_ tiers set, as every import of autornd does. With OUT and
MAX_SPEND it makes one search request a draw, appends a line to OUT, and never starts a
call that could pass MAX_SPEND. Paid: it needs the owner's word and a stated amount (a call
has cost '$0.0059'). The reply limit is the one for critical risk, as in the smoke test.

2026-11-21: run with MAX_SPEND '$0.02', spent '$0.0176'. Its record is
docs/traces/20261121T-whole-question-smoke.jsonl (sha256
d92a059a81b8c6b09efe19fc544faddd57637213cd53dde63783e3deebf90007), written by the
scratchpad script this one was made from. That record's `iaea` and `n` count every
address the reply named (15 to 17); the harness reads only the first six (MAX_DOCUMENTS in
autornd/knowledge/research.py), so this version also writes `first_six` and
`iaea_first_six`, and the first-six counts of the record come from its `urls`.
"""
from __future__ import annotations

import asyncio
import json
import re
import shutil
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

import logging  # noqa: E402

logging.basicConfig(level=logging.ERROR)

from autornd.config import settings  # noqa: E402
from autornd.knowledge import research  # noqa: E402
from autornd.knowledge.context import search_budget  # noqa: E402
from autornd.knowledge.research import MAX_DOCUMENTS, _bundle, lookup_questions  # noqa: E402
from autornd.models.verdicts import RiskLevel  # noqa: E402
from autornd.routing.openrouter import BudgetExceeded, OpenRouterClient  # noqa: E402

INPUTS = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
REQUEST = INPUTS["question"]["request"]
# The pages that are the IAEA's regulations or hold them; written down before the smoke test.
GOVERNING = re.compile(INPUTS["pages_matching"], re.I)
# A search call has cost '$0.0059' at most; never start one that could pass the amount.
CALL = 0.0062


def plan() -> list[dict]:
    """Each draw's whole-first question, rebuilt now; a mismatch with the file stops the run."""
    out = []
    for draw in INPUTS["draws"]:
        rebuilt = _bundle(lookup_questions(REQUEST, draw["gaps"]))
        same = rebuilt == draw["whole_first_question"]
        scoped = _bundle(draw["gaps"]) == draw["scoped_question"]
        print("PLAN", draw["draw"], "| gaps", len(draw["gaps"]), "| chars",
              len(rebuilt), "vs scoped", len(draw["scoped_question"]),
              "| file matches the code:", same, "| scoped rebuilt from gaps:", scoped)
        if not (same and scoped):
            sys.exit("the questions in INPUTS are not what the code builds now")
        out.append({"draw": draw["draw"], "question": rebuilt})
    return out


async def replay(jobs: list[dict], out: Path, max_spend: float) -> None:
    settings.chromadb_path = tempfile.mkdtemp(prefix="replay-")
    client = OpenRouterClient()
    spent = 0.0
    try:
        for job in jobs:
            if spent + CALL > max_spend:
                print("stopped: the next call could pass", max_spend, "after", round(spent, 4))
                break
            started = time.time()
            try:
                named = await research._name_documents(
                    client, REQUEST, job["question"], search_budget(RiskLevel.CRITICAL))
            except BudgetExceeded:
                break
            if named is None:
                record = {"draw": job["draw"], "arm": "whole", "failed": True}
            else:
                response, near = named
                spent += response.cost or 0.0
                urls = list(near)
                first = urls[:MAX_DOCUMENTS]
                record = {"draw": job["draw"], "arm": "whole", "urls": urls,
                          "n": len(urls), "iaea": sum(bool(GOVERNING.search(u)) for u in urls),
                          "first_six": len(first),
                          "iaea_first_six": sum(bool(GOVERNING.search(u)) for u in first),
                          "cost": response.cost, "seconds": round(time.time() - started, 1)}
            with out.open("a", encoding="utf-8") as log:
                log.write(json.dumps(record) + "\n")
            print("DONE", record["draw"], "governing pages in the first six:",
                  record.get("iaea_first_six"), "spent", round(spent, 4), flush=True)
    finally:
        await client.close()
        shutil.rmtree(settings.chromadb_path, ignore_errors=True)
    print("total spent", round(spent, 4))


if __name__ == "__main__":
    jobs = plan()
    if len(sys.argv) >= 4:
        asyncio.run(replay(jobs, Path(sys.argv[2]).resolve(), float(sys.argv[3])))
    else:
        print("dry run: nothing was asked")
