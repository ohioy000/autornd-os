"""Test API endpoints."""

import pytest


@pytest.mark.asyncio
class TestHealthEndpoint:
    async def test_health(self, api_client):
        resp = await api_client.get("/api/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["service"] == "autornd"


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
