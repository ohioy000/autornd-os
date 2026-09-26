"""Every retry is counted somewhere, and an empty rejection count says which.

**The measurement.** On the B17 prohibition run (2026-09-22,
`docs/traces/b17-prohibition-branch.jsonl`, stderr at
`docs/traces/b17-prohibition-branch-STDERR.txt`) stderr carried three retry
events — one JSON parse failure and two empty replies — while both
`rejections_by_tier` and `rejections_by_provider` were **empty** in the unit
record.

**The ruling: the counters were correct and narrow.** They are scoped to schema
rejections, and none of the three was one. `chat_json` has three retry paths and
only the `ValidationError` branch ever incremented them — by design, because the
counter's own comment defines a rejection as *a reply the truth table could not
repair*, which an empty reply is not.

**So the counters were not widened.** Widening them would have destroyed the
distinction that comment exists to preserve, and `normalised_verdicts` is read
against them as a pair. What was wrong is the REPORT: a reader seeing
`rejections_by_tier: {}` beside 23 calls cannot tell *"nothing was refused"* from
*"the refusals were a class this does not count"*. Convention 26 makes that the
instrument's defect, not the reader's error — so the record now reconciles, and
names the excluded classes.

Convention 28 is why `unattributed` is always present rather than omitted when
zero: an absent field and a measured zero are different claims, and only one of
them is evidence.
"""

from __future__ import annotations

import json
from typing import Any

import pytest

from autornd.routing.openrouter import ModelResponse, OpenRouterClient


def _client() -> OpenRouterClient:
    return OpenRouterClient(api_key="test-key")


def _reply(content: str, finish_reason: str | None = "stop") -> ModelResponse:
    return ModelResponse(
        content=content,
        model="test-provider/test-model",
        prompt_tokens=10,
        completion_tokens=5,
        cost=0.0001,
        provider="TestServing",
        finish_reason=finish_reason,
    )


class _Scripted:
    """Serves a fixed list of replies, one per call, then repeats the last."""

    def __init__(self, replies: list[ModelResponse]):
        self.replies = replies
        self.calls = 0

    async def __call__(self, *args: Any, **kwargs: Any) -> ModelResponse:
        reply = self.replies[min(self.calls, len(self.replies) - 1)]
        self.calls += 1
        return reply


@pytest.fixture
def client(monkeypatch):
    """A client whose retry backoff does not actually wait.

    The real backoff is `min(2 ** attempt, 8)` seconds and is correct — it is
    there for live providers. Left alone, these eight tests spend ~20s sleeping,
    which is a sixth of the whole suite's budget for no signal. The suite is
    free and fast on purpose (CONTRIBUTING.md), so the wait is stubbed and the
    retry LOGIC, which is what is under test, runs unchanged.

    The backoff is reached through a function-local `import asyncio as _aio`,
    so there is no module attribute to patch — `asyncio.sleep` itself is the
    only target that the local alias resolves to.
    """
    import asyncio

    async def _no_wait(_seconds):
        return None

    monkeypatch.setattr(asyncio, "sleep", _no_wait)
    return _client()


def _drive(client, monkeypatch, replies):
    """Run chat_json against a scripted sequence of provider replies."""
    scripted = _Scripted(replies)
    monkeypatch.setattr(client, "chat", scripted)
    return scripted


class TestEachRetryClassIsCounted:
    """One test per path, each simulating its own condition end to end."""

    async def test_an_empty_reply_is_counted_and_is_not_a_rejection(
        self, client, monkeypatch
    ):
        _drive(client, monkeypatch, [
            _reply("", finish_reason=None),
            _reply(json.dumps({"ok": True})),
        ])
        parsed, _ = await client.chat_json("engineering", "sys", "msg")

        assert parsed == {"ok": True}
        assert client.retries_by_kind == {client.RETRY_EMPTY_REPLY: 1}
        assert client.rejections_by_function == {}, (
            "an empty reply is not a schema rejection — the truth table never "
            "saw a reply to repair")
        assert client.rejections_by_provider == {}

    async def test_a_parse_failure_is_counted_and_is_not_a_rejection(
        self, client, monkeypatch
    ):
        _drive(client, monkeypatch, [
            _reply("this is not json at all"),
            _reply(json.dumps({"ok": True})),
        ])
        parsed, _ = await client.chat_json("engineering", "sys", "msg")

        assert parsed == {"ok": True}
        assert client.retries_by_kind == {client.RETRY_PARSE_FAILURE: 1}
        assert client.rejections_by_function == {}
        assert client.rejections_by_provider == {}

    async def test_a_schema_rejection_is_counted_in_both_places(
        self, client, monkeypatch
    ):
        from pydantic import BaseModel

        class Wants(BaseModel):
            required_field: str

        _drive(client, monkeypatch, [
            _reply(json.dumps({"wrong": "shape"})),
            _reply(json.dumps({"required_field": "here"})),
        ])
        parsed, _ = await client.chat_json(
            "engineering", "sys", "msg", schema=Wants)

        assert parsed == {"required_field": "here"}
        assert client.retries_by_kind == {client.RETRY_SCHEMA_REJECTION: 1}
        assert client.rejections_by_function == {"engineering": 1}
        assert client.rejections_by_provider == {"TestServing": 1}


class TestTheReportReconciles:
    async def test_total_equals_attributed_plus_unattributed(
        self, client, monkeypatch
    ):
        """The run's own shape: a parse failure and an empty reply, no rejection."""
        _drive(client, monkeypatch, [
            _reply("not json"),
            _reply("", finish_reason="error"),
            _reply(json.dumps({"ok": True})),
        ])
        await client.chat_json("engineering", "sys", "msg")

        report = client.retry_reconciliation()
        assert report["total"] == 2
        assert report["attributed"] == 0
        assert report["unattributed"] == 2
        assert report["total"] == report["attributed"] + report["unattributed"]

    async def test_an_empty_rejection_count_no_longer_reads_as_no_problem(
        self, client, monkeypatch
    ):
        """The defect this command exists to fix, asserted directly.

        Both rejection counters are empty AND two retries happened. Before the
        reconciliation, those two facts could not be told apart by any reader of
        the record.
        """
        _drive(client, monkeypatch, [
            _reply("not json"),
            _reply("", finish_reason="error"),
            _reply(json.dumps({"ok": True})),
        ])
        await client.chat_json("engineering", "sys", "msg")

        assert client.rejections_by_function == {}
        report = client.retry_reconciliation()
        assert report["unattributed"] == 2, (
            "an empty rejection count beside a non-zero retry total is exactly "
            "the reading this reconciliation exists to make possible")

    def test_unattributed_is_present_even_when_zero(self, client):
        """Convention 28: an absent field and a measured zero are different claims."""
        report = client.retry_reconciliation()
        assert report["total"] == 0
        assert "unattributed" in report, "omitted when zero — no evidence read as no problem"
        assert report["unattributed"] == 0

    def test_the_excluded_classes_are_named_in_the_report(self, client):
        """A reader must not have to open openrouter.py to learn what is excluded."""
        excluded = client.retry_reconciliation()["excluded_from_rejection_counters"]
        assert client.RETRY_EMPTY_REPLY in excluded
        assert client.RETRY_PARSE_FAILURE in excluded
        assert client.RETRY_SCHEMA_REJECTION not in excluded, (
            "schema rejections ARE attributed; listing them as excluded would "
            "make the reconciliation lie in the other direction")

    async def test_reset_accounting_clears_the_retry_counts(
        self, client, monkeypatch
    ):
        _drive(client, monkeypatch, [
            _reply("not json"), _reply(json.dumps({"ok": True}))])
        await client.chat_json("engineering", "sys", "msg")
        assert client.retry_reconciliation()["total"] == 1

        client.reset_accounting()
        assert client.retry_reconciliation()["total"] == 0
        assert client.retries_by_kind == {}


class TestAnExhaustedEmptySequenceIsAProviderFailure:
    """ARCH-20260926-073 acceptance 2: a truncated-or-empty reply is a
    distinct, counted, attributed failure class — demonstrated.

    The -071 shape: every attempt consumes its full budget and emits
    nothing (finish_reason=length, completion == max_tokens), three
    attempts, zero verdicts. The call must raise ProviderFailure carrying
    the serving — not the bare ValueError the record still shows — and
    record one provider_failures entry beside rejections_by_tier, which
    stays empty because an empty reply is not a schema rejection.

    The command's question 1, answered: a truncated reply does NOT bypass
    the retry path — the empty-reply branch already retries up to
    max_retries. So this is a visibility fix (the class is named, counted
    and attributed), not a retry-path fix — and per the constraint, NO
    retry was added or changed.
    """

    async def test_all_empty_raises_provider_failure_naming_the_serving(
        self, client, monkeypatch
    ):
        from autornd.routing.openrouter import ProviderFailure

        _drive(client, monkeypatch, [
            _reply("", finish_reason="length"),
            _reply("", finish_reason="length"),
            _reply("", finish_reason="length"),
        ])
        with pytest.raises(ProviderFailure) as exc:
            await client.chat_json("engineering", "sys", "msg")

        assert exc.value.function == "engineering"
        assert exc.value.provider == "TestServing"
        assert exc.value.serving("test-provider/test-model") == (
            "TestServing/test-provider/test-model")
        assert "finish_reason=length" in str(exc.value)

    async def test_the_failure_is_recorded_beside_not_inside_rejections(
        self, client, monkeypatch
    ):
        from autornd.routing.openrouter import ProviderFailure

        _drive(client, monkeypatch, [
            _reply("", finish_reason="length"),
            _reply("", finish_reason="length"),
            _reply("", finish_reason="length"),
        ])
        with pytest.raises(ProviderFailure):
            await client.chat_json("engineering", "sys", "msg")

        assert client.rejections_by_function == {}, (
            "an empty reply is not a schema rejection — acceptance 2 keeps "
            "the class distinct rather than widening the counter")
        assert client.rejections_by_provider == {}
        assert len(client.provider_failures) == 1
        entry = client.provider_failures[0]
        assert entry["function"] == "engineering"
        assert entry["provider"] == "TestServing"
        assert entry["finish_reason"] == "length"
        assert entry["attempts"] == 3

    async def test_a_mixed_sequence_raises_the_last_error_unchanged(
        self, client, monkeypatch
    ):
        """No single class owns a mixed sequence (convention 26): one empty
        reply then two parse failures is not a provider failure."""
        from autornd.routing.openrouter import ProviderFailure

        _drive(client, monkeypatch, [
            _reply("", finish_reason="length"),
            _reply("not json"),
            _reply("not json either"),
        ])
        with pytest.raises(ValueError) as exc:
            await client.chat_json("engineering", "sys", "msg")

        assert not isinstance(exc.value, ProviderFailure)
        assert client.provider_failures == []

    async def test_a_recovered_call_records_no_failure(
        self, client, monkeypatch
    ):
        """Per-call tracking (empty_attempts), not client history: a call
        that parses after one empty reply leaves no provider_failures entry,
        and a LATER exhausted call records exactly one — not two."""
        from autornd.routing.openrouter import ProviderFailure

        _drive(client, monkeypatch, [
            _reply("", finish_reason="length"),
            _reply(json.dumps({"ok": True})),
            _reply("", finish_reason="length"),
            _reply("", finish_reason="length"),
            _reply("", finish_reason="length"),
        ])
        parsed, _ = await client.chat_json("engineering", "sys", "msg")
        assert parsed == {"ok": True}
        assert client.provider_failures == []

        with pytest.raises(ProviderFailure):
            await client.chat_json("engineering", "sys", "msg")
        assert len(client.provider_failures) == 1

    async def test_no_retry_added_or_changed(self, client, monkeypatch):
        """Acceptance 5 (partial): the retry budget is untouched — the same
        max_retries=3 path the schema rejections already used."""
        import inspect

        from autornd.routing import openrouter as or_mod

        params = inspect.signature(or_mod.OpenRouterClient.chat_json).parameters
        assert params["max_retries"].default == 3
        assert or_mod.OpenRouterClient.RETRY_EMPTY_REPLY == "empty_reply"
