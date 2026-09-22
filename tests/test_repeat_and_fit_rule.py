"""B19: a skipped unit must say which of the two reasons skipped it.

**The measurement.** On 2026-09-22 the B17-R1 validation ran `--repeat 2` and
produced **one unit**. The summary read:

    sweep budget: $0.1547 of $0.5000 · exhausted after 1 of 2 units

**$0.1547 is 31% of $0.50, and that is not exhaustion.** The unit was skipped by
the **fit rule** — with a $0.50 per-unit cap and $0.3453 remaining, no unit could
be *guaranteed* to fit, which is the conservative behaviour the fit rule exists
to provide. Reporting the conservative case in the exhausted case's words cost
half a registered sample and sent an investigation after an arithmetic bug that
was not there.

**The arithmetic was impossible from the start and nothing said so.** Two units
at a $0.50 cap need $1.00 of a $0.50 sweep. Exactly one unit could ever run. The
pre-registration asked for n=2 and the caps made n=2 unreachable on arrival.
"""

from __future__ import annotations

from autornd.evals.cli import sweep_summary
from autornd.evals.runner import SweepBudget


class TestTheFitRuleIsNotExhaustion:
    """The two reasons a unit is skipped, told apart."""

    def test_the_measured_case_reads_as_the_fit_rule(self):
        """The exact numbers from the lost run."""
        budget = SweepBudget(cap=0.50)
        budget.record(0.1547)
        assert not budget.can_start(0.50)          # as it happened

        message = budget.skip(0.50)
        assert "fit rule" in message
        assert "not exhausted" in message
        assert "$0.3453" in message                 # what was actually left

    def test_a_genuinely_exhausted_budget_still_says_exhausted(self):
        """The repair must not trade one wrong word for another."""
        budget = SweepBudget(cap=0.50)
        budget.record(0.50)
        assert "exhausted" in budget.skip(0.10)
        assert "fit rule" not in budget.skip(0.10)

    def test_the_backstop_mode_has_no_fit_rule_to_blame(self):
        """With no per-unit cap there is nothing to reason about in advance, so
        a skip there really is exhaustion."""
        budget = SweepBudget(cap=0.50)
        budget.record(0.50)
        assert "exhausted" in budget.skip(None)


class TestTheSummaryLine:
    def test_the_measured_line_no_longer_claims_exhaustion(self):
        budget = SweepBudget(cap=0.50)
        budget.record(0.1547)
        budget.skip(0.50)

        line = sweep_summary(budget)
        assert "exhausted" not in line
        assert "1 of 2 units ran" in line
        assert "no unit could be guaranteed to fit" in line

    def test_it_reports_produced_and_requested_separately(self):
        """Convention 28: the runner says how many units it produced before it
        reports a total, so a shortfall cannot hide inside an aggregate."""
        budget = SweepBudget(cap=1.00)
        budget.record(0.30)
        budget.record(0.30)
        budget.skip(0.50)

        line = sweep_summary(budget)
        assert "2 of 3 units ran" in line and "1 skipped" in line

    def test_a_real_exhaustion_still_says_so(self):
        budget = SweepBudget(cap=0.20)
        budget.record(0.20)
        budget.skip(0.05)
        assert "budget exhausted" in sweep_summary(budget)

    def test_a_complete_sweep_says_nothing_extra(self):
        budget = SweepBudget(cap=1.00)
        budget.record(0.10)
        assert sweep_summary(budget) == "sweep budget: $0.1000 of $1.0000"


class TestTheArithmeticIsCheckableBeforeSpending:
    """The free check that would have caught the registration."""

    def test_the_registered_configuration_permitted_exactly_one_unit(self):
        """`--max-spend 0.50 --max-spend-sweep 0.50` against `--repeat 2`."""
        assert SweepBudget(cap=0.50).units_that_can_ever_start(0.50) == 1

    def test_a_workable_configuration_permits_the_sample(self):
        assert SweepBudget(cap=0.50).units_that_can_ever_start(0.25) == 2
        assert SweepBudget(cap=1.00).units_that_can_ever_start(0.25) == 4

    def test_the_backstop_mode_cannot_be_predicted_and_says_so(self):
        """None, not zero and not infinity — with no per-unit cap there is
        genuinely nothing to compute, and returning a number would be an
        instrument asserting more than it measured."""
        assert SweepBudget(cap=0.50).units_that_can_ever_start(None) is None

    def test_a_zero_cap_does_not_divide_by_zero(self):
        assert SweepBudget(cap=0.50).units_that_can_ever_start(0.0) is None


class TestTheWarningReachesTheOperator:
    """End to end through the CLI, because the arithmetic being right proves
    nothing about whether anyone is told — which is the distinction that cost
    four guards today."""

    def test_an_impossible_sample_warns_before_any_call(self, capsys, monkeypatch):
        import asyncio

        import autornd.evals.cli as cli

        async def no_runs(*a, **k):
            raise AssertionError("a paid path was entered after the warning")

        monkeypatch.setattr(cli, "run_repeated", no_runs)
        monkeypatch.setattr(
            "sys.argv",
            ["prog", "--scenarios", "evals/scenarios/generalization/gen_marketing_claims.yaml",
             "--workflow", "engineering-rnd", "--repeat", "2",
             "--max-spend", "0.50", "--max-spend-sweep", "0.50"],
        )
        try:
            asyncio.run(cli.main())
        except AssertionError as exc:
            assert "paid path" in str(exc)          # we got past the warning
        except SystemExit:
            pass

        out = capsys.readouterr().out
        assert "permits at most 1 unit(s), not the 2 requested" in out
        assert "Raise --max-spend-sweep to $1.00" in out


class TestSkippedIsNotDecidedByReadingEnglish:
    """Found while fixing B19, and worse than B19.

    `ScenarioRun.skipped` was decided by substring-matching the error message
    against `("not applicable", "sweep budget exhausted")`. That is control flow
    reading English, which non-negotiable 3 forbids — and it broke the instant
    the fit rule's message was corrected: a skipped unit whose message no longer
    contained the word *exhausted* silently began counting as a unit that
    **ran**, which would have inflated the denominator of every pass rate in any
    sweep that hit its cap.

    It was caught by an existing test failing, which is the only reason it did
    not ship inside a change whose entire purpose was to correct that message.
    """

    def test_a_skip_is_flagged_not_parsed(self):
        from autornd.evals.runner import ScenarioRun
        from autornd.evals.scenario import Scenario

        run = ScenarioRun(
            scenario=Scenario(id="s", request="r", expect={}),
            results=[], calls=0, seconds=0.0,
            error="skipped: $0.3453 left of $0.50 cannot guarantee a unit "
                  "capped at $0.50 (fit rule — the budget is not exhausted)",
            was_skipped=True,
        )
        assert run.skipped

    def test_the_new_message_would_have_been_missed_by_the_old_parse(self):
        """The regression, asserted rather than remembered: the corrected
        message contains none of the words the old matcher looked for."""
        from autornd.evals.runner import ScenarioRun, SweepBudget

        budget = SweepBudget(cap=0.50)
        budget.record(0.1547)
        message = budget.skip(0.50)
        assert not any(marker in message for marker in ScenarioRun._SKIP_REASONS)

    def test_the_prose_fallback_still_serves_directly_built_runs(self):
        """Kept deliberately: tests and older paths construct a ScenarioRun
        from an error string alone. Removing the fallback would break them
        silently, which is the same class of failure one more time."""
        from autornd.evals.runner import ScenarioRun
        from autornd.evals.scenario import Scenario

        run = ScenarioRun(
            scenario=Scenario(id="s", request="r", expect={}),
            results=[], calls=0, seconds=0.0,
            error="not applicable to workflow 'triage-classify': no build loop",
        )
        assert run.skipped
