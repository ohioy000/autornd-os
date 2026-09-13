"""Tests for the workflow graph — spec, conditions, and deterministic checks.

None of these make a model call. That is the point of the graph: the shape of a
workflow, and everything decidable about it, is testable for free.
"""

from __future__ import annotations

import pytest

from autornd.graph.checks import get_check, registry
from autornd.graph.conditions import ConditionError, evaluate, resolve_path
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
