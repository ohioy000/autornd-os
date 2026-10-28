"""Ruling D53, phase 1: the recompute vote, as a note.

The acceptance criteria the command enumerates, each with its
break-proof — the one line that, reverted, fails the assertion,
with the failure it produces. Where the break-proof is itself a
runnable outcome, the test runs it: the counterfactual is asserted
beside the ruled outcome, so the test proves it can fail
(convention 28 — an instrument that cannot fail cannot be trusted).

The replay (criterion (e)) scores the 21 recorded tier-4 answers
the command names — kimi's T4-42 calibration answer and its three
repetitions, F's T4-15 from the pilot, the batch-3 four, the
batch-4 three, the batch-5 three and the batch-6 five — against
the blind samples the probe's own sampling runs recorded, and
compares the harness check's flags with the probe's own scoring of
the same data, computed here with the probe's own primitives.
Three of the 21 are wrong answers the vote must flag; exactly one
correct answer is flagged (T4-42 repetition 1, on the ambiguous
row 'current compared with I_n (A)'): the false flag the D53
record carries, reproduced rather than fixed — the vote is a note,
and a note that never fired on a wrong answer would be a quieter
defect than one that fired once on a right one.

Free throughout: no test in this file makes a paid call. The
accounting tests drive the real client over an httpx MockTransport
(a local fake that never touches a socket), and the workflow tests
drive the real graph behind a recording double that bills like the
client (convention 7).
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from autornd.engine import phases
from autornd.engine.phases import render_asks
from autornd.graph.adapter import PhaseRunner
from autornd.graph.checks import (
    _recompute_ident,
    get_check,
    recompute_vote,
)
from autornd.graph.executor import ExecutionState, GraphExecutor
from autornd.graph.spec import Node, NodeKind, WorkflowSpec, load
from autornd.models.verdicts import (
    ImplementVerdict,
    PlanVerdict,
    ResultValue,
    RecomputeVerdict,
    SpecialistRole,
)
from autornd.routing import openrouter
from autornd.routing.openrouter import (
    ModelResponse, OpenRouterClient)
from autornd.specialists.registry import get_specialist
from tests.conftest import make_mock_response, seal_double

ROOT = Path(__file__).resolve().parents[1]
TRACES = ROOT / "docs/traces"
PROBES = ROOT / "evals/tier4/probes"

# The probe's own primitives, on the path the golden-keys test
# uses: the replay scores with them, so the comparison is between
# two implementations, not between an implementation and itself.
sys.path.insert(0, str(PROBES))
import recompute_check as rc  # noqa: E402
import recompute_vote as rv  # noqa: E402
sys.path.remove(str(PROBES))

# The fixed inputs every prompt-level test uses. The request's two
# asks — one value, one verdict — are the shape the recompute
# vote's asks are built from, and the summary and its results are
# the answer the vote compares against: distinctive words that
# occur nowhere else, so an isolation test can tell them apart.
REQUEST = ("Size the backoff timer for the reconnect path. Give "
           "the cap in seconds and state whether jitter applies.")
GROUNDING = ("The reconnect path's timer is sized by the request "
             "alone; no corpus was consulted for it.")
ASKS = [
    {"number": 1, "quote": "Give the cap in seconds", "kind": "value"},
    {"number": 2, "quote": "state whether jitter applies",
     "kind": "verdict"},
]
SUMMARY = ("Cap the timer at 60 s using a full jitter exponential "
           "schedule; jitter applies: yes.")
# The ruled sentence (D53 §2 (4)), verbatim — the test pins the
# ruling's words, so a drift in the code's copy fails here.
RESULTS_INSTRUCTION = (
    "In results, give one entry for each ask of kind value or "
    "verdict listed above: ask = its number, value = the final "
    "number or the identifier you chose, unit = the unit of the "
    "number (empty for an identifier). These are the values your "
    "summary states.")

# The vote-sampling runs the probe recorded, one file per session
# (the session that sampled T4-15 sampled batch 3's four with it,
# and so on), as docs/traces/ holds them.
SAMPLES_BY_BATCH = {
    "batch2": "20261018T035714Z-recompute-vote-samples.json",
    "batch3": "20261018T035714Z-recompute-vote-samples.json",
    "batch4": "20261018T164638Z-recompute-vote-samples.json",
    "batch5": "20261018T181158Z-recompute-vote-samples.json",
    "batch6": "20261018T192122Z-recompute-vote-samples.json",
}


# ── the recorded answers (criterion (e)'s fixture) ───────────────


def _unit_records(path: Path):
    """The unit records of a tier-4 trace, as the trace holds them."""
    for line in open(path):
        record = json.loads(line)
        if record.get("record") == "unit":
            yield record


def _recorded_answers() -> list[tuple[str, str, str, str]]:
    """(label, question, answer text, truth) for the 21 recorded
    answers the command names.

    The truth column is the advisor's reading, already recorded:
    three wrong (F's pilot T4-15, kimi's T4-42 calibration answer
    and its third repetition) and the rest correct, repetition 1
    of T4-42 among them — the one correct answer the vote flags.
    """
    answers: list[tuple[str, str, str, str]] = []
    # F's T4-15 from the pilot (wrong: the minor-axis
    # torsional-flexural coupling).
    for r in _unit_records(
            TRACES / "20261018T022735Z-tier4-pilot-batch2.jsonl"):
        if r.get("question_id") == "T4-15" and r.get("arm") == "F":
            answers.append(("pilot-batch2 arm F", "T4-15",
                            r["answer"], "wrong"))
    # The kimi calibration answers, batch 3 through 6 (T4-42 is
    # the wrong one; the rest are correct by the reading above).
    wrong = {"T4-42"}
    for batch, fname in (
            ("batch3", "20261018T034225Z-tier4-calibration-batch3.jsonl"),
            ("batch4", "20261018T164435Z-tier4-calibration-batch4.jsonl"),
            ("batch5", "20261018T180951Z-tier4-calibration-batch5.jsonl"),
            ("batch6", "20261018T185019Z-tier4-calibration-batch6.jsonl")):
        for r in _unit_records(TRACES / fname):
            q = r.get("question_id")
            if q in rv.KEY_ROWS and r.get("answer"):
                answers.append((f"{batch} kimi {q}", q, r["answer"],
                                "wrong" if q in wrong else "correct"))
    # The T4-42 repetitions: 1 and 2 correct, 3 wrong — the repeat
    # run's own record, same question, same blind samples.
    repeats = json.load(
        open(TRACES / "20261018T193358Z-repeat-T4-42.json"))
    for u in repeats["units"]:
        repetition = u["repetition"]
        answers.append((f"T4-42 repeat {repetition}", "T4-42",
                        u["answer"],
                        "wrong" if repetition == 3 else "correct"))
    return answers


ANSWERS = _recorded_answers()
# The STOP condition, mechanized: the command names these answers,
# so a record that does not carry them fails collection here, not
# silently later (convention 28 — no evidence is never no problem).
assert len(ANSWERS) == 21, (
    f"expected the 21 recorded answers the command names, "
    f"found {len(ANSWERS)}: {[a[0] for a in ANSWERS]}")
assert {a[0] for a in ANSWERS if a[3] == "wrong"} == (
    {"pilot-batch2 arm F", "batch5 kimi T4-42", "T4-42 repeat 3"}), (
    "the three wrong answers the D53 record names are not the "
    "three the traces carry")


def _fixture_asks(question: str) -> list[dict[str, Any]]:
    """The anchored asks for a question: its key rows, at their own
    numbers — the first row (the selection) a verdict ask, the rest
    value asks, each carrying the row's unit."""
    asks = []
    for i, row in enumerate(rv.KEY_ROWS[question]):
        asks.append({
            "number": i + 1,
            "quote": row,
            "kind": "verdict" if i == 0 else "value",
        })
    return asks


def _row_unit(row: str) -> str:
    """The unit a key row's name carries in its parentheses."""
    m = re.search(r"\(([^)]*)\)\s*$", row)
    return m.group(1) if m else ""


def _raw_samples(question: str) -> list[dict[str, Any]]:
    """The blind samples the probe's own run recorded for the
    question, as the JSON holds them."""
    batch = rv.QUESTIONS[question]
    data = json.load(open(TRACES / SAMPLES_BY_BATCH[batch]))
    return data["samples"][question]


def _answer_results(answer_text: str,
                    question: str) -> list[ResultValue]:
    """The answer's typed results, read from its Results table with
    the probe's own parser — the shape the harness's ImplementVerdict
    carries, built from the shape the records hold."""
    rows = rc.parse_table(answer_text)
    results: list[ResultValue] = []
    for i, row in enumerate(rv.KEY_ROWS[question]):
        raw = rc.find(rows, row)
        if raw is None:
            continue
        results.append(ResultValue(
            ask=i + 1,
            value=raw if i == 0 else rc.num(raw),
            unit=_row_unit(row)))
    return results


def _sample_results(raw_samples: list[dict[str, Any]],
                    question: str) -> list[dict[str, Any]]:
    """The samples as a recompute run returns them: one typed
    results list per sample, the values as the sample stated them
    (the selection as text, the figures as numbers)."""
    samples = []
    for raw in raw_samples:
        entries = []
        clean = {k: v for k, v in raw.items() if not k.startswith("_")}
        for i, row in enumerate(rv.KEY_ROWS[question]):
            value = rc.find(clean, row)
            if value is None:
                continue
            if i > 0:
                value = rc.num(value)
                if value is None:
                    continue
            entries.append({"ask": i + 1, "value": value,
                            "unit": _row_unit(row)})
        samples.append({"results": entries})
    return samples


def _probe_flag(answer_text: str, question: str,
                raw_samples: list[dict[str, Any]]) -> tuple[bool, list]:
    """The probe's own scoring (recompute_vote.score's logic) on the
    same recorded data — the flag the harness check must reproduce,
    computed with the probe's own primitives."""
    key_rows = rv.KEY_ROWS[question]
    majority = {}
    for i, row in enumerate(key_rows):
        majority[row] = rv.majority(
            [rc.find({k: v for k, v in s.items() if not k.startswith("_")},
                     row) for s in raw_samples],
            i == 0)
    answer_rows = rc.parse_table(answer_text)
    diffs = []
    for i, row in enumerate(key_rows):
        answer_value, majority_value = (rc.find(answer_rows, row),
                                        majority[row])
        if majority_value is None or answer_value is None:
            continue
        if i == 0:
            if rc.ident(answer_value) != majority_value:
                diffs.append((i + 1, row))
        elif (rc.num(answer_value) is not None
                and abs(rc.num(answer_value) - majority_value)
                > rc.TOL * max(abs(majority_value), 1e-9)):
            diffs.append((i + 1, row))
    return bool(diffs), diffs


def _request_of(question: str) -> str:
    """The question's request, verbatim from its batch's candidates."""
    return rc.load(rv.BATCHES[rv.QUESTIONS[question]]
                   / "candidates.json")[question]["request"]


# ── (a) the schema coercions ──────────────────────────────────────


class TestSchemaCoercions:
    """ResultValue and the results fields coerce the shapes that
    arrive over the wire; a recorded verdict from before the field
    existed still parses (D53 §2 (3))."""

    def test_a_null_results_field_coerces_to_empty(self):
        assert ImplementVerdict(
            done=True, green=True, summary="s",
            results=None).results == []
        assert RecomputeVerdict(results=None).results == []

    def test_a_null_unit_coerces_to_the_empty_string(self):
        assert ResultValue(ask=1, value=1.0, unit=None).unit == ""

    def test_a_recorded_verdict_without_results_still_parses(self):
        """Every recorded ImplementVerdict predates the field."""
        verdict = ImplementVerdict(
            done=True, green=True, red_cause=None,
            summary="Backoff capped at 60 s with jitter.",
            blocked_on=[], iteration=1)
        assert verdict.results == []

    def test_an_ask_is_a_number_or_a_string(self):
        """The recompute prompt instructs 'ask = its number' — a JSON
        number — and a quote names the ask as text."""
        assert ResultValue(ask=3, value=1.0).ask == 3
        assert ResultValue(ask="3", value=1.0).ask == "3"

    def test_breakproof_a_required_results_field_would_not_parse(self):
        """The default is load-bearing: make `results` required and a
        recorded verdict no longer parses — which is why the field is
        defaulted, not required."""
        from pydantic import ValidationError

        class Required(ImplementVerdict):
            results: list[ResultValue]

        with pytest.raises(ValidationError):
            Required(done=True, green=True, summary="s",
                     blocked_on=[], iteration=1)


# ── (b) the skip ──────────────────────────────────────────────────


def _recompute_node(**kw) -> Node:
    spec = load("workflows/answer-and-recompute.yaml")
    node = next(n for n in spec.nodes if n.id == "recompute")
    for key, value in kw.items():
        setattr(node, key, value)
    return node


def _recompute_state() -> ExecutionState:
    state = ExecutionState(request=REQUEST)
    state.outputs["asks_anchored"] = {
        "anchored": ASKS, "quotes": [a["quote"] for a in ASKS],
        "demoted": [], "fallback": False}
    return state


class TestTheSkip:
    """The recompute tier is optional, like the premium tier: unset,
    the node skips and records the skip, and the vote reads a skip
    as skipped — never as passed (D53 §2 (2))."""

    async def test_the_node_skips_when_no_model_is_configured(self):
        """No model configured for the tier: no call made, the skip
        recorded with its reason and an empty samples list — the
        shape `recompute.samples` and `recompute.reason` resolve
        against, whatever the tier's state."""
        runner = PhaseRunner(client=OpenRouterClient(api_key="test"))
        assert runner.client.recompute_model() is None
        out, responses = await runner._phase_recompute(
            _recompute_node(), _recompute_state())
        assert out == {
            "skipped": True,
            "flagged": False,
            "reason": ("no model configured for the recompute "
                       "tier — the recompute samples did not run"),
            "samples": [],
        }
        assert responses == []
        assert runner.client.calls == 0

    async def test_breakproof_a_configured_tier_makes_the_calls(self):
        """The skip is the tier's absence, not the node's: with a
        model configured for the tier, the same phase on the same
        node makes the samples' calls."""
        from autornd import config

        client = OpenRouterClient(api_key="test")
        seen: list = []

        async def chat_json(function, system_prompt, user_message, **kw):
            seen.append(function)
            data = {"results": [{"ask": 1, "value": 200.0, "unit": "s"}]}
            client._account(function, 0.001)
            return dict(data), make_mock_response(data, "mock-recompute")

        client.chat_json = AsyncMock(side_effect=chat_json)
        seal_double(client)
        monkeypatch_model = patch.object(
            config.settings, "model_recompute", "vendor/recompute-tier")
        monkeypatch_function = patch.dict(
            OpenRouterClient.FUNCTION_MODELS,
            {"recompute": "vendor/recompute-tier"})
        with monkeypatch_model, monkeypatch_function:
            runner = PhaseRunner(client=client)
            out, responses = await runner._phase_recompute(
                _recompute_node(), _recompute_state())
        assert out["skipped"] is False
        assert seen == ["recompute", "recompute", "recompute"]
        assert len(responses) == 3

    def test_a_skip_is_never_read_as_a_pass(self):
        result = recompute_vote(
            results=_answer_results(
                ANSWERS[0][2], ANSWERS[0][1]),
            samples=_sample_results(
                _raw_samples(ANSWERS[0][1]), ANSWERS[0][1]),
            asks=_fixture_asks(ANSWERS[0][1]),
            request=_request_of(ANSWERS[0][1]),
            skipped=True,
            reason=("no model configured for the recompute tier — "
                    "the recompute samples did not run"))
        assert result.passed is False
        assert result.checked is False
        assert result.data["skipped"] is True
        assert result.data["flagged"] is False
        assert result.data["samples_parsed"] == 0

    def test_breakproof_the_same_inputs_not_skipped_vote(self):
        """The skip branch is what produces the outcome above:
        the same results, samples and asks, not skipped, vote —
        a different outcome, checked and unflagged. The answer
        is a correct one (the first correct answer the records
        carry), so the vote's outcome is unflagged: the skip
        and the vote differ on checked and skipped, not only
        on the flag."""
        label, question, answer_text, truth = next(
            a for a in ANSWERS if a[3] == "correct")
        result = recompute_vote(
            results=_answer_results(answer_text, question),
            samples=_sample_results(_raw_samples(question), question),
            asks=_fixture_asks(question),
            request=_request_of(question))
        assert result.data["skipped"] is False
        assert result.checked is True
        assert result.data["flagged"] is False


# ── (c) isolation ─────────────────────────────────────────────────


class TestIsolation:
    """No sample's messages contain the implement summary, its
    results, the plan or another sample's output (D53 §2 (7)) —
    isolation is structural: the prompt is built from the request,
    the grounding and the asks, and nothing else is an input."""

    async def test_no_sample_sees_the_answer_or_another_sample(self):
        client = OpenRouterClient(api_key="test")
        recorded: list[tuple[str, str, str]] = []

        async def chat_json(function, system_prompt, user_message, **kw):
            recorded.append((function, system_prompt, user_message))
            data = {"results": [{"ask": 1, "value": 200.0, "unit": "s"},
                                {"ask": 2, "value": "yes", "unit": ""}]}
            client._account(function, 0.001)
            return dict(data), make_mock_response(data, "mock-recompute")

        client.chat_json = AsyncMock(side_effect=chat_json)
        seal_double(client)
        out, responses = await phases.run_recompute(
            client, REQUEST, GROUNDING, ASKS, samples=3)
        assert out["skipped"] is False
        assert len(recorded) == 3
        assert len(responses) == 3
        for function, system, user in recorded:
            assert function == "recompute"
            assert system == "You are a careful senior engineer."
            # the request, the grounding and the anchored asks of
            # kind value and verdict, at their own numbers
            assert REQUEST in user
            assert GROUNDING in user
            assert "1. Give the cap in seconds [value]" in user
            assert "2. state whether jitter applies [verdict]" in user
            # nothing of the answer: no summary words, no results
            # values, no plan
            for phrase in ("exponential schedule", "Cap the timer",
                           "60 s", "yes", "60"):
                assert phrase not in user
        # No sample saw another's output: every prompt was built
        # from the same inputs, so the three are identical.
        assert recorded[0][2] == recorded[1][2] == recorded[2][2]

    def test_breakproof_the_absence_assertion_can_fail(self):
        """The detector is not vacuous: applied to a prompt that
        does carry the summary, it finds the summary's words and
        the answer's values — the same assertions that pass on the
        samples' prompts fail here."""
        contaminated = (
            "The asks, quoted from the request:\n"
            "1. Give the cap in seconds [value]\n"
            + SUMMARY)
        for phrase in ("exponential schedule", "Cap the timer",
                       "60 s", "yes", "60"):
            assert phrase in contaminated


# ── (d) accounting ────────────────────────────────────────────────


def _accounting_client(handler, monkeypatch):
    """A real client over a local transport, with the recompute
    tier configured at a rate the catalogue knows — an unrated
    model would make the guard blind, and a blind call reserves
    nothing, which is the condition this test exists to watch."""
    model = "vendor/recompute-tier"
    monkeypatch.setattr(
        openrouter, "_model_pricing", {model: (1e-6, 1e-6)})
    monkeypatch.setattr(
        openrouter.settings, "model_recompute", model)
    monkeypatch.setitem(
        OpenRouterClient.FUNCTION_MODELS, "recompute", model)
    client = OpenRouterClient(
        api_key="test-key", base_url="https://router.test/api/v1")
    client._client = httpx.AsyncClient(
        base_url=client.base_url, transport=httpx.MockTransport(handler))
    client.spend_ceiling = 1.0
    return client


def _reply(data: dict[str, Any], model: str) -> httpx.Response:
    return httpx.Response(200, json={
        "choices": [{"message": {"content": json.dumps(data)},
                     "finish_reason": "stop"}],
        "usage": {"prompt_tokens": 100, "completion_tokens": 100,
                  "cost": 0.001},
        "provider": "Test", "model": model})


class TestAccounting:
    """Each sample goes through the client's reservation path, which
    reserves its worst case and releases it by identity (D45, D47).
    No new post site: the call is chat_json, like every other
    phase's (D53 §2 (8))."""

    async def test_each_sample_reserves_and_releases_its_own_worst_case(
            self, monkeypatch):
        in_flight: list[tuple[int, float]] = []
        sent: list[list[dict[str, str]]] = []

        def handler(request: httpx.Request) -> httpx.Response:
            body = json.loads(request.content)
            sent.append(body["messages"])
            # What is in flight at dispatch time: the count of
            # reservations and their summed worst case.
            in_flight.append((len(client._reservations),
                              client.reserved))
            return _reply({"results": [
                {"ask": 1, "value": 200.0, "unit": "s"}]},
                body["model"])

        client = _accounting_client(handler, monkeypatch)
        out, responses = await phases.run_recompute(
            client, REQUEST, GROUNDING, ASKS, samples=3,
            max_tokens=1000)
        assert client.calls_by_function["recompute"] == 3
        # Each call saw exactly one reservation in flight — its own:
        # a reservation another call leaked would grow the count and
        # the sum call over call (the D47 defect this pins).
        assert [n for n, _ in in_flight] == [1, 1, 1]
        system, user = sent[0][0]["content"], sent[0][1]["content"]
        worst = ((openrouter._prompt_bytes(system, user)
                  + openrouter.CHAT_TEMPLATE_ALLOWANCE_BYTES) * 1e-6
                 + 1000 * 1e-6)
        assert all(reserved == pytest.approx(worst)
                   for _, reserved in in_flight)
        # Every worst case released by its own identity, and every
        # sample accounted at its own cost.
        assert client._reservations == []
        assert client.reserved == 0.0
        assert client.unreconciled_liability == 0.0
        assert client.spend_by_function["recompute"] == (
            pytest.approx(0.003))
        assert len(responses) == 3

    async def test_a_sample_failing_after_dispatch_keeps_its_worst_case(
            self, monkeypatch):
        """D45 (5): the request left this process, so the money may
        have been spent and no actual cost will ever arrive — the
        sample's own reservation becomes unreconciled liability,
        with the failure's kind recorded. ARCH-20261021-124: the
        failed sample is recorded, not raised, and the next sample
        still runs."""
        sent: list[list[dict[str, str]]] = []
        dispatched: list[int] = []

        def handler(request: httpx.Request) -> httpx.Response:
            body = json.loads(request.content)
            sent.append(body["messages"])
            dispatched.append(len(dispatched) + 1)
            if len(dispatched) == 2:
                return httpx.Response(
                    500, json={"error": {"message": "boom"}})
            return _reply({"results": [
                {"ask": 1, "value": 200.0, "unit": "s"}]},
                body["model"])

        client = _accounting_client(handler, monkeypatch)
        verdict, responses = await phases.run_recompute(
            client, REQUEST, GROUNDING, ASKS, samples=3,
            max_tokens=1000)
        # The first and third samples reconciled; the second failed
        # after dispatch and is recorded in its place. The call count
        # is what reconciled — the failed sample's record is the
        # failed_after_dispatch entry below.
        assert len(sent) == 3
        assert len(responses) == 2
        assert verdict["samples"][1]["failed"] is True
        assert verdict["samples"][1]["error"].startswith("HTTPStatusError: ")
        assert client.calls_by_function["recompute"] == 2
        assert len(client.failed_after_dispatch) == 1
        entry = client.failed_after_dispatch[0]
        assert entry["function"] == "recompute"
        assert entry["kind"] == "error_status"
        system, user = sent[0][0]["content"], sent[0][1]["content"]
        worst = ((openrouter._prompt_bytes(system, user)
                  + openrouter.CHAT_TEMPLATE_ALLOWANCE_BYTES) * 1e-6
                 + 1000 * 1e-6)
        assert entry["worst_case"] == pytest.approx(worst)
        assert client.unreconciled_liability == pytest.approx(worst)
        # The failed call's reservation is gone from the in-flight
        # set — it was the call's own, released into liability.
        assert client._reservations == []
        assert client.reserved == 0.0


# ── (e) the replay ────────────────────────────────────────────────


class TestTheReplay:
    """The vote on the recorded answers, against the probe's own
    scoring of the same records. The check's flags match
    recompute_vote.score's on every answer — including the one
    false flag, which is reproduced, not fixed."""

    @pytest.mark.parametrize(
        "label,question,answer_text,truth", ANSWERS,
        ids=[a[0] for a in ANSWERS])
    def test_the_check_reproduces_the_probe_flag(
            self, label, question, answer_text, truth):
        asks = _fixture_asks(question)
        raw_samples = _raw_samples(question)
        result = recompute_vote(
            results=_answer_results(answer_text, question),
            samples=_sample_results(raw_samples, question),
            asks=asks,
            request=_request_of(question))
        probe_flagged, probe_diffs = _probe_flag(
            answer_text, question, raw_samples)
        assert result.data["flagged"] == probe_flagged
        # The disagreements are the probe's diffs, at the asks' own
        # numbers — not merely the same boolean.
        assert {d["ask"] for d in result.data["disagreements"]} == (
            {number for number, _row in probe_diffs})
        if not probe_diffs:
            assert result.data["disagreements"] == []
            assert result.data["no_consensus"] == []
        assert result.data["samples_parsed"] == 3
        assert result.checked is True

    def test_the_false_flag_is_the_ambiguous_row(self):
        """T4-42 repetition 1: a correct answer, flagged on one row
        — 'current compared with I_n (A)', where the answer states
        −5.5 against the samples' 40.5. The D53 record's one false
        flag in 23, reproduced exactly: one disagreement, ask 3,
        the answer's value against the majority's, at the majority's
        support."""
        answer = next(a for a in ANSWERS if a[0] == "T4-42 repeat 1")
        question = answer[1]
        result = recompute_vote(
            results=_answer_results(answer[2], question),
            samples=_sample_results(_raw_samples(question), question),
            asks=_fixture_asks(question),
            request=_request_of(question))
        assert result.data["flagged"] is True
        assert result.data["disagreements"] == [
            {"ask": 3, "answer": -5.5, "majority": 40.5, "support": 3}]

    def test_the_wrong_pilot_answer_is_flagged_on_three_rows(self):
        """F's T4-15: wrong on all three numeric rows — the
        torsional-flexural coupling the advisor's reading named."""
        answer = next(a for a in ANSWERS if a[0] == "pilot-batch2 arm F")
        question = answer[1]
        raw_samples = _raw_samples(question)
        result = recompute_vote(
            results=_answer_results(answer[2], question),
            samples=_sample_results(raw_samples, question),
            asks=_fixture_asks(question),
            request=_request_of(question))
        assert result.data["flagged"] is True
        disagreements = {d["ask"]: d for d in result.data["disagreements"]}
        assert set(disagreements) == {2, 3, 4}
        # Each majority is the probe's own, on the same samples.
        key_rows = rv.KEY_ROWS[question]
        for i, row in enumerate(key_rows[1:], start=2):
            majority = rv.majority(
                [rc.find({k: v for k, v in s.items()
                          if not k.startswith("_")}, row)
                 for s in raw_samples],
                False)
            assert disagreements[i]["majority"] == majority
        assert disagreements[2]["answer"] == pytest.approx(229.3)
        assert disagreements[3]["answer"] == pytest.approx(1.29)
        assert disagreements[4]["answer"] == pytest.approx(151.7)

    def test_the_wrong_t4_42_answers_are_flagged_on_selection_and_current(
            self):
        """Kimi's T4-42 calibration answer and its third repetition:
        wrong on the selection (VL-25 against VL42, an identifier)
        and on the current comparison (4.36 against 40.5)."""
        for label in ("batch5 kimi T4-42", "T4-42 repeat 3"):
            answer = next(a for a in ANSWERS if a[0] == label)
            question = answer[1]
            result = recompute_vote(
                results=_answer_results(answer[2], question),
                samples=_sample_results(_raw_samples(question), question),
                asks=_fixture_asks(question),
                request=_request_of(question))
            assert result.data["flagged"] is True, label
            disagreements = {d["ask"]: d
                             for d in result.data["disagreements"]}
            assert set(disagreements) == {1, 3}, label
            # The selection compares as an identifier: the majority
            # is the normalised identifier the samples agreed on.
            assert disagreements[1] == {
                "ask": 1, "answer": "VL-25", "majority": "VL42",
                "support": 3}
            assert disagreements[3]["answer"] == pytest.approx(4.36)
            assert disagreements[3]["majority"] == pytest.approx(40.5)
            assert disagreements[3]["support"] == 3

    def test_every_correct_answer_is_unflagged(self):
        """The 16 of the 17 correct answers the vote reads
        cleanly — the controls the record carries: no
        disagreement, no consensus failure, on any row.
        T4-42 repetition 1, the seventeenth, is correct
        and flagged on the ambiguous 'current compared
        with I_n (A)' row — the recorded false flag,
        pinned by test_the_false_flag_is_the_ambiguous_row
        above."""
        for label, question, answer_text, truth in ANSWERS:
            if truth != "correct" or label == "T4-42 repeat 1":
                continue
            result = recompute_vote(
                results=_answer_results(answer_text, question),
                samples=_sample_results(_raw_samples(question), question),
                asks=_fixture_asks(question),
                request=_request_of(question))
            assert result.data["flagged"] is False, label
            assert result.data["disagreements"] == [], label
            assert result.data["no_consensus"] == [], label


# ── (f) the vote's rules ──────────────────────────────────────────


def _vote(answer_value, sample_values, kind="value",
          answer_unit="", sample_unit=""):
    """The vote on one ask: the answer's value against the samples'
    values, the smallest shaped input the ruling describes."""
    return recompute_vote(
        results=[ResultValue(ask=1, value=answer_value,
                             unit=answer_unit)],
        samples=[{"results": [ResultValue(ask=1, value=v,
                                          unit=sample_unit)]}
                 for v in sample_values],
        asks=[{"number": 1, "quote": "the ask", "kind": kind}],
        request="the request asks the answer to give the ask")


class TestVoteRules:
    """The vote's comparison rules, unit by unit (D53 §2 (9))."""

    def test_identity_values_compare_after_normalisation(self):
        """'VL-42' and 'vl 42' are one identifier: case, spacing and
        punctuation dropped, the multiplication sign and a count's
        'x' read as separators — recompute_check.ident without its
        'in parallel' special case."""
        assert _recompute_ident("VL-42") == "VL42"
        assert _recompute_ident("vl 42") == "VL42"
        assert _recompute_ident("VL-42") == _recompute_ident("vl 42")
        # Through the vote itself: a majority stated three ways.
        result = _vote("vl-42", ["VL-42", "vl 42", "VL42"],
                       kind="verdict")
        assert result.data["flagged"] is False
        assert result.data["disagreements"] == []
        # Break-proof: a different identifier flags.
        result = _vote("VL-43", ["VL-42", "vl 42", "VL42"],
                       kind="verdict")
        assert result.data["flagged"] is True
        assert result.data["disagreements"][0]["majority"] == "VL42"

    def test_the_tolerance_edge_is_three_percent(self):
        """Numbers agree within a relative tolerance of 0.03: 2.9%
        agrees, 3.1% disagrees."""
        result = _vote(102.9, [100.0, 100.0, 100.0])
        assert result.data["flagged"] is False
        result = _vote(103.1, [100.0, 100.0, 100.0])
        assert result.data["flagged"] is True
        assert result.data["disagreements"] == [
            {"ask": 1, "answer": 103.1, "majority": 100.0, "support": 3}]

    def test_a_majority_forms_within_the_tolerance(self):
        """The formation edge: two samples 2.9% apart form a majority
        of two (the mean of the agreeing group); two samples 3.1%
        apart form none — the ask is no consensus, not a flag."""
        result = _vote(101.45, [100.0, 102.9, 500.0])
        assert result.data["flagged"] is False
        assert result.data["no_consensus"] == []
        result = _vote(100.0, [100.0, 103.1, 500.0])
        assert result.data["flagged"] is False
        assert result.data["unchecked"] is False
        assert result.data["no_consensus"] == [1]

    def test_a_unit_mismatch_is_no_consensus_not_a_flag(self):
        """Numbers compare only when the units are equal after
        normalise_key; otherwise the ask has no consensus to compare
        against — a disagreement of units is not a disagreement of
        values."""
        result = _vote(100.0, [100.0, 100.0, 100.0],
                       answer_unit="kN", sample_unit="N")
        assert result.data["flagged"] is False
        assert result.data["no_consensus"] == [1]
        # Break-proof: the same values in the same unit compare, and
        # a value that differs by more than the tolerance flags —
        # the unit gate is what suppressed the comparison, not a
        # tolerance that happens to hold.
        result = _vote(100.0, [200.0, 200.0, 200.0],
                       answer_unit="kN", sample_unit="kN")
        assert result.data["flagged"] is True

    def test_a_three_way_split_has_no_consensus(self):
        """A 1-1-1 split: no value matched by 2 of the samples, so
        no majority and no flag — the ask is no consensus."""
        result = _vote(100.0, [100.0, 200.0, 300.0])
        assert result.data["flagged"] is False
        assert result.data["no_consensus"] == [1]
        # Break-proof: two of three agree and the ask is voted.
        result = _vote(100.0, [100.0, 100.0, 300.0])
        assert result.data["flagged"] is False
        assert result.data["no_consensus"] == []

    def test_one_parseable_sample_leaves_the_vote_unchecked(self):
        """Fewer than two parseable samples: the vote compared
        nothing, and says so — unchecked, flagged false."""
        result = recompute_vote(
            results=[ResultValue(ask=1, value=100.0, unit="")],
            samples=[{"results": [ResultValue(ask=1, value=100.0,
                                              unit="")]}],
            asks=[{"number": 1, "quote": "the ask", "kind": "value"}],
            request="the request asks the answer to give the ask")
        assert result.data["unchecked"] is True
        assert result.data["flagged"] is False
        assert result.data["checked"] is False
        assert result.data["samples_parsed"] == 1
        # Break-proof: two samples vote.
        result = _vote(100.0, [100.0, 100.0])
        assert result.data["unchecked"] is False
        assert result.data["checked"] is True

    def test_an_answer_naming_no_anchored_ask_is_unchecked(self):
        """No answer result names an anchored ask: nothing to vote
        on, and the vote says so rather than passing silently."""
        result = recompute_vote(
            results=[ResultValue(ask=99, value=100.0, unit="")],
            samples=[{"results": [ResultValue(ask=1, value=v, unit="")]}
                     for v in (100.0, 100.0, 100.0)],
            asks=[{"number": 1, "quote": "the ask", "kind": "value"}],
            request="the request asks the answer to give the ask")
        assert result.data["unchecked"] is True
        assert result.data["flagged"] is False
        # Break-proof: a result naming the ask votes it.
        result = _vote(100.0, [100.0, 100.0, 100.0])
        assert result.data["unchecked"] is False
        assert result.data["checked"] is True


# ── (g) the workflow ──────────────────────────────────────────────


SETTINGS = {"max_iterations": 5, "escalation_recovery_attempts": 3,
            "review_rework_attempts": 2}


def _workflow_router(answer_value: float, sample_values: list[float]):
    """The double's router: every phase of answer-and-recompute,
    answered by the prompt's own first words. The implement's
    results state `answer_value` for the value ask; the recompute's
    samples state `sample_values`, one per call, in call order."""

    def route(user_message: str, calls: list[dict[str, str]]):
        if user_message.startswith("Classify this engineering request"):
            return {"domains": ["backend"], "risk": "medium",
                    "specialists": ["backend_engineer"],
                    "summary": "A sizing question."}
        if user_message.startswith("List what this request asks"):
            return {"asks": [
                {"quote": "Give the cap in seconds", "kind": "value"},
                {"quote": "state whether jitter applies",
                 "kind": "verdict"}]}
        if user_message.startswith(
                "Produce the answer to the following request"):
            return {
                "reasoning": "r", "done": True, "green": True,
                "red_cause": None, "blocked_on": [],
                "summary": SUMMARY,
                "results": [{"ask": 1, "value": answer_value,
                             "unit": "s"},
                            {"ask": 2, "value": "yes", "unit": ""}]}
        if user_message.startswith(REQUEST):
            index = (sum(1 for c in calls
                         if c["function"] == "recompute") - 1)
            return {"results": [
                {"ask": 1, "value": sample_values[index], "unit": "s"},
                {"ask": 2, "value": "yes", "unit": ""}]}
        raise AssertionError(f"unrouted prompt: {user_message[:80]}")

    return route


def _double(router):
    """A recording double around the router: every call is recorded
    and billed like the real client's (convention 7), and every
    network method the double does not serve is sealed."""
    client = OpenRouterClient(api_key="test")
    calls: list[dict[str, str]] = []

    async def chat_json(function, system_prompt, user_message, **kw):
        calls.append({"function": function, "user": user_message})
        data = router(user_message, calls)
        response = make_mock_response(data, f"mock-{function}")
        client._account(function, response.cost)
        return data, response

    client.chat_json = AsyncMock(side_effect=chat_json)
    seal_double(client)
    client.close = AsyncMock()
    return client, calls


async def _drive(spec, router, request: str):
    """One run of the real graph behind the double."""
    client, calls = _double(router)
    runner = PhaseRunner(client)
    state = await GraphExecutor(spec, runner, SETTINGS).run(request)
    return state, runner, calls


class TestTheWorkflow:
    """workflows/answer-and-recompute.yaml: the workflow loads, and
    a mocked run delivers with the vote in its outputs — once
    flagged, once not — with the run's status decided without the
    vote (D53 §2 (5), (10))."""

    def test_the_workflow_loads(self):
        spec = load("workflows/answer-and-recompute.yaml")
        assert spec.name == "answer-and-recompute"
        assert spec.ids == [
            "triage", "asks", "asks_anchored", "context", "implement",
            "blocked_check", "blocked_gate", "coverage", "consistency",
            "recompute", "recompute_vote"]
        recompute = spec.get("recompute")
        assert recompute.kind is NodeKind.AI
        assert recompute.tier == "recompute"
        assert recompute.args == {"samples": 3}
        assert recompute.max_tokens == "recompute_max_tokens"
        vote = spec.get("recompute_vote")
        assert vote.kind is NodeKind.CHECK
        assert vote.check == "recompute_vote"
        assert vote.args["results"] == "implement.results"
        assert vote.args["samples"] == "recompute.samples"
        assert vote.args["asks"] == "asks_anchored.anchored"
        assert vote.args["skipped"] == "recompute.skipped"
        assert vote.args["reason"] == "recompute.reason"

    async def test_the_run_delivers_the_vote_once_flagged_and_once_not(
            self, monkeypatch):
        # The test environment leaves the recompute tier
        # unset (the production default — no paid call
        # without configuration); these drives configure
        # it so the recompute node makes its three blind
        # samples through the double. Both settings are
        # restored on teardown.
        monkeypatch.setattr(
            openrouter.settings, "model_recompute",
            "vendor/recompute-tier")
        monkeypatch.setitem(
            OpenRouterClient.FUNCTION_MODELS, "recompute",
            "vendor/recompute-tier")
        # Flagged: the answer's value (100) differs from the
        # 2-of-3 majority of the samples (200) — the vote's note is
        # on the delivery, and the run still completes.
        state, runner, calls = await _drive(
            load("workflows/answer-and-recompute.yaml"),
            _workflow_router(100.0, [200.0, 200.0, 200.0]), REQUEST)
        vote = state.outputs["recompute_vote"]
        assert vote["flagged"] is True
        assert vote["passed"] is False
        assert vote["disagreements"] == [
            {"ask": 1, "answer": 100.0, "majority": 200.0, "support": 3}]
        assert vote["no_consensus"] == []
        assert vote["samples_parsed"] == 3
        assert state.status == "completed"
        # The recompute made three separate calls on its own tier.
        recompute_calls = [c for c in calls if c["function"] == "recompute"]
        assert len(recompute_calls) == 3

        # Not flagged: the answer's value (200) agrees with the
        # majority of the samples (200, 200, 201 — a mean of
        # 200.33, within the tolerance).
        state, runner, calls = await _drive(
            load("workflows/answer-and-recompute.yaml"),
            _workflow_router(200.0, [200.0, 200.0, 201.0]), REQUEST)
        vote = state.outputs["recompute_vote"]
        assert vote["flagged"] is False
        assert vote["passed"] is True
        assert vote["disagreements"] == []
        assert vote["no_consensus"] == []
        assert state.status == "completed"

    async def test_the_run_status_is_decided_without_the_vote(
            self, monkeypatch):
        """The vote never blocks, routes or revises: the same run
        with the vote nodes removed completes with the same status —
        on the flagged scenario, where the full run carries a flag
        the stripped run cannot."""
        monkeypatch.setattr(
            openrouter.settings, "model_recompute",
            "vendor/recompute-tier")
        monkeypatch.setitem(
            OpenRouterClient.FUNCTION_MODELS, "recompute",
            "vendor/recompute-tier")
        spec = load("workflows/answer-and-recompute.yaml")
        stripped = WorkflowSpec(
            spec.name,
            [n for n in spec.nodes
             if n.id not in {"recompute", "recompute_vote"}],
            spec.description)
        full, _, _ = await _drive(
            spec, _workflow_router(100.0, [200.0, 200.0, 200.0]),
            REQUEST)
        without, _, _ = await _drive(
            stripped, _workflow_router(100.0, [200.0, 200.0, 200.0]),
            REQUEST)
        assert full.outputs["recompute_vote"]["flagged"] is True
        assert "recompute_vote" not in without.outputs
        assert full.status == without.status == "completed"

    async def test_the_votes_output_reaches_the_delivery(self):
        """The API's delivery returns the run's persisted phases, and
        a check's output is not otherwise persisted — only AI nodes
        write phase rows. The vote's own output is written through
        the phase channel, on a zero-cost response, so the flag the
        vote found is what the delivery carries."""
        persisted: list[tuple[str, Any, list, int]] = []

        def on_phase(node_id, verdict, responses, iteration):
            persisted.append((node_id, verdict, responses, iteration))

        runner = PhaseRunner(
            client=seal_double(OpenRouterClient(api_key="test")),
            on_phase=on_phase)
        spec = load("workflows/answer-and-recompute.yaml")
        node = spec.get("recompute_vote")
        state = ExecutionState(request=REQUEST)
        state.outputs["asks_anchored"] = {
            "anchored": ASKS, "quotes": [a["quote"] for a in ASKS],
            "demoted": [], "fallback": False}
        state.outputs["implement"] = {
            "results": [ResultValue(ask=1, value=100.0, unit="s"),
                        ResultValue(ask=2, value="yes", unit="")]}
        state.outputs["recompute"] = {
            "skipped": False, "reason": "",
            "samples": [{"results": [
                ResultValue(ask=1, value=200.0, unit="s"),
                ResultValue(ask=2, value="yes", unit="")]},
                {"results": [
                    ResultValue(ask=1, value=200.0, unit="s"),
                    ResultValue(ask=2, value="yes", unit="")]},
                {"results": [
                    ResultValue(ask=1, value=200.0, unit="s"),
                    ResultValue(ask=2, value="yes", unit="")]}]}
        result = await runner.run_check(node, state)
        assert result.data["flagged"] is True
        assert len(persisted) == 1
        node_id, verdict, responses, iteration = persisted[0]
        assert node_id == "recompute_vote"
        # The vote's own output, as data — the delivery's payload.
        assert verdict["flagged"] is True
        assert verdict["disagreements"] == [
            {"ask": 1, "answer": 100.0, "majority": 200.0, "support": 3}]
        # A zero-cost, empty-model response: the write is a record,
        # not a call, and it bills nothing.
        assert responses == [ModelResponse(
            content="", model="", prompt_tokens=0,
            completion_tokens=0, cost=0.0)]


# ── (h) the prompts ───────────────────────────────────────────────


# The implement prompts of main (pre-D53), captured
# byte-for-byte on 2026-10-18 from the pre-change
# run_implement, on the two fixed inputs the header's
# criterion (h) names (the capture ran before the first
# D53 edit; its script is the session record).
VERIFY_FIRST = (
    "Produce the answer to the following request. This is iteration 1.\n"
    "\n"
    "You have no repository, file system, shell, or build tools, and you are not expected to. Nothing you write is executed or applied automatically.\n"
    "\n"
    "Your response IS the deliverable. Produce the actual engineering work as text — the design, the code, the schema, the procedure, the calculation — in enough detail that a competent engineer could apply it directly. Never reply that you are unable to make changes or lack access: describing the work precisely is the task.\n"
    "\n"
    "The asks, quoted from the request — the answer is judged against these and nothing else:\n"
    "1. Give the cap in seconds [value]\n"
    "2. state whether jitter applies [verdict]\n"
    "\n"
    "If an ask cannot be honestly answered with the grounding available, name it by its number in blocked_on rather than producing something that answers it on paper.\n"
    "Answer the request, and include the plan's falsifiers, kill triggers or assumption tables only if the request asks for them.\n"
    "\n"
    "\n"
    "\n"
    "\n"
    "Return JSON with:\n"
    "- reasoning: fill this FIRST, before every other field. Think step by step here — how you will satisfy each ask, and, critically, verify that every numeric value you will state agrees with every threshold, bound and other value in the deliverable (the failure this guards against is a value that violates a limit the same deliverable sets, e.g. a computed figure exceeding a stated threshold). If a previous implementation is shown above, state exactly what was inconsistent, why its logic was wrong, and the specific change you will make to fix it WITHOUT breaking what already passed. This field is a private scratchpad: it is not the deliverable and is not read downstream.\n"
    "- done: true if the implementation is complete\n"
    "- green: true if you believe it satisfies the asks\n"
    "- red_cause: null if green, otherwise a short string describing what is wrong\n"
    "- blocked_on: list of asks the work cannot honestly answer, each entry\n"
    "  naming the ask (its number or its quote) and why it cannot be\n"
    "  answered; an empty list when there are none\n"
    "- iteration: 1\n"
    "- summary: the implementation itself — the design, code, schema, procedure or\n"
    "  calculation, in full. This field is the deliverable and is what the validate\n"
    "  phase and every downstream reviewer will read, so write the work out rather\n"
    "  than describing it in the abstract.\n"
    "\n"
    "Original request:\n"
    "Size the backoff timer for the reconnect path. Give the cap in seconds and state whether jitter applies."
)

ENGINEERING_RND = (
    "Produce the implementation for the following plan. This is iteration 1.\n"
    "\n"
    "You have no repository, file system, shell, or build tools, and you are not expected to. Nothing you write is executed or applied automatically.\n"
    "\n"
    "Your response IS the deliverable. Produce the actual engineering work as text — the design, the code, the schema, the procedure, the calculation — in enough detail that a competent engineer could apply it directly. Never reply that you are unable to make changes or lack access: describing the work precisely is the task.\n"
    "\n"
    "Plan:\n"
    "Cap the timer at 60 s.\n"
    "\n"
    "The asks, quoted from the request — the answer is judged against these and nothing else:\n"
    "1. Give the cap in seconds [value]\n"
    "2. state whether jitter applies [verdict]\n"
    "\n"
    "If an ask cannot be honestly answered with the grounding available, name it by its number in blocked_on rather than producing something that answers it on paper.\n"
    "Answer the request, and include the plan's falsifiers, kill triggers or assumption tables only if the request asks for them.\n"
    "\n"
    "\n"
    "\n"
    "\n"
    "Return JSON with:\n"
    "- reasoning: fill this FIRST, before every other field. Think step by step here — how you will satisfy each ask, and, critically, verify that every numeric value you will state agrees with every threshold, bound and other value in the deliverable (the failure this guards against is a value that violates a limit the same deliverable sets, e.g. a computed figure exceeding a stated threshold). If a previous implementation is shown above, state exactly what was inconsistent, why its logic was wrong, and the specific change you will make to fix it WITHOUT breaking what already passed. This field is a private scratchpad: it is not the deliverable and is not read downstream.\n"
    "- done: true if the implementation is complete\n"
    "- green: true if you believe it satisfies the asks\n"
    "- red_cause: null if green, otherwise a short string describing what is wrong\n"
    "- blocked_on: list of asks the work cannot honestly answer, each entry\n"
    "  naming the ask (its number or its quote) and why it cannot be\n"
    "  answered; an empty list when there are none\n"
    "- iteration: 1\n"
    "- summary: the implementation itself — the design, code, schema, procedure or\n"
    "  calculation, in full. This field is the deliverable and is what the validate\n"
    "  phase and every downstream reviewer will read, so write the work out rather\n"
    "  than describing it in the abstract.\n"
    "\n"
    "Original request:\n"
    "Size the backoff timer for the reconnect path. Give the cap in seconds and state whether jitter applies."
)


class TestGoldenPrompts:
    """The implement prompts of engineering-rnd and verify-first are
    byte-identical to main's (D53 §2 (4), criterion (h)): the
    results instruction is gated on the implement node's args, and
    with the arg unset the prompt is unchanged, byte for byte."""

    def _lead(self):
        return [get_specialist(SpecialistRole.BACKEND_ENGINEER)]

    async def _implement_prompt(self, plan, results):
        client = OpenRouterClient(api_key="test")
        recorded: list[str] = []

        async def chat_json(function, system_prompt, user_message, **kw):
            recorded.append(user_message)
            data = {"done": True, "green": True, "red_cause": None,
                    "summary": SUMMARY, "blocked_on": []}
            client._account(function, 0.0)
            return dict(data), make_mock_response(data, "mock-engineering")

        client.chat_json = AsyncMock(side_effect=chat_json)
        seal_double(client)
        await phases.run_implement(
            client, REQUEST, plan, self._lead(), iteration=1,
            max_tokens=32768, asks=ASKS, results=results)
        return recorded[0]

    async def test_the_verify_first_prompt_is_byte_identical(self):
        assert await self._implement_prompt(None, results=False) == (
            VERIFY_FIRST)

    async def test_the_engineering_rnd_prompt_is_byte_identical(self):
        plan = PlanVerdict(ready=True, plan="Cap the timer at 60 s.",
                           blockers=[], cost_estimate=None,
                           success_criteria=[])
        assert await self._implement_prompt(plan, results=False) == (
            ENGINEERING_RND)

    async def test_the_results_instruction_is_added_only_when_asked(self):
        """With args: {results: true} — the answer-and-recompute
        implement node's arg — the ruled sentence is added, after
        the asks block and before the blocked_on sentence, and
        nowhere else."""
        prompt = await self._implement_prompt(None, results=True)
        assert RESULTS_INSTRUCTION in prompt
        assert prompt.index(render_asks(ASKS)) < prompt.index(
            RESULTS_INSTRUCTION) < prompt.index(
                "If an ask cannot be honestly answered")
        # Break-proof: the ungated prompt does not carry it — the
        # sentence is the addition, and it is absent without the arg.
        assert RESULTS_INSTRUCTION not in VERIFY_FIRST
        assert RESULTS_INSTRUCTION not in ENGINEERING_RND

    async def test_the_recompute_prompt_is_the_ruled_shape(self):
        """The recompute prompt: the system 'You are a careful senior
        engineer.'; the user message the request, the grounding, the
        anchored asks of kind value and verdict numbered as in the
        answer, then the ruled computation instruction."""
        client = OpenRouterClient(api_key="test")
        recorded: list[tuple[str, str]] = []

        async def chat_json(function, system_prompt, user_message, **kw):
            recorded.append((system_prompt, user_message))
            data = {"results": [{"ask": 1, "value": 200.0, "unit": "s"},
                                {"ask": 2, "value": "yes", "unit": ""}]}
            client._account(function, 0.001)
            return dict(data), make_mock_response(data, "mock-recompute")

        client.chat_json = AsyncMock(side_effect=chat_json)
        seal_double(client)
        await phases.run_recompute(client, REQUEST, GROUNDING, ASKS,
                                   samples=1)
        system, user = recorded[0]
        assert system == "You are a careful senior engineer."
        assert user == (
            f"{REQUEST}\n\nProject context:\n{GROUNDING}\n\n"
            "The asks, quoted from the request — compute each one "
            "yourself:\n"
            "1. Give the cap in seconds [value]\n"
            "2. state whether jitter applies [verdict]\n\n"
            'Compute the answer yourself. Return JSON with results: '
            "one entry per listed ask, "
            '{"ask": its number, "value": your final number or the '
            "identifier you chose, \"unit\": the unit of the number, "
            "empty for an identifier}.")


# ── wiring ────────────────────────────────────────────────────────


class TestWiring:
    """The phase's contract with the client: the schema goes into
    the call, the node's token ceiling reaches it, and the tier is
    declared optional and empty."""

    async def test_the_recompute_call_carries_the_schema(self):
        client = OpenRouterClient(api_key="test")
        seen: dict[str, Any] = {}

        async def chat_json(function, system_prompt, user_message, **kw):
            seen.update(kw)
            data = {"results": [{"ask": 1, "value": 200.0, "unit": "s"}]}
            client._account(function, 0.001)
            return dict(data), make_mock_response(data, "mock-recompute")

        client.chat_json = AsyncMock(side_effect=chat_json)
        seal_double(client)
        await phases.run_recompute(client, REQUEST, GROUNDING, ASKS,
                                   samples=1)
        assert seen["schema"] is RecomputeVerdict

    async def test_the_node_ceiling_reaches_run_recompute(self, monkeypatch):
        """A node's declared ceiling reaches the call, the way every
        other phase's does (the 072 defect, pinned per phase): the
        string names a setting, and the setting is what the call
        carries."""
        from autornd import config

        monkeypatch.setattr(config.settings, "recompute_max_tokens",
                            112768)
        monkeypatch.setitem(OpenRouterClient.FUNCTION_MODELS,
                            "recompute", "vendor/recompute-tier")
        runner = PhaseRunner(
            client=seal_double(OpenRouterClient(api_key="test")))
        with patch("autornd.engine.phases.run_recompute",
                   new=AsyncMock(return_value=(
                       {"skipped": False, "reason": "", "samples": []},
                       []))) as run:
            await runner._phase_recompute(
                _recompute_node(max_tokens="recompute_max_tokens"),
                _recompute_state())
        assert run.await_args.kwargs["max_tokens"] == 112768

    async def test_an_unset_ceiling_falls_back_to_the_setting(self,
                                                              monkeypatch):
        from autornd import config

        monkeypatch.setattr(config.settings, "recompute_max_tokens", 32768)
        client = OpenRouterClient(api_key="test")
        seen: dict[str, Any] = {}

        async def chat_json(function, system_prompt, user_message, **kw):
            seen.update(kw)
            data = {"results": [{"ask": 1, "value": 200.0, "unit": "s"}]}
            client._account(function, 0.001)
            return dict(data), make_mock_response(data, "mock-recompute")

        client.chat_json = AsyncMock(side_effect=chat_json)
        seal_double(client)
        await phases.run_recompute(client, REQUEST, GROUNDING, ASKS,
                                   samples=1)
        assert seen["max_tokens"] == 32768

    def test_the_tier_is_optional_and_defaults_to_unset(self):
        from autornd.config import settings

        assert settings.model_recompute == ""
        assert settings.recompute_max_tokens == 32768
        # Optional like the premium tier: the client resolves no
        # model for the function, and the phase skips rather than
        # falling back to the engineering tier.
        client = OpenRouterClient(api_key="test")
        assert client.recompute_model() is None
        assert client.get_model("recompute") == settings.model_engineering

    def test_the_check_is_registered_under_its_workflow_name(self):
        assert get_check("recompute_vote") is recompute_vote

    def test_env_example_declares_the_tier_empty(self):
        text = (ROOT / ".env.example").read_text()
        assert "MODEL_RECOMPUTE=" in text
        assert "RECOMPUTE_MAX_TOKENS=32768" in text
