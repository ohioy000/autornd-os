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


Node ownership, which is easy to trip over
------------------------------------------
A loop **owns** the nodes it lists in `body`, and an owning relationship takes
those nodes off the top-level schedule — they run because the loop runs them,
never because their dependencies happened to be satisfied. The same holds for a
loop's `on_exhausted` target and, since gate routing, for a gate's `on_fail`
target when it names a node.

The consequence is not obvious and cost a real mistake: adding `review` to a
rework loop's body **deleted the first review from the pipeline**, and took the
gate that depended on it and the independent pass beyond that with it. The
failure mode is a silently shorter pipeline, not an error. A phase that must run
both in the main flow and inside a loop needs two nodes — same prompt, same
tier, two ids — because the scheduler distinguishes nodes, not phases.
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
#
# `builders` exists because the test engineer validates the work rather than
# producing it — a rule that used to live unexplained in the engine. Naming the
# rosters here puts it in the workflow file where it can be seen and changed.
FANOUT_ASSIGNED = "assigned"      # every specialist triage assigned, in parallel
FANOUT_BUILDERS = "builders"      # assigned, minus whoever validates
FANOUT_PEERS = "peers"            # builders other than the lead
FANOUT_REVIEWERS = "reviewers"    # the risk-scaled review team, in parallel
LEAD = "lead"                     # the domain lead among the builders


# The statuses a gate may end a run with. Anything else in on_fail must name a
# node to route to, and anything that is neither fails at load.
TERMINAL_STATUSES = frozenset({"completed", "blocked", "escalated"})


@dataclass
class Node:
    id: str
    kind: NodeKind
    depends_on: list[str] = field(default_factory=list)

    # `when` gates whether the node runs at all; a false condition skips it.
    when: str | None = None

    # ── ai ──
    tier: str | None = None
    # Conditional routing: {condition: tier}, first match wins, falling back to
    # `tier`. Phase alone is a crude proxy for how much model a call needs — a
    # restyle and a battery controller both "plan", and only one of them needs
    # a reasoning model to do it.
    tier_when: dict[str, str] = field(default_factory=dict)
    specialist: str | None = None
    prompt: str | None = None
    schema: str | None = None
    max_tokens: int | None = None

    # ── check ──
    check: str | None = None
    args: dict[str, Any] = field(default_factory=dict)

    # ── gate ──
    condition: str | None = None
    # Where a closed gate goes: a terminal status, or the id of a node to
    # continue at. Routing is what lets review's findings have a consumer —
    # before it, a blocked review was the end of the run and the findings had
    # nowhere to go.
    on_fail: str | None = None
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
        # A gate that routes owns its target the same way a loop owns its
        # on_exhausted node: the rework loop must run because review blocked,
        # never because its dependencies happened to be satisfied.
        owned |= {n.on_fail for n in self.nodes
                  if n.on_fail and n.on_fail not in TERMINAL_STATUSES}

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

    def handoff_subgraph(self, start_id: str) -> list[Node]:
        """One handoff sub-graph, topologically ordered and complete.

        The set is the named node, everything that depends on it (transitively,
        within the handoff-owned set), and every handoff-owned node the set
        depends on — support nodes included, however few dependencies they
        declare. Dependencies outside the set are treated as satisfied: they
        belong to the main flow or to a loop body, which provides them when it
        runs. Loop bodies are excluded beyond the start node — a loop runs its
        own body, and running a body member here as well would execute it
        twice.

        Provenance (Blueprint 016 A1/A4): this replaces a single linear pass
        over the node list in file order, which dropped a handoff node whose
        dependencies were declared later, could execute a handoff node before
        the node it depends on, and dropped every handoff-owned node with no
        declared dependencies. Found by external assessment, verified by the
        advisor at 27cf116; latent in every shipped workflow because they
        declare each sub-graph in dependency order.
        tests/test_handoff_scheduler.py fails against the old code by
        construction. The same method is the load-time check in parse() — one
        definition of a sub-graph, run by the scheduler and checked by the
        loader.
        """
        if start_id not in self._by_id:
            raise SpecError(f"no node named '{start_id}'")
        reachable = self.handoff_reachable()
        body_members = {bid for n in self.nodes for bid in n.body}

        wanted = {start_id}
        changed = True
        while changed:
            changed = False
            for node in self.nodes:
                nid = node.id
                if nid in wanted or nid not in reachable or nid in body_members:
                    continue
                # downstream: every dependency is already in the set
                if node.depends_on and all(d in wanted for d in node.depends_on):
                    wanted.add(nid)
                    changed = True
                    continue
                # upstream support: some member of the set depends on this node
                if any(nid in self._by_id[m].depends_on for m in wanted):
                    wanted.add(nid)
                    changed = True

        ordered: list[Node] = []
        done: set[str] = set()
        pending = [self._by_id[nid] for nid in self.ids if nid in wanted]
        while pending:
            ready = [n for n in pending
                     if all(d in done or d not in wanted for d in n.depends_on)]
            if not ready:
                stuck = ", ".join(sorted(n.id for n in pending))
                raise SpecError(
                    f"handoff sub-graph from '{start_id}' is not orderable — "
                    f"dependency cycle among: {stuck}. A workflow that would "
                    f"silently lose a node must fail at load, not mid-run."
                )
            for node in ready:
                ordered.append(node)
                done.add(node.id)
            pending = [n for n in pending if n.id not in done]
        return ordered

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
        tier_when=raw.get("tier_when") or {},
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
        # A gate's on_fail is either a terminal status or a declared node. A
        # typo must not become a silent terminal state — the same reasoning as
        # a missing condition path raising rather than evaluating false.
        if node.on_fail and node.on_fail not in TERMINAL_STATUSES:
            if node.on_fail not in known:
                raise SpecError(
                    f"gate '{node.id}' has on_fail '{node.on_fail}', which is "
                    f"neither a terminal status ({', '.join(sorted(TERMINAL_STATUSES))}) "
                    f"nor a declared node id"
                )
        # Every loop must declare a bound. Review and implement can disagree
        # indefinitely; the graph must not be able to.
        if node.body and not node.max_iterations:
            raise SpecError(
                f"loop '{node.id}' declares no max_iterations — every loop is "
                f"bounded, so that no disagreement between phases can run forever"
            )
        if node.on_exhausted and node.on_exhausted_status:
            raise SpecError(
                f"loop '{node.id}' sets both on_exhausted and "
                f"on_exhausted_status; it can hand off or end, not both"
            )

    spec = WorkflowSpec(name=name, nodes=nodes, description=data.get("description", ""))
    spec.execution_order()  # surface cycles at load time, not mid-run
    # And the same guarantee for every routing target: the sub-graph a closed
    # gate or an exhausted loop hands off to must be orderable. Before this a
    # cycle there surfaced mid-run, after the run had already paid for
    # everything that came before it — the conditions module's founding
    # principle, applied to its own scheduler (Blueprint 016 A2).
    for node in nodes:
        for target in (node.on_exhausted, node.on_fail):
            if target and target not in TERMINAL_STATUSES:
                spec.handoff_subgraph(target)
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
