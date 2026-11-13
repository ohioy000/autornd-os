"""A cut-off answer is not a finished one (the owner, 2026-11-13).

Golden batch 1 of 2026-11-13 delivered Q6 r2 as done and green: its text
stopped at character 1948, mid-sentence ("…reads as "), with its bold
open and no gate named, and no caution said so
(docs/reviews/2026-11-13-golden-decisions.md). The owner's word that day,
"yes to all 3", added a free check and a gate: a text that ends cut off
ends the run blocked with that reason, the answer kept as the candidate,
and nothing more paid for. No retry.

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
