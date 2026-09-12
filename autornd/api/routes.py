"""REST API endpoints for AutoRnD."""

from __future__ import annotations

import json

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from autornd.database import get_session
from autornd.engine.workflow import WorkflowEngine
from autornd.models.workflow import PhaseResult, Workflow, WorkflowStatus
from autornd.routing.openrouter import OpenRouterClient

router = APIRouter(prefix="/api")


class WorkflowRequest(BaseModel):
    request: str


class WorkflowSummary(BaseModel):
    id: int
    request: str
    status: str
    risk_level: str | None
    iteration: int
    total_cost: float
    created_at: str
    updated_at: str


class PhaseDetail(BaseModel):
    phase: str
    iteration: int
    verdict: dict
    model_used: str | None
    cost: float
    created_at: str


class WorkflowDetail(WorkflowSummary):
    phases: list[PhaseDetail]


def _summarize(w: Workflow) -> WorkflowSummary:
    return WorkflowSummary(
        id=w.id,
        request=w.request[:200],
        status=w.status.value,
        risk_level=w.risk_level,
        iteration=w.iteration,
        total_cost=round(w.total_cost, 4),
        created_at=w.created_at.isoformat(),
        updated_at=w.updated_at.isoformat(),
    )


async def _run_workflow(request: str, session: AsyncSession):
    client = OpenRouterClient()
    engine = WorkflowEngine(client, session)
    try:
        await engine.execute(request)
    finally:
        await client.close()


@router.post("/workflows", status_code=202)
async def submit_workflow(
    body: WorkflowRequest,
    background: BackgroundTasks,
    session: AsyncSession = Depends(get_session),
):
    workflow = Workflow(request=body.request, status=WorkflowStatus.PENDING)
    session.add(workflow)
    await session.commit()

    background.add_task(_run_workflow_bg, workflow.id, body.request)

    return {
        "data": _summarize(workflow),
        "meta": {"message": "Workflow queued for execution"},
    }


async def _run_workflow_bg(workflow_id: int, request: str):
    from autornd.database import async_session

    async with async_session() as session:
        stmt = select(Workflow).where(Workflow.id == workflow_id)
        result = await session.execute(stmt)
        workflow = result.scalar_one()

        client = OpenRouterClient()
        engine = WorkflowEngine(client, session)
        try:
            await engine.execute(workflow.request)
        finally:
            await client.close()


@router.post("/workflows/sync")
async def submit_workflow_sync(
    body: WorkflowRequest,
    session: AsyncSession = Depends(get_session),
):
    """Execute a workflow synchronously and return the full result."""
    client = OpenRouterClient()
    engine = WorkflowEngine(client, session)
    try:
        workflow = await engine.execute(body.request)
    finally:
        await client.close()

    await session.refresh(workflow, ["phases"])
    return {"data": _detail(workflow)}


@router.get("/workflows")
async def list_workflows(
    limit: int = 20,
    offset: int = 0,
    session: AsyncSession = Depends(get_session),
):
    stmt = (
        select(Workflow)
        .order_by(Workflow.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    result = await session.execute(stmt)
    workflows = result.scalars().all()
    return {
        "data": [_summarize(w) for w in workflows],
        "meta": {"count": len(workflows), "limit": limit, "offset": offset},
    }


@router.get("/workflows/{workflow_id}")
async def get_workflow(
    workflow_id: int,
    session: AsyncSession = Depends(get_session),
):
    stmt = (
        select(Workflow)
        .where(Workflow.id == workflow_id)
        .options(selectinload(Workflow.phases))
    )
    result = await session.execute(stmt)
    workflow = result.scalar_one_or_none()
    if not workflow:
        raise HTTPException(404, "Workflow not found")
    return {"data": _detail(workflow)}


def _detail(w: Workflow) -> WorkflowDetail:
    phases = sorted(w.phases, key=lambda p: p.created_at)
    return WorkflowDetail(
        id=w.id,
        request=w.request,
        status=w.status.value,
        risk_level=w.risk_level,
        iteration=w.iteration,
        total_cost=round(w.total_cost, 4),
        created_at=w.created_at.isoformat(),
        updated_at=w.updated_at.isoformat(),
        phases=[
            PhaseDetail(
                phase=p.phase,
                iteration=p.iteration,
                verdict=json.loads(p.verdict_json),
                model_used=p.model_used,
                cost=round(p.cost, 6),
                created_at=p.created_at.isoformat(),
            )
            for p in phases
        ],
    )


@router.get("/health")
async def health():
    return {"status": "ok", "service": "autornd"}


@router.get("/profiles")
async def get_profiles():
    from autornd.profiles import get_profile, list_profiles
    active = get_profile()
    return {
        "data": {
            "active": active.name,
            "available": list_profiles(),
        }
    }


@router.post("/profiles/{name}")
async def switch_profile(name: str):
    from autornd.profiles import load_profile, set_profile
    from autornd.specialists.registry import reload_specialists
    profile = load_profile(name)
    set_profile(profile)
    reload_specialists()
    return {"data": {"active": profile.name}}


@router.get("/knowledge/stats")
async def knowledge_stats():
    from autornd.knowledge.store import get_stats
    return {"data": get_stats()}


@router.get("/episodes")
async def list_episodes(
    limit: int = 10,
    session: AsyncSession = Depends(get_session),
):
    from autornd.knowledge.episodic import get_recent_episodes
    episodes = await get_recent_episodes(session, limit=limit)
    return {
        "data": [
            {
                "id": ep.id,
                "workflow_id": ep.workflow_id,
                "request": ep.request[:200],
                "domains": ep.domains,
                "risk": ep.risk,
                "iterations": ep.iterations,
                "shipped": ep.shipped,
                "verdict": ep.verdict[:200],
                "findings_count": ep.findings_count,
                "total_cost": round(ep.total_cost, 4),
                "created_at": ep.created_at.isoformat(),
            }
            for ep in episodes
        ],
        "meta": {"count": len(episodes)},
    }
