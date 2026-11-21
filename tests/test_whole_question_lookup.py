"""The first lookup of a run asks the whole request too (owner, 2026-11-21).

Scoping rewrites a request into the unknowns it has to settle, and a rewrite
can lose the words that say which document is meant. Read from the ten X12
draws kept from 2026-11-20 and 21: the three draws that asked the whole
question all read IAEA pages; of the seven that asked scoping's rewrite, three
read only US federal rules and all three gave a wrong answer. The owner's
word: "also scope the whole question if it's still frugal". It is frugal by
construction, and the tests pin that: the lookup stays one request.
"""

from __future__ import annotations

import glob
import json
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

import autornd.knowledge.context as ctx
from autornd import config
from autornd.knowledge import research
from autornd.knowledge.research import WHOLE_QUESTION_MAX_CHARS, lookup_questions
from autornd.models.verdicts import Domain, RiskLevel
from autornd.routing.openrouter import ModelResponse

ROOT = Path(__file__).resolve().parent.parent
REQUEST = ("Under the current edition of the international rules, what TI is "
           "assigned to a container at 0.08 mSv/h at 1 m with a 3 m2 load?")
GAP = "the multiplication factor for a load of 3 m2"


class TestWhatTheFirstLookupAsks:
    def test_the_request_comes_first_then_each_gap(self):
        assert lookup_questions(REQUEST, [GAP, "the TI limit"]) == [
            REQUEST, GAP, "the TI limit"]

    def test_no_gaps_means_no_lookup_is_made_for_the_request_alone(self):
        assert lookup_questions(REQUEST, []) == []
        assert lookup_questions(REQUEST, ["", "   "]) == []

    def test_a_gap_that_is_the_request_is_not_asked_twice(self):
        assert lookup_questions(REQUEST, [f"  {REQUEST} "]) == [REQUEST]

    def test_blank_gaps_are_dropped_and_the_rest_trimmed(self):
        assert lookup_questions(REQUEST, ["", f" {GAP} "]) == [REQUEST, GAP]

    def test_a_request_past_the_cap_is_a_brief_and_stands_aside(self):
        at_the_cap = "x" * WHOLE_QUESTION_MAX_CHARS
        assert lookup_questions(at_the_cap, [GAP]) == [at_the_cap, GAP]
        assert lookup_questions(at_the_cap + "x", [GAP]) == [GAP]

    def test_the_cap_covers_every_question_in_the_evaluation_sets(self):
        lengths = []
        for path in glob.glob(str(ROOT / "evals" / "**" / "*questions.json"),
                              recursive=True):
            data = json.load(open(path, encoding="utf-8"))
            for q in (data["questions"] if isinstance(data, dict) else data):
                lengths.append(len(q.get("question") or q.get("prompt") or ""))
        # The guard read its subject before it judged it: 111 questions in
        # the five sets when the cap was set, the longest 1,091 characters.
        assert len(lengths) >= 111 and max(lengths) == 1091
        assert max(lengths) <= WHOLE_QUESTION_MAX_CHARS


@pytest.fixture
def empty_store(monkeypatch):
    monkeypatch.setattr(config.settings, "model_research", "vendor/researcher")
    monkeypatch.setattr(config.settings, "model_search", "vendor/search")
    monkeypatch.setattr(ctx, "retrieve", lambda *a, **k: [])
    monkeypatch.setattr(ctx, "load_docs_context", lambda *a, **k: "")
    monkeypatch.setattr(research, "retrieve", lambda *a, **k: [])
    monkeypatch.setattr(research, "ingest_text", lambda *a, **k: 0)


def _client(blocking):
    client = AsyncMock()
    client.chat_json = AsyncMock(return_value=({
        "objective": "o", "unknowns": [GAP], "blocking_unknowns": blocking,
        "assumptions": [], "considerations": []}, None))
    client.chat = AsyncMock(return_value=ModelResponse(
        content="A: the figure", model="m", prompt_tokens=1,
        completion_tokens=1, cost=0.0, citations=["https://example.org/ds.pdf"]))
    return client


class TestTheEmptyStorePath:
    async def test_one_search_request_asks_the_request_then_the_gap(
            self, empty_store, pages_served):
        client, record = _client([GAP]), {}
        await ctx.build_phase_context(
            REQUEST, [Domain.HARDWARE], client=client, risk=RiskLevel.HIGH,
            grounding_lookup=record)
        # Frugal: still the one search request, and the record says what it asked.
        assert client.chat.await_count == 1
        assert record["asked"] == [REQUEST, GAP]
        assert f"1. {REQUEST}\n2. {GAP}" in client.chat.await_args.kwargs[
            "user_message"]

    async def test_a_declined_lookup_defers_only_the_gaps(
            self, empty_store):
        client, deferred = _client([GAP]), []
        await ctx.build_phase_context(
            REQUEST, [Domain.HARDWARE], client=client, risk=RiskLevel.LOW,
            deferred_gaps=deferred)
        assert client.chat.await_count == 0
        assert deferred == [GAP], "what was declined, not the request"

    async def test_no_blocking_gap_and_nothing_demanded_is_no_lookup(
            self, empty_store):
        client, record = _client([]), {}
        await ctx.build_phase_context(
            REQUEST, [Domain.HARDWARE], client=client, risk=RiskLevel.LOW,
            grounding_lookup=record)
        assert client.chat.await_count == 0 and record == {}

    async def test_a_request_that_asks_to_be_cited_is_asked_once(
            self, empty_store, pages_served):
        cited = "What is the limit? Cite the datasheet."
        client, record = _client([]), {}
        await ctx.build_phase_context(
            cited, [Domain.HARDWARE], client=client, risk=RiskLevel.LOW,
            grounding_lookup=record)
        assert client.chat.await_count == 1
        assert record["asked"] == [cited]


class TestTheDocumentationPath:
    async def test_the_briefings_lookup_asks_the_request_too(self, monkeypatch,
                                                           pages_served):
        monkeypatch.setattr(config.settings, "model_research", "vendor/researcher")
        monkeypatch.setattr(config.settings, "model_search", "vendor/search")
        client, record = _client([]), {}
        client.chat_json = AsyncMock(return_value=(
            {"briefing": "Supply is 24V nominal.", "gaps": [GAP],
             "blocking_gaps": [GAP]}, None))
        await ctx.synthesize_briefing(
            client, REQUEST,
            [{"text": "24V nominal", "tag": "power", "distance": 0.1}],
            risk=RiskLevel.HIGH, grounding_lookup=record)
        assert client.chat.await_count == 1
        assert record["asked"] == [REQUEST, GAP]
        # What was sent, not only what was recorded.
        assert f"1. {REQUEST}\n2. {GAP}" in client.chat.await_args.kwargs[
            "user_message"]

    async def test_a_declined_lookup_defers_only_the_gaps(self, monkeypatch):
        monkeypatch.setattr(config.settings, "model_research", "vendor/researcher")
        monkeypatch.setattr(config.settings, "model_search", "vendor/search")
        client, deferred = _client([]), []
        client.chat_json = AsyncMock(return_value=(
            {"briefing": "Supply is 24V nominal.", "gaps": [GAP],
             "blocking_gaps": [GAP]}, None))
        await ctx.synthesize_briefing(
            client, REQUEST,
            [{"text": "24V nominal", "tag": "power", "distance": 0.1}],
            risk=RiskLevel.LOW, deferred_gaps=deferred)
        assert client.chat.await_count == 0
        assert deferred == [GAP]
