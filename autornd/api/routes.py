"""REST API endpoints for AutoRnD."""

from __future__ import annotations

import json

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from autornd.database import get_session
from autornd.engine.workflow import WorkflowEngine
from autornd.models.workflow import PhaseResult, Workflow, WorkflowStatus
from autornd.routing.openrouter import OpenRouterClient

router = APIRouter(prefix="/api")


def _get_user_id(request: Request) -> int | None:
    return getattr(request.state, "user_id", None)


# ── Auth endpoints ──

class RegisterRequest(BaseModel):
    username: str
    email: str
    password: str


class LoginRequest(BaseModel):
    username: str
    password: str


@router.post("/auth/register", status_code=201)
async def register(body: RegisterRequest, session: AsyncSession = Depends(get_session)):
    from autornd.api.auth import create_token, hash_password
    from autornd.config import settings
    from autornd.models.user import User

    if not settings.registration_enabled:
        raise HTTPException(403, "Registration is disabled")

    existing = await session.execute(
        select(User).where((User.username == body.username) | (User.email == body.email))
    )
    if existing.scalar_one_or_none():
        raise HTTPException(409, "Username or email already taken")

    user = User(
        username=body.username,
        email=body.email,
        password_hash=hash_password(body.password),
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)

    token = create_token(user.id, user.username)
    return {"data": {"id": user.id, "username": user.username, "token": token}}


@router.post("/auth/login")
async def login(body: LoginRequest, session: AsyncSession = Depends(get_session)):
    from autornd.api.auth import create_token, verify_password
    from autornd.models.user import User

    result = await session.execute(select(User).where(User.username == body.username))
    user = result.scalar_one_or_none()
    if not user or not verify_password(body.password, user.password_hash):
        raise HTTPException(401, "Invalid username or password")

    token = create_token(user.id, user.username)
    return {"data": {"id": user.id, "username": user.username, "token": token}}


@router.get("/auth/me")
async def get_me(request: Request):
    user_id = _get_user_id(request)
    username = getattr(request.state, "username", None)
    if not user_id:
        return {"data": {"id": None, "username": None, "anonymous": True}}
    return {"data": {"id": user_id, "username": username, "anonymous": False}}


# ── Workflow endpoints ──

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
    request: Request,
    background: BackgroundTasks,
    session: AsyncSession = Depends(get_session),
):
    workflow = Workflow(
        request=body.request,
        status=WorkflowStatus.PENDING,
        user_id=_get_user_id(request),
    )
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
    request: Request,
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
    request: Request,
    limit: int = 20,
    offset: int = 0,
    session: AsyncSession = Depends(get_session),
):
    stmt = select(Workflow).order_by(Workflow.created_at.desc())
    user_id = _get_user_id(request)
    if user_id is not None:
        stmt = stmt.where(Workflow.user_id == user_id)
    stmt = stmt.limit(limit).offset(offset)
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


@router.get("/workflows/{workflow_id}/doublecheck/estimate")
async def estimate_doublecheck(
    workflow_id: int,
    session: AsyncSession = Depends(get_session),
):
    from autornd.config import settings
    if not settings.model_premium:
        raise HTTPException(404, "Premium model not configured")

    stmt = (
        select(Workflow)
        .where(Workflow.id == workflow_id)
        .options(selectinload(Workflow.phases))
    )
    result = await session.execute(stmt)
    workflow = result.scalar_one_or_none()
    if not workflow:
        raise HTTPException(404, "Workflow not found")
    if workflow.status.value not in ("completed", "escalated", "blocked"):
        raise HTTPException(400, "Workflow is still running")

    payload_chars = len(workflow.request)
    for p in workflow.phases:
        payload_chars += len(p.verdict_json)
    est_tokens = payload_chars // 3
    client = OpenRouterClient()
    cost = client._estimate_cost(settings.model_premium, est_tokens, est_tokens // 2)
    return {"data": {"estimated_cost": round(cost, 4), "model": settings.model_premium}}


@router.post("/workflows/{workflow_id}/doublecheck")
async def run_doublecheck_endpoint(
    workflow_id: int,
    session: AsyncSession = Depends(get_session),
):
    from autornd.config import settings
    from autornd.engine.phases import run_doublecheck
    from autornd.models.verdicts import ImplementVerdict, PlanVerdict

    if not settings.model_premium:
        raise HTTPException(404, "Premium model not configured")

    stmt = (
        select(Workflow)
        .where(Workflow.id == workflow_id)
        .options(selectinload(Workflow.phases))
    )
    result = await session.execute(stmt)
    workflow = result.scalar_one_or_none()
    if not workflow:
        raise HTTPException(404, "Workflow not found")
    if workflow.status.value not in ("completed", "escalated", "blocked"):
        raise HTTPException(400, "Workflow is still running")

    plan_data = None
    impl_data = None
    for p in sorted(workflow.phases, key=lambda x: x.created_at):
        v = json.loads(p.verdict_json)
        if p.phase == "plan" and plan_data is None:
            plan_data = v
        if p.phase == "implement":
            impl_data = v

    if not plan_data or not impl_data:
        raise HTTPException(400, "Workflow missing plan or implement phase")

    plan = PlanVerdict(**plan_data)
    implement = ImplementVerdict(**impl_data)

    client = OpenRouterClient()
    try:
        verdict, response = await run_doublecheck(
            client, workflow.request, plan, implement,
        )
    finally:
        await client.close()

    phase_result = PhaseResult(
        workflow_id=workflow.id,
        phase="doublecheck",
        iteration=1,
        verdict_json=json.dumps(verdict.model_dump()),
        model_used=response.model,
        cost=response.cost,
    )
    session.add(phase_result)
    workflow.total_cost += response.cost
    await session.commit()

    return {
        "data": {
            "verdict": verdict.model_dump(),
            "model": response.model,
            "cost": round(response.cost, 4),
        }
    }


# ── Settings endpoints ──

SENSITIVE_FIELDS = {"openrouter_api_key", "api_key", "jwt_secret"}


@router.get("/settings")
async def get_settings():
    from autornd.config import Settings, settings

    data = {}
    for field_name in Settings.model_fields:
        if field_name in ("model_config", "RUNTIME_MUTABLE"):
            continue
        val = getattr(settings, field_name)
        if field_name in SENSITIVE_FIELDS and val:
            val = "****" + val[-4:] if len(val) > 4 else "****"
        data[field_name] = val
    return {
        "data": data,
        "meta": {"runtime_mutable": sorted(settings.RUNTIME_MUTABLE)},
    }


class SettingsUpdate(BaseModel):
    max_iterations: int | None = None
    escalation_max_tokens: int | None = None
    escalation_recovery_attempts: int | None = None
    autornd_profile: str | None = None
    log_level: str | None = None


@router.put("/settings")
async def update_settings(body: SettingsUpdate):
    import logging

    from autornd.config import settings

    updates = body.model_dump(exclude_none=True)
    if not updates:
        raise HTTPException(400, "No settings to update")

    bad = set(updates) - settings.RUNTIME_MUTABLE
    if bad:
        raise HTTPException(400, f"Cannot change at runtime: {', '.join(sorted(bad))}")

    if "max_iterations" in updates:
        v = updates["max_iterations"]
        if not 1 <= v <= 20:
            raise HTTPException(422, "max_iterations must be between 1 and 20")

    if "log_level" in updates:
        valid = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        if updates["log_level"].upper() not in valid:
            raise HTTPException(422, f"log_level must be one of {sorted(valid)}")
        updates["log_level"] = updates["log_level"].upper()

    profile_changed = False
    for key, val in updates.items():
        if key == "autornd_profile" and val != settings.autornd_profile:
            profile_changed = True
        setattr(settings, key, val)

    if "log_level" in updates:
        logging.getLogger("autornd").setLevel(updates["log_level"])

    if profile_changed and settings.autornd_profile:
        from autornd.profiles import load_profile, set_profile
        from autornd.specialists.registry import reload_specialists
        profile = load_profile(settings.autornd_profile)
        set_profile(profile)
        reload_specialists()

    return {"data": {"updated": list(updates.keys())}}


@router.get("/health")
async def health():
    from autornd.config import settings
    from autornd.routing.openrouter import get_model_status

    model_status = get_model_status()
    any_unavailable = any(s.get("available") is False for s in model_status.values())
    return {
        "status": "degraded" if any_unavailable else "ok",
        "service": "autornd",
        "premium_model": settings.model_premium or None,
        "models": model_status,
    }


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
