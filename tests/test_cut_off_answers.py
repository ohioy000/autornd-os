"""A cut-off answer is not a finished one (the owner, 2026-11-13).

Golden batch 1 of 2026-11-13 delivered Q6 r2 as done and green: its text
stopped at character 1948, mid-sentence ("…reads as "), with its bold
open and no gate named, and no caution said so
(docs/reviews/2026-11-13-golden-decisions.md). The owner's word that day,
"yes to all 3", added a free check and a gate: a text that ends cut off
ends the run blocked with that reason, the answer kept as the candidate,
and nothing more paid for. It had no retry. The owner's word of 2026-11-21,
"def a retry, 3 attempts at least, to have slack for the routers", added
one: the implement node of each workflow that gates on the check writes a
cut-off answer again, up to three more times, before the gate sees it.

The check's signs were measured on every recorded answer in docs/traces
before they were kept. The tier-4 calibration runs of 2026-10-17 record
which answers stopped at the token limit, so they are the answer key here:
the check must find the cut ones it claims to and pass every finished one.
"""

from __future__ import annotations

import glob
import json
from pathlib import Path

import pytest

from autornd.graph.checks import answer_ends_whole
from autornd.graph.executor import GraphExecutor
from autornd.graph.spec import load
from autornd.routing import openrouter
from autornd.routing.openrouter import OpenRouterClient
from tests.test_all_workflows_terminate import _satisfying_verdicts
from tests.test_graph import SETTINGS as SCRIPTED_SETTINGS
from tests.test_graph import ScriptedRunner
from tests.test_recompute_vote import REQUEST, SUMMARY, _drive, _workflow_router

# Every test here is of a request judged to need a calculation: the
# recompute step runs only for those (owner's ruling, 2026-11-16).
pytestmark = pytest.mark.usefixtures("calculation_request")

ROOT = Path(__file__).resolve().parent.parent
TRACES = ROOT / "docs" / "traces"
# Q6 r2 as it shipped, ending as the record has it.
CUT = ("Door switches NC-to-ground mean a fault is safe.\n\n### Why these "
       "polarities\n\n- Door switches NC-to-ground means a **broken door "
       "wire or unplugged connector reads as ")


def _recorded(pattern: str) -> list[dict]:
    return [json.loads(line)
            for path in sorted(glob.glob(str(TRACES / pattern)))
            for line in open(path, encoding="utf-8")]


class TestTheRecordedAnswers:
    def test_of_the_runs_that_record_a_cut_it_finds_12_of_16_and_no_finished_one(
            self):
        """The tier-3 and tier-4 runs' records say whether each answer
        stopped at the token limit (`truncated`)."""
        records = [r for r in _recorded("*.jsonl")
                   if isinstance(r, dict) and isinstance(r.get("answer"), str)
                   and r["answer"].strip() and isinstance(r.get("truncated"), bool)]
        cut = [r for r in records if r["truncated"]]
        finished = [r for r in records if not r["truncated"]]
        # The guard read its subject before it judged it.
        assert (len(cut), len(finished)) == (16, 152)
        assert sum(not answer_ends_whole(r["answer"]).passed for r in cut) == 12
        assert [r["question_id"] for r in finished
                if not answer_ends_whole(r["answer"]).passed] == []

    def test_the_golden_answer_that_shipped_cut_off_is_found_and_no_other(self):
        units = _recorded("20261113T180026Z-golden-batch1-shard-*.jsonl")
        assert len(units) == 15 and all(u["delivered"] for u in units)
        found = [(u["question"], u["repeat"]) for u in units
                 if not answer_ends_whole(u["answer"]).passed]
        assert found == [("Q6", 2)]

    def test_every_answer_the_tier2_run_delivered_ends_whole(self):
        units = [u for u in _recorded("20261113T091013Z-short-workflows-shard-*.jsonl")
                 if u.get("delivered")]
        assert len(units) == 149
        assert [(u["question"], u["workflow"], u["repeat"]) for u in units
                if not answer_ends_whole(u["answer"]).passed] == []


class TestTheSigns:
    @pytest.mark.parametrize("text", [
        CUT,
        "The lamp lights when\n\n```\nL = B AND (F OR A)",
        "The head is\n\n\\[\nH = 1.35(1.10)^{1.5}",
        "Moment:\n\n\\[\n\\begin{aligned}\nM &= PL\n\\]",
        "| Part | Rating |\n|---|---|\n| L2,",
        "Use the pump rated for",
        "The verdict is (pass",
        "Select the strip,",
        "The steps are:",
        "It was “closed",
    ])
    def test_a_text_that_stops_short_fails(self, text):
        result = answer_ends_whole(text)
        assert result.passed is False and result.checked is True
        assert result.data["cut"] is True and result.data["signs"]
        assert result.detail.startswith("answer cut off")

    @pytest.mark.parametrize("text", [
        "The lamp lights when either door is open and the brake is set.",
        "| Part | Rating |\n|---|---|\n| L2 | 10 bar |",
        "Use a Class A extinguisher",
        "Drill a hole 2 in",
        "Source: https://www.ecfr.gov/current/title-14/part-65/",
        "=== END DELIVERABLE ===",
        "---",
        "```\nL = B AND (F OR A)\n```",
        "\\[\nH = 1.557 + 0.840\n\\]",
        "Mass per unit length: 0.471 kg/m",
    ])
    def test_a_text_that_ends_whole_passes(self, text):
        result = answer_ends_whole(text)
        assert result.passed is True and result.data["cut"] is False

    @pytest.mark.parametrize("text", ["", "   \n", None])
    def test_no_text_is_unchecked_not_cut(self, text):
        result = answer_ends_whole(text)
        assert result.passed is True and result.checked is False


def _cut_router():
    """answer-and-recompute's double, with the answer's text cut off."""
    route = _workflow_router(60.0, [60.0] * 3)

    def cut(user_message, calls):
        data = route(user_message, calls)
        if user_message.startswith("Produce the answer to the following request"):
            data = dict(data, summary=SUMMARY + "\n\n- Then **apply it as")
        return data

    return cut


@pytest.fixture
def recompute_tier(monkeypatch):
    """The recompute tier set, so a recompute that is not paid for is the
    gate's doing and not an unset tier's."""
    monkeypatch.setattr(openrouter.settings, "model_recompute",
                        "vendor/recompute-tier")
    monkeypatch.setitem(OpenRouterClient.FUNCTION_MODELS, "recompute",
                        "vendor/recompute-tier")


class TestTheGate:
    async def test_answer_and_recompute_ends_blocked_and_buys_no_recompute(
            self, recompute_tier):
        spec = load("workflows/answer-and-recompute.yaml")
        state, _, calls = await _drive(spec, _cut_router(), REQUEST)
        assert state.status == "blocked"
        assert state.reason.startswith("Answer incomplete: it ends mid-sentence")
        assert "open bold" in state.reason
        assert "recompute" not in [c["function"] for c in calls]
        assert "recompute" not in state.outputs
        assert state.candidate is not None

    async def test_a_whole_answer_still_completes(self, recompute_tier):
        spec = load("workflows/answer-and-recompute.yaml")
        state, _, calls = await _drive(
            spec, _workflow_router(60.0, [60.0] * 3), REQUEST)
        assert state.status == "completed"
        assert state.outputs["answer_end"]["passed"] is True
        assert [c["function"] for c in calls].count("recompute") == 3

    @pytest.mark.parametrize("workflow", ["verify-first", "lean"])
    async def test_the_loop_workflows_end_blocked_on_a_cut_final_answer(
            self, workflow):
        verdicts = _satisfying_verdicts()
        verdicts["implement"] = dict(
            verdicts["implement"],
            summary="The breadth probe is done, and the next step is the")
        runner = ScriptedRunner(verdicts)
        state = await GraphExecutor(
            load(f"workflows/{workflow}.yaml"), runner,
            SCRIPTED_SETTINGS).run("breadth probe")
        assert state.status == "blocked"
        assert state.reason.startswith("Answer incomplete: it ends mid-sentence")
        # lean's review is not paid for on an answer that is not finished.
        assert "review" not in runner.ai_calls


def _answer_calls(calls):
    return [c for c in calls
            if c["user"].startswith("Produce the answer to the following request")]


def _cut_first(cuts: int):
    """answer-and-recompute's double whose first `cuts` answers are cut off
    and whose later ones are whole, counted by the answers written."""
    route = _workflow_router(60.0, [60.0] * 3)

    def router(user_message, calls):
        data = route(user_message, calls)
        if (user_message.startswith("Produce the answer to the following request")
                and len(_answer_calls(calls)) <= cuts):
            data = dict(data, summary=SUMMARY + "\n\n- Then **apply it as")
        return data

    return router


class TestTheRetry:
    async def test_a_cut_answer_is_written_again_and_the_run_completes(
            self, recompute_tier):
        state, _, calls = await _drive(
            load("workflows/answer-and-recompute.yaml"), _cut_first(1), REQUEST)
        assert state.status == "completed"
        assert state.outputs["answer_end"]["passed"] is True
        assert len(_answer_calls(calls)) == 2
        assert [c["function"] for c in calls].count("recompute") == 3

    async def test_it_tries_three_more_times_and_no_more(self, recompute_tier):
        # Cut three times, whole on the fourth: the last retry is the one
        # that gets through.
        state, _, calls = await _drive(
            load("workflows/answer-and-recompute.yaml"), _cut_first(3), REQUEST)
        assert state.status == "completed"
        assert len(_answer_calls(calls)) == 4

    async def test_when_every_attempt_is_cut_the_run_ends_blocked_after_four(
            self, recompute_tier):
        state, _, calls = await _drive(
            load("workflows/answer-and-recompute.yaml"), _cut_first(99), REQUEST)
        assert state.status == "blocked"
        assert state.reason.startswith("Answer incomplete: it ends mid-sentence")
        assert len(_answer_calls(calls)) == 4
        assert "recompute" not in [c["function"] for c in calls]
        assert state.candidate is not None

    async def test_a_whole_answer_is_written_once(self, recompute_tier):
        state, _, calls = await _drive(
            load("workflows/answer-and-recompute.yaml"), _cut_first(0), REQUEST)
        assert state.status == "completed"
        assert len(_answer_calls(calls)) == 1

    async def test_a_node_that_does_not_ask_for_it_writes_once(self, recompute_tier):
        spec = load("workflows/answer-and-recompute.yaml")
        implement = next(n for n in spec.nodes if n.id == "implement")
        implement.args.pop("cut_retries")
        state, _, calls = await _drive(spec, _cut_first(1), REQUEST)
        assert state.status == "blocked"
        assert len(_answer_calls(calls)) == 1

    def test_every_workflow_that_gates_on_a_cut_answer_asks_for_three_retries(self):
        gated = []
        for path in sorted(glob.glob(str(ROOT / "workflows" / "*.yaml"))):
            spec = load(path)
            if any(n.kind == "check" and n.check == "answer_ends_whole"
                   for n in spec.nodes):
                gated.append(Path(path).stem)
                implement = next(n for n in spec.nodes if n.id == "implement")
                assert implement.args.get("cut_retries", 0) >= 3, path
        # The guard read its subject before it judged it.
        assert gated == ["answer-and-recompute", "lean", "verify-first"]


def _recorded_answer(workflow_id: int) -> str:
    """The implement summary of one workflow of the hold-out's shard 2."""
    path = TRACES / "20261117T-holdout-phases-shard-2.jsonl"
    for line in open(path, encoding="utf-8"):
        row = json.loads(line)
        if (row["kind"] == "phase" and row["phase"] == "implement"
                and row["workflow_id"] == workflow_id):
            return row["verdict"]["summary"]
    raise AssertionError(f"no implement row for workflow {workflow_id}")


class TestTheTwoAnswersTheHoldoutBlocked:
    """Shard 2 of the hold-out blocked two answers as cut off. Read from
    their records, one is cut off and one is not."""

    def test_x3_draw_1_ends_on_the_word_of_and_is_cut(self):
        result = answer_ends_whole(_recorded_answer(1))
        assert result.passed is False
        assert result.data["signs"] == ["a last line ending on 'of'"]

    def test_x24_draw_2_ends_on_a_whole_sentence_and_is_not_cut(self):
        answer = _recorded_answer(22)
        # The two `\(` the check once counted as open math are in one jq line.
        assert answer.count("\\(") == 2 and answer.count("\\)") == 0
        assert answer.rstrip().endswith("schedule an upgrade to 1.26/1.27.")
        assert answer_ends_whole(answer).passed is True

    @pytest.mark.parametrize("text", [
        "Run it.\n\n```\njq '.[] | \"\\(.name)\"'\n```\n\nThat is the list.",
        "Interpolate with `\\(.name)` inside a jq string. That is all.",
    ])
    def test_a_math_delimiter_in_code_opens_nothing(self, text):
        assert answer_ends_whole(text).passed is True

    @pytest.mark.parametrize("text, sign", [
        ("The head is \\(H = 1.35 and the rest follows.", "open inline math"),
        ("Run it.\n\n```\njq .\n```\n\nThe head is \\[H = 1.35 and so.",
         "open display math"),
    ])
    def test_a_math_delimiter_left_open_in_prose_still_fails(self, text, sign):
        result = answer_ends_whole(text)
        assert result.passed is False and sign in result.data["signs"]
