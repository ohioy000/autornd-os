"""The review of 2026-10-14 — the #176 follow-up (Part 1).

The four false-fail and veto paths the D51 review found on the
reading sheet's 58 entries, each guarded by a test that carries
its break-proof (convention 22: the test simulates the condition
it watches, and the counterfactual is asserted beside the ruled
outcome, so the test proves it can fail):

- **Consistency** read the request's LaTeX '$' delimiters as a
  currency unit and failed five correct answers on a unit the
  request never states. The delimiter is stripped before figures
  are extracted, and a disagreement the check finds is a note —
  out of the judges' fold, counted, never a veto.
- **Fallback coverage** judged the whole request by word presence
  and failed five of seven correct answers on Q15. Coverage over
  a fallback ask is passed and not checked.
- **Anchoring** did not fold the math-mode machinery, so a quote
  of the request's LaTeX-quoted words did not anchor.
- **A hazard** blocked on the bool alone. A hazard anchors only
  through the answer's own words that state or instruct it,
  carried in `hazard_quote`; unquoted, it is a note.

The measurement the review was opened on is re-run here as a
replay of the committed reading sheet (autornd/evals/runner.py:
`replay_reading_sheet`), so the record's own entries decide
whether the defects are gone.
"""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import AsyncMock

import pytest

from autornd.engine import phases
from autornd.evals.runner import READING_SHEET, replay_reading_sheet
from autornd.graph.checks import (
    judges_agree,
    numbers_consistent,
)
from autornd.models.verdicts import (
    CONSISTENCY_NOTE,
    RED_NO_ANCHOR,
    normalisations_by_kind,
    reset_normalisations,
)
from autornd.models.workflow import PhaseResult, Workflow, WorkflowStatus
from autornd.routing.openrouter import OpenRouterClient
from tests.conftest import make_mock_response, seal_double
from tests.test_api import TestEverySpendingRoutePassesTheGate
from tests.test_d51_acceptance import (
    Q15,
    Q15_ASKS,
    SETTINGS,
    TestTheQ15Shape,
    _drive,
)


@pytest.fixture(autouse=True)
def _reset_counts():
    reset_normalisations()
    yield
    reset_normalisations()


def _entry(n: int) -> dict[str, Any]:
    """One entry of the committed reading sheet."""
    sheet = json.loads(READING_SHEET.read_text())
    return next(e for e in sheet["entries"] if e["entry"] == n)


# The scripted Q14 run: the request and the reading sheet's
# entry 3 answer, verbatim from the committed record.
Q14_REQUEST = str(_entry(3)["question"])
ENTRY3_ANSWER = str(_entry(3)["answer"])

# The asks the scripted run proposes — quotes that occur in
# Q14's request verbatim, so the free anchoring check keeps
# them, and entry 3's answer addresses all three.
Q14_ASKS = [
    {"quote": "raise $2.00\\,\\mathrm{kg}$ of liquid",
     "kind": "value"},
    {"quote": "no more than $120\\,\\mathrm{s}$",
     "kind": "constraint"},
    {"quote": "the smallest passing power", "kind": "value"},
]


# ── the reading-sheet replay ──────────────────────────────────

class TestTheReadingSheetReplay:
    """The review's acceptance measurement, re-run on the
    committed record: on the 58 entries, no '$' unit in any
    consistency record; fallback coverage passed and unchecked;
    fixture-ask coverage fails no correct answer."""

    @pytest.fixture()
    def replay(self):
        return replay_reading_sheet()

    def test_the_sheet_is_the_fifty_eight(self, replay):
        assert len(replay) == 58
        assert len({r["question_id"] for r in replay}) >= 2

    def test_no_dollar_unit_in_any_consistency_record(self, replay):
        # A conflict names its unit first — "unit: request
        # says ..., implementation says ...". The false fail
        # read the LaTeX '$' delimiter as a currency unit and
        # failed five correct answers (the sheet's entries 3,
        # 11, 42, 46, 50) on it. The delimiter is math markup,
        # not a unit: it is stripped from both texts before
        # figures are extracted, so no record carries it.
        # Break-proof: undo the strip and the five entries
        # return, each conflict reading "$: request says ...".
        for record in replay:
            for conflict in record["consistency"]["conflicts"]:
                assert not conflict.startswith("$: "), (
                    f"entry {record['entry']} failed on a "
                    f"currency unit: {conflict}")

    def test_fallback_coverage_is_passed_and_unchecked(self, replay):
        # On the sheet, the fixture's asks are the scorer's
        # summaries — they are not the request's own words, so
        # nothing anchors and every entry is judged over the
        # fallback. The fallback ask is the whole request, and
        # word presence cannot judge a whole request: coverage
        # is passed and recorded as not checked.
        # Break-proof: judge the fallback by word presence
        # (the retired rule) and the five correct Q15 answers
        # (the sheet's entries 17, 22, 32, 43, 48) fail.
        for record in replay:
            assert record["fallback"] is True, (
                f"entry {record['entry']} anchored a fixture ask")
            assert record["coverage"]["passed"] is True
            assert record["coverage"]["checked"] is False

    def test_fixture_ask_coverage_fails_no_correct_answer(
            self, replay):
        failed = [r["entry"] for r in replay
                  if r["resolved_pass"] and not r["coverage"]["passed"]]
        assert failed == []


# ── the scripted Q14 run ──────────────────────────────────────

class TestTheQ14ScriptedRun:
    """Item 1's scripted run: Q14, the reading sheet's entry 3
    answer (a correct answer), validate green, reviewers ship —
    and the run completes on iteration 1 in both workflows that
    carry the consistency check.

    Before the review, the figure extractor read the request's
    LaTeX '$' delimiters as a currency unit, the consistency
    check failed this very answer on a unit the request never
    states, and — in the judges' fold — that false fail looped
    the run to escalation. The check still runs and its result
    is still recorded; it is a note, so no loop turns on it.

    Break-proofs, both runnable:
    - put consistency back into the fold and a recorded fail
      dissents — the fold's passed is false, which is the
      loop's until-condition failing, the escalation path the
      (b) break-proof drives end to end;
    - a genuine contradiction in plain units still completes on
      iteration 1: the fail is recorded and counted, and
      nothing loops on it."""

    @staticmethod
    def _routes(answer: str):
        """The scripted run's double: validate green, reviewers
        ship, the given answer delivered first time."""

        def reply(msg, calls):
            m = msg.lower()
            if "classify this engineering request" in m:
                return {"domains": ["backend"], "risk": "medium",
                        "specialists": ["backend_engineer",
                                        "test_engineer"],
                        "summary": "s"}
            if "list what this request asks" in m:
                if "backoff" in m:
                    return {"asks": [
                        {"quote": "the retry backoff",
                         "kind": "constraint"}]}
                return {"asks": Q14_ASKS}
            if "create an implementation plan" in m:
                return {"ready": True, "blockers": [],
                        "plan": "Work the energy balance.",
                        "cost_estimate": None,
                        "success_criteria": [
                            "the energy balance is worked"]}
            if ("review this implementation plan" in m
                    or "plan produced by systems architect" in m):
                return {"feasible": True, "concerns": [],
                        "blockers": []}
            if ("implementation for the following plan" in m
                    or "produce the answer to the following request"
                    in m
                    or "revise your previous implementation" in m):
                return {"done": True, "green": True,
                        "red_cause": None, "iteration": 1,
                        "blocked_on": [], "summary": answer}
            if "review this implementation from your domain perspective" \
                    in m:
                return {"concerns": [], "critical": False}
            if "validate this implementation" in m:
                return {"green": True, "red_cause": None,
                        "evidence": ["all asks: PASS"]}
            if "review this engineering work" in m:
                return {"ship": True, "findings": [],
                        "verdict": "Ship."}
            if "attempts all failed validation" in m:
                return {"root_cause_analysis":
                            "unreachable in this script",
                        "architectural_correction": None,
                        "resolution_directive": "None.",
                        "requires_human": False,
                        "rulings": []}
            return {"findings": [], "queries": [], "brief": ""}

        return reply

    async def test_completes_on_iteration_one_in_engineering_rnd(
            self):
        state, runner, calls = await _drive(
            "full-team", self._routes(ENTRY3_ANSWER),
            Q14_REQUEST, SETTINGS)
        assert state.status == "completed"
        assert state.outputs["implement"].summary == ENTRY3_ANSWER
        # One iteration: the false fail no longer loops the run.
        assert [(i["iteration"], i["dissenting"])
                for i in runner.iterations] == [(1, [])]
        # The check ran and its result is recorded — no shared
        # unit, because every figure the request states is
        # wrapped for math mode and carries no unit the answer
        # shares.
        assert state.outputs["consistency"]["passed"] is True
        assert state.outputs["consistency"]["checked"] is False

    async def test_completes_on_iteration_one_in_verify_first(
            self):
        state, runner, calls = await _drive(
            "verify-first", self._routes(ENTRY3_ANSWER),
            Q14_REQUEST, SETTINGS)
        assert state.status == "completed"
        assert state.outputs["implement"].summary == ENTRY3_ANSWER
        assert [(i["iteration"], i["dissenting"])
                for i in runner.iterations] == [(1, [])]
        assert state.outputs["consistency"]["passed"] is True

    async def test_the_break_proof_a_genuine_fail_still_completes(
            self):
        # A genuine contradiction in plain units: the request
        # states 60 seconds, the answer states 90. Before the
        # review this failed the work through the fold; now the
        # fail is a note — recorded, counted, and nothing
        # loops on it.
        request = "Set the retry backoff to 60 seconds. " \
                  "State the backoff."
        answer = "The retry backoff is 90 seconds."
        state, runner, calls = await _drive(
            "full-team", self._routes(answer), request,
            SETTINGS)
        assert state.status == "completed"
        # The record is honest: the iteration lists the
        # consistency fail among the red signals. The run
        # completes all the same, because the fold — the
        # loop's exit condition — does not read it.
        assert [(i["iteration"], i["dissenting"])
                for i in runner.iterations] == [(1, ["consistency"])]
        # The fail is recorded, and counted as a note.
        assert state.outputs["consistency"]["passed"] is False
        assert normalisations_by_kind().get(CONSISTENCY_NOTE) == 1

    async def test_the_break_proof_back_in_the_fold_it_dissents(
            self):
        # Put consistency back into the fold — the counterfactual
        # the break-proof names — and a recorded fail dissents:
        # the fold's passed is false, which is the loop's
        # until-condition failing, so the run loops and ends
        # escalated with the candidate kept (the escalation
        # terminal the (b) break-proof drives end to end).
        request = "Set the retry backoff to 60 seconds. " \
                  "State the backoff."
        answer = "The retry backoff is 90 seconds."
        consistency = numbers_consistent(
            reference=request, implementation=answer)
        assert consistency.passed is False
        # The fold as the workflows pass it: the check's whole
        # output, `passed` and all.
        fold = judges_agree(
            implement=True,
            validate=True,
            coverage={"passed": True, "checked": True},
            consistency={**consistency.data,
                         "passed": consistency.passed,
                         "detail": consistency.detail})
        assert fold.passed is False
        assert "consistency" in fold.data["dissenting"]


# ── the hazard table through validate ─────────────────────────

class TestTheHazardNeedsItsQuote:
    """The hazard table through validate — the third judge the
    review of 2026-10-14 changed; the review and domain tables
    in the D51 acceptance suite carry the same four cases. A red
    hazard with no quote is a note: validate is green in the
    record and the answer ships. A hazard whose quote is not in
    the answer is a note. A hazard in the answer's own words
    blocks. An omission framed as a hazard is a note — the
    answer's own words cannot state what is absent.

    Break-proof: were the bool alone an anchor (the retired
    rule), the first case would end escalated and the test
    fails."""

    @staticmethod
    def _routes(red: dict[str, Any]):
        def reply(msg, calls):
            m = msg.lower()
            if "classify this engineering request" in m:
                return {"domains": ["backend"], "risk": "medium",
                        "specialists": ["backend_engineer",
                                        "test_engineer"],
                        "summary": "s"}
            if "list what this request asks" in m:
                return {"asks": Q15_ASKS}
            if "create an implementation plan" in m:
                return {"ready": True, "blockers": [],
                        "plan": "Write the check.",
                        "cost_estimate": None,
                        "success_criteria": ["the check is written"]}
            if ("review this implementation plan" in m
                    or "plan produced by systems architect" in m):
                return {"feasible": True, "concerns": [],
                        "blockers": []}
            if ("implementation for the following plan" in m
                    or "revise your previous implementation" in m):
                return {"done": True, "green": True,
                        "red_cause": None, "iteration": 1,
                        "blocked_on": [],
                        "summary": TestTheQ15Shape.CORRECT}
            if "review this implementation from your domain perspective" \
                    in m:
                return {"concerns": [], "critical": False}
            if "validate this implementation" in m:
                return red
            if "review this engineering work" in m:
                return {"ship": True, "findings": [],
                        "verdict": "Ship."}
            if "attempts all failed validation" in m:
                return {"root_cause_analysis":
                            "the answer states a hazard",
                        "architectural_correction": None,
                        "resolution_directive": "Quote the words.",
                        "requires_human": False,
                        "rulings": []}
            return {"findings": [], "queries": [], "brief": ""}

        return reply

    @pytest.mark.parametrize("red,ends", [
        # A hazard with no quote: a note — the bool alone
        # cannot say what the answer does. Break-proof: were
        # the bool alone an anchor (the retired rule), this
        # case would end escalated and the assertion fails.
        ({"green": False,
          "red_cause": "the answer instructs shorting the fixture "
                        "to ground",
          "evidence": ["hazard: the answer instructs shorting"],
          "hazard": True},
         "completed"),
        # A hazard whose quote is not in the answer: a note.
        ({"green": False,
          "red_cause": "the answer omits the service disconnect",
          "evidence": ["hazard: the answer omits the disconnect"],
          "hazard": True,
          "hazard_quote": "disconnect the fixture before servicing"},
         "completed"),
        # A hazard in the answer's own words: blocks.
        ({"green": False,
          "red_cause": "the answer's return-to-zero instruction "
                        "damages the fixture",
          "evidence": ["hazard: the return-to-zero instruction"],
          "hazard": True,
          "hazard_quote": "returns to zero and records without "
                          "re-zeroing"},
         "escalated"),
        # An omission framed as a hazard: the answer's own words
        # cannot state what is absent, so no quote can anchor —
        # a note.
        ({"green": False,
          "red_cause": "the answer omits the per-reading zero",
          "evidence": ["hazard: the answer omits the zero"],
          "hazard": True,
          "hazard_quote": "zero the readout before each reading"},
         "completed"),
    ])
    async def test_the_validate_hazard_table(self, red, ends):
        state, runner, calls = await _drive(
            "full-team", self._routes(red), Q15)
        assert state.status == ends
        if ends == "completed":
            # The unanchored hazard was demoted to a note:
            # validate is green in the record, and the
            # demotion is counted.
            assert state.outputs["validate"].green is True
            assert normalisations_by_kind().get(RED_NO_ANCHOR) == 1


# ── the doublecheck takes a verify-first run ──────────────────

class TestTheDoublecheckTakesAVerifyFirstRun:
    """Item 5: the doublecheck endpoint requires the implement
    phase — the plan is not required, because a verify-first
    run has none. A workflow whose only verdict is an implement
    phase is doublechecked, not refused."""

    @staticmethod
    async def _workflow_with_implement_only(db_session) -> int:
        w = Workflow(request="check me without a plan",
                     status=WorkflowStatus.COMPLETED)
        db_session.add(w)
        await db_session.flush()
        db_session.add(PhaseResult(
            workflow_id=w.id, phase="implement", iteration=1,
            verdict_json=json.dumps({"done": True, "green": True,
                                     "summary": "s", "iteration": 1}),
            model_used="test", cost=0.001))
        await db_session.commit()
        return w.id

    async def test_a_verify_first_run_is_doublechecked(
            self, api_client, db_session, monkeypatch):
        made = await TestEverySpendingRoutePassesTheGate(
        )._prepared(monkeypatch)
        one = await self._workflow_with_implement_only(db_session)

        resp = await api_client.post(
            f"/api/workflows/{one}/doublecheck")
        assert resp.status_code == 200, (
            "the endpoint must require the implement phase, "
            "not the plan")
        assert "verdict" in resp.json()["data"]
        assert len(made) == 1


# ── the asks node dispatches without max_tokens ───────────────

class TestRunAsksDispatchesWithoutMaxTokens:
    """Item 6: the asks node dispatches with no max_tokens —
    the client's own default (16384, as triage), not the plan
    tier's ceiling. The asks node proposes a quote list, not a
    deliverable; the plan ceiling was never measured for it."""

    async def test_the_asks_dispatch_carries_no_max_tokens(self):
        client = OpenRouterClient(api_key="test")
        dispatched: list[dict[str, Any]] = []

        async def chat_json(function, system_prompt, user_message,
                            **kw):
            dispatched.append(kw)
            data = {"asks": [{"quote": "the retry backoff",
                              "kind": "constraint"}]}
            client._account(function, 0.001)
            return data, make_mock_response(data, "mock-triage")

        client.chat_json = AsyncMock(side_effect=chat_json)
        seal_double(client)
        client.close = AsyncMock()

        verdict, response = await phases.run_asks(
            client, "Set the retry backoff to 60 seconds.")
        assert verdict.asks[0].quote == "the retry backoff"
        assert len(dispatched) == 1
        assert "max_tokens" not in dispatched[0]
