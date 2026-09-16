"""The honest-refusal channel: the implementer may refuse, and the loop listens.

**The ruled design (Blueprint 016 B2/B3).** `blocked_on` is the implementer's
channel for naming success criteria the work cannot satisfy with what is
available. The measured failure it exists for: a low-risk brief whose plan
demanded "a citable source a reader can use to verify the claim" while the risk
gate had already zeroed its lookups — the implementer fabricated sources for six
iterations and died on the cost ceiling rather than refusing. The loop
semantics: a block naming a plan criterion routes to escalation immediately,
without consuming further iterations.

Every test here drives the real check, the real gate wiring or the real
executor end to end — convention 22's shape. The override-once-per-run half of
B4 lives in tests/test_citation_demand.py and is not duplicated here.
"""

from __future__ import annotations

import pytest

from autornd.graph.checks import get_check
from tests.test_graph import BASE, IMPL, SETTINGS, PLAN, _run

unmet = get_check("blocked_on_unmet")


class TestTheCheck:
    """`blocked_on_unmet`: did a blocked entry name a plan criterion?"""

    CRITERIA = [
        "Every claim carries a citable source a reader can use to verify it",
        "Tone matches the house style guide",
    ]

    def test_an_empty_list_is_not_a_block(self):
        assert unmet(blocked_on=[], criteria=self.CRITERIA).passed

    def test_an_index_reference_names_the_criterion(self):
        r = unmet(blocked_on=["Criterion 1: no source available to verify it"],
                  criteria=self.CRITERIA)
        assert not r.passed
        assert r.data["blocked"], "the matched entries travel to the log"

    def test_index_spellings_all_match(self):
        for spelling in ("criterion 2", "criterion_2", "Criteria 2",
                         "CRITERION-2"):
            assert not unmet(blocked_on=[f"{spelling} — impossible"],
                             criteria=self.CRITERIA).passed, spelling

    def test_a_quoted_criterion_matches_by_terms(self):
        entry = ('"Every claim carries a citable source a reader can use to '
                 'verify it" — the search tier is unavailable')
        assert not unmet(blocked_on=[entry], criteria=self.CRITERIA).passed

    def test_a_paraphrase_sharing_most_terms_matches(self):
        """The first scripted paraphrase this check ever met: "cannot provide a
        citable source for each claim" shares three of its five significant
        terms with criterion 1 and matched nothing under a pure subset rule.
        A real model's refusal carries filler the criterion does not have, so
        the subset rule alone was the check's fault, not the entry's
        (convention 17). Half of the smaller term set is the line; still
        uncalibrated against a live corpus of refusals."""
        entry = "cannot provide a citable source for each claim"
        assert not unmet(blocked_on=[entry], criteria=self.CRITERIA).passed

    def test_an_entry_sharing_fewer_than_half_its_terms_does_not_block(self):
        """The threshold's other side, pinned so the shared-majority rule
        cannot quietly become any-overlap."""
        assert unmet(blocked_on=["cannot verify the deadline here"],
                     criteria=self.CRITERIA).passed

    def test_an_entry_naming_no_criterion_does_not_block(self):
        """A block about something else is the implementer's judgement, and the
        fold judges it like any other dissent."""
        assert unmet(blocked_on=["the deadline is unrealistic"],
                     criteria=self.CRITERIA).passed

    def test_an_out_of_range_index_does_not_block(self):
        assert unmet(blocked_on=["criterion 9: impossible"],
                     criteria=self.CRITERIA).passed

    def test_blank_entries_are_ignored(self):
        assert unmet(blocked_on=["", "   "], criteria=self.CRITERIA).passed

    def test_the_matched_entries_are_reported_not_swallowed(self):
        entries = ["criterion 1: no source", "the deadline is unrealistic"]
        r = unmet(blocked_on=entries, criteria=self.CRITERIA)
        assert r.data["blocked"] == ["criterion 1: no source"]


class TestTheVerdictField:
    """`blocked_on` is independent of `green` by ruling — no truth-table
    change, and these pin that."""

    def test_it_defaults_to_empty(self):
        from autornd.models.verdicts import ImplementVerdict

        assert ImplementVerdict(done=True, summary="s").blocked_on == []

    def test_the_green_truth_table_is_unaffected_by_a_block(self):
        """A block does not have to also declare itself red: the loop routes on
        this field, not on the implementer's own green self-assessment."""
        from autornd.models.verdicts import ImplementVerdict

        v = ImplementVerdict(done=True, summary="s",
                             blocked_on=["criterion 1: no source"])
        assert v.green is True

    def test_a_block_alongside_red_stays_red(self):
        from autornd.models.verdicts import ImplementVerdict

        v = ImplementVerdict(done=True, summary="s", green=False,
                             red_cause="criterion 4 fails",
                             blocked_on=["criterion 1: no source"])
        assert v.green is False


class TestTheWiring:
    """The gate lives where escalation cannot re-enter itself."""

    def test_it_sits_right_after_implement_in_the_build_loop(self):
        from autornd.graph.spec import load

        body = load("workflows/engineering-rnd.yaml").get("build_loop").body
        assert body.index("blocked_check") == body.index("implement") + 1
        assert body.index("blocked_gate") == body.index("blocked_check") + 1

    def test_it_is_absent_from_the_loops_inside_the_escalation_subgraph(self):
        """A routing gate inside recovery_loop or review_rework_loop would
        re-enter the escalation sub-graph with a fresh budget each time — an
        unbounded path, which B3 forbids. Their bounds are the protection, and
        exhaustion ends `escalated`, the honest terminal."""
        from autornd.graph.spec import load

        spec = load("workflows/engineering-rnd.yaml")
        for loop in ("recovery_loop", "review_rework_loop"):
            assert "blocked_gate" not in spec.get(loop).body, loop


@pytest.mark.asyncio
class TestEscalationReadsTheBlock:
    """B3's invariant: the autopsy reads blocked_on in its failure log. The
    block fires before validate — the only phase that previously wrote the log
    — so the adapter writes the entry on the real path."""

    @staticmethod
    def _state(blocked_on):
        from autornd.graph.executor import ExecutionState
        from autornd.models.verdicts import ImplementVerdict, PlanVerdict

        state = ExecutionState(request="write the brief", iteration=1)
        state.outputs["implement"] = ImplementVerdict(
            done=True, green=True, summary="s", iteration=1,
            blocked_on=blocked_on)
        state.outputs["plan"] = PlanVerdict(
            ready=True, plan="p",
            success_criteria=["Every claim carries a citable source"])
        return state

    @staticmethod
    async def _run_check(state):
        from autornd.graph.adapter import PhaseRunner
        from autornd.graph.executor import ExecutionState  # noqa: F401
        from autornd.graph.spec import Node, NodeKind
        from autornd.routing.openrouter import OpenRouterClient

        runner = PhaseRunner(OpenRouterClient(api_key="test"))
        node = Node(id="blocked_check", kind=NodeKind.CHECK,
                    check="blocked_on_unmet",
                    args={"blocked_on": "implement.blocked_on",
                          "criteria": "plan.success_criteria"})
        result = await runner.run_check(node, state)
        return runner, result

    async def test_a_block_writes_itself_to_the_log_escalation_reads(self):
        runner, result = await self._run_check(
            self._state(["criterion 1: no source available"]))
        assert result.passed is False
        entry = runner.failure_log[-1]
        assert entry["blocked_on"] == ["criterion 1: no source available"]
        assert entry["iteration"] == 1
        assert entry["evidence"], "the reason travels with the refusal"

    async def test_a_passing_check_writes_nothing(self):
        runner, result = await self._run_check(self._state([]))
        assert result.passed is True
        assert runner.failure_log == []


@pytest.mark.asyncio
class TestTheGateRoutes:
    """The ruled loop semantics, end to end through the real executor."""

    BLOCKED = {**IMPL, "blocked_on": [
        "Criterion 1: no source available to verify the backoff cap"]}

    async def test_a_block_routes_immediately_without_consuming_iterations(self):
        """The measured failure was six iterations against an impossible
        criterion. Here: one implement call, then escalation."""
        state, runner = await _run({
            **BASE, "implement": self.BLOCKED,
            "escalation": {"requires_human": True}})

        assert runner.ai_calls.count("implement") == 1, "no iteration against it"
        assert "escalation" in state.path
        assert state.status == "blocked"
        # The block's own reason lives on the gate's record. The terminal
        # reason is the recoverable gate's — the honest last word — so the
        # block is read where routing detail always lives, exactly as the
        # review_clean test reads its gate.
        assert state.outputs["blocked_gate"]["routed_to"] == "escalation"
        assert "criterion" in state.outputs["blocked_gate"]["reason"]

    async def test_blocked_on_empty_behaves_exactly_as_today(self):
        state, runner = await _run({**BASE, "validate": {"green": True}})
        assert state.status == "completed"
        assert runner.ai_calls.count("implement") == 1

    async def test_a_block_naming_no_criterion_does_not_route(self):
        """A block about something else is a dissent, not a dead end — the fold
        judges it."""
        state, runner = await _run({
            **BASE,
            "implement": {**IMPL, "blocked_on": ["the deadline is unrealistic"]},
            "validate": {"green": True}})
        assert state.status == "completed"
        assert runner.ai_calls.count("implement") == 1

    async def test_recovery_after_a_block_is_bounded_and_ends_escalated(self):
        """The no-unbounded-path invariant, exercised: escalation judges the
        work recoverable, recovery runs its own bounded attempts — inside which
        the blocked gate does NOT exist, or it would re-enter escalation
        forever — and exhaustion ends the run escalated."""
        state, runner = await _run({
            **BASE, "implement": self.BLOCKED,
            "validate": {"green": True},
            "review": {"ship": False, "verdict": "no", "findings": []},
            "escalation": {"requires_human": False,
                           "root_cause_analysis": "unsatisfiable as planned",
                           "resolution_directive": "drop the criterion"}})

        assert state.status == "escalated", "exhaustion is the honest terminal"
        # 1 build attempt + escalation_recovery_attempts (3) recovery attempts
        assert runner.ai_calls.count("implement") == 1 + 3
        assert runner.ai_calls.count("escalation") == 1, (
            "the escalation sub-graph must not be re-entered from inside itself")
