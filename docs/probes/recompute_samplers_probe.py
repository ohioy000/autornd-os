"""The recompute step's samples from several models, on the same answer. Paid.

    SAMPLER_MODELS=<id>,<id>,... python docs/probes/recompute_samplers_probe.py \
        OUT_DIR SHARD SHARDS REPEATS MAX_SPEND [QUESTION_ID ...]

Run from the directory that holds the owner's `.env`. It needs the owner's
word and an amount before it is run.

One unit is one live answer through the default workflow, exactly as
shipped, with one addition. When the run reaches its recompute step, the
configured recompute model makes its three blind samples as always, and
then each model named in SAMPLER_MODELS makes three of its own, at the same
moment as each other, shown the very same request, context and asks. The
run goes on with the configured model's samples, so the answer, the vote
and the delivery are the shipped ones. Every model's samples are written
beside the unit, with the vote each would have given, worked out free by
the harness's own vote.

The other models are not pinned to a provider: the recompute tier's pin in
the owner's `.env` names a provider of the configured model only. Each
model reasons at its catalogue default.

The questions are the set where a summary misleads and H1 of the harder
set, both with keys the owner signed. One process is one shard and stops
starting units once its own spend, the other models' samples included, has
reached MAX_SPEND.
"""
from __future__ import annotations

import asyncio
import json
import os
import shutil
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
OUT = Path(sys.argv[1]).resolve()
SHARD, SHARDS, REPEATS = int(sys.argv[2]), int(sys.argv[3]), int(sys.argv[4])
MAX_SPEND = float(sys.argv[5])
ONLY = set(sys.argv[6:])
OUT.mkdir(parents=True, exist_ok=True)
# The database is named before the engine is imported, or the rows go to the
# default one.
os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{OUT}/shard-{SHARD}.db"
sys.path.insert(0, str(ROOT))

import logging  # noqa: E402

logging.basicConfig(level=logging.ERROR)

from sqlalchemy import select  # noqa: E402
from sqlalchemy.orm import selectinload  # noqa: E402

import autornd.main  # noqa: E402,F401  registers every table
from autornd import database  # noqa: E402
from autornd.api.routes import _detail  # noqa: E402
from autornd.config import settings  # noqa: E402
from autornd.engine import phases  # noqa: E402
from autornd.engine.workflow import WORKFLOWS_DIR, WorkflowEngine  # noqa: E402
from autornd.graph import checks  # noqa: E402
from autornd.graph.adapter import PhaseRunner  # noqa: E402
from autornd.models.workflow import Workflow  # noqa: E402
from autornd.routing.openrouter import OpenRouterClient, check_models  # noqa: E402

WORKFLOW = "answer-and-recompute"
CONFIGURED = settings.model_recompute
OTHERS = [m.strip() for m in os.environ.get("SAMPLER_MODELS", "").split(",")
          if m.strip() and m.strip() != CONFIGURED]
if not CONFIGURED or not OTHERS:
    raise SystemExit("the recompute tier must be configured, and SAMPLER_MODELS "
                     "must name at least one other model")


def _questions() -> list[dict]:
    out = []
    for name, wanted in (("misleading-questions.json", None),
                         ("hard-questions.json", {"H1"})):
        frozen = json.loads((ROOT / "evals/professional" / name).read_text())
        if str(frozen.get("status", "")).upper().startswith("DRAFT"):
            raise SystemExit(f"{name} is a draft: its keys are not signed off")
        out += [{"id": q["id"], "question": q["question"]}
                for q in frozen["questions"] if wanted is None or q["id"] in wanted]
    return out


def _unpinned(order: str) -> str:
    """The provider order with the recompute tier named and left empty, which
    is how one tier opts out of a pin (provider_order_for)."""
    kept = [entry.strip() for entry in (order or "").split(",") if entry.strip()
            and not entry.strip().lower().startswith("recompute:")]
    return ",".join([*kept, "recompute:"])


# What the wrapped recompute step saw and what each model returned, for the
# unit in hand. One process runs one unit at a time.
SIDE: dict = {}
_shipped_recompute = PhaseRunner._phase_recompute


async def _sample(model: str, request: str, context: str, asks, max_tokens) -> dict:
    client = OpenRouterClient()
    client.FUNCTION_MODELS = dict(OpenRouterClient.FUNCTION_MODELS, recompute=model)
    started = time.time()
    try:
        verdict, responses = await phases.run_recompute(
            client, request, context, asks, max_tokens=max_tokens, samples=3)
        return {"samples": verdict.get("samples") or [],
                "cost": round(sum(r.cost for r in responses), 6),
                "served_by": sorted({r.model for r in responses}),
                "completion_tokens": sum(r.completion_tokens for r in responses),
                "seconds": round(time.time() - started, 1)}
    except Exception as exc:
        return {"samples": [], "error": f"{type(exc).__name__}: {exc}"[:300],
                "cost": round(float(getattr(client, "spend", 0.0) or 0.0), 6),
                "seconds": round(time.time() - started, 1)}
    finally:
        await client.close()


async def _recompute_with_every_model(self, node, state):
    started = time.time()
    verdict, responses = await _shipped_recompute(self, node, state)
    asks = self._anchored_asks(state)
    SIDE.update({
        "asks": asks, "context_chars": len(self.context or ""),
        # The context itself, kept since the addendum of 2026-11-15, so a
        # model added later can be given the same samples to make without
        # the answer being made again.
        "context": self.context or "",
        "models": {CONFIGURED: {
            "samples": verdict.get("samples") or [],
            "cost": round(sum(r.cost for r in responses), 6),
            "served_by": sorted({r.model for r in responses}),
            "completion_tokens": sum(r.completion_tokens for r in responses),
            "seconds": round(time.time() - started, 1),
            "skipped": bool(verdict.get("skipped"))}}})
    if verdict.get("skipped"):
        return verdict, responses
    pinned = settings.openrouter_provider_order
    settings.openrouter_provider_order = _unpinned(pinned)
    try:
        others = await asyncio.gather(*(
            _sample(model, state.request, self.context, asks, self._max_tokens(node))
            for model in OTHERS))
    finally:
        settings.openrouter_provider_order = pinned
    SIDE["models"].update(dict(zip(OTHERS, others)))
    return verdict, responses


PhaseRunner._phase_recompute = _recompute_with_every_model


def _vote(results, samples, asks, request: str) -> dict:
    try:
        return dict(checks.recompute_vote(results or [], samples or [], asks or [],
                                          request).data)
    except Exception as exc:
        return {"error": f"{type(exc).__name__}: {exc}"[:200]}


async def run_unit(question: dict, repeat: int) -> dict:
    store = tempfile.mkdtemp(prefix="store-", dir=OUT)
    settings.chromadb_path = store
    SIDE.clear()
    client = OpenRouterClient()
    started = time.time()
    record = {"question": question["id"], "repeat": repeat}
    try:
        async with database.async_session() as session:
            run = await WorkflowEngine(client, session).execute(
                question["question"],
                workflow_file=str(WORKFLOWS_DIR / f"{WORKFLOW}.yaml"))
            row = (await session.execute(
                select(Workflow).where(Workflow.id == run.id)
                .options(selectinload(Workflow.phases)))).scalar_one()
            detail = _detail(row)
        results = next((p.verdict.get("results") for p in reversed(detail.phases)
                        if p.phase == "implement" and isinstance(p.verdict, dict)), None)
        models = SIDE.get("models") or {}
        for entry in models.values():
            entry["vote"] = _vote(results, entry.get("samples"), SIDE.get("asks"),
                                  question["question"])
        record.update({
            "status": detail.status, "error": detail.error,
            "cost": detail.total_cost, "liability": detail.unreconciled_liability,
            "answer": detail.answer or "", "results": results,
            "cautions": detail.cautions, "confirmations": detail.confirmations,
            "shipped_vote": detail.recompute_vote,
            "asks": SIDE.get("asks"), "context_chars": SIDE.get("context_chars"),
            "context": SIDE.get("context"),
            "models": models,
            "others_cost": round(sum(float(models[m].get("cost") or 0.0)
                                     for m in OTHERS if m in models), 6),
        })
    except Exception as exc:
        record.update({"status": "raised",
                       "error": f"{type(exc).__name__}: {exc}"[:400],
                       "cost": getattr(client, "spend", 0.0),
                       "models": dict(SIDE.get("models") or {})})
    finally:
        await client.close()
        shutil.rmtree(store, ignore_errors=True)
    record["seconds"] = round(time.time() - started, 1)
    return record


async def main() -> None:
    await database.init_db()
    # The catalogue's rates, as the server loads them at startup, so every
    # model named is priced before it is called.
    await check_models()
    questions = [q for q in _questions() if not ONLY or q["id"] in ONLY]
    units = [(question, repeat) for repeat in range(1, REPEATS + 1)
             for question in questions]
    log = (OUT / f"shard-{SHARD}.jsonl").open("a", encoding="utf-8")
    if SHARD == 0 and not (OUT / "header.json").exists():
        (OUT / "header.json").write_text(json.dumps({
            "configured_recompute": CONFIGURED, "other_samplers": OTHERS,
            "models": {t: getattr(settings, f"model_{t}") for t in (
                "triage", "engineering", "architecture", "escalation",
                "research", "search", "recompute", "decision")},
            "provider_order": settings.openrouter_provider_order,
            "provider_order_for_other_samplers":
                _unpinned(settings.openrouter_provider_order),
            "lookup_reads_documents": settings.lookup_reads_documents,
            "workflow": WORKFLOW, "repeats": REPEATS, "shards": SHARDS,
            "max_spend_per_shard": MAX_SPEND}, indent=1))
    spent = 0.0
    for index, (question, repeat) in enumerate(units):
        if index % SHARDS != SHARD:
            continue
        if spent >= MAX_SPEND:
            log.write(json.dumps({"question": question["id"], "repeat": repeat,
                                  "status": "not_started", "skipped": True}) + "\n")
            log.flush()
            continue
        record = await run_unit(question, repeat)
        spent += (float(record.get("cost") or 0.0) + float(record.get("liability") or 0.0)
                  + float(record.get("others_cost") or 0.0))
        record["shard_spent"] = round(spent, 6)
        log.write(json.dumps(record, default=str) + "\n")
        log.flush()
        print(SHARD, question["id"], repeat, record.get("status"), round(spent, 4),
              {m: (e.get("vote") or {}).get("flagged")
               for m, e in (record.get("models") or {}).items()}, flush=True)


asyncio.run(main())
