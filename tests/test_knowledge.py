"""Test knowledge store, context loading, and episodic memory."""

import json
import tempfile
from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
def _fresh_rerank_mode():
    """Ranking strategy is cached per process, so tests must not inherit it.

    Without this the result of one test depends on which test ran before it,
    which is exactly the order-dependence a probed-once cache invites.
    """
    import autornd.knowledge.context as ctx

    ctx.reset_rerank_mode()
    yield
    ctx.reset_rerank_mode()
import pytest_asyncio

from autornd.models.verdicts import Domain, SpecialistRole


class TestContextLoader:
    def setup_method(self):
        from autornd.profiles import load_profile, set_profile
        set_profile(load_profile("example"))

    def teardown_method(self):
        from autornd.profiles import reset_profile
        reset_profile()

    def test_load_docs_context_returns_content(self):
        from autornd.knowledge.context import load_docs_context

        ctx = load_docs_context([Domain.BACKEND])
        assert len(ctx) > 0
        assert "SmartFactory" in ctx

    def test_load_docs_context_includes_global(self):
        from autornd.knowledge.context import load_docs_context

        ctx = load_docs_context([Domain.FRONTEND])
        assert "architecture" in ctx.lower()

    def test_load_docs_context_domain_specific(self):
        from autornd.knowledge.context import load_docs_context

        firmware_ctx = load_docs_context([Domain.FIRMWARE])
        backend_ctx = load_docs_context([Domain.BACKEND])
        assert "constraints.md" in firmware_ctx
        assert "architecture.md" in backend_ctx

    async def test_build_phase_context_includes_docs(self):
        from autornd.knowledge.context import build_phase_context

        ctx = await build_phase_context(
            "Add a handler for a new sensor type",
            [Domain.BACKEND],
            include_retrieval=False,
        )
        assert "PROJECT DOCUMENTATION" in ctx

    def test_context_truncation(self):
        from autornd.knowledge.context import load_docs_context, MAX_CONTEXT_CHARS

        ctx = load_docs_context(
            [Domain.FIRMWARE, Domain.HARDWARE, Domain.BACKEND, Domain.FRONTEND]
        )
        assert len(ctx) <= MAX_CONTEXT_CHARS + 50  # small buffer for truncation marker


class TestChromaStore:
    def test_ingest_and_retrieve(self, tmp_path):
        from autornd.knowledge.store import (
            _get_chroma_client,
            ingest_file,
            retrieve,
            COLLECTION_NAME,
        )
        from autornd.config import settings

        original_path = settings.chromadb_path
        settings.chromadb_path = str(tmp_path / "chroma_test")

        try:
            test_file = tmp_path / "test_doc.md"
            test_file.write_text(
                "# LoRa Deep Sleep\n\n"
                "The ESP32-S3 enters deep sleep mode to conserve battery. "
                "Wake sources include RTC timer and GPIO interrupt. "
                "Sleep current target is under 10 microamps.\n\n"
                "## Power Budget\n\n"
                "LiFePO4 3.2V 3000mAh cell provides approximately 18 months "
                "of operation with 10-minute wake cycles."
            )

            count = ingest_file(test_file, source_tag="test_doc")
            assert count > 0

            results = retrieve("deep sleep power consumption")
            assert len(results) > 0
            assert any("sleep" in r["text"].lower() for r in results)
        finally:
            settings.chromadb_path = original_path

    def test_get_stats_empty(self, tmp_path):
        from autornd.knowledge.store import get_stats
        from autornd.config import settings

        original_path = settings.chromadb_path
        settings.chromadb_path = str(tmp_path / "chroma_empty")

        try:
            stats = get_stats()
            assert stats["count"] == 0 or stats.get("status") == "not_initialized"
        finally:
            settings.chromadb_path = original_path


@pytest.mark.asyncio
class TestEpisodicMemory:
    async def test_save_and_retrieve_episode(self, db_session):
        from autornd.knowledge.episodic import save_episode, get_recent_episodes

        await save_episode(
            db_session,
            workflow_id=1,
            request="Add temperature threshold alert",
            domains=["backend"],
            risk="medium",
            iterations=1,
            shipped=True,
            verdict="Ship — all thresholds configured correctly",
            findings_count=0,
            total_cost=0.45,
        )
        await db_session.commit()

        episodes = await get_recent_episodes(db_session)
        assert len(episodes) == 1
        assert episodes[0].shipped is True
        assert episodes[0].request == "Add temperature threshold alert"

    async def test_similar_episodes_by_domain(self, db_session):
        from autornd.knowledge.episodic import save_episode, get_similar_episodes

        await save_episode(
            db_session, workflow_id=1, request="Fix firmware bug",
            domains=["firmware"], risk="high", iterations=3,
            shipped=True, verdict="Ship", findings_count=1, total_cost=0.80,
        )
        await save_episode(
            db_session, workflow_id=2, request="Update dashboard",
            domains=["frontend"], risk="low", iterations=1,
            shipped=True, verdict="Ship", findings_count=0, total_cost=0.20,
        )
        await db_session.commit()

        firmware_similar = await get_similar_episodes(db_session, ["firmware"])
        assert len(firmware_similar) == 1
        assert firmware_similar[0].workflow_id == 1

    async def test_format_episodes_context(self, db_session):
        from autornd.knowledge.episodic import (
            save_episode, get_recent_episodes, format_episodes_context,
        )

        await save_episode(
            db_session, workflow_id=1, request="Blocked task",
            domains=["hardware"], risk="critical", iterations=5,
            shipped=False, verdict="Blocked on missing datasheet",
            findings_count=3, total_cost=1.20,
        )
        await db_session.commit()

        episodes = await get_recent_episodes(db_session)
        ctx = format_episodes_context(episodes)
        assert "BLOCKED" in ctx
        assert "missing datasheet" in ctx.lower()


@pytest.mark.asyncio
class TestRerank:
    """Ranking must never be able to break a workflow: every failure path
    degrades to the embedding-distance order retrieval already produced."""

    CANDIDATES = [
        {"text": f"chunk {i}", "tag": f"t{i}", "source": "s", "distance": i / 10}
        for i in range(8)
    ]

    async def test_reorders_by_model_ranking(self):
        from unittest.mock import AsyncMock
        from autornd.knowledge.context import rerank_chunks

        client = AsyncMock()
        client.chat_json = AsyncMock(return_value=({"ranking": [5, 0, 3]}, None))
        out = await rerank_chunks(client, "q", self.CANDIDATES, keep=3)
        assert [c["tag"] for c in out] == ["t5", "t0", "t3"]

    async def test_no_client_keeps_distance_order(self):
        from autornd.knowledge.context import rerank_chunks

        out = await rerank_chunks(None, "q", self.CANDIDATES, keep=3)
        assert [c["tag"] for c in out] == ["t0", "t1", "t2"]

    async def test_model_failure_falls_back(self):
        from unittest.mock import AsyncMock
        from autornd.knowledge.context import rerank_chunks

        client = AsyncMock()
        client.chat_json = AsyncMock(side_effect=RuntimeError("provider down"))
        out = await rerank_chunks(client, "q", self.CANDIDATES, keep=3)
        assert [c["tag"] for c in out] == ["t0", "t1", "t2"]

    async def test_garbage_ranking_falls_back(self):
        from unittest.mock import AsyncMock
        from autornd.knowledge.context import rerank_chunks

        client = AsyncMock()
        client.chat_json = AsyncMock(return_value=({"ranking": ["nope", 99]}, None))
        out = await rerank_chunks(client, "q", self.CANDIDATES, keep=3)
        assert [c["tag"] for c in out] == ["t0", "t1", "t2"]

    async def test_listwise_ranking_uses_the_ranker_tier(self, monkeypatch):
        from unittest.mock import AsyncMock
        from autornd import config
        import autornd.knowledge.context as ctx

        monkeypatch.setattr(config.settings, "model_ranker", "vendor/ranker")
        monkeypatch.setattr(ctx, "_rerank_mode", "listwise")   # chat model, not a reranker
        client = AsyncMock()
        client.chat_json = AsyncMock(return_value=({"ranking": [1]}, None))
        await ctx.rerank_chunks(client, "q", self.CANDIDATES, keep=1)
        assert client.chat_json.call_args.kwargs["function"] == "ranker"

    async def test_falls_back_to_research_tier_when_no_ranker(self, monkeypatch):
        from unittest.mock import AsyncMock
        from autornd import config
        import autornd.knowledge.context as ctx

        monkeypatch.setattr(config.settings, "model_ranker", "")
        monkeypatch.setattr(config.settings, "model_research", "vendor/researcher")
        monkeypatch.setattr(ctx, "_rerank_mode", "listwise")
        client = AsyncMock()
        client.chat_json = AsyncMock(return_value=({"ranking": [1]}, None))
        await ctx.rerank_chunks(client, "q", self.CANDIDATES, keep=1)
        assert client.chat_json.call_args.kwargs["function"] == "research"

    async def test_prefers_native_rerank_model(self, monkeypatch):
        from unittest.mock import AsyncMock
        import autornd.knowledge.context as ctx

        monkeypatch.setattr(ctx, "_rerank_mode", None)
        client = AsyncMock()
        client.rerank = AsyncMock(return_value=[(6, 0.98), (1, 0.4)])
        client.chat_json = AsyncMock()
        out = await ctx.rerank_chunks(client, "q", self.CANDIDATES, keep=2)
        assert [c["tag"] for c in out] == ["t6", "t1"]
        client.chat_json.assert_not_called()

    async def test_falls_back_to_listwise_when_rerank_unsupported(self, monkeypatch):
        from unittest.mock import AsyncMock
        import autornd.knowledge.context as ctx

        monkeypatch.setattr(ctx, "_rerank_mode", None)
        client = AsyncMock()
        client.rerank = AsyncMock(side_effect=RuntimeError("404 no rerank"))
        client.chat_json = AsyncMock(return_value=({"ranking": [2, 4]}, None))
        out = await ctx.rerank_chunks(client, "q", self.CANDIDATES, keep=2)
        assert [c["tag"] for c in out] == ["t2", "t4"]
        assert ctx._rerank_mode == "listwise"

    async def test_both_failing_keeps_distance_order(self, monkeypatch):
        from unittest.mock import AsyncMock
        import autornd.knowledge.context as ctx

        monkeypatch.setattr(ctx, "_rerank_mode", None)
        client = AsyncMock()
        client.rerank = AsyncMock(side_effect=RuntimeError("no rerank"))
        client.chat_json = AsyncMock(side_effect=RuntimeError("provider down"))
        out = await ctx.rerank_chunks(client, "q", self.CANDIDATES, keep=3)
        assert [c["tag"] for c in out] == ["t0", "t1", "t2"]


@pytest.mark.asyncio
class TestResearchTier:
    """The research tier reads docs and writes a briefing. Every step degrades
    to the behaviour that existed before it, so an unset or failing research
    model costs grounding quality, never a workflow."""

    CHUNKS = [
        {"text": "Supply rail is 24V nominal, 18-30V tolerated.", "tag": "power", "distance": 0.1},
        {"text": "All fill-zone connectors must be IP69K rated.", "tag": "ingress", "distance": 0.2},
    ]

    async def test_expands_into_targeted_queries(self, monkeypatch):
        from unittest.mock import AsyncMock
        from autornd import config
        import autornd.knowledge.context as ctx

        monkeypatch.setattr(config.settings, "model_research", "vendor/researcher")
        client = AsyncMock()
        client.chat_json = AsyncMock(
            return_value=({"queries": ["sensor supply voltage", "connector ingress rating"]}, None))
        out = await ctx.expand_queries(client, "wire the laser sensor")
        assert out == ["sensor supply voltage", "connector ingress rating"]
        assert client.chat_json.call_args.kwargs["function"] == "research"

    async def test_no_research_model_searches_raw_request(self, monkeypatch):
        from autornd import config
        import autornd.knowledge.context as ctx

        monkeypatch.setattr(config.settings, "model_research", "")
        assert await ctx.expand_queries(object(), "wire the sensor") == ["wire the sensor"]

    async def test_expansion_failure_searches_raw_request(self, monkeypatch):
        from unittest.mock import AsyncMock
        from autornd import config
        import autornd.knowledge.context as ctx

        monkeypatch.setattr(config.settings, "model_research", "vendor/researcher")
        client = AsyncMock()
        client.chat_json = AsyncMock(side_effect=RuntimeError("down"))
        assert await ctx.expand_queries(client, "wire it") == ["wire it"]

    async def test_briefing_cites_sources_and_names_gaps(self, monkeypatch):
        from unittest.mock import AsyncMock
        from autornd import config
        import autornd.knowledge.context as ctx

        monkeypatch.setattr(config.settings, "model_research", "vendor/researcher")
        client = AsyncMock()
        client.chat_json = AsyncMock(return_value=(
            {"briefing": "Supply is 24V nominal.", "gaps": ["cable length limits"]}, None))
        out = await ctx.synthesize_briefing(client, "wire it", self.CHUNKS)
        assert "24V nominal" in out
        assert "cable length limits" in out
        assert "power" in out and "ingress" in out   # sources cited

    async def test_briefing_failure_passes_excerpts_through(self, monkeypatch):
        from unittest.mock import AsyncMock
        from autornd import config
        import autornd.knowledge.context as ctx

        monkeypatch.setattr(config.settings, "model_research", "vendor/researcher")
        client = AsyncMock()
        client.chat_json = AsyncMock(side_effect=RuntimeError("down"))
        out = await ctx.synthesize_briefing(client, "wire it", self.CHUNKS)
        assert "IP69K" in out


@pytest.mark.asyncio
class TestRankTierSelection:
    async def test_ranker_tier_preferred(self, monkeypatch):
        from autornd import config
        import autornd.knowledge.context as ctx

        monkeypatch.setattr(config.settings, "model_ranker", "vendor/reranker")
        monkeypatch.setattr(config.settings, "model_research", "vendor/researcher")
        assert ctx._rank_tier() == "ranker"

    async def test_research_ranks_when_no_ranker_set(self, monkeypatch):
        from autornd import config
        import autornd.knowledge.context as ctx

        monkeypatch.setattr(config.settings, "model_ranker", "")
        monkeypatch.setattr(config.settings, "model_research", "vendor/researcher")
        assert ctx._rank_tier() == "research"

    async def test_neither_set_means_no_ranking(self, monkeypatch):
        from unittest.mock import AsyncMock
        from autornd import config
        import autornd.knowledge.context as ctx

        monkeypatch.setattr(config.settings, "model_ranker", "")
        monkeypatch.setattr(config.settings, "model_research", "")
        assert ctx._rank_tier() is None
        cands = [{"text": f"c{i}", "tag": f"t{i}", "distance": i/10} for i in range(8)]
        out = await ctx.rerank_chunks(AsyncMock(), "q", cands, keep=3)
        assert [c["tag"] for c in out] == ["t0", "t1", "t2"]

    async def test_scopes_the_request_when_there_are_no_docs(self, monkeypatch):
        """Most installs have an empty knowledge store. Scoping needs no
        documents, so the research tier still earns its place there."""
        from unittest.mock import AsyncMock
        from autornd import config
        import autornd.knowledge.context as ctx

        monkeypatch.setattr(config.settings, "model_research", "vendor/researcher")
        client = AsyncMock()
        client.chat_json = AsyncMock(return_value=({
            "objective": "Deliver 24V from the board to the sensor.",
            "unknowns": ["sensor current draw", "connector type"],
            "assumptions": ["supply is regulated"],
            "considerations": ["ingress rating"],
        }, None))

        out, unknowns = await ctx.analyze_request(client, "wire the sensor")
        assert "Deliver 24V" in out
        assert "sensor current draw" in out
        assert "Assumed unless corrected" in out
        assert unknowns == ["sensor current draw", "connector type"]
        assert client.chat_json.call_args.kwargs["function"] == "research"

    async def test_scoping_is_labelled_as_analysis_not_documentation(self, monkeypatch):
        from unittest.mock import AsyncMock
        from autornd import config
        from autornd.models.verdicts import Domain
        import autornd.knowledge.context as ctx

        monkeypatch.setattr(config.settings, "model_research", "vendor/researcher")
        monkeypatch.setattr(ctx, "retrieve", lambda *a, **k: [])
        monkeypatch.setattr(ctx, "load_docs_context", lambda *a, **k: "")
        client = AsyncMock()
        client.chat_json = AsyncMock(return_value=(
            {"objective": "o", "unknowns": ["u"], "assumptions": [], "considerations": []}, None))

        out = await ctx.build_phase_context("req", [Domain.BACKEND], client=client)
        assert "REQUEST ANALYSIS" in out
        assert "assumptions, not facts" in out

    async def test_no_research_model_means_no_scoping(self, monkeypatch):
        from unittest.mock import AsyncMock
        from autornd import config
        import autornd.knowledge.context as ctx

        monkeypatch.setattr(config.settings, "model_research", "")
        assert await ctx.analyze_request(AsyncMock(), "req") == ("", [])

    async def test_scoping_failure_is_not_fatal(self, monkeypatch):
        from unittest.mock import AsyncMock
        from autornd import config
        import autornd.knowledge.context as ctx

        monkeypatch.setattr(config.settings, "model_research", "vendor/researcher")
        client = AsyncMock()
        client.chat_json = AsyncMock(side_effect=RuntimeError("down"))
        assert await ctx.analyze_request(client, "req") == ("", [])

    async def test_scoping_unknowns_drive_outward_lookups(self, monkeypatch):
        """An empty knowledge store is how this ships, and it is the case that
        most needs facts looked up. Search used to hang off documentation gaps
        only, which left the search tier configured, required, and inert on a
        default install."""
        from unittest.mock import AsyncMock
        from autornd import config
        from autornd.models.verdicts import Domain
        import autornd.knowledge.context as ctx
        import autornd.knowledge.research as research

        monkeypatch.setattr(config.settings, "model_research", "vendor/researcher")
        monkeypatch.setattr(config.settings, "model_search", "vendor/search")
        monkeypatch.setattr(ctx, "retrieve", lambda *a, **k: [])
        monkeypatch.setattr(ctx, "load_docs_context", lambda *a, **k: "")
        monkeypatch.setattr(research, "ingest_text", lambda *a, **k: 0)

        asked: list[str] = []

        client = AsyncMock()
        client.chat_json = AsyncMock(return_value=({
            "objective": "wire it", "unknowns": ["sensor supply voltage"],
            "assumptions": [], "considerations": []}, None))

        async def chat(**kw):
            asked.append(kw["user_message"])
            from autornd.routing.openrouter import ModelResponse
            return ModelResponse(content="18-30 V per the datasheet", model="m",
                                 prompt_tokens=1, completion_tokens=1, cost=0.0,
                                 citations=["https://example.com/ds.pdf"])

        client.chat = AsyncMock(side_effect=chat)

        out = await ctx.build_phase_context("wire it", [Domain.HARDWARE], client=client)
        assert "REQUEST ANALYSIS" in out
        assert "RESEARCHED FACTS" in out
        assert "18-30 V" in out
        assert any("sensor supply voltage" in a for a in asked)

    async def test_no_search_model_still_scopes(self, monkeypatch):
        from unittest.mock import AsyncMock
        from autornd import config
        from autornd.models.verdicts import Domain
        import autornd.knowledge.context as ctx

        monkeypatch.setattr(config.settings, "model_research", "vendor/researcher")
        monkeypatch.setattr(config.settings, "model_search", "")
        monkeypatch.setattr(ctx, "retrieve", lambda *a, **k: [])
        monkeypatch.setattr(ctx, "load_docs_context", lambda *a, **k: "")
        client = AsyncMock()
        client.chat_json = AsyncMock(return_value=({
            "objective": "o", "unknowns": ["u"], "assumptions": [],
            "considerations": []}, None))
        out = await ctx.build_phase_context("req", [Domain.BACKEND], client=client)
        assert "REQUEST ANALYSIS" in out
        assert "RESEARCHED FACTS" not in out


@pytest.mark.asyncio
class TestRerankModeIsProbedOnce:
    """Regression: two states were not enough. One transient failure of the
    native rerank call latched "unsupported", after which every workflow made a
    listwise chat call against a rerank-only model — which cannot answer it. A
    hiccup became a guaranteed wasted call per workflow for the life of the
    process."""

    CANDIDATES = [
        {"text": f"chunk {i}", "tag": f"t{i}", "source": "s", "distance": i / 10}
        for i in range(8)
    ]

    @staticmethod
    def _ranker(monkeypatch):
        from autornd import config
        import autornd.knowledge.context as ctx

        monkeypatch.setattr(config.settings, "model_ranker", "vendor/reranker")
        monkeypatch.setattr(ctx, "_rerank_mode", None)
        return ctx

    async def test_native_success_latches_native_and_never_chats(self, monkeypatch):
        from unittest.mock import AsyncMock

        ctx = self._ranker(monkeypatch)
        client = AsyncMock()
        client.rerank = AsyncMock(return_value=[(6, 0.9), (1, 0.4)])
        client.chat_json = AsyncMock()

        out = await ctx.rerank_chunks(client, "q", self.CANDIDATES, keep=2)
        assert [c["tag"] for c in out] == ["t6", "t1"]
        assert ctx._rerank_mode == "native"
        client.chat_json.assert_not_called()

    async def test_a_rerank_only_model_stops_costing_calls(self, monkeypatch):
        """The measured failure: native 404s, listwise 400s because the model
        cannot chat, and every later workflow must then make zero calls."""
        from unittest.mock import AsyncMock

        ctx = self._ranker(monkeypatch)
        client = AsyncMock()
        client.rerank = AsyncMock(side_effect=RuntimeError("404 no rerank"))
        client.chat_json = AsyncMock(side_effect=RuntimeError("400 cannot chat"))

        first = await ctx.rerank_chunks(client, "q", self.CANDIDATES, keep=3)
        assert [c["tag"] for c in first] == ["t0", "t1", "t2"]
        assert ctx._rerank_mode == "distance"
        assert client.rerank.await_count == 1
        assert client.chat_json.await_count == 1

        # the regression: a second workflow must cost nothing
        second = await ctx.rerank_chunks(client, "q", self.CANDIDATES, keep=3)
        assert [c["tag"] for c in second] == ["t0", "t1", "t2"]
        assert client.rerank.await_count == 1
        assert client.chat_json.await_count == 1

    async def test_a_chat_ranker_latches_listwise_and_stops_probing_native(self, monkeypatch):
        from unittest.mock import AsyncMock

        ctx = self._ranker(monkeypatch)
        client = AsyncMock()
        client.rerank = AsyncMock(side_effect=RuntimeError("404 no rerank"))
        client.chat_json = AsyncMock(return_value=({"ranking": [2, 4]}, None))

        out = await ctx.rerank_chunks(client, "q", self.CANDIDATES, keep=2)
        assert [c["tag"] for c in out] == ["t2", "t4"]
        assert ctx._rerank_mode == "listwise"

        await ctx.rerank_chunks(client, "q", self.CANDIDATES, keep=2)
        assert client.rerank.await_count == 1      # native not re-probed
        assert client.chat_json.await_count == 2

    async def test_a_transient_native_failure_keeps_the_native_mode(self, monkeypatch):
        """Worked before, failed now: a fault, not a capability change. Degrade
        for this workflow without downgrading the strategy permanently."""
        from unittest.mock import AsyncMock

        ctx = self._ranker(monkeypatch)
        client = AsyncMock()
        client.rerank = AsyncMock(return_value=[(0, 0.9), (1, 0.5)])
        client.chat_json = AsyncMock()
        await ctx.rerank_chunks(client, "q", self.CANDIDATES, keep=2)
        assert ctx._rerank_mode == "native"

        client.rerank = AsyncMock(side_effect=RuntimeError("503 upstream"))
        out = await ctx.rerank_chunks(client, "q", self.CANDIDATES, keep=3)
        assert [c["tag"] for c in out] == ["t0", "t1", "t2"]
        assert ctx._rerank_mode == "native"        # not downgraded
        client.chat_json.assert_not_called()       # and no doomed chat call

    async def test_reset_allows_a_re_probe(self, monkeypatch):
        import autornd.knowledge.context as ctx

        self._ranker(monkeypatch)
        monkeypatch.setattr(ctx, "_rerank_mode", "distance")
        ctx.reset_rerank_mode()
        assert ctx._rerank_mode is None
