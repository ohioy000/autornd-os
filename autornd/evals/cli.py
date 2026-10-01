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

from autornd import preflight
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

# The exit code of a sweep the preflight gate refused. Distinct from 0 (every
# scenario passed), 1 (a scenario failed) and 2 (argparse's usage error), so
# a script driving a sweep can tell "nothing was run" from "it ran and failed".
PREFLIGHT_REFUSED_EXIT = 3


async def preflight_gate(skip: bool) -> tuple[dict, bool]:
    """Run the free preflight before any paid call. (header record, proceed).

    ARCH-20260930-096. The checks in autornd/preflight.py catch, for nothing,
    the apparatus deaths that otherwise cost a paid call to discover: a pin
    that serves no endpoint of its model (091 run 8, a 404 before the first
    call), and a pin the router strips by parameters (091 run 2, a 404 after
    eight paid calls). They ran only when someone remembered to run them.

    A preflight that cannot run is a refusal, not a pass: no evidence must
    never be reported as no problem (convention 28). The override is
    recorded, so a results file says whether its configuration was checked.
    """
    if skip:
        return {"ran": False, "override": True}, True
    try:
        findings = await preflight.run()
    except Exception as exc:
        return {"ran": False, "override": False, "passed": False,
                "error": f"{type(exc).__name__}: {exc}"}, False
    record = {
        "ran": True,
        "override": False,
        "passed": all(f.ok for f in findings),
        "findings": [{"ok": f.ok, "name": f.subject, "detail": f.detail}
                     for f in findings],
    }
    return record, record["passed"]


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
    parser.add_argument("--skip-preflight", action="store_true",
                        help="start without the free preflight. The results "
                             "header records the override. Without this flag a "
                             "failing preflight refuses the sweep before any "
                             f"paid call, exit code {PREFLIGHT_REFUSED_EXIT}")
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

    # Free, before the results file and before any client exists. A refused
    # sweep writes no results file: a header with no units is not a record of
    # a run, and 25 of them from one night are named in notebook section 83.3.
    preflight_record, proceed = await preflight_gate(args.skip_preflight)
    if args.skip_preflight:
        print("preflight: SKIPPED (--skip-preflight; recorded in the header)\n")
    elif not proceed:
        if "error" in preflight_record:
            print(f"preflight could not run: {preflight_record['error']}")
        for finding in preflight_record.get("findings", []):
            mark = "ok " if finding["ok"] else "FAIL"
            print(f"[{mark}] {finding['name']:34} {finding['detail']}")
        print(f"\nrefused: the preflight did not pass, so no paid call was made "
              f"(exit {PREFLIGHT_REFUSED_EXIT}). Fix the configuration, or pass "
              f"--skip-preflight to run anyway with the override recorded.")
        return PREFLIGHT_REFUSED_EXIT
    else:
        print(f"preflight: {len(preflight_record['findings'])} checks passed\n")

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
            # What was verified before the spend, or that it was skipped.
            "preflight": preflight_record,
        },
    )
    print(f"results: {results.path}")
    if results.mirror_path is not None:
        # B20: the primary path sits in the working tree and is not ignored, so
        # an ordinary `git stash -u` can unlink it mid-run. It did once, and
        # $0.1547 of measurement died with the handle.
        print(f"mirrored: {results.mirror_path}  "
              f"(outside the repo — no git operation here can reach it)")
    print()

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
