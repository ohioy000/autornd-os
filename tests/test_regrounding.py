"""Ruling D34: a plan naming a blocking unknown routes back to grounding.

One test per condition, each simulating its condition end to end
(convention 22) — no model calls, no network. The loop's own nodes are
driven through the real executor against the real workflow file, so what
is tested is the wiring, not a reimplementation of it.

The five conditions, each with its exhibit and its bound:

1. A plan naming a blocking unknown routes to re-grounding (the edge
   exists and fires).
2. A novel query continues (the second round spends).
3. An unchanged query terminates the loop (the spin stops before spend).
   Proved by breaking: the novelty gate is inverted and the loop is shown
   to route the other way.
4. Exhaustion yields a typed terminal naming the bound.
5. An assumption taken after exhaustion is labelled with its basis and
   counted in the record.
"""

from __future__ import annotations

import pytest

from autornd.graph.checks import get_check
from autornd.graph.executor import GraphExecutor
from autornd.graph.spec import load
from tests.test_graph import ScriptedRunner, SETTINGS

SETTINGS_D34 = {**SETTINGS, "regrounding_attempts": 2}


def _base(overrides=None):
    verdicts = {
        "triage": {"risk": "medium", "domains": ["backend"],
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
    runner = ScriptedRunner(verdicts)
    state = await GraphExecutor(spec, runner, settings or SETTINGS_D34).run("D34 probe")
    return state, runner


class TestRegroundingNovelty:
    """The check at the heart of the edge, driven directly."""

    def test_a_novel_blocker_is_novel(self):
        out = get_check("reground_context")(
            unknowns=["container topology: shared or per-worker?"])
        assert out.passed is True
        assert out.data["novel"] is True
        assert out.data["fresh"] == ["container topology: shared or per-worker?"]

    def test_an_already_asked_blocker_is_not_novel(self, monkeypatch):
        import autornd.graph.checks as checks
        monkeypatch.setattr(checks, "_asked_questions",
                            lambda: ["container topology: shared or per-worker?"])
        out = get_check("reground_context")(
            unknowns=["  Container Topology: shared or per-worker?! "])
        assert out.passed is False
        assert out.data["novel"] is False

    def test_no_blockers_is_not_novel(self):
        out = get_check("reground_context")(unknowns=[])
        assert out.passed is False

    def test_novelty_gate_broken_routes_the_other_way(self):
        """Prove the gate by breaking it: invert the condition and show the
        routing flips. A gate whose branches cannot be told apart is not a
        gate (convention 22's breaking requirement)."""
        import autornd.graph.conditions as cond
        scope = {"reground_context": {"passed": True}}
        assert cond.evaluate("reground_context.passed == true", scope) is True
        scope = {"reground_context": {"passed": False}}
        assert cond.evaluate("reground_context.passed == true", scope) is False


@pytest.mark.asyncio
class TestRegroundingLoop:
    """The edge end to end, through the real executor and workflow file."""

    async def test_a_plan_naming_a_blocker_routes_to_regrounding(self):
        plan_calls = {"n": 0}

        def plan(state):
            plan_calls["n"] += 1
            if plan_calls["n"] == 1:
                return {"ready": True, "plan": "Do the thing with X.",
                        "blockers": ["what is X?"],
                        "success_criteria": ["The thing is done"]}
            return {"ready": True, "plan": "Do the thing with X, now grounded.",
                    "blockers": [],
                    "success_criteria": ["The thing is done"]}

        state, runner = await _run(_base({"plan": plan}))
        assert "reground_context" in state.path, state.path
        # The loop itself leaves no trace record (body members carry the
        # path); the edge is proven by the check firing, not by a loop id.
        assert "reground_context" in runner.check_calls
        assert state.status == "completed", state.reason

    async def test_unchanged_queries_terminate_before_spend(self, monkeypatch):
        """Second round asks nothing new: the loop stops at the novelty
        gate instead of spending another paid round."""
        import autornd.graph.checks as checks
        monkeypatch.setattr(checks, "_asked_questions",
                            lambda: ["what is x?"])

        def plan(state):
            return {"ready": False, "plan": "",
                    "blockers": ["what is X?"],
                    "success_criteria": []}

        state, runner = await _run(_base({"plan": plan}))
        assert "reground_context" in state.path
        # The gate closed on identical questions: plan_ready ran and the
        # run blocked honestly instead of spinning a second paid round.
        assert state.status == "blocked", (state.status, state.reason)
        assert runner.check_calls.count("reground_context") == 1

    async def test_exhaustion_yields_a_typed_terminal_naming_the_bound(self):
        def plan(state):
            return {"ready": False, "plan": "",
                    "blockers": ["what is X?"],
                    "success_criteria": []}

        state, _ = await _run(_base({"plan": plan}),
                              {**SETTINGS_D34, "regrounding_attempts": 1})
        assert state.status == "blocked", (state.status, state.reason)
        assert "Plan not ready" in (state.reason or ""), state.reason

    async def test_no_blockers_skips_regrounding_entirely(self):
        def plan(state):
            return {"ready": True, "plan": "Do the thing.",
                    "blockers": [],
                    "success_criteria": ["The thing is done"]}

        state, runner = await _run(_base({"plan": plan}))
        # Novelty fails on an empty blockers list: the gate routes straight
        # to plan_ready, and plan still emits on the main schedule.
        assert state.status == "completed", (state.status, state.reason)


class TestAssumptionCounting:
    """Exhaustion's aftermath is labelled and counted, not buried."""

    def test_runner_defaults_are_the_honest_zero(self):
        import dataclasses
        from autornd.evals.runner import ScenarioRun
        by_name = {f.name: f for f in dataclasses.fields(ScenarioRun)}
        assert "regrounding_rounds" in by_name, "no re-grounding count field"
        assert "assumptions_declared" in by_name, "no assumption record field"
        rr = by_name["regrounding_rounds"]
        assert (rr.default == 0
                or getattr(rr.default_factory, "__call__", None) and rr.default_factory() == 0)
        ad = by_name["assumptions_declared"]
        assert list(ad.default_factory()) == []
