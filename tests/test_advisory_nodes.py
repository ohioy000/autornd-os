"""ARCH-20261021-124: advisory nodes, and the recompute that is one.

The review of #208 (docs/reviews/2026-10-21-review-208-d53-phase1.md, §2)
found D53 §2 (5) broken: a recompute sample that raised, or a watchdog cut
at the recompute, turned a run that completes without the vote into one that
raised or ended blocked. The run's status must be decided without the vote.
Two repairs: run_recompute records a failed sample and runs the next, and a
node marked `advisory: true` stores its skip output and lets the run go on
when its work raises, is cut mid-call, or is refused at the start.
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock

import pytest

from autornd.graph.adapter import PhaseRunner
from autornd.graph.checks import Result, _recompute_ident
from autornd.graph.executor import ABANDONED_CALL_BILLING, GraphExecutor
from autornd.graph.spec import SpecError, WorkflowSpec, load, parse
from autornd.models.verdicts import reset_normalisations
from autornd.routing import openrouter
from autornd.routing.openrouter import BudgetExceeded, OpenRouterClient
from tests.conftest import make_mock_response, seal_double
from tests.test_recompute_vote import REQUEST, SETTINGS, _workflow_router

WORKFLOW = "workflows/answer-and-recompute.yaml"


@pytest.fixture(autouse=True)
def _recompute_tier(monkeypatch):
    """Configure the recompute tier, so the node makes its calls through
    the double. The test environment leaves it unset, as production does."""
    monkeypatch.setattr(openrouter.settings, "model_recompute",
                        "vendor/recompute-tier")
    monkeypatch.setitem(OpenRouterClient.FUNCTION_MODELS, "recompute",
                        "vendor/recompute-tier")


@pytest.fixture(autouse=True)
def _reset_counts():
    """The runs here add coverage notes to the process-wide count, and
    tests/test_all_judges_exit.py reads that count without zeroing it.
    Zero it before and after, as tests/test_d51_acceptance.py does."""
    reset_normalisations()
    yield
    reset_normalisations()


def _double(router, fail_on=(), error=None, delay=None):
    """A recording double around the router. The recompute calls numbered
    in `fail_on` (1-based) raise `error`. `delay` maps a function name to
    the seconds each of its calls sleeps before answering."""
    client = OpenRouterClient(api_key="test")
    calls: list[dict[str, str]] = []

    async def chat_json(function, system_prompt, user_message, **kw):
        calls.append({"function": function, "user": user_message})
        if delay and function in delay:
            await asyncio.sleep(delay[function])
        if function == "recompute":
            number = sum(1 for c in calls if c["function"] == "recompute")
            if number in fail_on:
                raise error
        data = router(user_message, calls)
        response = make_mock_response(data, f"mock-{function}")
        client._account(function, response.cost)
        return data, response

    client.chat_json = AsyncMock(side_effect=chat_json)
    seal_double(client)
    client.close = AsyncMock()
    return client, calls


def _stripped(spec: WorkflowSpec) -> WorkflowSpec:
    """The same workflow without the recompute and its vote."""
    return WorkflowSpec(
        spec.name,
        [n for n in spec.nodes if n.id not in {"recompute", "recompute_vote"}],
        spec.description)


async def _run(spec: WorkflowSpec, fail_on=(), error=None, delay=None,
               **budget):
    """One run of the real graph behind the double: answer 100 against
    samples of 200, the flagged scenario of tests/test_recompute_vote.py."""
    client, calls = _double(_workflow_router(100.0, [200.0, 200.0, 200.0]),
                            fail_on, error, delay)
    executor = GraphExecutor(spec, PhaseRunner(client), SETTINGS, **budget)
    return await executor.run(REQUEST)


def _step(state, node_id: str):
    return next(s for s in state.trace if s.node_id == node_id)


class TestAFailedSample:
    """D53 §2 (5): a sample that raises is recorded, and the next one runs."""

    @pytest.mark.parametrize("error", [ValueError("not a verdict"),
                                       BudgetExceeded("run budget spent")],
                             ids=["value_error", "budget_exceeded"])
    async def test_a_failed_sample_is_recorded_and_the_run_completes(
            self, error):
        spec = load(WORKFLOW)
        full = await _run(spec, fail_on={2}, error=error)
        without = await _run(_stripped(spec))
        assert full.status == without.status == "completed"
        vote = full.outputs["recompute_vote"]
        assert vote["samples_parsed"] == 2
        assert vote["samples_failed"] == 1
        # Two of three still form a majority, and it differs from 100.
        assert vote["flagged"] is True
        failed = full.outputs["recompute"]["samples"][1]
        assert failed == {"failed": True,
                          "error": f"{type(error).__name__}: {error}"}

    async def test_two_failed_samples_leave_the_vote_unchecked(self):
        full = await _run(load(WORKFLOW), fail_on={2, 3},
                          error=ValueError("not a verdict"))
        assert full.status == "completed"
        vote = full.outputs["recompute_vote"]
        assert vote["unchecked"] is True
        assert vote["flagged"] is False
        assert vote["samples_parsed"] == 1
        assert vote["samples_failed"] == 2
        assert "2 failed" in vote["detail"]


class TestTheWatchdog:
    """A cut or a refusal at the advisory recompute is recorded, and the
    run goes on. Without the mark, the same run ends blocked."""

    async def test_a_cut_recompute_is_skipped_and_the_run_completes(self):
        spec = load(WORKFLOW)
        budget = {"time_budget": 1.5, "reserve_seconds": 0.0}
        full = await _run(spec, delay={"recompute": 3.0}, **budget)
        without = await _run(_stripped(spec), delay={"recompute": 3.0},
                             **budget)
        assert full.status == without.status == "completed"
        assert _step(full, "recompute").cancelled is True
        assert full.outputs["recompute"]["skipped"] is True
        assert full.outputs["recompute"]["samples"] == []
        assert full.outputs["recompute_vote"]["skipped"] is True
        assert full.watchdog.fired is False
        assert [c["rule"] for c in full.watchdog.advisory_cuts] == ["cancelled"]
        assert full.watchdog.advisory_cuts[0]["node"] == "recompute"
        assert full.watchdog.advisory_cuts[0]["billing"] == ABANDONED_CALL_BILLING

    async def test_breakproof_a_cut_recompute_not_advisory_blocks_the_run(self):
        spec = load(WORKFLOW)
        spec.get("recompute").advisory = False
        state = await _run(spec, delay={"recompute": 3.0},
                           time_budget=1.5, reserve_seconds=0.0)
        assert state.status == "blocked"
        assert state.watchdog.fired is True
        assert state.watchdog.rule == "cancelled"

    async def test_a_refused_recompute_is_skipped_and_the_run_completes(self):
        """The recompute shares the engineering tier here, so the answer's
        slow call gives the pre-start rule a pace to refuse on."""
        spec = load(WORKFLOW)
        spec.get("recompute").tier = "engineering"
        budget = {"time_budget": 2.0, "reserve_seconds": 0.0}
        full = await _run(spec, delay={"engineering": 1.2}, **budget)
        without = await _run(_stripped(spec), delay={"engineering": 1.2},
                             **budget)
        assert full.status == without.status == "completed"
        assert _step(full, "recompute").skipped is True
        assert full.outputs["recompute"]["skipped"] is True
        assert full.outputs["recompute_vote"]["skipped"] is True
        assert full.watchdog.fired is False
        assert [c["rule"] for c in full.watchdog.advisory_cuts] == [
            "not_started"]
        assert full.watchdog.advisory_cuts[0]["billing"] is None

    async def test_breakproof_a_refused_recompute_not_advisory_blocks_the_run(
            self):
        spec = load(WORKFLOW)
        spec.get("recompute").tier = "engineering"
        spec.get("recompute").advisory = False
        state = await _run(spec, delay={"engineering": 1.2},
                           time_budget=2.0, reserve_seconds=0.0)
        assert state.status == "blocked"
        assert state.watchdog.rule == "not_started"


class TestTheReviewProbe:
    """The probe of the review of #208, §2, as tests: each row reads the
    same status with the vote and without it."""

    @pytest.mark.parametrize("row", ["value_error", "budget_exceeded",
                                     "watchdog_cut"])
    async def test_the_status_is_the_same_with_and_without_the_vote(
            self, row):
        spec = load(WORKFLOW)
        if row == "watchdog_cut":
            kw = {"delay": {"recompute": 3.0}, "time_budget": 1.5,
                  "reserve_seconds": 0.0}
        else:
            kw = {"fail_on": {2}, "error": (
                ValueError("not a verdict") if row == "value_error"
                else BudgetExceeded("run budget spent"))}
        full = await _run(spec, **kw)
        without = await _run(_stripped(spec), **kw)
        assert full.status == without.status == "completed"


class _Runner:
    """A minimal runner: node `b` raises `error` or sleeps `sleep` seconds."""

    def __init__(self, error=None, sleep=0.0):
        self.error, self.sleep = error, sleep

    async def run_ai(self, node, state):
        if node.id == "b":
            if self.sleep:
                await asyncio.sleep(self.sleep)
            if self.error is not None:
                raise self.error
        return {"ok": True}

    async def run_check(self, node, state):
        return Result(True, "ok")


def _spec(advisory=False):
    return parse({"name": "t", "nodes": [
        {"id": "a", "kind": "ai", "tier": "t", "prompt": "p"},
        {"id": "b", "kind": "ai", "tier": "t", "prompt": "p",
         "depends_on": ["a"], "advisory": advisory},
        {"id": "c", "kind": "check", "check": "x", "depends_on": ["b"]},
    ]})


class TestUnchangedElsewhere:
    """A node that is not advisory behaves exactly as before, and the mark
    is allowed only where it means something."""

    async def test_a_node_that_is_not_advisory_still_raises(self):
        with pytest.raises(ValueError, match="boom"):
            await GraphExecutor(_spec(), _Runner(ValueError("boom"))).run("r")

    async def test_an_advisory_node_that_raises_stores_its_skip(self):
        state = await GraphExecutor(
            _spec(advisory=True), _Runner(ValueError("boom"))).run("r")
        assert state.status == "completed"
        assert state.outputs["b"] == {
            "skipped": True,
            "reason": "this advisory node raised ValueError: boom"}
        assert _step(state, "b").failed is True
        assert state.outputs["c"]["passed"] is True

    async def test_a_node_that_is_not_advisory_cut_still_blocks(self):
        state = await GraphExecutor(
            _spec(), _Runner(sleep=1.0), time_budget=0.3,
            reserve_seconds=0.0).run("r")
        assert state.status == "blocked"
        assert state.watchdog.rule == "cancelled"

    def test_advisory_defaults_to_false_and_parses_true(self):
        assert _spec().get("b").advisory is False
        assert _spec(advisory=True).get("b").advisory is True
        assert _spec().get("a").advisory is False

    @pytest.mark.parametrize("node", [
        {"id": "g", "kind": "gate", "condition": "a.ok == true",
         "depends_on": ["a"], "on_fail": "blocked", "advisory": True},
        {"id": "l", "kind": "ai", "body": ["a"], "until": "a.ok == true",
         "max_iterations": 2, "advisory": True},
    ], ids=["gate", "loop"])
    def test_advisory_on_a_gate_or_a_loop_is_refused(self, node):
        with pytest.raises(SpecError, match="cannot be advisory"):
            parse({"name": "t", "nodes": [
                {"id": "a", "kind": "ai", "tier": "t", "prompt": "p"}, node]})

    def test_advisory_must_be_true_or_false(self):
        with pytest.raises(SpecError, match="must be true or false"):
            _spec(advisory="yes")

    def test_only_the_recompute_is_advisory_in_the_shipped_workflows(self):
        from pathlib import Path

        marked = sorted(
            (path.stem, node.id)
            for path in Path("workflows").glob("*.yaml")
            for node in load(path).nodes if node.advisory)
        assert marked == [("answer-and-recompute", "recompute")]


class TestTheIdent:
    def test_in_parallel_is_part_of_the_identifier(self):
        """The review of #208, §3: a shipped check carries no subject's
        vocabulary, so 'in parallel' is no longer dropped."""
        assert _recompute_ident("VL-42") == _recompute_ident("vl 42")
        assert _recompute_ident("5 x EPC-1200-60") == _recompute_ident(
            "5 × EPC-1200-60")
        assert _recompute_ident("5 × EPC-1200-60 in parallel") != (
            _recompute_ident("5 × EPC-1200-60"))
