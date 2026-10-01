"""Ruling D38 — the deliberation watchdog finishes cleanly.

**What bought this.** ARCH-20260930-094: the build judges agreed on the
second implementation pass at $0.070, the run went on through review,
rework, escalation and recovery, and the eval runner killed it from outside
at 3,600 s mid-rework_review, $0.51 spent and no answer returned. Three
night runs before it (091, at 1,500, 3,900 and 4,800 s) died the same way.
D25's second clause, that a run emits its own terminal at its deadline,
existed only as a comment beside the runner's `wait_for`.

**What is ruled.** A run with a declared time budget ends by its own
terminal. A call this run's own pace says cannot finish inside the budget
less a reserve is not started; a call still running when that point
arrives is cancelled. Either way the status is blocked, a typed record
names what fired, and the terminal points at the last implementation the
build judges agreed on. A run with no budget behaves exactly as before.

**How these tests are built (convention 22).** Every one drives the real
GraphExecutor over the real `workflows/engineering-rnd.yaml` with the real
PhaseRunner, through `make_mock_client`, whose calls take a declared time
and still bill. Nothing here stands in for the adapter or the executor.
Delays and budgets are milliseconds, with each margin set so that a slow
machine moves the outcome in the direction the test already asserts.
"""

from __future__ import annotations

import asyncio
import json
import statistics
import time
from unittest.mock import AsyncMock

import pytest

from autornd.evals.runner import ResultsLog, _isolated_store, run_scenario
from autornd.evals.scenario import parse
from autornd.graph import executor as executor_module
from autornd.graph.adapter import PhaseRunner
from autornd.graph.executor import (
    ABANDONED_CALL_BILLING, WATCHDOG_RESERVE_SECONDS, GraphExecutor,
    SLOW_CALL_MULTIPLE, WatchdogRecord, _watchdog_reason,
)
from autornd.graph.spec import load
from autornd.routing.openrouter import OpenRouterClient
from tests.conftest import make_mock_client

SPEC = load("workflows/engineering-rnd.yaml")
SETTINGS = {"max_iterations": 5, "escalation_recovery_attempts": 3,
            "review_rework_attempts": 2}
REQUEST = "Add retry with exponential backoff to the MQTT client"

# One reply per function, each a union of the verdicts that function serves
# on this workflow. The verdict models ignore keys they do not declare, so the
# judge reply satisfies domain_review, validate and review at once, and the
# engineering reply satisfies feasibility and implement.
RESPONSES = {
    "triage": {"domains": ["backend"], "risk": "medium",
               "specialists": ["backend_engineer", "test_engineer"],
               "summary": "MQTT client retry", "unrecallable": False},
    "architecture": {"ready": True, "plan": "Cap backoff at 60s.", "blockers": [],
                     "success_criteria": ["Backoff is capped at 60s with jitter"]},
    "engineering": {"feasible": True, "concerns": [], "blockers": [],
                    "done": True, "green": True, "red_cause": None,
                    "summary": "Backoff is capped at 60s with jitter applied."},
    "judge": {"concerns": [], "critical": False, "green": True,
              "red_cause": None, "evidence": [], "ship": True, "findings": [],
              "verdict": "Ship."},
}

# The path and per-function call counts of this request on this workflow
# BEFORE D38, read on c444c51 (the ruling commit, executor untouched) with
# the same double: completed, 17 nodes, 10 calls. Recorded in the 095
# response.
TODAY_PATH = ["triage", "context", "plan", "reground_context", "feasibility",
              "plan_ready", "verify_grounding", "implement", "blocked_check",
              "blocked_gate", "domain_review", "coverage", "consistency",
              "validate", "judges", "review", "review_clean"]
TODAY_CALLS = {"triage": 1, "research": 2, "architecture": 1,
               "engineering": 3, "judge": 3}

# Prompt phrases that tell the judge tier's phases apart, for the doubles
# below that need one phase slower than another. Each is a line of the
# phase's own prompt in autornd/engine/phases.py.
VALIDATE_PROMPT = "validate this implementation against the plan"
REVIEW_PROMPT = "ship: true if safe to ship"
IMPLEMENT_PROMPT = "implementation for the following plan"


def _responses(**overrides) -> dict:
    out = {k: dict(v) for k, v in RESPONSES.items()}
    for function, patch in overrides.items():
        out[function].update(patch)
    return out


def _reshape(client, before=None, summary_by_call=False) -> None:
    """Wrap the double's chat_json without replacing it: the original still
    sleeps for its declared delay and still bills. `before(function,
    message)` may await extra time first; `summary_by_call` numbers each
    implementation so a rework produces a different artifact."""
    original = client.chat_json.side_effect
    implements = {"n": 0}

    async def wrapped(function, system_prompt, user_message, **kwargs):
        message = user_message.lower()
        if before is not None:
            await before(function, message)
        data, response = await original(function, system_prompt, user_message, **kwargs)
        if summary_by_call and function == "engineering" and IMPLEMENT_PROMPT in message:
            implements["n"] += 1
            data = {**data, "summary": f"{data['summary']} Revision {implements['n']}."}
        return data, response

    client.chat_json = AsyncMock(side_effect=wrapped)


@pytest.fixture(scope="module", autouse=True)
def _one_warm_store():
    """One isolated knowledge store for the whole module, warmed once.

    Measured 2026-09-30: the time to reach the first judge call is almost
    all `context`, and a fresh store per run made it 0.10-0.25 s unloaded
    and past 0.35 s with two copies of this file running, which flipped
    timing margins. A shared, warm store holds it near 0.04 s. Isolation
    is kept: nothing here reads a developer's local store.
    """
    with _isolated_store():
        asyncio.run(_run(make_mock_client(_responses())))
        yield


async def _run(client, budget=None, reserve=None):
    runner = PhaseRunner(client)
    executor = GraphExecutor(SPEC, runner, SETTINGS, time_budget=budget,
                             reserve_seconds=reserve)
    started = time.perf_counter()
    state = await executor.run(REQUEST)
    returned = time.perf_counter() - started
    return state, runner, returned


def _scenario(timeout: float):
    return parse({"id": "watchdog", "request": REQUEST, "timeout": timeout})


def _disable_watchdog(monkeypatch) -> None:
    """The break: the executor runs every node as it did before D38."""
    async def bare(self, work, node, state, record):
        await work(node, state)
        return True

    monkeypatch.setattr(GraphExecutor, "_watched", bare)
    monkeypatch.setattr(GraphExecutor, "_refuse_to_start",
                        lambda self, node, state, tier: False)


class TestNoBudgetIsToday:
    """(a) No declared budget: the same path, calls and status as before D38,
    and no timer is ever entered."""

    async def test_no_budget_enters_no_timer_and_matches_the_pre_d38_run(self, monkeypatch):
        def no_timer(*args, **kwargs):
            raise AssertionError("an unbudgeted run entered the watchdog's timer")

        monkeypatch.setattr(executor_module.asyncio, "timeout", no_timer)
        client = make_mock_client(_responses())
        state, _, _ = await _run(client)
        assert state.status == "completed", state.reason
        assert state.path == TODAY_PATH
        assert client.calls == 10
        assert dict(client.calls_by_function) == TODAY_CALLS
        assert state.stop_reason is None
        watchdog = state.watchdog
        assert watchdog.armed is False and watchdog.fired is False
        assert watchdog.budget_seconds is None and watchdog.approved is None

    async def test_a_budget_that_never_binds_changes_nothing(self):
        client = make_mock_client(_responses())
        state, _, _ = await _run(client, budget=60.0)
        assert state.status == "completed"
        assert state.path == TODAY_PATH
        assert dict(client.calls_by_function) == TODAY_CALLS
        assert state.watchdog.armed is True and state.watchdog.fired is False


class TestAJudgeCallIsCancelledMidFlight:
    """(b) Through the eval runner: the first judge call has no pace yet, so
    it starts, outlives the budget, and is cut at the reserve."""

    async def test_the_cut_is_the_workflows_own_terminal(self):
        # The shipped reserve (0.4 s) puts the cut at 0.8 s. Getting to
        # validate takes 0.1-0.25 s through run_scenario, which builds a
        # fresh store per run, and may take 0.8 s before the outcome
        # changes; the judge call takes 3 s.
        budget = 1.2
        run = await run_scenario(
            _scenario(budget), SPEC,
            lambda: make_mock_client(_responses(), delays={"judge": 3.0}), SETTINGS)
        assert run.status == "blocked"
        # D23: the watchdog end is the workflow's terminal, not the runner's.
        assert run.stop_reason is None and run.error is None
        watchdog = run.watchdog
        assert watchdog["fired"] is True and watchdog["rule"] == "cancelled"
        assert (watchdog["node"], watchdog["iteration"], watchdog["tier"]) == (
            "validate", 1, "judge")
        assert watchdog["pace_seconds"] is None        # first judge call: no pace
        assert watchdog["terminal_seconds"] < watchdog["budget_seconds"]
        assert run.seconds < budget
        assert watchdog["billing"] == ABANDONED_CALL_BILLING
        assert watchdog["serving_observed"] is None
        assert watchdog["serving_configured"]["model"]
        # The cancelled call is in the record, marked, and never billed.
        assert run.steps[-1]["node"] == "validate" and run.steps[-1]["cancelled"] is True
        assert run.calls_by_tier.get("judge", 0) == 0
        # Nothing was agreed: said so, and the latest work is labelled.
        approved = watchdog["approved"]
        assert approved["history"] == "present" and approved["agreed"] is False
        assert approved["latest"] == "unjudged"

    async def test_disabling_the_watchdog_hands_the_run_to_the_runners_kill(self, monkeypatch):
        """Convention 22, the break: with the watchdog off, the same run is
        killed from outside by the runner's wait_for, which is exactly what
        D38 names as its falsifier."""
        _disable_watchdog(monkeypatch)
        run = await run_scenario(
            _scenario(1.2), SPEC,
            lambda: make_mock_client(_responses(), delays={"judge": 3.0}), SETTINGS)
        assert run.stop_reason == "runner stopped the run: timed out after 1s"
        assert run.watchdog["fired"] is False


class TestThePaceRuleDoesNotStartACallThatCannotFinish:
    """(c) After one slow judge call, the next judge call is not started when
    the time left is under that pace. The client's call count proves it."""

    async def test_the_next_judge_call_is_never_made(self):
        # Let `pre` be the time to reach validate (~0.04 s). validate is
        # granted 0.9 - pre and needs 0.5, so it completes for any pre up to
        # 0.4 s. review would then have 0.4 - pre against a 0.5 s pace, which
        # is refused for every pre >= 0. Measured 2026-09-30: a 0.55 s budget
        # with 0.3 s calls left pre only 0.2 s, and two copies of this file
        # running at once flipped it in 2 rounds of 12.
        client = make_mock_client(_responses(), delays={"judge": 0.5})
        state, _, _ = await _run(client, budget=0.95, reserve=0.05)
        watchdog = state.watchdog
        assert state.status == "blocked" and state.stop_reason is None
        assert watchdog.rule == "not_started"
        assert (watchdog.node, watchdog.tier) == ("review", "judge")
        assert watchdog.pace_seconds >= 0.5
        assert watchdog.available_seconds < watchdog.pace_seconds
        assert client.calls_by_function["judge"] == 1      # validate only
        assert "review" not in state.path
        approved = watchdog.approved
        assert approved["agreed"] is True
        assert (approved["index"], approved["loop"], approved["iteration"]) == (
            0, "build_loop", 1)
        assert approved["gates"] == {"review": "not_reached",
                                     "rework_review": "not_reached"}
        assert approved["latest_differs"] is False and approved["latest"] == "approved"

    async def test_with_time_to_spare_the_same_call_is_made(self):
        """The contrast that makes the count above a measurement: the same
        delays under a budget that holds make all three judge calls."""
        client = make_mock_client(_responses(), delays={"judge": 0.5})
        state, _, _ = await _run(client, budget=5.0, reserve=0.05)
        assert state.status == "completed"
        assert client.calls_by_function["judge"] == 3


class TestTheRunnerPathFiresBeforeItsBackstop:
    """(d) Through run_scenario with the shipped reserve: the watchdog cuts at
    budget less reserve, the terminal lands before the budget, and the
    runner's wait_for never fires."""

    async def test_the_watchdog_fires_a_reserve_before_the_wait_for(self):
        budget = 1.2
        run = await run_scenario(
            _scenario(budget), SPEC,
            lambda: make_mock_client(_responses(), delays={"judge": 3.0}), SETTINGS)
        watchdog = run.watchdog
        assert watchdog["reserve_seconds"] == WATCHDOG_RESERVE_SECONDS
        cut_point = budget - WATCHDOG_RESERVE_SECONDS
        # The timer is granted exactly up to the cut point; anything later is
        # scheduling. Half the reserve bounds it with room on a loaded
        # machine and still leaves the cut a clear margin before the runner.
        assert cut_point - 0.01 <= watchdog["elapsed_seconds"] <= (
            cut_point + WATCHDOG_RESERVE_SECONDS / 2)
        assert watchdog["terminal_seconds"] < budget
        assert run.stop_reason is None
        assert run.seconds < budget


class TestTheAPIPathGetsTheWatchdog:
    """(e) engine/workflow.py: unset is today's behaviour, set arms it."""

    async def test_unset_runs_as_before(self, db_session, monkeypatch):
        from autornd.config import settings
        from autornd.engine.workflow import WorkflowEngine
        from autornd.models.workflow import WorkflowStatus

        def no_timer(*args, **kwargs):
            raise AssertionError("the API path entered the timer with no budget set")

        monkeypatch.setattr(settings, "run_time_budget_seconds", None)
        monkeypatch.setattr(executor_module.asyncio, "timeout", no_timer)
        workflow = await WorkflowEngine(
            make_mock_client(_responses()), db_session).execute(REQUEST)
        assert workflow.status == WorkflowStatus.COMPLETED
        assert workflow.error is None

    async def test_set_arms_it_and_lands_in_the_existing_fields(self, db_session, monkeypatch):
        from autornd.config import settings
        from autornd.engine.workflow import WorkflowEngine
        from autornd.models.workflow import WorkflowStatus

        monkeypatch.setattr(settings, "run_time_budget_seconds", 1.2)
        started = time.perf_counter()
        workflow = await WorkflowEngine(
            make_mock_client(_responses(), delays={"judge": 3.0}),
            db_session).execute(REQUEST)
        assert time.perf_counter() - started < 1.2
        assert workflow.status == WorkflowStatus.BLOCKED
        assert workflow.error.startswith("stopped by the deliberation watchdog")


class TestThePointerNamesTheLastAgreedImplementation:
    """(f) The terminal points at the last implementation the build judges
    agreed on, says which later gates it met, and labels a differing latest
    implementation unjudged."""

    async def test_a_rework_after_agreement_leaves_the_latest_unjudged(self):
        # Build iteration 1: the judges agree (validate green, 0.5 s), review
        # takes 0.5 s and says do not ship, review_clean routes to rework,
        # and implement writes Revision 2. With `pre` the time to reach
        # validate: review starts if 1.4 - pre - 0.5 >= 0.5 (pre up to 0.4 s),
        # and the next judge-tier node then has 0.4 - pre against a 0.5 s
        # pace, so it is not started.
        # That node is validate. domain_review comes first but has no peers to
        # ask on this two-specialist roster and makes no call, so under A1
        # (ARCH-20260930-100) the pre-start rule passes it by and names the
        # node whose call would overrun. Until A1 this test asserted
        # domain_review, the misattribution 095 asked about and 098 run 1
        # showed live. The run ends at the same paid point either way.
        client = make_mock_client(_responses(judge={"ship": False}),
                                  delays={"judge": 0.5})
        _reshape(client, summary_by_call=True)
        state, runner, _ = await _run(client, budget=1.45, reserve=0.05)
        watchdog = state.watchdog
        assert watchdog.rule == "not_started"
        assert (watchdog.node, watchdog.iteration, watchdog.tier) == (
            "validate", 1, "judge")
        assert [s.node_id for s in state.trace][-1] == "consistency"
        approved = watchdog.approved
        assert approved["agreed"] is True
        assert (approved["index"], approved["loop"], approved["iteration"]) == (
            0, "build_loop", 1)
        assert approved["gates"] == {"review": "failed",
                                     "rework_review": "not_reached"}
        assert approved["latest_differs"] is True
        assert approved["latest"] == "unjudged"
        assert state.outputs["implement"].summary.endswith("Revision 2.")
        assert runner.iterations[0]["implement_summary"].endswith("Revision 1.")
        assert "not approved (unjudged)" in state.reason

    async def test_the_094_shape_cut_while_rework_review_is_in_flight(self):
        """094 itself: a rework iteration the build judges agreed on, cut
        while its rework_review was still reading it."""
        async def slow_rereview(function, message):
            # Only the second review-shaped judging (rework_review) is slow.
            if function == "judge" and REVIEW_PROMPT in message:
                slow_rereview.reviews += 1
                if slow_rereview.reviews > 2:      # review has a team of two
                    await asyncio.sleep(5.0)
        slow_rereview.reviews = 0

        client = make_mock_client(_responses(judge={"ship": False}))
        _reshape(client, before=slow_rereview, summary_by_call=True)
        state, runner, _ = await _run(client, budget=1.0, reserve=0.05)
        watchdog = state.watchdog
        assert watchdog.rule == "cancelled"
        assert (watchdog.node, watchdog.iteration) == ("rework_review", 1)
        approved = watchdog.approved
        assert (approved["index"], approved["loop"], approved["iteration"]) == (
            1, "review_rework_loop", 1)
        assert approved["gates"] == {"review": "not_reached",
                                     "rework_review": "cut"}
        assert approved["latest_differs"] is False and approved["latest"] == "approved"
        assert [i["dissenting"] for i in runner.iterations] == [[], []]


def _missing_blocks(unit: dict) -> list[str]:
    """What the D37/D38 blocks lack in a unit record read back from disk.

    Present and explicit: an absent key and a quiet zero are different
    claims (convention 28), so a quiet run must still carry each block.
    """
    missing = [key for key in ("steps", "watchdog", "regrounding",
                               "regrounding_rounds", "assumptions_declared")
               if key not in unit]
    if "regrounding" in unit and "rounds" not in (unit["regrounding"] or {}):
        missing.append("regrounding.rounds")
    if "watchdog" in unit and not isinstance(unit["watchdog"], dict):
        missing.append("watchdog (not a record)")
    return missing


class TestTheRecordIsWrittenToDisk:
    """(g) The serialiser repair found by 094: the unit record read back
    from the file carries steps, watchdog, regrounding, regrounding_rounds
    and assumptions_declared, with zeros when quiet."""

    async def _units(self, tmp_path, runs) -> list[dict]:
        path = tmp_path / "units.jsonl"
        with ResultsLog(path, {"suite": "watchdog"}) as log:
            for run in runs:
                log.record(run, SPEC.name, repetition=1)
        lines = [json.loads(line) for line in path.read_text().splitlines()]
        return [line for line in lines if line["record"] == "unit"]

    async def test_every_block_survives_the_round_trip(self, tmp_path):
        quiet = await run_scenario(_scenario(60), SPEC,
                                   lambda: make_mock_client(_responses()), SETTINGS)
        cut = await run_scenario(
            _scenario(1.2), SPEC,
            lambda: make_mock_client(_responses(), delays={"judge": 3.0}), SETTINGS)
        units = await self._units(tmp_path, [quiet, cut])
        assert len(units) == 2
        for unit in units:
            assert _missing_blocks(unit) == [], unit.keys()
            assert [s["node"] for s in unit["steps"]] == unit["path"]
        q, c = units
        assert q["regrounding_rounds"] == 0 and q["assumptions_declared"] == []
        assert q["regrounding"]["rounds"] == 0
        assert q["watchdog"]["armed"] is True and q["watchdog"]["fired"] is False
        assert q["watchdog"]["slow_calls"] == []
        assert c["watchdog"]["fired"] is True and c["steps"][-1]["cancelled"] is True
        tiers = {s["node"]: s["tier"] for s in q["steps"]}
        assert tiers["validate"] == "judge" and tiers["coverage"] is None

    async def test_a_writer_that_drops_a_block_fails_the_check(self, tmp_path, monkeypatch):
        """The check above can fail: drop one block on the way to disk."""
        original = ResultsLog._write

        def dropping(self, payload):
            payload = {k: v for k, v in payload.items() if k != "regrounding"}
            original(self, payload)

        monkeypatch.setattr(ResultsLog, "_write", dropping)
        run = await run_scenario(_scenario(60), SPEC,
                                 lambda: make_mock_client(_responses()), SETTINGS)
        (unit,) = await self._units(tmp_path, [run])
        assert _missing_blocks(unit) == ["regrounding"]


class TestASlowCallIsFlaggedNotCancelled:
    """Ruling D40: a call is flagged, not cancelled, when it runs past
    SLOW_CALL_MULTIPLE of its OWN node's slowest earlier call in this run.
    Until D40 the comparison was the tier's pace at 1.0, which flagged a
    review for being slower than validate: different work (098: tier-keyed
    ratios 5.733 and 3.030, same-node at most 1.624 and 1.118)."""

    async def test_a_review_slower_than_validate_is_not_flagged(self):
        # This test asserted the opposite until D40 (convention 17).
        async def slow_review(function, message):
            if function == "judge" and REVIEW_PROMPT in message:
                await asyncio.sleep(0.2)
            elif function == "judge" and VALIDATE_PROMPT in message:
                await asyncio.sleep(0.05)

        client = make_mock_client(_responses())
        _reshape(client, before=slow_review)
        state, _, _ = await _run(client)                  # no budget at all
        assert state.status == "completed"
        assert not [f for f in state.watchdog.slow_calls if f["node"] == "review"]

    async def test_a_node_past_twice_its_own_earlier_call_is_flagged(self):
        implements = {"n": 0}

        async def slower_each_time(function, message):
            if IMPLEMENT_PROMPT in message:
                implements["n"] += 1
                await asyncio.sleep(0.02 if implements["n"] == 1 else 0.2)

        responses = _responses(judge={"ship": False})
        responses["escalation"] = {"root_cause_analysis": "x",
                                   "resolution_directive": "y",
                                   "requires_human": True}
        client = make_mock_client(responses)
        _reshape(client, before=slower_each_time)
        state, _, _ = await _run(client)                  # no budget at all
        assert implements["n"] >= 2
        flags = [f for f in state.watchdog.slow_calls if f["node"] == "implement"]
        assert flags, state.watchdog.slow_calls
        assert flags[0]["pace_basis"] == "node"
        assert flags[0]["ratio"] > SLOW_CALL_MULTIPLE
        assert all(f["cancelled"] is False for f in flags)


class TestTheReserveIsMeasured:
    """The reserve constant's comment carries a measurement; this re-takes
    it on every suite run. Cut point to terminal written, and to the
    executor returning, on the real path."""

    async def test_a_cut_takes_a_small_fraction_of_the_reserve(self):
        budget, reserve = 0.4, 0.05
        to_terminal, to_return = [], []
        for _ in range(5):
            client = make_mock_client(_responses(), delays={"judge": 5.0})
            state, _, returned = await _run(client, budget=budget, reserve=reserve)
            assert state.watchdog.rule == "cancelled", state.reason
            cut_point = budget - reserve
            to_terminal.append(state.watchdog.terminal_seconds - cut_point)
            to_return.append(returned - cut_point)
        assert max(to_terminal) < WATCHDOG_RESERVE_SECONDS / 4, to_terminal
        assert max(to_return) < WATCHDOG_RESERVE_SECONDS / 4, to_return
        assert statistics.median(to_return) >= 0

    async def test_cancelling_a_real_http_call_closes_its_connection(self):
        """Command question 1, answered by observation where it can be: the
        real OpenRouterClient against a local socket that never replies.
        The server sees the connection closed once the await is cancelled,
        so cancellation does not merely abandon the wait. A remote provider
        behind TLS is not observable from here; the billing note stands."""
        received, closed = asyncio.Event(), asyncio.Event()

        async def silent(reader, writer):
            try:
                await reader.readuntil(b"\r\n\r\n")
                received.set()
                await reader.read()                 # b"" only once closed
            except asyncio.IncompleteReadError:
                pass                                # closed mid-request
            finally:
                closed.set()
                writer.close()

        server = await asyncio.start_server(silent, "127.0.0.1", 0)
        port = server.sockets[0].getsockname()[1]
        client = OpenRouterClient(api_key="test", base_url=f"http://127.0.0.1:{port}/v1")
        try:
            loop = asyncio.get_running_loop()
            # Half a second, so the cut lands on a request in flight: under
            # load, 0.1 s once cut httpx before the request was fully sent.
            with pytest.raises(TimeoutError):
                async with asyncio.timeout(0.5) as guard:
                    await client.chat("engineering", "system", "user")
            lag = loop.time() - guard.when()
            assert received.is_set(), "the cut landed before the request was sent"
            await asyncio.wait_for(closed.wait(), 1.0)
        finally:
            await client.close()
            server.close()
            await server.wait_closed()
        assert lag < WATCHDOG_RESERVE_SECONDS / 4, lag


class TestANotApprovedArtifactSaysNotApproved:
    """A2 (ARCH-20260930-100): 'dissented' (judged, not agreed) and
    'unjudged' (no judge finished) are both NOT APPROVED. The terminal says
    'not approved' in both, with the finer label beside it."""

    @staticmethod
    def _record(**approved) -> WatchdogRecord:
        return WatchdogRecord(
            armed=True, budget_seconds=60.0, reserve_seconds=0.4, fired=True,
            rule="not_started", node="validate", iteration=2, tier="judge",
            elapsed_seconds=50.0, available_seconds=9.6, pace_seconds=20.0,
            approved={"history": "present", **approved})

    @pytest.mark.parametrize("label", ["dissented", "unjudged"])
    def test_a_differing_latest_reads_not_approved(self, label):
        reason = _watchdog_reason(self._record(
            agreed=True, index=0, loop="build_loop", iteration=1,
            gates={"review": "failed"}, latest_differs=True, latest=label))
        assert f"is not approved ({label})" in reason

    @pytest.mark.parametrize("label", ["dissented", "unjudged"])
    def test_with_nothing_agreed_the_latest_still_reads_not_approved(self, label):
        reason = _watchdog_reason(self._record(
            agreed=False, index=None, loop=None, iteration=None, gates=None,
            latest_differs=None, latest=label))
        assert "no implementation was agreed by the build judges" in reason
        assert f"the latest implementation is not approved ({label})" in reason
