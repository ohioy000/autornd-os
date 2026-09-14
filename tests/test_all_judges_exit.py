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


class TestEveryShippedLoopFoldsItsOwnJudges:
    """A loop folds the judges its body actually produces — not a list written
    here that drifts when a body changes."""

    @pytest.mark.parametrize("workflow,loop,expected", [
        ("engineering-rnd", "build_loop",
         {"implement", "validate", "coverage", "consistency"}),
        ("engineering-rnd", "recovery_loop",
         {"implement", "validate", "coverage", "consistency"}),
        ("lean", "build_loop", {"implement", "validate", "coverage"}),
    ])
    def test_the_fold_matches_the_body(self, workflow, loop, expected):
        from autornd.graph.spec import load

        spec = load(f"workflows/{workflow}.yaml")
        assert spec.get(loop).until == "judges.passed == true"
        assert set(spec.get("judges").args) == expected
        assert "judges" in spec.get(loop).body
