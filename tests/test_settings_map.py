"""Ruling D39: one settings map for every path that runs a workflow.

The API path (engine/workflow.py) and the eval CLI (evals/cli.py) each kept a
hand-written settings_lookup, and the two drifted. The API path's had no
review_rework_attempts, so any blocking review there ended BLOCKED with
"ConditionError: loop 'review_rework_loop' wants max_iterations from setting
'review_rework_attempts', which is not available" (reproduced in
ARCH-20260930-095's response), while the eval path ran the designed rework
loop. Both now call autornd.config.settings_lookup().
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import select

from autornd.config import settings, settings_lookup
from autornd.engine.workflow import WorkflowEngine
from autornd.evals.runner import _isolated_store
from autornd.graph.spec import load
from autornd.models.workflow import PhaseResult, WorkflowStatus
from tests.conftest import make_mock_client

WORKFLOWS = sorted(
    (Path(__file__).resolve().parent.parent / "workflows").glob("*.yaml"))


def _setting_named_bounds() -> list[tuple[str, str, str]]:
    """(workflow file, node id, setting) for every node whose max_iterations
    names a setting. Read off the loaded specs, not the YAML text: the
    executor resolves exactly these, through GraphExecutor._budget."""
    found = []
    for path in WORKFLOWS:
        for node in load(path).nodes:
            if isinstance(node.max_iterations, str):
                found.append((path.name, node.id, node.max_iterations))
    return found


class TestEveryNamedLoopBoundIsInTheSharedMap:
    """D39's falsifier: a shipped workflow that names a setting the shared
    map does not carry. Enumerated from every workflows/*.yaml."""

    def test_the_subject_was_computed(self):
        # Convention 28: an empty enumeration would pass the guard vacuously.
        assert WORKFLOWS, "no workflows/*.yaml found beside the tests"
        bounds = _setting_named_bounds()
        assert bounds, "no workflow names a loop bound by setting; the guard checks nothing"
        assert ("engineering-rnd.yaml", "review_rework_loop",
                "review_rework_attempts") in bounds

    def test_every_setting_a_shipped_workflow_names_is_carried(self):
        known = settings_lookup()
        missing = [b for b in _setting_named_bounds() if b[2] not in known]
        assert not missing, (
            "a shipped workflow names a loop bound the shared settings map does "
            f"not carry (Ruling D39's falsifier): {missing}. The map carries "
            f"{sorted(known)}; add the setting to LOOP_BOUND_SETTINGS in "
            "autornd/config.py.")

    def test_the_map_reads_the_live_settings(self, monkeypatch):
        # A runtime settings change (RUNTIME_MUTABLE) must reach the next run.
        monkeypatch.setattr(settings, "review_rework_attempts", 7)
        assert settings_lookup()["review_rework_attempts"] == 7


# ── the API path reaches the rework loop ─────────────────────────────────

REQUEST = "Add retry with exponential backoff to the MQTT client"

# Lines of the phases' own prompts (autornd/engine/phases.py) that tell them
# apart: the implement prompt (produce or revise, D33) and the review prompt.
IMPLEMENT_PROMPT = "implementation for the following plan"
REVIEW_PROMPT = "ship: true if safe to ship"

# One reply serves every engineering and judge phase. The verdict models
# ignore keys they do not declare, and with MODEL_JUDGE unset the judge nodes
# fall back to the engineering tier (D35), so both functions answer alike.
_WORK = {"feasible": True, "concerns": [], "blockers": [], "critical": False,
         "done": True, "green": True, "red_cause": None,
         # Ruling D46 (1): a green with nothing behind it is the bug the rule
         # names — the double carries the assessment it claims.
         "evidence": ["Backoff is capped at 60s with jitter, the plan's one "
                      "criterion"],
         "summary": "Backoff is capped at 60s with jitter applied.",
         "ship": True, "findings": [], "verdict": "Ship."}
RESPONSES = {
    "triage": {"domains": ["backend"], "risk": "medium",
               "specialists": ["backend_engineer", "test_engineer"],
               "summary": "MQTT client retry", "unrecallable": False},
    "architecture": {"ready": True, "plan": "Cap backoff at 60s.", "blockers": [],
                     "success_criteria": ["Backoff is capped at 60s with jitter"]},
    "engineering": _WORK,
    "judge": _WORK,
    # requires_human ends the run at the recoverable gate, so every
    # rework_review recorded below belongs to review_rework_loop and none to
    # recovery_loop, which re-reviews through the same node.
    "escalation": {"root_cause_analysis": "Review and implement disagree.",
                   "architectural_correction": None,
                   "resolution_directive": "Resolve the review finding.",
                   "requires_human": True},
}

BLOCKING = {"lens": "systems_architect", "severity": "high",
            "detail": "Backoff has no ceiling on reconnect storms."}


def _client(review_ships_after: int | None):
    """The billing double, with review refusing to ship until it has seen more
    than `review_ships_after` implementations (None: it never ships). The
    wrapped double still bills every call."""
    client = make_mock_client(RESPONSES)
    original = client.chat_json.side_effect
    implements = {"n": 0}

    async def chat_json(function, system_prompt, user_message, **kwargs):
        data, response = await original(function, system_prompt, user_message, **kwargs)
        message = user_message.lower()
        if IMPLEMENT_PROMPT in message:
            implements["n"] += 1
        elif REVIEW_PROMPT in message:
            ships = (review_ships_after is not None
                     and implements["n"] > review_ships_after)
            data = {**data, "ship": ships, "findings": [] if ships else [BLOCKING],
                    "verdict": "Ship." if ships else "Blocked."}
        return data, response

    client.chat_json = AsyncMock(side_effect=chat_json)
    return client


async def _phases(session, workflow_id: int) -> list[PhaseResult]:
    result = await session.execute(
        select(PhaseResult).where(PhaseResult.workflow_id == workflow_id))
    return list(result.scalars())


@pytest.fixture
def bounds(monkeypatch):
    """Distinct values for the three loop bounds, so a count of rework
    iterations can only come from review_rework_attempts. Set here rather
    than trusted from defaults, because the suite reads the owner's .env."""
    monkeypatch.setattr(settings, "max_iterations", 5)
    monkeypatch.setattr(settings, "escalation_recovery_attempts", 1)
    monkeypatch.setattr(settings, "review_rework_attempts", 4)
    monkeypatch.setattr(settings, "run_time_budget_seconds", None)


class TestTheAPIPathReachesTheReworkLoop:
    """Convention 22: drive WorkflowEngine itself, the API's entry point,
    into review_rework_loop with the billing double."""

    async def test_a_review_that_blocks_once_is_reworked_and_completes(
            self, db_session, bounds):
        with _isolated_store():
            workflow = await WorkflowEngine(_client(review_ships_after=1),
                                            db_session).execute(REQUEST)
        assert workflow.status == WorkflowStatus.COMPLETED, workflow.error
        assert workflow.error is None
        phases = await _phases(db_session, workflow.id)
        reviews = {(p.phase, p.iteration) for p in phases
                   if p.phase in ("review", "rework_review")}
        # The first review blocked; one rework iteration re-reviewed and shipped.
        assert reviews == {("review", 1), ("rework_review", 1)}

    async def test_the_configured_rework_bound_is_the_one_that_bounds_it(
            self, db_session, bounds):
        with _isolated_store():
            workflow = await WorkflowEngine(_client(review_ships_after=None),
                                            db_session).execute(REQUEST)
        phases = await _phases(db_session, workflow.id)
        rework = sorted({p.iteration for p in phases if p.phase == "rework_review"})
        # review_rework_attempts is 4; max_iterations (5) and
        # escalation_recovery_attempts (1) would each give a different count.
        assert rework == [1, 2, 3, 4]
        # Exhaustion takes the designed exit: escalation, which here requires
        # a human, so the run ends at the recoverable gate, not in a crash.
        assert [p.phase for p in phases].count("escalation") == 1
        assert workflow.status == WorkflowStatus.BLOCKED
        # The recoverable gate's on_fail_reason, from the workflow file.
        assert workflow.error.startswith("Escalation requires human intervention")
