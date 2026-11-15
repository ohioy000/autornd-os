"""The sweep of the typed search queries: vague and clear requests, through
the grounding step alone. Paid.

    python docs/probes/typed_queries_sweep.py OUT_FILE MAX_SPEND

The typed-queries test of 2026-11-14 found the answer's passage in 8 of 10
runs against 4 of 10, on three vague requests
(docs/reviews/2026-11-14-typed-queries.md). This asks what that test could
not: does the field harm a clear request, and does it hold on vague requests
it was not first tried on.

Two arms, each run on its own empty knowledge store:

  now            the code as it is: the blocking unknowns are looked up;
  typed_queries  the scoping call's JSON gains lookup_queries and the lookup
                 asks those; empty, the blocking unknowns are used, as now.
                 The wording is the last test's with one sentence added
                 after its one miss: no section number the request did not
                 give. Done by wrapping analyze_request; main is not changed.

Nine requests, two repeats each: five vague (IA, V17, V22 as before, V2 and
V12 new) and four clear (tier-2 Q2, Q12, Q17, Q22 as written). The record
keeps what the model put in the field beside its blocking unknowns.
typed_queries_answers.py imports this module for the same wrapper.
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
DIRECT = __name__ == "__main__"
OUT = Path(sys.argv[1]).resolve() if DIRECT else Path(".")
MAX_SPEND = float(sys.argv[2]) if DIRECT else 0.0
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
TIER2 = {q["id"]: q["question"] for q in
         json.loads((ROOT / "evals/tier2/questions.json").read_text())}
# IA is the owner's recorded request; V17 and V22 are the last two tests';
# V2 and V12 were written for this sweep before the run, in the same manner.
REQUESTS = {
    "IA": GOLDEN["side_test"]["request"],
    "V17": ("what are the requirments for lockout tagout devices regarding "
            "strength, (OSHA), https://www.ecfr.gov/ is a good source"),
    "V22": ("what are the rules for audiograms regarding new employees, "
            "(OSHA), https://www.ecfr.gov/ is a good source"),
    "V2": ("what are the rules for confined spaces regarding oxygen, (OSHA), "
           "https://www.ecfr.gov/ is a good source"),
    "V12": ("what are the limits for drinking water regarding arsenic, (EPA), "
            "https://www.ecfr.gov/ is a good source"),
    **{k: TIER2[k] for k in ("Q2", "Q12", "Q17", "Q22")},
}
VAGUE = ("IA", "V17", "V22", "V2", "V12")
REPEATS = {name: 2 for name in REQUESTS}
# Words of the sentence that states the answer, as in the earlier tests.
MARKS = {"IA": r"actively engaged",          # 14 CFR 65.91(c)(2)
         "V17": r"50 pounds", "Q17": r"50 pounds",    # 29 CFR 1910.147(c)(5)
         "V22": r"6 months|14 hours", "Q22": r"6 months|14 hours",  # 1910.95(g)(5)
         "V2": r"19\.5", "Q2": r"19\.5",              # 29 CFR 1910.146(b)
         "V12": r"0\.010", "Q12": r"0\.010"}          # 40 CFR 141.62(b)
ORIGINAL = ctx.analyze_request
PROMPT = ctx.SCOPING_PROMPT
TYPED_PROMPT = PROMPT + """
- lookup_queries: the questions to put to a search engine before answering.
  Each item is one question a published source answers directly. When the
  request can be read more than one way, one item per reading, each asking
  what that reading's answer is. Never an item about what the requester
  meant. Name no section or paragraph number the request did not give.
  Never more than three."""


FILLED: list[dict] = []


async def typed_queries(client, request):
    seen: list[dict] = []
    real = client.chat_json

    async def recording(*args, **kwargs):
        data, response = await real(*args, **kwargs)
        seen.append(data)
        return data, response

    client.chat_json = recording
    ctx.SCOPING_PROMPT = TYPED_PROMPT
    try:
        scoping, unknowns = await ORIGINAL(client, request)
    finally:
        client.chat_json = real
        ctx.SCOPING_PROMPT = PROMPT
    queries = [q.strip() for d in seen if isinstance(d, dict)
               for q in d.get("lookup_queries") or []
               if isinstance(q, str) and q.strip()][:3]
    FILLED.append({"lookup_queries": queries,
                   "blocking_unknowns": list(unknowns)})
    return scoping, queries or unknowns


async def run(arm: str, name: str, repeat: int) -> dict:
    store = tempfile.mkdtemp(prefix="store-", dir=OUT.parent)
    settings.chromadb_path = store
    ctx.analyze_request = typed_queries if arm == "typed_queries" else ORIGINAL
    client = OpenRouterClient()
    sources: list[dict] = []
    started = time.time()
    record = {"arm": arm, "question": name, "repeat": repeat}
    FILLED.clear()

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
            "scoped": list(FILLED),
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
        for repeat in range(1, max(REPEATS.values()) + 1):
            for name in REQUESTS:
                if repeat > REPEATS[name]:
                    continue
                for arm in ("now", "typed_queries"):
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


if __name__ == "__main__":
    asyncio.run(main())
