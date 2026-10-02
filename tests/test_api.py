"""Test API endpoints."""

import asyncio
import json
from unittest.mock import AsyncMock

import pytest

from autornd.models.workflow import PhaseResult, Workflow, WorkflowStatus


@pytest.mark.asyncio
class TestHealthEndpoint:
    async def test_health(self, api_client):
        resp = await api_client.get("/api/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["service"] == "autornd"

    async def test_health_shows_premium_model(self, api_client):
        resp = await api_client.get("/api/health")
        data = resp.json()
        assert "premium_model" in data

    async def test_health_shows_model_status(self, api_client):
        resp = await api_client.get("/api/health")
        data = resp.json()
        assert "models" in data

    async def test_health_degraded_when_model_unavailable(self, api_client, monkeypatch):
        from autornd.routing import openrouter
        monkeypatch.setattr(openrouter, "_model_status", {
            "triage": {"model": "bad/model", "available": False},
        })
        resp = await api_client.get("/api/health")
        assert resp.json()["status"] == "degraded"

    async def test_health_ok_when_all_available(self, api_client, monkeypatch):
        from autornd.routing import openrouter
        monkeypatch.setattr(openrouter, "_model_status", {
            "triage": {"model": "some/model", "available": True},
        })
        resp = await api_client.get("/api/health")
        assert resp.json()["status"] == "ok"


@pytest.mark.asyncio
class TestWorkflowEndpoints:
    async def test_list_empty(self, api_client):
        resp = await api_client.get("/api/workflows")
        assert resp.status_code == 200
        body = resp.json()
        assert body["data"] == []
        assert body["meta"]["count"] == 0

    async def test_get_missing_workflow(self, api_client):
        resp = await api_client.get("/api/workflows/999")
        assert resp.status_code == 404


class TestSpecialistRegistry:
    def test_all_specialists_registered(self):
        from autornd.models.verdicts import SpecialistRole
        from autornd.specialists.registry import SPECIALISTS

        for role in SpecialistRole:
            assert role in SPECIALISTS, f"{role} not registered"

    def test_specialist_prompts_nonempty(self):
        from autornd.specialists.registry import SPECIALISTS

        for role, spec in SPECIALISTS.items():
            assert len(spec.system_prompt) > 100, f"{role} prompt too short"
            assert "JSON" in spec.system_prompt, f"{role} prompt missing JSON instruction"

    def test_architect_uses_architecture_route(self):
        from autornd.models.verdicts import SpecialistRole
        from autornd.specialists.registry import SPECIALISTS

        assert SPECIALISTS[SpecialistRole.SYSTEMS_ARCHITECT].router_function == "architecture"

    def test_engineers_use_engineering_route(self):
        from autornd.models.verdicts import SpecialistRole
        from autornd.specialists.registry import SPECIALISTS

        engineering_roles = [
            SpecialistRole.FIRMWARE_ENGINEER,
            SpecialistRole.HARDWARE_ENGINEER,
            SpecialistRole.BACKEND_ENGINEER,
            SpecialistRole.FRONTEND_ENGINEER,
            SpecialistRole.TEST_ENGINEER,
            SpecialistRole.SUPPLY_CHAIN,
        ]
        for role in engineering_roles:
            assert SPECIALISTS[role].router_function == "engineering"


@pytest.mark.asyncio
class TestDoubleCheckEndpoints:
    async def test_estimate_404_when_no_premium(self, api_client):
        resp = await api_client.get("/api/workflows/999/doublecheck/estimate")
        assert resp.status_code == 404

    async def test_run_404_when_no_premium(self, api_client):
        resp = await api_client.post("/api/workflows/999/doublecheck")
        assert resp.status_code == 404

    async def test_estimate_404_missing_workflow(self, api_client, db_session, monkeypatch):
        from autornd import config
        monkeypatch.setattr(config.settings, "model_premium", "test/premium-model")
        resp = await api_client.get("/api/workflows/999/doublecheck/estimate")
        assert resp.status_code == 404

    async def test_estimate_returns_cost(self, api_client, db_session, monkeypatch):
        from autornd import config
        monkeypatch.setattr(config.settings, "model_premium", "test/premium-model")

        w = Workflow(request="test request", status=WorkflowStatus.COMPLETED)
        db_session.add(w)
        await db_session.flush()
        plan_phase = PhaseResult(
            workflow_id=w.id, phase="plan", iteration=1,
            verdict_json=json.dumps({"ready": True, "plan": "do it", "blockers": [], "success_criteria": []}),
            model_used="test", cost=0.001,
        )
        db_session.add(plan_phase)
        await db_session.commit()

        resp = await api_client.get(f"/api/workflows/{w.id}/doublecheck/estimate")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert "estimated_cost" in data
        assert data["model"] == "test/premium-model"


@pytest.mark.asyncio
class TestHealthReportsUnverifiedModels:
    """Regression: the degraded check tested `available is False`, so when the
    catalogue fetch failed every tier went None and health still said 'ok' —
    silent in exactly the case the warning exists for."""

    async def test_unknown_availability_is_degraded_not_ok(self, api_client, monkeypatch):
        from autornd.routing import openrouter

        monkeypatch.setattr(
            openrouter, "_model_status",
            {"triage": {"model": "v/t", "available": None},
             "engineering": {"model": "v/e", "available": None}},
        )
        resp = await api_client.get("/api/health")
        body = resp.json()
        assert body["status"] == "degraded"
        assert set(body["unverified_models"]) == {"triage", "engineering"}

    async def test_all_verified_is_ok(self, api_client, monkeypatch):
        from autornd.routing import openrouter

        monkeypatch.setattr(
            openrouter, "_model_status",
            {"triage": {"model": "v/t", "available": True}},
        )
        resp = await api_client.get("/api/health")
        assert resp.json()["status"] == "ok"
        assert resp.json()["unverified_models"] == []


@pytest.mark.asyncio
class TestWorkflowErrorIsSurfaced:
    """Regression: infrastructure faults and legitimate plan-blocks both ended as
    `blocked` with no reason anywhere in the API — the cause lived only in stderr."""

    async def test_error_reaches_the_api(self, api_client, db_session):
        from autornd.models.workflow import Workflow, WorkflowStatus

        wf = Workflow(
            request="doomed run",
            status=WorkflowStatus.BLOCKED,
            error="HTTPStatusError: Client error '401 Unauthorized'",
        )
        db_session.add(wf)
        await db_session.commit()

        detail = await api_client.get(f"/api/workflows/{wf.id}")
        assert "401 Unauthorized" in detail.json()["data"]["error"]

        listed = await api_client.get("/api/workflows")
        assert listed.json()["data"][0]["error"] is not None

    async def test_healthy_workflow_has_no_error(self, api_client, db_session):
        from autornd.models.workflow import Workflow, WorkflowStatus

        wf = Workflow(request="fine", status=WorkflowStatus.COMPLETED)
        db_session.add(wf)
        await db_session.commit()

        resp = await api_client.get(f"/api/workflows/{wf.id}")
        assert resp.json()["data"]["error"] is None


@pytest.mark.asyncio
class TestAdditiveMigration:
    """Upgrading a live database must not need manual SQL — create_all only
    creates missing tables, never alters an existing one."""

    async def test_adds_error_column_to_an_old_table(self, tmp_path):
        from sqlalchemy import text
        from sqlalchemy.ext.asyncio import create_async_engine
        from autornd.database import _add_missing_columns

        db = tmp_path / "old.db"
        eng = create_async_engine(f"sqlite+aiosqlite:///{db}")
        async with eng.begin() as conn:
            # a workflows table as it looked before the error column existed
            await conn.execute(text(
                "CREATE TABLE workflows (id INTEGER PRIMARY KEY, request TEXT)"))
        async with eng.begin() as conn:
            await conn.run_sync(_add_missing_columns)
        async with eng.begin() as conn:
            cols = [r[1] for r in (await conn.execute(text("PRAGMA table_info(workflows)")))]
        await eng.dispose()
        assert "error" in cols

    async def test_is_idempotent(self, tmp_path):
        from sqlalchemy import text
        from sqlalchemy.ext.asyncio import create_async_engine
        from autornd.database import _add_missing_columns

        db = tmp_path / "twice.db"
        eng = create_async_engine(f"sqlite+aiosqlite:///{db}")
        async with eng.begin() as conn:
            await conn.execute(text(
                "CREATE TABLE workflows (id INTEGER PRIMARY KEY, request TEXT)"))
        for _ in range(3):
            async with eng.begin() as conn:
                await conn.run_sync(_add_missing_columns)
        async with eng.begin() as conn:
            cols = [r[1] for r in (await conn.execute(text("PRAGMA table_info(workflows)")))]
        await eng.dispose()
        assert cols.count("error") == 1


# ── ARCH-20261002-109: workflow identity, progress, and the terminal cast ──
#
# (a)-(d) run through the real routes (httpx ASGITransport) against the real
# engine and the real graph, on the provider-free double that still bills.
# The database is file-backed: a "second session" is then a second connection,
# so what it sees was committed, and test (c) can see progress mid-run at all
# — on the shared in-memory connection an uncommitted row would be visible too.


async def _wire_file_backed_run(tmp_path, monkeypatch, delays=None):
    """The run path on a file-backed database, with the provider-free double.

    The app and the background runner share one session factory; a second
    engine over the same file is the observer. Returns the clients the run
    path builds (so a test can read what was called and billed) and the
    observer's factory.
    """
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

    import autornd.database as database
    from autornd.api import routes
    from autornd.database import Base, get_session
    from autornd.main import app
    from tests.conftest import make_mock_client
    from tests.test_watchdog import _responses

    db = tmp_path / "run.db"
    run_engine = create_async_engine(
        f"sqlite+aiosqlite:///{db}", connect_args={"timeout": 30})
    observer_engine = create_async_engine(
        f"sqlite+aiosqlite:///{db}", connect_args={"timeout": 30})
    run_factory = async_sessionmaker(
        run_engine, class_=AsyncSession, expire_on_commit=False)
    observer_factory = async_sessionmaker(
        observer_engine, class_=AsyncSession, expire_on_commit=False)

    async with run_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async def _override():
        async with run_factory() as session:
            yield session

    app.dependency_overrides[get_session] = _override
    monkeypatch.setattr(database, "async_session", run_factory)

    made: list = []

    def _make_client():
        client = make_mock_client(_responses(), delays=delays)
        # The double answers chat but leaves `rerank` real, and a run ingests
        # what it looks up — so a later retrieval would probe the provider's
        # rerank API from inside a test. Stubbed here: these tests make no
        # provider call, billed or not.
        client.rerank = AsyncMock(
            side_effect=RuntimeError("rerank is not part of the test double"))
        made.append(client)
        return client

    monkeypatch.setattr(routes, "OpenRouterClient", _make_client)
    return made, observer_factory


@pytest.mark.asyncio
class TestOneRowPerSubmission:
    """(a) The id the caller is handed is the id the run writes. Before the
    repair the background task ran against a second row — no user_id, no
    phases the caller could see — and the submitted row stayed PENDING."""

    async def test_the_submitted_id_runs_finishes_and_stays_one_row(
        self, api_client, tmp_path, monkeypatch
    ):
        from collections import Counter

        from sqlalchemy import select
        from tests.test_watchdog import REQUEST

        clients, observer_factory = await _wire_file_backed_run(tmp_path, monkeypatch)

        resp = await api_client.post("/api/workflows", json={"request": REQUEST})
        assert resp.status_code == 202
        submitted_id = resp.json()["data"]["id"]

        detail = (await api_client.get(f"/api/workflows/{submitted_id}")).json()["data"]
        assert detail["status"] == "completed", detail["error"]
        assert detail["phases"], "the run's phases never reached the submitted row"

        async with observer_factory() as session:
            rows = (await session.execute(select(Workflow))).scalars().all()
            db_phases = (await session.execute(select(PhaseResult))).scalars().all()
        assert [w.id for w in rows] == [submitted_id], (
            f"{len(rows)} Workflow rows for one submission")

        # Nothing written twice: the phase rows never outnumber the paid
        # calls whose responses they record.
        calls = clients[0].calls_by_function
        for model, n in Counter(p.model_used for p in db_phases).items():
            function = model.removeprefix("mock-")
            assert n <= calls.get(function, 0), (
                f"{n} phase rows recorded for {model} but only "
                f"{calls.get(function, 0)} call(s) produced them")


@pytest.mark.asyncio
class TestSubmissionsBelongToTheirCaller:
    """(b) Both submit paths record the caller's user_id, and the caller can
    list and read what they submitted. The synchronous path used to create
    its row without one."""

    async def test_both_submit_paths_keep_the_caller(
        self, api_client, tmp_path, monkeypatch
    ):
        from autornd.config import settings
        from sqlalchemy import select
        from tests.test_watchdog import REQUEST

        clients, observer_factory = await _wire_file_backed_run(tmp_path, monkeypatch)
        # Authentication configured: requests without a token are refused.
        monkeypatch.setattr(settings, "jwt_secret", "test-secret-0123456789abcdef0123456789abcdef")
        assert (await api_client.get("/api/workflows")).status_code == 401

        registered = await api_client.post(
            "/api/auth/register",
            json={"username": "caller-one",
                  "email": "caller-one@example.com",
                  "password": "correct-horse-battery-staple"},
        )
        assert registered.status_code == 201
        user_id = registered.json()["data"]["id"]
        headers = {"Authorization": f"Bearer {registered.json()['data']['token']}"}

        queued = await api_client.post(
            "/api/workflows", json={"request": REQUEST}, headers=headers)
        assert queued.status_code == 202
        async_id = queued.json()["data"]["id"]

        sync = await api_client.post(
            "/api/workflows/sync", json={"request": REQUEST}, headers=headers)
        assert sync.status_code == 200
        sync_id = sync.json()["data"]["id"]

        async with observer_factory() as session:
            rows = {w.id: w for w in
                    (await session.execute(select(Workflow))).scalars()}
        assert rows[async_id].user_id == user_id, "the async path lost the caller"
        assert rows[sync_id].user_id == user_id, "the sync path lost the caller"

        listed = await api_client.get("/api/workflows", headers=headers)
        assert {w["id"] for w in listed.json()["data"]} == {async_id, sync_id}
        for wf_id in (async_id, sync_id):
            got = await api_client.get(f"/api/workflows/{wf_id}", headers=headers)
            assert got.status_code == 200, (
                f"the caller cannot read their own workflow {wf_id}")
            assert got.json()["data"]["status"] == "completed"


@pytest.mark.asyncio
class TestProgressIsVisibleMidRun:
    """(c) A phase written mid-run is visible from a second session before the
    run ends. Before the repair every phase was buffered until the run
    finished, so a poll saw nothing for the length of a run and a crash
    discarded the nodes already paid for."""

    async def test_a_phase_written_mid_run_is_visible_from_a_second_session(
        self, api_client, tmp_path, monkeypatch
    ):
        from sqlalchemy import select
        from tests.test_watchdog import REQUEST

        # Every call takes a while, so the run is long enough to observe.
        clients, observer_factory = await _wire_file_backed_run(
            tmp_path, monkeypatch, delays={"default": 0.25})

        posted = asyncio.create_task(
            api_client.post("/api/workflows", json={"request": REQUEST}))

        seen = None
        for _ in range(600):
            async with observer_factory() as session:
                phases = (await session.execute(select(PhaseResult))).scalars().all()
                rows = (await session.execute(select(Workflow))).scalars().all()
            if phases:
                seen = (rows[0].status.value, len(phases))
                break
            await asyncio.sleep(0.01)

        assert seen is not None, "no phase was ever visible to the second session"
        status, n_phases = seen
        assert n_phases >= 1
        assert status not in ("completed", "blocked", "escalated"), (
            f"the run had already ended ({status}) when the phase was first seen")
        assert not posted.done(), (
            "the run had already ended when the phase was first seen")

        await posted
        final = (await api_client.get(f"/api/workflows/{rows[0].id}")).json()["data"]
        assert final["status"] == "completed", final["error"]
        assert len(final["phases"]) > n_phases


@pytest.mark.asyncio
class TestAnUnknownTerminalKeepsTheResult:
    """(d) A terminal string that is not a status ends the row BLOCKED, with
    the raw terminal in error. Before the repair the cast ran after the
    guarded region and raised there: the run was done and paid for, and the
    result never reached the row."""

    UNKNOWN_TERMINAL_WORKFLOW = """\
name: unknown-terminal
nodes:
  - id: triage
    kind: ai
    tier: triage
    prompt: triage
    schema: TriageVerdict

  - id: spin
    depends_on: [triage]
    body: [plan]
    until: plan.ready == false
    max_iterations: 1
    on_exhausted_status: frobnicate

  - id: plan
    kind: ai
    tier: architecture
    prompt: plan
    schema: PlanVerdict
"""

    async def test_the_row_ends_blocked_and_committed(
        self, api_client, tmp_path, monkeypatch
    ):
        from autornd.config import settings
        from sqlalchemy import select
        from tests.test_watchdog import REQUEST

        workflow_file = tmp_path / "unknown-terminal.yaml"
        workflow_file.write_text(self.UNKNOWN_TERMINAL_WORKFLOW)
        monkeypatch.setattr(settings, "autornd_workflow", str(workflow_file))
        clients, observer_factory = await _wire_file_backed_run(tmp_path, monkeypatch)

        resp = await api_client.post("/api/workflows", json={"request": REQUEST})
        assert resp.status_code == 202
        submitted_id = resp.json()["data"]["id"]

        detail = (await api_client.get(f"/api/workflows/{submitted_id}")).json()["data"]
        assert detail["status"] == "blocked"
        assert "frobnicate" in detail["error"], (
            f"the raw terminal is not in error: {detail['error']!r}")
        assert detail["phases"], "the completed nodes were lost"

        # Committed, not merely set: a second connection sees the terminal.
        async with observer_factory() as session:
            row = (await session.execute(
                select(Workflow).where(Workflow.id == submitted_id)
            )).scalar_one()
            phases = (await session.execute(
                select(PhaseResult).where(PhaseResult.workflow_id == submitted_id)
            )).scalars().all()
        assert row.status == WorkflowStatus.BLOCKED
        assert "frobnicate" in row.error
        assert phases


# ── Ruling D45 (ARCH-20261002-110): no open, unbounded spend ────────────────
#
# (a) the server is not open by default, (b) episodes by owner, (c) settings
# are not a remote lever, (d) every API run carries its bounds, (h) the
# concurrent-run cap, (i) the duplicate refusal. All provider-free; the run
# tests drive the real routes on the billing double.


@pytest.fixture(autouse=True)
def _clean_run_gate():
    """The gate is process state; a run admitted by one test must not count
    against the next."""
    from autornd.api import routes
    routes._run_gate._in_flight.clear()
    yield
    routes._run_gate._in_flight.clear()


def _remote_client():
    from httpx import ASGITransport, AsyncClient

    from autornd.main import app

    transport = ASGITransport(app=app, client=("203.0.113.5", 5000))
    return AsyncClient(transport=transport, base_url="http://test")


def _unauthenticated(monkeypatch, allow_remote: bool = False):
    from autornd.config import settings

    monkeypatch.setattr(settings, "api_key", "")
    monkeypatch.setattr(settings, "jwt_secret", "")
    monkeypatch.setattr(settings, "allow_unauthenticated_remote", allow_remote)


class TestTheServerIsNotOpenByDefault:
    """(a) The documented Docker quick start published this endpoint on every
    interface with no key (review A F6). With neither API_KEY nor JWT_SECRET
    configured the API now serves loopback callers only."""

    async def test_a_remote_caller_is_refused_and_the_sentence_names_the_fix(
            self, api_client, monkeypatch):
        _unauthenticated(monkeypatch)
        async with _remote_client() as remote:
            refused = await remote.get("/api/workflows")
            assert refused.status_code == 403
            detail = refused.json()["detail"]
            assert "API_KEY" in detail
            assert "ALLOW_UNAUTHENTICATED_REMOTE" in detail

            health = await remote.get("/api/health")
            assert health.status_code == 200     # open to everyone

    async def test_a_loopback_caller_is_served(self, api_client, monkeypatch):
        _unauthenticated(monkeypatch)
        resp = await api_client.get("/api/workflows")
        assert resp.status_code == 200

    async def test_the_override_serves_remote_and_health_says_so(
            self, api_client, monkeypatch):
        _unauthenticated(monkeypatch, allow_remote=True)
        async with _remote_client() as remote:
            resp = await remote.get("/api/workflows")
            assert resp.status_code == 200
            body = (await remote.get("/api/health")).json()
            assert body["allow_unauthenticated_remote"] is True
            assert body["authentication_configured"] is False


class TestEpisodesAreScopedToTheirCaller:
    """(b) /api/episodes showed every run's request, verdict and cost to any
    caller. Ownership lives on the workflow row; the filter joins it."""

    async def test_a_caller_sees_only_their_own_runs(
            self, api_client, db_session, monkeypatch):
        from autornd.config import settings
        from autornd.knowledge.episodic import Episode

        monkeypatch.setattr(
            settings, "jwt_secret",
            "test-secret-0123456789abcdef0123456789abcdef")

        tokens = {}
        owners = {}
        for name in ("alice", "bob"):
            registered = await api_client.post(
                "/api/auth/register",
                json={"username": f"{name}-episodes",
                      "email": f"{name}-episodes@example.com",
                      "password": "correct-horse-battery-staple"})
            assert registered.status_code == 201
            tokens[name] = registered.json()["data"]["token"]
            owners[name] = registered.json()["data"]["id"]

        for name in ("alice", "bob"):
            row = Workflow(request=f"{name}'s run",
                           status=WorkflowStatus.COMPLETED,
                           user_id=owners[name])
            db_session.add(row)
            await db_session.flush()
            db_session.add(Episode(
                workflow_id=row.id, request=f"{name}'s run",
                domains='["backend"]', risk="medium", shipped=True,
                verdict=f"{name}'s verdict", findings_count=0, total_cost=0.01))
        await db_session.commit()

        alice = await api_client.get(
            "/api/episodes", headers={"Authorization": f"Bearer {tokens['alice']}"})
        bob = await api_client.get(
            "/api/episodes", headers={"Authorization": f"Bearer {tokens['bob']}"})
        assert {e["request"] for e in alice.json()["data"]} == {"alice's run"}
        assert {e["request"] for e in bob.json()["data"]} == {"bob's run"}


class TestSettingsAreNotARemoteLever:
    """(c) A runtime ceiling raise applied to every run in flight (review F8).
    The endpoint is loopback-only and can only tighten; the tighten half lives
    beside its validator tests in tests/test_settings.py."""

    async def test_put_settings_from_a_remote_caller_is_refused(
            self, api_client, monkeypatch):
        _unauthenticated(monkeypatch, allow_remote=True)
        async with _remote_client() as remote:
            resp = await remote.put("/api/settings", json={"max_iterations": 3})
            assert resp.status_code == 403
            assert "loopback" in resp.json()["detail"]

            profiles = await remote.post("/api/profiles/example")
            assert profiles.status_code == 403


class TestTheApiRunCarriesItsBounds:
    """(d) run_time_budget_seconds and run_spend_ceiling_usd default to bounds
    now (1800 s, $0.50): every client the API creates carries the ceiling and
    every executor carries the budget."""

    async def test_the_client_and_executor_carry_the_default_bounds(
            self, api_client, monkeypatch):
        from autornd.api import routes
        from autornd.config import settings
        from autornd.graph import executor as executor_module

        from tests.conftest import make_mock_client
        from tests.test_watchdog import REQUEST, _responses

        assert settings.run_time_budget_seconds == 1800.0
        assert settings.run_spend_ceiling_usd == 0.50

        made: list = []

        def _make():
            client = make_mock_client(_responses())
            made.append(client)
            return client

        monkeypatch.setattr(routes, "OpenRouterClient", _make)

        seen: dict = {}
        real = executor_module.GraphExecutor

        class Recording(real):
            def __init__(self, spec, runner, **kwargs):
                seen["time_budget"] = kwargs.get("time_budget")
                super().__init__(spec, runner, **kwargs)

        monkeypatch.setattr(executor_module, "GraphExecutor", Recording)

        resp = await api_client.post("/api/workflows/sync",
                                     json={"request": REQUEST})
        assert resp.status_code == 200
        assert made[0].spend_ceiling == 0.50
        assert seen["time_budget"] == 1800.0


class TestTheRunCapAndTheDuplicate:
    """(h) and (i): a per-run ceiling bounds one run, not a caller who submits
    many — at most max_concurrent_runs in flight, and never twice the same
    request from the same caller (review A F6: no rate limiting, no queue
    depth cap, no dedupe)."""

    async def test_a_submission_beyond_the_cap_gets_429_and_leaves_no_row(
            self, api_client, db_session, tmp_path, monkeypatch):
        import asyncio

        from autornd.config import settings
        from sqlalchemy import func, select

        from tests.test_watchdog import REQUEST

        monkeypatch.setattr(settings, "max_concurrent_runs", 1)
        monkeypatch.setattr(settings, "allow_unauthenticated_remote", True)
        clients, _observer = await _wire_file_backed_run(
            tmp_path, monkeypatch, delays={"default": 0.3})

        async with _remote_client() as remote:
            first = asyncio.create_task(
                remote.post("/api/workflows", json={"request": REQUEST}))
            await asyncio.sleep(0.1)            # the first is admitted, in flight
            second = await remote.post(
                "/api/workflows", json={"request": "some other work"})
            assert second.status_code == 429
            assert "in flight" in second.json()["detail"]
            await first

        async with _observer() as session:
            rows = (await session.execute(
                select(func.count()).select_from(Workflow))).scalar_one()
        assert rows == 1, f"the refused submission left {rows - 1} row(s) behind"

    async def test_an_identical_request_is_a_duplicate_but_another_caller_is_served(
            self, api_client, db_session, tmp_path, monkeypatch):
        import asyncio

        from httpx import ASGITransport, AsyncClient

        from autornd.config import settings
        from autornd.main import app

        from tests.test_watchdog import REQUEST

        monkeypatch.setattr(settings, "max_concurrent_runs", 4)
        monkeypatch.setattr(settings, "allow_unauthenticated_remote", True)
        clients, _observer = await _wire_file_backed_run(
            tmp_path, monkeypatch, delays={"default": 0.3})

        same = ASGITransport(app, client=("203.0.113.5", 5000))
        other = ASGITransport(app, client=("203.0.113.6", 5000))
        async with AsyncClient(transport=same, base_url="http://test") as a, \
                AsyncClient(transport=other, base_url="http://test") as b:
            first = asyncio.create_task(
                a.post("/api/workflows", json={"request": REQUEST}))
            await asyncio.sleep(0.1)
            duplicate = await a.post("/api/workflows", json={"request": REQUEST})
            assert duplicate.status_code == 409
            assert "already running" in duplicate.json()["detail"]
            stranger = await b.post("/api/workflows", json={"request": REQUEST})
            assert stranger.status_code == 202
            await first
