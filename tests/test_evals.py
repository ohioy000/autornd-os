"""Tests for the eval harness.

These exercise the harness, not the models: a mocked run tells you whether
scoring, bounding and reporting work. Whether AutoRnD actually triages a
packaging machine as high risk is a question only a live run answers, which is
what evals/scenarios and `python -m autornd.evals.cli` are for.
"""

from __future__ import annotations

import asyncio
import json
from unittest.mock import AsyncMock

import pytest

from autornd.evals.assertions import RunOutcome, score
from autornd.evals.runner import (
    DEFAULT_CALL_CEILING, EvalReport, run_repeated, run_scenario, run_suite,
)
from autornd.evals.scenario import Scenario, ScenarioError, load_scenarios, parse
from autornd.graph.executor import ExecutionState
from autornd.graph.spec import load
from autornd.models.verdicts import RiskLevel, TriageVerdict
from autornd.routing.openrouter import ModelResponse, OpenRouterClient

SETTINGS = {"max_iterations": 5, "escalation_recovery_attempts": 3}


def triage_state(domains=("backend",), risk="medium",
                 specialists=("backend_engineer", "test_engineer"), **outputs):
    state = ExecutionState(request="r")
    state.outputs["triage"] = TriageVerdict(
        domains=list(domains), risk=RiskLevel(risk),
        specialists=list(specialists), summary="s")
    state.outputs.update(outputs)
    state.status = outputs.pop("_status", "completed")
    return state


def outcome(state, calls=8):
    return RunOutcome(state=state, calls=calls)


class TestScenarioParsing:
    def test_minimal_scenario(self):
        s = parse({"id": "a", "request": "do a thing"})
        assert s.id == "a" and s.expect == {}

    @pytest.mark.parametrize("missing", ["id", "request"])
    def test_required_fields(self, missing):
        raw = {"id": "a", "request": "r"}
        del raw[missing]
        with pytest.raises(ScenarioError, match=missing):
            parse(raw)

    def test_unknown_expectation_is_a_typo_not_a_feature(self):
        """Silently ignoring an unknown key means a scenario that asserts
        nothing while looking like it asserts something."""
        with pytest.raises(ScenarioError, match="unknown expectation"):
            parse({"id": "a", "request": "r", "expect": {"risk_levl": "high"}})

    def test_bad_risk_value_rejected(self):
        with pytest.raises(ScenarioError, match="expected one of"):
            parse({"id": "a", "request": "r", "expect": {"risk": "urgent"}})

    @pytest.mark.parametrize("value", [0, -1, "two"])
    def test_budgets_must_be_positive_integers(self, value):
        with pytest.raises(ScenarioError, match="positive integer"):
            parse({"id": "a", "request": "r", "expect": {"max_calls": value}})

    def test_shipped_scenarios_all_load(self):
        scenarios = load_scenarios("evals/scenarios")
        assert len(scenarios) >= 4
        assert all(s.request for s in scenarios)

    def test_duplicate_ids_rejected(self, tmp_path):
        for name in ("a.yaml", "b.yaml"):
            (tmp_path / name).write_text("id: same\nrequest: r\n")
        with pytest.raises(ScenarioError, match="duplicate"):
            load_scenarios(tmp_path)


class TestAssertions:
    def _one(self, expect, state, calls=8):
        results = score(Scenario(id="s", request="r", expect=expect), outcome(state, calls))
        assert len(results) == 1
        return results[0]

    def test_domains_exact(self):
        assert self._one({"domains": ["backend"]}, triage_state()).passed
        assert not self._one({"domains": ["hardware"]}, triage_state()).passed

    def test_domains_include_allows_extras(self):
        state = triage_state(domains=("backend", "frontend"))
        assert self._one({"domains_include": ["backend"]}, state).passed
        assert not self._one({"domains_include": ["hardware"]}, state).passed

    def test_risk_exact(self):
        assert self._one({"risk": "medium"}, triage_state()).passed
        assert not self._one({"risk": "high"}, triage_state()).passed

    def test_risk_at_least_accepts_over_classification(self):
        """Over-classifying risk costs money; under-classifying costs safety."""
        assert self._one({"risk_at_least": "medium"},
                         triage_state(risk="critical")).passed
        assert not self._one({"risk_at_least": "high"},
                             triage_state(risk="medium")).passed

    def test_specialists_include_reports_what_is_missing(self):
        result = self._one({"specialists_include": ["hardware_engineer"]}, triage_state())
        assert not result.passed
        assert "hardware_engineer" in result.detail

    def test_specialists_exclude(self):
        assert self._one({"specialists_exclude": ["hardware_engineer"]},
                         triage_state()).passed
        assert not self._one({"specialists_exclude": ["backend_engineer"]},
                             triage_state()).passed

    def test_status(self):
        state = triage_state()
        state.status = "blocked"
        state.reason = "Plan not ready"
        result = self._one({"status": "completed"}, state)
        assert not result.passed
        assert "Plan not ready" in result.detail

    def test_converge_within_counts_iterations(self):
        converged = triage_state(build_loop={"converged": True, "iterations": 2})
        assert self._one({"converge_within": 2}, converged).passed
        assert not self._one({"converge_within": 1}, converged).passed

    def test_converge_within_fails_when_it_never_converged(self):
        result = self._one({"converge_within": 5},
                           triage_state(build_loop={"converged": False, "iterations": 5}))
        assert not result.passed
        assert "did not converge" in result.detail

    def test_max_calls_is_a_cost_regression_guard(self):
        assert self._one({"max_calls": 10}, triage_state(), calls=8).passed
        assert not self._one({"max_calls": 6}, triage_state(), calls=8).passed

    def test_criteria_addressed_reads_the_free_check(self):
        state = triage_state(coverage={"passed": False, "detail": "2 not addressed"})
        result = self._one({"criteria_addressed": True}, state)
        assert not result.passed
        assert "2 not addressed" in result.detail

    def test_only_declared_expectations_are_scored(self):
        """A scenario that pins one thing must not fail on nine others."""
        results = score(Scenario(id="s", request="r", expect={"risk": "medium"}),
                        outcome(triage_state()))
        assert [r.name for r in results] == ["risk"]

    def test_a_failed_run_scores_as_one_failure(self):
        results = score(
            Scenario(id="s", request="r", expect={"risk": "medium"}),
            RunOutcome(state=ExecutionState(request="r"), calls=0, error="boom"))
        assert len(results) == 1 and not results[0].passed
        assert "boom" in results[0].detail


# ── runner ────────────────────────────────────────────────────────────────

def make_client(reply, log=None, delay=0.0):
    client = OpenRouterClient(api_key="test")

    async def chat_json(function, system_prompt, user_message, **kw):
        if delay:
            await asyncio.sleep(delay)
        if log is not None:
            log.append(function)
        data = reply(user_message)
        return data, ModelResponse(content=json.dumps(data), model="mock",
                                   prompt_tokens=1, completion_tokens=1, cost=0.001)

    client.chat_json = AsyncMock(side_effect=chat_json)
    client.close = AsyncMock()
    return client


def scripted(risk="medium", green=True):
    def reply(message: str) -> dict:
        m = message.lower()
        if "classify this engineering request" in m:
            return {"domains": ["backend"], "risk": risk,
                    "specialists": ["backend_engineer", "test_engineer"], "summary": "s"}
        if "create an implementation plan" in m:
            return {"ready": True, "plan": "Cap backoff at 60s.", "blockers": [],
                    "cost_estimate": None,
                    "success_criteria": ["Backoff is capped at 60s with jitter"]}
        if "review this implementation plan" in m:
            return {"feasible": True, "concerns": [], "blockers": []}
        if "produce the implementation for the following plan" in m:
            return {"done": True, "green": True, "red_cause": None, "iteration": 1,
                    "summary": "Backoff is capped at 60s with jitter applied."}
        if "review this implementation from your domain perspective" in m:
            return {"concerns": [], "critical": False}
        if "validate this implementation" in m:
            return {"green": green, "red_cause": None if green else "red", "evidence": []}
        return {"ship": True, "findings": [], "verdict": "Ship."}
    return reply


@pytest.mark.asyncio
class TestRunner:
    async def test_a_passing_scenario_scores_clean(self):
        scenario = parse({"id": "s", "request": "Add retry", "expect": {
            "domains_include": ["backend"], "risk": "medium",
            "status": "completed", "converge_within": 1, "max_calls": 14}})
        run = await run_scenario(scenario, load("workflows/engineering-rnd.yaml"),
                                 lambda: make_client(scripted()), SETTINGS)
        assert run.passed, [str(f) for f in run.failures]
        assert run.calls > 0

    async def test_failures_name_the_actual_value(self):
        scenario = parse({"id": "s", "request": "Add retry",
                          "expect": {"risk": "critical"}})
        run = await run_scenario(scenario, load("workflows/engineering-rnd.yaml"),
                                 lambda: make_client(scripted()), SETTINGS)
        assert not run.passed
        assert run.failures[0].got == "medium"

    async def test_call_ceiling_stops_a_runaway(self):
        """The lesson of a live sweep that ran forty minutes before anyone
        stopped it: a bound that only limits iterations does not limit spend."""
        scenario = parse({"id": "s", "request": "Add retry",
                          "expect": {"max_calls": 3}})
        run = await run_scenario(scenario, load("workflows/engineering-rnd.yaml"),
                                 lambda: make_client(scripted(green=False)), SETTINGS)
        assert not run.passed
        assert run.calls <= 5          # ceiling plus the headroom call
        assert "ceiling" in (run.error or "")

    async def test_timeout_is_recorded_not_raised(self):
        scenario = parse({"id": "s", "request": "Add retry", "expect": {"risk": "medium"}})
        run = await run_scenario(
            scenario, load("workflows/engineering-rnd.yaml"),
            lambda: make_client(scripted(), delay=0.05), SETTINGS, timeout=0.01)
        assert not run.passed
        assert "timed out" in run.error

    async def test_a_crashing_run_is_a_result_not_an_exception(self):
        def explode(_message):
            raise RuntimeError("provider down")

        scenario = parse({"id": "s", "request": "r", "expect": {"risk": "medium"}})
        run = await run_scenario(scenario, load("workflows/engineering-rnd.yaml"),
                                 lambda: make_client(explode), SETTINGS)
        assert not run.passed
        assert "provider down" in run.error

    async def test_suite_reports_totals(self):
        scenarios = [
            parse({"id": "ok", "request": "r", "expect": {"risk": "medium"}}),
            parse({"id": "nope", "request": "r", "expect": {"risk": "critical"}}),
        ]
        report = await run_suite(scenarios, load("workflows/engineering-rnd.yaml"),
                                 lambda: make_client(scripted()), SETTINGS)
        assert report.total == 2 and report.passed == 1
        rendered = report.render()
        assert "1/2 applicable scenarios passed" in rendered
        assert "nope" in rendered

    async def test_the_same_suite_can_compare_two_workflows(self):
        """The point of the graph and the point of the evals, together: which
        shape is cheaper, scored against the same expectations."""
        scenarios = [parse({"id": "s", "request": "Add retry",
                            "expect": {"status": "completed"}})]
        full = await run_suite(scenarios, load("workflows/engineering-rnd.yaml"),
                               lambda: make_client(scripted()), SETTINGS)
        lean = await run_suite(scenarios, load("workflows/lean.yaml"),
                               lambda: make_client(scripted()), SETTINGS)
        assert full.passed == lean.passed == 1
        assert lean.calls < full.calls


@pytest.mark.asyncio
class TestRepetitions:
    """Models are stochastic. The same triage request passed on one live run and
    failed on the next, so a single result cannot be the unit of measurement."""

    async def test_a_consistent_scenario_passes_every_repetition(self):
        scenario = parse({"id": "s", "request": "r", "expect": {"risk": "medium"}})
        report = await run_repeated(
            [scenario], load("workflows/engineering-rnd.yaml"),
            lambda: make_client(scripted()), SETTINGS, repeat=3)
        result = report.results[0]
        assert result.passed and result.passes == 3 and result.rate == 1.0

    async def test_a_flaky_assertion_is_named_and_counted(self):
        """A scenario that passes twice out of three is not a pass."""
        state = {"n": 0}

        def wobbly(message):
            if "classify this engineering request" in message.lower():
                state["n"] += 1
                risk = "medium" if state["n"] % 2 else "high"
                return {"domains": ["backend"], "risk": risk,
                        "specialists": ["backend_engineer"], "summary": "s"}
            return scripted()(message)

        scenario = parse({"id": "s", "request": "r", "expect": {"risk": "medium"}})
        report = await run_repeated(
            [scenario], load("workflows/triage-only.yaml"),
            lambda: make_client(wobbly), SETTINGS, repeat=4)
        result = report.results[0]
        assert not result.passed
        assert 0 < result.rate < 1
        assert result.flaky.get("risk", 0) >= 1
        assert "risk" in report.render()

    async def test_an_inapplicable_scenario_is_not_repeated(self):
        """Shape does not change between runs, so do not pay to rediscover it."""
        scenario = parse({"id": "s", "request": "r",
                          "expect": {"converge_within": 1}})
        report = await run_repeated(
            [scenario], load("workflows/triage-only.yaml"),
            lambda: make_client(scripted()), SETTINGS, repeat=5)
        result = report.results[0]
        assert result.skipped and len(result.runs) == 1
        assert report.applicable == 0


class TestScenarioTimeout:
    def test_a_scenario_may_state_its_own_timeout(self):
        s = parse({"id": "a", "request": "r", "timeout": 300})
        assert s.timeout == 300

    @pytest.mark.parametrize("value", [0, -5, "soon"])
    def test_a_bad_timeout_is_rejected(self, value):
        with pytest.raises(ScenarioError, match="positive number"):
            parse({"id": "a", "request": "r", "timeout": value})


@pytest.mark.asyncio
class TestTimeoutPrecedence:
    async def test_the_scenario_timeout_wins_over_the_suite_default(self):
        """A slow-by-design scenario must not be failed by a global default, and
        a global default must not let a genuine hang run for ten minutes."""
        scenario = parse({"id": "slow", "request": "r", "timeout": 0.01,
                          "expect": {"risk": "medium"}})
        run = await run_scenario(
            scenario, load("workflows/triage-only.yaml"),
            lambda: make_client(scripted(), delay=0.2), SETTINGS, timeout=60)
        assert "timed out after 0s" in run.error

    async def test_the_suite_default_applies_when_a_scenario_is_silent(self):
        scenario = parse({"id": "quiet", "request": "r", "expect": {"risk": "medium"}})
        run = await run_scenario(
            scenario, load("workflows/triage-only.yaml"),
            lambda: make_client(scripted(), delay=0.2), SETTINGS, timeout=0.01)
        assert "timed out" in run.error
