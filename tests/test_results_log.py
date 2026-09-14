"""A sweep keeps what it pays for.

Two defects, both discovered by paying for them, both fixed by the same file:

- **The harness discarded the verdicts it bought.** `ScenarioRun` kept cost,
  calls and assertion outcomes, but not the typed verdicts, so a past sweep
  could not be diagnosed after the fact. Blueprint 005 set out to read eighteen
  triage verdicts it had already paid for and found nothing left to read; the
  diagnosis step was structurally impossible and had to be abandoned.
- **A killed sweep lost everything.** The report rendered only after the last
  unit, so an interrupted run threw away every unit it had completed —
  measured at about $0.018 on one interrupted invocation, which then had to be
  repeated in full.

Both are why a record carries `providers_by_function` as well as the numbers:
§6.1's lesson is that a score is partly a record of who answered, and a
retained result that omits the serving cannot support a B4-class diagnosis —
which was the whole point of retaining it.
"""

from __future__ import annotations

import json

import pytest

from autornd.evals.runner import ResultsLog, default_results_path, run_repeated
from autornd.evals.scenario import parse
from autornd.graph.spec import load
from tests.test_evals import SETTINGS, scripted
from tests.test_sweep_budget import billing_client

TRIAGE_CLASSIFY = "workflows/triage-classify.yaml"


def read(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


@pytest.mark.asyncio
class TestARunIsWrittenAsItGoes:
    async def test_a_two_unit_run_writes_a_header_and_two_units(self, tmp_path):
        log = ResultsLog(tmp_path / "r.jsonl", config={"suite": "t", "repeat": 2})
        report = await run_repeated(
            [parse({"id": "s", "request": "Add retry", "expect": {"risk": "medium"}})],
            load(TRIAGE_CLASSIFY),
            lambda: billing_client(scripted("medium"), per_call=0.001),
            SETTINGS, repeat=2, results_log=log)
        log.close()

        records = read(tmp_path / "r.jsonl")
        assert records[0]["record"] == "header"
        assert records[0]["suite"] == "t" and records[0]["repeat"] == 2
        assert "written_at" in records[0]

        units = [r for r in records if r["record"] == "unit"]
        assert len(units) == 2
        assert [u["repetition"] for u in units] == [1, 2]

    async def test_the_file_replays_to_the_same_verdict_as_the_report(self, tmp_path):
        """A stored result that disagrees with the run is worse than none."""
        log = ResultsLog(tmp_path / "r.jsonl")
        report = await run_repeated(
            [parse({"id": "s", "request": "Add retry", "expect": {"risk": "medium"}}),
             parse({"id": "t", "request": "Add retry", "expect": {"risk": "critical"}})],
            load(TRIAGE_CLASSIFY),
            lambda: billing_client(scripted("medium"), per_call=0.001),
            SETTINGS, repeat=1, results_log=log)
        log.close()

        on_disk = {u["scenario"]: u["passed"]
                   for u in read(tmp_path / "r.jsonl") if u["record"] == "unit"}
        in_memory = {r.scenario.id: r.passed for r in report.results}
        assert on_disk == in_memory
        assert in_memory == {"s": True, "t": False}, "the doubles classify medium"


@pytest.mark.asyncio
class TestAnInterruptedSweepKeepsWhatItBought:
    async def test_the_first_units_record_survives_an_abort(self, tmp_path):
        """The abort is simulated rather than a real kill: CI must not depend on
        process signals, and what is under test is durability-on-append, not the
        signal path. If the line is on disk before unit two starts, any way of
        dying after that point keeps it."""
        path = tmp_path / "r.jsonl"
        log = ResultsLog(path)
        scenarios = [parse({"id": f"s{i}", "request": "Add retry"}) for i in range(3)]

        for i, scenario in enumerate(scenarios):
            await run_repeated(
                [scenario], load(TRIAGE_CLASSIFY),
                lambda: billing_client(scripted("medium"), per_call=0.001),
                SETTINGS, repeat=1, results_log=log)
            if i == 0:
                # Die here: no close(), no flush of our own, nothing tidy.
                break

        units = [r for r in read(path) if r["record"] == "unit"]
        assert len(units) == 1, "the completed unit must survive an untidy exit"
        assert units[0]["scenario"] == "s0"
        assert units[0]["cost"] > 0, "and it must still carry what it cost"


@pytest.mark.asyncio
class TestARecordCarriesEnoughToDiagnoseWith:
    async def test_it_keeps_the_verdicts_and_who_served_them(self, tmp_path):
        log = ResultsLog(tmp_path / "r.jsonl")
        await run_repeated(
            [parse({"id": "s", "request": "Add retry"})], load(TRIAGE_CLASSIFY),
            lambda: billing_client(scripted("high"), per_call=0.001),
            SETTINGS, repeat=1, results_log=log)
        log.close()

        unit = [r for r in read(tmp_path / "r.jsonl") if r["record"] == "unit"][0]

        # The verdict text 005 went looking for and could not find.
        assert "triage" in unit["verdicts"], unit["verdicts"]
        assert unit["verdicts"]["triage"]["risk"] == "high"
        assert unit["verdicts"]["triage"]["summary"]

        assert "providers_by_function" in unit
        assert unit["cost_by_tier"] and unit["calls_by_tier"]
        assert unit["status"] == "completed"
        assert isinstance(unit["assertions"], list)

    async def test_verdicts_survive_the_json_round_trip(self, tmp_path):
        """Pydantic models are dumped in JSON mode, so a result file can be read
        without importing the schemas back."""
        log = ResultsLog(tmp_path / "r.jsonl")
        await run_repeated(
            [parse({"id": "s", "request": "Add retry"})], load(TRIAGE_CLASSIFY),
            lambda: billing_client(scripted("medium"), per_call=0.001),
            SETTINGS, repeat=1, results_log=log)
        log.close()
        raw = (tmp_path / "r.jsonl").read_text()
        assert "RiskLevel." not in raw, "enums must serialise by value, not repr"


class TestTheDefaultPath:
    def test_it_is_timestamped_and_names_the_suite(self):
        path = default_results_path("evals/scenarios/wide")
        assert path.parent.as_posix() == "evals/results"
        assert path.name.endswith("-wide.jsonl")
        assert path.name[:4].isdigit(), path.name

    def test_a_single_file_suite_keeps_its_name(self):
        assert default_results_path(
            "evals/scenarios/wide/wide_legal_ops.yaml").name.endswith(
                "-wide_legal_ops.jsonl")


@pytest.mark.asyncio
class TestAFailedRunKeepsWhatItCompleted:
    """Found by execution, not by design: a transport error partway through a
    live probe discarded every verdict already paid for, because run_scenario
    replaced the executor's state with a blank one in its exception handlers.
    The runs worth diagnosing are precisely the ones that broke."""

    async def test_verdicts_survive_an_exception_mid_run(self, tmp_path):
        from unittest.mock import AsyncMock

        from autornd.routing.openrouter import ModelResponse, OpenRouterClient

        calls = {"n": 0}

        def exploding_client():
            client = OpenRouterClient(api_key="test")
            base = scripted("medium")

            async def chat_json(function, system_prompt, user_message, **kw):
                calls["n"] += 1
                client._account(function, 0.001)
                if calls["n"] > 1:            # triage lands, then the wire dies
                    raise RuntimeError("ReadError")
                data = base(user_message)
                return data, ModelResponse(content=json.dumps(data), model="mock",
                                           prompt_tokens=1, completion_tokens=1,
                                           cost=0.001)

            client.chat_json = AsyncMock(side_effect=chat_json)
            client.chat = AsyncMock(side_effect=RuntimeError("ReadError"))
            client.close = AsyncMock()
            return client

        log = ResultsLog(tmp_path / "r.jsonl")
        await run_repeated(
            [parse({"id": "s", "request": "Add retry"})],
            load("workflows/engineering-rnd.yaml"),
            exploding_client, SETTINGS, repeat=1, results_log=log)
        log.close()

        unit = [r for r in read(tmp_path / "r.jsonl") if r["record"] == "unit"][0]
        assert unit["error"], "the failure is still reported"
        assert "triage" in unit["verdicts"], (
            "the verdict that completed before the break must survive it")
        assert unit["verdicts"]["triage"]["risk"] == "medium"


class TestRefusedLookupsAreLoud:
    """A poisoned unit scores zero and reads exactly like a model that found
    nothing. 007 lost most of two eval arms to that: a spend ceiling began
    refusing every completion partway through a sweep, the affected units ran
    and scored zero, and only a hand count of lookups per unit told the two
    apart — after the scores had been written down."""

    def test_the_report_says_so_when_lookups_were_refused(self):
        from autornd.evals.runner import _refusal_line

        class Run:
            def __init__(self, n):
                self.refused_lookups = n

        assert _refusal_line([Run(0), Run(0)]) == ""
        line = _refusal_line([Run(3), Run(0), Run(1)])
        assert "4 lookup(s) refused across 2 unit(s)" in line
        assert "not a measurement of the model" in line

    def test_the_counter_resets_between_units(self):
        from autornd.knowledge import research

        research.reset_refused_lookups()
        assert research.refused_lookups() == 0
