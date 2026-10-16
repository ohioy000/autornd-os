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
    COVERAGE_NOTE,
    RED_NO_ANCHOR,
    UNANCHORED_DISSENT,
    UNVERIFIED_DISSENT,
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

# Words the doubles' scoping pass puts into the grounding the
# judge is given — the empty-store path, where the request
# analysis lands in the context every judge reads. R2's
# grounding-anchored cases quote them as their source.
GROUNDING_WORDS = ("the fixture instruction card "
                   "requires the zeroing step")


@pytest.fixture(autouse=True)
def _reset_counts():
    reset_normalisations()
    yield
    reset_normalisations()


def _double(router, serve_chat: bool = False):
    """A recording double around `router`: a callable taking
    (user_message, the call log so far) and returning the reply
    dict. Every call is recorded and billed like the real
    client's (convention 7), and every network method the
    double does not serve is sealed.

    `serve_chat` wires `chat` through the same router. The
    search tier's lookup speaks through `chat`, not
    `chat_json` (research._lookup), so a run whose grounding
    reaches its maximum needs it served for that call to be
    recorded and billed like every other."""
    client = OpenRouterClient(api_key="test")
    calls: list[dict[str, str]] = []

    async def chat_json(function, system_prompt, user_message, **kw):
        calls.append({"function": function,
                      "user": user_message})
        data = router(user_message, calls)
        response = make_mock_response(data, f"mock-{function}")
        client._account(function, response.cost)
        return data, response

    async def chat(function, system_prompt, user_message, **kw):
        calls.append({"function": function,
                      "user": user_message})
        data = router(user_message, calls)
        response = make_mock_response(data, f"mock-{function}")
        client._account(function, response.cost)
        return response

    client.chat_json = AsyncMock(side_effect=chat_json)
    if serve_chat:
        client.chat = AsyncMock(side_effect=chat)
    seal_double(client)
    client.close = AsyncMock()
    return client, calls


async def _drive(workflow: str, router, request: str,
                 settings: dict | None = None,
                 spec: Any = None,
                 serve_chat: bool = False,
                 call_ceiling: int | None = None):
    """One run of the real graph behind the double.

    Returns (state, runner, calls) — the terminal state, the phase
    runner (whose `iterations` is the build history the record
    reads), and every model call the run made, prompts included.

    `spec` runs a mutated workflow file: the break-proofs that put
    a check back into a judges' fold load the spec, add the check
    to the fold's args, and drive that. `serve_chat` serves the
    search tier's `chat` calls (the grounding's lookup).
    `call_ceiling` sets the client's own call bound — the
    break-proof for the call limit ends the run with the client's
    ceiling exception, not a test assertion."""
    client, calls = _double(router, serve_chat=serve_chat)
    if call_ceiling is not None:
        client.call_ceiling = call_ceiling
    runner = PhaseRunner(client)
    state = await GraphExecutor(
        spec or load(f"workflows/{workflow}.yaml"), runner,
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
                # no hazard, and (R2, 2026-10-15) no kind and no
                # source_quote, so it is read as a wrong_fact that
                # shows no source: an unverified dissent.
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
        # the record, and the demotion is counted — an
        # unverified dissent since R2 (2026-10-15): a red that
        # states no kind is read as a wrong_fact, and a wrong_fact
        # that shows no source is a note the run cannot check.
        assert state.outputs["validate"].green is True
        assert normalisations_by_kind().get(UNVERIFIED_DISSENT) == 1
        # The plan's invented criteria changed nothing: one
        # iteration, one answer.
        assert [(i["iteration"], i["dissenting"])
                for i in runner.iterations] == [(1, [])]

    async def test_break_proof_the_same_dissent_anchored_fails_the_work(self):
        """Break-proof: give the objection its anchor (a failed
        ask, stated as the unmet ask it is) and the same script
        ends escalated with no answer — the outcome main
        45b59f1 produced for this very shape, where ANY red
        failed the work. The test above fails if the
        demotion is reverted, because this is what the run then
        does."""
        routes = self._routes(True)

        def anchored(msg, calls):
            data = routes(msg, calls)
            if "validate this implementation" in msg.lower():
                data = dict(data)
                # The one line: the anchor the criterion-shaped
                # objection did not carry. R2 (2026-10-15): the
                # ask number anchors an unmet_ask — the answer
                # gives nothing for the ask — so the kind is
                # stated alongside it.
                data["kind"] = "unmet_ask"
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
                    # The anchor: the ask the work fails. R2
                    # (2026-10-15): an omission is an
                    # unmet_ask — the answer gives nothing for
                    # the ask — and the ask number anchors it,
                    # unchanged.
                    red["kind"] = "unmet_ask"
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
                    # The anchor: the request's own words
                    # that show the answer false. R2
                    # (2026-10-15): a misstatement is a
                    # wrong_fact — the answer gives
                    # something for the ask and the judge
                    # says it is false — and a wrong_fact
                    # anchors only through a source_quote
                    # the free check finds in the request.
                    # The words occur in Q15 verbatim ("The
                    # fixture instruction requires zeroing
                    # the readout at zero displacement").
                    red["kind"] = "wrong_fact"
                    red["source_quote"] = ("zeroing the readout "
                                           "at zero displacement")
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
        # The demotion is an unverified dissent since R2
        # (2026-10-15): the unanchored red states no kind,
        # so it is read as a wrong_fact, and a wrong_fact
        # with no source_quote is a note the run cannot check.
        assert normalisations_by_kind().get(UNVERIFIED_DISSENT) == 1

    async def test_the_omitted_step_is_caught_revised_and_delivered(self):
        """The command's literal (c) script: the first answer
        omits the step ask's words. Validate's anchored failure
        makes it red — and coverage, the free check that judges
        the asks by construction (D51 (2)), fails with it,
        because the ask's words are absent from the answer. The
        revision receives the unmet ask and the failure's
        evidence; the second answer includes the step; the run
        completes. Coverage's fail is recorded and counted, but
        since the ruling of 2026-10-15 (R1) it is a note out of
        the judges' fold — validate's anchored dissent is the
        only judge that routes the revision."""
        state, runner, calls = await _drive(
            "engineering-rnd", self._routes_omitting(True), Q15)
        assert state.status == "completed"
        assert "zeroing the readout at zero displacement" in (
            state.outputs["implement"].summary)
        # Validate dissented on the first iteration, anchored
        # on the unmet ask. Coverage failed the same words
        # and is recorded red beside it — but out of the
        # fold since R1, a coverage_note, so the loop read
        # validate alone.
        assert [i["dissenting"] for i in runner.iterations] == [
            ["coverage", "validate"], []]
        assert normalisations_by_kind().get(COVERAGE_NOTE) == 1
        # The revision carries the failure and the unmet ask —
        # the ask's own words, and the judge's FAIL line.
        revisions = _revision_prompts(calls)
        assert len(revisions) == 1
        assert "zeroing the readout at zero displacement" in (
            revisions[0])
        assert "FAIL" in revisions[0]
        assert TestTheQ15Shape.OMITTED in revisions[0]

    async def test_the_omitted_step_ships_when_nothing_anchors(self):
        """The (c) counterfactual, as the ruling of 2026-10-15
        (R1) leaves it: strip the anchor, and the omission
        SHIPS. Coverage — the free check that judges the asks by
        construction — still fails on the ask's absent words,
        but R1 made it a note: out of the judges' fold, counted
        as a coverage_note, never blocking and never reaching a
        revision. Validate's unanchored red is demoted the same
        way (an unverified dissent since R2). Nothing anchors,
        the judges agree on the first iteration, and the answer
        that leaves the step out is delivered completed.

        Convention 17: this test asserted the opposite — that
        coverage held the loop on the ask's own words, so the
        omission could not ship unanchored. That was the
        pre-ruling behaviour, and R1 repealed it deliberately:
        the starved re-measurement held four correct answers
        back on exactly this check. The test is rewritten to
        assert the ruled outcome, and the break-proof is the
        test above, where the anchored validate dissent still
        catches the same omission."""
        state, runner, calls = await _drive(
            "engineering-rnd", self._routes_omitting(False), Q15)
        assert state.status == "completed"
        # Nothing held the loop: one iteration, the omission
        # delivered, the step's words absent from the answer.
        # Coverage's fail is in the record beside the
        # demoted validate — recorded, as R1 requires, and
        # counted as a coverage_note, but the fold read
        # neither, so the judges agreed on the first
        # iteration.
        assert len(runner.iterations) == 1
        assert [i["dissenting"] for i in runner.iterations] == [
            ["coverage"]]
        assert "zeroing the readout at zero displacement" not in (
            state.outputs["implement"].summary)
        # Both demotions counted as the notes they now are.
        assert state.outputs["validate"].green is True
        assert normalisations_by_kind().get(UNVERIFIED_DISSENT) == 1
        assert normalisations_by_kind().get(COVERAGE_NOTE) == 1


# ── (d) review anchors ──────────────────────────────────────────

class TestReviewAnchors:
    """The anchor table for review findings (R-e) and domain
    concerns (R-f), as R2 (2026-10-15) amended it. A high
    finding with no anchor is a note and ships; a finding
    anchored by ask number or by the request's own words
    blocks when its kind is unmet_ask; a wrong_fact blocks
    only through a source_quote the free check finds in the
    request or in the grounding the judge was given; a
    hazard anchors only through the answer's own words. A
    finding whose quote or source does not occur is a note."""

    @staticmethod
    def _routes(finding, grounding: bool = False):
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
            if ("an engineer is about to plan and carry out"
                    " the request below" in m):
                # The scoping pass the empty store runs: its
                # text is the grounding the judge was given.
                considerations = ([GROUNDING_WORDS]
                                  if grounding else [])
                return {"objective": "state the check's result",
                        "unknowns": [], "assumptions": [],
                        "considerations": considerations,
                        "blocking_unknowns": []}
            return {"findings": [], "queries": [], "brief": ""}
        return reply

    @pytest.mark.parametrize("finding,blocks,note", [
        # A high finding with no anchor and no kind: a
        # wrong_fact that shows no source — an
        # unverified dissent, a note, recorded, ships.
        ({"lens": "backend_engineer", "severity": "high",
          "detail": "the answer does not follow the house style guide"},
         False, UNVERIFIED_DISSENT),
        # An unmet_ask anchored by ask number: blocks.
        ({"lens": "backend_engineer", "severity": "high",
          "ask": 1, "kind": "unmet_ask",
          "detail": "the answer leaves the zeroing step out"},
         True, None),
        # An unmet_ask anchored by the request's own
        # words: blocks.
        ({"lens": "backend_engineer", "severity": "high",
          "quote": "zeroing the readout at zero displacement",
          "kind": "unmet_ask",
          "detail": "the answer leaves this step out"},
         True, None),
        # An unmet_ask whose quote does not occur in the
        # request: an unanchored dissent, a note.
        ({"lens": "backend_engineer", "severity": "high",
          "quote": "a requirement the request never states",
          "kind": "unmet_ask",
          "detail": "the answer does not meet it"},
         False, UNANCHORED_DISSENT),
        # R2's own case: a wrong_fact that shows no
        # source_quote. The claim cannot be checked, so
        # under D51 (5) it is unavailable — a note,
        # never blocking. Break-proof: were the kind
        # alone an anchor (the retired rule), this case
        # would escalate and the assertion fails.
        ({"lens": "backend_engineer", "severity": "high",
          "kind": "wrong_fact",
          "detail": "the answer states the step as optional"},
         False, UNVERIFIED_DISSENT),
        # A wrong_fact whose source_quote is not in the
        # request or the grounding: still unverifiable,
        # a note.
        ({"lens": "backend_engineer", "severity": "high",
          "kind": "wrong_fact",
          "source_quote": "a requirement no source states",
          "detail": "the answer does not meet it"},
         False, UNVERIFIED_DISSENT),
        # A wrong_fact whose source_quote occurs in the
        # request: anchored, blocks.
        ({"lens": "backend_engineer", "severity": "high",
          "kind": "wrong_fact",
          "source_quote": "zeroing the readout at zero displacement",
          "detail": "the answer calls the required step optional"},
         True, None),
        # A wrong_fact whose source_quote occurs in the
        # grounding the judge was given, not the request:
        # anchored, blocks. (The double's scoping pass
        # carries the words, so the grounding is real.)
        ({"lens": "backend_engineer", "severity": "high",
          "kind": "wrong_fact",
          "source_quote": GROUNDING_WORDS,
          "detail": "the answer skips the zeroing step the "
                    "instruction card requires"},
         True, None),
        # The hazard table (the review of 2026-10-14): a
        # hazard anchors only through the answer's own words
        # that state or instruct it, carried in hazard_quote.
        # A hazard with no quote: a note — the bool alone
        # cannot say what the answer does. Break-proof: were
        # the bool alone an anchor (the retired rule), this
        # case would escalate and the assertion fails.
        ({"lens": "backend_engineer", "severity": "high",
          "hazard": True,
          "detail": "the answer instructs shorting the fixture "
                    "to ground, which would damage the extensometer"},
         False, UNANCHORED_DISSENT),
        # A hazard whose quote is not in the answer: a note.
        ({"lens": "backend_engineer", "severity": "high",
          "hazard": True,
          "hazard_quote": "disconnect the fixture before "
                          "servicing",
          "detail": "the answer omits the service disconnect"},
         False, UNANCHORED_DISSENT),
        # A hazard in the answer's own words: blocks.
        ({"lens": "backend_engineer", "severity": "high",
          "hazard": True,
          "hazard_quote": "returns to zero and records "
                          "without re-zeroing",
          "detail": "the answer's return-to-zero instruction, "
                    "followed as written, damages the fixture"},
         True, None),
        # An omission framed as a hazard: the answer's own
        # words cannot state what is absent, so no quote can
        # anchor — a note.
        ({"lens": "backend_engineer", "severity": "high",
          "hazard": True,
          "hazard_quote": "zero the readout before each reading",
          "detail": "the answer omits the per-reading zero"},
         False, UNANCHORED_DISSENT),
    ])
    async def test_the_finding_table(self, finding, blocks, note):
        # The grounding-anchored case needs the double's
        # scoping pass to carry the words; every other
        # case runs on the empty grounding.
        grounding = finding.get("source_quote") == \
            GROUNDING_WORDS
        state, runner, calls = await _drive(
            "engineering-rnd",
            self._routes(finding, grounding=grounding), Q15)
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
            assert normalisations_by_kind().get(note, 0) >= 1

    @pytest.mark.parametrize("concern,blocks,note", [
        # An unanchored critical concern with no kind: a
        # wrong_fact that shows no source — an unverified
        # dissent, a note, never critical.
        ({"detail": "the answer does not follow the house style guide",
          "critical": True}, False, UNVERIFIED_DISSENT),
        # An unmet_ask anchored by ask number: critical,
        # and the work goes red.
        ({"detail": "the answer leaves the zeroing step out",
          "critical": True, "ask": 1, "kind": "unmet_ask"},
         True, None),
        # An unmet_ask anchored by the request's own words:
        # critical.
        ({"detail": "the answer leaves this step out",
          "critical": True,
          "quote": "zeroing the readout at zero displacement",
          "kind": "unmet_ask"}, True, None),
        # R2's own case: a wrong_fact that shows no
        # source_quote — an unverified dissent, a note.
        ({"detail": "the answer states the step as optional",
          "critical": True, "kind": "wrong_fact"},
         False, UNVERIFIED_DISSENT),
        # A wrong_fact whose source_quote occurs in the
        # request: critical, and the work goes red.
        ({"detail": "the answer calls the required step optional",
          "critical": True, "kind": "wrong_fact",
          "source_quote": "zeroing the readout at zero displacement"},
         True, None),
        # A wrong_fact whose source_quote occurs in the
        # grounding the judge was given: critical.
        ({"detail": "the answer skips the zeroing step the "
                    "instruction card requires",
          "critical": True, "kind": "wrong_fact",
          "source_quote": GROUNDING_WORDS},
         True, None),
        # The hazard table (the review of 2026-10-14), the
        # same four cases the review-finding table carries:
        # a hazard with no quote is a note — the bool alone
        # cannot say what the answer does. Break-proof: were
        # the bool alone an anchor (the retired rule), this
        # case would escalate and the assertion fails.
        ({"detail": "the answer instructs shorting the fixture to "
                    "ground, which would damage the extensometer",
          "critical": True, "hazard": True}, False, UNANCHORED_DISSENT),
        # A hazard whose quote is not in the answer: a note.
        ({"detail": "the answer omits the service disconnect",
          "critical": True, "hazard": True,
          "hazard_quote": "disconnect the fixture before "
                          "servicing"}, False, UNANCHORED_DISSENT),
        # A hazard in the answer's own words: critical.
        ({"detail": "the answer's return-to-zero instruction, "
                    "followed as written, damages the fixture",
          "critical": True, "hazard": True,
          "hazard_quote": "returns to zero and records "
                          "without re-zeroing"}, True, None),
        # An omission framed as a hazard: a note.
        ({"detail": "the answer omits the per-reading zero",
          "critical": True, "hazard": True,
          "hazard_quote": "zero the readout before each reading"},
         False, UNANCHORED_DISSENT),
    ])
    async def test_domain_review_follows_the_same_table(self, concern,
                                                       blocks, note):
        # The grounding-anchored cases need the double's
        # scoping pass to carry the words.
        grounding = concern.get("source_quote") == \
            GROUNDING_WORDS

        def reply(msg, calls):
            data = TestReviewAnchors._routes(
                {"lens": "backend_engineer", "severity": "high",
                 "detail": "unused"},
                grounding=grounding)(msg, calls)
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
            # the roster's, not one — and the kind is the
            # case's, as the table rows it.
            assert normalisations_by_kind().get(note, 0) >= 1


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
                            # An omission is an unmet_ask
                            # (R2, 2026-10-15): the ask
                            # number anchors it.
                            "kind": "unmet_ask",
                            "evidence": ["ask 1 (zeroing the "
                                         "readout at zero "
                                         "displacement): FAIL — "
                                         "the answer leaves the "
                                         "step out"]}
                return {"green": False,
                        "red_cause": "the answer states no verdict",
                        "failed_ask": 2,
                        # The verdict ask is unmet too: the
                        # answer gives nothing for it.
                        "kind": "unmet_ask",
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
                # A dissent that never clears: anchored, every
                # time. An omission is an unmet_ask (R2,
                # 2026-10-15): the ask number anchors it.
                return {"green": False,
                        "red_cause": "the answer omits an ask",
                        "failed_ask": 1,
                        "kind": "unmet_ask",
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
                        # An omission is an unmet_ask (R2,
                        # 2026-10-15): the ask number
                        # anchors it.
                        "kind": "unmet_ask",
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
                    # An omission is an unmet_ask (R2,
                    # 2026-10-15): the ask number
                    # anchors it.
                    "kind": "unmet_ask",
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
                                # An omission is an unmet_ask
                                # (R2, 2026-10-15): the ask
                                # number anchors it.
                                "kind": "unmet_ask",
                                "evidence": ["ask 1: FAIL"]}
                               if sum(1 for c in calls
                                      if "validate this implementation"
                                      in c["user"].lower()) == 1
                               else {"green": True, "red_cause": None,
                                     "evidence": ["all three asks: PASS"]}),
                lambda calls: {"green": False, "red_cause": "red",
                               "failed_ask": 1,
                               "kind": "unmet_ask",
                               "evidence": ["ask 1: FAIL"]}):
            state, runner, calls = await _drive(
                "verify-first", self._routes(validate), Q23)
            phases = _phases(calls)
            assert phases[0] == "triage"
            assert phases[1] == "asks"
            assert len(phases) - 2 <= 4
            assert len(phases) <= 6


# ── the ruling of 2026-10-15, scripted on the starved run's
#    own units ─────────────────────────────────────────────────────
# R1, R2 and R3 below are driven end to end through the real
# graph on the very units the starved re-measurement measured:
# F-Q10-r1's asks and first answer (R1), Q17-r3's critical
# finding (R2), and a grounding taken at its maximum (R3).
# Each carries its break-proof, and where the break-proof is a
# runnable outcome the test runs it beside the ruled outcome.

# Q10's request, verbatim from the frozen tier-2 questions —
# the unit the starved re-measurement held back in arm F.
Q10 = ("Write the cure-check sequence for an adhesive coupon in a "
       "guarded laboratory oven. The coupon and its temperature "
       "probe are already installed. The work instruction requires "
       "setting the oven to $120\\,^{\\circ}\\mathrm{C}$, waiting "
       "until the coupon temperature enters the inclusive band "
       "$118$–$122\\,^{\\circ}\\mathrm{C}$, then starting a "
       "$600\\,\\mathrm{s}$ timer. The coupon must remain inside "
       "that band throughout the timed hold; any excursion fails "
       "the run and no restart is permitted. At the end, assess "
       "the run, switch off heating, and leave the coupon inside "
       "until its probe reads $\\leq40\\,^{\\circ}\\mathrm{C}$ "
       "before removal. A completed log records an uninterrupted "
       "$600\\,\\mathrm{s}$ hold with minimum "
       "$119\\,^{\\circ}\\mathrm{C}$ and maximum "
       "$121\\,^{\\circ}\\mathrm{C}$. Include the acceptance "
       "criteria and this log's verdict.")

# The twelve asks the pipeline's own asks node proposed on
# F-Q10-r1, each a quote that occurs in the request verbatim, so
# the free anchoring check keeps every one.
Q10_ASKS = [
    ("Write the cure-check sequence for an adhesive coupon in a "
     "guarded laboratory oven", "step"),
    ("setting the oven to $120\\,^{\\circ}\\mathrm{C}$", "step"),
    ("waiting until the coupon temperature enters the inclusive "
     "band $118$–$122\\,^{\\circ}\\mathrm{C}$", "step"),
    ("then starting a $600\\,\\mathrm{s}$ timer", "step"),
    ("The coupon must remain inside that band throughout the "
     "timed hold", "constraint"),
    ("any excursion fails the run", "constraint"),
    ("no restart is permitted", "constraint"),
    ("assess the run", "step"),
    ("switch off heating", "step"),
    ("leave the coupon inside until its probe reads "
     "$\\leq40\\,^{\\circ}\\mathrm{C}$ before removal", "step"),
    ("Include the acceptance criteria", "step"),
    ("this log's verdict", "verdict"),
]

# F-Q10-r1's first answer, verbatim from the committed trace
# (docs/traces/20261015T140229Z-tier3-remeasure.jsonl, sha256
# 33ad32b8…). It states every ask's substance — including the
# setpoint, as "Set oven controller to 120°C" — but not ask 2's
# own words, so the free coverage check measures ask 2 at 40% of
# its terms and fails it. That fail is what the starved run's
# fold treated as a blocking dissent and held the answer back
# for: a correct answer kept on the bench while the run recorded
# no delivery.
F_Q10_R1_ANSWER = (
    "CURE-CHECK SEQUENCE — ADHESIVE COUPON IN GUARDED LABORATORY OVEN\n"
    "Precondition: Coupon and its temperature probe are already "
    "installed in the guarded oven. Operator wears appropriate "
    "thermal PPE.\n"
    "\n"
    "PROCEDURE (Steps 1–10)\n"
    "1. Confirm oven guard/door is closed and probe is reading "
    "coupon temperature (not ambient).\n"
    "2. Set oven controller to 120°C.\n"
    "3. Monitor the coupon probe. Wait until the temperature "
    "enters the inclusive band 118°C ≤ T ≤ 122°C. Do not start "
    "the timer before entry.\n"
    "4. Once inside the band, start the 600 s timer. Record "
    "start time and probe reading.\n"
    "5. CONSTRAINT — Hold requirement: The coupon must remain "
    "inside 118°C–122°C inclusive for the entire 600 s timed "
    "hold.\n"
    "6. CONSTRAINT — Excursion failure: If the probe reads "
    "<118°C or >122°C at any point during the hold, the run "
    "fails immediately. Record the excursion value and time.\n"
    "7. CONSTRAINT — No restart: A failed run is not restarted; "
    "do not re-initiate the 600 s hold for this coupon under "
    "this protocol.\n"
    "8. At the end of an uninterrupted 600 s hold, assess the "
    "run: verify timer completed, no excursions occurred, and all "
    "recorded temperatures are within 118°C–122°C.\n"
    "9. Switch off oven heating (set controller to off / disable "
    "heaters).\n"
    "10. Leave the coupon inside the oven with heating off. "
    "Monitor the probe until it reads ≤40°C. Only then remove "
    "the coupon.\n"
    "\n"
    "ACCEPTANCE CRITERIA (Ask 11)\n"
    "- Oven setpoint: 120°C.\n"
    "- Band entry: 118°C ≤ coupon temperature ≤ 122°C (inclusive) "
    "before timer start.\n"
    "- Hold duration: uninterrupted 600 s.\n"
    "- In-hold temperature: 118°C ≤ T ≤ 122°C at all monitored "
    "points; zero excursions permitted.\n"
    "- Failure: any excursion outside the band; no restart "
    "permitted.\n"
    "- Post-hold: coupon remains inside until probe reads ≤40°C; "
    "removal only after that.\n"
    "- Log assessment: the run is accepted only if the above are "
    "fully satisfied.\n"
    "\n"
    "LOG VERDICT (Ask 12)\n"
    "Recorded log: uninterrupted 600 s hold; minimum temperature "
    "119°C; maximum temperature 121°C.\n"
    "Assessment:\n"
    "- 119°C ≥ 118°C and 121°C ≤ 122°C → within inclusive band.\n"
    "- Range 119–121°C contains no excursion outside 118–122°C.\n"
    "- Hold duration is uninterrupted 600 s.\n"
    "- Therefore all acceptance criteria are met.\n"
    "VERDICT: PASS / ACCEPTED. The run complies with the "
    "cure-check sequence and may be recorded as successful. No "
    "restart is required (not applicable to a passing run). After "
    "assessment, heating is switched off and the coupon remains "
    "inside until ≤40°C per step 10.\n"
    "\n"
    "ASSUMPTIONS (not facts; apply unless corrected)\n"
    "- Human-operated SOP format; automated script adaptation "
    "would require explicit sampling-rate and interlock "
    "definitions.\n"
    "- Cool-down occurs with oven door closed and heaters off; "
    "active venting is not specified.\n"
    "- Probe measurement uncertainty/calibration tolerance is not "
    "applied to the 118–122°C window unless specified "
    "separately.\n"
    "- No post-cure mechanical/physical tests (e.g., lap shear, "
    "visual) are required for this thermal-profile verdict.\n"
    "- Sampling frequency is assumed adequate to capture any "
    "brief excursion; the log reports no such events.")

# The revision the R1 break-proof's fold demands: the same answer
# with step 2 stated as the request states it. Ask 2's term
# overlap rises from 40% to 60% — the check's floor is half — so
# the free check accepts the revision.
F_Q10_R1_REVISED = F_Q10_R1_ANSWER.replace(
    "2. Set oven controller to 120°C.",
    "2. Setting the oven to 120°C: set the oven controller to "
    "120°C.")


class TestR1CoverageIsANoteOnTheStarvedRunsOwnUnit:
    """R1 (the ruling of 2026-10-15), scripted on the unit the
    starved re-measurement held back: F-Q10-r1's own asks and
    its own first answer. Coverage fails that answer — ask 2's
    words are not the answer's words — and the ruling's outcome
    is that the run completes on the first iteration anyway,
    delivering the answer, because coverage is a note out of the
    judges' fold: its result is still recorded (the iteration
    lists it red) and a fail is counted as a coverage_note, but
    it never blocks and never reaches a revision. The break-proof
    is the counterfactual the starved run ran under: coverage
    back in the fold, and the same script revises."""

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
                return {"asks": [{"quote": quote, "kind": kind}
                                 for quote, kind in Q10_ASKS]}
            if "produce the answer to the following request" in m:
                return {"done": True, "green": True,
                        "red_cause": None, "iteration": 1,
                        "blocked_on": [],
                        "summary": F_Q10_R1_ANSWER}
            if "revise your previous implementation" in m:
                return {"done": True, "green": True,
                        "red_cause": None, "iteration": 2,
                        "blocked_on": [],
                        "summary": F_Q10_R1_REVISED}
            if "validate this implementation" in m:
                return {"green": True, "red_cause": None,
                        "evidence": ["all twelve asks: PASS"]}
            return {"findings": [], "queries": [], "brief": ""}
        return reply

    async def test_the_starved_answer_completes_on_iteration_one(self):
        state, runner, calls = await _drive(
            "verify-first", self._routes(), Q10)
        # R1's ruled outcome: the run completes on the first
        # iteration, delivering the answer the starved run held
        # back — the answer states every ask's substance.
        assert state.status == "completed"
        assert (state.outputs["implement"].summary
                == F_Q10_R1_ANSWER)
        assert len(runner.iterations) == 1
        # Coverage's fail is in the record — the iteration lists
        # it red, the way R1 requires — but out of the fold:
        # validate is green, the judges agreed on the first
        # iteration, and the fail is counted as a coverage_note.
        assert runner.iterations[0]["dissenting"] == ["coverage"]
        assert state.outputs["validate"].green is True
        assert normalisations_by_kind().get(COVERAGE_NOTE) == 1

    async def test_break_proof_coverage_back_in_the_fold_revisions(self):
        """Break-proof: the counterfactual the starved run ran
        under. Coverage back in the judges' fold, and the same
        script revises — the fold reads coverage's red, the
        revision states ask 2 as the request states it, and the
        free check accepts it (ask 2 at 60% of its terms). The
        test above fails if R1 is reverted, because this is what
        the run then does: two iterations, and a second answer
        the recorded unit never paid for."""
        spec = load("workflows/verify-first.yaml")
        # The fold, as it was before the ruling: coverage's
        # signal beside implement's and validate's.
        spec.get("judges").args["coverage"] = "coverage.passed"
        state, runner, calls = await _drive(
            "verify-first", self._routes(), Q10, spec=spec)
        assert state.status == "completed"
        assert len(runner.iterations) == 2
        assert runner.iterations[0]["dissenting"] == ["coverage"]
        assert runner.iterations[1]["dissenting"] == []
        assert (state.outputs["implement"].summary
                == F_Q10_R1_REVISED)


# Q17's scripted answer: it gives something for both asks — the
# strength, in the regulation's pounds unit, and the inspection
# interval — and states the strength as a number the enforceable
# text does not contain. That is the shape R2's wrong_fact
# names: the answer gives something for the ask, and the judge
# says it is false.
Q17_ANSWER = ("Under 29 CFR § 1910.147 (July 1, 2014 edition), "
              "the minimum unlocking strength required for "
              "tagout-device attachment means is 50 pounds (lb). "
              "The employer must inspect the energy-control "
              "procedure at least annually — once every 12 months — "
              "and between inspections whenever a change occurs "
              "that could affect the procedure's integrity.")

# The words the scripted scoping pass puts into the grounding the
# judge was given: the enforceable text names no number. They do
# not occur in the request, so a source_quote of them anchors in
# the grounding alone — R2's second anchor.
Q17_GROUNDING_WORDS = ("the enforceable text specifies no numeric "
                       "unlocking strength")

# Q17-r3's critical finding, verbatim from the committed trace —
# the dissent the starved run's arm E ended blocked on, under the
# pre-R2 rule that let an ask number anchor any kind.
Q17_R3_FINDING = {
    "lens": "Systems Architect",
    "severity": "critical",
    "detail": ("The answer assigns a minimum unlocking strength of "
               "50 pounds to tagout-device attachment means, but "
               "29 CFR § 1910.147(c)(5)(iii) does not specify a "
               "numeric value of 50 pounds in the July 1, 2014 "
               "edition. The regulation states that tagout devices "
               "must be 'substantial enough to prevent removal "
               "without the use of excessive force or unusual "
               "techniques' and lists design characteristics (e.g., "
               "non-reusable, self-locking), but it does not "
               "include any numeric strength requirement such as "
               "'50 pounds'. The value '50 pounds' appears in "
               "non-mandatory appendices or guidance documents, not "
               "in the enforceable text of the standard. Therefore, "
               "the answer fabricates a regulatory value not present "
               "in the cited section."),
    "ask": 2,
    "quote": "what minimum unlocking strength is required for "
             "tagout-device attachment means",
    "hazard": False,
    "hazard_quote": "",
}


class TestR2TheWrongFactThatShowsItsSource:
    """R2 (the ruling of 2026-10-15), scripted on Q17-r3's own
    critical finding: the answer states a 50-pound unlocking
    strength, and the judge says that is false — a wrong_fact. A
    wrong_fact anchors only through a source_quote the free check
    finds in the request or in the grounding the judge was given.
    Without an anchored source_quote the claim is a note — an
    unverified dissent, counted, never blocking, unavailable under
    D51 (5): the run cannot check it. The finding as the record
    holds it states no kind and no source, so it is read as a
    wrong_fact and ships as a note; the break-proof is the retired
    rule, under which the claim anchored itself and the run ended
    blocked.

    The triage is low-risk: the review team is then the one most
    relevant reviewer, so the demotion count is the finding's own,
    not the roster's."""

    @staticmethod
    def _routes(finding, grounding: bool = False):
        def reply(msg, calls):
            m = msg.lower()
            if "classify this engineering request" in m:
                return {"domains": ["backend"], "risk": "low",
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
                        "summary": Q17_ANSWER}
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
                        "resolution_directive": "Cite the section.",
                        "requires_human": True,
                        "rulings": [{"dissent": 1, "upheld": True,
                                     "reason": "the finding holds"}]}
            if ("an engineer is about to plan and carry out"
                    " the request below" in m):
                # The scoping pass the empty store runs. The
                # grounding-anchored case carries the words the
                # judge was given; every other case runs on the
                # bare request.
                considerations = ([Q17_GROUNDING_WORDS]
                                  if grounding else [])
                return {"objective": "state the strength and the interval",
                        "unknowns": [], "assumptions": [],
                        "considerations": considerations,
                        "blocking_unknowns": []}
            return {"findings": [], "queries": [], "brief": ""}
        return reply

    async def test_the_recorded_finding_ships_as_an_unverified_dissent(self):
        """The finding as the record holds it: no kind stated, so
        read as a wrong_fact (R2's default), and no source_quote —
        the claim shows nothing. The run cannot check it, so under
        D51 (5) it is unavailable: a note, counted as an
        unverified dissent, never blocking. The answer the starved
        run held back is delivered."""
        state, runner, calls = await _drive(
            "engineering-rnd", self._routes(Q17_R3_FINDING), Q17)
        assert state.status == "completed"
        assert state.outputs["implement"].summary == Q17_ANSWER
        # The finding was demoted, not obeyed: it is in the record
        # at the severity the demotion left it, and the demotion is
        # counted — once, because the low-risk team is one reviewer.
        recorded = state.outputs["review"].findings[0]
        assert recorded.severity == "medium"
        assert recorded.detail == Q17_R3_FINDING["detail"]
        assert normalisations_by_kind().get(UNVERIFIED_DISSENT) == 1

    async def test_a_source_quote_nowhere_anchored_ships_the_same_way(self):
        finding = dict(Q17_R3_FINDING, kind="wrong_fact",
                       source_quote="a requirement no source states")
        state, runner, calls = await _drive(
            "engineering-rnd", self._routes(finding), Q17)
        assert state.status == "completed"
        assert state.outputs["review"].findings[0].severity == "medium"
        assert normalisations_by_kind().get(UNVERIFIED_DISSENT) == 1

    async def test_a_source_quote_in_the_grounding_blocks(self):
        """The finding anchored by its source: the words occur in
        the grounding the judge was given (the scoping pass put
        them there), not in the request. Anchored, the critical
        finding blocks: the review says do not ship, the rework
        loop cannot clear it, and the escalation's autopsy asks
        for a human — the run ends blocked, the finding still
        critical in the record."""
        finding = dict(Q17_R3_FINDING, kind="wrong_fact",
                       source_quote=Q17_GROUNDING_WORDS)
        state, runner, calls = await _drive(
            "engineering-rnd",
            self._routes(finding, grounding=True), Q17)
        assert state.status == "blocked"
        recorded = state.outputs["review"].findings[0]
        assert recorded.severity == "critical"
        assert recorded.source_quote == Q17_GROUNDING_WORDS
        # Anchored, so nothing was demoted: no unverified dissent.
        assert normalisations_by_kind().get(UNVERIFIED_DISSENT, 0) == 0

    async def test_break_proof_without_the_source_check_the_claim_blocks(
            self, monkeypatch):
        """Break-proof: the retired rule, under which a wrong_fact
        anchored by its claim alone — no source shown. Drop the
        source check and the recorded finding, the very one that
        ships above, blocks: it stays critical, the review says do
        not ship, and the run ends blocked. The first test fails
        if R2 is reverted, because this is what the run then does."""
        import autornd.engine.phases as phases_module
        real = phases_module.dissent_anchored

        def retired_rule(ask, quote, hazard, asks, request, answer="",
                         hazard_quote="", kind="", source_quote="",
                         grounding=""):
            # The retired rule: the kind anchored the claim, and a
            # dissent that named no kind was read as a wrong_fact
            # that anchored itself.
            if not hazard and (kind or "wrong_fact") == "wrong_fact":
                return True
            return real(ask, quote, hazard, asks, request, answer,
                        hazard_quote, kind, source_quote, grounding)

        monkeypatch.setattr(phases_module, "dissent_anchored",
                            retired_rule)
        state, runner, calls = await _drive(
            "engineering-rnd", self._routes(Q17_R3_FINDING), Q17)
        assert state.status == "blocked"
        assert state.outputs["review"].findings[0].severity == "critical"


class TestR3TheCallBoundCountsGroundingAtItsMaximum:
    """R3 (the ruling of 2026-10-15): D51 (8)'s four model calls
    are counted after triage, asks AND grounding, so the bound is
    2 + grounding's maximum + 4. This run takes grounding at its
    maximum — the store holds more chunks than the rerank keeps,
    so the expansion, the rerank, the briefing and the lookup the
    briefing's blocking gaps name all fire — and still completes
    after the revision's check, inside ARM_F_CALL_LIMIT. The
    break-proof is the pre-amendment bound: at six calls the same
    script dies at the answer itself, the seventh call, before any
    check ran — which is what the pre-amendment bound did to every
    arm-F unit whose grounding reached its maximum."""

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
            if "write the search queries" in m:
                return {"queries": ["a query about the request"]}
            if "rank these documentation excerpts" in m:
                return {"ranking": [0, 1, 2, 3, 4]}
            if "write a short grounding briefing" in m:
                return {"briefing": "a grounding briefing",
                        "gaps": ["a gap"],
                        "blocking_gaps": ["a blocking gap"]}
            if "answer these engineering questions" in m:
                return {"answer": "a looked-up answer",
                        "citations": ["a source"]}
            if "produce the answer to the following request" in m:
                return {"done": True, "green": True,
                        "red_cause": None, "iteration": 1,
                        "blocked_on": [], "summary": Q23_ANSWER}
            if "revise your previous implementation" in m:
                return {"done": True, "green": True,
                        "red_cause": None, "iteration": 2,
                        "blocked_on": [],
                        "summary": Q23_ANSWER + " Revised."}
            if "validate this implementation" in m:
                red = not any("revise" in c["user"].lower()
                              for c in calls)
                if red:
                    return {"green": False,
                            "red_cause": "the answer omits an ask",
                            "failed_ask": 1,
                            # An omission is an unmet_ask (R2,
                            # 2026-10-15): the ask number
                            # anchors it.
                            "kind": "unmet_ask",
                            "evidence": ["ask 1 (the common "
                                         "extension): FAIL"]}
                return {"green": True, "red_cause": None,
                        "evidence": ["all three asks: PASS"]}
            return {"findings": [], "queries": [], "brief": ""}
        return reply

    @staticmethod
    def _populate_store(tmp_path):
        """A store with more chunks than the rerank keeps, so the
        rerank call itself fires — grounding's second of four
        calls. Returns the path the suite's store was at, for the
        caller's finally."""
        from autornd.config import settings
        from autornd.knowledge.context import reset_rerank_mode
        from autornd.knowledge.store import ingest_text

        before = settings.chromadb_path
        settings.chromadb_path = str(tmp_path / "r3-store")
        # The rerank mode latches per process; a fresh probe
        # per run, so the listwise call is made every time.
        reset_rerank_mode()
        for i in range(6):
            ingest_text(
                f"a distinct documentation chunk about the "
                f"request's subject, numbered {i}",
                tag="r3_doc")
        return before

    async def test_grounding_at_its_maximum_completes_inside_the_bound(
            self, tmp_path):
        from autornd.knowledge.store import COLLECTION_NAME  # noqa: F401

        before = self._populate_store(tmp_path)
        try:
            state, runner, calls = await _drive(
                "verify-first", self._routes(), Q23,
                serve_chat=True)
        finally:
            from autornd.config import settings
            settings.chromadb_path = before

        assert state.status == "completed"
        # answer, check, revision, check — four phase calls after
        # triage and asks, as the ruling counts them.
        assert _phases(calls) == ["triage", "asks", "implement",
                                  "validate", "implement", "validate"]
        # Grounding at its maximum: the expansion, the rerank, the
        # briefing and the lookup the briefing's blocking gaps
        # named — four calls, each by its prompt's own words.
        grounding = [c for c in calls if any(
            marker in c["user"].lower() for marker in (
                "write the search queries",
                "rank these documentation excerpts",
                "write a short grounding briefing",
                "answer these engineering questions"))]
        assert len(grounding) == 4
        # And the whole run inside the amended bound: triage, asks,
        # grounding's four at their maximum, and the four.
        from evals.tier3.runner import ARM_F_CALL_LIMIT, GROUNDING_MAX_CALLS
        assert len(calls) == 10
        assert len(calls) == ARM_F_CALL_LIMIT
        assert ARM_F_CALL_LIMIT == 2 + GROUNDING_MAX_CALLS + 4

    async def test_break_proof_the_pre_amendment_bound_ends_at_the_answer(
            self, tmp_path):
        """Break-proof: the pre-amendment bound of six. The same
        script — grounding at its maximum — dies at the answer
        itself, the seventh call, before any check ran: the bound
        that did not count grounding's calls ended exactly the
        runs R3 was written for. The ceiling is the client's own
        (the double bills through it, convention 7), so the
        exception is the run's, not the test's."""
        from autornd.evals.runner import CallCeilingExceeded

        before = self._populate_store(tmp_path)
        try:
            with pytest.raises(CallCeilingExceeded) as raised:
                await _drive(
                    "verify-first", self._routes(), Q23,
                    serve_chat=True, call_ceiling=6)
        finally:
            from autornd.config import settings
            settings.chromadb_path = before

        # The seventh call was the answer — triage, asks and
        # grounding's four are the six the old bound allowed, so
        # the run ended at the answer itself, before any check.
        assert "ceiling 6" in str(raised.value)
        assert "stopped at 7 model calls" in str(raised.value)
