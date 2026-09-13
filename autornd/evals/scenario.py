"""A scenario: one request, and what a good run of it looks like.

Expectations are written before the run, which is the only way they mean
anything. Every field is optional — a scenario that only pins the risk level is
a useful scenario, and one that pins everything is a brittle one.

    id: rnd_hardware_routing
    request: "Route 24V from the PCB to the laser sensor"
    expect:
      domains: [hardware]          # triage must find these
      risk: high
      specialists_include: [hardware_engineer]
      status: completed
      converge_within: 2           # implement/validate iterations
      max_calls: 16                # cost regression guard
      criteria_addressed: true     # the free check must pass
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

__all__ = ["Scenario", "ScenarioError", "load_scenario", "load_scenarios", "parse"]


class ScenarioError(ValueError):
    """A scenario file is malformed."""


_KNOWN_EXPECTATIONS = {
    "domains", "domains_include", "risk", "risk_at_least",
    "specialists_include", "specialists_exclude",
    "status", "converge_within", "max_calls", "criteria_addressed",
}

# Risk ordering, for `risk_at_least`. Under-classifying risk is the dangerous
# direction: a critical change triaged as low gets one reviewer.
RISK_ORDER = ["low", "medium", "high", "critical"]


@dataclass
class Scenario:
    id: str
    request: str
    description: str = ""
    expect: dict[str, Any] = field(default_factory=dict)
    tags: list[str] = field(default_factory=list)

    @property
    def max_calls(self) -> int | None:
        """A hard ceiling for the run, so one scenario cannot run away."""
        return self.expect.get("max_calls")


def parse(raw: dict[str, Any], source: str = "<inline>") -> Scenario:
    if not isinstance(raw, dict):
        raise ScenarioError(f"{source}: a scenario must be a mapping")

    for required in ("id", "request"):
        if not raw.get(required):
            raise ScenarioError(f"{source}: scenario needs '{required}'")

    expect = raw.get("expect") or {}
    if not isinstance(expect, dict):
        raise ScenarioError(f"{source}: 'expect' must be a mapping")

    unknown = set(expect) - _KNOWN_EXPECTATIONS
    if unknown:
        raise ScenarioError(
            f"{source}: unknown expectation(s) {sorted(unknown)}. "
            f"Known: {sorted(_KNOWN_EXPECTATIONS)}"
        )

    for key in ("risk", "risk_at_least"):
        value = expect.get(key)
        if value is not None and value not in RISK_ORDER:
            raise ScenarioError(
                f"{source}: {key} is {value!r}; expected one of {RISK_ORDER}"
            )

    for key in ("converge_within", "max_calls"):
        value = expect.get(key)
        if value is not None and (not isinstance(value, int) or value < 1):
            raise ScenarioError(f"{source}: {key} must be a positive integer")

    return Scenario(
        id=raw["id"],
        request=raw["request"],
        description=raw.get("description", ""),
        expect=expect,
        tags=list(raw.get("tags") or []),
    )


def load_scenario(path: str | Path) -> Scenario:
    file = Path(path)
    try:
        data = yaml.safe_load(file.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise ScenarioError(f"{file} is not valid YAML: {exc}") from exc
    return parse(data, str(file))


def load_scenarios(path: str | Path) -> list[Scenario]:
    """Load one scenario file, or every .yaml in a directory."""
    target = Path(path)
    if target.is_file():
        return [load_scenario(target)]
    if not target.exists():
        raise ScenarioError(f"no scenarios at {target}")

    scenarios = [load_scenario(f) for f in sorted(target.glob("*.yaml"))]
    if not scenarios:
        raise ScenarioError(f"no .yaml scenarios in {target}")

    seen: set[str] = set()
    for scenario in scenarios:
        if scenario.id in seen:
            raise ScenarioError(f"duplicate scenario id '{scenario.id}' in {target}")
        seen.add(scenario.id)
    return scenarios
