"""Tests for the workflow graph — spec, conditions, and deterministic checks.

None of these make a model call. That is the point of the graph: the shape of a
workflow, and everything decidable about it, is testable for free.
"""

from __future__ import annotations

import pytest

from autornd.graph.checks import get_check, registry
from autornd.graph.conditions import ConditionError, evaluate, resolve_path
from autornd.graph.executor import ExecutionState
from autornd.graph.spec import NodeKind, SpecError, load, parse


def _ai(node_id, **kw):
    base = {"id": node_id, "kind": "ai", "tier": "engineering", "prompt": "p"}
    base.update(kw)
    return base


class TestConditions:
    SCOPE = {
        "plan": {"ready": True, "criteria": ["a", "b"], "cost": 42.5},
        "triage": {"risk": "high"},
        "validate": {"green": False, "attempts": 3},
    }

    @pytest.mark.parametrize("expr,expected", [
        ("plan.ready", True),
        ("not plan.ready", False),
        ("validate.green", False),
        ("not validate.green", True),
        ("validate.green == true", False),
        ("validate.green != true", True),
        ("triage.risk == 'high'", True),
        ('triage.risk == "low"', False),
        ("triage.risk in ['high', 'critical']", True),
        ("triage.risk in ['low']", False),
        ("validate.attempts >= 3", True),
        ("validate.attempts > 3", False),
        ("plan.cost <= 42.5", True),
        ("plan.criteria != []", True),
    ])
    def test_evaluates(self, expr, expected):
        assert evaluate(expr, self.SCOPE) is expected

    def test_missing_path_names_what_is_available(self):
        with pytest.raises(ConditionError, match="not available"):
            evaluate("plan.nonexistent == true", self.SCOPE)

    def test_unparseable_condition_explains_the_shape(self):
        with pytest.raises(ConditionError, match="Expected"):
            evaluate("plan.ready ~~ 2", self.SCOPE)

    def test_empty_condition_rejected(self):
        with pytest.raises(ConditionError):
            evaluate("   ", self.SCOPE)

    def test_incomparable_types_are_reported(self):
        with pytest.raises(ConditionError, match="incompatible types"):
            evaluate("triage.risk > 3", self.SCOPE)

    def test_no_code_execution(self):
        """A workflow file is configuration. It must not be able to run code."""
        for attack in ["__import__('os').system('x') == 1",
                       "plan.__class__ == 1",
                       "(1,2) == 1"]:
            with pytest.raises(ConditionError):
                evaluate(attack, self.SCOPE)

    def test_resolves_objects_as_well_as_dicts(self):
        class Verdict:
            green = True

        assert resolve_path("v.green", {"v": Verdict()}) is True


class TestSpec:
    def test_parses_a_minimal_workflow(self):
        spec = parse({"name": "w", "nodes": [_ai("a", schema="TriageVerdict")]})
        assert spec.name == "w"
        assert spec.get("a").kind is NodeKind.AI

    def test_ai_node_needs_tier_and_prompt(self):
        with pytest.raises(SpecError, match="prompt"):
            parse({"name": "w", "nodes": [{"id": "a", "kind": "ai", "tier": "t"}]})

    def test_check_node_needs_a_check_name(self):
        with pytest.raises(SpecError, match="check"):
            parse({"name": "w", "nodes": [{"id": "a", "kind": "check"}]})

    def test_gate_node_needs_a_condition(self):
        with pytest.raises(SpecError, match="condition"):
            parse({"name": "w", "nodes": [{"id": "a", "kind": "gate"}]})

    def test_loop_needs_an_until(self):
        with pytest.raises(SpecError, match="until"):
            parse({"name": "w", "nodes": [
                _ai("body"), {"id": "l", "kind": "ai", "body": ["body"]}]})

    def test_unknown_dependency_rejected(self):
        with pytest.raises(SpecError, match="unknown node"):
            parse({"name": "w", "nodes": [_ai("a", depends_on=["ghost"])]})

    def test_cycle_rejected_at_load_time(self):
        with pytest.raises(SpecError, match="cycle"):
            parse({"name": "w", "nodes": [
                _ai("a", depends_on=["b"]), _ai("b", depends_on=["a"])]})

    def test_duplicate_ids_rejected(self):
        with pytest.raises(SpecError, match="duplicate"):
            parse({"name": "w", "nodes": [_ai("a"), _ai("a")]})

    def test_status_in_on_exhausted_is_caught(self):
        """Naming a terminal status where a node belongs is an easy slip."""
        with pytest.raises(SpecError, match="on_exhausted_status"):
            parse({"name": "w", "nodes": [
                _ai("body"),
                {"id": "l", "kind": "ai", "body": ["body"],
                 "until": "body.green == true", "on_exhausted": "escalated"}]})

    def test_cannot_both_hand_off_and_end(self):
        with pytest.raises(SpecError, match="hand off or end"):
            parse({"name": "w", "nodes": [
                _ai("body"), _ai("next"),
                {"id": "l", "kind": "ai", "body": ["body"],
                 "until": "body.green == true",
                 "on_exhausted": "next", "on_exhausted_status": "escalated"}]})

    def test_loop_bodies_are_not_scheduled_at_top_level(self):
        spec = parse({"name": "w", "nodes": [
            _ai("impl"), _ai("val"),
            {"id": "loop", "kind": "ai", "body": ["impl", "val"],
             "until": "val.green == true"}]})
        assert [n.id for n in spec.execution_order()] == ["loop"]

    def test_handoff_targets_are_not_scheduled_at_top_level(self):
        """Escalation must run because a loop gave up, never because its
        dependencies happened to be satisfied."""
        spec = parse({"name": "w", "nodes": [
            _ai("impl"),
            _ai("escalate"),
            _ai("recover", depends_on=["escalate"]),
            {"id": "loop", "kind": "ai", "body": ["impl"],
             "until": "impl.green == true", "on_exhausted": "escalate"}]})
        assert [n.id for n in spec.execution_order()] == ["loop"]
        assert spec.handoff_reachable() == {"impl", "escalate", "recover"}


class TestShippedWorkflow:
    """The bundled workflow must stay loadable and must keep describing the
    pipeline the engine actually runs."""

    def test_loads(self):
        spec = load("workflows/engineering-rnd.yaml")
        assert spec.name == "engineering-rnd"

    def test_top_level_order_is_the_documented_pipeline(self):
        spec = load("workflows/engineering-rnd.yaml")
        assert [n.id for n in spec.execution_order()] == [
            "triage", "context", "plan", "feasibility",
            "plan_ready", "build_loop", "review",
        ]

    def test_free_nodes_run_before_the_paid_validator(self):
        """The cheap checks exist to avoid a model call, so they must not be
        scheduled after the model call they are meant to pre-empt."""
        spec = load("workflows/engineering-rnd.yaml")
        body = spec.get("build_loop").body
        assert body.index("coverage") < body.index("validate")
        assert body.index("consistency") < body.index("validate")

    def test_every_check_named_is_registered(self):
        spec = load("workflows/engineering-rnd.yaml")
        for node in spec.nodes:
            if node.kind is NodeKind.CHECK and node.check != "build_context":
                assert node.check in registry, f"{node.id} names unknown check"


class TestCriteriaAddressed:
    CRITERIA = [
        "Reconnect loop applies exponential backoff capped at 60s",
        "Jitter is applied to every retry attempt",
    ]

    def test_on_plan_implementation_passes(self):
        text = ("Added exponential backoff to the reconnect loop, capped at 60s, "
                "with jitter applied on every retry attempt.")
        result = get_check("criteria_addressed")(self.CRITERIA, text)
        assert result.passed
        assert result.data["missed"] == []

    def test_drifted_implementation_names_what_is_missing(self):
        text = "Refactored the connection handler and tidied the logging."
        result = get_check("criteria_addressed")(self.CRITERIA, text)
        assert not result.passed
        assert len(result.data["missed"]) == 2
        assert "not visibly addressed" in result.detail

    def test_partial_coverage_reports_only_the_gap(self):
        text = "Added exponential backoff to the reconnect loop, capped at 60s."
        result = get_check("criteria_addressed")(self.CRITERIA, text)
        assert not result.passed
        assert result.data["addressed"] == 1

    def test_no_criteria_is_a_failure_not_a_pass(self):
        """An empty criteria list must never read as 'everything passed'."""
        assert not get_check("criteria_addressed")([], "anything").passed


class TestNumbersConsistent:
    def test_agreeing_values_pass(self):
        r = get_check("numbers_consistent")("cap backoff at 60s, 3 retries",
                                            "sets max_interval to 60s with 3 retries")
        assert r.passed

    def test_contradicting_values_are_caught(self):
        r = get_check("numbers_consistent")("cap backoff at 60s",
                                            "sets max_interval to 600s")
        assert not r.passed
        assert "60" in r.detail and "600" in r.detail

    def test_decimal_and_integer_forms_are_the_same_number(self):
        r = get_check("numbers_consistent")("cap at 60s", "sets 60.0s")
        assert r.passed

    def test_value_absent_from_the_implementation_is_not_a_conflict(self):
        r = get_check("numbers_consistent")("cap at 60s, use 4 workers",
                                            "sets max_interval to 60s")
        assert r.passed


class TestTotalsReconcile:
    def test_components_summing_to_the_total_pass(self):
        r = get_check("totals_reconcile")("Parts: $12.50, $20.00, $14.70. Total: $47.20")
        assert r.passed and r.data["checked"]

    def test_mismatched_total_is_caught(self):
        r = get_check("totals_reconcile")("Parts: $12.50, $20.00, $10.00. Total: $47.20")
        assert not r.passed
        assert r.data["claimed"] == 47.20

    def test_no_total_present_is_not_a_failure(self):
        r = get_check("totals_reconcile")("Some prose with $5.00 in it")
        assert r.passed and not r.data["checked"]


# ── executor ──────────────────────────────────────────────────────────────

from autornd.graph.checks import Result, registry
from autornd.graph.executor import GraphExecutor, resolve_args

SETTINGS = {"max_iterations": 5, "escalation_recovery_attempts": 3}

PLAN = {
    "ready": True,
    "plan": "Cap backoff at 60s, add jitter.",
    "success_criteria": [
        "Reconnect loop applies exponential backoff capped at 60s",
        "Jitter is applied to every retry attempt",
    ],
}
IMPL = {
    "done": True, "green": True, "iteration": 1,
    "summary": ("Applied exponential backoff to the reconnect loop capped at 60s "
                "with jitter on every retry attempt."),
}
BASE = {
    "triage": {"risk": "medium", "domains": ["backend"]},
    "context": {}, "plan": PLAN, "feasibility": {"feasible": True},
    "implement": IMPL, "domain_review": {"critical": False},
    "review": {"ship": True},
}


class ScriptedRunner:
    """Returns canned verdicts and records what it was asked for."""

    def __init__(self, verdicts):
        self.verdicts = verdicts
        self.ai_calls: list[str] = []
        self.check_calls: list[str] = []

    async def run_ai(self, node, state):
        self.ai_calls.append(node.id)
        out = self.verdicts.get(node.id)
        return out(state) if callable(out) else (out or {})

    async def run_check(self, node, state):
        self.check_calls.append(node.id)
        if node.check not in registry:      # infrastructure step, runner-owned
            return Result(True, "context assembled")
        return get_check(node.check)(**resolve_args(node, state))


async def _run(verdicts, settings=None):
    spec = load("workflows/engineering-rnd.yaml")
    runner = ScriptedRunner(verdicts)
    state = await GraphExecutor(spec, runner, settings or SETTINGS).run("Add retry")
    return state, runner


@pytest.mark.asyncio
class TestExecutorReproducesThePipeline:
    """The graph must behave exactly like the sequence it replaced, including
    the expensive paths — otherwise it is not a baseline to measure against."""

    async def test_happy_path_matches_the_measured_shape(self):
        state, runner = await _run({**BASE, "validate": {"green": True}})
        assert state.status == "completed"
        assert state.path == [
            "triage", "context", "plan", "feasibility", "plan_ready",
            "implement", "domain_review", "coverage", "consistency",
            "validate", "review",
        ]
        assert len(runner.ai_calls) == 7

    async def test_blocked_plan_surfaces_the_blocker(self):
        state, _ = await _run({**BASE, "plan": {
            "ready": False, "plan": "x", "blockers": ["missing datasheet"],
            "success_criteria": []}})
        assert state.status == "blocked"
        assert "missing datasheet" in state.reason
        assert "implement" not in state.path

    async def test_loop_repeats_until_green(self):
        seen = {"n": 0}

        def flaky(_state):
            seen["n"] += 1
            return {"green": seen["n"] >= 3}

        state, runner = await _run({**BASE, "validate": flaky})
        assert state.status == "completed"
        assert runner.ai_calls.count("implement") == 3
        assert state.outputs["build_loop"] == {"converged": True, "iterations": 3}

    async def test_exhausted_loop_hands_off_to_escalation(self):
        state, runner = await _run({
            **BASE, "validate": {"green": False},
            "escalation": {"requires_human": False, "root_cause_analysis": "wrong topic"}})
        assert state.status == "escalated"
        assert "escalation" in state.path
        assert runner.ai_calls.count("implement") == 5 + 3   # budget + recovery

    async def test_escalation_requiring_a_human_blocks_with_the_cause(self):
        state, _ = await _run({
            **BASE, "validate": {"green": False},
            "escalation": {"requires_human": True,
                           "root_cause_analysis": "needs bench access"}})
        assert state.status == "blocked"
        assert "needs bench access" in state.reason
        assert "recovery_loop" not in state.path

    async def test_escalation_never_runs_on_a_healthy_workflow(self):
        """It is reachable only by handoff — never because its dependencies
        happen to be satisfied."""
        state, runner = await _run({**BASE, "validate": {"green": True}})
        assert "escalation" not in runner.ai_calls


@pytest.mark.asyncio
class TestExecutorMechanics:
    async def test_when_skips_a_node_without_ending_the_run(self):
        state, runner = await _run({
            **BASE,
            "implement": {**IMPL, "green": False},
            "validate": {"green": True}})
        assert "domain_review" not in runner.ai_calls    # when: implement.green
        assert state.status == "completed"
        skipped = [s for s in state.trace if s.skipped]
        assert any(s.node_id == "domain_review" for s in skipped)

    async def test_free_checks_run_before_the_paid_validator(self):
        state, runner = await _run({**BASE, "validate": {"green": True}})
        assert state.path.index("coverage") < state.path.index("validate")
        assert state.path.index("consistency") < state.path.index("validate")

    async def test_check_output_is_visible_to_later_conditions(self):
        state, _ = await _run({**BASE, "validate": {"green": True}})
        assert state.outputs["coverage"]["passed"] is True
        assert state.outputs["coverage"]["addressed"] == 2

    async def test_drifted_implementation_is_caught_by_a_free_check(self):
        """The check cannot fail the run on its own here, but it records the
        drift for the validator and for anyone reading the trace."""
        state, _ = await _run({
            **BASE,
            "implement": {**IMPL, "summary": "Tidied the logging."},
            "validate": {"green": True}})
        assert state.outputs["coverage"]["passed"] is False
        assert len(state.outputs["coverage"]["missed"]) == 2

    async def test_budget_reads_from_settings(self):
        state, runner = await _run(
            {**BASE, "validate": {"green": False},
             "escalation": {"requires_human": True}},
            settings={"max_iterations": 2, "escalation_recovery_attempts": 1})
        assert runner.ai_calls.count("implement") == 2

    async def test_unknown_setting_for_a_budget_is_loud(self):
        with pytest.raises(ConditionError, match="not available"):
            await _run({**BASE, "validate": {"green": False}}, settings={})

    async def test_trace_records_iteration_numbers(self):
        seen = {"n": 0}

        def flaky(_state):
            seen["n"] += 1
            return {"green": seen["n"] >= 2}

        state, _ = await _run({**BASE, "validate": flaky})
        implements = [s for s in state.trace if s.node_id == "implement"]
        assert [s.iteration for s in implements] == [1, 2]


class TestResolveArgs:
    def test_paths_resolve_and_literals_pass_through(self):
        from autornd.graph.spec import Node, NodeKind

        node = Node(id="c", kind=NodeKind.CHECK, check="criteria_addressed",
                    args={"criteria": "plan.success_criteria",
                          "text": "implement.summary", "threshold": 0.4})
        state = ExecutionState(request="r", outputs={
            "plan": {"success_criteria": ["a"]}, "implement": {"summary": "s"}})
        assert resolve_args(node, state) == {
            "criteria": ["a"], "text": "s", "threshold": 0.4}

    def test_a_typo_in_a_path_raises_rather_than_becoming_a_string(self):
        from autornd.graph.spec import Node, NodeKind

        node = Node(id="c", kind=NodeKind.CHECK, check="x",
                    args={"text": "implement.sumary"})
        state = ExecutionState(request="r", outputs={"implement": {"summary": "s"}})
        with pytest.raises(ConditionError):
            resolve_args(node, state)

    def test_quoted_strings_stay_literal(self):
        from autornd.graph.spec import Node, NodeKind

        node = Node(id="c", kind=NodeKind.CHECK, check="x", args={"text": "'hello'"})
        assert resolve_args(node, ExecutionState(request="r"))["text"] == "hello"
