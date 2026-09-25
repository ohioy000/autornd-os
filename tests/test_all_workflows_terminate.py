"""Every workflow reaches a terminal — breadth beyond the proven pipeline.

ARCH-20260925-061. Only engineering-rnd had been driven end to end (cases
(a)–(c) in test_failure_path_terminal.py, case (d) recovery-succeeds). The
tree holds six workflow files; this file drives the other five provider-free
through the same ScriptedRunner harness and asserts each reaches `completed`.

No workflow, bound, threshold, gate or check is modified here — a defect
found is reported, not fixed (that needs a ruling). The independent-check
probe's `independent_check` node runs under the ScriptedRunner like any
other AI node: the harness answers it, so the node is reached and the path
is proven; what a real independent tier would conclude is not measured here.
"""

from __future__ import annotations

import pytest

from autornd.graph.executor import GraphExecutor
from autornd.graph.spec import load
from tests.test_graph import ScriptedRunner, SETTINGS


def _satisfying_verdicts(**overrides):
    verdicts = {
        "triage": {"risk": "medium", "domains": ["backend"],
                   "unrecallable": False},
        "context": {},
        "plan": {"ready": True, "plan": "Do the thing.",
                 "success_criteria": ["The thing is done"]},
        "feasibility": {"feasible": True},
        "implement": {"done": True, "green": True, "iteration": 1,
                      "blocked_on": [], "summary": "The thing is done."},
        "domain_review": {"critical": False},
        "validate": {"green": True},
        "review": {"ship": True},
        "rework_review": {"ship": True},
    }
    verdicts.update(overrides)
    return verdicts


async def _drive(workflow_name, verdicts):
    spec = load(f"workflows/{workflow_name}.yaml")
    runner = ScriptedRunner(verdicts)
    state = await GraphExecutor(spec, runner, SETTINGS).run("breadth probe")
    return state, runner


@pytest.mark.asyncio
class TestEveryWorkflowReachesATerminal:
    """Convention 22: each workflow is driven end to end, not inspected."""

    async def test_lean_completes(self):
        state, runner = await _drive("lean", _satisfying_verdicts())
        assert state.status == "completed", state.reason
        assert state.reason == "advisory review: shipped"
        assert state.path == [
            "triage", "context", "plan", "plan_ready",
            "implement", "coverage", "validate", "judges", "review",
        ]

    async def test_lean_dissent_is_visible(self):
        """ARCH-20260925-063 (Ruling D22): a dissenting lean review is
        visible in the terminal — the run still completes (no gate added),
        but completed can no longer read as reviewed and approved."""
        state, _ = await _drive(
            "lean",
            _satisfying_verdicts(review={"ship": False,
                                         "findings": "missing tests"}))
        assert state.status == "completed"
        assert state.reason is not None
        assert "advisory" in state.reason
        assert "did not ship" in state.reason
        assert "missing tests" in state.reason

    async def test_advisory_label_breaks_without_the_plumbing(self):
        """Prove it by breaking it: with review.ship removed the suffix
        reads nothing — the label reads the field it claims to read
        (convention 28)."""
        from autornd.graph.executor import _advisory_review_suffix
        from autornd.graph.executor import ExecutionState as ES

        state = ES(request="r")
        state.outputs["review"] = {"ship": True}
        assert "advisory" in _advisory_review_suffix(state)

        del state.outputs["review"]["ship"]
        assert _advisory_review_suffix(state) == ""

    async def test_triage_only_completes(self):
        state, runner = await _drive("triage-only", _satisfying_verdicts())
        assert state.status == "completed", state.reason
        assert state.path == ["triage", "context"]

    async def test_triage_classify_completes(self):
        state, runner = await _drive("triage-classify",
                                     _satisfying_verdicts())
        assert state.status == "completed", state.reason
        assert state.path == ["triage"]

    async def test_plan_probe_completes(self):
        state, runner = await _drive("plan-probe", _satisfying_verdicts())
        assert state.status == "completed", state.reason
        assert state.path == ["triage", "context", "plan"]

    async def test_independent_check_probe_completes(self):
        """With an unrecallable triage the probe reaches independent_check;
        with a recallable one the node skips and the run still completes —
        both are terminals, and both are asserted."""
        reached, _ = await _drive(
            "independent-check-probe",
            _satisfying_verdicts(
                triage={"risk": "medium", "domains": ["backend"],
                        "unrecallable": True}))
        assert reached.status == "completed", reached.reason
        assert "independent_check" in reached.path

        skipped, _ = await _drive("independent-check-probe",
                                  _satisfying_verdicts())
        assert skipped.status == "completed", skipped.reason
        assert "independent_check" not in skipped.path
