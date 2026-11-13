"""The same-meaning replay of 2026-11-13: does a decision model tell a text
value that says what the samples said, in other words, from one that says
something else? Preregistered in docs/preregistration-20261113-golden-decisions.md.

    python docs/probes/same_meaning_replay.py OUT.json PHASES.jsonl [...]

Each PHASES file is a shard's database exported a row per line, as in
docs/traces/*-phases-shard-N.jsonl. Every disagreement a recompute vote
recorded on a text value is put to the decision tier through the real
Switchboard, with the request, the answer's value and the first agreeing
sample's own words, beside the six contrary pairs the preregistration fixed.
The question is asked here only; no workflow asks it. Paid: under a cent.
"""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from autornd.graph.checks import _recompute_ident  # noqa: E402
from autornd.routing.openrouter import OpenRouterClient  # noqa: E402
from autornd.routing.switches import (MAX_QUESTIONS, SHADOW, Switch,  # noqa: E402
                                      Switchboard)

SAME_MEANING = Switch(
    name="same_meaning",
    question="Do the two values state the same thing for this ask?",
    yes="They state the same fact, figure or verdict, even in other words "
        "or with more detail.",
    no="They state a different fact, figure or verdict, or one contradicts "
       "the other.",
    yes_at=0.80, no_at=0.20, safe="yes", mode=SHADOW)

TIER2 = {q["id"]: q["question"] for q in json.loads(
    (ROOT / "evals/tier2/questions.json").read_text())}
# Written before the run (the preregistration's list): the second value of
# each means something other than the first.
CONTRARY = [
    ("Q24", "same direction as the driver", "opposite direction to the driver"),
    ("Q24", "not the same direction as the driver", "same direction"),
    ("Q6", "XOR: Alarm = A ⊕ B = A'B + AB'", "XNOR"),
    ("Q12", "as Nitrogen (as N)", "as nitrate ion (as NO3)"),
    ("Q17", "at least annually (no less than once every 12 months)",
     "at least every two years"),
    ("Q7", "8 h at 90 dBA; 4 h at 95 dBA; 2 h at 100 dBA", "8; 2; 1"),
]


def disagreements(path: Path) -> list[dict]:
    """Every text disagreement a vote recorded in one exported shard.
    Workflow ids restart in each shard, so the join stays in one file."""
    rows = [json.loads(line) for line in path.open(encoding="utf-8")]
    requests = {r["id"]: r["request"] for r in rows if r["kind"] == "workflow"}
    phases = [r for r in rows if r["kind"] == "phase"]
    out = []
    for vote in phases:
        if vote["phase"] != "recompute_vote":
            continue
        wid = vote["workflow_id"]
        samples = next((p["verdict"].get("samples") or [] for p in phases
                        if p["workflow_id"] == wid and p["phase"] == "recompute"), [])
        for d in vote["verdict"].get("disagreements") or []:
            if not isinstance(d.get("answer"), str):
                continue
            words = next((r.get("value") for s in samples
                          for r in s.get("results") or []
                          if r.get("ask") == d["ask"]
                          and _recompute_ident(r.get("value")) == d["majority"]),
                         d["majority"])
            out.append({"kind": "real", "source": f"{path.name} workflow {wid}",
                        "request": requests[wid], "ask": d["ask"],
                        "answer_value": d["answer"], "sample_value": str(words)})
    return out


async def main() -> None:
    pairs = [p for name in sys.argv[2:] for p in disagreements(Path(name))]
    pairs += [{"kind": "contrary", "source": f"preregistered, from {qid}",
               "request": TIER2[qid], "ask": None,
               "answer_value": a, "sample_value": b} for qid, a, b in CONTRARY]
    client = OpenRouterClient()
    board = Switchboard(client, {"same_meaning": SAME_MEANING})
    try:
        for start in range(0, len(pairs), MAX_QUESTIONS):
            chunk = pairs[start:start + MAX_QUESTIONS]
            records = await board.ask([
                ("same_meaning", str(start + i),
                 {"request": p["request"], "answer_value": p["answer_value"],
                  "sample_value": p["sample_value"]})
                for i, p in enumerate(chunk)])
            for pair, record in zip(chunk, records):
                pair.update(probability=record["probability"], choice=record["choice"])
    finally:
        await client.close()
    cost = sum(r.cost for r in board.responses)
    Path(sys.argv[1]).write_text(json.dumps(
        {"decision_model": client.get_model("decision"), "cost": cost,
         "pairs": pairs}, indent=1, ensure_ascii=False))
    for p in pairs:
        print(f"{p['kind']:8} {p['choice']:11} {p['probability']}"
              f" | {p['answer_value'][:60]!r} / {p['sample_value'][:40]!r}")
    print(f"pairs {len(pairs)} cost ${cost:.5f}")


asyncio.run(main())
