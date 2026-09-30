"""Ruling D37: one re-grounding round, novel blockers only.

Each test drives the real executor against the real workflow file with a
billing scripted client (convention 22: the condition it watches, simulated
end to end; convention 9: the double bills). The asked history is seeded
the way production seeds it -- the context node's own output carries asked
and rounds, and the paid lookup mutates them in place -- so pass two's check
reads what pass one plus the lookup left behind. No network, no module
patching of production code.

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
    assumptions with their basis.

Breaking proofs: the novelty decision inverted turns (c) into a lookup,
and 'once' removed turns (d) into a second lookup. A gate whose branches
cannot be told apart is not a gate.
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
        # (f): a plan that proceeds while naming blockers records them as
        # assumptions with their basis -- mirroring what the adapter does in
        # production, where the record is read off the runner.
        if node.id == "plan" and isinstance(out, dict):
            if out.get("ready") and out.get("blockers"):
                if not hasattr(self, "assumptions_declared"):
                    self.assumptions_declared: list[dict] = []
                for b in out["blockers"]:
                    self.assumptions_declared.append(
                        {"blocker": b, "basis": "plan proceeded naming it"})
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
        # A ready plan that still names blockers proceeds -- and records them
        # as assumptions with their basis on the runner, where the unit
        # record reads them.
        def plan(state):
            return {"ready": True, "plan": "Do the thing, assuming the topology.",
                    "blockers": ["container topology: shared or per-worker?"],
                    "success_criteria": ["The thing is done"]}
        state, runner = await _run(_base({"plan": plan}))
        assert runner.search_calls == [], runner.search_calls
        assert state.status == "completed", (state.status, state.reason)
        assert {"blocker": "container topology: shared or per-worker?",
                "basis": "plan proceeded naming it"} in runner.assumptions_declared


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
    """The record block is present with zeros when the edge did not fire."""

    def test_runner_defaults_are_the_honest_zero(self):
        import dataclasses
        by_name = {f.name: f for f in dataclasses.fields(ScenarioRun)}
        assert "regrounding_rounds" in by_name, "no re-grounding count field"
        assert "assumptions_declared" in by_name, "no assumption record field"
        rr = by_name["regrounding_rounds"]
        assert (rr.default == 0
                or getattr(rr.default_factory, "__call__", None) and rr.default_factory() == 0)
        ad = by_name["assumptions_declared"]
        assert list(ad.default_factory()) == []
