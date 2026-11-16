"""The claim check, in shadow (the owner, 2026-11-14): a model lists the
figures a finished answer relies on, a free check keeps the ones the blind
samples can be asked, three samples state them, and the vote compares them.
Recorded only: the delivery and the answer are as they were."""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from autornd.api.routes import _detail
from autornd.graph.adapter import PhaseRunner
from autornd.graph.checks import MAX_CLAIMS, get_check
from autornd.graph.executor import GraphExecutor
from autornd.graph.spec import load
from autornd.routing import openrouter
from autornd.routing.openrouter import OpenRouterClient
from tests.test_switches import _with_decisions
from tests.test_recompute_vote import (REQUEST, SETTINGS, SUMMARY, _double,
                                       _workflow_router)

# Every test here is of a request judged to need a calculation: the
# recompute step runs only for those (owner's ruling, 2026-11-16).
pytestmark = pytest.mark.usefixtures("calculation_request")

BASE = "workflows/answer-and-recompute.yaml"
CLAIMS = "workflows/answer-and-recompute-claims.yaml"
CLAIM_NODES = ["claims", "claims_named", "claims_recompute", "claims_vote",
               "claims_switches"]
# SUMMARY states a 60 s cap. The second claim's value is not in the answer.
LISTED = [{"name": "timer cap", "value": 60, "unit": "s"},
          {"name": "retry limit", "value": 45, "unit": ""}]


def _kept(claims, text=SUMMARY):
    return get_check("claims_named")(claims=claims, text=text).data


class TestTheClaimsKept:
    def test_a_claim_whose_value_is_in_the_answer_is_kept_at_its_position(self):
        data = _kept([{"name": "retry limit", "value": 45, "unit": ""},
                      {"name": "timer cap", "value": 60, "unit": "s"}])
        assert data["asks"] == [{"number": 2, "quote": "timer cap", "kind": "value"}]
        assert data["results"] == [{"ask": 2, "value": 60, "unit": "s"}]
        assert data["kept"] == 1 and data["dropped"]["not_in_answer"] == 1

    @pytest.mark.parametrize("text", ["It is 12 years.", "It is 2.5 years.",
                                      "See rule 2a.", "About 1.2 years."])
    def test_a_number_is_matched_whole_not_inside_another(self, text):
        assert _kept([{"name": "period", "value": 2, "unit": "years"}],
                     text)["dropped"]["not_in_answer"] == 1

    @pytest.mark.parametrize("value", [2, 2.0, "2"])
    def test_a_number_is_found_however_it_is_typed(self, value):
        assert _kept([{"name": "period", "value": value, "unit": "years"}],
                     "At least 2 years, or 1,200 hours.")["kept"] == 1

    def test_a_number_written_with_a_thousands_comma_is_found(self):
        assert _kept([{"name": "hours", "value": 1200, "unit": "h"}],
                     "At least 2 years, or 1,200 hours.")["kept"] == 1

    def test_a_text_value_is_matched_as_an_identifier(self):
        data = _kept([{"name": "nitrate basis", "value": "as nitrogen", "unit": ""},
                      {"name": "arsenic basis", "value": "as arsenate", "unit": ""}],
                     "Nitrate is 10 mg/L (as Nitrogen).")
        assert [a["number"] for a in data["asks"]] == [1]

    def test_a_name_that_gives_the_value_away_is_dropped(self):
        data = _kept([{"name": "the 60 second cap", "value": 60, "unit": "s"}])
        assert data["kept"] == 0 and data["dropped"]["value_in_name"] == 1

    def test_a_repeated_name_and_an_empty_claim_are_dropped(self):
        data = _kept([{"name": "timer cap", "value": 60, "unit": "s"},
                      {"name": "Timer-cap", "value": 60, "unit": "s"},
                      {"name": "", "value": 60}, {"name": "x", "value": ""}])
        assert data["kept"] == 1
        assert data["dropped"]["repeated"] == 1 and data["dropped"]["empty"] == 2

    def test_no_more_than_the_limit_are_kept(self):
        data = _kept([{"name": f"cap {chr(97 + i)}", "value": 60, "unit": "s"}
                      for i in range(MAX_CLAIMS + 3)])
        assert data["kept"] == MAX_CLAIMS and data["dropped"]["over_limit"] == 3

    @pytest.mark.parametrize("value, stated, unit", [
        ("at least 3 years", 3.0, "years"), ("not less than 8 hours", 8.0, "hours"),
        ("<25 ns", 25.0, "ns"), ("\u2265 2 years", 2.0, "years")])
    def test_a_number_behind_a_bounding_word_is_that_number(self, value, stated, unit):
        data = _kept([{"name": "the limit", "value": value, "unit": ""}],
                     f"The limit is {value}.")
        assert data["results"] == [{"ask": 1, "value": stated, "unit": unit}]

    @pytest.mark.parametrize("value", ["3 years", "at least both ratings",
                                       "11.0-16.0 V", "odd-numbered years"])
    def test_any_other_value_is_kept_as_it_came(self, value):
        data = _kept([{"name": "the limit", "value": value, "unit": ""}],
                     f"The limit is {value}.")
        assert data["results"][0]["value"] == value

    def test_no_claim_is_not_checked_and_never_fails(self):
        result = get_check("claims_named")(claims=[], text=SUMMARY)
        assert result.passed and not result.checked and result.data["asks"] == []


def _router(listed=LISTED, sample_values=(30, 30, 60), claims_fail=False):
    """The answer-and-recompute double, with the claims list and the claim
    samples added. The ask vote agrees (60 against 60, 60, 60)."""
    base = _workflow_router(60, [60, 60, 60])

    def route(user_message, calls):
        if user_message.startswith("List the claims this answer relies on"):
            if claims_fail:
                raise ValueError("the claims model returned nothing usable")
            return {"claims": listed}
        if "relies on the values named below" in user_message:
            index = sum(1 for c in calls if "relies on the values named below"
                        in c["user"]) - 1
            return {"results": [{"ask": 1, "value": sample_values[index],
                                 "unit": "s"}]}
        return base(user_message, [c for c in calls if
                                   "relies on the values named below" not in c["user"]])

    return route


@pytest.fixture
def recompute_tier(monkeypatch):
    monkeypatch.setattr(openrouter.settings, "model_recompute",
                        "vendor/recompute-tier")
    monkeypatch.setitem(OpenRouterClient.FUNCTION_MODELS, "recompute",
                        "vendor/recompute-tier")


async def _run(path, router, decisions=None):
    client, calls = _double(router)
    if decisions is not None:
        client, asked = _with_decisions(router, answer=decisions)
        calls = asked
    rows: list[tuple[str, dict]] = []

    def on_phase(node_id, verdict, responses, iteration):
        data = (verdict.model_dump() if hasattr(verdict, "model_dump")
                else dict(verdict))
        rows.extend((node_id, data) for _ in responses)

    runner = PhaseRunner(client, on_phase=on_phase)
    state = await GraphExecutor(load(path), runner, SETTINGS).run(REQUEST)
    return state, calls, rows


def _delivery(rows):
    start = datetime(2026, 11, 14, tzinfo=timezone.utc)
    phases = [SimpleNamespace(
        phase=name, verdict_json=json.dumps(verdict, default=str), iteration=1,
        model_used="m", cost=0.0, id=n, created_at=start + timedelta(seconds=n))
        for n, (name, verdict) in enumerate(rows, start=1)]
    return _detail(SimpleNamespace(
        id=1, request=REQUEST, status=SimpleNamespace(value="completed"),
        risk_level=None, iteration=1, total_cost=0.0,
        unreconciled_liability=0.0, error=None, created_at=start,
        updated_at=start, phases=phases))


class TestTheWorkflow:
    def test_it_is_the_default_workflow_with_five_nodes_added_after_it(self):
        base, claims = load(BASE), load(CLAIMS)
        assert claims.ids == base.ids + CLAIM_NODES
        assert [claims.get(i) for i in base.ids] == [base.get(i) for i in base.ids]
        assert claims.get("claims").depends_on == [base.ids[-1]]

    def test_it_is_not_offered_and_every_claim_node_is_advisory(self):
        claims = load(CLAIMS)
        assert claims.offered is False
        assert all(claims.get(i).advisory for i in CLAIM_NODES)

    async def test_a_claim_the_samples_disagree_with_is_flagged_in_the_record(
            self, recompute_tier):
        state, calls, rows = await _run(CLAIMS, _router())
        assert state.status == "completed"
        vote = state.outputs["claims_vote"]
        assert vote["flagged"] is True
        assert [d["ask"] for d in vote["disagreements"]] == [1]
        stored = dict(rows)
        assert stored["claims"]["claims"][0]["name"] == "timer cap"
        assert stored["claims_named"]["dropped"]["not_in_answer"] == 1
        assert stored["claims_vote"]["flagged"] is True

    async def test_a_claim_the_samples_agree_with_is_not_flagged(
            self, recompute_tier):
        state, _, _ = await _run(CLAIMS, _router(sample_values=(60, 60, 30)))
        vote = state.outputs["claims_vote"]
        assert vote["flagged"] is False and vote["checked"] is True

    async def test_the_samples_see_the_names_and_never_a_value_or_the_answer(
            self, recompute_tier):
        _, calls, _ = await _run(CLAIMS, _router())
        asked = [c["user"] for c in calls
                 if "relies on the values named below" in c["user"]]
        assert len(asked) == 3
        for prompt in asked:
            assert "1. timer cap [value]" in prompt
            assert "retry limit" not in prompt      # dropped: not in the answer
            assert SUMMARY not in prompt and "60" not in prompt

    async def test_every_call_the_default_workflow_makes_is_made_unchanged(
            self, recompute_tier):
        _, base_calls, _ = await _run(BASE, _router())
        _, calls, _ = await _run(CLAIMS, _router())
        assert calls[:len(base_calls)] == base_calls
        assert len(calls) == len(base_calls) + 4     # the list, three samples

    async def test_the_delivery_is_the_default_workflows_delivery(
            self, recompute_tier):
        _, _, base_rows = await _run(BASE, _router())
        _, _, rows = await _run(CLAIMS, _router())
        base, shadow = _delivery(base_rows), _delivery(rows)
        assert shadow.recompute_vote == base.recompute_vote
        assert shadow.recompute_vote["flagged"] is False   # the claim vote is not it
        assert shadow.cautions == base.cautions
        assert shadow.answer == base.answer and shadow.decisions == base.decisions
        assert shadow.sources == base.sources

    async def test_a_failed_claims_call_is_a_skip_and_no_sample_is_paid_for(
            self, recompute_tier):
        state, calls, _ = await _run(CLAIMS, _router(claims_fail=True))
        assert state.status == "completed"
        assert state.outputs["claims"]["skipped"] is True
        assert state.outputs["claims_recompute"]["skipped"] is True
        assert state.outputs["claims_vote"]["skipped"] is True
        assert state.outputs["claims_vote"]["flagged"] is False
        assert not any("relies on the values named below" in c["user"] for c in calls)

    async def test_with_no_claim_kept_no_sample_is_paid_for(self, recompute_tier):
        state, calls, _ = await _run(CLAIMS, _router(listed=[LISTED[1]]))
        assert state.status == "completed"
        assert state.outputs["claims_recompute"]["reason"].startswith("no claim was kept")
        assert not any("relies on the values named below" in c["user"] for c in calls)

    async def test_with_no_recompute_tier_the_claim_vote_records_a_skip(self):
        state, _, _ = await _run(CLAIMS, _router())
        assert state.status == "completed"
        assert state.outputs["claims_vote"]["skipped"] is True


TEXT = [{"name": "jitter", "value": "full jitter", "unit": ""}]


def _text_router():
    """One text claim, 'full jitter', against samples that say 'jitter: full'."""
    base = _router(listed=TEXT)

    def route(user_message, calls):
        if "relies on the values named below" in user_message:
            return {"results": [{"ask": 1, "value": "jitter: full", "unit": ""}]}
        return base(user_message, calls)

    return route


@pytest.fixture
def decision_tier(monkeypatch):
    monkeypatch.setattr(openrouter.settings, "model_decision", "vendor/decider")
    monkeypatch.setitem(OpenRouterClient.FUNCTION_MODELS, "decision", "vendor/decider")


class TestSameMeaningBehindTheClaimVote:
    async def test_a_text_flag_is_asked_with_the_claims_name_and_both_wordings(
            self, recompute_tier, decision_tier):
        state, asked, rows = await _run(CLAIMS, _text_router(),
                                        decisions=lambda evidence: 0.95)
        assert state.outputs["claims_vote"]["flagged"] is True
        evidence = asked[-1][0]["q0"]
        assert evidence == {"request": REQUEST, "claim": "jitter",
                            "answer_value": "full jitter",
                            "sample_value": "jitter: full"}
        stored = dict(rows)["claims_switches"]
        assert stored["same"] == [1]
        assert stored["claim_records"][0]["item"] == "claim 1"
        assert state.outputs["claims_vote"]["flagged"] is True   # the row is kept

    async def test_a_no_or_an_unsure_answer_judges_nothing_the_same(
            self, recompute_tier, decision_tier):
        for probability in (0.05, 0.5):
            state, _, _ = await _run(CLAIMS, _text_router(),
                                     decisions=lambda evidence: probability)
            assert state.outputs["claims_switches"]["same"] == []

    async def test_its_records_never_reach_the_delivery(
            self, recompute_tier, decision_tier):
        answer = lambda evidence: 0.95
        _, _, base_rows = await _run(BASE, _text_router(), decisions=answer)
        _, _, rows = await _run(CLAIMS, _text_router(), decisions=answer)
        base, shadow = _delivery(base_rows), _delivery(rows)
        assert shadow.decisions == base.decisions and base.decisions
        assert shadow.recompute_vote == base.recompute_vote
        assert shadow.cautions == base.cautions and shadow.sources == base.sources
        stored = dict(rows)["claims_switches"]
        assert "records" not in stored and "cleared" not in stored

    async def test_with_no_decision_tier_it_skips(self, recompute_tier):
        state, _, _ = await _run(CLAIMS, _text_router())
        assert state.status == "completed"
        assert state.outputs["claims_switches"] == {
            "skipped": True, "claim_records": [], "same": [],
            "reason": state.outputs["claims_switches"]["reason"]}

    async def test_a_number_flag_is_not_asked(self, recompute_tier, decision_tier):
        state, asked, _ = await _run(CLAIMS, _router(),
                                     decisions=lambda evidence: 0.95)
        assert state.outputs["claims_vote"]["flagged"] is True
        assert state.outputs["claims_switches"]["claim_records"] == []
