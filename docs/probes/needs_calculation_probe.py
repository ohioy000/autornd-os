"""The needs_calculation switch asked alone, on requests of a known kind. Paid.

    python docs/probes/needs_calculation_probe.py OUT_FILE MAX_SPEND

Run from the directory that holds the owner's `.env`. It needs the owner's
word and an amount before it is run.

Every question of the three professional sets and of the tier-2 set is put
to the switch as shipped (switches/default.yaml), one request each, through
the harness's own switchboard on the decision tier. No answer is made and
no lookup runs. One line per question is written: its set, its shape where
the set gives one, the probability, the choice and the route. It stops
asking once its spend has reached MAX_SPEND.
"""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
OUT = Path(sys.argv[1]).resolve()
MAX_SPEND = float(sys.argv[2])
sys.path.insert(0, str(ROOT))

import logging  # noqa: E402

logging.basicConfig(level=logging.ERROR)

from autornd.config import settings  # noqa: E402
from autornd.routing.openrouter import OpenRouterClient, check_models  # noqa: E402
from autornd.routing.switches import Switchboard, load_switches  # noqa: E402

SWITCH = "needs_calculation"


def _questions() -> list[dict]:
    out = []
    for name in ("questions.json", "hard-questions.json",
                 "misleading-questions.json"):
        frozen = json.loads((ROOT / "evals/professional" / name).read_text())
        out += [{"set": name, "id": q["id"], "shape": "PROFESSIONAL",
                 "question": q["question"]} for q in frozen["questions"]]
    tier2 = json.loads((ROOT / "evals/tier2/questions.json").read_text())
    out += [{"set": "tier2", "id": q["id"], "shape": q["shape"],
             "question": q["question"]} for q in tier2]
    return out


async def main() -> None:
    if not settings.model_decision:
        raise SystemExit("the decision tier is not configured")
    await check_models()
    declared = {SWITCH: load_switches()[SWITCH]}
    client = OpenRouterClient()
    board = Switchboard(client, declared)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("a", encoding="utf-8") as log:
        log.write(json.dumps({"record": "header", "switch": SWITCH,
                              "mode": declared[SWITCH].mode,
                              "decision_model": settings.model_decision,
                              "max_spend": MAX_SPEND}) + "\n")
        try:
            for q in _questions():
                if client.spend >= MAX_SPEND:
                    log.write(json.dumps({**q, "status": "not_started"}) + "\n")
                    continue
                records = await board.ask(
                    [(SWITCH, "request", {"request": q["question"]})])
                board.drain_responses()
                record = records[0] if records else {}
                log.write(json.dumps({
                    "set": q["set"], "id": q["id"], "shape": q["shape"],
                    "probability": record.get("probability"),
                    "choice": record.get("choice"),
                    "route": record.get("route"),
                    "spent": round(client.spend, 6)}) + "\n")
                log.flush()
        finally:
            await client.close()
    print("asked", len(_questions()), "spent", round(client.spend, 6))


asyncio.run(main())
