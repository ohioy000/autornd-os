"""Run the eval suite.

    python -m autornd.evals.cli                          # default workflow
    python -m autornd.evals.cli --workflow lean
    python -m autornd.evals.cli --compare engineering-rnd lean

Uses live models, so it costs money. Every run is bounded by the scenario's
max_calls and a wall-clock timeout; nothing here can run away.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

from autornd.config import settings
from autornd.evals.runner import (
    _BUDGET_EPSILON,
    ResultsLog,
    SweepBudget,
    default_results_path,
    run_repeated,
)
from autornd.evals.scenario import load_scenarios
from autornd.graph.spec import load as load_spec
from autornd.routing.openrouter import OpenRouterClient


# Every figure here is post-b4cd89f; anything earlier understates by 2.6x-295x.
# A wide triage sweep costs $0.01-0.03 and a grounding sweep $0.17-0.72, so the
# default clears real work by a wide margin. What it does not clear is the shape
# it exists for: a full workflow over the wide suite is 108 units at ~$0.1454,
# about $15.70. That stops here and needs a deliberate override to proceed.
SWEEP_CAP_DEFAULT = "1.00"


def parse_sweep_cap(value: str) -> SweepBudget | None:
    """The flag value as a budget, or None when the operator opts out."""
    if value.strip().lower() == "none":
        return None
    return SweepBudget(cap=float(value))


def sweep_summary(budget: SweepBudget) -> str:
    """What the sweep actually spent, and whether it ran to the end.

    Four decimals on the cap as well as the spend: a live check with
    --max-spend-sweep 0.001 printed "$0.0000 of $0.00", which reads as no
    budget at all precisely when the budget is tightest.
    """
    line = f"sweep budget: ${budget.spent:.4f} of ${budget.cap:.4f}"
    if budget.skipped:
        total = budget.started + budget.skipped
        # "exhausted" was written for one of the two ways a unit gets skipped
        # and printed for both. Measured 2026-09-22: one unit ran at $0.1547
        # of a $0.50 sweep and the line read "exhausted after 1 of 2 units" —
        # at 31% of the cap. The other way is the fit rule declining to start
        # a unit it cannot guarantee, which is not the budget running out.
        why = ("budget exhausted" if budget.remaining <= _BUDGET_EPSILON
               else f"${budget.remaining:.4f} left but no unit could be "
                    f"guaranteed to fit")
        line += (f" · {budget.started} of {total} units ran, "
                 f"{budget.skipped} skipped — {why}")
    return line


def _spec(name: str):
    candidate = Path(name)
    if candidate.suffix and candidate.exists():
        return load_spec(candidate)
    return load_spec(Path("workflows") / f"{candidate.stem}.yaml")


def _settings() -> dict[str, int]:
    return {
        "max_iterations": settings.max_iterations,
        "escalation_recovery_attempts": settings.escalation_recovery_attempts,
        "review_rework_attempts": settings.review_rework_attempts,
        "plan_max_tokens": settings.plan_max_tokens,
        "escalation_max_tokens": settings.escalation_max_tokens,
    }


async def main() -> int:
    parser = argparse.ArgumentParser(description="Run AutoRnD evals")
    parser.add_argument("--scenarios", default="evals/scenarios")
    parser.add_argument("--workflow", default=settings.autornd_workflow)
    parser.add_argument("--compare", nargs="+", metavar="WORKFLOW",
                        help="run the suite against several workflows and compare")
    parser.add_argument("--timeout", type=float, default=600.0,
                        help="per-scenario wall-clock limit in seconds")
    parser.add_argument("--repeat", type=int, default=3,
                        help="runs per scenario; models are stochastic, so one "
                             "result is an anecdote")
    parser.add_argument("--max-spend", type=float, default=None, metavar="USD",
                        help="stop ONE scenario-run once it has cost this much. "
                             "Bounds a single repetition, not the invocation — "
                             "see --max-spend-sweep for that. Off by default. "
                             "Worth setting on any sweep that touches the search "
                             "tier: one unattended sweep here ran forty minutes "
                             "and about $3.30 (the $1.28 it reported at the time "
                             "came from the meter that did not count search)")
    parser.add_argument("--max-spend-sweep", default=SWEEP_CAP_DEFAULT,
                        metavar="USD",
                        help=f"aggregate ceiling across the WHOLE invocation — "
                             f"every scenario, every repetition, every compared "
                             f"workflow. Defaults to ${SWEEP_CAP_DEFAULT}; pass "
                             f"'none' to disable. With --max-spend also set this "
                             f"is a hard guarantee: a unit that might not fit is "
                             f"never started")
    parser.add_argument("--results-file", default=None, metavar="PATH",
                        help="where to append per-unit JSONL results. Defaults "
                             "to evals/results/<utc-timestamp>-<suite>.jsonl. "
                             "Each line is flushed as its unit finishes, so an "
                             "interrupted sweep keeps everything it paid for")
    args = parser.parse_args()

    budget = parse_sweep_cap(args.max_spend_sweep)

    scenarios = load_scenarios(args.scenarios)
    targets = args.compare or [args.workflow]
    reports = []

    # Free, and before anything is paid. Measured 2026-09-22: a pre-registration
    # asked for n=2 under `--max-spend 0.50 --max-spend-sweep 0.50`. Two units
    # at a $0.50 cap need $1.00 of a $0.50 sweep, so exactly ONE unit could
    # ever start — the registered sample size was impossible on arrival and
    # nothing said so. The shortfall was then read as a defect (B19) and cost
    # an investigation on top of half the sample.
    #
    # A warning rather than a refusal: a deliberately over-tight cap is a
    # legitimate way to buy "as much as this much money allows".
    if budget is not None:
        permitted = budget.units_that_can_ever_start(args.max_spend)
        wanted = len(scenarios) * len(targets) * args.repeat
        if permitted is not None and permitted < wanted:
            print(
                f"⚠ this configuration permits at most {permitted} unit(s), "
                f"not the {wanted} requested: {wanted} × ${args.max_spend:.2f} "
                f"exceeds the ${budget.cap:.2f} sweep cap. The fit rule will "
                f"skip the rest before they start. Raise --max-spend-sweep to "
                f"${wanted * args.max_spend:.2f}, or lower --max-spend to "
                f"${budget.cap / wanted:.4f}, if you want the full sample.\n"
            )

    # The header makes a results file self-describing: which model ran at each
    # tier, who was pinned to serve it, and what the run was allowed to spend.
    # Without it a stored result cannot be priced against its serving later,
    # which is the diagnosis B4 turned on.
    results = ResultsLog(
        args.results_file or default_results_path(args.scenarios),
        config={
            "suite": args.scenarios,
            "workflows": targets,
            "repeat": args.repeat,
            "max_spend": args.max_spend,
            "max_spend_sweep": budget.cap if budget else None,
            "timeout": args.timeout,
            "models": OpenRouterClient.FUNCTION_MODELS,
            "provider_order": settings.openrouter_provider_order,
        },
    )
    print(f"results: {results.path}\n")

    for name in targets:
        # A scenario that names its own workflow always runs against that one,
        # so a triage eval stays a triage eval no matter what is being compared.
        chosen = [s for s in scenarios if (s.workflow or name) == name]
        pinned = [s for s in scenarios if s.workflow and s.workflow != name]
        report = await run_repeated(
            chosen, _spec(name), lambda: OpenRouterClient(),
            _settings(), repeat=args.repeat, timeout=args.timeout,
            max_spend=args.max_spend, budget=budget, results_log=results,
        )
        for scenario in pinned:
            # The same budget object, not a fresh one. This loop is the trap:
            # a per-call budget would let every pinned scenario, and every
            # compared workflow, spend the whole cap again.
            extra = await run_repeated(
                [scenario], _spec(scenario.workflow), lambda: OpenRouterClient(),
                _settings(), repeat=args.repeat, timeout=args.timeout,
                max_spend=args.max_spend, budget=budget, results_log=results,
            )
            report.results.extend(extra.results)
        report.results.sort(key=lambda r: r.scenario.id)
        reports.append((name, report))
        print(report.render())
        print()

    results.close()

    if budget is not None:
        print(sweep_summary(budget))
        print()

    if len(reports) > 1:
        print(f"{'workflow':<24}{'passed':>10}{'calls':>8}{'cost':>10}{'secs':>8}")
        print("-" * 60)
        for name, report in reports:
            print(f"{name:<24}{report.passed:>6}/{report.applicable:<3}"
                  f"{report.calls:>8}{report.cost:>10.4f}{report.seconds:>8.1f}")

    return 0 if all(
        all(r.passed or r.skipped for r in report.results)
        for _, report in reports
    ) else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
