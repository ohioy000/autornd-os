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
from autornd.evals.runner import run_repeated
from autornd.evals.scenario import load_scenarios
from autornd.graph.spec import load as load_spec
from autornd.routing.openrouter import OpenRouterClient


def _spec(name: str):
    candidate = Path(name)
    if candidate.suffix and candidate.exists():
        return load_spec(candidate)
    return load_spec(Path("workflows") / f"{candidate.stem}.yaml")


def _settings() -> dict[str, int]:
    return {
        "max_iterations": settings.max_iterations,
        "escalation_recovery_attempts": settings.escalation_recovery_attempts,
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
                        help="stop a scenario once it has cost this much. Off by "
                             "default. Worth setting on any sweep that touches "
                             "the search tier — one sweep here ran forty minutes "
                             "and $1.28 before anyone stopped it")
    args = parser.parse_args()

    scenarios = load_scenarios(args.scenarios)
    targets = args.compare or [args.workflow]
    reports = []

    for name in targets:
        # A scenario that names its own workflow always runs against that one,
        # so a triage eval stays a triage eval no matter what is being compared.
        chosen = [s for s in scenarios if (s.workflow or name) == name]
        pinned = [s for s in scenarios if s.workflow and s.workflow != name]
        report = await run_repeated(
            chosen, _spec(name), lambda: OpenRouterClient(),
            _settings(), repeat=args.repeat, timeout=args.timeout,
            max_spend=args.max_spend,
        )
        for scenario in pinned:
            extra = await run_repeated(
                [scenario], _spec(scenario.workflow), lambda: OpenRouterClient(),
                _settings(), repeat=args.repeat, timeout=args.timeout,
                max_spend=args.max_spend,
            )
            report.results.extend(extra.results)
        report.results.sort(key=lambda r: r.scenario.id)
        reports.append((name, report))
        print(report.render())
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
