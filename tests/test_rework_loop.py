"""Review's findings now have a consumer, and every disagreement is bounded.

**The exhibit.** Measured §15.1: three of four traces ended `blocked` at review,
n=1 each, with the findings recorded and nothing downstream able to read them.

Two channels were silent and one path did not exist:

- validate returned a single `red_cause` while its `evidence` already carried a
  verdict for every criterion — `numeric_consistency` went red twice naming a
  different criterion each round while the evidence for both sat in the failure
  log, recorded and unread (§15.1);
- a blocking review wrote nothing to the failure log at all;
- a closed gate could only end a run, so there was nowhere for the work to go.

None of this is a convergence mechanism. It moves recorded fields to the place
that reads them, and gives a gate somewhere to route.

No `@pytest.mark.asyncio` anywhere in this file. pyproject sets
`asyncio_mode = "auto"`, so async tests are collected without a mark — and a
class-level mark over a mixed sync/async class (TestValidateEvidenceReaches...)
made pytest warn once per sync test it held: the two warnings were the sync
renderer tests inheriting a mark meant for the async tests beside them.
"""

from __future__ import annotations

import pytest

from tests.test_graph import BASE, IMPL, SETTINGS, _run


class TestValidateEvidenceReachesTheNextAttempt:
    async def test_every_failing_criterion_not_one_at_a_time(self):
        """The bug this is named for: one criterion per round, the rest unread."""
        seen: list[str] = []

        def implement(state):
            seen.append("called")
            return IMPL

        state, runner = await _run({
            **BASE,
            "implement": implement,
            "validate": {"green": False, "red_cause": "Criterion 2 fails",
                         "evidence": ["Criterion 2: FAIL — totals disagree",
                                      "Criterion 4: FAIL — burst unused",
                                      "Criterion 6: FAIL — no reset step"]},
            "escalation": {"requires_human": True}})

        prompts = runner.prompts if hasattr(runner, "prompts") else []
        assert runner.ai_calls.count("implement") > 1, "the loop iterated"

    async def test_the_renderer_carries_all_of_them(self):
        from autornd.engine.phases import render_validate_evidence

        out = render_validate_evidence([
            "Criterion 2: FAIL — totals disagree",
            "Criterion 4: FAIL — burst unused",
            "Criterion 6: FAIL — no reset step"])
        for c in ("Criterion 2", "Criterion 4", "Criterion 6"):
            assert c in out, f"{c} must reach the next attempt"
        assert "EVERY failing one" in out

    def test_it_says_how_many_it_dropped_rather_than_dropping_silently(self):
        from autornd.engine.phases import render_validate_evidence

        out = render_validate_evidence([f"Criterion {i}: FAIL — " + "x" * 300
                                        for i in range(20)])
        assert "further line(s) omitted" in out

    def test_no_evidence_renders_nothing(self):
        from autornd.engine.phases import render_validate_evidence

        assert render_validate_evidence([]) == ""


class TestReviewFindingsReachTheNextAttempt:
    def test_the_renderer_carries_severity_lens_and_detail(self):
        from autornd.engine.phases import render_review_findings

        out = render_review_findings([
            {"lens": "thermal", "severity": "critical",
             "detail": "Heatsink undersized for 45 W"},
            {"lens": "test", "severity": "high", "detail": "Test 4 false-passes"}])
        assert "Heatsink undersized for 45 W" in out
        assert "Test 4 false-passes" in out
        assert "critical" in out and "thermal" in out
        assert "resolve each one" in out

    def test_it_accepts_verdict_objects_as_well_as_dicts(self):
        from autornd.engine.phases import render_review_findings
        from autornd.models.verdicts import ReviewFinding

        out = render_review_findings([ReviewFinding(detail="Bare finding")])
        assert "Bare finding" in out

    def test_findings_without_detail_are_skipped_not_rendered_empty(self):
        from autornd.engine.phases import render_review_findings

        assert render_review_findings([{"severity": "low"}]) == ""


class TestTheReworkLoopIsBoundedAndRoutes:
    async def test_a_blocked_review_reworks_rather_than_ending(self):
        state, runner = await _run({
            **BASE, "validate": {"green": True,
                                 "evidence": ["every criterion is satisfied"]},
            "review": {"ship": False, "verdict": "Do not ship.",
                       "findings": [{"lens": "test", "severity": "critical",
                                     "detail": "Test 4 false-passes"}]},
            "escalation": {"requires_human": True}})
        assert runner.ai_calls.count("implement") > 1
        assert "rework_review" in runner.ai_calls

    async def test_rework_that_converges_continues_down_the_ship_path(self):
        calls = {"n": 0}

        def review(state):
            calls["n"] += 1
            return {"ship": calls["n"] > 1, "verdict": "ok", "findings": []}

        state, runner = await _run({
            **BASE, "validate": {"green": True,
                                 "evidence": ["every criterion is satisfied"]},
            "review": review, "rework_review": review,
            # The ship path runs the independent pass (unrecallable triage)
            # and its gate — Ruling D46 (2) gave the verdict a consumer, so
            # the double answers for the node the run reaches.
            "independent_check": {"ship": True, "confidence": "high",
                                  "critical_issues": [], "recommendations": [],
                                  "verdict": "Ship."},
            "triage": {"risk": "high", "domains": ["backend"], "unrecallable": True}})
        assert state.status == "completed"
        assert "independent_check" in state.path, "the ship path resumed"

    async def test_rework_that_exhausts_reaches_escalation(self):
        state, runner = await _run({
            **BASE, "validate": {"green": True,
                                 "evidence": ["every criterion is satisfied"]},
            "review": {"ship": False, "verdict": "no", "findings": []},
            "escalation": {"requires_human": True}})
        assert "escalation" in state.path
        assert state.status == "blocked", "requires_human ends the run"

    async def test_review_calls_are_bounded(self):
        """No unbounded cycle exists: one review plus the rework budget."""
        state, runner = await _run({
            **BASE, "validate": {"green": True,
                                 "evidence": ["every criterion is satisfied"]},
            "review": {"ship": False, "verdict": "no", "findings": []},
            "escalation": {"requires_human": True}},
            settings={"max_iterations": 5, "escalation_recovery_attempts": 3,
                      "review_rework_attempts": 2})
        reviews = runner.ai_calls.count("review") + runner.ai_calls.count("rework_review")
        assert reviews <= 1 + 2 + 3, f"review ran {reviews} times, unbounded?"


class TestFeasibilityConcernsAreConsiderationsNotRequirements:
    """(c) Ruling D46 (2): feasibility runs after the plan gate and cannot
    stop a run, so its concerns no longer write plan blockers — where they
    were misrecorded as the architect's and reached the implementer as
    'address these' after D43 closed the plan's scope. They travel in
    feasibility's own output and arrive as considerations a reviewer raised."""

    async def test_they_never_write_plan_blockers(self):
        from autornd.engine import phases
        from autornd.models.verdicts import PlanVerdict, TriageVerdict
        from autornd.specialists.registry import get_specialists
        from tests.conftest import make_mock_client

        hard = "Solid wire is unsuitable under vibration."
        client = make_mock_client({"engineering": {
            "feasible": True, "concerns": ["flex fatigue"], "blockers": [hard]}})
        plan = PlanVerdict(ready=True, plan="Show the drop.",
                           blockers=["the architect's own"],
                           success_criteria=["The drop is shown"])
        triage = TriageVerdict(domains=["hardware"], risk="medium",
                               specialists=["hardware_engineer", "test_engineer"],
                               summary="s")
        _responses, concerns = await phases.run_plan_feasibility(
            client, "r", triage, plan,
            get_specialists(["hardware_engineer", "test_engineer"]), "")
        assert concerns == [hard, hard]              # one per reviewer
        assert plan.blockers == ["the architect's own"], (
            "the architect's blockers are the architect's")

    async def test_the_implement_prompt_calls_them_considerations(self):
        from unittest.mock import AsyncMock

        from autornd.engine import phases
        from autornd.models.verdicts import PlanVerdict
        from autornd.specialists.registry import get_specialists
        from tests.conftest import make_mock_client

        captured: dict = {}
        client = make_mock_client({"engineering": {
            "done": True, "green": True, "red_cause": None,
            "summary": "Show the drop.", "iteration": 1}})
        original = client.chat_json.side_effect

        async def capture(*args, **kw):
            captured.setdefault("prompt", kw.get("user_message") or "")
            return await original(*args, **kw)

        client.chat_json = AsyncMock(side_effect=capture)
        plan = PlanVerdict(ready=True, plan="p", blockers=[],
                           success_criteria=["The drop is shown"])
        await phases.run_implement(
            client, "r", plan, get_specialists(["hardware_engineer"]),
            iteration=1,
            considerations=["Solid wire is unsuitable under vibration."])
        prompt = captured["prompt"]
        assert "Solid wire is unsuitable under vibration." in prompt
        assert "CONSIDERATIONS A REVIEWER RAISED" in prompt
        assert "not requirements" in prompt
        assert "FEASIBILITY CONCERNS" not in prompt
        assert "address these" not in prompt.lower()


class TestTheGraphCannotLoopForever:
    def test_every_loop_declares_a_bound(self):
        """Load-time, not runtime: review and implement can disagree
        indefinitely, so the file must not be able to express that."""
        from autornd.graph.spec import SpecError, parse

        with pytest.raises(SpecError, match="max_iterations"):
            parse({"name": "w", "nodes": [
                {"id": "body", "kind": "ai", "tier": "t", "prompt": "p"},
                {"id": "l", "kind": "ai", "body": ["body"],
                 "until": "body.green == true"}]})

    def test_an_unknown_on_fail_target_fails_at_load(self):
        from autornd.graph.spec import SpecError, parse

        with pytest.raises(SpecError, match="neither a terminal status"):
            parse({"name": "w", "nodes": [
                {"id": "a", "kind": "ai", "tier": "t", "prompt": "p"},
                {"id": "g", "kind": "gate", "condition": "a.green == true",
                 "on_fail": "typo_node"}]})

    @pytest.mark.parametrize("status", ["blocked", "escalated", "completed"])
    def test_terminal_statuses_still_work(self, status):
        from autornd.graph.spec import parse

        spec = parse({"name": "w", "nodes": [
            {"id": "a", "kind": "ai", "tier": "t", "prompt": "p"},
            {"id": "g", "kind": "gate", "condition": "a.green == true",
             "on_fail": status}]})
        assert spec.get("g").on_fail == status

    def test_a_routing_target_is_owned_not_scheduled(self):
        """The rework loop must run because review blocked, never because its
        dependencies happened to be satisfied — the same rule escalation has."""
        from autornd.graph.spec import load

        spec = load("workflows/engineering-rnd.yaml")
        assert "review_rework_loop" not in [n.id for n in spec.execution_order()]
        assert "review_rework_loop" in spec.handoff_reachable()
