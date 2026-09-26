"""B18: a run stopped by a bound must end with a status that names the bound.

Measured 2026-09-21 on the B14 demonstration
(`docs/traces/b14-demo-marketing-claims-grounded.jsonl`). Read the trace before
believing the framing, which is what the command asked for and what narrowed
the fix:

    status: ''
    error:  "stopped at 42 model calls (ceiling 41); raise max_calls on the
             scenario if this is expected. By tier: {...}"

**The bound was named, and named well.** The `error` field is correct and is not
touched here. What was missing was the typed terminal, so a consumer reading
`status` saw a run that neither finished nor stopped.

The gap was in the EVAL RUNNER only. `engine/workflow.py` catches the same
exception in production and persists `WorkflowStatus.BLOCKED` with the message
as `error` — so `blocked` is what the harness already concludes for a
bound-stopped run, and matching it is consistency repair rather than a ruling.

Every test simulates its own condition end to end (convention 22): a real
`ExecutionState`, a real bound, through the real code path.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest

from autornd.evals.runner import _end_on_bound
from autornd.graph.executor import ExecutionState, _dissent_suffix
from autornd.graph.spec import Node, NodeKind

TRACE = Path("docs/traces/b14-demo-marketing-claims-grounded.jsonl")


def _state() -> ExecutionState:
    return ExecutionState(request="index the sensor readings table")


class TestEveryBoundNamesItself:
    """One per bound, in the operator's words."""

    def test_call_ceiling(self):
        state = _state()
        _end_on_bound(state, "call ceiling",
                      "stopped at 42 model calls (ceiling 41); "
                      "raise max_calls on the scenario if this is expected.")
        assert state.status == "blocked"
        assert "call ceiling" in state.reason
        assert "42 model calls" in state.reason      # the message is preserved

    def test_spend_ceiling(self):
        state = _state()
        _end_on_bound(state, "spend ceiling", "stopped at $0.1783 (ceiling $0.1500).")
        assert state.status == "blocked"
        assert "spend ceiling" in state.reason

    def test_deadline(self):
        state = _state()
        _end_on_bound(state, "deadline", "timed out after 1200s")
        assert state.status == "blocked"
        assert "deadline" in state.reason and "1200s" in state.reason

    def test_an_unhandled_error_also_terminates(self):
        """The path most likely to be forgotten. A run that broke is still a
        run that stopped, and a consumer reading `status` must not see a blank
        for it either."""
        state = _state()
        _end_on_bound(state, "unhandled error", "ValidationError: 2 errors")
        assert state.status == "blocked"
        assert state.reason


class TestTheBoundNeverStealsATerminal:
    def test_a_run_that_already_ended_keeps_its_own_status(self):
        """The ordering that matters. A bound firing after the run reached its
        own terminal is not the reason it stopped, and overwriting would make
        every late timeout look like a block."""
        state = _state()
        state.end("completed", "the deliverable was produced")
        _end_on_bound(state, "deadline", "timed out after 1200s")
        assert state.status == "completed"
        assert state.reason == "the deliverable was produced"


class TestStopReasonTravelsSeparately:
    """Ruling D23: the runner's stop-reason and the workflow terminal are
    two fields, never one. Each test simulates its condition end to end
    (convention 22): a real ExecutionState through the real _end_on_bound."""

    def test_a_bound_stopped_run_carries_both_fields(self):
        state = _state()
        _end_on_bound(state, "deadline", "timed out after 600s")
        assert state.status == "blocked"
        assert "deadline" in state.reason
        assert state.stop_reason == "runner stopped the run: timed out after 600s"

    def test_a_workflow_that_concluded_has_no_stop_reason(self):
        """A reader must be able to tell a workflow that concluded blocked
        from a runner that killed one that never concluded: the first has a
        terminal and no stop_reason; the second has both."""
        state = _state()
        state.end("blocked", "the workflow concluded it was blocked")
        _end_on_bound(state, "deadline", "timed out after 600s")
        assert state.status == "blocked"
        assert state.reason == "the workflow concluded it was blocked"
        assert state.stop_reason is None

    def test_removing_the_separation_returns_to_one_field(self):
        """Prove it by breaking it: without the separate field the record
        carries only the terminal and the -049 ambiguity returns — a reader
        cannot tell who stopped the run (convention 26)."""
        state = _state()
        _end_on_bound(state, "deadline", "timed out after 600s")
        fields = {k: v for k, v in vars(state).items()
                  if k in ("status", "reason", "stop_reason")}
        assert set(fields) == {"status", "reason", "stop_reason"}
        delattr(state, "stop_reason")
        assert "stop_reason" not in vars(state)


class TestLoopExhaustionNamesTheDissent:
    """The second half of B18: a loop that exhausts its bound already named the
    bound and never named WHY it kept going. `judges_agree` records `dissenting`
    on every failing fold."""

    @staticmethod
    def _body():
        return [Node(id="implement", kind=NodeKind.AI),
                Node(id="judges", kind=NodeKind.CHECK, check="judges_agree")]

    def test_the_dissenting_judges_are_named(self):
        state = _state()
        state.outputs["judges"] = {"green": False, "dissenting": ["coverage", "validate"]}
        assert _dissent_suffix(self._body(), state) == ", still red: coverage, validate"

    def test_silence_when_nothing_dissented(self):
        state = _state()
        state.outputs["judges"] = {"green": True, "dissenting": []}
        assert _dissent_suffix(self._body(), state) == ""

    def test_the_fold_is_found_by_shape_not_by_name(self):
        """A loop folds exactly the judges its own body produces, so the fold's
        id belongs to the workflow file and the executor must not assume it."""
        state = _state()
        state.outputs["whatever_the_file_called_it"] = {"dissenting": ["implement"]}
        body = [Node(id="whatever_the_file_called_it", kind=NodeKind.CHECK)]
        assert "implement" in _dissent_suffix(body, state)

    def test_a_missing_fold_output_is_not_a_crash(self):
        assert _dissent_suffix(self._body(), _state()) == ""


@pytest.mark.skipif(not TRACE.exists(), reason="demonstration trace not committed")
class TestAgainstTheRunThatOpenedB18:
    def test_the_committed_trace_still_shows_the_defect(self):
        """The measurement this exists for, asserted rather than remembered.
        Committed traces stand as measured and are never rewritten, so this is
        the before-picture and must keep failing the new standard."""
        records = [json.loads(line) for line in TRACE.read_text().splitlines() if line.strip()]
        unit = next(r for r in records if r.get("record") == "unit")
        assert unit["status"] == ""                       # no terminal
        assert "ceiling 41" in unit["error"]              # the bound, named well

    def test_replaying_that_stop_now_yields_a_terminal(self):
        records = [json.loads(line) for line in TRACE.read_text().splitlines() if line.strip()]
        unit = next(r for r in records if r.get("record") == "unit")

        state = _state()
        _end_on_bound(state, "call ceiling", unit["error"])
        assert state.status == "blocked"
        assert "call ceiling" in state.reason
        assert "ceiling 41" in state.reason


class TestTheRunnerActuallyCallsIt:
    """The lesson from this morning's preflight repair, applied to my own work.

    Six preflight tests passed against broken code because every one of them
    tested the pure core while both bugs lived in the wiring that built its
    arguments. The first version of this class made the same mistake — it
    called the helper by hand and asserted the helper worked, which proves
    nothing about whether `run_scenario` calls it.

    So this drives `run_scenario` itself: a real `Scenario`, a real
    `WorkflowSpec`, and an executor whose `run` raises the real bound. The
    assertion is on the recorded `ScenarioRun.status`, which is the field that
    was empty in the committed trace.
    """

    @staticmethod
    def _drive(exc: Exception):
        import autornd.evals.runner as runner_mod
        from autornd.evals.scenario import Scenario
        from autornd.graph.spec import WorkflowSpec

        class FakeExecutor:
            def __init__(self, *a, **k):
                self.state = ExecutionState(request="r")

            async def run(self, request):
                raise exc

        original = runner_mod.GraphExecutor
        runner_mod.GraphExecutor = FakeExecutor
        try:
            return asyncio.run(runner_mod.run_scenario(
                scenario=Scenario(id="s", request="r", expect={}),
                spec=WorkflowSpec(name="w", nodes=[]),
                client_factory=lambda: _StubClient(),
                settings_lookup={},
                timeout=5.0,
            ))
        finally:
            runner_mod.GraphExecutor = original

    def test_a_ceiling_stop_is_recorded_with_a_status(self):
        from autornd.routing.openrouter import BudgetExceeded

        run = self._drive(BudgetExceeded(
            "stopped at 42 model calls (ceiling 41); "
            "raise max_calls on the scenario if this is expected."))
        assert run.status == "blocked"                 # was "" in the trace
        assert "ceiling 41" in run.error               # message untouched

    def test_a_deadline_stop_is_recorded_with_a_status(self):
        run = self._drive(asyncio.TimeoutError())
        assert run.status == "blocked"
        assert "timed out" in run.error

    def test_an_unhandled_error_is_recorded_with_a_status(self):
        run = self._drive(RuntimeError("something gave way"))
        assert run.status == "blocked"
        assert "RuntimeError" in run.error


class _StubClient:
    """Enough client for a run that never makes a call. `total_cost` and the
    per-tier dicts are read unconditionally when the ScenarioRun is built."""

    def __init__(self) -> None:
        self.spend_by_function: dict = {}
        self.calls_by_function: dict = {}
        self.providers_by_function: dict = {}
        self.tokens_by_function: dict = {}
        self.rejections_by_function: dict = {}
        self.rejections_by_provider: dict = {}
        self.provider_failures: list = []
        self.retries_by_kind: dict = {}
        self.call_ceiling = None
        self.spend_ceiling = None
        self.calls = 0
        self.spend = 0.0

    def reset_accounting(self) -> None:
        pass

    def retry_reconciliation(self) -> dict:
        """A run that never called anything still reports its zero.

        Added when B23's reconciliation landed. The same rule that makes a
        double bill applies here: a double that omitted this would report no
        retries because it cannot count, which is exactly the "no evidence read
        as no problem" confusion the reconciliation exists to prevent.
        `unattributed` is present and zero rather than absent (convention 28).
        """
        return {"total": 0, "attributed": 0, "unattributed": 0,
                "by_kind": {}, "excluded_from_rejection_counters":
                    ["empty_reply", "parse_failure"]}


class TestAProviderFailureReachesATypedTerminal:
    """ARCH-20260926-073: the -071 shape, simulated end to end (convention 22).

    Read the trace before believing the framing, which is what the command
    asked for. `docs/traces/071-live-terminal-2.jsonl` unit record:

        error: "ValueError: model returned no text (provider=GMICloud,
                finish_reason=length, completion_tokens=8000 of
                max_tokens=8000 — ...)"
        status: "blocked", stop_reason: "runner stopped the run: ValueError:
                model returned no text (provider=GMICloud, ...)"
        path: [..., "consistency", "validate"] — died AT validate, 12 calls,
              $0.0287.
        retries: total 4, unattributed 4, by_kind {empty_reply: 4}.

    Two corrections to the command's framing, both from the trace rather
    than the PR body. First, the failing tier was VALIDATE on the
    architecture tier (StreamLake served plan, GMICloud served validate —
    providers_by_function), and the FIRST empty reply (16384/16384) was an
    earlier engineering call; validate then failed 8000/8000 three times.
    So: finish_reason=length, completion 8000 of max_tokens 8000, content
    EMPTY (not truncated — nothing was emitted at all). Second, the -071
    unit record ALREADY carries status "blocked" — the B18 terminal, which
    fires for any exception. What was missing was not a terminal but a
    terminal that NAMES the provider failure: the reason read "stopped by
    the unhandled error: ValueError: model returned no text (...)", which
    is the generic bucket, not the failure class. This class asserts the
    terminal names the tier and the serving, and the unit record carries
    the failure beside rejections_by_tier.
    """

    TRACE_071 = Path("docs/traces/071-live-terminal-2.jsonl")

    def test_the_trace_shows_empty_not_truncated(self):
        """Acceptance 1: the validate call's finish_reason, quoted from the
        trace rather than the PR body. If this fails, the 'truncated reply'
        framing is wrong and so is everything built on it."""
        if not self.TRACE_071.exists():
            pytest.skip("071 trace not committed")
        records = [json.loads(line) for line in self.TRACE_071.read_text().splitlines()
                   if line.strip()]
        unit = next(r for r in records if r.get("record") == "unit")
        assert "finish_reason=length" in unit["error"]
        assert "completion_tokens=8000 of max_tokens=8000" in unit["error"]
        assert unit["retries"]["by_kind"] == {"empty_reply": 4}
        assert unit["path"][-1] == "validate"

    @staticmethod
    def _drive(provider_failure):
        import autornd.evals.runner as runner_mod
        from autornd.evals.scenario import Scenario
        from autornd.graph.spec import WorkflowSpec

        class FakeExecutor:
            def __init__(self, *a, **k):
                self.state = ExecutionState(request="r")

            async def run(self, request):
                raise provider_failure

        original = runner_mod.GraphExecutor
        runner_mod.GraphExecutor = FakeExecutor
        try:
            return asyncio.run(runner_mod.run_scenario(
                scenario=Scenario(id="s", request="r", expect={}),
                spec=WorkflowSpec(name="w", nodes=[]),
                client_factory=lambda: _StubClient(),
                settings_lookup={},
                timeout=5.0,
            ))
        finally:
            runner_mod.GraphExecutor = original

    def test_a_provider_failure_reaches_a_typed_terminal_naming_it(self):
        """Acceptance 3: the run ends blocked with the tier and provider in
        the reason — not the generic 'unhandled error' bucket."""
        from autornd.routing.openrouter import ProviderFailure

        run = self._drive(ProviderFailure(
            "engineering", "GMICloud",
            "model returned no text (provider=GMICloud, finish_reason=length, "
            "completion_tokens=8000 of max_tokens=8000)"))
        assert run.status == "blocked"
        assert "provider failure" in (run.error or "")
        assert "engineering" in (run.error or "")
        assert "GMICloud" in (run.error or "")
        assert "unhandled error" not in (run.error or "")

    def test_stop_reason_and_terminal_stay_separate(self):
        """Acceptance 4 (Ruling D23): the terminal names the failure, the
        stop_reason names how the runner stopped — asserted, not merged."""
        import autornd.evals.runner as runner_mod
        from autornd.evals.scenario import Scenario
        from autornd.graph.spec import WorkflowSpec
        from autornd.routing.openrouter import ProviderFailure

        states = {}

        class FakeExecutor:
            def __init__(self, *a, **k):
                self.state = ExecutionState(request="r")
                states["state"] = self.state

            async def run(self, request):
                raise ProviderFailure("engineering", "GMICloud", "no text")

        original = runner_mod.GraphExecutor
        runner_mod.GraphExecutor = FakeExecutor
        try:
            run = asyncio.run(runner_mod.run_scenario(
                scenario=Scenario(id="s", request="r", expect={}),
                spec=WorkflowSpec(name="w", nodes=[]),
                client_factory=lambda: _StubClient(),
                settings_lookup={},
                timeout=5.0,
            ))
        finally:
            runner_mod.GraphExecutor = original

        state = states["state"]
        assert state.status == "blocked"
        assert state.stop_reason is not None
        assert state.stop_reason.startswith("runner stopped the run: ")
        assert state.reason != state.stop_reason, (
            "the terminal and the stop-reason must never be the same field")
        assert run.stop_reason == state.stop_reason


class TestLoopExhaustionEndToEnd:
    """Driving the executor's real loop, because the tests above prove only
    that `_dissent_suffix` works — not that exhaustion calls it.

    This is the third time today that distinction has mattered. It is written
    out rather than assumed.
    """

    @staticmethod
    def _run_an_exhausting_loop():
        from autornd.graph.executor import GraphExecutor
        from autornd.graph.spec import WorkflowSpec

        class Runner:
            """A body that never converges: the fold is red every iteration,
            exactly as the B14 demonstration's seven iterations were."""

            async def run_ai(self, node, state):
                return {"green": False}

            async def run_check(self, node, state):
                from autornd.graph.checks import Result
                return Result(False, "not agreed",
                              green=False, dissenting=["coverage", "validate"])

        spec = WorkflowSpec(name="w", nodes=[
            Node(id="build_loop", kind=NodeKind.CHECK,
                 body=["implement", "judges"],
                 until="judges.passed == true",
                 max_iterations=2,
                 on_exhausted_status="escalated"),
            Node(id="implement", kind=NodeKind.AI),
            Node(id="judges", kind=NodeKind.CHECK, check="judges_agree"),
        ])
        executor = GraphExecutor(spec, Runner(), {})
        return asyncio.run(executor.run("r"))

    def test_the_exhausted_loop_names_the_bound_and_the_dissent(self):
        state = self._run_an_exhausting_loop()
        assert state.status == "escalated"
        assert "did not converge within 2 iterations" in state.reason   # the bound
        assert "still red: coverage, validate" in state.reason          # the cause
