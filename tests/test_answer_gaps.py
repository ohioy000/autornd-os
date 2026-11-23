"""What an answer leaves open is said beside it (routes._gaps).

**Why.** The delivery's cautions read the recompute vote and the pages the lookup handed on, and nothing
the answer itself recorded. Over the 681 labelled answers of four runs (2026-11-17 to 2026-11-23, 23 of
them not right) the shipped cautions stood beside 25.4 percent of the right answers and 35 percent of the
not-right ones, and five of the not-right answers said, in typed fields the delivery never read, that
they were incomplete: an ask with no result, a part they could not answer, an ask they called not stated,
and an answer text of the single word PLACEHOLDER beside two typed results (docs/reviews/2026-11-23-caution-flaw.md).

**What is pinned.** Four cautions, each read off a typed field and none off prose: an ask of kind value or
verdict with no typed result and no claim that the document states none; a `blocked_on` entry (an entry that
names an ask ends the run blocked, so one that is delivered names none, and nothing showed it); an ask the
answer reports as not stated; a text shorter than MIN_ANSWER_WORDS beside typed results. Two real recorded
units (the second hold-out run, Y140 and Y149) are carried whole through `_detail`, and the asks are numbered
as `asks_anchored` numbers them.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from autornd.api.routes import (
    ASK_QUOTE_CHARS, BLOCKED_REASON_CHARS, MIN_ANSWER_WORDS, _detail, _gaps,
)
from autornd.graph import checks
from autornd.models.workflow import WorkflowStatus

ASK_1 = "what minimum ratio applied in 2014 for the bank described here"
ASK_2 = "what ratio does the cited page state for the same bank"
REQUEST = f"A bank asks: {ASK_1}, and {ASK_2}? Ignore buffers and other add-ons."
CONSTRAINT = "Ignore buffers and other add-ons."
REPORT = " ".join(["word"] * (MIN_ANSWER_WORDS + 10))


def _run(results=None, kinds=("value", "value"), blocked=None, not_stated=None,
         summary=REPORT, proposals=None):
    """The stored verdicts of one answer: the asks node, then the implement node."""
    quotes = (ASK_1, ASK_2, CONSTRAINT)
    asks = proposals if proposals is not None else [
        {"quote": q, "kind": k} for q, k in zip(quotes, kinds)]
    implement = {"summary": summary, "results": results if results is not None else [],
                 "blocked_on": blocked or [], "not_stated": not_stated or []}
    return [("asks", {"asks": asks}), ("implement", implement)]


def _result(ask, value="4.5", unit="percent"):
    return {"ask": ask, "value": value, "unit": unit}


class TestAnAskWithNoResult:
    def test_an_ask_of_kind_value_with_no_typed_result_is_named_with_its_quote(self):
        out = _gaps(_run(results=[_result(1)]), REQUEST)
        assert out == [f'The answer gives no result for ask 2: "{ASK_2}".']

    def test_an_answer_with_a_result_for_every_ask_has_no_such_caution(self):
        assert _gaps(_run(results=[_result(1), _result(2)]), REQUEST) == []

    def test_a_constraint_or_a_format_wants_no_result(self):
        """Only value and verdict asks are asked for a typed result: a step, a constraint and a
        format are things to do, not things to state (the implement prompt's own rule)."""
        verdicts = _run(results=[_result(1)], kinds=("value", "constraint"))
        assert _gaps(verdicts, REQUEST) == []
        verdicts = _run(results=[_result(1)], kinds=("value", "format"))
        assert _gaps(verdicts, REQUEST) == []

    def test_a_verdict_ask_wants_a_result_too(self):
        out = _gaps(_run(results=[_result(1)], kinds=("value", "verdict")), REQUEST)
        assert len(out) == 1 and "ask 2" in out[0]

    def test_a_claim_that_the_document_states_none_answers_the_ask(self):
        """The claim is the answer to that ask, so it is not also told it has no result; the
        absence caution below says what the claim rests on."""
        out = _gaps(_run(results=[_result(1)], not_stated=[{"ask": 2, "why": "p"}]), REQUEST)
        assert not any("gives no result" in c for c in out)
        assert len(out) == 1 and "ask 2 is not stated" in out[0]

    def test_a_result_may_name_its_ask_by_the_number_as_text_or_by_its_quote(self):
        """As the recompute vote reads a result: "2", "ask 2" and the ask's own words name ask 2."""
        for named in ("2", "ask 2", "#2", ASK_2, ASK_2.upper()):
            verdicts = _run(results=[_result(1), _result(named)])
            assert _gaps(verdicts, REQUEST) == [], named

    def test_an_answer_that_typed_no_results_is_not_told_it_left_an_ask_open(self):
        """Only an answer asked for results has typed any, and an empty list cannot tell an answer
        that was not asked from one that typed nothing."""
        assert _gaps(_run(results=[]), REQUEST) == []

    def test_a_run_with_no_asks_node_has_no_such_caution(self):
        verdicts = [("implement", {"summary": REPORT, "results": [_result(1)]})]
        assert _gaps(verdicts, REQUEST) == []

    def test_the_asks_are_numbered_over_the_ones_that_anchor(self):
        """A proposal that is not in the request is dropped and does not take a number, as in
        asks_anchored: ask 1 is the first that anchors, whatever came before it."""
        proposals = [{"quote": "a paraphrase that is nowhere in the request", "kind": "value"},
                     {"quote": ASK_1, "kind": "value"}, {"quote": ASK_2, "kind": "value"}]
        assert _gaps(_run(results=[_result(1), _result(2)], proposals=proposals), REQUEST) == []
        out = _gaps(_run(results=[_result(1)], proposals=proposals), REQUEST)
        assert out == [f'The answer gives no result for ask 2: "{ASK_2}".']

    def test_numbered_asks_are_the_ones_asks_anchored_numbers(self):
        proposals = [{"quote": "nothing like this is in the request at all", "kind": "value"},
                     {"quote": ASK_1, "kind": "value"}, {"quote": "x", "kind": "value"},
                     {"quote": ASK_2, "kind": "verdict"}, {"quote": CONSTRAINT, "kind": "constraint"}]
        assert checks.numbered_asks(proposals, REQUEST) == \
            checks.asks_anchored(proposals, REQUEST).data["anchored"]

    def test_when_nothing_anchors_no_ask_is_named(self):
        """The whole request is then the one ask, of no kind: nothing to name."""
        proposals = [{"quote": "nothing like this is in the request at all", "kind": "value"}]
        assert checks.numbered_asks(proposals, REQUEST) == []
        assert _gaps(_run(results=[_result(1)], proposals=proposals), REQUEST) == []

    def test_a_long_quote_is_cut(self):
        long_quote = "what minimum ratio applied " + "and still " * 30 + "for the bank"
        request = f"First, {long_quote}? Then more."
        out = _gaps(_run(results=[_result(5)], proposals=[{"quote": long_quote, "kind": "value"}]), request)
        assert out == [f'The answer gives no result for ask 1: "{long_quote[:ASK_QUOTE_CHARS]}".']


class TestAPartTheAnswerSaysItCouldNotAnswer:
    def test_a_blocked_entry_that_names_no_ask_is_shown_with_its_reason(self):
        out = _gaps(_run(results=[_result(1), _result(2)],
                         blocked=[{"ask": None, "why": "the cited page was not supplied"}]), REQUEST)
        assert out == ["The answer marks part of the request as one it could not answer: "
                       "the cited page was not supplied"]

    def test_every_entry_is_shown(self):
        blocked = [{"ask": None, "why": "first"}, {"ask": None, "why": "second"}]
        out = _gaps(_run(results=[_result(1), _result(2)], blocked=blocked), REQUEST)
        assert [c.rsplit(": ", 1)[-1] for c in out] == ["first", "second"]

    def test_a_long_reason_is_cut(self):
        out = _gaps(_run(results=[_result(1), _result(2)],
                         blocked=[{"ask": None, "why": "w" * 1000}]), REQUEST)
        assert out == ["The answer marks part of the request as one it could not answer: "
                       + "w" * BLOCKED_REASON_CHARS]

    def test_an_entry_with_no_reason_is_still_shown(self):
        out = _gaps(_run(results=[_result(1), _result(2)], blocked=[{"ask": None, "why": ""}]),
                    REQUEST)
        assert out == ["The answer marks part of the request as one it could not answer."]

    def test_a_null_entry_is_skipped(self):
        assert _gaps(_run(results=[_result(1), _result(2)], blocked=[None]), REQUEST) == []

    def test_it_is_said_even_when_the_answer_typed_no_results(self):
        """A workflow that never asked for results can still carry a blocked note."""
        out = _gaps(_run(results=[], blocked=[{"ask": None, "why": "x"}]), REQUEST)
        assert len(out) == 1 and out[0].endswith(": x")


class TestAnAbsenceClaim:
    def test_each_claimed_ask_is_told_once_what_the_claim_rests_on(self):
        claims = [{"ask": 1, "why": "a"}, {"ask": 2, "why": "b"}, {"ask": 2, "why": "again"}]
        out = _gaps(_run(results=[_result(1, "not_stated", ""), _result(2, "not_stated", "")],
                         not_stated=claims), REQUEST)
        assert len(out) == 2
        assert out[0].startswith("The answer says ask 1 is not stated in the document.")
        assert out[1].startswith("The answer says ask 2 is not stated in the document.")
        assert "search of the pages read in full" in out[0]
        assert out[0].endswith("and it found none.")

    def test_a_claim_may_name_its_ask_by_quote(self):
        out = _gaps(_run(results=[_result(1)], not_stated=[{"ask": ASK_2, "why": "b"}]), REQUEST)
        assert len(out) == 1 and "ask 2 is not stated" in out[0]

    def test_a_claim_that_names_no_ask_is_not_shown(self):
        """As the gate reads it, such a claim is a note naming no ask; nothing is said of it."""
        out = _gaps(_run(results=[_result(1), _result(2)], not_stated=[{"ask": 9, "why": "z"}]),
                    REQUEST)
        assert out == []


class TestATextTooShortForItsResults:
    def test_a_text_of_one_word_beside_typed_results_is_told_so(self):
        out = _gaps(_run(results=[_result(1), _result(2)], summary="PLACEHOLDER"), REQUEST)
        assert out == ["The text of this answer is only 1 word long, so it may not state the "
                       "results listed for it."]

    def test_the_limit_is_the_fewest_words_of_a_report(self):
        results = [_result(1), _result(2)]
        short = " ".join(["w"] * (MIN_ANSWER_WORDS - 1))
        full = " ".join(["w"] * MIN_ANSWER_WORDS)
        out = _gaps(_run(results=results, summary=short), REQUEST)
        assert out == [f"The text of this answer is only {MIN_ANSWER_WORDS - 1} words long, so it "
                       f"may not state the results listed for it."]
        assert _gaps(_run(results=results, summary=full), REQUEST) == []

    def test_a_short_text_with_no_typed_results_is_not_told_so(self):
        """Many tests and some workflows deliver a short summary with no typed result: with no
        results there is nothing the text should have stated."""
        assert _gaps(_run(results=[], summary="a"), REQUEST) == []

    def test_an_empty_text_beside_typed_results_is_told_so(self):
        out = _gaps(_run(results=[_result(1), _result(2)], summary=""), REQUEST)
        assert out == ["The text of this answer is only 0 words long, so it may not state the "
                       "results listed for it."]


def _workflow(*phases, status=WorkflowStatus.COMPLETED, request=REQUEST):
    start = datetime(2026, 11, 23, tzinfo=timezone.utc)
    return SimpleNamespace(
        id=1, request=request, status=status, error=None, risk_level="low", iteration=1,
        total_cost=0.0, unreconciled_liability=0.0, created_at=start, updated_at=start,
        phases=[SimpleNamespace(phase=name, iteration=1, verdict_json=json.dumps(verdict),
                                model_used="", cost=0.0, created_at=start + timedelta(seconds=n))
                for n, (name, verdict) in enumerate(phases)])


# The second hold-out run's unit Y140 on the earlier line-up (docs/traces/20261122T-holdout2-O-*): the
# answer text was the single word PLACEHOLDER, the typed results were right, and the delivery carried
# no caution at all. Recorded verbatim.
Y140_REQUEST = (
    "An action was already pending when the Federal Rules of Evidence took effect. Under their original "
    "applicability provisions, do the rules govern further procedure in that action, and what happens to "
    "the extent that applying them would not be feasible or would work injustice?")
Y140 = [
    ("asks", {"asks": [{"quote": "do the rules govern further procedure in that action", "kind": "verdict"},
                       {"quote": "what happens to the extent that applying them would not be feasible or "
                                 "would work injustice?", "kind": "verdict"}]}),
    ("implement", {"done": True, "green": True, "red_cause": None, "iteration": 1,
                   "summary": "PLACEHOLDER", "domain_concerns": [], "blocked_on": [], "not_stated": [],
                   "results": [{"ask": 1, "value": "yes_except_to_the_extent_not_feasible_or_injustice",
                                "unit": ""},
                               {"ask": 2, "value": "former_evidentiary_principles_apply_to_that_extent",
                                "unit": ""}]})]

# Y149 on the new line-up: ask 2 was declared unanswerable in a `blocked_on` entry that names no ask (the
# gate reads a number or a quote, so the run completed), no result was typed for it, and the delivery
# carried no caution. Recorded verbatim, the answer text shortened.
Y149_REQUEST = (
    "An advanced approaches national bank that is not a savings and loan holding company has a legacy "
    "checklist using the OCC transition standards for calendar year 2014. What minimum common equity tier 1 "
    "and tier 1 capital ratios applied from January 1 through December 31, 2014, and what are the "
    "corresponding minimum ratios in the text of 12 CFR Part 3 reproduced on the cited page? Ignore "
    "buffers and other add-ons.")
Y149 = [
    ("asks", {"asks": [{"quote": "What minimum common equity tier 1 and tier 1 capital ratios applied from "
                                 "January 1 through December 31, 2014", "kind": "value"},
                       {"quote": "what are the corresponding minimum ratios in the text of 12 CFR Part 3 "
                                 "reproduced on the cited page?", "kind": "value"},
                       {"quote": "Ignore buffers and other add-ons.", "kind": "constraint"}]}),
    ("implement", {"done": True, "green": True, "red_cause": None, "iteration": 1,
                   "summary": " ".join(["DRAFT"] * 60), "domain_concerns": [],
                   "blocked_on": [{"ask": None, "why": "Ask 2 ('what are the corresponding minimum ratios in "
                                   "the text of 12 CFR Part 3 reproduced on the cited page?'): Neither the "
                                   "request nor the project documentation identifies or supplies 'the cited "
                                   "page'."}],
                   "not_stated": [],
                   "results": [{"ask": 1, "value": "4% CET1 / 5.5% Tier 1", "unit": "percent"}]})]


class TestTheDelivery:
    def test_the_placeholder_answer_of_the_second_hold_out_is_marked(self):
        detail = _detail(_workflow(*Y140, request=Y140_REQUEST))
        assert detail.answer == "PLACEHOLDER"
        assert detail.cautions[-1] == ("The text of this answer is only 1 word long, so it may not "
                                       "state the results listed for it.")

    def test_the_ask_declared_blocked_and_left_without_a_result_is_marked_twice_over(self):
        detail = _detail(_workflow(*Y149, request=Y149_REQUEST))
        gaps = [c for c in detail.cautions if c.startswith("The answer ")]
        assert len(gaps) == 2
        assert gaps[0].startswith('The answer gives no result for ask 2: "what are the corresponding '
                                  'minimum ratios')
        assert gaps[1].startswith("The answer marks part of the request as one it could not answer: "
                                  "Ask 2 (")

    def test_the_gaps_stand_after_the_cautions_that_were_there(self):
        detail = _detail(_workflow(*Y149, request=Y149_REQUEST))
        assert detail.cautions[0].startswith("No lookup ran")
        assert len(detail.cautions) == 3

    def test_an_answer_with_no_gap_carries_only_the_cautions_it_had(self):
        detail = _detail(_workflow(*_run(results=[_result(1), _result(2)])))
        assert detail.cautions == [
            "No lookup ran: figures and citations in this answer come from the model's memory and "
            "were not checked against a source."]

    def test_a_run_with_no_answer_has_no_gaps(self):
        detail = _detail(_workflow(*Y140, status=WorkflowStatus.BLOCKED, request=Y140_REQUEST))
        assert detail.answer is None and detail.cautions == []
