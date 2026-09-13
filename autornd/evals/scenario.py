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
    "domains", "domains_include", "risk", "risk_at_least", "risk_at_most",
    "specialists_include", "specialists_exclude",
    "status", "converge_within", "max_calls", "criteria_addressed",
}

# Risk ordering, for `risk_at_least` and `risk_at_most`.
#
# Both bounds matter, and a floor alone is what let a regression through: every
# scenario kept passing `risk_at_least` while the whole distribution drifted
# upward, until `low` was never assigned at all and a noise measurement came
# back critical. Under-classifying is the dangerous direction and
# over-classifying is the expensive one — risk sets review team size — so risk
# scenarios should state both.
RISK_ORDER = ["low", "medium", "high", "critical"]


@dataclass
class Scenario:
    id: str
    request: str
    description: str = ""
    # Which shape this scenario is about. Triage quality is measurable in two
    # calls and a few seconds; asserting it against the full pipeline means a
    # ten-minute run to check something decided in the first two.
    workflow: str | None = None
    # Scenarios differ legitimately in how long they should take. A reasoning
    # model on the architecture tier took 79-115 seconds to decide it could not
    # plan an underspecified request — correct behaviour, slow by nature. One
    # global timeout either fails that scenario or lets a genuine hang run for
    # ten minutes, so each scenario states its own.
    timeout: float | None = None
    expect: dict[str, Any] = field(default_factory=dict)
    tags: list[str] = field(default_factory=list)
    # Why this scenario states a risk floor but no ceiling. Some boundaries have
    # two defensible readings — occupational noise exposure is both a health
    # limit and a regulated one — and writing `risk_at_most: critical` there
    # would assert nothing, since critical is the top of the scale. Omitting the
    # ceiling is the honest option, but only with the reason recorded, so the
    # waiver is data a test can check rather than a comment it cannot see.
    risk_ceiling_waived: str = ""

    # Expectations that can only be answered by a workflow containing the node
    # that produces them. Scoring `converge_within` against a shape with no
    # loop is not a failure, it is the wrong question.
    _NEEDS_NODE = {"converge_within": "build_loop", "criteria_addressed": "coverage"}

    def unmet_requirements(self, node_ids: set[str]) -> dict[str, str]:
        """Expectations this workflow cannot answer, as {expectation: node}."""
        return {
            key: node for key, node in self._NEEDS_NODE.items()
            if key in self.expect and node not in node_ids
        }

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

    for key in ("risk", "risk_at_least", "risk_at_most"):
        value = expect.get(key)
        if value is not None and value not in RISK_ORDER:
            raise ScenarioError(
                f"{source}: {key} is {value!r}; expected one of {RISK_ORDER}"
            )

    timeout = raw.get("timeout")
    if timeout is not None and (not isinstance(timeout, (int, float)) or timeout <= 0):
        raise ScenarioError(f"{source}: timeout must be a positive number of seconds")

    waiver = raw.get("risk_ceiling_waived")
    if waiver is not None and not (isinstance(waiver, str) and waiver.strip()):
        raise ScenarioError(
            f"{source}: risk_ceiling_waived must state why the ceiling is omitted"
        )
    if waiver and expect.get("risk_at_most"):
        raise ScenarioError(
            f"{source}: risk_ceiling_waived is set but risk_at_most is also stated"
        )

    for key in ("converge_within", "max_calls"):
        value = expect.get(key)
        if value is not None and (not isinstance(value, int) or value < 1):
            raise ScenarioError(f"{source}: {key} must be a positive integer")

    return Scenario(
        id=raw["id"],
        request=raw["request"],
        description=raw.get("description", ""),
        workflow=raw.get("workflow"),
        timeout=raw.get("timeout"),
        risk_ceiling_waived=(raw.get("risk_ceiling_waived") or "").strip(),
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
