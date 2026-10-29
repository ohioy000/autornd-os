"""The honest-refusal channel: the implementer may refuse, and the loop listens.

**The ruled design (Blueprint 016 B2/B3, re-anchored by Ruling D51
(5)).** `blocked_on` is the implementer's channel for naming an ask
the work cannot honestly satisfy with what is available. The
measured failure it exists for: a low-risk brief whose request
demanded "a citable source a reader can use to verify the claim"
while the risk gate had already zeroed its lookups — the implementer
fabricated sources for six iterations and died on the cost ceiling
rather than refusing. The loop semantics: a block naming an ask —
by its number, or by a quote of the request's own words — routes to
escalation immediately, without consuming further iterations. A block
naming no ask is a note: counted, recorded, routed nowhere, and the
fold judges it like any other dissent.

Every test here drives the real check, the real gate wiring or the
real executor end to end — convention 22's shape. The override-once-per-run
half of B4 lives in tests/test_citation_demand.py and is not duplicated here.
"""

from __future__ import annotations

import pytest

from autornd.graph.checks import get_check
from tests.test_graph import BASE, IMPL, SETTINGS, PLAN, _run

unmet = get_check("blocked_on_unmet")

# Ruling D51 (5): the typed contract's fixtures. The asks are
# the anchoring check's own output shape — dicts with a
# number, a quote and a kind — and the request is the text
# both the quotes and a by-quote entry must anchor in.
REQUEST = ("Add retry with exponential backoff to the MQTT client, "
           "and cite a source for every claim")
ASKS = [
    {"number": 1, "quote": "retry with exponential backoff",
     "kind": "step"},
    {"number": 2, "quote": "cite a source for every claim",
     "kind": "constraint"},
]


class TestTheCheck:
    """`blocked_on_unmet`: did a blocked entry name an ask?"""

    def test_an_empty_list_is_not_a_block(self):
        assert unmet(blocked_on=[], asks=ASKS,
                     request=REQUEST).passed

    def test_a_number_reference_names_the_ask(self):
        r = unmet(blocked_on=[{"ask": 1,
                               "why": "no source available to verify it"}],
                  asks=ASKS, request=REQUEST)
        assert not r.passed
        assert r.data["blocked"] == [
            {"ask": 1, "why": "no source available to verify it"}], (
            "the named entries travel to the log")

    def test_a_quote_reference_names_the_ask(self):
        r = unmet(blocked_on=[{
            "ask": "retry with exponential backoff",
            "why": "the backoff curve is unmeasurable here"}],
            asks=ASKS, request=REQUEST)
        assert not r.passed

    def test_a_quote_matching_an_anchored_ask_names_it_by_number(self):
        """The detail the failure log and the gate read renders
        the ask's own number when the quote is one of the
        anchored asks verbatim — so the autopsy can rule on
        the dissent by number."""
        r = unmet(blocked_on=[{"ask": "retry with exponential backoff",
                               "why": "unmeasurable"}],
                  asks=ASKS, request=REQUEST)
        assert "ask 1: unmeasurable" in r.detail

    def test_an_out_of_range_number_names_nothing(self):
        assert unmet(blocked_on=[{"ask": 9, "why": "impossible"}],
                     asks=ASKS, request=REQUEST).passed

    def test_a_quote_not_in_the_request_names_nothing(self):
        """A paraphrase anchors nothing — the yardstick cannot
        drift off the request's own words."""
        assert unmet(blocked_on=[{"ask": "retry the connection",
                                  "why": "no bench"}],
                     asks=ASKS, request=REQUEST).passed

    def test_an_entry_naming_no_ask_is_a_note(self):
        """A block about something else is the implementer's
        judgement, and the fold judges it — counted, never
        blocking, routed nowhere."""
        from autornd.models.verdicts import (
            BLOCKED_ON_NO_ASK, normalisations_by_kind,
            reset_normalisations)

        reset_normalisations()
        assert unmet(blocked_on=[{"why": "the deadline is unrealistic"}],
                     asks=ASKS, request=REQUEST).passed
        assert normalisations_by_kind().get(BLOCKED_ON_NO_ASK) == 1

    def test_a_bare_string_names_nothing(self):
        """The pre-D51 shape — a refusal in prose. Under the
        typed contract it is the ruled note: it carries its
        reason and names no ask (convention 17: the old check
        matched it by term overlap; the typed contract is what
        the ruling demands)."""
        assert unmet(blocked_on=["criterion 1: no source available"],
                     asks=ASKS, request=REQUEST).passed

    def test_blank_entries_are_ignored(self):
        assert unmet(blocked_on=["", "   "], asks=ASKS,
                     request=REQUEST).passed

    def test_the_named_entries_are_reported_not_swallowed(self):
        entries = [{"ask": 1, "why": "no source"},
                   {"why": "the deadline is unrealistic"}]
        r = unmet(blocked_on=entries, asks=ASKS, request=REQUEST)
        assert r.data["blocked"] == [{"ask": 1, "why": "no source"}]


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

        body = load("workflows/full-team.yaml").get("build_loop").body
        assert body.index("blocked_check") == body.index("implement") + 1
        assert body.index("blocked_gate") == body.index("blocked_check") + 1

    def test_it_is_absent_from_the_loops_inside_the_escalation_subgraph(self):
        """A routing gate inside recovery_loop or review_rework_loop would
        re-enter the escalation sub-graph with a fresh budget each time — an
        unbounded path, which B3 forbids. Their bounds are the protection, and
        exhaustion ends `escalated`, the honest terminal."""
        from autornd.graph.spec import load

        spec = load("workflows/full-team.yaml")
        for loop in ("recovery_loop", "review_rework_loop"):
            assert "blocked_gate" not in spec.get(loop).body, loop

    def test_those_loops_carry_the_terminal_gate_instead(self):
        """What the routing gate cannot do there, a terminal gate can: it ends
        the run, so there is nothing to re-enter. Without it a green-but-blocked
        implementation met no gate at all on those paths and shipped."""
        from autornd.graph.spec import TERMINAL_STATUSES, load

        spec = load("workflows/full-team.yaml")
        for loop in ("recovery_loop", "review_rework_loop"):
            body = spec.get(loop).body
            assert body.index("blocked_check") == body.index("implement") + 1, loop
            assert body.index("blocked_terminal") == body.index("blocked_check") + 1, loop
        assert spec.get("blocked_terminal").on_fail in TERMINAL_STATUSES, (
            "a routing on_fail here would be the unbounded path B3 forbids")


@pytest.mark.asyncio
class TestEscalationReadsTheBlock:
    """B3's invariant: the autopsy reads blocked_on in its failure log. The
    block fires before validate — the only phase that previously wrote the log
    — so the adapter writes the entry on the real path."""

    @staticmethod
    def _state(blocked_on):
        from autornd.graph.executor import ExecutionState
        from autornd.models.verdicts import ImplementVerdict

        # Ruling D51 (5): the state carries the anchored asks
        # the check names the entry against — the anchoring
        # check's own output, with the request itself as the
        # one ask (its ruled fallback for a request that
        # anchors nothing).
        state = ExecutionState(request="write the brief", iteration=1)
        state.outputs["implement"] = ImplementVerdict(
            done=True, green=True, summary="s", iteration=1,
            blocked_on=blocked_on)
        state.outputs["asks_anchored"] = {
            "anchored": [{"number": 1, "quote": "write the brief",
                          "kind": ""}],
            "quotes": ["write the brief"],
            "demoted": [],
        }
        return state

    @staticmethod
    async def _run_check(state):
        from autornd.graph.adapter import PhaseRunner
        from autornd.graph.spec import Node, NodeKind
        from autornd.routing.openrouter import OpenRouterClient

        runner = PhaseRunner(OpenRouterClient(api_key="test"))
        node = Node(id="blocked_check", kind=NodeKind.CHECK,
                    check="blocked_on_unmet",
                    args={"blocked_on": "implement.blocked_on",
                          "asks": "asks_anchored.anchored",
                          "request": "request"})
        result = await runner.run_check(node, state)
        return runner, result

    async def test_a_block_writes_itself_to_the_log_escalation_reads(self):
        runner, result = await self._run_check(
            self._state([{"ask": 1, "why": "no source available"}]))
        assert result.passed is False
        entry = runner.failure_log[-1]
        # Ruling D51 (5): the typed entry travels to the log
        # escalation reads, ask number and reason together.
        assert entry["blocked_on"] == [
            {"ask": 1, "why": "no source available"}]
        assert entry["iteration"] == 1
        assert entry["evidence"], "the reason travels with the refusal"

    async def test_a_passing_check_writes_nothing(self):
        runner, result = await self._run_check(self._state([]))
        assert result.passed is True
        assert runner.failure_log == []


@pytest.mark.asyncio
class TestTheGateRoutes:
    """The ruled loop semantics, end to end through the real executor."""

    # Ruling D51 (5): the typed entry — ask 1 is the whole
    # request under the anchoring check's fallback (the
    # scripted request anchors nothing a model proposed), so
    # the number names it.
    BLOCKED = {**IMPL, "blocked_on": [
        {"ask": 1, "why": "no source available to verify the backoff cap"}]}

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
        assert "ask" in state.outputs["blocked_gate"]["reason"]

    async def test_blocked_on_empty_behaves_exactly_as_today(self):
        state, runner = await _run({**BASE, "validate": {"green": True}})
        assert state.status == "completed"
        assert runner.ai_calls.count("implement") == 1

    async def test_a_block_naming_no_ask_does_not_route(self):
        """A block about something else is a note, not a dead end — the fold
        judges it. A bare string names no ask under the typed contract, so
        even the pre-D51 shape is the note the ruling demands."""
        state, runner = await _run({
            **BASE,
            "implement": {**IMPL, "blocked_on": ["the deadline is unrealistic"]},
            "validate": {"green": True}})
        assert state.status == "completed"
        assert runner.ai_calls.count("implement") == 1

    async def test_a_block_inside_recovery_ends_blocked_on_its_first_attempt(self):
        """Was: exhaustion is the honest terminal. It is not, for a block.

        The old assertion here pinned three recovery attempts against an
        unsatisfiable ask, ending `escalated` — a terminal the run reaches by
        paying for the answer it already had. `blocked` is the honest one, and
        `blocked_terminal` reaches it on the first attempt.

        The invariant the old test actually guarded is unchanged and asserted
        below: the escalation sub-graph is never re-entered from inside itself.
        A terminal gate cannot re-enter anything — that is why it is terminal
        and the routing gate stays out of these bodies.
        """
        state, runner = await _run({
            **BASE, "implement": self.BLOCKED,
            "validate": {"green": True},
            "review": {"ship": False, "verdict": "no", "findings": []},
            "escalation": {"requires_human": False,
                           "root_cause_analysis": "unsatisfiable as planned",
                           "resolution_directive": "drop the ask"}})

        assert state.status == "blocked"
        # 1 build attempt + 1 recovery attempt that ends on the gate, where it
        # used to be 1 + 3 with the last two buying nothing.
        assert runner.ai_calls.count("implement") == 1 + 1
        assert runner.ai_calls.count("escalation") == 1, (
            "the escalation sub-graph must not be re-entered from inside itself")

    async def test_an_unblocked_failure_in_recovery_still_exhausts_to_escalated(self):
        """The fix must not steal the exhaustion path from everything else.

        No block anywhere: rework exhausts its two attempts, escalation judges
        the work recoverable, recovery exhausts its three, and the run ends
        `escalated` exactly as before.
        """
        state, runner = await _run({
            **BASE,
            "validate": {"green": True},
            "review": {"ship": False, "verdict": "no", "findings": []},
            "escalation": {"requires_human": False,
                           "root_cause_analysis": "still red",
                           "resolution_directive": "try again"}})

        assert state.status == "escalated", "exhaustion is the honest terminal"
        assert runner.ai_calls.count("escalation") == 1


@pytest.mark.asyncio
class TestTheGreenButBlockedGap:
    """The defect this gate closes, simulated end to end (convention 22).

    `blocked_check` is the only thing in the graph that reads `blocked_on`
    independently of `green`; validate's failure-log write is guarded on the
    iteration being red. So an implementation that came back GREEN while naming
    an ask it could not satisfy used to record nothing and meet no gate inside
    the rework and recovery loops: four green judges, the loop converged, and
    the work SHIPPED carrying the refusal.

    Found by reading the two write sites, not by a trace — there is no trace of
    it, because the run it produces reports `completed`.

    The block has to arrive AFTER the build loop, or `blocked_gate` catches it
    there and the rework path is never reached. So implement is scripted as a
    callable: clean on the build attempt, green-but-blocked on every attempt
    after it.
    """

    @staticmethod
    def _implement_blocks_after_the_build():
        calls = {"n": 0}

        def implement(state):
            calls["n"] += 1
            if calls["n"] == 1:
                return IMPL
            return {**IMPL, "green": True, "blocked_on": [
                {"ask": 1, "why": "no source available to verify the backoff cap"}]}

        return implement

    async def test_a_green_block_in_the_rework_loop_does_not_ship(self):
        state, runner = await _run({
            **BASE,
            "validate": {"green": True},
            "review": {"ship": False, "verdict": "no", "findings": []},
            "implement": self._implement_blocks_after_the_build()})

        assert state.status == "blocked", (
            "a green implementation naming an unsatisfiable ask must not "
            "ship out of the rework loop")
        assert "blocked_terminal" in state.path

    async def test_the_terminal_reason_names_the_ask(self):
        """A blocked run says why in the terms the work is judged by — the
        gate's detail carries the named entries, not just that a condition
        failed."""
        state, runner = await _run({
            **BASE,
            "validate": {"green": True},
            "review": {"ship": False, "verdict": "no", "findings": []},
            "implement": self._implement_blocks_after_the_build()})

        assert "ask" in (state.reason or "").lower()

    async def test_the_same_verdict_still_ships_when_nothing_is_blocked(self):
        """The gate fires on the block, not on the rework path itself."""
        state, runner = await _run({
            **BASE,
            "validate": {"green": True},
            "review": {"ship": False, "verdict": "no", "findings": []},
            "rework_review": {"ship": True, "verdict": "yes", "findings": []}})

        assert state.status == "completed"
