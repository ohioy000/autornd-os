"""Tests for settings endpoints — GET/PUT, validation, runtime mutability.

No `@pytest.mark.asyncio` anywhere in this file. pyproject sets
`asyncio_mode = "auto"`, so async tests are collected without a mark — and a
class-level mark on a class holding sync tests makes pytest warn once per sync
test, which is where seven of the suite's eleven warnings came from
(TestConfigValidation is all-sync and was marked).
"""

from __future__ import annotations

import pytest


class TestGetSettings:
    async def test_returns_all_fields(self, api_client):
        resp = await api_client.get("/api/settings")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert "model_triage" in data
        assert "max_iterations" in data
        assert "log_level" in data
        assert "api_host" in data

    async def test_redacts_api_key(self, api_client, monkeypatch):
        from autornd import config
        monkeypatch.setattr(config.settings, "openrouter_api_key", "sk-or-v1-abcdef123456")
        resp = await api_client.get("/api/settings")
        data = resp.json()["data"]
        assert data["openrouter_api_key"] == "****3456"
        assert "abcdef" not in data["openrouter_api_key"]

    async def test_redacts_jwt_secret(self, api_client, monkeypatch):
        from autornd import config
        monkeypatch.setattr(config.settings, "api_key", "myapikey1234")
        resp = await api_client.get("/api/settings", headers={"Authorization": "Bearer myapikey1234"})
        data = resp.json()["data"]
        assert data["api_key"] == "****1234"
        assert "myapikey" not in data["api_key"]

    async def test_includes_runtime_mutable_list(self, api_client):
        resp = await api_client.get("/api/settings")
        meta = resp.json()["meta"]
        assert "runtime_mutable" in meta
        assert "max_iterations" in meta["runtime_mutable"]
        assert "log_level" in meta["runtime_mutable"]


class TestUpdateSettings:
    async def test_update_max_iterations(self, api_client, monkeypatch):
        from autornd import config
        monkeypatch.setattr(config.settings, "max_iterations", 5)
        resp = await api_client.put("/api/settings", json={"max_iterations": 10})
        assert resp.status_code == 200
        assert "max_iterations" in resp.json()["data"]["updated"]
        assert config.settings.max_iterations == 10

    async def test_update_log_level(self, api_client, monkeypatch):
        from autornd import config
        monkeypatch.setattr(config.settings, "log_level", "INFO")
        resp = await api_client.put("/api/settings", json={"log_level": "debug"})
        assert resp.status_code == 200
        assert config.settings.log_level == "DEBUG"

    async def test_reject_immutable_field(self, api_client):
        resp = await api_client.put("/api/settings", json={"max_iterations": 3})
        # First a valid update succeeds, now test an invalid field name
        # by sending a raw JSON body with a non-mutable field
        import httpx
        resp = await api_client.request(
            "PUT", "/api/settings",
            content='{"api_host": "127.0.0.1"}',
            headers={"Content-Type": "application/json"},
        )
        assert resp.status_code == 422 or resp.status_code == 400

    async def test_reject_bad_max_iterations(self, api_client):
        resp = await api_client.put("/api/settings", json={"max_iterations": 50})
        assert resp.status_code == 422

    async def test_reject_bad_log_level(self, api_client):
        resp = await api_client.put("/api/settings", json={"log_level": "VERBOSE"})
        assert resp.status_code == 422

    async def test_empty_body_rejected(self, api_client):
        resp = await api_client.put("/api/settings", json={})
        assert resp.status_code == 400


class TestConfigValidation:
    def test_max_iterations_range(self):
        from pydantic import ValidationError
        from autornd.config import Settings

        with pytest.raises(ValidationError, match="max_iterations"):
            Settings(max_iterations=0)
        with pytest.raises(ValidationError, match="max_iterations"):
            Settings(max_iterations=21)

    def test_model_id_must_contain_slash(self):
        from pydantic import ValidationError
        from autornd.config import Settings

        with pytest.raises(ValidationError, match="Model ID must contain"):
            Settings(model_triage="bad-model-id")

    def test_premium_model_empty_ok(self):
        from autornd.config import Settings
        s = Settings(model_premium="")
        assert s.model_premium == ""

    def test_premium_model_with_slash_ok(self):
        from autornd.config import Settings
        s = Settings(model_premium="test/premium")
        assert s.model_premium == "test/premium"

    def test_premium_model_without_slash_rejected(self):
        from pydantic import ValidationError
        from autornd.config import Settings

        with pytest.raises(ValidationError, match="Premium model ID must contain"):
            Settings(model_premium="bad-premium")

    def test_log_level_validated(self):
        from pydantic import ValidationError
        from autornd.config import Settings

        with pytest.raises(ValidationError, match="log_level"):
            Settings(log_level="VERBOSE")

    def test_log_level_uppercased(self):
        from autornd.config import Settings
        s = Settings(log_level="debug")
        assert s.log_level == "DEBUG"


class TestRebuildFunctionModels:
    def test_rebuild_updates_class_attribute(self, monkeypatch):
        from autornd import config
        from autornd.routing.openrouter import OpenRouterClient, rebuild_function_models

        monkeypatch.setattr(config.settings, "model_triage", "new/triage")
        rebuild_function_models()
        assert OpenRouterClient.FUNCTION_MODELS["triage"] == "new/triage"

    def test_rebuild_adds_premium(self, monkeypatch):
        from autornd import config
        from autornd.routing.openrouter import OpenRouterClient, rebuild_function_models

        monkeypatch.setattr(config.settings, "model_premium", "test/premium")
        rebuild_function_models()
        assert "premium" in OpenRouterClient.FUNCTION_MODELS
        assert OpenRouterClient.FUNCTION_MODELS["premium"] == "test/premium"

    def test_rebuild_removes_premium_when_empty(self, monkeypatch):
        from autornd import config
        from autornd.routing.openrouter import OpenRouterClient, rebuild_function_models

        monkeypatch.setattr(config.settings, "model_premium", "")
        rebuild_function_models()
        assert "premium" not in OpenRouterClient.FUNCTION_MODELS


class TestBindAddressDefault:
    """The default must be the one that cannot be reached from another machine.

    AutoRnD has no rate limiting and spends real money on every request, and
    both .env.example and the README have always told operators it defaults to
    loopback. The code said 0.0.0.0 from the initial commit until B3's pass.
    Containers are unaffected: the bundled Dockerfile passes --host on its own
    command line, and this value is read only by `python -m autornd.main`.
    """

    def test_api_host_defaults_to_loopback(self, monkeypatch):
        monkeypatch.delenv("API_HOST", raising=False)
        from autornd.config import Settings

        assert Settings().api_host == "127.0.0.1"

    def test_a_lan_bind_is_still_possible_but_deliberate(self, monkeypatch):
        monkeypatch.setenv("API_HOST", "0.0.0.0")
        from autornd.config import Settings

        assert Settings().api_host == "0.0.0.0"
