"""Test knowledge store, context loading, and episodic memory."""

import json
import tempfile
from pathlib import Path

import pytest
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

    def test_build_phase_context_includes_docs(self):
        from autornd.knowledge.context import build_phase_context

        ctx = build_phase_context(
            "Add Modbus handler for new sensor",
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
