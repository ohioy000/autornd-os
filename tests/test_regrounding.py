"""Ruling D37: one re-grounding round, novel blockers only.

Each test drives the real executor against the real workflow file with a
billing scripted client (convention 22: the condition it watches, simulated
end to end; convention 9: the double bills). The asked history is seeded
the way production seeds it -- the context node's own output carries asked
and rounds, and the paid lookup mutates them in place -- so pass two's check
reads what pass one plus the lookup left behind. No network, no module
patching of production code.

One test (b) drives the real PhaseRunner's own lookup handler with a
scripted billing client, so the code that ships is the code that is
tested; the rest drive a double that mirrors the adapter's state evolution
step for step (seeding asked/rounds off context, mutating them in the
lookup, recording first-pass blockers and assumptions with basis).

The six cases, each with its exhibit:

(a) Ready on the first pass: no lookup, one plan pass, unchanged call
    count -- the happy path costs exactly what it cost before the edge.
(b) Not ready, novel blockers, medium risk: exactly one lookup carrying
    only the novel blockers, then exactly one more plan pass.
(c) Blockers all already asked: zero lookups, no second pass, and
    plan_ready blocks naming them.
(d) Second pass still not ready with new blockers: no second lookup,
    and the run blocks naming them -- once is ruled.
(e) Low risk: zero search calls (risk policy unchanged).
(f) A plan that proceeds while naming blockers records them as
    assumptions with their basis -- in the adapter, driven through the
    real PhaseRunner.

Breaking proofs: the novelty decision inverted turns (c) into a lookup,
and 'once' removed turns (d) into a second lookup. A gate whose branches
cannot be told apart is not a gate.

Known limitation (fix belongs to 097): the lookup mutates the context
node's output in place, so the persisted context record shows the
lookup's questions and rounds=1 -- a later write visibly rewriting an
earlier phase's record.
"""

from __future__ import annotations

import pytest

from autornd.evals.runner import ScenarioRun
from autornd.graph.checks import get_check
from autornd.graph.executor import GraphExecutor
from autornd.graph.spec import load
from autornd.routing.openrouter import OpenRouterClient
from tests.test_evals import SETTINGS
from tests.test_graph import ScriptedRunner


class BillingScriptedRunner(ScriptedRunner):
    """Scripted verdicts (no model), but every lookup bills (convention 9).

    AI verdicts come from the canned map; the search-tier lookup goes
    through a priced stand-in so (b) can assert exactly-one-lookup and
    (c)/(e) can assert zero. The double mirrors the adapter's state
    evolution: the context output carries asked/rounds, and the paid lookup
    appends the novel blockers and counts the round in place -- pass two's
    check reads rounds == 1 off it and exits. No module function is
    patched; the asked history flows through state, the way production's
    does.
    """

    def __init__(self, verdicts, per_lookup: float = 0.001):
        super().__init__(verdicts)
        self.search_calls: list[list[str]] = []
        self._client = OpenRouterClient(api_key="test")
        self._per_lookup = per_lookup

    async def run_check(self, node, state):
        if node.id == "context":
            # The executor writes the check output into state AFTER this
            # returns, so seed via the returned Result only.
            from autornd.graph.checks import Result
            return Result(True, "context assembled", asked=[], rounds=0)
        if node.id == "reground_lookup":
            from autornd.graph.checks import Result
            from autornd.graph.executor import resolve_args
            args = resolve_args(node, state)
            gaps = [g for g in list(args.get("blockers") or []) if g]
            self.search_calls.append(list(gaps))
            self._client._account("search", self._per_lookup)
            ctx = state.outputs.get("context")
            if isinstance(ctx, dict):
                ctx["asked"] = list(ctx.get("asked") or []) + list(gaps)
                ctx["rounds"] = 1
            return Result(True, f"{len(gaps)} finding(s) for {len(gaps)} novel blocker(s)",
                          rounds=1, asked=len(gaps), found=len(gaps))
        return await super().run_check(node, state)

    async def run_ai(self, node, state):
        out = await super().run_ai(node, state)
        return out


def _base(overrides=None, risk="medium"):
    # The loop re-runs plan on its own id, so a counting script on "plan"
    # answers every pass -- no second node id, no prompt fallback.
    verdicts = {
        "triage": {"risk": risk, "domains": ["backend"],
                   "unrecallable": False},
        "context": {},
        "plan": {"ready": True, "plan": "Do the thing.",
                 "blockers": [],
                 "success_criteria": ["The thing is done"]},
        "feasibility": {"feasible": True},
        "implement": {"done": True, "green": True, "iteration": 1,
                      "blocked_on": [], "summary": "The thing is done."},
        "domain_review": {"critical": False},
        "validate": {"green": True},
        "review": {"ship": True},
        "rework_review": {"ship": True},
    }
    verdicts.update(overrides or {})
    return verdicts


async def _run(verdicts, settings=None):
    spec = load("workflows/engineering-rnd.yaml")
    runner = BillingScriptedRunner(verdicts)
    state = await GraphExecutor(spec, runner, settings or SETTINGS).run("D37 probe")
    return state, runner


class TestRegroundingNovelty:
    """The check at the heart of the edge, driven directly with args."""

    def test_a_novel_blocker_is_novel(self):
        out = get_check("reground_context")(
            ready=False, risk="medium",
            blockers=["container topology: shared or per-worker?"],
            asked=[], rounds=0)
        assert out.passed is True
        assert out.data["novel"] is True
        assert out.data["fresh"] == ["container topology: shared or per-worker?"]

    def test_an_already_asked_blocker_is_not_novel(self):
        out = get_check("reground_context")(
            ready=False, risk="medium",
            blockers=["  Container Topology: shared or per-worker?! "],
            asked=["container topology: shared or per-worker?"], rounds=0)
        assert out.passed is False
        assert out.data["novel"] is False

    def test_no_blockers_is_not_novel(self):
        out = get_check("reground_context")(
            ready=False, risk="medium", blockers=[], asked=[], rounds=0)
        assert out.passed is False

    def test_a_ready_plan_needs_no_regrounding(self):
        out = get_check("reground_context")(
            ready=True, risk="medium",
            blockers=["a brand new question never asked"], asked=[], rounds=0)
        assert out.passed is False

    def test_a_low_risk_plan_needs_no_paid_regrounding(self):
        out = get_check("reground_context")(
            ready=False, risk="low",
            blockers=["a brand new question never asked"], asked=[], rounds=0)
        assert out.passed is False

    def test_a_round_already_run_is_not_novel_whatever_the_blockers(self):
        out = get_check("reground_context")(
            ready=False, risk="medium",
            blockers=["a brand new question never asked"], asked=[], rounds=1)
        assert out.passed is False

    def test_novelty_false_then_lookup_skips(self):
        """Prove the gate by its wiring: passed False skips the lookup (its
        when reads reground_context.passed == true) -- a False check means
        zero search calls, a True check means one."""
        import autornd.graph.conditions as cond
        scope = {"reground_context": {"passed": True}}
        assert cond.evaluate("reground_context.passed == true", scope) is True
        scope = {"reground_context": {"passed": False}}
        assert cond.evaluate("reground_context.passed == true", scope) is False


@pytest.mark.asyncio
class TestRegroundingEdge:
    """The edge end to end: (a) ready first pass costs nothing new."""

    async def test_ready_first_pass_no_lookup_one_plan_pass(self):
        state, runner = await _run(_base())
        assert state.status == "completed", state.reason
        # Ready first pass: the check exits the loop (passed False), no
        # lookup fires, plan ran once. Zero lookups, zero billed, one plan
        # pass: the happy path costs exactly what it cost before the edge.
        assert runner.search_calls == []
        assert runner.ai_calls.count("plan") == 1
        assert state.outputs["regrounding_loop"]["iterations"] == 1

    async def test_novel_blockers_one_lookup_then_one_more_pass(self):
        plan_calls = {"n": 0}

        def plan(state):
            plan_calls["n"] += 1
            if plan_calls["n"] == 1:
                return {"ready": False, "plan": "",
                        "blockers": ["container topology: shared or per-worker?"],
                        "success_criteria": []}
            return {"ready": True, "plan": "Do the thing, grounded.",
                    "blockers": [],
                    "success_criteria": ["The thing is done"]}

        state, runner = await _run(_base({"plan": plan}))
        # Exactly one lookup, carrying only the novel blocker; then exactly
        # one more plan pass. The second plan is ready, so the run
        # completes on the re-grounded context.
        assert runner.search_calls == [["container topology: shared or per-worker?"]]
        assert plan_calls["n"] == 2, plan_calls
        assert state.outputs["plan"].get("ready") is True
        assert state.status == "completed", (state.status, state.reason)

    async def test_already_asked_zero_lookups_no_second_pass(self):
        # Seed the asked record the way production seeds it -- through the
        # context node's own output -- with the same question the plan will
        # name: the check finds nothing novel, the lookup's when skips, the
        # loop exits, plan_ready blocks naming the blocker.
        orig_run_check = BillingScriptedRunner.run_check

        async def seeded(self, node, state):
            # The executor writes each check output into state AFTER run_check
            # returns, so seeding on the "context" entry would be overwritten.
            # Seed lazily on the first check entry instead: context's output
            # is already written by then.
            if node.id == "reground_context":
                ctx = state.outputs.get("context")
                if isinstance(ctx, dict):
                    ctx["asked"] = [
                        "container topology: shared or per-worker?"]
            return await orig_run_check(self, node, state)

        BillingScriptedRunner.run_check = seeded
        try:
            def plan(state):
                return {"ready": False, "plan": "",
                        "blockers": ["container topology: shared or per-worker?"],
                        "success_criteria": []}
            state, runner = await _run(_base({"plan": plan}))
        finally:
            BillingScriptedRunner.run_check = orig_run_check
        assert runner.search_calls == []
        assert runner.ai_calls.count("plan") == 1, runner.ai_calls
        assert state.status == "blocked", (state.status, state.reason)
        assert "container topology" in state.reason

    async def test_second_pass_new_blockers_no_second_lookup(self):
        # Second pass names a NEW blocker: still no second lookup -- once is
        # ruled (rounds == 1 exits the check), and the run blocks naming it.
        calls = {"n": 0}

        def plan(state):
            calls["n"] += 1
            if calls["n"] == 1:
                return {"ready": False, "plan": "",
                        "blockers": ["first unknown"],
                        "success_criteria": []}
            return {"ready": False, "plan": "",
                    "blockers": ["second unknown, never asked before"],
                    "success_criteria": []}
        state, runner = await _run(_base({"plan": plan}))
        assert runner.search_calls == [["first unknown"]], runner.search_calls
        assert calls["n"] == 2, calls
        assert state.status == "blocked", (state.status, state.reason)
        assert "second unknown" in state.reason

    async def test_low_risk_zero_search_calls(self):
        # Low risk: the check itself returns False, so the lookup never
        # fires -- zero search calls -- and the run blocks on the plan as
        # written.
        def plan(state):
            return {"ready": False, "plan": "",
                    "blockers": ["container topology: shared or per-worker?"],
                    "success_criteria": []}
        state, runner = await _run(_base({"plan": plan}, risk="low"))
        assert runner.search_calls == [], runner.search_calls
        assert runner.ai_calls.count("plan") == 1, runner.ai_calls
        assert state.status == "blocked", (state.status, state.reason)

    async def test_proceeding_with_blockers_records_assumptions(self):
        # (f), through the real PhaseRunner: a ready plan that still names
        # blockers proceeds -- and the ADAPTER records them as assumptions
        # with their basis (asked or not, findings from the round). The
        # scripted client bills every call (convention 9); the plan verdict
        # is canned, but the recording code is production's.
        from autornd.graph.adapter import PhaseRunner
        from autornd.graph.executor import ExecutionState
        from autornd.models.verdicts import TriageVerdict
        from tests.conftest import make_mock_client

        client = make_mock_client({
            "architecture": {"ready": True,
                             "plan": "Do the thing, assuming the topology.",
                             "blockers": ["container topology: shared or per-worker?"],
                             "success_criteria": ["The thing is done"]},
        })
        runner = PhaseRunner(client)
        state = ExecutionState(request="D37 probe (f)")
        state.outputs["triage"] = TriageVerdict(
            risk="medium", domains=["backend"], specialists=["systems_architect"],
            unrecallable=False, summary="backend change, recallable")
        state.iteration = 1
        from autornd.graph.spec import load as _load
        node = _load("workflows/engineering-rnd.yaml").get("plan")
        verdict = await runner.run_ai(node, state)
        assert verdict.ready is True
        assert runner.assumptions_declared == [{
            "blocker": "container topology: shared or per-worker?",
            "basis": "asked: false; lookup returned 0 finding(s) this round"}]

    async def test_adapter_lookup_handler_bills_and_evolves_state(self):
        # (b), through the real PhaseRunner: the adapter's own lookup
        # handler sends only the novel blockers, bills the search call, and
        # mutates context asked/rounds in place -- the code that ships is
        # the code that is tested.
        from autornd.graph.adapter import PhaseRunner
        from autornd.graph.executor import ExecutionState
        from tests.conftest import make_mock_client

        client = make_mock_client({
            "search": {"answer": "dedicated per-worker sidecars",
                       "citations": ["runbook p.3"]},
        })
        runner = PhaseRunner(client)
        state = ExecutionState(request="D37 probe (b)")
        state.outputs["triage"] = {"risk": "medium"}
        state.outputs["reground_context"] = {
            "passed": True, "fresh": ["container topology: shared or per-worker?"]}
        state.outputs["context"] = {"asked": [], "rounds": 0}
        from autornd.graph.spec import load as _load
        node = _load("workflows/engineering-rnd.yaml").get("reground_lookup")
        before = client.calls
        result = await runner.run_check(node, state)
        assert result.passed is True
        assert result.data["asked"] == 1 and result.data["found"] == 1
        assert client.calls == before + 1  # billed (convention 9)
        assert runner.regrounding_rounds == 1
        assert runner.regrounding_novel == ["container topology: shared or per-worker?"]
        assert state.outputs["context"] == {
            "asked": ["container topology: shared or per-worker?"], "rounds": 1}


class TestBreakingProofs:
    """A gate whose branches cannot be told apart is not a gate."""

    async def test_novelty_inverted_turns_no_lookup_into_lookup(self):
        """Break the novelty decision and (c) flips: the already-asked
        blocker now reads novel, the lookup fires, the second pass runs.
        With the inversion: search_calls == [[blocker]]; without: []."""
        import autornd.graph.checks as checks_mod
        real = checks_mod.registry["reground_context"]

        def inverted(**kw):
            out = real(**kw)
            from autornd.graph.checks import Result
            # Invert only the no-novelty branch ((c)'s shape: blockers all
            # asked): a False becomes True carrying the blockers. Leave the
            # already-True branches alone, or the second pass would fire a
            # second lookup off an empty fresh list.
            if not out.passed and (kw.get("blockers") or []):
                return Result(True, "inverted for the break demo",
                              novel=True, fresh=list(kw.get("blockers") or []))
            return out

        checks_mod.registry["reground_context"] = inverted
        try:
            calls = {"n": 0}

            def plan(state):
                calls["n"] += 1
                if calls["n"] == 1:
                    return {"ready": False, "plan": "",
                            "blockers": ["container topology: shared or per-worker?"],
                            "success_criteria": []}
                return {"ready": True, "plan": "Do the thing, grounded.",
                        "blockers": [],
                        "success_criteria": ["The thing is done"]}
            orig_run_check = BillingScriptedRunner.run_check

            async def seeded(self, node, state):
                if node.id == "reground_context":
                    ctx = state.outputs.get("context")
                    if isinstance(ctx, dict):
                        ctx["asked"] = [
                            "container topology: shared or per-worker?"]
                return await orig_run_check(self, node, state)

            BillingScriptedRunner.run_check = seeded
            try:
                state, runner = await _run(_base({"plan": plan}))
            finally:
                BillingScriptedRunner.run_check = orig_run_check
        finally:
            checks_mod.registry["reground_context"] = real
        assert runner.search_calls == [["container topology: shared or per-worker?"]]

    async def test_once_removed_turns_one_lookup_into_two(self):
        """Break 'once' (rounds ignored) and (d) flips: the second pass's
        new blocker fires a second lookup. Two search calls with the guard
        removed, one with it."""
        import autornd.graph.checks as checks_mod
        real = checks_mod.registry["reground_context"]

        def no_once(ready=False, risk=None, blockers=None, asked=None, rounds=0):
            return real(ready=ready, risk=risk, blockers=blockers,
                        asked=asked, rounds=0)

        checks_mod.registry["reground_context"] = no_once
        try:
            calls = {"n": 0}

            def plan(state):
                calls["n"] += 1
                if calls["n"] == 1:
                    return {"ready": False, "plan": "",
                            "blockers": ["first unknown"],
                            "success_criteria": []}
                return {"ready": False, "plan": "",
                        "blockers": ["second unknown, never asked before"],
                        "success_criteria": []}
            state, runner = await _run(_base({"plan": plan}))
        finally:
            checks_mod.registry["reground_context"] = real
        assert runner.search_calls == [["first unknown"],
                                       ["second unknown, never asked before"]]


class TestAssumptionCounting:
    """The typed block is present with zeros when the edge did not fire.

    This drives a real run (ready first pass, no lookup) and asserts the
    block the unit-record builder produces — not dataclass defaults, which
    cannot fail on behaviour (convention 28: no evidence is not no
    problem).
    """

    async def test_quiet_run_reports_the_block_with_zeros(self):
        from autornd.evals.runner import _regrounding_block
        state, runner = await _run(_base())
        assert state.status == "completed", state.reason
        block = _regrounding_block(runner, state)
        assert block == {
            "rounds": 0,
            "blockers_first_pass": [],
            "novel": [],
            "asked": 0,
            "findings": 0,
            "blockers_second_pass": [],
            "assumptions": [],
        }

    async def test_fired_run_reports_the_full_block(self):
        from autornd.evals.runner import _regrounding_block

        def plan(state):
            return {"ready": True, "plan": "Do the thing, assuming the topology.",
                    "blockers": ["container topology: shared or per-worker?"],
                    "success_criteria": ["The thing is done"]}
        state, runner = await _run(_base({"plan": plan}))
        assert state.status == "completed", (state.status, state.reason)
        block = _regrounding_block(runner, state)
        assert block["rounds"] == 0  # ready first pass: the check exits, no lookup
        assert block["blockers_first_pass"] == ["container topology: shared or per-worker?"]
        assert block["assumptions"] == [{
            "blocker": "container topology: shared or per-worker?",
            "basis": "asked: false; lookup returned 0 finding(s) this round"}]
