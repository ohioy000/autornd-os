"""A per-phase timing table must sum to the run, not to three times the run.

**Why this exists.** B3 named the per-phase timing table as B7's deliverable
when a trace expires: "a naked timeout at 1800 s is B7's next name plus the
per-phase timing table, not closure." The first expiry that actually needed it
produced this:

    review_clean 1573s   rework_review 919s   implement 432s   escalation 186s
    plan 99s   validate 89s   review 55s   context 14s   triage 7s

— 3,374 seconds attributed inside an 1,800-second run, with a *gate* as the
largest consumer. `_run_gate` awaited `_run_from` for its routing target from
inside the node's timing block, so every node the gate routed to was billed to
the gate as well as to itself.

A gate's own work is one condition test and one detail string. The sub-graph it
hands off to is timed by its own nodes. So the delegation happens outside the
timer, and these tests pin both halves: the gate is cheap, and the table adds up.
"""

from __future__ import annotations

import asyncio

import pytest

from autornd.graph.checks import Result, get_check, registry
from autornd.graph.executor import GraphExecutor, resolve_args
from autornd.graph.spec import load
from tests.test_graph import BASE, SETTINGS

SLOW = 0.05          # per AI call, in the routed sub-graph


class SlowScriptedRunner:
    """Every AI call costs real wall clock, so timings are comparable."""

    def __init__(self, verdicts):
        self.verdicts = verdicts
        self.ai_calls: list[str] = []

    async def run_ai(self, node, state):
        self.ai_calls.append(node.id)
        await asyncio.sleep(SLOW)
        out = self.verdicts.get(node.id)
        if out is None and node.prompt:
            out = self.verdicts.get(node.prompt)
        return out(state) if callable(out) else (out or {})

    async def run_check(self, node, state):
        if node.check not in registry:
            return Result(True, "context assembled")
        return get_check(node.check)(**resolve_args(node, state))


async def _timed_run(verdicts):
    spec = load("workflows/engineering-rnd.yaml")
    runner = SlowScriptedRunner(verdicts)
    state = await GraphExecutor(spec, runner, SETTINGS).run("Add retry")
    return state, runner


def _seconds_by_node(state) -> dict[str, float]:
    out: dict[str, float] = {}
    for step in state.trace:
        out[step.node_id] = out.get(step.node_id, 0.0) + step.seconds
    return out


@pytest.mark.asyncio
async def test_a_routing_gate_is_not_billed_for_what_it_routes_to():
    """`review_clean` closes and hands off to the rework loop."""
    state, runner = await _timed_run({**BASE, "validate": {"green": True},
                                      "escalation": {"requires_human": True,
                                                     "root_cause_analysis": "rc"},
                                      "review": {"ship": False, "findings": [
                                          {"lens": "test_engineer",
                                           "severity": "high",
                                           "detail": "numbers disagree"}]}})
    by_node = _seconds_by_node(state)
    assert "review_clean" in by_node, state.path
    # The gate routed — otherwise this test is not exercising the bug.
    assert state.outputs["review_clean"].get("routed_to")

    # Its own work is a condition test. One AI call's sleep is the yardstick.
    assert by_node["review_clean"] < SLOW, by_node


@pytest.mark.asyncio
async def test_the_table_sums_to_no_more_than_the_run():
    """The defect showed as a table summing to 187% of its own run."""
    state, runner = await _timed_run({**BASE, "validate": {"green": True},
                                      "escalation": {"requires_human": True,
                                                     "root_cause_analysis": "rc"},
                                      "review": {"ship": False, "findings": [
                                          {"lens": "test_engineer",
                                           "severity": "high",
                                           "detail": "numbers disagree"}]}})
    by_node = _seconds_by_node(state)
    total = sum(by_node.values())
    # Every AI call is timed once; the sleeps are the floor the table must clear
    # without double counting them.
    floor = SLOW * len(runner.ai_calls)
    assert floor <= total < floor * 1.5, (total, floor, by_node)


@pytest.mark.asyncio
async def test_an_open_gate_is_still_timed():
    """Removing the double count must not stop timing gates altogether."""
    state, _ = await _timed_run({**BASE, "validate": {"green": True}})
    by_node = _seconds_by_node(state)
    assert "review_clean" in by_node
    assert by_node["review_clean"] >= 0.0
    assert state.status == "completed"
