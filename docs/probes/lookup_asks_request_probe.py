"""Does looking up the request's own question fetch the passage that holds
the answer? A paid probe of the grounding step alone.

    python docs/probes/lookup_asks_request_probe.py OUT_FILE REPEATS MAX_SPEND

The lookup's questions are the scoping call's blocking unknowns: what the
request leaves unspecified (autornd/knowledge/context.py, analyze_request).
The request's own question is looked up only when a lookup is demanded and
there is no unknown. On 2026-11-14 all 4 recorded wrong answers to the
inspection-authorization question were written without the passage that
states the answer (docs/reviews/2026-11-14-prose-errors-are-retrieval.md).

Two arms, on the same requests, through the real engine's grounding
(workflows/triage-only.yaml: triage, then build_context), each run on its
own empty knowledge store:

  now            the code as it is;
  request_first  the request itself is the first lookup question, followed
                 by the first two blocking unknowns. Done here by wrapping
                 analyze_request; main's code is not changed.

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
REPEATS, MAX_SPEND = int(sys.argv[2]), float(sys.argv[3])
sys.path.insert(0, str(ROOT))

import logging  # noqa: E402

logging.basicConfig(level=logging.ERROR)

from autornd.config import settings, settings_lookup  # noqa: E402
from autornd.graph.adapter import PhaseRunner  # noqa: E402
from autornd.graph.executor import GraphExecutor  # noqa: E402
from autornd.graph.spec import load  # noqa: E402
from autornd.knowledge import context as ctx  # noqa: E402
from autornd.routing.openrouter import OpenRouterClient  # noqa: E402

TIER2 = {q["id"]: q["question"] for q in
         json.loads((ROOT / "evals/tier2/questions.json").read_text())}
GOLDEN = json.loads((ROOT / "evals/golden/keys.json").read_text())
REQUESTS = {"IA": GOLDEN["side_test"]["request"],
            **{k: TIER2[k] for k in ("Q2", "Q12", "Q17", "Q22")}}
# Words of the sentence that states the answer, per request.
MARKS = {"IA": r"actively engaged",          # 14 CFR 65.91(c)(2)
         "Q2": r"19\.5",                     # 29 CFR 1910.146(b)
         "Q12": r"0\.010",                   # 40 CFR 141.62(b), arsenic
         "Q17": r"50 pounds",                # 29 CFR 1910.147(c)(5)(ii)(C)(2)
         "Q22": r"6 months|14 hours"}        # 29 CFR 1910.95(g)(5)
ORIGINAL = ctx.analyze_request


async def request_first(client, request):
    scoping, unknowns = await ORIGINAL(client, request)
    return scoping, [request] + list(unknowns)[:2]


async def run(arm: str, name: str, repeat: int) -> dict:
    store = tempfile.mkdtemp(prefix="store-", dir=OUT.parent)
    settings.chromadb_path = store
    ctx.analyze_request = request_first if arm == "request_first" else ORIGINAL
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
        ctx.analyze_request = ORIGINAL
        shutil.rmtree(store, ignore_errors=True)
    record["seconds"] = round(time.time() - started, 1)
    return record


async def main() -> None:
    spent = 0.0
    with OUT.open("a", encoding="utf-8") as log:
        for repeat in range(1, REPEATS + 1):
            for name in REQUESTS:
                for arm in ("now", "request_first"):
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
