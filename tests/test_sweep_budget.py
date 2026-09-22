"""The sweep-level spend cap (B3).

`--max-spend` bounds one scenario-run. Every repetition builds a fresh client
carrying that ceiling, so the flag says nothing at all about what an invocation
costs in total: 36 scenarios at 3 repetitions with `--max-spend 0.25` is a $27
ceiling, not a $0.25 one. That is the same defect as B10 in a different place —
a budget counting the wrong unit.

Every double here bills through `client._account`, per convention 9. A free
double cannot test a spend ceiling at all, which is the point of the rule.

Per-unit call counts used below were measured, not assumed:
`triage-classify` is 1 call, `engineering-rnd` is 10 under these doubles.
"""

from __future__ import annotations

import json

import pytest
from unittest.mock import AsyncMock

from autornd.evals.runner import (
    SweepBudget,
    run_repeated,
    run_scenario,
    run_suite,
)
from autornd.evals.scenario import parse
from autornd.graph.spec import load
from autornd.routing.openrouter import ModelResponse, OpenRouterClient
from tests.test_evals import SETTINGS, scripted


def billing_client(reply, per_call: float, search_cost: float | None = None):
    """The test_evals double, with a price per call and a mocked `chat`.

    `chat` is mocked here and not in test_evals because the scripted replies
    there never produce unknowns, so the search path is never reached. A budget
    test that wants to land on the search tier has to reach it — and must not
    reach the network to do so.
    """
    client = OpenRouterClient(api_key="test")

    async def chat_json(function, system_prompt, user_message, **kw):
        data = reply(user_message)
        client._account(function, per_call)
        return data, ModelResponse(content=json.dumps(data), model="mock",
                                   prompt_tokens=1, completion_tokens=1,
                                   cost=per_call)

    async def chat(function, system_prompt, user_message, **kw):
        cost = per_call if search_cost is None else search_cost
        client._account(function, cost)
        return ModelResponse(content="A: a figure [1] https://example.org/ds.pdf",
                             model="mock", prompt_tokens=1, completion_tokens=1,
                             cost=cost, citations=["https://example.org/ds.pdf"])

    client.chat_json = AsyncMock(side_effect=chat_json)
    client.chat = AsyncMock(side_effect=chat)
    client.close = AsyncMock()
    return client


def grounded(risk="medium"):
    """Scripted replies that navigate grounding to the search tier.

    The trap recorded in §9.2: a double returning nonsense query expansions
    retrieves nothing and falls through to a branch you were not measuring. The
    store is empty in every unit anyway (run_scenario isolates it), so the
    scoping branch is the one to answer — with unknowns, or no lookup happens.
    """
    base = scripted(risk)

    def reply(message: str) -> dict:
        m = message.lower()
        if "write the search qu" in m:
            return {"queries": ["retry backoff cap", "jitter policy"]}
        if "no documentation" in m or "unspecified" in m or "restate" in m:
            return {"objective": "add retry", "unknowns": ["the backoff ceiling"],
                    "blocking_unknowns": ["the backoff ceiling"],
                    "assumptions": [], "considerations": []}
        return base(message)
    return reply


def units(n: int, prefix: str = "s"):
    return [parse({"id": f"{prefix}{i}", "request": "Add retry with capped backoff"})
            for i in range(n)]


TRIAGE_CLASSIFY = "workflows/triage-classify.yaml"
FULL = "workflows/engineering-rnd.yaml"


@pytest.mark.asyncio
class TestFitRule:
    """Both caps set: a unit that might not fit is never started.

    Deliberately conservative — a unit is skipped even when it would have cost
    less than its own cap. The payoff is that the sweep cap is a hard guarantee
    rather than an estimate, and no unit is ever killed mid-flight by it.
    """

    async def test_units_that_cannot_fit_never_start(self):
        budget = SweepBudget(cap=1.20)
        report = await run_repeated(
            units(3), load(TRIAGE_CLASSIFY),
            lambda: billing_client(scripted("medium"), per_call=0.50),
            SETTINGS, repeat=1, max_spend=0.50, budget=budget)

        ran = [r for r in report.results if not r.skipped]
        skipped = [r for r in report.results if r.skipped]

        assert len(ran) == 2, "two units fit in $1.20 at $0.50 each"
        assert len(skipped) == 1, "the third cannot be guaranteed to fit"
        assert budget.spent == pytest.approx(1.00)
        assert budget.spent <= budget.cap, "the fit rule makes the cap a hard ceiling"

    async def test_a_skipped_unit_says_why(self):
        budget = SweepBudget(cap=0.60)
        report = await run_repeated(
            units(2), load(TRIAGE_CLASSIFY),
            lambda: billing_client(scripted("medium"), per_call=0.50),
            SETTINGS, repeat=1, max_spend=0.50, budget=budget)

        skipped = [r for r in report.results if r.skipped]
        assert len(skipped) == 1
        error = skipped[0].runs[0].error or ""
        # Convention 17, decided 2026-09-22: this test was wrong, not the code.
        # It asserted "sweep budget exhausted" for a budget with $0.10 of $0.60
        # STILL IN IT — enshrining the exact confusion B19 turned out to be.
        # The unit is skipped by the fit rule, which declines to start a unit it
        # cannot guarantee; that is not the budget running out, and calling it
        # so cost half a registered sample on a live run.
        assert "fit rule" in error
        assert "not exhausted" in error
        assert "$0.1000 left of $0.60" in error, (
            f"the numbers belong in the marker: {error}")

    async def test_no_unit_is_aborted_mid_flight(self):
        budget = SweepBudget(cap=1.20)
        report = await run_repeated(
            units(3), load(TRIAGE_CLASSIFY),
            lambda: billing_client(scripted("medium"), per_call=0.50),
            SETTINGS, repeat=1, max_spend=0.50, budget=budget)

        for result in report.results:
            for run in result.runs:
                assert "stopped at $" not in (run.error or ""), (
                    "the fit rule exists so the sweep cap never kills a unit")


@pytest.mark.asyncio
class TestBackstop:
    """No per-unit cap: a unit starts while budget remains and is stopped by the
    client's own ceiling the moment the total crosses. Overshoot is bounded by
    one model call, because the ceiling is checked after each call is billed."""

    async def test_the_crossing_unit_dies_and_later_units_are_skipped(self):
        budget = SweepBudget(cap=1.20)
        report = await run_repeated(
            units(4), load(FULL),
            lambda: billing_client(scripted("medium"), per_call=0.05),
            SETTINGS, repeat=1, budget=budget)

        errors = [r.runs[0].error or "" for r in report.results]
        # 10 calls x $0.05 = $0.50 a unit, so two complete and the third crosses.
        assert errors[0] == "" and errors[1] == ""
        assert "stopped at $" in errors[2], f"expected a budget abort, got {errors[2]!r}"
        assert "sweep budget exhausted" in errors[3]

    async def test_overshoot_is_bounded_by_the_calls_already_in_flight(self):
        """Not by ONE call, which is what the design assumed.

        Feasibility, domain review and final review all fan out with
        asyncio.gather (phases.py:310, 512, 725), so several calls can be in
        flight when the ceiling trips and every one of them bills. The real
        bound is the widest fan-out, not one — measured here at two calls with
        a two-specialist roster.

        This is why the fit rule matters: with a per-unit cap set there is no
        overshoot at all, because no unit is ever started that could exceed the
        budget. The backstop is the weaker guarantee of the two.
        """
        budget = SweepBudget(cap=1.20)
        await run_repeated(
            units(4), load(FULL),
            lambda: billing_client(scripted("medium"), per_call=0.05),
            SETTINGS, repeat=1, budget=budget)

        assert budget.spent > budget.cap, "the backstop trades exactness for progress"
        assert budget.spent == pytest.approx(1.30), (
            f"two in-flight calls past a $1.20 cap at $0.05: {budget.spent}")
        assert budget.spent <= budget.cap + 2 * 0.05 + 1e-9

    async def test_the_fit_rule_has_no_overshoot_at_all(self):
        """The contrast that makes the previous test's looser bound acceptable."""
        budget = SweepBudget(cap=1.20)
        await run_repeated(
            units(4), load(FULL),
            lambda: billing_client(scripted("medium"), per_call=0.05),
            SETTINGS, repeat=1, max_spend=0.50, budget=budget)

        assert budget.spent <= budget.cap, (
            f"with both caps set the sweep cap is exact: {budget.spent}")

    async def test_the_unit_ceiling_is_the_remaining_budget(self):
        budget = SweepBudget(cap=1.00, spent=0.75)
        assert budget.unit_ceiling(None) == pytest.approx(0.25)
        # Composed, not duplicated: whichever binds first wins.
        assert budget.unit_ceiling(0.10) == pytest.approx(0.10)
        assert budget.unit_ceiling(0.90) == pytest.approx(0.25)


@pytest.mark.asyncio
class TestOneBudgetSpansTheWholeInvocation:
    """The trap in --compare: the CLI makes several run_repeated calls, and a
    per-call budget would let each one spend the whole cap again."""

    async def test_exhaustion_in_the_first_call_starves_the_second(self):
        budget = SweepBudget(cap=1.20)
        first = await run_repeated(
            units(2, "a"), load(TRIAGE_CLASSIFY),
            lambda: billing_client(scripted("medium"), per_call=0.50),
            SETTINGS, repeat=1, max_spend=0.50, budget=budget)
        second = await run_repeated(
            units(2, "b"), load(TRIAGE_CLASSIFY),
            lambda: billing_client(scripted("medium"), per_call=0.50),
            SETTINGS, repeat=1, max_spend=0.50, budget=budget)

        assert all(not r.skipped for r in first.results)
        assert all(r.skipped for r in second.results), (
            "a second workflow must not get a fresh budget")
        assert budget.spent == pytest.approx(1.00)

    async def test_run_suite_takes_a_budget_too(self):
        """Symmetry: tests and callers may use either entry point."""
        budget = SweepBudget(cap=0.60)
        report = await run_suite(
            units(3), load(TRIAGE_CLASSIFY),
            lambda: billing_client(scripted("medium"), per_call=0.50),
            SETTINGS, max_spend=0.50, budget=budget)
        assert sum(1 for r in report.runs if r.skipped) == 2


@pytest.mark.asyncio
class TestRepetitionsCountAsUnits:
    async def test_the_budget_spans_repetitions_of_one_scenario(self):
        budget = SweepBudget(cap=1.20)
        report = await run_repeated(
            units(1), load(TRIAGE_CLASSIFY),
            lambda: billing_client(scripted("medium"), per_call=0.50),
            SETTINGS, repeat=5, max_spend=0.50, budget=budget)

        runs = report.results[0].runs
        assert sum(1 for r in runs if not r.skipped) == 2, (
            "five repetitions at $0.50 do not fit in $1.20")
        assert budget.spent == pytest.approx(1.00)


@pytest.mark.asyncio
class TestTheAbortLandsOnTheExpensiveTier:
    """A budget that only ever stops cheap calls proves nothing. Search is 61%
    of a full workflow, so the case worth testing is the one where the ceiling
    is crossed by the lookup itself."""

    async def test_the_search_call_is_what_crosses_the_cap(self):
        budget = SweepBudget(cap=0.20)
        report = await run_repeated(
            units(1), load(FULL),
            lambda: billing_client(grounded(), per_call=0.01, search_cost=0.50),
            SETTINGS, repeat=1, budget=budget)

        run = report.results[0].runs[0]
        assert "stopped at $" in (run.error or ""), run.error
        assert "search" in run.cost_by_tier, (
            f"the run never reached the search tier: {run.cost_by_tier}")
        assert run.cost_by_tier["search"] == pytest.approx(0.50)
        assert run.calls == 4, (
            f"triage, two grounding calls, then the lookup: {run.calls_by_tier}")


@pytest.mark.asyncio
class TestNoBudgetIsTheOldBehaviour:
    """C5 regression. --max-spend on its own must behave exactly as before."""

    async def test_max_spend_alone_still_bounds_only_the_unit(self):
        report = await run_repeated(
            units(3), load(TRIAGE_CLASSIFY),
            lambda: billing_client(scripted("medium"), per_call=0.50),
            SETTINGS, repeat=1, max_spend=0.50)

        assert all(not r.skipped for r in report.results), (
            "without a sweep budget nothing is skipped for spend")
        assert report.cost == pytest.approx(1.50), (
            "three units at $0.50 with a $0.50 per-unit cap costs $1.50 — "
            "which is exactly the defect B3 exists to bound")


class TestSweepBudgetArithmetic:
    def test_can_start_uses_the_fit_rule_when_both_caps_are_set(self):
        budget = SweepBudget(cap=1.00, spent=0.60)
        assert budget.can_start(0.40) is True      # exactly fits
        assert budget.can_start(0.41) is False

    def test_can_start_uses_the_backstop_when_there_is_no_unit_cap(self):
        assert SweepBudget(cap=1.00, spent=0.99).can_start(None) is True
        assert SweepBudget(cap=1.00, spent=1.00).can_start(None) is False

    def test_float_noise_does_not_close_the_budget_early(self):
        """0.1 * 3 is not 0.3. Without an epsilon the third unit is refused."""
        budget = SweepBudget(cap=0.30)
        for _ in range(2):
            assert budget.can_start(0.10)
            budget.record(0.10)
        assert budget.can_start(0.10), "0.1+0.1+0.1 must still fit in 0.3"

    def test_record_counts_every_unit_including_failed_ones(self):
        budget = SweepBudget(cap=1.00)
        budget.record(0.25)
        budget.record(0.0)
        assert budget.spent == pytest.approx(0.25)
        assert budget.remaining == pytest.approx(0.75)


class TestTheFlag:
    def test_absent_means_the_measured_default(self):
        from autornd.evals.cli import SWEEP_CAP_DEFAULT, parse_sweep_cap

        budget = parse_sweep_cap(SWEEP_CAP_DEFAULT)
        assert budget is not None and budget.cap == pytest.approx(1.00)

    def test_none_disables_it(self):
        from autornd.evals.cli import parse_sweep_cap

        assert parse_sweep_cap("none") is None
        assert parse_sweep_cap("NONE") is None

    def test_a_number_is_taken_as_dollars(self):
        from autornd.evals.cli import parse_sweep_cap

        budget = parse_sweep_cap("0.25")
        assert budget is not None and budget.cap == pytest.approx(0.25)

    def test_the_summary_line_reports_what_was_spent(self):
        from autornd.evals.cli import sweep_summary

        budget = SweepBudget(cap=1.00)
        budget.record(0.40)
        budget.started = 4
        assert sweep_summary(budget) == "sweep budget: $0.4000 of $1.0000"

        budget.skipped = 2
        # Also convention 17. $0.40 of $1.00 is not an exhausted budget, and the
        # line said "exhausted" for it. It now reports produced and requested
        # separately and names which of the two reasons applied.
        assert sweep_summary(budget) == (
            "sweep budget: $0.4000 of $1.0000 · 4 of 6 units ran, 2 skipped — "
            "$0.6000 left but no unit could be guaranteed to fit")

    def test_a_sub_cent_cap_is_not_rounded_to_nothing(self):
        """The live check printed "$0.00" for a $0.001 cap."""
        from autornd.evals.cli import sweep_summary

        assert "of $0.0010" in sweep_summary(SweepBudget(cap=0.001))
