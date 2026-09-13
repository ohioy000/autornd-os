"""The workflow graph: phases as data rather than a hardcoded sequence.

AutoRnD ran one fixed pipeline — triage, plan, feasibility, implement/validate,
review — written into Python. That made the shape untestable: you could not ask
whether a phase earned its place, reorder anything, or drop a step for a cheap
request, because the shape was the code.

A spec describes the same work as a graph of nodes. Three kinds:

    ai        one model call, routed to a tier, validated against a verdict
    check     a deterministic function over prior outputs — no model, no cost
    gate      a condition that either lets the run continue or ends it

`check` is the important one. A model asked whether numbers reconcile is slower,
costlier and less reliable than arithmetic. Any question with a right answer
belongs in a check, and the model is left to do the part that actually needs
judgement.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

import yaml

__all__ = ["Node", "NodeKind", "SpecError", "WorkflowSpec"]


class SpecError(ValueError):
    """A workflow file is malformed. Raised at load time, never mid-run."""


class NodeKind(str, Enum):
    AI = "ai"
    CHECK = "check"
    GATE = "gate"


# Who runs an `ai` node. A concrete role name also works.
FANOUT_ASSIGNED = "assigned"      # every specialist triage assigned, in parallel
FANOUT_REVIEWERS = "reviewers"    # the risk-scaled review team, in parallel
LEAD = "lead"                     # the domain lead for this request


@dataclass
class Node:
    id: str
    kind: NodeKind
    depends_on: list[str] = field(default_factory=list)

    # `when` gates whether the node runs at all; a false condition skips it.
    when: str | None = None

    # ── ai ──
    tier: str | None = None
    specialist: str | None = None
    prompt: str | None = None
    schema: str | None = None
    max_tokens: int | None = None

    # ── check ──
    check: str | None = None
    args: dict[str, Any] = field(default_factory=dict)

    # ── gate ──
    condition: str | None = None
    on_fail: str | None = None        # terminal status when the gate closes
    on_fail_reason: str | None = None

    # ── loop ──
    # A node with `body` repeats that sub-sequence until `until` holds or the
    # iteration budget runs out. The budget may name a setting.
    body: list[str] = field(default_factory=list)
    until: str | None = None
    max_iterations: int | str | None = None
    # When the iteration budget is spent, either hand off to another node or
    # end the run with a status. They are different things, so they are
    # different fields — naming a status where a node belongs is a common
    # enough slip that it is worth failing at load time.
    on_exhausted: str | None = None          # node id to run next
    on_exhausted_status: str | None = None   # terminal status to end with

    @property
    def is_loop(self) -> bool:
        return bool(self.body)


@dataclass
class WorkflowSpec:
    name: str
    nodes: list[Node]
    description: str = ""

    def __post_init__(self) -> None:
        self._by_id = {n.id: n for n in self.nodes}

    def get(self, node_id: str) -> Node:
        try:
            return self._by_id[node_id]
        except KeyError:
            raise SpecError(f"no node named '{node_id}'") from None

    @property
    def ids(self) -> list[str]:
        return [n.id for n in self.nodes]

    def handoff_reachable(self) -> set[str]:
        """Nodes reached only by a handoff, never scheduled on their own.

        A loop owns its body. A loop's `on_exhausted` target is reached only
        when that loop runs out of iterations — and so is everything hanging off
        it. Escalation is the example: it must not run because its dependencies
        happen to be satisfied, only because the build loop gave up.
        """
        owned = {bid for n in self.nodes for bid in n.body}
        owned |= {n.on_exhausted for n in self.nodes if n.on_exhausted}

        # anything whose every dependency sits inside the owned set is only
        # reachable through it
        changed = True
        while changed:
            changed = False
            for node in self.nodes:
                if node.id in owned or not node.depends_on:
                    continue
                if all(dep in owned for dep in node.depends_on):
                    owned.add(node.id)
                    changed = True
        return owned

    def execution_order(self) -> list[Node]:
        """Top-level nodes in dependency order.

        Loop bodies and handoff-only nodes are excluded — they are run by
        whichever node owns them, not by the scheduler.
        """
        owned = self.handoff_reachable()
        pending = [n for n in self.nodes if n.id not in owned]
        resolved: list[Node] = []
        done: set[str] = set()

        while pending:
            ready = [
                n for n in pending
                if all(d in done or d in owned for d in n.depends_on)
            ]
            if not ready:
                stuck = ", ".join(sorted(n.id for n in pending))
                raise SpecError(f"dependency cycle or missing dependency among: {stuck}")
            # stable: preserve file order within a dependency level
            for node in ready:
                resolved.append(node)
                done.add(node.id)
            pending = [n for n in pending if n.id not in done]

        return resolved


def _require(raw: dict[str, Any], key: str, node_id: str) -> Any:
    if not raw.get(key):
        raise SpecError(f"node '{node_id}' is a {raw.get('kind')} node and needs '{key}'")
    return raw[key]


def _parse_node(raw: dict[str, Any]) -> Node:
    node_id = raw.get("id")
    if not node_id:
        raise SpecError(f"every node needs an 'id' (offending entry: {raw!r})")

    try:
        kind = NodeKind(raw.get("kind", "ai"))
    except ValueError:
        raise SpecError(
            f"node '{node_id}' has unknown kind {raw.get('kind')!r}; "
            f"expected one of {[k.value for k in NodeKind]}"
        ) from None

    depends_on = raw.get("depends_on") or []
    if isinstance(depends_on, str):
        depends_on = [depends_on]

    body = raw.get("body") or []
    if isinstance(body, str):
        body = [body]

    node = Node(
        id=node_id,
        kind=kind,
        depends_on=list(depends_on),
        when=raw.get("when"),
        tier=raw.get("tier"),
        specialist=raw.get("specialist"),
        prompt=raw.get("prompt"),
        schema=raw.get("schema"),
        max_tokens=raw.get("max_tokens"),
        check=raw.get("check"),
        args=raw.get("args") or {},
        condition=raw.get("condition"),
        on_fail=raw.get("on_fail"),
        on_fail_reason=raw.get("on_fail_reason"),
        body=list(body),
        until=raw.get("until"),
        max_iterations=raw.get("max_iterations"),
        on_exhausted=raw.get("on_exhausted"),
        on_exhausted_status=raw.get("on_exhausted_status"),
    )

    if kind is NodeKind.AI and not node.is_loop:
        _require(raw, "prompt", node_id)
        _require(raw, "tier", node_id)
    if kind is NodeKind.CHECK:
        _require(raw, "check", node_id)
    if kind is NodeKind.GATE:
        _require(raw, "condition", node_id)
    if node.is_loop and not node.until:
        raise SpecError(f"loop node '{node_id}' needs an 'until' condition")

    return node


def parse(data: dict[str, Any]) -> WorkflowSpec:
    if not isinstance(data, dict):
        raise SpecError("a workflow file must be a mapping with 'name' and 'nodes'")
    name = data.get("name")
    if not name:
        raise SpecError("workflow needs a 'name'")
    raw_nodes = data.get("nodes")
    if not raw_nodes:
        raise SpecError(f"workflow '{name}' has no nodes")

    nodes = [_parse_node(n) for n in raw_nodes]

    seen: set[str] = set()
    for node in nodes:
        if node.id in seen:
            raise SpecError(f"duplicate node id '{node.id}'")
        seen.add(node.id)

    known = {n.id for n in nodes}
    for node in nodes:
        for dep in node.depends_on:
            if dep not in known:
                raise SpecError(f"node '{node.id}' depends on unknown node '{dep}'")
        for member in node.body:
            if member not in known:
                raise SpecError(f"loop '{node.id}' names unknown body node '{member}'")
        if node.on_exhausted and node.on_exhausted not in known:
            raise SpecError(
                f"loop '{node.id}' names unknown on_exhausted node "
                f"'{node.on_exhausted}'. If you meant a terminal status, use "
                f"on_exhausted_status instead."
            )
        if node.on_exhausted and node.on_exhausted_status:
            raise SpecError(
                f"loop '{node.id}' sets both on_exhausted and "
                f"on_exhausted_status; it can hand off or end, not both"
            )

    spec = WorkflowSpec(name=name, nodes=nodes, description=data.get("description", ""))
    spec.execution_order()  # surface cycles at load time, not mid-run
    return spec


def load(path: str | Path) -> WorkflowSpec:
    file = Path(path)
    if not file.exists():
        raise SpecError(f"no workflow file at {file}")
    try:
        data = yaml.safe_load(file.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise SpecError(f"{file} is not valid YAML: {exc}") from exc
    return parse(data)
