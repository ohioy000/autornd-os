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
                 "until": "body.green == true", "max_iterations": 2,
                 "on_exhausted": "escalated"}]})

    def test_cannot_both_hand_off_and_end(self):
        with pytest.raises(SpecError, match="hand off or end"):
            parse({"name": "w", "nodes": [
                _ai("body"), _ai("next"),
                {"id": "l", "kind": "ai", "body": ["body"],
                 "until": "body.green == true", "max_iterations": 2,
                 "on_exhausted": "next", "on_exhausted_status": "escalated"}]})

    def test_loop_bodies_are_not_scheduled_at_top_level(self):
        spec = parse({"name": "w", "nodes": [
            _ai("impl"), _ai("val"),
            {"id": "loop", "kind": "ai", "body": ["impl", "val"],
             "until": "val.green == true", "max_iterations": 2}]})
        assert [n.id for n in spec.execution_order()] == ["loop"]

    def test_handoff_targets_are_not_scheduled_at_top_level(self):
        """Escalation must run because a loop gave up, never because its
        dependencies happened to be satisfied."""
        spec = parse({"name": "w", "nodes": [
            _ai("impl"),
            _ai("escalate"),
            _ai("recover", depends_on=["escalate"]),
            {"id": "loop", "kind": "ai", "body": ["impl"],
             "until": "impl.green == true", "max_iterations": 2,
             "on_exhausted": "escalate"}]})
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
        # D37: plan runs inside regrounding_loop (a loop owns its body, so
        # plan/feasibility no longer sit on the top-level schedule); the
        # rest of the pipeline order is unchanged.
        assert [n.id for n in spec.execution_order()] == [
            "triage", "context", "regrounding_loop", "feasibility",
            "plan_ready", "verify_grounding", "build_loop", "review", "review_clean",
            # Ruling D46 (2): the independent verdict's gate follows the
            # check that produces it — the verdict finally has a consumer.
            "independent_check", "independent_verdict",
        ]

    def test_the_independent_pass_is_conditional_and_last(self):
        """It exists only for work that cannot be recalled, and it must see the
        review it is meant to be independent of — so it runs after it, and it
        must never run unconditionally, since the premium tier costs the most."""
        spec = load("workflows/engineering-rnd.yaml")
        node = spec.get("independent_check")
        assert node.when == "triage.unrecallable"
        # Not "premium": that key is dropped from FUNCTION_MODELS when unset and
        # the lookup fell back to the engineering model, so the independent pass
        # would silently have been the model it was checking.
        assert node.tier == "independent"
        # It depends on the gate, not the raw review: there is no point paying
        # for a second opinion on work the first review already blocked.
        assert node.depends_on == ["review_clean"]

    def test_free_nodes_run_before_the_paid_validator(self):
        """The cheap checks exist to avoid a model call, so they must not be
        scheduled after the model call they are meant to pre-empt."""
        spec = load("workflows/engineering-rnd.yaml")
        body = spec.get("build_loop").body
        assert body.index("coverage") < body.index("validate")
        assert body.index("consistency") < body.index("validate")

    def test_the_block_gate_sits_right_after_implement(self):
        """B13's refusal check must fire before any paid judge sees the work:
        the measured failure was six iterations of fabrication against an
        impossible criterion. The ROUTING gate must be in build_loop's body
        only — inside the escalation sub-graph it would re-enter it. The check
        itself runs in all three; the other two route nowhere, they terminate
        (`blocked_terminal`, pinned in tests/test_blocked_on.py)."""
        spec = load("workflows/engineering-rnd.yaml")
        body = spec.get("build_loop").body
        assert body.index("blocked_check") == body.index("implement") + 1
        assert body.index("blocked_gate") == body.index("blocked_check") + 1
        for loop in ("recovery_loop", "review_rework_loop"):
            assert "blocked_gate" not in spec.get(loop).body, loop

    def test_every_check_named_is_registered(self):
        """Three checks are adapter-owned rather than registry entries — they
        need the client or the runner's state, which a pure registry function
        has no access to. All three are special-cased in PhaseRunner.run_check
        beside each other, so all three are excluded here by name."""
        spec = load("workflows/engineering-rnd.yaml")
        for node in spec.nodes:
            if node.kind is NodeKind.CHECK and node.check not in (
                    "build_context", "verify_grounding", "reground_context_lookup"):
                assert node.check in registry, f"{node.id} names unknown check"


class TestAnUncheckedFailureStillDissents:
    """(a) Ruling D48 (1): a check that compared nothing never turns a fail
    into a pass. An unchecked PASS is not a dissent; an unchecked FAILURE is,
    exactly as it was before D46 — 111's constraint [4] made every unchecked
    check non-blocking, which let a failing check that compared nothing vote
    the work through."""

    def test_a_failing_unchecked_judge_dissents_and_a_passing_one_does_not(self):
        r = get_check("judges_agree")(
            implement=True, validate=True,
            coverage={"passed": False, "checked": False},
            consistency={"passed": True, "checked": False},
        )
        assert not r.passed
        assert r.data["dissenting"] == ["coverage"]
        assert r.data["unchecked"] == ["consistency", "coverage"]
        assert "coverage is red" in r.detail
        assert "unchecked: consistency, coverage" in r.detail, (
            "the detail names both lists")

    async def test_a_run_whose_coverage_fails_unchecked_does_not_converge(self):
        # No criteria: criteria_addressed compares nothing (checked false)
        # and fails — and a failing unchecked judge must still hold the loop.
        plan = {**PLAN, "success_criteria": []}
        state, runner = await _run({
            **BASE, "plan": plan,
            "validate": {"green": True},
            "escalation": {"requires_human": True}})
        assert runner.ai_calls.count("implement") > 1, "the loop iterated"
        judges = state.outputs["judges"]
        assert "coverage" in judges["dissenting"]
        assert "coverage" in judges["unchecked"]
        assert state.status == "blocked", state.reason


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
        r = get_check("criteria_addressed")([], "anything")
        assert not r.passed
        # Ruling D46 (3): with no criteria there is nothing to check against —
        # unchanged verdict, recorded as NOT CHECKED so the fold does not loop
        # the work for a comparison that could not happen.
        assert r.checked is False


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

    def test_no_shared_unit_passes_but_says_it_compared_nothing(self):
        """Ruling D46 (3): a check that compared nothing says so. It passes
        exactly as before — reporting absence as conflict would be a different
        check — but it is recorded as NOT CHECKED, and the fold treats it as
        non-blocking."""
        r = get_check("numbers_consistent")("no figures at all",
                                            "nothing numeric here either")
        assert r.passed
        assert r.checked is False
        assert "compared nothing" in r.detail


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

SETTINGS = {"max_iterations": 5, "escalation_recovery_attempts": 3,
            "review_rework_attempts": 2}

PLAN = {
    "ready": True,
                     "blockers": [],
    "plan": "Cap backoff at 60s, add jitter.",
    "blockers": [],
    "success_criteria": [
        "Reconnect loop applies exponential backoff capped at 60s",
        "Jitter is applied to every retry attempt",
    ],
}
IMPL = {
    "done": True, "green": True, "iteration": 1,
    # The real verdict always carries this — it defaults to [] — so the double
    # must too: the block check resolves implement.blocked_on, and a fixture
    # missing a defaulted field is a fixture that does not simulate the verdict
    # it stands in for (convention 22). Its first absence took 36 tests down
    # with one ConditionError.
    "blocked_on": [],
    "summary": ("Applied exponential backoff to the reconnect loop capped at 60s "
                "with jitter on every retry attempt."),
}
BASE = {
    "triage": {"risk": "medium", "domains": ["backend"], "unrecallable": False},
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
        if out is None and node.prompt:
            # The rework loop re-runs review through a node of its own, because
            # a loop owns its body and `review` has to stay on the main
            # schedule. Same prompt, so a script that answers `review` answers
            # `rework_review` too unless a test scripts it separately.
            out = self.verdicts.get(node.prompt)
        got = out(state) if callable(out) else (out or {})
        if isinstance(got, dict):
            got = dict(got)
        state.outputs[node.id] = got
        self._record_regrounding(node, got, state)
        return got

    def _record_regrounding(self, node, got, state):
        """The adapter's assumption/first-pass record, mirrored for doubles.

        Production records these in PhaseRunner._phase_plan; the scripted
        double answers plan from the canned map, so it keeps the same
        counters here — the unit-record builder reads them off whichever
        runner drove the run. Only plan verdicts; only blockers named by a
        plan that went on to proceed (ready) become assumptions with basis.
        """
        if node.id != "plan" or not isinstance(got, dict):
            return
        from autornd.graph.checks import _normalize_question
        blockers = [str(b) for b in (got.get("blockers") or [])]
        if state.iteration <= 1 and not getattr(self, "regrounding_first_pass_blockers", None):
            self.regrounding_first_pass_blockers = list(blockers)
        if got.get("ready") and blockers:
            asked = set()
            ctx = state.outputs.get("context")
            if isinstance(ctx, dict):
                asked = {_normalize_question(q) for q in (ctx.get("asked") or []) if q}
            lookup = state.outputs.get("reground_lookup") or {}
            found = lookup.get("found", 0) if isinstance(lookup, dict) else 0
            if not hasattr(self, "assumptions_declared"):
                self.assumptions_declared: list[dict] = []
            for b in blockers:
                self.assumptions_declared.append({
                    "blocker": b,
                    "basis": (f"asked: {str(_normalize_question(b) in asked).lower()}; "
                              f"lookup returned {found} finding(s) this round"),
                })

    def _regrounding_block(self, state):
        """The typed record, read off this runner and the run's own state."""
        outputs = state.outputs or {}
        lookup = outputs.get("reground_lookup") or {}
        plan = outputs.get("plan") or {}
        second = list(plan.get("blockers") or []) if isinstance(plan, dict) else []
        if isinstance(lookup, dict):
            asked_n, found_n = lookup.get("asked", 0), lookup.get("found", 0)
        else:
            asked_n = getattr(lookup, "asked", 0) or 0
            found_n = getattr(lookup, "found", 0) or 0
        rounds = 1 if lookup else 0
        novel = list(getattr(self, "regrounding_novel", None) or [])
        return {
            "rounds": rounds,
            "blockers_first_pass": list(getattr(self, "regrounding_first_pass_blockers", None) or []),
            "novel": novel,
            "asked": int(asked_n),
            "findings": int(found_n),
            "blockers_second_pass": list(second),
            "assumptions": list(getattr(self, "assumptions_declared", None) or []),
        }

    async def run_check(self, node, state):
        self.check_calls.append(node.id)
        if node.check == "build_context":
            # The adapter's context node seeds the asked history the novelty
            # check compares against; the double carries the same output keys
            # (asked, rounds) with the honest zero, so resolves off them.
            # The executor writes the check output into state AFTER this
            # returns, so seed here rather than assigning outputs directly.
            from autornd.graph.checks import Result as _R
            return _R(True, "context assembled", asked=[], rounds=0)
        if node.check == "reground_context_lookup":
            # The paid lookup bills (convention 9) and mutates the context
            # output in place, exactly like the adapter: pass two's check
            # reads rounds == 1 off it and exits — once is ruled.
            from autornd.graph.executor import resolve_args as _ra
            novel = [b for b in list(_ra(node, state).get("blockers") or []) if b]
            ctx = state.outputs.get("context")
            if isinstance(ctx, dict):
                ctx["asked"] = list(ctx.get("asked") or []) + list(novel)
                ctx["rounds"] = 1
            if not hasattr(self, "regrounding_novel"):
                self.regrounding_novel: list[str] = []
            self.regrounding_novel = list(novel)
            from autornd.graph.checks import Result as _R
            return _R(True, "re-grounding round 1", rounds=1,
                      asked=len(novel), found=len(novel), novel=list(novel))
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
        # D37: plan runs inside regrounding_loop (ready first pass exits on
        # the check), then feasibility on the final plan, then the rest of
        # the pipeline unchanged.
        assert state.path == [
            "triage", "context", "plan", "reground_context",
            "feasibility", "plan_ready",
            "verify_grounding",
            "implement", "blocked_check", "blocked_gate",
            "domain_review", "coverage", "consistency",
            "validate", "judges", "review", "review_clean",
        ]
        assert len(runner.ai_calls) == 7

    async def test_blocked_plan_surfaces_the_blocker(self):
        # D37 legitimately changes the PATH (one lookup plus one re-plan at
        # medium risk); the STATUS assertion is unchanged — still blocked.
        state, _ = await _run({**BASE, "plan": {
            "ready": False, "plan": "x", "blockers": ["missing datasheet"],
            "success_criteria": []}})
        assert state.status == "blocked"
        assert "missing datasheet" in state.reason
        assert "implement" not in state.path

    async def test_a_negative_review_sends_the_work_back(self):
        """`review.ship` reached one place only — the `shipped` column of
        episodic memory — while the run reported `completed`. Then it gated, and
        three traces in four died there with the findings unread. Now it routes:
        the work goes back through the loop, and only exhausted rework escalates.
        """
        state, runner = await _run({**BASE, "validate": {"green": True},
                                    "review": {"ship": False},
                                    "escalation": {"requires_human": True}})
        assert state.status != "completed"
        assert runner.ai_calls.count("implement") > 1, "the work was reworked"
        assert "rework_review" in runner.ai_calls, "and re-reviewed"

    async def test_a_blocked_review_says_what_was_found(self):
        """A gate on a Pydantic verdict used to produce no detail at all: the
        detail lookup only handled dicts, so the findings sat unread."""
        state, _ = await _run({**BASE, "validate": {"green": True}, "review": {
            "ship": False,
            "findings": [{"lens": "thermal", "severity": "high",
                          "detail": "Heatsink undersized for 45 W"}],
            "verdict": "Do not ship."},
            "escalation": {"requires_human": True}})
        # The gate routes now rather than ending the run, so its detail is on
        # its own record instead of the terminal reason — which is where the
        # rework loop reads it from too.
        assert state.outputs["review_clean"]["passed"] is False
        assert "Heatsink undersized for 45 W" in state.outputs["review_clean"]["reason"]
        assert "Review found blocking issues" in state.outputs["review_clean"]["reason"]

    async def test_a_do_not_ship_ends_the_run_blocked_with_its_findings(self):
        """Ruling D46 (2): the independent check's verdict had no consumer —
        the run could complete after the one reviewer that sees unrecallable
        work said not to ship. It blocks now, findings and all, and it is a
        terminal, not a route: a do-not-ship is not an iteration."""
        state, runner = await _run({
            **BASE, "validate": {"green": True},
            "triage": {"risk": "high", "domains": ["firmware"],
                       "specialists": ["firmware_engineer"],
                       "unrecallable": True},
            "review": {"ship": True},
            "independent_check": {
                "ship": False, "vetoed": True, "confidence": "high",
                "critical_issues": ["Resistor R7 value contradicts the schematic"],
                "recommendations": [], "verdict": "Do not ship."}})
        assert state.status == "blocked"
        assert "Independent check: do not ship" in state.reason
        assert "Resistor R7 value contradicts the schematic" in state.reason
        assert "build_loop" not in runner.ai_calls, (
            "the gate must not route a do-not-ship into a loop")

    async def test_an_implementation_marked_incomplete_cannot_complete(self):
        """Ruling D49 (2): the completed terminal means finished.
        The implement verdict's typed `done` field says the work
        is not done, so the run ends blocked naming it — even
        though every gate downstream passed. Reproduced: the
        executor ended every run no node stopped as completed,
        never reading `done` at all."""
        state, runner = await _run({
            **BASE, "validate": {"green": True},
            "implement": {"done": False, "green": True, "iteration": 1,
                          "blocked_on": [],
                          "summary": ("Applied exponential backoff to the "
                                      "reconnect loop capped at 60s with "
                                      "jitter on every retry attempt. The "
                                      "operator guide is not written.")}})
        assert state.status == "blocked"
        assert "done: false" in state.reason
        assert "operator guide is not written" in state.reason
        assert runner.ai_calls.count("implement") == 1, (
            "the loop converged — this is the terminal's refusal, "
            "not a rework")

    async def test_a_skipped_independent_pass_is_not_an_approval(self):
        """Ruling D49 (3): unavailable verification is distinct
        from passing verification. The skip record — what
        PhaseRunner writes when no model can serve the pass
        (test_routing.py drives that path directly) — carries no
        `ship` at all: neither an approval nor a veto. The gate
        routes on `vetoed`, so a skip continues the run, but the
        record says a check did not happen, and anything that
        reads it can tell a skip from a pass. Reproduced: the
        skip record claimed `ship: true`, so a check that never
        ran read exactly like one that passed."""
        state, runner = await _run({
            **BASE, "validate": {"green": True},
            "triage": {"risk": "high", "domains": ["firmware"],
                       "specialists": ["firmware_engineer"],
                       "unrecallable": True},
            "review": {"ship": True},
            "independent_check": {
                "skipped": True, "vetoed": False,
                "reason": ("no model available for an independent "
                           "pass that is not the engineering model "
                           "itself")}})
        assert state.status == "completed"
        assert "independent_check" in state.path
        record = state.outputs["independent_check"]
        assert record["skipped"] is True
        assert record["vetoed"] is False
        assert "ship" not in record, "a skip must not claim an approval"

    async def test_the_gate_costs_nothing(self):
        """It is a gate, not a call. Free checks exist to avoid paid ones."""
        _, clean = await _run({**BASE, "validate": {"green": True},
                               "review": {"ship": True}})
        _, blocked = await _run({**BASE, "validate": {"green": True},
                                 "review": {"ship": False},
                                 "escalation": {"requires_human": True}})
        assert len(clean.ai_calls) == 7, "a clean run pays the gate nothing"
        assert len(blocked.ai_calls) > 7, (
            "a blocked one pays for rework, which is the point — the gate "
            "itself is still free")

    async def test_the_independent_pass_runs_when_work_cannot_be_recalled(self):
        """The wiring proof. Every other assertion is blind to a conditional
        node: a workflow whose `when` never fires produces the same verdicts as
        one without the node at all.

        Live runs kept terminating before review for model-behaviour reasons on
        several tiers, so this is where the wiring is actually established —
        deterministically, and for nothing.
        """
        state, runner = await _run({
            **BASE,
            "validate": {"green": True},
            "triage": {"risk": "high", "domains": ["firmware"],
                       "specialists": ["firmware_engineer"],
                       "unrecallable": True},
            "review": {"ship": True},
            "independent_check": {"ship": True, "vetoed": False, "confidence": "high",
                                  "critical_issues": [],
                                  "verdict": "Independently sound."},
        })
        assert state.status == "completed"
        assert "independent_check" in state.path
        assert "independent_check" in runner.ai_calls
        assert state.outputs["independent_check"]["ship"] is True

    async def test_recallable_work_does_not_pay_for_it(self):
        """The other half: the node must stay dormant by default, or every
        workflow buys the most expensive tier in the system."""
        state, runner = await _run({**BASE, "validate": {"green": True}})
        assert state.status == "completed"
        assert "independent_check" not in state.path
        assert "independent_check" not in runner.ai_calls

    async def test_a_blocked_review_skips_the_independent_pass(self):
        """No point paying for a second opinion on work the first review
        already stopped."""
        state, _ = await _run({
            **BASE,
            "validate": {"green": True},
            "triage": {"risk": "high", "domains": ["backend"],
                       "unrecallable": True},
            "review": {"ship": False},
            "escalation": {"requires_human": True}})
        assert state.status == "blocked"
        assert "independent_check" not in state.path

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
        """A skipped node does not end the run — the loop still governs that.

        This used to assert `completed` on a red implementation with a green
        validate, which is the exit-on-one-judge bug written down as an
        expectation. The loop now folds every judge, so the same inputs keep
        iterating and finish escalated; what this test is actually about — the
        `when` clause skipping domain review — is unchanged.
        """
        state, runner = await _run({
            **BASE,
            "implement": {**IMPL, "green": False},
            "validate": {"green": True},
            "escalation": {"requires_human": True}})
        assert "domain_review" not in runner.ai_calls    # when: implement.green
        assert state.status == "blocked", "a red implementation must not ship"
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
        """A free check now carries the same weight as the paid judges.

        It used to record the drift and let the run finish anyway, because the
        exit read validate alone. The fold means a red `coverage` keeps the loop
        going: an implementation that never mentions two of the criteria does
        not ship because the validator happened to say green.
        """
        state, _ = await _run({
            **BASE,
            "implement": {**IMPL, "summary": "Tidied the logging."},
            "validate": {"green": True},
            "escalation": {"requires_human": True}})
        assert state.outputs["coverage"]["passed"] is False
        assert len(state.outputs["coverage"]["missed"]) == 2
        assert state.status != "completed", "drift must not ship on one judge"

    async def test_budget_reads_from_settings(self):
        state, runner = await _run(
            {**BASE, "validate": {"green": False},
             "escalation": {"requires_human": True}},
            settings={"max_iterations": 2, "escalation_recovery_attempts": 1,
                      "review_rework_attempts": 1})
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


class TestUnitAliasing:
    """Calibration against realistic text found that "60s" and "5 second" were
    treated as different units, so a plan reversed by its implementation passed
    the consistency check. A check that cannot fire is worse than no check: it
    reports confidence it has not earned."""

    PLAN = "Apply exponential backoff to the reconnect loop, capped at 60s, with jitter."

    @pytest.mark.parametrize("written,symbol", [
        ("60 seconds", "60s"), ("5 volts", "5V"), ("20 milliamps", "20mA"),
        ("3 minutes", "3min"), ("915 megahertz", "915 mhz"),
    ])
    def test_written_and_symbolic_forms_agree(self, written, symbol):
        from autornd.graph.checks import _canonical_unit
        import re
        from autornd.graph.checks import _NUMBER

        units = [_canonical_unit(u) for _, u in _NUMBER.findall(f"{written} {symbol}")]
        assert len(set(u for u in units if u)) == 1, units

    def test_a_reversed_plan_is_caught(self):
        r = get_check("numbers_consistent")(
            self.PLAN,
            "Exponential backoff was removed in favour of a fixed 5 second retry interval.")
        assert not r.passed

    def test_the_same_value_written_out_is_not_a_conflict(self):
        r = get_check("numbers_consistent")(self.PLAN, "Backoff capped at 60 seconds.")
        assert r.passed

    def test_plurals_of_non_units_still_compare(self):
        """'3 retries' and '3 retry' are the same claim."""
        from autornd.graph.checks import _canonical_unit
        assert _canonical_unit("retries") == _canonical_unit("retry")


class TestCriteriaAddressedCalibration:
    """The threshold was a guess. Measured against realistic implementation text,
    addressed criteria score 71-100% and unaddressed ones 0-33%, so 50%
    discriminates — including the case that matters most, text that names every
    topic while committing to nothing."""

    CRITERIA = [
        "Reconnect loop applies exponential backoff capped at 60s with jitter",
        "Client re-subscribes to all topics after a successful reconnect",
        "Each reconnect attempt emits a metric with the attempt number",
    ]

    def test_faithful_work_passes(self):
        r = get_check("criteria_addressed")(self.CRITERIA, (
            "Added exponential backoff to the reconnect loop, capped at 60s with "
            "jitter. After a successful reconnect the client re-subscribes to all "
            "topics. Each attempt emits a metric carrying the attempt number."))
        assert r.passed

    def test_topic_mentioning_waffle_is_rejected(self):
        """The failure mode most worth catching: on-topic, commits to nothing."""
        r = get_check("criteria_addressed")(self.CRITERIA, (
            "Reworked the reconnection handling. The loop now backs off between "
            "attempts, topics are handled on reconnect, and attempts are observable."))
        assert not r.passed
        assert r.data["addressed"] == 0

    def test_partial_work_names_the_gap(self):
        r = get_check("criteria_addressed")(self.CRITERIA,
            "Added exponential backoff with jitter to the reconnect loop, capped at 60s.")
        assert not r.passed
        assert r.data["addressed"] == 1

    def test_term_overlap_cannot_see_negation(self):
        """A known, documented limit: an implementation that says it *removed*
        the backoff scores highly on a criterion requiring backoff. That gap is
        numbers_consistent's job, not this check's."""
        r = get_check("criteria_addressed")(
            [self.CRITERIA[0]],
            "Exponential backoff and jitter were removed from the reconnect loop, "
            "which was capped at 60s before.")
        assert r.passed      # documents the limit rather than pretending otherwise
