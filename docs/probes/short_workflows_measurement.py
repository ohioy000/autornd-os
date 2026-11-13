"""The short-workflow measurement of 2026-11-13: the tier-2 questions through
answer-and-recompute and verify-first, live.

    python docs/probes/short_workflows_measurement.py OUT_DIR SHARD SHARDS \
        REPEATS MAX_SPEND [QUESTION_ID ...]

One process is one shard: it takes every unit whose index is SHARD modulo
SHARDS, runs them in order through the real engine against its own scratch
database, and appends one JSON line per unit to OUT_DIR/shard-SHARD.jsonl,
flushed as the unit ends. A shard starts no unit once its own spend has
reached MAX_SPEND. The scorer is the tier-2 screen, never the result (D50).
Paid: it needs the owner's word and an amount before it is run.

Two settings choose the questions and the workflows; unset, the run is the
tier-2 run of 2026-11-13 exactly. MEASURE_SET is tier2, golden or tier4:
golden asks evals/golden's six questions and its side test, screened by the
golden scorer and, where the question is also tier-2's, by tier-2's; tier4
asks the frozen tier-4 questions with their own catalogue pages, as tier-4's
D-pages arm sends them, and has no screen: the reading is the result.
MEASURE_WORKFLOWS is a comma list of workflow names.
"""
from __future__ import annotations

import asyncio
import importlib.util
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
os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{OUT}/shard-{SHARD}.db"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "evals" / "tier2"))
sys.path.insert(0, str(ROOT / "evals" / "golden"))

import logging  # noqa: E402

logging.basicConfig(level=logging.ERROR)

from sqlalchemy import select  # noqa: E402
from sqlalchemy.orm import selectinload  # noqa: E402

import autornd.main  # noqa: E402,F401  registers every table
import score as golden_score  # noqa: E402
import scorer  # noqa: E402
from autornd import database  # noqa: E402
from autornd.api.routes import _detail  # noqa: E402
from autornd.config import settings  # noqa: E402
from autornd.engine.workflow import WORKFLOWS_DIR, WorkflowEngine  # noqa: E402
from autornd.models.workflow import Workflow  # noqa: E402
from autornd.routing.openrouter import OpenRouterClient  # noqa: E402

SET = os.environ.get("MEASURE_SET", "tier2")
WORKFLOWS = tuple(w for w in os.environ.get(
    "MEASURE_WORKFLOWS", "answer-and-recompute,verify-first").split(",") if w)
TIER2 = json.loads((ROOT / "evals/tier2/questions.json").read_text())
TIER4_BATCHES = ("pilot", "batch2", "batch3", "batch4", "batch5", "batch6")


def _questions() -> list[dict]:
    if SET == "tier2":
        return TIER2
    if SET == "golden":
        keys = json.loads((ROOT / "evals/golden/keys.json").read_text())
        return [{"id": q["id"], "shape": q["shape"], "question": q["request"],
                 "key": q} for q in keys["golden"] + [keys["side_test"]]]
    if SET == "tier4":
        spec = importlib.util.spec_from_file_location(
            "tier4_runner", ROOT / "evals" / "tier4" / "runner.py")
        tier4 = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = tier4   # its dataclasses look themselves up
        spec.loader.exec_module(tier4)
        out = []
        for name in TIER4_BATCHES:
            batch = tier4.load_batch(ROOT / "evals" / "tier4" / name)
            for candidate in json.loads(batch.candidates_path.read_text()):
                pages = candidate.get("corpus_pages")
                out.append({"id": candidate["id"], "shape": candidate["family"],
                            "question": tier4.d_pages_message(candidate, batch)
                            if pages else candidate["request"]})
        return out
    raise SystemExit(f"MEASURE_SET {SET!r} is not tier2, golden or tier4")


QUESTIONS = _questions()


def screen(question: dict, text: str) -> dict | None:
    """The screen's verdict on an answer: never the result (D50)."""
    if SET == "tier2":
        return scorer.score(question["id"], text)
    if SET == "golden":
        key = question["key"]
        held = golden_score.score(
            key, text, "core_items" if "core_items" in key else "items")
        out = {"golden": held, "golden_holds": all(held.values())}
        # Golden Q1 to Q5 are tier-2's Q1 to Q5 word for word (compared
        # 2026-11-13), so the two screens can stand side by side.
        if question["id"] in ("Q1", "Q2", "Q3", "Q4", "Q5"):
            out["tier2"] = scorer.score(question["id"], text)
        return out
    return None


def units() -> list[tuple[int, str, dict, int]]:
    """Every unit, in one fixed order: repeat, then question, then workflow."""
    out = []
    for repeat in range(1, REPEATS + 1):
        for question in QUESTIONS:
            if ONLY and question["id"] not in ONLY:
                continue
            for workflow in WORKFLOWS:
                out.append((len(out), workflow, question, repeat))
    return out


async def run_unit(workflow: str, question: dict, repeat: int) -> dict:
    # Each unit has its own empty knowledge store, so no unit recalls what
    # another looked up and the owner's store is not written to. The store
    # builds a fresh client from this path on every call.
    store = tempfile.mkdtemp(prefix="store-", dir=OUT)
    settings.chromadb_path = store
    try:
        return await _run_unit(workflow, question, repeat)
    finally:
        shutil.rmtree(store, ignore_errors=True)


async def _run_unit(workflow: str, question: dict, repeat: int) -> dict:
    client = OpenRouterClient()
    started = time.time()
    record = {"question": question["id"], "shape": question["shape"],
              "workflow": workflow, "repeat": repeat}
    try:
        async with database.async_session() as session:
            run = await WorkflowEngine(client, session).execute(
                question["question"],
                workflow_file=str(WORKFLOWS_DIR / f"{workflow}.yaml"))
            row = (await session.execute(
                select(Workflow).where(Workflow.id == run.id)
                .options(selectinload(Workflow.phases)))).scalar_one()
            detail = _detail(row)
        answer = detail.answer or ""
        candidate = detail.candidate if isinstance(detail.candidate, dict) else {}
        scored_text = answer or str(candidate.get("summary") or "")
        verdict = screen(question, scored_text) if scored_text else None
        triage = next((p.verdict for p in detail.phases if p.phase == "triage"), {})
        record.update({
            "status": detail.status, "error": detail.error,
            "cost": detail.total_cost, "liability": detail.unreconciled_liability,
            "delivered": bool(answer), "answer": answer,
            "candidate": "" if answer else scored_text,
            "scorer": verdict, "triage_risk": (triage or {}).get("risk"),
            "phases": [p.phase for p in detail.phases],
            "recompute_vote": detail.recompute_vote,
            "decisions": detail.decisions, "cautions": detail.cautions,
            "lookups": [{"lookup": s.get("lookup"),
                         "quotes": [q.get("status") for f in s.get("findings") or []
                                    for q in f.get("quotes") or []]}
                        for s in detail.sources],
        })
    except Exception as exc:
        record.update({"status": "raised",
                       "error": f"{type(exc).__name__}: {exc}"[:400],
                       "cost": getattr(client, "spend", 0.0)})
    finally:
        await client.close()
    record["seconds"] = round(time.time() - started, 1)
    return record


async def main() -> None:
    await database.init_db()
    log = (OUT / f"shard-{SHARD}.jsonl").open("a", encoding="utf-8")
    if SHARD == 0 and not (OUT / "header.json").exists():
        (OUT / "header.json").write_text(json.dumps({
            "models": {t: getattr(settings, f"model_{t}") for t in (
                "triage", "engineering", "architecture", "escalation",
                "research", "search", "ranker", "judge", "recompute",
                "decision")},
            "provider_order": settings.openrouter_provider_order,
            "set": SET,
            "dataset_version": scorer.MANIFEST["dataset_version"],
            "scorer_version": scorer.SCORER_VERSION,
            "golden_keys_version": json.loads(
                (ROOT / "evals/golden/keys.json").read_text())["version"],
            "workflows": WORKFLOWS, "repeats": REPEATS, "shards": SHARDS,
            "max_spend_per_shard": MAX_SPEND,
        }, indent=1))
    spent = 0.0
    for index, workflow, question, repeat in units():
        if index % SHARDS != SHARD:
            continue
        if spent >= MAX_SPEND:
            log.write(json.dumps({"question": question["id"], "workflow": workflow,
                                  "repeat": repeat, "status": "not_started",
                                  "skipped": True, "cost": 0.0}) + "\n")
            log.flush()
            continue
        record = await run_unit(workflow, question, repeat)
        spent += float(record.get("cost") or 0.0) + float(record.get("liability") or 0.0)
        record["shard_spent"] = round(spent, 6)
        log.write(json.dumps(record) + "\n")
        log.flush()
        print(SHARD, question["id"], workflow, repeat, record.get("status"),
              round(spent, 4), flush=True)


asyncio.run(main())
