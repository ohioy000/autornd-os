"""ARCH-20261001-101: the run record states exactly what happened.

098 found five places where it did not. Every test here drives a real path
(run_repeated or run_scenario, the real PhaseRunner, the billing double) and
reads the field back FROM THE WRITTEN JSONL, not from memory: 094's lesson
was a writer that dropped fields the in-memory tests never missed.

R5: the watchdog record says whether its pace was the node's or the tier's.
R6: the grounding's paid lookup is recorded, its questions and its answer.
R7: blockers_second_pass is [] unless the run re-planned; feasibility's
    hard blockers sit under feasibility_blockers.
R8: the unit record carries the terminal sentence for every terminal.
R9: the summary never says 'passed' without how the runs ended.
"""

from __future__ import annotations

import json

import pytest

from autornd.evals.runner import ResultsLog, _isolated_store, run_repeated
from autornd.evals.scenario import parse
from autornd.graph import executor as executor_module
from autornd.graph.spec import load
from tests.conftest import make_mock_client

SPEC = load("workflows/engineering-rnd.yaml")
SETTINGS = {"max_iterations": 5, "escalation_recovery_attempts": 1,
            "review_rework_attempts": 2}
REQUEST = "Specify the wiring for a 24 VDC sensor on a 3 ft 22 AWG run"

_WORK = {"feasible": True, "concerns": [], "blockers": [], "critical": False,
         "done": True, "green": True, "red_cause": None, "evidence": [],
         "summary": "Drop is 2 x 3 ft x 0.01614 ohm/ft x 0.050 A = 0.004842 V.",
         "ship": True, "findings": [], "verdict": "Ship."}
LOOKUP_ANSWER = "22 AWG solid copper is 16.14 ohm per 1000 ft at 20 C."
BLOCKING = "What is the resistance of 22 AWG solid copper?"


def _responses(**overrides) -> dict:
    out = {
        "triage": {"domains": ["hardware"], "risk": "medium",
                   "specialists": ["hardware_engineer", "test_engineer"],
                   "summary": "Sensor wiring", "unrecallable": False},
        # Serves query expansion and request scoping alike: with an empty
        # store the grounding scopes the request, and its blocking unknown
        # is what the paid lookup asks.
        "research": {"queries": ["22 AWG resistance"], "objective": "Wire it.",
                     "unknowns": [BLOCKING], "blocking_unknowns": [BLOCKING]},
        "search": {"answer": LOOKUP_ANSWER},
        "architecture": {"ready": True, "plan": "Show the drop.", "blockers": [],
                         "success_criteria": ["The drop arithmetic is shown"]},
        "engineering": dict(_WORK),
        "judge": dict(_WORK),
        "escalation": {"root_cause_analysis": "x", "resolution_directive": "y",
                       "requires_human": True},
    }
    for function, patch in overrides.items():
        out[function] = {**out[function], **patch}
    return out


async def _units(tmp_path, client_factory, timeout=60.0, repeat=1):
    path = tmp_path / "units.jsonl"
    scenario = parse({"id": "record", "request": REQUEST, "timeout": timeout})
    with _isolated_store(), ResultsLog(path, {"suite": "record"}) as log:
        report = await run_repeated([scenario], SPEC, client_factory, SETTINGS,
                                    repeat=repeat, timeout=timeout, results_log=log)
    lines = [json.loads(line) for line in path.read_text().splitlines()]
    return report, [line for line in lines if line["record"] == "unit"]


class TestR6TheGroundingLookupIsRecorded:
    async def test_its_questions_and_answer_are_in_the_written_record(self, tmp_path):
        _, (unit,) = await _units(tmp_path, lambda: make_mock_client(_responses()))
        lookup = unit["verdicts"]["context"]["lookup"]
        assert lookup["asked"] == [BLOCKING]
        assert lookup["found"] == 1
        assert LOOKUP_ANSWER in lookup["findings"]
        assert lookup["truncated"] is False
        assert lookup["bound_chars"] == lookup["bound_chars"] > 0
        # `asked` beside it is the retrieval queries, a different list.
        assert unit["verdicts"]["context"]["asked"] == ["22 AWG resistance"]

    async def test_no_lookup_reads_as_none_not_as_an_empty_answer(self, tmp_path):
        _, (unit,) = await _units(tmp_path, lambda: make_mock_client(
            _responses(research={"blocking_unknowns": []})))
        assert unit["verdicts"]["context"]["lookup"] is None


class TestR7FeasibilityBlockersAreNotASecondPass:
    async def test_on_a_run_that_did_not_replan(self, tmp_path):
        hard = "Solid wire is unsuitable under vibration."
        _, (unit,) = await _units(tmp_path, lambda: make_mock_client(
            _responses(engineering={"blockers": [hard]})))
        assert unit["regrounding"]["rounds"] == 0
        assert unit["regrounding"]["blockers_second_pass"] == []
        # One per feasibility reviewer: each named it.
        reviewed = unit["verdicts"]["feasibility"]["reviewed"]
        assert reviewed >= 1
        assert unit["feasibility_blockers"] == [hard] * reviewed


class TestR8AndR9TheTerminalIsWrittenAndSaid:
    async def test_a_watchdog_end_writes_its_sentence(self, tmp_path):
        report, (unit,) = await _units(
            tmp_path,
            lambda: make_mock_client(_responses(), delays={"judge": 3.0}),
            timeout=1.2)
        assert unit["status"] == "blocked" and unit["error"] is None
        assert unit["reason"].startswith("stopped by the deliberation watchdog")
        # R9: the summary says how the runs ended beside 'passed'.
        assert "runs ended blocked 1" in report.render()

    async def test_a_workflow_terminal_writes_its_sentence_too(self, tmp_path):
        # Not the watchdog's: this double's build judges never agree, so the
        # build loop exhausts into escalation, which requires a human.
        report, (unit,) = await _units(tmp_path, lambda: make_mock_client(_responses()))
        assert unit["status"] == "blocked" and unit["error"] is None
        assert unit["reason"].startswith("Escalation requires human intervention")
        assert unit["watchdog"]["fired"] is False
        assert "runs ended blocked 1" in report.render()


class TestR5ThePaceBasisIsWritten:
    async def test_a_node_keyed_refusal_says_node(self, tmp_path, monkeypatch):
        # validate's own first call (0.5 s) is its pace when it is next
        # reached. With a 0.05 s reserve and a
        # 1.45 s budget there is not 0.5 s left, so validate is not started.
        monkeypatch.setattr(executor_module, "WATCHDOG_RESERVE_SECONDS", 0.05)
        _, (unit,) = await _units(
            tmp_path,
            lambda: make_mock_client(_responses(judge={"ship": False}),
                                     delays={"judge": 0.5}),
            timeout=1.45)
        watchdog = unit["watchdog"]
        assert watchdog["fired"] and watchdog["rule"] == "not_started", unit["reason"]
        # Observed 3 of 3 before commit: about 0.1 s available against 0.5 s.
        assert watchdog["node"] == "validate"
        assert watchdog["pace_basis"] == "node"
        assert watchdog["pace_seconds"] == pytest.approx(0.5, abs=0.15)
        assert "this node's pace" in unit["reason"]
