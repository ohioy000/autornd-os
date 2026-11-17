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

    def test_the_page_fits_a_phone_without_losing_a_button(self):
        """Measured 2026-11-16 in Chromium at 390 px: the header's Refresh
        button ran 20 px past the edge and the body hides overflow, so it was
        cut off and could not be reached; the workflows table was 435 px wide
        inside a box that could not scroll sideways. The header wraps and the
        table's box scrolls."""
        def rule(selector):
            start = DASHBOARD.index(selector + "{")
            return DASHBOARD[start:DASHBOARD.index("}", start)]
        assert "flex-wrap:wrap" in rule(".top-bar")
        assert "flex-wrap:wrap" in rule(".top-bar .controls")
        assert "overflow:auto" in rule(".workflows-wrap")


@pytest.mark.asyncio
class TestARunStrandedByARestartIsEnded:
    """API audit of 2026-11-16: a run in flight when the server stopped
    read as running for ever. Owner's word that day: end such runs as
    blocked when the server starts."""

    async def _rows(self, db_session, monkeypatch):
        from autornd import database
        from autornd.models.workflow import Workflow, WorkflowStatus
        from tests.conftest import test_session_factory

        monkeypatch.setattr(database, "async_session", test_session_factory)
        rows = {}
        for status, error in ((WorkflowStatus.PENDING, None),
                              (WorkflowStatus.IMPLEMENT, None),
                              (WorkflowStatus.COMPLETED, None),
                              (WorkflowStatus.BLOCKED, "its own reason"),
                              (WorkflowStatus.ESCALATED, None)):
            row = Workflow(request=status.value, status=status, error=error)
            db_session.add(row)
            rows[status] = row
        await db_session.commit()
        return rows

    async def test_a_run_in_flight_ends_blocked_with_the_reason(
            self, db_session, monkeypatch):
        from autornd.main import STRANDED, end_stranded_runs
        from autornd.models.workflow import WorkflowStatus

        rows = await self._rows(db_session, monkeypatch)
        assert await end_stranded_runs() == 2
        for row in rows.values():
            await db_session.refresh(row)
        for was in (WorkflowStatus.PENDING, WorkflowStatus.IMPLEMENT):
            assert rows[was].status is WorkflowStatus.BLOCKED
            assert rows[was].error == STRANDED
        assert "Submit it again" in STRANDED

    async def test_a_run_that_ended_is_left_as_it_ended(
            self, db_session, monkeypatch):
        """Break-proof: the sweep takes only rows still in flight."""
        from autornd.main import end_stranded_runs
        from autornd.models.workflow import WorkflowStatus

        rows = await self._rows(db_session, monkeypatch)
        await end_stranded_runs()
        for row in rows.values():
            await db_session.refresh(row)
        assert rows[WorkflowStatus.COMPLETED].status is WorkflowStatus.COMPLETED
        assert rows[WorkflowStatus.COMPLETED].error is None
        assert rows[WorkflowStatus.ESCALATED].status is WorkflowStatus.ESCALATED
        assert rows[WorkflowStatus.BLOCKED].error == "its own reason"
        assert await end_stranded_runs() == 0


class TestTheRuntimeSettingsNamedAreTheOnesAccepted:
    """API audit of 2026-11-16: thirteen settings were named as changeable
    and the endpoint's body took five; the other eight were dropped without
    a word."""

    def test_the_list_and_the_body_are_the_same_names(self):
        from autornd import config
        from autornd.api.routes import SettingsUpdate
        assert config.settings.RUNTIME_MUTABLE == set(SettingsUpdate.model_fields)

    @pytest.mark.asyncio
    async def test_a_setting_not_on_the_list_is_refused_and_the_list_named(
            self, api_client, monkeypatch):
        from autornd import config
        before = config.settings.plan_max_tokens
        resp = await api_client.put("/api/settings",
                                    json={"plan_max_tokens": 100})
        assert resp.status_code == 400
        detail = resp.json()["detail"]
        for name in sorted(config.settings.RUNTIME_MUTABLE):
            assert name in detail
        assert "in .env and restart" in detail
        assert config.settings.plan_max_tokens == before


@pytest.mark.asyncio
class TestHealthListsEveryConfiguredTier:
    """API audit of 2026-11-16: a wrong model on the recompute or decision
    tier showed only when a run reached it."""

    async def _status(self, monkeypatch, recompute, decision):
        from unittest.mock import patch
        from autornd import config
        monkeypatch.setattr(config.settings, "model_recompute", recompute)
        monkeypatch.setattr(config.settings, "model_decision", decision)
        monkeypatch.setattr(openrouter, "_model_status", {})
        with patch("autornd.routing.openrouter.httpx.AsyncClient",
                   side_effect=RuntimeError("no catalogue in the suite")):
            return await openrouter.check_models()

    async def test_the_recompute_and_decision_tiers_are_listed_when_set(
            self, monkeypatch):
        status = await self._status(monkeypatch, "vendor/recompute", "vendor/decider")
        assert status["recompute"] == {"model": "vendor/recompute", "available": None}
        assert status["decision"] == {"model": "vendor/decider", "available": None}

    async def test_an_unset_tier_is_not_listed(self, monkeypatch):
        """Break-proof: an optional tier left empty is not a degraded one."""
        status = await self._status(monkeypatch, "", "")
        assert "recompute" not in status and "decision" not in status


class TestARetiredSettingDoesNotStopTheServer:
    """Probe of 2026-11-16: an .env that still named a removed lookup
    setting stopped the server at import, as any unknown name does."""

    ENV = ("MODEL_TRIAGE=a/b\nMODEL_ENGINEERING=a/b\nMODEL_ARCHITECTURE=a/b\n"
           "MODEL_ESCALATION=a/b\nMODEL_RESEARCH=a/b\nMODEL_SEARCH=a/b\n")

    def test_it_is_dropped_and_said(self, tmp_path, caplog):
        from autornd.config import RETIRED_SETTINGS, Settings
        env = tmp_path / ".env"
        env.write_text(self.ENV + "".join(
            f"{name.upper()}=true\n" for name in sorted(RETIRED_SETTINGS)))
        with caplog.at_level("WARNING"):
            cfg = Settings(_env_file=str(env))
        for name in RETIRED_SETTINGS:
            assert not hasattr(cfg, name)
            assert f"{name.upper()} is no longer a setting" in caplog.text

    def test_any_other_unknown_name_is_still_refused(self, tmp_path):
        """Break-proof: only the retired names are let through."""
        from pydantic import ValidationError
        from autornd.config import Settings
        env = tmp_path / ".env"
        env.write_text(self.ENV + "LOOKUP_READS_DOCUMENTZ=true\n")
        with pytest.raises(ValidationError):
            Settings(_env_file=str(env))
