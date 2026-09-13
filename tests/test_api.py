"""Test API endpoints."""

import json

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
