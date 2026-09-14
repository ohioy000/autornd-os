"""A budget stop must escape every handler that wraps a paid call.

**This is a propagation test file, not an accounting one.** The doubles here
raise `BudgetExceeded` *instead of* billing, so they deliberately do not call
`client._account`. Convention 9 — test doubles must bill like the real client —
does not apply: there is no call to bill, because the point is the call that was
refused. Do not "fix" these doubles to bill; it would test nothing.

Why this file exists at all. Every function covered here catches `Exception`
around a paid call, and each handler is correct: a lookup that breaks must not
sink a workflow, and context selection must never be the thing that fails a run.
But a spend ceiling raises through the same channel as a broken lookup, and a
handler that cannot tell them apart swallows the ceiling and lets the run keep
spending after it has been told to stop.

The class has now bitten twice:

  - HANDOVER §6.8: the rerank fallback latched on *any* exception, so one
    failure made a doomed call every workflow thereafter.
  - Blueprint 003 (§10.2): the same lines, plus four more, swallowed
    `BudgetExceeded`, so a sweep cap kept spending past its own limit. Found
    only because a test asserted *where* the abort landed.

Twice is a pattern, so it gets pinned rather than remembered.

**The rule for future work: when you add a paid call inside a broad `except`,
add its transparency test in the same commit.** The whole file runs free and in
milliseconds; there is no reason not to.
"""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock

import autornd.knowledge.context as ctx
import autornd.knowledge.research as research
from autornd.routing.openrouter import BudgetExceeded

STOP = BudgetExceeded("stopped at $1.0000 (ceiling $1.0000)")


def refusing_client():
    """A client whose every paid entry point refuses on budget grounds."""
    client = AsyncMock()
    client.chat_json = AsyncMock(side_effect=STOP)
    client.chat = AsyncMock(side_effect=STOP)
    client.rerank = AsyncMock(side_effect=STOP)
    return client


CHUNKS = [
    {"text": f"excerpt {i}", "tag": "docs", "distance": 0.1 * i, "source": "d.md"}
    for i in range(6)
]


@pytest.fixture(autouse=True)
def _tiers(monkeypatch):
    from autornd import config

    monkeypatch.setattr(config.settings, "model_research", "vendor/researcher")
    monkeypatch.setattr(config.settings, "model_search", "vendor/search")
    # Retrieval and ingestion are free and irrelevant here; keep them out of it.
    monkeypatch.setattr(ctx, "retrieve", lambda *a, **k: [])
    monkeypatch.setattr(research, "retrieve", lambda *a, **k: [])
    monkeypatch.setattr(research, "ingest_text", lambda *a, **k: 0)


@pytest.mark.asyncio
class TestGroundingHandlers:
    async def test_expand_queries_does_not_swallow_it(self):
        with pytest.raises(BudgetExceeded):
            await ctx.expand_queries(refusing_client(), "add retry with backoff")

    async def test_synthesize_briefing_does_not_swallow_it(self):
        with pytest.raises(BudgetExceeded):
            await ctx.synthesize_briefing(
                refusing_client(), "add retry with backoff", CHUNKS)

    async def test_analyze_request_does_not_swallow_it(self):
        with pytest.raises(BudgetExceeded):
            await ctx.analyze_request(refusing_client(), "add retry with backoff")


@pytest.mark.asyncio
class TestTheSearchTier:
    """The expensive one, and so the one a cap is most likely to stop."""

    async def test_research_gaps_does_not_swallow_it(self):
        with pytest.raises(BudgetExceeded):
            await research.research_gaps(
                refusing_client(), "add retry with backoff",
                ["the backoff ceiling"], max_tokens=1500)


@pytest.mark.asyncio
class TestBothRerankStrategies:
    """Each strategy is probed at most once and latches on failure, so a
    swallowed abort here does not merely lose the stop — it can also mark a
    working ranker dead for the rest of the process. §6.8 is that bug."""

    @pytest.fixture(autouse=True)
    def _ranker(self, monkeypatch):
        from autornd import config

        monkeypatch.setattr(config.settings, "model_ranker", "vendor/ranker")

    async def test_native_rerank_does_not_swallow_it(self, monkeypatch):
        monkeypatch.setattr(ctx, "_rerank_mode", "native")
        with pytest.raises(BudgetExceeded):
            await ctx.rerank_chunks(refusing_client(), "backoff", CHUNKS, 3)

    async def test_listwise_rerank_does_not_swallow_it(self, monkeypatch):
        monkeypatch.setattr(ctx, "_rerank_mode", "listwise")
        with pytest.raises(BudgetExceeded):
            await ctx.rerank_chunks(refusing_client(), "backoff", CHUNKS, 3)

    async def test_an_abort_does_not_latch_the_strategy_off(self, monkeypatch):
        """The §6.8 half of the bug, stated as its own expectation."""
        monkeypatch.setattr(ctx, "_rerank_mode", "native")
        with pytest.raises(BudgetExceeded):
            await ctx.rerank_chunks(refusing_client(), "backoff", CHUNKS, 3)
        assert ctx._rerank_mode == "native", (
            "a budget stop must not be read as 'this ranker does not work'")


@pytest.mark.asyncio
class TestOrdinaryFailuresStillDoNotEscape:
    """The guard must not have been bought by breaking the handlers.

    Everything above would also pass if these functions simply stopped catching
    anything, which would undo the reason each handler exists.
    """

    @staticmethod
    def _broken_client():
        client = AsyncMock()
        client.chat_json = AsyncMock(side_effect=RuntimeError("upstream 503"))
        client.chat = AsyncMock(side_effect=RuntimeError("upstream 503"))
        client.rerank = AsyncMock(side_effect=RuntimeError("upstream 503"))
        return client

    async def test_expand_queries_still_degrades(self):
        out = await ctx.expand_queries(self._broken_client(), "add retry")
        assert out == ["add retry"], "a broken expansion falls back to the request"

    async def test_analyze_request_still_degrades(self):
        scoping, unknowns = await ctx.analyze_request(self._broken_client(), "add retry")
        assert (scoping, unknowns) == ("", [])

    async def test_research_gaps_still_degrades(self):
        out = await research.research_gaps(
            self._broken_client(), "add retry", ["a gap"], max_tokens=1500)
        assert out == [], "a failed lookup is a missing finding, not a failed run"

    async def test_rerank_still_degrades(self, monkeypatch):
        from autornd import config

        monkeypatch.setattr(config.settings, "model_ranker", "vendor/ranker")
        monkeypatch.setattr(ctx, "_rerank_mode", "native")
        out = await ctx.rerank_chunks(self._broken_client(), "backoff", CHUNKS, 3)
        assert len(out) == 3, "ranking degrades to retrieval order rather than raising"
