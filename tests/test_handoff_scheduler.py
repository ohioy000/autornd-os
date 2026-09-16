"""The handoff scheduler runs the sub-graph a routing target names, completely.

**The defect.** Until this file's fix, `_run_from` walked the node list once,
in file order, admitting a node only if its dependencies had already been
admitted by that same pass. Three ways to lose a node, all silent:

- a handoff node declared before its dependency was never revisited — dropped;
- a handoff node could execute before the node it depends on;
- a handoff-owned node with no declared dependencies was dropped
  unconditionally (`and node.depends_on`).

Found by external assessment, verified by the advisor at 27cf116 — the one
structural defect fifteen blueprints of instrumentation walked past. Latent in
every shipped workflow because each declares its handoff sub-graphs in
dependency order, which is why the suite stayed green throughout. The first two
tests fail against the old code by construction; the third pins the shipped
flagship's exact routing path as the no-regression guard — any change to the
path every live run takes must be deliberate, ruled, and visible here (B2's
block gate changed it, and this assertion caught that on the first run).

Convention 22's shape: every test drives the real executor end to end, on the
condition the scheduler watches — a routing target whose sub-graph is not in
file order.
"""

from __future__ import annotations

import pytest

from autornd.graph.executor import GraphExecutor
from autornd.graph.spec import SpecError, parse

from tests.test_graph import BASE, SETTINGS, ScriptedRunner, _ai, _run


async def _run_spec(nodes, verdicts, settings=None):
    spec = parse({"name": "w", "nodes": nodes})
    runner = ScriptedRunner(verdicts)
    state = await GraphExecutor(spec, runner, settings or SETTINGS).run("Add retry")
    return state, runner


class TestAHandoffSubGraphRunsCompleteAndInOrder:
    async def test_a_node_whose_dependency_is_declared_later_is_not_dropped(self):
        """`cleanup` depends on `recover`, which is declared after it. The old
        single pass reached `cleanup` first, found `recover` unadmitted, and
        dropped it forever — the escalation sub-graph ran one node short, and
        ran `recover` before the `escalate` it depends on."""
        state, runner = await _run_spec([
            _ai("impl"),
            _ai("cleanup", depends_on=["recover"]),
            _ai("recover", depends_on=["escalate"]),
            _ai("escalate"),
            {"id": "loop", "kind": "ai", "body": ["impl"],
             "until": "impl.green == true", "max_iterations": 1,
             "on_exhausted": "escalate"},
        ], {"impl": {"green": False}})

        assert state.status == "completed"
        # dependency order, not file order: escalate, then recover, then the
        # node the old pass silently lost
        assert state.path == ["impl", "escalate", "recover", "cleanup"]

    async def test_a_handoff_owned_node_with_no_dependencies_executes(self):
        """`notify` declares no dependencies, so the old pass skipped it
        unconditionally — even though `escalate`, the node the handoff routes
        to, depends on it. `notify` is handoff-owned (a gate's on_fail target
        whose condition never fires), so nothing else would ever run it: the
        sub-graph ran without the one node its target needed."""
        state, runner = await _run_spec([
            _ai("impl"),
            {"id": "anchor", "kind": "check", "check": "not_a_real_check"},
            {"id": "gate", "kind": "gate", "condition": "anchor.passed == true",
             "on_fail": "notify"},
            _ai("notify"),
            _ai("escalate", depends_on=["notify"]),
            {"id": "loop", "kind": "ai", "body": ["impl"],
             "until": "impl.green == true", "max_iterations": 1,
             "on_exhausted": "escalate"},
        ], {"impl": {"green": False}})

        assert state.status == "completed"
        assert "notify" in state.path, "dropped by the old pass — no dependencies"
        assert state.path.index("notify") < state.path.index("escalate")


class TestTheShippedFlagshipIsUnchanged:
    async def test_the_blocked_review_routing_path_is_pinned(self):
        """The shipped yamls declare every handoff sub-graph in dependency
        order, which is exactly why the scheduler defect stayed latent. This
        pins the full blocked-review path — the one that exercises `_run_from`
        twice, once for the gate route and once for the loop's exhaustion — so
        any change to the path every live run takes must be deliberate and
        visible here. The B13 block nodes sit inside the build iterations; the
        rework loops' bodies are unchanged, because a routing gate inside the
        escalation sub-graph would be an unbounded path."""
        state, runner = await _run({
            **BASE, "validate": {"green": True},
            "review": {"ship": False, "verdict": "no", "findings": []},
            "escalation": {"requires_human": True}})

        assert state.status == "blocked"
        assert state.path == [
            "triage", "context", "plan", "feasibility", "plan_ready",
            "verify_grounding",
            "implement", "blocked_check", "blocked_gate",
            "domain_review", "coverage", "consistency",
            "validate", "judges", "review", "review_clean",
            "implement", "domain_review", "coverage", "consistency",
            "validate", "judges", "rework_review", "review_fold",
            "implement", "domain_review", "coverage", "consistency",
            "validate", "judges", "rework_review", "review_fold",
            "escalation", "recoverable",
        ]


class TestLoadTimeValidation:
    def test_a_cycle_in_a_handoff_subgraph_fails_at_load(self):
        """The scheduler can now order anything orderable; a cycle is not, and
        it must fail at load rather than mid-run, after the run has paid for
        everything before it — the conditions module's founding principle,
        applied to its own scheduler."""
        with pytest.raises(SpecError, match="not orderable"):
            parse({"name": "w", "nodes": [
                _ai("a", depends_on=["b"]),
                _ai("b", depends_on=["a"]),
                {"id": "g", "kind": "gate", "condition": "a.green == true",
                 "on_fail": "a"},
            ]})
