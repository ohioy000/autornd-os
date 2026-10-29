"""Ruling D57's tests (command ARCH-20261028-129): the convergence repairs.

D51 named what kept a correct answer from shipping: a yardstick the run wrote
itself, vetoes without evidence, a terminal that threw the work away, and a
revision ratchet. D57 closes what was left of each, and these tests show it
end to end through the real graph, behind the recording double of
tests/test_d51_acceptance.py, with no provider:

- a revision receives the anchored dissents and nothing else (D57 (1));
- the independent check vetoes only on an anchored issue (D57 (2));
- a run that ends without a delivered answer gives its caller the candidate
  (D57 (3));
- the record says whether the build judges agreed, and how long each answer
  was (D57 (4));
- and so a correct first answer ships past every note.

Each test has its break-proof in the command's Task 6: the line that, put
back, fails it.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock

import pytest
import yaml

from autornd.api.routes import _detail
from autornd.config import settings
from autornd.engine.phases import run_doublecheck
from autornd.engine.workflow import WorkflowEngine
from autornd.models.verdicts import (
    UNANCHORED_DISSENT,
    UNVERIFIED_DISSENT,
    ImplementVerdict,
    normalisations_by_kind,
    reset_normalisations,
)
from autornd.models.workflow import WorkflowStatus
from autornd.routing.openrouter import OpenRouterClient
from tests.conftest import make_mock_response, seal_double
from tests.test_d51_acceptance import (
    Q15,
    Q15_ASKS,
    _double,
    _drive,
    _revision_prompts,
)

CORRECT = ("The check begins with zeroing the readout at zero displacement, "
           "then applies the reference displacement and records, increases "
           "and records, and returns to zero and records without re-zeroing. "
           "Signed errors: +0.010 mm, -0.030 mm, +0.005 mm. The overall "
           "verdict is fail.")
# Misstates the step as optional, and leaves out the words "the overall
# verdict", so coverage misses ask 2 while validate dissents on ask 1.
MISSTATED = ("Signed errors: +0.010 mm, -0.030 mm, +0.005 mm. Zeroing the "
             "readout at zero displacement is optional on an unloaded fixture.")
ANCHORED_FINDING = "ANCHORED-FINDING the zeroing step is stated as optional"
DEMOTED_FINDING = "DEMOTED-FINDING add a section on protective equipment"
LOW_FINDING = "LOW-FINDING consider a table of the readings"


@pytest.fixture(autouse=True)
def _reset_counts():
    reset_normalisations()
    yield
    reset_normalisations()


def _router(overrides=None):
    """The Q15 run. Every phase answers as a correct, agreeing team would;
    `overrides` maps a phase to a function (message, revised) -> reply."""
    overrides = overrides or {}

    def reply(msg, calls):
        m = msg.lower()
        revised = any("revise your previous implementation" in c["user"].lower()
                      for c in calls)
        routes = (
            ("classify this engineering request", "triage"),
            ("list what this request asks", "asks"),
            ("create an implementation plan", "plan"),
            ("review this implementation plan", "feasibility"),
            ("revise your previous implementation", "implement"),
            ("implementation for the following plan", "implement"),
            ("review this implementation from your domain perspective",
             "domain_review"),
            ("validate this implementation", "validate"),
            ("review this engineering work", "review"),
            ("independently", "doublecheck"),
            ("attempts all failed validation", "escalation"),
        )
        phase = next((p for marker, p in routes if marker in m), None)
        if phase in overrides:
            return overrides[phase](m, revised)
        if phase == "triage":
            return {"domains": ["backend"], "risk": "medium",
                    "specialists": ["backend_engineer", "test_engineer"],
                    "summary": "s", "unrecallable": False}
        if phase == "asks":
            return {"asks": Q15_ASKS}
        if phase == "plan":
            return {"ready": True, "blockers": [], "plan": "Write the check.",
                    "cost_estimate": None, "success_criteria": []}
        if phase == "feasibility":
            return {"feasible": True, "concerns": [], "blockers": []}
        if phase == "implement":
            return {"done": True, "green": True, "red_cause": None,
                    "iteration": 2 if revised else 1, "blocked_on": [],
                    "summary": CORRECT}
        if phase == "domain_review":
            return {"concerns": [], "critical": False}
        if phase == "validate":
            return {"green": True, "red_cause": None,
                    "evidence": ["ask 1: PASS", "ask 2: PASS"]}
        if phase == "review":
            return {"ship": True, "findings": [], "verdict": "Ship."}
        if phase == "doublecheck":
            return {"ship": True, "confidence": "high", "critical_issues": [],
                    "recommendations": [], "verdict": "Ship."}
        if phase == "escalation":
            return {"root_cause_analysis": "r", "architectural_correction": None,
                    "resolution_directive": "State the step as required.",
                    "requires_human": True, "rulings": []}
        return {"findings": [], "queries": [], "brief": ""}
    return reply


def _two_builders(risk="medium", unrecallable=False):
    """Triage with a second builder, so the domain review has a peer to
    draw: with one builder it makes no call at all."""
    return lambda m, revised: {
        "domains": ["backend"], "risk": risk,
        "specialists": ["backend_engineer", "firmware_engineer",
                        "test_engineer"],
        "summary": "s", "unrecallable": unrecallable}


def _misstated_then_correct(m, revised):
    return {"done": True, "green": True, "red_cause": None,
            "iteration": 2 if revised else 1, "blocked_on": [],
            "summary": CORRECT if revised else MISSTATED}


def _validate_anchored_on_ask_1(m, revised):
    if revised:
        return {"green": True, "red_cause": None, "evidence": ["ask 1: PASS"]}
    return {"green": False, "red_cause": "the zeroing step is stated as optional",
            "kind": "unmet_ask", "failed_ask": 1,
            "evidence": ["ask 1 (zeroing the readout): FAIL - stated as optional"]}


def _review_blocks_once(m, revised):
    if revised:
        return {"ship": True, "findings": [], "verdict": "Ship."}
    return {"ship": False, "verdict": "Do not ship.", "findings": [
        {"lens": "a", "severity": "critical", "detail": ANCHORED_FINDING,
         "ask": 1, "kind": "unmet_ask"},
        {"lens": "b", "severity": "critical", "detail": DEMOTED_FINDING},
        {"lens": "c", "severity": "low", "detail": LOW_FINDING}]}


# ── (1) a revision receives only the anchored dissents ──────────────

@pytest.mark.asyncio
class TestARevisionReceivesOnlyTheAnchoredDissents:

    async def test_a_coverage_miss_does_not_reach_the_revision(self):
        """Validate dissents on ask 1 and coverage misses ask 2's words. The
        revision is told about ask 1 and nothing about coverage, a note since
        R1; the note stays in the log for the autopsy and the record."""
        state, runner, calls = await _drive("full-team", _router({
            "implement": _misstated_then_correct,
            "validate": _validate_anchored_on_ask_1}), Q15)
        assert state.status == "completed", state.reason
        assert runner.iterations[0]["dissenting"] == ["coverage", "validate"]
        revision = _revision_prompts(calls)[0]
        assert "stated as optional" in revision
        assert "SUCCESS CRITERIA UNMET" not in revision
        assert "coverage" not in revision.lower().split("revise your previous implementation")[1]
        entry = runner.failure_log[0]
        assert [n.split(":")[0] for n in entry["notes"]] == ["coverage"]
        assert "coverage" not in entry["red_cause"]

    async def test_a_review_note_does_not_reach_the_rework(self):
        """Review blocks on one anchored finding beside a demoted critical
        finding and a low one. The rework is told about the anchored finding
        alone, once per reviewer, never as an object's repr; the notes stay
        in the log."""
        state, runner, calls = await _drive("full-team", _router({
            "review": _review_blocks_once}), Q15)
        assert state.status == "completed", state.reason
        revision = _revision_prompts(calls)[0]
        assert ANCHORED_FINDING in revision
        assert DEMOTED_FINDING not in revision
        assert LOW_FINDING not in revision
        assert "lens=" not in revision
        assert "SUCCESS CRITERIA UNMET" not in revision
        entry = runner.failure_log[-1]
        assert {f["detail"] for f in entry["review_findings"]} == {ANCHORED_FINDING}
        assert {f["detail"] for f in entry["review_notes"]} == {
            DEMOTED_FINDING, LOW_FINDING}
        assert entry["red_cause"].startswith("Review blocked on ")

    async def test_validate_evidence_reaches_a_revision_only_when_validate_dissents(self):
        """An anchored domain concern turns the implementation red while
        validate passes. The revision carries the concern, not validate's
        passing lines: they are not a dissent."""
        def domain(m, revised):
            if revised:
                return {"concerns": [], "critical": False}
            return {"concerns": [{"detail": "DOMAIN-CONCERN the step is optional",
                                  "critical": True, "ask": 1,
                                  "kind": "unmet_ask"}], "critical": True}

        def validate(m, revised):
            return {"green": True, "red_cause": None,
                    "evidence": ["ask 1: PASS VALIDATE-PASS-LINE"]}

        state, runner, calls = await _drive("full-team", _router({
            "triage": _two_builders(), "implement": _misstated_then_correct,
            "domain_review": domain, "validate": validate}), Q15)
        assert state.status == "completed", state.reason
        revision = _revision_prompts(calls)[0]
        assert "DOMAIN-CONCERN" in revision
        assert "VALIDATE-PASS-LINE" not in revision


# ── (2) the independent check vetoes only on an anchored issue ──────

ANSWER = ImplementVerdict(done=True, green=True, iteration=1, blocked_on=[],
                          summary=CORRECT)
ASKS = [{"number": 1, "quote": "zeroing the readout at zero displacement",
         "kind": "step"}]


async def _doublecheck(reply):
    client = OpenRouterClient(api_key="test")
    client.chat_json = AsyncMock(return_value=(reply, make_mock_response(reply)))
    seal_double(client)
    verdict, _ = await run_doublecheck(client, Q15, ANSWER, asks=ASKS)
    return verdict


def _check(*issues, ship=False):
    return {"ship": ship, "confidence": "high", "critical_issues": list(issues),
            "recommendations": [], "verdict": "v"}


@pytest.mark.asyncio
class TestTheIndependentCheckNeedsAnAnchor:

    async def test_an_unanchored_issue_is_a_note_and_the_work_ships(self):
        verdict = await _doublecheck(_check("R7 contradicts the schematic"))
        assert verdict.ship is True and verdict.vetoed is False
        assert verdict.critical_issues == []
        assert [n.detail for n in verdict.notes] == ["R7 contradicts the schematic"]
        # A bare claim states no kind, so R2 reads it as a wrong_fact,
        # and a wrong_fact with no source is an unverified dissent.
        assert normalisations_by_kind().get(UNVERIFIED_DISSENT) == 1

    async def test_an_unanchored_unmet_ask_is_an_unanchored_dissent(self):
        verdict = await _doublecheck(_check(
            {"detail": "a step is missing", "kind": "unmet_ask"}))
        assert verdict.vetoed is False
        assert normalisations_by_kind().get(UNANCHORED_DISSENT) == 1

    async def test_do_not_ship_with_no_issue_ships(self):
        verdict = await _doublecheck(_check())
        assert verdict.ship is True and verdict.vetoed is False

    async def test_an_issue_naming_its_ask_vetoes(self):
        verdict = await _doublecheck(_check(
            {"detail": "the step is wrong", "ask": 1, "kind": "unmet_ask"},
            ship=True))
        assert verdict.vetoed is True
        assert [i.severity for i in verdict.critical_issues] == ["critical"]

    async def test_an_issue_quoting_the_request_vetoes(self):
        verdict = await _doublecheck(_check(
            {"detail": "left out", "kind": "unmet_ask",
             "quote": "Do not adjust the instrument between readings"}))
        assert verdict.vetoed is True

    async def test_a_wrong_fact_without_its_source_is_unverified(self):
        verdict = await _doublecheck(_check(
            {"detail": "the limit is 0.015 mm", "kind": "wrong_fact"}))
        assert verdict.vetoed is False
        assert normalisations_by_kind().get(UNVERIFIED_DISSENT) == 1

    async def test_a_hazard_anchors_only_through_the_answers_words(self):
        quoted = await _doublecheck(_check(
            {"detail": "unsafe", "hazard": True, "kind": "hazard",
             "hazard_quote": "returns to zero and records without re-zeroing"}))
        unquoted = await _doublecheck(_check(
            {"detail": "unsafe", "hazard": True, "kind": "hazard",
             "hazard_quote": "remove the guard while it runs"}))
        assert quoted.vetoed is True
        assert unquoted.vetoed is False


# ── a correct first answer ships past every note ────────────────────

@pytest.mark.asyncio
class TestACorrectDraftShips:

    async def test_a_correct_first_answer_ships_past_every_note(self, monkeypatch):
        """Unrecallable work, so every judge runs. Each one objects without
        an anchor: the domain reviewer, validate, two reviewers and the
        independent check. Each objection is a note; the first answer ships,
        with no revision."""
        monkeypatch.setattr(settings, "model_premium", "test/premium-model")
        state, runner, calls = await _drive("full-team", _router({
            "triage": _two_builders(risk="high", unrecallable=True),
            "domain_review": lambda m, r: {
                "concerns": [{"detail": "feels light", "critical": True}],
                "critical": True},
            "validate": lambda m, r: {
                "green": False, "red_cause": "not convinced",
                "evidence": ["ask 1: unsure"]},
            "review": lambda m, r: {"ship": False, "verdict": "No.", "findings": [
                {"lens": "b", "severity": "critical", "detail": DEMOTED_FINDING},
                {"lens": "c", "severity": "low", "detail": LOW_FINDING}]},
            "doublecheck": lambda m, r: _check("R7 contradicts the schematic"),
        }), Q15)
        assert state.status == "completed", state.reason
        assert _revision_prompts(calls) == []
        assert state.outputs["implement"].summary == CORRECT
        assert "independent_verdict" in state.path
        assert state.outputs["independent_check"].vetoed is False


# ── (3) the candidate reaches the caller ────────────────────────────

def _engine_client(router):
    client, calls = _double(router)
    client.close = AsyncMock()
    return client


def _never_agreed(m, revised):
    return {"green": False, "red_cause": "the zeroing step is stated as optional",
            "kind": "unmet_ask", "failed_ask": 1,
            "evidence": ["ask 1: FAIL - stated as optional"]}


@pytest.mark.asyncio
class TestTheCandidateReachesTheCaller:

    async def test_a_run_that_ends_blocked_returns_its_last_answer(self, db_session):
        """Validate never agrees; the escalation needs a human; the run ends
        blocked. The caller reads the last answer, unendorsed, with its open
        dissent and its anchor."""
        engine = WorkflowEngine(_engine_client(_router({
            "implement": lambda m, r: {
                "done": True, "green": True, "red_cause": None, "iteration": 1,
                "blocked_on": [], "summary": MISSTATED},
            "validate": _never_agreed})), db_session)
        workflow = await engine.execute(Q15)
        await db_session.refresh(workflow, ["phases"])
        assert workflow.status is WorkflowStatus.BLOCKED
        candidate = _detail(workflow).candidate
        assert candidate is not None
        assert candidate["answer"] == MISSTATED
        assert candidate["endorsed"] is False
        assert [d["judge"] for d in candidate["open_dissents"]] == ["validate"]
        assert candidate["open_dissents"][0]["ask"] == 1
        assert candidate["approved"]["agreed"] is False
        assert "approved_answer" not in candidate

    async def test_the_agreed_answer_is_returned_when_the_last_differs(self, db_session):
        """The build judges agree on the first answer; review blocks it on an
        anchored finding, every time; validate dissents from every revision,
        and the run ends without an answer. The caller gets the last answer
        and the one the build judges agreed on."""
        def implement(m, revised):
            return {"done": True, "green": True, "red_cause": None,
                    "iteration": 2 if revised else 1, "blocked_on": [],
                    "summary": "REVISED " + CORRECT if revised else CORRECT}

        def review(m, revised):
            return {"ship": False, "verdict": "No.", "findings": [
                {"lens": "a", "severity": "critical", "detail": ANCHORED_FINDING,
                 "ask": 1, "kind": "unmet_ask"}]}

        def validate(m, revised):
            if revised:
                return _never_agreed(m, revised)
            return {"green": True, "red_cause": None, "evidence": ["ask 1: PASS"]}

        engine = WorkflowEngine(_engine_client(_router({
            "implement": implement, "review": review,
            "validate": validate})), db_session)
        workflow = await engine.execute(Q15)
        await db_session.refresh(workflow, ["phases"])
        assert workflow.status is not WorkflowStatus.COMPLETED
        candidate = _detail(workflow).candidate
        assert candidate["answer"].startswith("REVISED ")
        assert candidate["approved"]["agreed"] is True
        assert candidate["approved"]["latest_differs"] is True
        assert candidate["approved_answer"] == CORRECT

    async def test_a_completed_run_has_no_candidate(self, db_session):
        engine = WorkflowEngine(_engine_client(_router()), db_session)
        workflow = await engine.execute(Q15)
        await db_session.refresh(workflow, ["phases"])
        assert workflow.status is WorkflowStatus.COMPLETED
        assert _detail(workflow).candidate is None
        assert "candidate" not in [p.phase for p in workflow.phases]


# ── (4) the record ──────────────────────────────────────────────────

@pytest.mark.asyncio
class TestTheRecord:

    async def test_an_answer_agreed_beside_a_coverage_note_is_agreed(self):
        """Coverage misses ask 2's words and nothing else objects: the build
        judges agree, and the record says so, though the dissent list names
        coverage. Review then blocks on an anchored finding until the run
        ends, and the approved pointer finds the last agreed answer: before
        D57 it read the dissent list and found none."""
        def implement(m, revised):
            return {"done": True, "green": True, "red_cause": None,
                    "iteration": 2 if revised else 1, "blocked_on": [],
                    "summary": "REVISED " + MISSTATED if revised else MISSTATED}

        def review(m, revised):
            return {"ship": False, "verdict": "No.", "findings": [
                {"lens": "a", "severity": "critical", "detail": ANCHORED_FINDING,
                 "ask": 1, "kind": "unmet_ask"}]}

        state, runner, calls = await _drive("full-team", _router({
            "implement": implement, "review": review}), Q15)
        assert state.status != "completed"
        first = runner.iterations[0]
        assert first["dissenting"] == ["coverage"]
        assert first["agreed"] is True
        assert all(i["dissenting"] == ["coverage"] for i in runner.iterations)
        approved = state.watchdog.approved
        assert approved["agreed"] is True
        assert approved["index"] == len(runner.iterations) - 1

    async def test_each_iteration_records_its_answer_length(self):
        state, runner, calls = await _drive("full-team", _router({
            "implement": _misstated_then_correct,
            "validate": _validate_anchored_on_ask_1}), Q15)
        assert [i["answer_chars"] for i in runner.iterations] == [
            len(MISSTATED), len(CORRECT)]
        assert [i["agreed"] for i in runner.iterations] == [False, True]


class TestEveryBuildFoldIsTheSame:

    def test_every_build_fold_is_implement_and_validate(self):
        """The record's `agreed` is implement and validate both green. That
        is right only while every workflow's build fold is those two."""
        folds = {}
        for path in sorted(Path("workflows").glob("*.yaml")):
            for node in yaml.safe_load(path.read_text())["nodes"]:
                if node.get("id") == "judges" and node.get("check") == "judges_agree":
                    folds[path.stem] = node["args"]
        assert set(folds) == {"full-team", "lean", "verify-first"}
        for name, args in folds.items():
            assert args == {"implement": "implement.green",
                            "validate": "validate.green"}, name
