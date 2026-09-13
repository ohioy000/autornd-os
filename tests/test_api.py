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
