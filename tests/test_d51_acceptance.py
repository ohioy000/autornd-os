"""Ruling D51's acceptance tests (command ARCH-20261010-120).

The acceptance criteria the command enumerates, each driven end to
end through the real graph — GraphExecutor and the real PhaseRunner,
behind a double that routes by the prompt's own words and records
every call (convention 22: the test simulates the condition it
watches). Criteria (a), (k) and (l) are guarded by the existing
suites (the verbatim-ruling greps, test_scope_rule's D36 hash and
test_docs's anonymity); (e) is pinned from both sides in
tests/test_anchor_floor.py; (f) is pinned in tests/test_blocked_on.py.

Each test carries its break-proof: the one line that, reverted,
fails the assertion, with the failure it produces. Where the
break-proof is itself a runnable outcome, the test runs it — the
counterfactual is asserted beside the ruled outcome, so the test
proves it can fail.

The requests are the frozen tier-2 questions the stage-1 report
measured (evals/tier2/questions.json, frozen under D44): Q23, the
hand calculation whose plan wrote the exam; Q15, the step the
single call omitted; Q17, the regulation the pipeline cannot fetch.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock

import pytest

from autornd.graph.adapter import PhaseRunner
from autornd.graph.executor import GraphExecutor
from autornd.graph.spec import load
from autornd.models.verdicts import (
    RED_NO_ANCHOR,
    UNANCHORED_DISSENT,
    normalisations_by_kind,
    reset_normalisations,
)
from autornd.routing.openrouter import OpenRouterClient
from evals.golden.score_trace import answer_of
from evals.tier3.runner import UnitResult
from tests.conftest import make_mock_response, seal_double

SETTINGS = {"max_iterations": 5, "escalation_recovery_attempts": 3,
            "review_rework_attempts": 2}

# The requests, verbatim from the frozen tier-2 questions.
Q23 = ("An aluminum bar and a steel bar are mounted side by side between "
       "rigid end plates. Both bars are initially unstressed, have length "
       "$1.00\\,\\mathrm{m}$, and undergo the same axial extension. "
       "Aluminum area is $200\\,\\mathrm{mm^2}$ and Young's modulus is "
       "$70.0\\,\\mathrm{GPa}$; steel area is $100\\,\\mathrm{mm^2}$ and "
       "modulus is $200\\,\\mathrm{GPa}$. A total tensile load of "
       "$30.0\\,\\mathrm{kN}$ is applied to the end plates. Assume linear "
       "elasticity and no temperature change. Find the common extension, "
       "tensile stress in each bar, and force carried by each bar.")
Q15 = ("Write the displacement-channel check for a tensile-test extensometer "
       "already mounted on an unloaded calibration fixture. The fixture "
       "instruction requires zeroing the readout at zero displacement, "
       "applying a $1.000\\,\\mathrm{mm}$ reference displacement and "
       "recording the reading, then increasing to $2.000\\,\\mathrm{mm}$ "
       "and recording again, then returning to zero and recording without "
       "re-zeroing. Each nonzero reading must be within "
       "$\\pm0.020\\,\\mathrm{mm}$ of its reference, and the final zero "
       "reading must have magnitude no greater than $0.010\\,\\mathrm{mm}$; "
       "limits are inclusive. Do not adjust the instrument between readings. "
       "The log gives $1.010$, $1.970$, and $0.005\\,\\mathrm{mm}$ for "
       "those three readings. State each signed error as reading minus "
       "reference and the overall verdict.")
Q17 = ("Under $29$ CFR § $1910.147$, July 1, 2014 edition, what minimum "
       "unlocking strength is required for tagout-device attachment means, "
       "and how frequently must the employer inspect the energy-control "
       "procedure? Give the strength in the regulation's pounds unit and "
       "the inspection interval.")

# The asks the doubles propose — quotes that occur in the requests
# verbatim, so the free anchoring check keeps them.
Q23_ASKS = [
    {"quote": "the common extension", "kind": "value"},
    {"quote": "tensile stress in each bar", "kind": "value"},
    {"quote": "force carried by each bar", "kind": "value"},
]
Q15_ASKS = [
    {"quote": "zeroing the readout at zero displacement", "kind": "step"},
    {"quote": "the overall verdict", "kind": "verdict"},
]
Q17_ASKS = [
    {"quote": "minimum unlocking strength is required for "
              "tagout-device attachment means", "kind": "value"},
    {"quote": "how frequently must the employer inspect the "
              "energy-control procedure", "kind": "value"},
]

# The Q23 plan's invented criteria, as the stage-1 report found them:
# inline arithmetic, two routes, a format, kill triggers, a falsifier
# no hand calculation can satisfy.
INVENTED_CRITERIA = [
    "the working shows the arithmetic inline, not as a black-box result",
    "two independent routes to each stress agree",
    "the answer is presented as a table with one row per bar",
    "kill triggers fire on yielding and on eccentricity",
    "a measured 60 s falsifier demonstrates the result",
]

Q23_ANSWER = ("Common extension 0.882 mm; aluminum stress 61.8 MPa, "
              "steel stress 176.4 MPa; aluminum force 12.36 kN, steel "
              "force 17.64 kN. The common extension, tensile stress in "
              "each bar, and force carried by each bar.")


@pytest.fixture(autouse=True)
def _reset_counts():
    reset_normalisations()
    yield
    reset_normalisations()


def _double(router):
    """A recording double around `router`: a callable taking
    (user_message, the call log so far) and returning the reply
    dict. Every call is recorded and billed like the real
    client's (convention 7), and every network method the
    double does not serve is sealed."""
    client = OpenRouterClient(api_key="test")
    calls: list[dict[str, str]] = []

    async def chat_json(function, system_prompt, user_message, **kw):
        calls.append({"function": function,
                      "user": user_message})
        data = router(user_message, calls)
        response = make_mock_response(data, f"mock-{function}")
        client._account(function, response.cost)
        return data, response

    client.chat_json = AsyncMock(side_effect=chat_json)
    seal_double(client)
    client.close = AsyncMock()
    return client, calls


async def _drive(workflow: str, router, request: str,
                 settings: dict | None = None):
    """One run of the real graph behind the double.

    Returns (state, runner, calls) — the terminal state, the phase
    runner (whose `iterations` is the build history the record
    reads), and every model call the run made, prompts included.
    """
    client, calls = _double(router)
    runner = PhaseRunner(client)
    state = await GraphExecutor(
        load(f"workflows/{workflow}.yaml"), runner,
        settings or SETTINGS).run(request)
    return state, runner, calls


def _phases(calls):
    """The phase calls a run made, by the prompt's own first words —
    the count the acceptance criteria name. Grounding's research
    calls are not phase calls: they are the context the phases read,
    and the criteria exclude them ('besides grounding')."""
    markers = (
        ("classify this engineering request", "triage"),
        ("list what this request asks", "asks"),
        ("create an implementation plan", "plan"),
        ("review this implementation plan", "feasibility"),
        ("produce the implementation for the following plan",
         "implement"),
        ("produce the answer to the following request", "implement"),
        ("revise your previous implementation", "implement"),
        ("review this implementation from your domain perspective",
         "domain_review"),
        ("validate this implementation", "validate"),
        ("review this engineering work", "review"),
        ("attempts all failed validation", "escalation"),
    )
    named = []
    for call in calls:
        for marker, name in markers:
            if marker in call["user"].lower():
                named.append(name)
                break
    return named


def _revision_prompts(calls):
    """The revision prompts the run made — the implement calls after
    the first, which the implementer receives only the anchored
    dissents in."""
    return [c["user"] for c in calls
            if "revise your previous implementation"
            in c["user"].lower()]


# ── (b) the stage-1 route, closed ───────────────────────────────

class TestTheStage1RouteIsClosed:
    """The Q23 route that held 0 of 21 in arm E. The plan carries
    the Q23 plan's shape of invented criteria; the implementer
    returns the correct answer; validate dissents on a
    criterion-shaped objection with no anchor. Under D51 the
    dissent is a note and the answer ships."""

    @staticmethod
    def _routes(criterion_shaped_objection: bool):
        def reply(msg, calls):
            m = msg.lower()
            if "classify this engineering request" in m:
                return {"domains": ["backend"], "risk": "medium",
                        "specialists": ["backend_engineer",
                                        "test_engineer"],
                        "summary": "s"}
            if "list what this request asks" in m:
                return {"asks": Q23_ASKS}
            if "create an implementation plan" in m:
                return {"ready": True, "blockers": [],
                        "plan": "Compute the extension from stiffness "
                                "sharing; split the load by area and "
                                "modulus.",
                        "cost_estimate": None,
                        # The plan still writes the exam — D51 does
                        # not stop it writing, it stops it being the
                        # yardstick.
                        "success_criteria": INVENTED_CRITERIA}
            if ("review this implementation plan" in m
                    or "plan produced by systems architect" in m):
                return {"feasible": True, "concerns": [], "blockers": []}
            if "implementation for the following plan" in m:
                return {"done": True, "green": True, "red_cause": None,
                        "iteration": 1, "blocked_on": [],
                        "summary": Q23_ANSWER}
            if "review this implementation from your domain perspective" in m:
                return {"concerns": [], "critical": False}
            if "validate this implementation" in m:
                if not criterion_shaped_objection:
                    return {"green": True, "red_cause": None,
                            "evidence": ["all three asks: PASS"]}
                # The criterion-shaped objection: it judges the answer
                # against criteria the request never asked for, and
                # names no anchor — no failed ask, no request quote,
                # no hazard.
                return {"green": False,
                        "red_cause": ("the answer shows no inline "
                                      "arithmetic and no kill triggers"),
                        "evidence": ["inline arithmetic: ABSENT",
                                     "kill triggers: ABSENT"]}
            if "review this engineering work" in m:
                return {"ship": True, "findings": [], "verdict": "Ship."}
            if "attempts all failed validation" in m:
                return {"root_cause_analysis": "the answer omits an ask",
                        "architectural_correction": None,
                        "resolution_directive": "State the figure.",
                        "requires_human": False,
                        "rulings": [{"dissent": 1, "upheld": True,
                                     "reason": "no figure is stated"}]}
            return {"findings": [], "queries": [], "brief": ""}
        return lambda msg, calls: reply(msg, calls)

    async def test_the_answer_ships_and_the_dissent_is_a_note(self):
        state, runner, calls = await _drive(
            "engineering-rnd", self._routes(True), Q23)
        # The ruled outcome: completed, the answer delivered.
        assert state.status == "completed"
        assert (state.outputs["implement"].summary
                == Q23_ANSWER)
        # The dissent was demoted, not obeyed: validate is green in
        # the record, and the demotion is counted.
        assert state.outputs["validate"].green is True
        assert normalisations_by_kind().get(RED_NO_ANCHOR) == 1
        # The plan's invented criteria changed nothing: one
        # iteration, one answer.
        assert [(i["iteration"], i["dissenting"])
                for i in runner.iterations] == [(1, [])]

    async def test_break_proof_the_same_dissent_anchored_fails_the_work(self):
        """Break-proof: give the objection its anchor (a failed ask)
        and the same script ends escalated with no answer — the
        outcome main 45b59f1 produced for this very shape, where
        ANY red failed the work. The test above fails if the
        demotion is reverted, because this is what the run then
        does."""
        routes = self._routes(True)

        def anchored(msg, calls):
            data = routes(msg, calls)
            if "validate this implementation" in msg.lower():
                data = dict(data)
                # The one line: the anchor the criterion-shaped
                # objection did not carry.
                data["failed_ask"] = 1
            return data
        state, runner, calls = await _drive(
            "engineering-rnd", anchored, Q23)
        assert state.status == "escalated"
        # No answer is delivered: the candidate is kept, unendorsed.
        assert state.candidate is not None
        assert state.candidate["endorsed"] is False


# ── (c) the Q15 shape, caught ───────────────────────────────────

class TestTheQ15Shape:
    """The omission the single call made on Q15 (arm A omitted the
    zeroing step in 2 of its 3 units). The first answer names the
    step's words but states the step wrongly — optional, not
    required — so coverage, which checks the ask's words occur,
    passes and validate's anchored failure is the only catcher.
    The revision receives that failure and no notes; the second
    answer states the step as required, and the run completes."""

    MISSTATES = ("Signed errors: +0.010 mm, -0.030 mm, "
                 "+0.005 mm. Zeroing the readout at zero "
                 "displacement is optional on an unloaded "
                 "fixture; the overall verdict is fail.")
    CORRECT = ("The check begins with zeroing the readout at "
               "zero displacement, then applies the reference "
               "displacement and records, increases and records, "
               "and returns to zero and records without "
               "re-zeroing. Signed errors: +0.010 mm, -0.030 mm, "
               "+0.005 mm. The overall verdict is fail.")
    # The command's literal (c) script: the first answer
    # omits the step ask's words entirely. Coverage — the
    # free check that judges the asks by construction —
    # catches a word-omission regardless of any anchor, so
    # this shape and the misstatement shape above isolate
    # different mechanisms, and both are tested.
    OMITTED = ("Signed errors: +0.010 mm, -0.030 mm, "
               "+0.005 mm. The 1.970 mm reading fails its "
               "reference limit; the overall verdict is fail.")

    @staticmethod
    def _routes_omitting(anchored: bool):
        """The literal (c) script: the first answer leaves
        the step's words out, the revision includes them."""
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
                        "plan": "Write the check.", "cost_estimate": None,
                        "success_criteria": ["the check is written"]}
            if ("review this implementation plan" in m
                    or "plan produced by systems architect" in m):
                return {"feasible": True, "concerns": [], "blockers": []}
            if "implementation for the following plan" in m:
                revised = any("revise" in c["user"].lower()
                              for c in calls)
                return {"done": True, "green": True, "red_cause": None,
                        "iteration": 2 if revised else 1,
                        "blocked_on": [],
                        "summary": TestTheQ15Shape.CORRECT
                        if revised else TestTheQ15Shape.OMITTED}
            if "review this implementation from your domain perspective" in m:
                return {"concerns": [], "critical": False}
            if "validate this implementation" in m:
                revised = any("revise" in c["user"].lower()
                              for c in calls)
                if revised:
                    return {"green": True, "red_cause": None,
                            "evidence": ["ask 1 (zeroing step): PASS",
                                         "ask 2 (overall verdict): PASS"]}
                red = {"green": False,
                       "red_cause": "the answer omits the zeroing step",
                       "evidence": ["ask 1 (zeroing the readout at zero "
                                    "displacement): FAIL — the answer "
                                    "leaves the step out"]}
                if anchored:
                    red["failed_ask"] = 1
                return red
            if "review this engineering work" in m:
                return {"ship": True, "findings": [], "verdict": "Ship."}
            return {"findings": [], "queries": [], "brief": ""}
        return reply

    @staticmethod
    def _routes(anchored: bool):
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
                        "plan": "Write the check.", "cost_estimate": None,
                        "success_criteria": ["the check is written"]}
            if ("review this implementation plan" in m
                    or "plan produced by systems architect" in m):
                return {"feasible": True, "concerns": [], "blockers": []}
            if "implementation for the following plan" in m:
                # First answer misstates the step; the
                # revision states it as required.
                revised = any("revise" in c["user"].lower()
                              for c in calls)
                return {"done": True, "green": True, "red_cause": None,
                        "iteration": 2 if revised else 1,
                        "blocked_on": [],
                        "summary": TestTheQ15Shape.CORRECT
                        if revised else TestTheQ15Shape.MISSTATES}
            if "review this implementation from your domain perspective" in m:
                return {"concerns": [], "critical": False}
            if "validate this implementation" in m:
                revised = any("revise" in c["user"].lower()
                              for c in calls)
                if revised:
                    return {"green": True, "red_cause": None,
                            "evidence": ["ask 1 (zeroing step): PASS",
                                         "ask 2 (overall verdict): PASS"]}
                red = {"green": False,
                       "red_cause": "the answer makes the "
                                    "zeroing step optional",
                       "evidence": ["ask 1 (zeroing the readout "
                                    "at zero displacement): "
                                    "FAIL — the answer calls the "
                                    "required step optional"]}
                if anchored:
                    # The anchor: the ask the work fails.
                    red["failed_ask"] = 1
                return red
            if "review this engineering work" in m:
                return {"ship": True, "findings": [], "verdict": "Ship."}
            return {"findings": [], "queries": [], "brief": ""}
        return reply

    async def test_the_misstated_step_is_caught_revised_and_delivered(self):
        state, runner, calls = await _drive(
            "engineering-rnd", self._routes(anchored=True), Q15)
        assert state.status == "completed"
        # The wrongness was fixed: the step is stated as
        # required, not optional.
        assert "optional on an unloaded fixture" not in (
            state.outputs["implement"].summary)
        assert "zeroing the readout at zero displacement" in (
            state.outputs["implement"].summary)
        # One iteration, then the revision. Coverage passes
        # throughout — the ask's words occur in both answers —
        # so validate is the ONLY dissenting judge: the anchored
        # ask, not the plan's criteria, is what routes the
        # revision. (The old harness's stage-1 report: the
        # omission shipped because nothing read the asks.)
        assert [i["dissenting"] for i in runner.iterations] == [
            ["validate"], []]

    async def test_the_revision_prompt_carries_the_failure(self):
        """The revision receives the anchored failure — the ask's
        own words, through the unmet-criteria channel and the
        validate evidence — and nothing the request does not ask
        for."""
        state, runner, calls = await _drive(
            "engineering-rnd", self._routes(anchored=True), Q15)
        revisions = _revision_prompts(calls)
        assert len(revisions) == 1
        revision = revisions[0]
        # The failure: the ask it misstated, quoted.
        assert "zeroing the readout at zero displacement" in revision
        # And the judge's evidence line naming it.
        assert "FAIL" in revision
        # The first answer is reproduced for revision, not
        # regeneration (Ruling D33's channel).
        assert TestTheQ15Shape.MISSTATES in revision

    async def test_break_proof_strip_the_anchor_and_the_wrong_answer_ships(self):
        """Break-proof, the command's own words: strip the anchor
        and the wrong answer ships. The unanchored red is demoted
        to a note, validate is recorded green, coverage passes (the
        ask's words occur), the loop never iterates, and the first
        answer — the one that calls the required step optional — is
        delivered completed. This is what arm E's 20 no-answer units
        were rescued from, and what a reverted anchor would re-open.
        The discriminator against the (b) counterfactual: coverage
        cannot catch this shape, so only the anchor stands between
        the wrong answer and delivery."""
        state, runner, calls = await _drive(
            "engineering-rnd", self._routes(anchored=False), Q15)
        assert state.status == "completed"
        # The wrong answer shipped: no revision was ever made.
        assert _revision_prompts(calls) == []
        assert len(runner.iterations) == 1
        assert "optional on an unloaded fixture" in (
            state.outputs["implement"].summary)
        assert normalisations_by_kind().get(RED_NO_ANCHOR) == 1

    async def test_the_omitted_step_is_caught_revised_and_delivered(self):
        """The command's literal (c) script: the first answer
        omits the step ask's words. Validate's anchored failure
        makes it red — and coverage, the free check that judges
        the asks by construction (D51 (2)), dissents with it,
        because the ask's words are absent from the answer. The
        revision receives the unmet ask and the failure's
        evidence; the second answer includes the step; the run
        completes."""
        state, runner, calls = await _drive(
            "engineering-rnd", self._routes_omitting(True), Q15)
        assert state.status == "completed"
        assert "zeroing the readout at zero displacement" in (
            state.outputs["implement"].summary)
        # Both judges that read the asks dissented on the first
        # iteration: validate on its anchored failure, coverage
        # on the ask's absent words.
        assert [i["dissenting"] for i in runner.iterations] == [
            ["coverage", "validate"], []]
        # The revision carries the failure and the unmet ask —
        # the ask's own words, and the judge's FAIL line.
        revisions = _revision_prompts(calls)
        assert len(revisions) == 1
        assert "zeroing the readout at zero displacement" in (
            revisions[0])
        assert "FAIL" in revisions[0]
        assert TestTheQ15Shape.OMITTED in revisions[0]

    async def test_the_omitted_step_does_not_ship_even_unanchored(self):
        """The (c) break-proof, measured: strip the anchor, and
        the omission STILL does not ship — coverage holds the
        loop on the ask's own words, with no paid judge
        dissenting at all. The run iterates once on the free
        check alone, the revision includes the step, and the run
        completes with the step in the answer and the demotion
        counted. The command's literal break-proof ('the omission
        ships') does not hold for a word-omission on this branch,
        by the ruling's own construction: coverage judges the
        asks by construction, so an ask whose words are absent is
        caught before any anchor is consulted. The break-proof
        that isolates validate's anchor is the misstatement shape
        above, where the words occur and only the anchor stands
        between the wrong answer and delivery."""
        state, runner, calls = await _drive(
            "engineering-rnd", self._routes_omitting(False), Q15)
        assert state.status == "completed"
        # Coverage held the loop: two iterations, the omission
        # revised away, the step in the delivered answer.
        assert len(runner.iterations) == 2
        assert [i["dissenting"] for i in runner.iterations] == [
            ["coverage"], []]
        assert "zeroing the readout at zero displacement" in (
            state.outputs["implement"].summary)
        # The unanchored red was demoted, not obeyed.
        assert state.outputs["validate"].green is True
        assert normalisations_by_kind().get(RED_NO_ANCHOR) == 1


# ── (d) review anchors ──────────────────────────────────────────

class TestReviewAnchors:
    """The anchor table for review findings (R-e) and domain concerns
    (R-f). A high finding with no anchor is a note and ships; a
    finding anchored by ask number, by the request's own words, or
    by a hazard blocks; a finding whose quote does not occur in the
    request is a note. Domain review follows the same table for its
    critical flag."""

    @staticmethod
    def _routes(finding):
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
                        "plan": "Write the check.", "cost_estimate": None,
                        "success_criteria": ["the check is written"]}
            if ("review this implementation plan" in m
                    or "plan produced by systems architect" in m):
                return {"feasible": True, "concerns": [], "blockers": []}
            if "implementation for the following plan" in m:
                return {"done": True, "green": True, "red_cause": None,
                        "iteration": 1, "blocked_on": [],
                        "summary": TestTheQ15Shape.CORRECT}
            if "review this implementation from your domain perspective" in m:
                return {"concerns": [], "critical": False}
            if "validate this implementation" in m:
                return {"green": True, "red_cause": None,
                        "evidence": ["ask 1: PASS", "ask 2: PASS"]}
            if "review this engineering work" in m:
                return {"ship": False, "findings": [finding],
                        "verdict": "Do not ship."}
            if "attempts all failed validation" in m:
                return {"root_cause_analysis": "the review blocked",
                        "architectural_correction": None,
                        "resolution_directive": "Address the finding.",
                        "requires_human": False,
                        "rulings": [{"dissent": 1, "upheld": True,
                                     "reason": "the finding holds"}]}
            return {"findings": [], "queries": [], "brief": ""}
        return reply

    @pytest.mark.parametrize("finding,blocks", [
        # A high finding with no anchor: a note, recorded, ships.
        ({"lens": "backend_engineer", "severity": "high",
          "detail": "the answer does not follow the house style guide"},
         False),
        # Anchored by ask number: blocks.
        ({"lens": "backend_engineer", "severity": "high",
          "ask": 1,
          "detail": "the answer leaves the zeroing step out"},
         True),
        # Anchored by the request's own words: blocks.
        ({"lens": "backend_engineer", "severity": "high",
          "quote": "zeroing the readout at zero displacement",
          "detail": "the answer leaves this step out"},
         True),
        # A quote that does not occur in the request: a note.
        ({"lens": "backend_engineer", "severity": "high",
          "quote": "a requirement the request never states",
          "detail": "the answer does not meet it"},
         False),
        # A hazard: blocks.
        ({"lens": "backend_engineer", "severity": "high",
          "hazard": True,
          "detail": "the answer instructs shorting the fixture to "
                    "ground, which would damage the extensometer"},
         True),
    ])
    async def test_the_finding_table(self, finding, blocks):
        state, runner, calls = await _drive(
            "engineering-rnd", self._routes(finding), Q15)
        if blocks:
            assert state.status == "escalated"
        else:
            assert state.status == "completed"
            # The note is recorded — at the severity the demotion
            # left it, never blocking. The review team is
            # risk-scaled (two reviewers at medium), and each
            # demoted the same note, so the count is per reviewer.
            recorded = state.outputs["review"].findings[0]
            assert recorded.severity == "medium"
            assert recorded.detail == finding["detail"]
            assert normalisations_by_kind().get(UNANCHORED_DISSENT, 0) >= 1

    @pytest.mark.parametrize("concern,blocks", [
        # An unanchored critical concern: a note, never critical.
        ({"detail": "the answer does not follow the house style guide",
          "critical": True}, False),
        # Anchored by ask number: critical, and the work goes red.
        ({"detail": "the answer leaves the zeroing step out",
          "critical": True, "ask": 1}, True),
        # Anchored by the request's own words: critical.
        ({"detail": "the answer leaves this step out",
          "critical": True,
          "quote": "zeroing the readout at zero displacement"}, True),
        # A hazard concern: critical.
        ({"detail": "the answer instructs shorting the fixture to "
                    "ground, which would damage the extensometer",
          "critical": True, "hazard": True}, True),
    ])
    async def test_domain_review_follows_the_same_table(self, concern,
                                                       blocks):
        def reply(msg, calls):
            data = TestReviewAnchors._routes(
                {"lens": "backend_engineer", "severity": "high",
                 "detail": "unused"})(msg, calls)
            if "classify this engineering request" in msg.lower():
                # A second builder, so the peers roster the
                # domain review draws is not empty: with one
                # builder the review makes no call at all and
                # the table would never be exercised.
                return {"domains": ["backend"], "risk": "medium",
                        "specialists": ["backend_engineer",
                                        "firmware_engineer",
                                        "test_engineer"],
                        "summary": "s"}
            if "review this implementation from your domain perspective" \
                    in msg.lower():
                return {"concerns": [concern], "critical": concern["critical"]}
            return data
        state, runner, calls = await _drive("engineering-rnd", reply, Q15)
        if blocks:
            assert state.status == "escalated"
        else:
            assert state.status == "completed"
            kept = state.outputs["implement"].domain_concerns[0]
            assert kept.critical is False
            assert kept.detail == concern["detail"]
            # Team-size dependent, like the review-finding
            # table above: every judge that saw the unanchored
            # critical concern demoted it (the domain peer and
            # the risk-scaled review team), so the count is
            # the roster's, not one.
            assert normalisations_by_kind().get(UNANCHORED_DISSENT) >= 1


# ── (g) unavailable is not a fail ─────────────────────────────────

class TestUnavailableIsNotAFail:
    """Q17's shape: the ask's verification needs a source text — the
    regulation's July 1, 2014 edition — that the grounding does not
    hold. Unavailable is neither pass nor fail, never blocks, and is
    listed in the run's record."""

    async def test_an_unavailable_ask_never_blocks_and_is_listed(self):
        def reply(msg, calls):
            m = msg.lower()
            if "classify this engineering request" in m:
                return {"domains": ["backend"], "risk": "medium",
                        "specialists": ["backend_engineer",
                                        "test_engineer"],
                        "summary": "s"}
            if "list what this request asks" in m:
                return {"asks": Q17_ASKS}
            if "create an implementation plan" in m:
                return {"ready": True, "blockers": [],
                        "plan": "State the strength and the interval.",
                        "cost_estimate": None,
                        "success_criteria": ["the answer states both"]}
            if ("review this implementation plan" in m
                    or "plan produced by systems architect" in m):
                return {"feasible": True, "concerns": [], "blockers": []}
            if "implementation for the following plan" in m:
                return {"done": True, "green": True, "red_cause": None,
                        "iteration": 1, "blocked_on": [],
                        "summary": ("The minimum unlocking strength is "
                                    "50 lbf; the employer must inspect "
                                    "the energy-control procedure "
                                    "annually. minimum unlocking "
                                    "strength is required for "
                                    "tagout-device attachment means; "
                                    "how frequently must the employer "
                                    "inspect the energy-control "
                                    "procedure.")}
            if "review this implementation from your domain perspective" in m:
                return {"concerns": [], "critical": False}
            if "validate this implementation" in m:
                # The ask's verification needs the regulation's text,
                # which the grounding does not hold: unavailable, not
                # a failure, and named.
                return {"green": True, "red_cause": None,
                        "unavailable_asks": [1],
                        "evidence": [
                            "ask 1: UNAVAILABLE — the regulation's "
                            "July 1, 2014 edition is not in the "
                            "grounding; the answer states 50 lbf and "
                            "could not be checked against it",
                            "ask 2: UNAVAILABLE — the inspection "
                            "interval likewise"]}
            if "review this engineering work" in m:
                return {"ship": True, "findings": [], "verdict": "Ship."}
            return {"findings": [], "queries": [], "brief": ""}

        state, runner, calls = await _drive(
            "engineering-rnd", reply, Q17)
        # Never blocks: the run completes with the answer delivered.
        assert state.status == "completed"
        # And the record lists the ask whose verification was
        # unavailable — in the verdict the run kept.
        assert state.outputs["validate"].unavailable_asks == [1]


# ── (h) escalation rules on each open dissent ─────────────────────

class TestEscalationRulesOnEachDissent:
    """The escalation verdict carries a ruling per open dissent, typed
    and recorded; the directive the implementer receives addresses the
    upheld dissent; and the run that converges after the ruling
    completes."""

    async def test_a_ruling_per_open_dissent_and_the_directive_reaches_the_revision(self):
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
                        "plan": "Write the check.", "cost_estimate": None,
                        "success_criteria": ["the check is written"]}
            if ("review this implementation plan" in m
                    or "plan produced by systems architect" in m):
                return {"feasible": True, "concerns": [], "blockers": []}
            if "implementation for the following plan" in m:
                revised = any("revise" in c["user"].lower()
                              for c in calls)
                return {"done": True, "green": True, "red_cause": None,
                        "iteration": 2 if revised else 1,
                        "blocked_on": [],
                        "summary": TestTheQ15Shape.CORRECT
                        if revised else TestTheQ15Shape.MISSTATES}
            if "review this implementation from your domain perspective" in m:
                return {"concerns": [], "critical": False}
            if "validate this implementation" in m:
                # The build loop's five attempts all fail — the
                # first three on ask 1 (the zeroing step), the
                # last two on ask 2 (the overall verdict): two
                # open dissents in the log the autopsy reads. The
                # recovery attempt after the ruling is the sixth
                # validate call and passes.
                validates = sum(
                    1 for c in calls
                    if "validate this implementation"
                    in c["user"].lower())
                if validates >= 6:
                    return {"green": True, "red_cause": None,
                            "evidence": ["ask 1: PASS",
                                         "ask 2: PASS"]}
                if validates <= 3:
                    return {"green": False,
                            "red_cause": "the answer omits the "
                                         "zeroing step",
                            "failed_ask": 1,
                            "evidence": ["ask 1 (zeroing the "
                                         "readout at zero "
                                         "displacement): FAIL — "
                                         "the answer leaves the "
                                         "step out"]}
                return {"green": False,
                        "red_cause": "the answer states no verdict",
                        "failed_ask": 2,
                        "evidence": ["ask 2 (the overall verdict): "
                                     "FAIL — the answer states no "
                                     "verdict"]}
            if "attempts all failed validation" in m:
                # Two open dissents in the log (ask 1 failed three
                # times, ask 2 twice): one typed ruling each. Ask 1
                # holds against its anchor — the answer states no
                # zeroing step — and the directive addresses it.
                # Ask 2 does not hold (the answer states the
                # verdict, as asked), so nothing directs it.
                return {"root_cause_analysis": "the answer omits the "
                                               "zeroing step the "
                                               "request asks for",
                        "architectural_correction": None,
                        "resolution_directive": "Begin the check with "
                                                "zeroing the readout at "
                                                "zero displacement.",
                        "requires_human": False,
                        "rulings": [
                            {"dissent": 1, "upheld": True,
                             "reason": "the answer states no "
                                       "zeroing step"},
                            {"dissent": 2, "upheld": False,
                             "reason": "the verdict was stated, "
                                       "as asked"}]}
            if "review this engineering work" in m:
                return {"ship": True, "findings": [], "verdict": "Ship."}
            return {"findings": [], "queries": [], "brief": ""}

        state, runner, calls = await _drive(
            "engineering-rnd", reply, Q15)
        # The ruling let the revision through: the run completes.
        assert state.status == "completed"
        # The build loop exhausted its five attempts before the
        # autopsy ran (five validate calls), and the recovery
        # attempt was the sixth.
        validates = [c for c in calls
                     if "validate this implementation"
                     in c["user"].lower()]
        assert len(validates) == 6
        # The verdict carries the rulings, typed, in the record:
        # one per open dissent.
        escalation = state.outputs["escalation"]
        assert len(escalation.rulings) == 2
        first, second = escalation.rulings
        assert first.dissent == 1
        assert first.upheld is True
        assert first.reason == "the answer states no zeroing step"
        assert second.dissent == 2
        assert second.upheld is False
        assert second.reason == "the verdict was stated, as asked"
        # The directive the implementer receives addresses the
        # UPHELD dissent only: it reaches the revision prompt and
        # names the ask the ruling upheld (the zeroing step),
        # while the dissent that did not hold directed nothing.
        revisions = _revision_prompts(calls)
        # Four build-loop revisions (iterations 2-5) and the
        # recovery attempt the autopsy directed — five in all.
        assert len(revisions) == 5
        # The directive rides only the recovery revision: the
        # build-loop revisions predate the autopsy, so none of
        # them could carry it.
        assert all("PRINCIPAL ARCHITECT DIRECTIVE" not in r
                   for r in revisions[:-1])
        assert "PRINCIPAL ARCHITECT DIRECTIVE" in revisions[-1]
        assert "zeroing the readout at zero displacement" in revisions[-1]


# ── (i) the candidate ───────────────────────────────────────────

class TestTheCandidate:
    """A run that ends escalated or blocked after an implementation
    exists records its last answer as an unendorsed candidate, with
    its open dissents and their anchors; D38's approved pointer is
    computed at the terminal; and neither kind counts as delivered."""

    @staticmethod
    def _routes():
        def reply(msg, calls):
            m = msg.lower()
            if "classify this engineering request" in m:
                return {"domains": ["backend"], "risk": "medium",
                        "specialists": ["backend_engineer",
                                        "test_engineer"],
                        "summary": "s"}
            if "list what this request asks" in m:
                return {"asks": Q23_ASKS}
            if "create an implementation plan" in m:
                return {"ready": True, "blockers": [],
                        "plan": "Compute the extension.", "cost_estimate":
                        None, "success_criteria": ["computed"]}
            if ("review this implementation plan" in m
                    or "plan produced by systems architect" in m):
                return {"feasible": True, "concerns": [], "blockers": []}
            if "implementation for the following plan" in m:
                return {"done": True, "green": True, "red_cause": None,
                        "iteration": 1, "blocked_on": [],
                        "summary": Q23_ANSWER}
            if "review this implementation from your domain perspective" in m:
                return {"concerns": [], "critical": False}
            if "validate this implementation" in m:
                # A dissent that never clears: anchored, every time.
                return {"green": False,
                        "red_cause": "the answer omits an ask",
                        "failed_ask": 1,
                        "evidence": ["ask 1 (the common extension): "
                                     "FAIL — the answer states no "
                                     "figure"]}
            if "attempts all failed validation" in m:
                return {"root_cause_analysis": "the answer omits an ask",
                        "architectural_correction": None,
                        "resolution_directive": "State the figure.",
                        "requires_human": False,
                        "rulings": [{"dissent": 1, "upheld": True,
                                     "reason": "no figure is stated"}]}
            if "review this engineering work" in m:
                return {"ship": True, "findings": [], "verdict": "Ship."}
            return {"findings": [], "queries": [], "brief": ""}
        return reply

    async def test_an_exhausted_run_keeps_its_unendorsed_candidate(self):
        state, runner, calls = await _drive(
            "engineering-rnd", self._routes(), Q23)
        assert state.status == "escalated"
        # The candidate: the last answer, unendorsed, with its open
        # dissent and its anchor — the ask the dissent names.
        assert state.candidate is not None
        assert state.candidate["answer"] == Q23_ANSWER
        assert state.candidate["endorsed"] is False
        dissents = state.candidate["open_dissents"]
        assert len(dissents) == 1
        assert dissents[0]["judge"] == "validate"
        assert dissents[0]["ask"] == 1
        assert dissents[0]["hazard"] is False
        # D38's approved pointer is present at the escalated terminal,
        # and says honestly that no iteration was agreed.
        approved = state.watchdog.approved
        assert approved is not None
        assert approved["history"] == "present"
        assert approved["agreed"] is False

    async def test_answer_of_reports_both_kinds(self):
        """The record's reader: an approved iteration reads 'approved,
        not shipped'; an unendorsed candidate reads 'unendorsed
        candidate'. Neither is delivered."""
        state, runner, calls = await _drive(
            "engineering-rnd", self._routes(), Q23)
        unit = {
            "status": state.status,
            "verdicts": state.outputs,
            "watchdog": (state.watchdog.as_dict()
                         if state.watchdog is not None else None),
            "iterations": runner.iterations,
            "candidate": state.candidate,
        }
        answer, kind = answer_of(unit)
        assert kind == "unendorsed candidate"
        assert answer == Q23_ANSWER
        # The approved-iteration shape: a pointer at an iteration the
        # build judges agreed on, in a run that still ended escalated.
        approved_unit = {
            "status": "escalated",
            "verdicts": {},
            "watchdog": {"approved": {"index": 1, "agreed": True}},
            "iterations": [{"implement_summary": "a first answer"},
                           {"implement_summary": "an approved answer"}],
            "candidate": {"answer": "an approved answer",
                          "endorsed": False, "open_dissents": []},
        }
        answer, kind = answer_of(approved_unit)
        assert kind == "approved, not shipped"
        assert answer == "an approved answer"

    async def test_the_tier3_delivered_count_does_not_include_it(self):
        """Arm E delivers only what the harness ships: a unit whose
        answer is an unendorsed candidate is not delivered, whatever
        its status field says."""
        unendorsed = UnitResult(
            question_id="Q23", repetition=1, arm="E",
            status="delivered",
            delivered_kind="unendorsed candidate")
        assert unendorsed.delivered is False
        assert unendorsed.record()["delivered"] is False
        approved = UnitResult(
            question_id="Q23", repetition=1, arm="E",
            status="delivered",
            delivered_kind="approved, not shipped")
        assert approved.delivered is False
        shipped = UnitResult(
            question_id="Q23", repetition=1, arm="E",
            status="delivered", delivered_kind="shipped")
        assert shipped.delivered is True


# ── (j) verify-first ────────────────────────────────────────────

class TestVerifyFirst:
    """The workflow the ruling adds: triage, grounding, asks, one
    answer on the engineering tier with no plan, the free checks,
    one check on the judge tier, and a loop of two iterations that
    ends escalated when a dissent survives. At most four model calls
    after triage and asks: answer, check, revision, check."""

    @staticmethod
    def _routes(validate):
        def reply(msg, calls):
            m = msg.lower()
            if "classify this engineering request" in m:
                return {"domains": ["backend"], "risk": "medium",
                        "specialists": ["backend_engineer",
                                        "test_engineer"],
                        "summary": "s"}
            if "list what this request asks" in m:
                return {"asks": Q23_ASKS}
            if "produce the answer to the following request" in m:
                return {"done": True, "green": True, "red_cause": None,
                        "iteration": 1, "blocked_on": [],
                        "summary": Q23_ANSWER}
            if "revise your previous implementation" in m:
                return {"done": True, "green": True, "red_cause": None,
                        "iteration": 2, "blocked_on": [],
                        "summary": Q23_ANSWER + " Revised."}
            if "validate this implementation" in m:
                return validate(calls)
            return {"findings": [], "queries": [], "brief": ""}
        return reply

    async def test_the_file_loads_under_the_spec_validator(self):
        spec = load("workflows/verify-first.yaml")
        assert spec.name == "verify-first"
        # The ruled node list: triage, grounding, the asks, the
        # answer, the free checks, the judge, and the loop that
        # owns them.
        assert [n.id for n in spec.execution_order()] == [
            "triage", "asks", "asks_anchored", "context", "verify_loop"]
        # Not the standing workflow, and nothing routes to it:
        # the configured default resolves to engineering-rnd, and
        # no shipped workflow names this one.
        from autornd.config import settings
        assert (settings.autornd_workflow or "engineering-rnd") \
            == "engineering-rnd"
        for workflow in ("engineering-rnd", "lean"):
            text = (Path(__file__).parent.parent / "workflows"
                    / f"{workflow}.yaml").read_text(encoding="utf-8")
            assert "verify-first" not in text

    async def test_a_pass_completes_with_four_model_calls(self):
        state, runner, calls = await _drive(
            "verify-first",
            self._routes(lambda calls: {"green": True, "red_cause": None,
                                        "evidence": ["all three asks: PASS"]}),
            Q23)
        assert state.status == "completed"
        assert _phases(calls) == ["triage", "asks", "implement", "validate"]
        # No plan node: the answer is produced from the request and the
        # asks, and the task line names the request, not a plan.
        assert not any("create an implementation plan" in c["user"].lower()
                       for c in calls)
        implement = next(c for c in calls
                         if "produce the answer to the following request"
                         in c["user"].lower())
        assert "Plan:" not in implement["user"]
        # The record keeps the first answer beside the final one —
        # here they are the same answer, one iteration.
        assert len(runner.iterations) == 1
        assert runner.iterations[0]["implement_summary"] == Q23_ANSWER

    async def test_a_dissent_then_a_pass_completes_with_six(self):
        def validate(calls):
            n = sum(1 for c in calls
                    if "validate this implementation" in c["user"].lower())
            if n == 1:
                return {"green": False, "red_cause": "the answer omits "
                                                    "an ask",
                        "failed_ask": 1,
                        "evidence": ["ask 1 (the common extension): FAIL"]}
            return {"green": True, "red_cause": None,
                    "evidence": ["all three asks: PASS"]}

        state, runner, calls = await _drive(
            "verify-first", self._routes(validate), Q23)
        assert state.status == "completed"
        # answer, check, revision, check — six phase calls after
        # triage and asks... four after them, as the ruling counts.
        assert _phases(calls) == ["triage", "asks", "implement",
                                  "validate", "implement", "validate"]
        # The record keeps the first answer beside the final one, so
        # the readers can say what the check changed.
        assert len(runner.iterations) == 2
        assert runner.iterations[0]["implement_summary"] == Q23_ANSWER
        assert runner.iterations[1]["implement_summary"] == Q23_ANSWER + \
            " Revised."
        assert runner.iterations[0]["dissenting"] == ["validate"]
        assert runner.iterations[1]["dissenting"] == []

    async def test_a_persistent_dissent_ends_escalated_with_the_candidate_kept(self):
        def validate(calls):
            return {"green": False, "red_cause": "the answer omits an ask",
                    "failed_ask": 1,
                    "evidence": ["ask 1 (the common extension): FAIL"]}

        state, runner, calls = await _drive(
            "verify-first", self._routes(validate), Q23)
        assert state.status == "escalated"
        # The candidate is kept, unendorsed, with its open dissent and
        # its anchor — and the first and final answers are both in the
        # record.
        assert state.candidate is not None
        assert state.candidate["endorsed"] is False
        assert state.candidate["open_dissents"][0]["ask"] == 1
        assert len(runner.iterations) == 2
        assert runner.iterations[0]["implement_summary"] == Q23_ANSWER
        assert runner.iterations[1]["implement_summary"] == Q23_ANSWER + \
            " Revised."
        # The approved pointer is present at the escalated terminal.
        assert state.watchdog.approved is not None
        assert state.watchdog.approved["agreed"] is False

    async def test_no_run_exceeds_six_model_calls_besides_grounding(self):
        """Every path above — pass, dissent-then-pass, persistent
        dissent — stays inside the bound: triage, asks, and at most
        answer, check, revision, check. The assertion is over the
        phase calls of all three, run together."""
        for validate in (
                lambda calls: {"green": True, "red_cause": None,
                               "evidence": ["all three asks: PASS"]},
                lambda calls: ({"green": False, "red_cause": "red",
                                "failed_ask": 1,
                                "evidence": ["ask 1: FAIL"]}
                               if sum(1 for c in calls
                                      if "validate this implementation"
                                      in c["user"].lower()) == 1
                               else {"green": True, "red_cause": None,
                                     "evidence": ["all three asks: PASS"]}),
                lambda calls: {"green": False, "red_cause": "red",
                               "failed_ask": 1,
                               "evidence": ["ask 1: FAIL"]}):
            state, runner, calls = await _drive(
                "verify-first", self._routes(validate), Q23)
            phases = _phases(calls)
            assert phases[0] == "triage"
            assert phases[1] == "asks"
            assert len(phases) - 2 <= 4
            assert len(phases) <= 6
