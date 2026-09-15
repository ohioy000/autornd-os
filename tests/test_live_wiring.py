"""What the API actually calls, pinned — and where the wall clock goes.

**Why this file exists.** Blueprint 009 ordered `autornd/engine/workflow.py`
deleted as the graph's legacy equivalence reference. It is not: `api/routes.py`
imports `WorkflowEngine` from it and calls it on every workflow request. The
ruling inherited an error from `HANDOVER`'s own data-flow diagram, which draws
the request path as going straight from the routes to the executor. Only the
hardcoded sequencer inside the file was the reference, and only that was removed.

A document can be wrong and stay wrong; a test cannot. The dependency that
stopped that deletion is asserted here so the next person reading the diagram
does not have to notice the same thing twice.
"""

from __future__ import annotations

import pytest


class TestTheRequestPathIsWhatTheDocumentsSay:
    def test_routes_drive_workflows_through_the_engine_facade(self):
        import autornd.api.routes as routes
        from autornd.engine.workflow import WorkflowEngine

        assert routes.WorkflowEngine is WorkflowEngine, (
            "api/routes.py drives workflows through WorkflowEngine — deleting "
            "that module breaks every workflow request, whatever the handover "
            "diagram shows"
        )

    def test_the_facade_runs_the_graph_rather_than_a_sequence(self):
        """The half of 009's ruling that was right: the hardcoded sequencer is
        gone. What remains loads a workflow file and runs it."""
        import inspect

        from autornd.engine.workflow import WorkflowEngine

        source = inspect.getsource(WorkflowEngine.execute)
        assert "GraphExecutor" in source
        assert not hasattr(WorkflowEngine, "execute_hardcoded"), (
            "the legacy sequencer was retired; it should not come back "
            "without a ruling")

    def test_the_workflow_file_a_run_uses_is_resolvable(self):
        from autornd.engine.workflow import workflow_path

        assert workflow_path().endswith(".yaml")


@pytest.mark.asyncio
class TestTheClockIsInstrumented:
    """A run that expires must already say where the time went. The settling
    run for B7 costs real money; "it timed out" is a reading, not a diagnosis."""

    async def test_every_executed_node_reports_its_wall_clock(self):
        from tests.test_graph import BASE, _run

        state, _ = await _run({**BASE, "validate": {"green": True}})
        timed = [s for s in state.trace if not s.skipped]
        assert timed, "a completed run executed nodes"
        assert all(hasattr(s, "seconds") for s in timed)
        assert all(s.seconds >= 0 for s in timed)

    async def test_a_skipped_node_is_not_charged_time(self):
        from tests.test_graph import BASE, _run

        state, _ = await _run({**BASE, "validate": {"green": True}})
        for step in state.trace:
            if step.skipped:
                assert step.seconds == 0.0

    async def test_the_results_record_sums_seconds_per_phase(self, tmp_path):
        import json

        from autornd.evals.runner import ResultsLog, run_repeated
        from autornd.evals.scenario import parse
        from autornd.graph.spec import load
        from tests.test_evals import SETTINGS, scripted
        from tests.test_sweep_budget import billing_client

        log = ResultsLog(tmp_path / "r.jsonl")
        await run_repeated(
            [parse({"id": "s", "request": "Add retry"})],
            load("workflows/triage-classify.yaml"),
            lambda: billing_client(scripted("medium"), per_call=0.001),
            SETTINGS, repeat=1, results_log=log)
        log.close()

        unit = [json.loads(l) for l in (tmp_path / "r.jsonl").read_text().splitlines()
                if '"unit"' in l][0]
        assert "seconds_by_phase" in unit
        assert "triage" in unit["seconds_by_phase"]

    async def test_a_node_that_raises_still_reports_its_cost(self):
        """The expensive failures are the ones worth timing."""
        from autornd.graph.executor import ExecutionState, GraphExecutor
        from autornd.graph.spec import load
        from tests.test_graph import BASE, ScriptedRunner

        class Exploding(ScriptedRunner):
            async def run_ai(self, node, state):
                if node.id == "plan":
                    raise RuntimeError("upstream died")
                return await super().run_ai(node, state)

        runner = Exploding({**BASE, "validate": {"green": True}})
        executor = GraphExecutor(load("workflows/engineering-rnd.yaml"), runner,
                                 {"max_iterations": 5,
                                  "escalation_recovery_attempts": 3,
                                  "review_rework_attempts": 2})
        with pytest.raises(RuntimeError):
            await executor.run("Add retry")
        plan = [s for s in executor.state.trace if s.node_id == "plan"][0]
        assert plan.seconds >= 0.0
