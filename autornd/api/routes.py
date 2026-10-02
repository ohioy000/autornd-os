"""REST API endpoints for AutoRnD."""

from __future__ import annotations

import asyncio
import json

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from autornd.api.auth import _is_loopback
from autornd.config import settings
from autornd.database import get_session
from autornd.engine.workflow import WorkflowEngine
from autornd.models.workflow import PhaseResult, Workflow, WorkflowStatus
from autornd.routing.openrouter import OpenRouterClient

router = APIRouter(prefix="/api")


def _get_user_id(request: Request) -> int | None:
    return getattr(request.state, "user_id", None)


def _caller_key(request: Request) -> tuple:
    """Who is asking: their account when they have one, else their address."""
    user_id = _get_user_id(request)
    if user_id is not None:
        return ("user", user_id)
    return ("host", (request.client.host if request.client else "") or "")


class _RunGate:
    """Ruling D45 (6): a per-run ceiling bounds one run, not a caller who
    submits many. At most `settings.max_concurrent_runs` API runs in flight at
    once, and never twice the same request text from the same caller.

    Admission is refused BEFORE a Workflow row exists — a refused submission
    must leave nothing behind — and released when the run it admitted ends,
    whatever way it ends."""

    def __init__(self) -> None:
        self._in_flight: dict[tuple, set[str]] = {}

    def count(self) -> int:
        return sum(len(texts) for texts in self._in_flight.values())

    def admit(self, caller: tuple, request_text: str) -> str | None:
        """None when admitted (and registered); else 'duplicate' or 'cap'."""
        mine = self._in_flight.setdefault(caller, set())
        if request_text in mine:
            return "duplicate"
        if self.count() >= settings.max_concurrent_runs:
            return "cap"
        mine.add(request_text)
        return None

    def release(self, caller: tuple, request_text: str) -> None:
        mine = self._in_flight.get(caller)
        if mine:
            mine.discard(request_text)
            if not mine:
                self._in_flight.pop(caller, None)


_run_gate = _RunGate()


def _admit_run(request: Request, request_text: str) -> tuple:
    """Register an API run with the gate or refuse it with a sentence."""
    caller = _caller_key(request)
    verdict = _run_gate.admit(caller, request_text)
    if verdict == "duplicate":
        raise HTTPException(
            409,
            "This request is already running for this caller; wait for it to "
            "finish or submit different work.")
    if verdict == "cap":
        raise HTTPException(
            429,
            f"At most {settings.max_concurrent_runs} runs are in flight at "
            f"once (Ruling D45); wait for one to finish and submit again.")
    return caller


def _bound_client() -> OpenRouterClient:
    """A client for an API run, carrying the run's spend ceiling.

    Every client the API creates — both submit paths and doublecheck — is
    bounded (Ruling D45 (2)), so no call on this endpoint spends past the
    run's ceiling."""
    client = OpenRouterClient()
    client.spend_ceiling = settings.run_spend_ceiling_usd
    return client


# Ruling D45 (3): runtime settings can only tighten. A ceiling raised at
# runtime raises it for every run in flight, and any caller the middleware
# admits could do it — which is review A's F8. These are the values the
# process started with: a numeric ceiling may be lowered below them and never
# raised above them while the server runs. Non-numeric fields (profiles,
# workflow names, log level) steer nothing spend-shaped and are unchanged.
_STARTUP_VALUES = {
    name: getattr(settings, name) for name in settings.RUNTIME_MUTABLE
}


def _only_tightens(name: str, value) -> bool:
    startup = _STARTUP_VALUES.get(name)
    if isinstance(startup, bool) or not isinstance(startup, (int, float)):
        return True
    return value <= startup


# ── Auth endpoints ──

class RegisterRequest(BaseModel):
    username: str = Field(min_length=3, max_length=64)
    email: EmailStr
    # NIST SP 800-63B floor. Raise it in your own deployment if you want a
    # stricter policy — the harness shouldn't impose one on downstream users.
    password: str = Field(min_length=8, max_length=256)


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
    error: str | None = None
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
        error=w.error,
        risk_level=w.risk_level,
        iteration=w.iteration,
        total_cost=round(w.total_cost, 4),
        created_at=w.created_at.isoformat(),
        updated_at=w.updated_at.isoformat(),
    )


@router.post("/workflows", status_code=202)
async def submit_workflow(
    body: WorkflowRequest,
    request: Request,
    background: BackgroundTasks,
    session: AsyncSession = Depends(get_session),
):
    # Ruling D45 (6): refused here, before the row exists — a submission that
    # is not admitted must leave nothing behind. Ruling D47: a slot admitted
    # is a slot released — if the commit or the scheduling raises, the gate is
    # restored before the error reaches the caller.
    caller = _admit_run(request, body.request)
    try:
        workflow = Workflow(
            request=body.request,
            status=WorkflowStatus.PENDING,
            user_id=_get_user_id(request),
        )
        session.add(workflow)
        await session.commit()

        background.add_task(_run_workflow_bg, workflow.id, caller, body.request)
    except BaseException:
        _run_gate.release(caller, body.request)
        raise

    return {
        "data": _summarize(workflow),
        "meta": {"message": "Workflow queued for execution"},
    }


async def _run_workflow_bg(workflow_id: int, caller: tuple, request_text: str):
    from autornd.database import async_session

    try:
        async with async_session() as session:
            stmt = select(Workflow).where(Workflow.id == workflow_id)
            result = await session.execute(stmt)
            workflow = result.scalar_one()

            client = _bound_client()
            engine = WorkflowEngine(client, session)
            try:
                # The row the caller was handed is the row the run writes —
                # one submission, one record (ARCH-20261002-109).
                await engine.execute(workflow.request, workflow=workflow)
            finally:
                await client.close()
    finally:
        _run_gate.release(caller, request_text)


@router.post("/workflows/sync")
async def submit_workflow_sync(
    body: WorkflowRequest,
    request: Request,
    session: AsyncSession = Depends(get_session),
):
    """Execute a workflow synchronously and return the full result."""
    caller = _admit_run(request, body.request)

    try:
        workflow = Workflow(
            request=body.request,
            status=WorkflowStatus.PENDING,
            user_id=_get_user_id(request),
        )
        session.add(workflow)
        await session.commit()
    except BaseException:
        _run_gate.release(caller, body.request)
        raise

    client = _bound_client()
    engine = WorkflowEngine(client, session)
    try:
        workflow = await engine.execute(body.request, workflow=workflow)
    finally:
        await client.close()
        _run_gate.release(caller, body.request)

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


async def _load_owned_workflow(
    workflow_id: int, request: Request, session: AsyncSession
) -> Workflow:
    """Load a workflow by id, scoped to the caller when one is authenticated.

    Missing and not-yours both return 404 so ids stay non-enumerable.
    """
    stmt = (
        select(Workflow)
        .where(Workflow.id == workflow_id)
        .options(selectinload(Workflow.phases))
    )
    user_id = _get_user_id(request)
    if user_id is not None:
        stmt = stmt.where(Workflow.user_id == user_id)
    result = await session.execute(stmt)
    workflow = result.scalar_one_or_none()
    if not workflow:
        raise HTTPException(404, "Workflow not found")
    return workflow


@router.get("/workflows/{workflow_id}")
async def get_workflow(
    workflow_id: int,
    request: Request,
    session: AsyncSession = Depends(get_session),
):
    workflow = await _load_owned_workflow(workflow_id, request, session)
    return {"data": _detail(workflow)}


def _detail(w: Workflow) -> WorkflowDetail:
    phases = sorted(w.phases, key=lambda p: p.created_at)
    return WorkflowDetail(
        id=w.id,
        request=w.request,
        status=w.status.value,
        error=w.error,
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
    request: Request,
    session: AsyncSession = Depends(get_session),
):
    from autornd.config import settings
    if not settings.model_premium:
        raise HTTPException(404, "Premium model not configured")

    workflow = await _load_owned_workflow(workflow_id, request, session)
    if workflow.status.value not in ("completed", "escalated", "blocked"):
        raise HTTPException(400, "Workflow is still running")

    payload_chars = len(workflow.request)
    for p in workflow.phases:
        payload_chars += len(p.verdict_json)
    est_tokens = payload_chars // 3
    # Ruling D47 (2): every route that CAN spend passes the run gate. This one
    # makes no call — _estimate_cost is local arithmetic over the catalogue
    # rate — so there is nothing to admit and nothing to count.
    client = OpenRouterClient()
    cost = client._estimate_cost(settings.model_premium, est_tokens, est_tokens // 2)
    return {"data": {"estimated_cost": round(cost, 4), "model": settings.model_premium}}


@router.post("/workflows/{workflow_id}/doublecheck")
async def run_doublecheck_endpoint(
    workflow_id: int,
    request: Request,
    session: AsyncSession = Depends(get_session),
):
    from autornd.config import settings
    from autornd.engine.phases import run_doublecheck
    from autornd.models.verdicts import ImplementVerdict, PlanVerdict

    if not settings.model_premium:
        raise HTTPException(404, "Premium model not configured")

    workflow = await _load_owned_workflow(workflow_id, request, session)
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

    # Ruling D47 (2): the doublecheck can spend, so it passes the same run
    # gate as the submit paths and counts against max_concurrent_runs — no
    # caller multiplies the per-run bounds by calling this many times at once.
    # The dedupe key is the workflow's own request text: a second doublecheck
    # of a workflow the caller already has in flight is a duplicate (409).
    caller = _admit_run(request, workflow.request)
    try:
        client = _bound_client()
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
    finally:
        _run_gate.release(caller, workflow.request)


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
async def update_settings(body: SettingsUpdate, request: Request):
    import logging

    from autornd.config import settings

    # Ruling D45 (3): loopback only. A runtime change applies to every run in
    # flight, so it is not a remote caller's to make.
    if not _is_loopback(request):
        raise HTTPException(
            403, "Runtime settings are for loopback callers only (Ruling "
                 "D45); change them in .env or from this machine.")

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

    # After the validators: an invalid value is still 422. This is the rule
    # itself — Ruling D45 (3): a ceiling may be lowered at runtime and never
    # raised above its startup value, because a raise applies to every run in
    # flight and any caller the middleware admits could make it (review F8).
    raised = [name for name, value in updates.items()
              if not _only_tightens(name, value)]
    if raised:
        raise HTTPException(
            400,
            "Runtime settings can only tighten (Ruling D45); "
            f"{', '.join(sorted(raised))} would be raised above its startup "
            f"value. Change it in .env and restart.")

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
    # `None` means the catalogue check itself failed — that is a degraded state,
    # not a healthy one. Only an explicit True counts as verified.
    unverified = [
        fn for fn, st in model_status.items() if st.get("available") is not True
    ]
    return {
        "status": "degraded" if unverified else "ok",
        "unverified_models": unverified,
        "service": "autornd",
        "premium_model": settings.model_premium or None,
        # Ruling D45 (1): the override is reported here and logged at
        # startup, so an open server cannot be mistaken for a closed one.
        "authentication_configured": bool(settings.api_key or settings.jwt_secret),
        "allow_unauthenticated_remote": settings.allow_unauthenticated_remote,
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
async def switch_profile(name: str, request: Request):
    from autornd.profiles import load_profile, set_profile
    from autornd.specialists.registry import reload_specialists

    # Ruling D45 (3): swapping the profile rewrites every specialist prompt
    # for every run in flight — loopback only, like the settings it shadows.
    if not _is_loopback(request):
        raise HTTPException(
            403, "Switching profiles is for loopback callers only (Ruling "
                 "D45); set AUTORND_PROFILE in .env or use this machine.")
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
    request: Request,
    limit: int = 10,
    session: AsyncSession = Depends(get_session),
):
    from autornd.knowledge.episodic import get_recent_episodes

    # Ruling D45 (4): a caller sees their own runs, as /api/workflows does.
    episodes = await get_recent_episodes(
        session, limit=limit, user_id=_get_user_id(request))
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
