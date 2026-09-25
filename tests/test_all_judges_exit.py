"""The build loop stops when its judges agree, not when one of them says so.

**The exhibit.** Measured 2026-09-14 on the `requires_execution` trace (n=1,
and one is enough for an existence proof): the loop exited satisfied while
`implement.green` was False in the same state. A domain reviewer had flagged a
critical concern and flipped it; validate returned green; `until` read validate.

Reading validate's own evidence afterwards showed which judge was wrong:

    Criterion 2 (exactly 100 and 101 req/s): PASS — Test Case 1 covers
    100 req/s; Test Case 2 corrected to 121 req/s, with 101 req/s explicitly
    noted as not causing rejection.

The criterion demanded a test at 101. Validate marked it PASS while stating in
the same sentence that the test had been changed to 121. The domain reviewer
caught exactly that, and the final review blocked on it. **Two of the three
judges present were right and the exit consulted the third.**

So the fold: green only if every judge the body produced agrees. It is a free
deterministic check, not a convergence mechanism — it does not make the loop
converge faster, it stops it lying about having converged.
"""

from __future__ import annotations

import pytest

from tests.test_graph import BASE, IMPL, _run


@pytest.mark.asyncio
class TestTheLoopContinuesWhileAnyJudgeDissents:
    async def test_validate_green_but_implement_red_keeps_going(self):
        """The regression that names the bug. The old exit shipped this."""
        state, runner = await _run({
            **BASE,
            "implement": {**IMPL, "green": False,
                          "red_cause": "Domain reviewer flagged critical concern"},
            "validate": {"green": True},
            "escalation": {"requires_human": True}})
        assert state.status != "completed", (
            "a red implementation must not ship because validate said green")
        assert runner.ai_calls.count("implement") > 1, "the loop should iterate"

    async def test_coverage_red_but_validate_green_keeps_going(self):
        """The variant never observed live, now structurally covered.

        A free check carries the same weight as a paid one: an implementation
        that never mentions two of its criteria does not ship on a green
        validator.
        """
        state, _ = await _run({
            **BASE,
            "implement": {**IMPL, "summary": "Tidied the logging."},
            "validate": {"green": True},
            "escalation": {"requires_human": True}})
        assert state.outputs["coverage"]["passed"] is False
        assert state.status != "completed"

    async def test_all_judges_green_exits_first_time(self):
        state, runner = await _run({**BASE, "validate": {"green": True}})
        assert state.status == "completed"
        assert runner.ai_calls.count("implement") == 1, "no needless iteration"
        assert state.outputs["judges"]["passed"] is True


class TestTheFoldItself:
    """Unit-level, because the fold is the part that must not be clever."""

    @staticmethod
    def _fold(**judges):
        from autornd.graph.checks import get_check

        return get_check("judges_agree")(**judges)

    def test_all_green_is_green(self):
        from autornd.graph.checks import Result

        assert self._fold(implement=True, validate=True,
                          coverage=Result(True), consistency=Result(True)).passed

    @pytest.mark.parametrize("dissenter", ["implement", "validate"])
    def test_any_boolean_judge_dissenting_is_red(self, dissenter):
        from autornd.graph.checks import Result

        judges = {"implement": True, "validate": True,
                  "coverage": Result(True), "consistency": Result(True)}
        judges[dissenter] = False
        result = self._fold(**judges)
        assert not result.passed
        assert dissenter in result.data["dissenting"]

    @pytest.mark.parametrize("dissenter", ["coverage", "consistency"])
    def test_any_check_judge_dissenting_is_red(self, dissenter):
        from autornd.graph.checks import Result

        judges = {"implement": True, "validate": True,
                  "coverage": Result(True), "consistency": Result(True)}
        judges[dissenter] = Result(False, "missed two criteria")
        result = self._fold(**judges)
        assert not result.passed
        assert dissenter in result.data["dissenting"]

    def test_it_names_every_dissenter_not_just_the_first(self):
        from autornd.graph.checks import Result

        result = self._fold(implement=False, validate=True,
                            coverage=Result(False), consistency=Result(True))
        assert result.data["dissenting"] == ["coverage", "implement"]

    def test_no_judges_is_not_agreement(self):
        """Folding an empty set to True would make a loop with no judges exit
        immediately and call it convergence."""
        assert not self._fold().passed

    def test_a_missing_judge_is_loud_rather_than_assumed_green(self):
        """`resolve_args` raises on a path that does not resolve, so a judge
        removed from a body without updating the fold fails the run rather than
        silently abstaining. Pinned here because the failure mode it prevents —
        a judge quietly dropping out of the fold — is the bug this file exists
        for, one level up."""
        from autornd.graph.conditions import ConditionError
        from autornd.graph.executor import ExecutionState, resolve_args
        from autornd.graph.spec import parse

        spec = parse({"name": "w", "nodes": [
            {"id": "judges", "kind": "check", "check": "judges_agree",
             "args": {"implement": "implement.green"}}]})
        with pytest.raises(ConditionError):
            resolve_args(spec.get("judges"), ExecutionState(request="r"))


class TestEmptySeat:
    """Ruling D9: an abstaining judge passes the fold but is not recorded as
    agreeing. The fold's DECISION is unchanged; only the RECORD distinguishes
    silence from assent."""

    @staticmethod
    async def _enriched_fold(coverage_abstained):
        """Run _run_check on a judges_agree node where coverage has the given
        abstention list. Returns the judges output dict."""
        from autornd.graph.checks import get_check
        from autornd.graph.executor import ExecutionState, GraphExecutor, resolve_args
        from autornd.graph.spec import Node

        node = Node(id="judges", kind="check", check="judges_agree",
                    args={"implement": "implement.green",
                          "validate": "validate.green",
                          "coverage": "coverage.passed",
                          "consistency": "consistency.passed"})
        state = ExecutionState(request="test")
        state.outputs["implement"] = {"green": True}
        state.outputs["validate"] = {"green": True}
        state.outputs["coverage"] = {
            "passed": True, "detail": "",
            "abstained": coverage_abstained,
            "missed": [], "coverage": {}, "shapes": {}, "addressed": 0,
            "extractions": {},
        }
        state.outputs["consistency"] = {"passed": True, "detail": ""}

        class FakeRunner:
            async def run_check(self, node, state):
                return get_check(node.check)(**resolve_args(node, state))

        executor = GraphExecutor.__new__(GraphExecutor)
        executor.runner = FakeRunner()
        await executor._run_check(node, state)
        return state.outputs["judges"]

    @pytest.mark.asyncio
    async def test_empty_seat_passes_but_is_not_unanimous(self):
        """Coverage abstains on one criterion — the fold passes (abstention
        is not dissent) but the record says 'empty seat, not unanimous'."""
        judges = await self._enriched_fold(
            [{"criterion": "c1", "shape": "form", "reason": "r"}])
        assert judges["passed"] is True
        assert judges["abstained_judges"] == {"coverage": 1}
        assert judges["abstention_count"] == 1
        assert "empty seat" in judges["detail"]
        assert "all " not in judges["detail"]

    @pytest.mark.asyncio
    async def test_no_abstention_is_unanimous(self):
        """Zero abstentions → the fold reports unanimity normally."""
        judges = await self._enriched_fold([])
        assert judges["passed"] is True
        assert judges.get("abstained_judges") is None
        assert "all " in judges["detail"] and "agree" in judges["detail"]

    @pytest.mark.asyncio
    async def test_regression_unanimous_excludes_empty_seat(self):
        """Invariant: 'all judges agree' and 'abstained_judges' never coexist.
        Without the D9 enrichment this would silently pass."""
        judges = await self._enriched_fold(
            [{"criterion": "c1", "shape": "form", "reason": "r"},
             {"criterion": "c2", "shape": "form", "reason": "r2"}])
        if judges.get("abstained_judges"):
            assert "all " not in judges.get("detail", ""), (
                "a panel with an empty seat must not be recorded as unanimous")


class TestEveryShippedLoopFoldsItsOwnJudges:
    """A loop folds the judges its body actually produces — not a list written
    here that drifts when a body changes."""

    @pytest.mark.parametrize("workflow,loop,until,fold,expected", [
        ("engineering-rnd", "build_loop", "judges.passed == true", "judges",
         {"implement", "validate", "coverage", "consistency"}),
        # The two loops that can ship re-review first, so they fold review in
        # as well — work ships when everyone who looked at it agrees.
        ("engineering-rnd", "review_rework_loop", "review_fold.passed == true",
         "review_fold", {"build", "review"}),
        ("engineering-rnd", "recovery_loop", "review_fold.passed == true",
         "review_fold", {"build", "review"}),
        ("lean", "build_loop", "judges.passed == true", "judges",
         {"implement", "validate", "coverage"}),
    ])
    def test_the_fold_matches_the_body(self, workflow, loop, until, fold, expected):
        from autornd.graph.spec import load

        spec = load(f"workflows/{workflow}.yaml")
        assert spec.get(loop).until == until
        assert set(spec.get(fold).args) == expected
        assert fold in spec.get(loop).body
