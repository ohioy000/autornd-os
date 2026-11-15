"""Does looking up each reading of a vague request fetch the passage that
holds the answer? A paid probe of the grounding step alone.

    python docs/probes/vague_request_probe.py OUT_FILE MAX_SPEND

The lookup test of 2026-11-14 found that for the inspection-authorization
request the scoping call names one blocking unknown, "which of two readings
is meant", and that choice is what gets looked up. No page answers a question
about what the asker meant, and the search brought the wrong section in 5 of
6 runs (docs/reviews/2026-11-14-lookup-asks-request.md).

Two arms, on the same requests, through the real engine's grounding
(workflows/triage-only.yaml: triage, then build_context), each run on its
own empty knowledge store:

  now           the code as it is;
  each_reading  one sentence added to the scoping prompt: when a blocking
                unknown is which reading is meant, list each reading as its
                own question a source can answer. Done here by replacing
                the prompt text inside the probe; main's code is not changed.

For each run it records the questions looked up, the quotes the quote check
found on their pages, and whether one of them holds the passage that states
the answer (MARKS: words of the governing sentence, chosen before the run).
No answer is written, so nothing here says an answer is right. Paid: it
needs the owner's word and a stop amount.
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
OUT = Path(sys.argv[1]).resolve()
MAX_SPEND = float(sys.argv[2])
sys.path.insert(0, str(ROOT))

import logging  # noqa: E402

logging.basicConfig(level=logging.ERROR)

from autornd.config import settings, settings_lookup  # noqa: E402
from autornd.graph.adapter import PhaseRunner  # noqa: E402
from autornd.graph.executor import GraphExecutor  # noqa: E402
from autornd.graph.spec import load  # noqa: E402
from autornd.knowledge import context as ctx  # noqa: E402
from autornd.routing.openrouter import OpenRouterClient  # noqa: E402

GOLDEN = json.loads((ROOT / "evals/golden/keys.json").read_text())
# IA is the owner's recorded request. V17 and V22 were written for this probe
# before the run, in its manner, from tier-2 Q17 and Q22: a subject, a loose
# "regarding", and no statement of which rule is wanted.
REQUESTS = {
    "IA": GOLDEN["side_test"]["request"],
    "V17": ("what are the requirments for lockout tagout devices regarding "
            "strength, (OSHA), https://www.ecfr.gov/ is a good source"),
    "V22": ("what are the rules for audiograms regarding new employees, "
            "(OSHA), https://www.ecfr.gov/ is a good source"),
}
REPEATS = {"IA": 4, "V17": 3, "V22": 3}
# Words of the sentence that states the answer, as in the lookup test.
MARKS = {"IA": r"actively engaged",          # 14 CFR 65.91(c)(2)
         "V17": r"50 pounds",                # 29 CFR 1910.147(c)(5)(ii)(C)(2)
         "V22": r"6 months|14 hours"}        # 29 CFR 1910.95(g)(5)
ORIGINAL = ctx.SCOPING_PROMPT
ANCHOR = "Often empty. Never more than three."
EACH_READING = ORIGINAL.replace(ANCHOR, ANCHOR + """
  When a blocking unknown is which of two or more readings of the request is
  meant, do not list the choice between them. List each reading as its own
  question, worded so a published source can answer it.""")
assert EACH_READING != ORIGINAL


async def run(arm: str, name: str, repeat: int) -> dict:
    store = tempfile.mkdtemp(prefix="store-", dir=OUT.parent)
    settings.chromadb_path = store
    ctx.SCOPING_PROMPT = EACH_READING if arm == "each_reading" else ORIGINAL
    client = OpenRouterClient()
    sources: list[dict] = []
    started = time.time()
    record = {"arm": arm, "question": name, "repeat": repeat}

    def on_phase(node_id, verdict, responses, iteration):
        if node_id == "sources":
            sources.append(dict(verdict))

    try:
        runner = PhaseRunner(client, on_phase=on_phase)
        state = await GraphExecutor(load(ROOT / "workflows/triage-only.yaml"),
                                    runner, settings_lookup()).run(REQUESTS[name])
        quotes = [q for s in sources for f in s.get("findings") or []
                  for q in f.get("quotes") or []]
        found = [q for q in quotes if q.get("status") == "found"]
        record.update({
            "status": state.status,
            "asked": [f.get("question") for s in sources
                      for f in s.get("findings") or []],
            "quotes": len(quotes), "found": len(found),
            "passage_found": any(re.search(MARKS[name], q.get("text", ""))
                                 for q in found),
            "passage_quoted": any(re.search(MARKS[name], q.get("text", ""))
                                  for q in quotes),
            "sources": sources})
    except Exception as exc:
        record.update({"status": "raised",
                       "error": f"{type(exc).__name__}: {exc}"[:300]})
    finally:
        record["cost"] = float(getattr(client, "spend", 0.0))
        await client.close()
        ctx.SCOPING_PROMPT = ORIGINAL
        shutil.rmtree(store, ignore_errors=True)
    record["seconds"] = round(time.time() - started, 1)
    return record


async def main() -> None:
    spent = 0.0
    with OUT.open("a", encoding="utf-8") as log:
        for repeat in range(1, max(REPEATS.values()) + 1):
            for name in REQUESTS:
                if repeat > REPEATS[name]:
                    continue
                for arm in ("now", "each_reading"):
                    if spent >= MAX_SPEND:
                        print("stopped at", round(spent, 4), flush=True)
                        return
                    record = await run(arm, name, repeat)
                    spent += record["cost"]
                    log.write(json.dumps(record) + "\n")
                    log.flush()
                    print(arm, name, repeat, record.get("status"),
                          "found", record.get("found"), "passage",
                          record.get("passage_found"), round(spent, 4), flush=True)


asyncio.run(main())
