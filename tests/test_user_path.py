"""The user's path: the API and the page a person meets first.

The repairs of the API audit of 2026-11-16, which re-checked the outside
reviews of 2026-10-02 on main and walked the path a user takes. Each test
was proven by breaking the line it guards.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from autornd.routing import openrouter
from autornd.routing.openrouter import MissingProviderKey, OpenRouterClient

DASHBOARD = (Path(__file__).resolve().parent.parent
             / "autornd/api/templates/dashboard.html").read_text(encoding="utf-8")


@pytest.mark.asyncio
class TestAMissingProviderKeyIsSaidPlainly:
    async def test_a_call_with_no_key_names_the_setting(self):
        """Measured 2026-11-16: with no key the header was "Bearer " and the
        transport refused it as an illegal header value."""
        client = OpenRouterClient(api_key="")
        with pytest.raises(MissingProviderKey) as raised:
            await client._get_client()
        assert str(raised.value) == (
            "No provider key is set. Put OPENROUTER_API_KEY in .env and "
            "restart the server.")

    async def test_a_client_with_a_key_is_built_as_before(self):
        """Break-proof: only the missing key is refused."""
        client = OpenRouterClient(api_key="test")
        built = await client._get_client()
        assert built.headers["Authorization"] == "Bearer test"
        await client.close()

    async def test_health_says_whether_a_key_is_set(self, api_client, monkeypatch):
        """The catalogue is public, so every model can read as available
        with no key to call it with."""
        assert (await api_client.get("/api/health")).json()[
            "provider_key_configured"] is False
        monkeypatch.setattr(openrouter.settings, "openrouter_api_key", "a-key")
        assert (await api_client.get("/api/health")).json()[
            "provider_key_configured"] is True


@pytest.mark.asyncio
class TestARuntimeLimitStaysPositive:
    @pytest.mark.parametrize("value", [0, -5])
    async def test_nought_or_less_is_refused(self, api_client, monkeypatch, value):
        """Measured 2026-11-16: -5 was accepted for a token ceiling, being
        lower than its startup value."""
        from autornd import config
        from autornd.api import routes
        monkeypatch.setattr(config.settings, "escalation_max_tokens", 16384)
        monkeypatch.setitem(routes._STARTUP_VALUES, "escalation_max_tokens", 16384)
        resp = await api_client.put("/api/settings",
                                    json={"escalation_max_tokens": value})
        assert resp.status_code == 422
        assert resp.json()["detail"] == (
            "escalation_max_tokens must be greater than zero.")
        assert config.settings.escalation_max_tokens == 16384

    async def test_a_lower_positive_limit_is_still_accepted(
            self, api_client, monkeypatch):
        """Break-proof: tightening is what the endpoint is for."""
        from autornd import config
        from autornd.api import routes
        monkeypatch.setattr(config.settings, "escalation_max_tokens", 16384)
        monkeypatch.setitem(routes._STARTUP_VALUES, "escalation_max_tokens", 16384)
        resp = await api_client.put("/api/settings",
                                    json={"escalation_max_tokens": 8000})
        assert resp.status_code == 200
        assert config.settings.escalation_max_tokens == 8000


@pytest.mark.asyncio
class TestAnUnexpectedErrorKeepsItsTraceback:
    async def test_the_caller_gets_a_sentence_and_no_traceback(self):
        """Measured 2026-11-16: a 500 returned the server's full traceback,
        files and lines, to whoever called."""
        from starlette.requests import Request

        from autornd.main import unhandled_exception_handler
        request = Request({"type": "http", "method": "GET", "path": "/x",
                           "headers": [], "query_string": b""})
        try:
            raise FileNotFoundError("profiles/nobody.yaml")
        except FileNotFoundError as exc:
            response = await unhandled_exception_handler(request, exc)
        assert response.status_code == 500
        assert response.body == (
            b'{"detail":"FileNotFoundError: profiles/nobody.yaml"}')


@pytest.mark.asyncio
class TestAWorkflowThatCannotBeLoadedEndsItsRow:
    async def test_the_row_ends_blocked_with_the_reason(self, tmp_path):
        """Measured 2026-11-16, by reading: the row is committed as pending
        before the workflow file is loaded, and a file that is missing or
        does not load left it pending for ever on the background path."""
        from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

        from autornd.database import Base
        from autornd.engine.workflow import WorkflowEngine
        from autornd.models.workflow import WorkflowStatus
        engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path}/run.db")
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        async with async_sessionmaker(engine, expire_on_commit=False)() as session:
            row = await WorkflowEngine(OpenRouterClient(api_key="test"), session).execute(
                "a request", workflow_file=str(tmp_path / "missing.yaml"))
            assert row.status == WorkflowStatus.BLOCKED
            assert row.error.startswith("The workflow could not be loaded: ")
            assert row.id is not None
        await engine.dispose()


class TestThePageShowsWhatARunDelivered:
    """The page has no test harness of its own; these pin the two lines the
    audit found wrong. On the walk of 2026-11-16 the served page's own
    functions were run under Node on real API responses, a completed run
    and a blocked one; no browser was installed on that machine."""

    def test_the_draft_is_read_from_the_key_the_record_has(self):
        """`candidate.summary` was never a key of the record, so a run that
        did not complete showed its error and no draft."""
        assert "w.candidate.answer" in DASHBOARD

    def test_the_workflows_tab_shows_the_delivery_too(self):
        """A run opened from the table showed its raw phases and no answer,
        no cautions and no confirmations."""
        detail = DASHBOARD[DASHBOARD.index("async function loadDetail(id)"):]
        detail = detail[:detail.index("\n}\n")]
        assert "renderDelivery(w)" in detail
        chat = DASHBOARD[DASHBOARD.index("function renderResult(w)"):]
        assert "renderDelivery(w)" in chat[:chat.index("\n}\n")]
