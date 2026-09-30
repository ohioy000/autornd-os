"""Runs a workflow graph.

The executor owns sequencing and nothing else. It decides what runs, in what
order, whether a gate closes and when a loop gives up — all of which is
decidable without a model, and therefore testable without one.

What a node *does* is delegated to a NodeRunner. In production that adapter
calls the existing phase functions; in tests it records what it was asked for.
Keeping the two apart is what makes "does this graph behave like the old
hardcoded pipeline" a question you can answer for free.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Protocol

from autornd.graph.conditions import ConditionError, evaluate, resolve_path
from autornd.graph.spec import TERMINAL_STATUSES, Node, NodeKind, WorkflowSpec

logger = logging.getLogger(__name__)

__all__ = ["ExecutionState", "GraphExecutor", "NodeRunner", "StepRecord",
           "_advisory_review_suffix", "_assessment_suffix", "_criteria_suffix"]


@dataclass
class StepRecord:
    """One node execution. The trace is the audit log of a run."""

    node_id: str
    kind: str
    iteration: int = 0
    skipped: bool = False
    reason: str = ""
    # Wall clock for this node, in seconds. A run that expires needs to say
    # where the time went without being bought a second time: the settling run
    # for B7 costs about half a dollar, and "it timed out" is a reading, not a
    # diagnosis. Zero for a skipped node, which costs nothing.
    seconds: float = 0.0


@dataclass
class ExecutionState:
    request: str
    outputs: dict[str, Any] = field(default_factory=dict)
    trace: list[StepRecord] = field(default_factory=list)
    status: str | None = None      # set once, ends the run
    reason: str | None = None
    iteration: int = 0             # current loop iteration, 0 outside a loop
    # Ruling D23: the runner's stop-reason is not the workflow's terminal.
    # A bound that stops the run from outside (wall-clock deadline, call or
    # spend ceiling) records how the runner stopped it here; the workflow's
    # own terminal stays in status/reason. A reader can therefore tell a
    # workflow that concluded blocked from a runner that killed a workflow
    # that never concluded. Set alongside status by _end_on_bound, never by
    # the workflow itself.
    stop_reason: str | None = None

    @property
    def finished(self) -> bool:
        return self.status is not None

    @property
    def path(self) -> list[str]:
        """Node ids actually executed, in order — skips excluded."""
        return [s.node_id for s in self.trace if not s.skipped]

    def end(self, status: str, reason: str | None = None) -> None:
        if self.status is None:
            self.status = status
            self.reason = reason


class NodeRunner(Protocol):
    """How a node's work actually happens. Injected, so the executor stays pure."""

    async def run_ai(self, node: Node, state: ExecutionState) -> dict[str, Any]:
        ...

    async def run_check(self, node: Node, state: ExecutionState) -> Any:
        ...


def _dissent_suffix(body: "list[Node]", state: "ExecutionState") -> str:
    """", still red: coverage, validate" — who was dissenting when time ran out.

    B18's second half. A loop that exhausts its bound already named the bound;
    it did not name WHY it kept going, and the answer is sitting in the fold's
    own output. `judges_agree` records `dissenting` on every failing fold, so
    the last iteration's dissent is the closest thing the run has to a cause.

    Read from the body's outputs rather than from a named node, because the
    fold's id is a property of the workflow file and this executor does not
    know it — a loop folds exactly the judges its own body produces.
    """
    for member in reversed(body):
        output = (state.outputs or {}).get(getattr(member, "id", ""))
        dissenting = None
        if isinstance(output, dict):
            dissenting = output.get("dissenting")
        else:
            dissenting = getattr(output, "dissenting", None)
        if dissenting:
            return ", still red: " + ", ".join(str(d) for d in dissenting)
    return ""


# Bound for the terminal's measured list: a run may carry many unmet
# criteria, so the terminal names the first few and counts the rest rather
# than growing without limit. Three because two is the common case in the
# harness and three still reads in one glance — a longer list belongs in
# coverage.detail, which the terminal does not replace.
CRITERIA_SUFFIX_SHOWN = 3


def _criteria_suffix(state: "ExecutionState") -> str:
    """", unmet: 'criterion one'; 'criterion two'" — what stayed unsatisfied.

    The -052 remedy, parallel to `_dissent_suffix()`. The dissent names the
    judge category ("coverage"); this names the criteria sitting in
    `coverage.missed`, which is MEASURED — the presence test's own output —
    not anyone's assessment. Read from the whole state's outputs rather than
    the loop body's, because the coverage node's id is a property of the
    workflow file and the loop body may not contain it.
    """
    coverage = (state.outputs or {}).get("coverage")
    missed = None
    if isinstance(coverage, dict):
        missed = coverage.get("missed")
    else:
        missed = getattr(coverage, "missed", None)
    if not missed:
        return ""
    names = [str(m) for m in missed]
    shown = names[:CRITERIA_SUFFIX_SHOWN]
    quoted = "; ".join(f"'{s}'" for s in shown)
    rest = len(names) - len(shown)
    tail = f", and {rest} more" if rest else ""
    return f", unmet: {quoted}{tail}"


# Placeholder strings an escalation model emits instead of a diagnosis.
# Compared case-insensitively after stripping; anything else is treated as
# a real assessment and quoted as one, labelled.
ASSESSMENT_PLACEHOLDERS = frozenset({"", "n/a", "none", "tbd", "unknown"})


def _advisory_review_suffix(state: "ExecutionState") -> str:
    """", advisory review: shipped" (or "did not ship: <findings>").

    Ruling D22: lean's review node is advisory — no gate reads review.ship,
    so a completed lean run carries no quality verdict while reading as
    though it does. The terminal states the review outcome and labels it
    advisory. MEASURED part (ship true/false, the harness's own record) is
    stated first; the MODEL part (the reviewer's findings, where the run
    dissents) follows labelled, per the -053 pattern. Empty when no review
    output is recorded, so workflows without a review node — and runs that
    never reached one — read no new text.

    The label carries no leading comma: the caller joins it to the reason.
    """
    review = (state.outputs or {}).get("review")
    ship = None
    findings = ""
    if isinstance(review, dict):
        ship = review.get("ship")
        findings = str(review.get("findings") or review.get("detail") or "").strip()
    else:
        ship = getattr(review, "ship", None)
        findings = str(getattr(review, "findings",
                               getattr(review, "detail", "")) or "").strip()
    if ship is None:
        return ""
    if ship is True or ship == "true":
        return "advisory review: shipped"
    tail = f": {findings}" if findings else ""
    return f"advisory review: did not ship (advisory){tail}"


def _assessment_suffix(state: "ExecutionState") -> str:
    """' — assessment: <diagnosis>' — what the escalation model concluded.

    Labelled as a MODEL'S CLAIM, never merged with the measured part:
    convention 26 says a reading mistakable for a stronger claim is a defect
    in the instrument, and an unlabelled diagnosis in the terminal would read
    as the harness's own finding. Empty or placeholder output is omitted
    rather than printed as an empty label.
    """
    escalation = (state.outputs or {}).get("escalation")
    diagnosis = None
    if isinstance(escalation, dict):
        diagnosis = escalation.get("root_cause_analysis")
    else:
        diagnosis = getattr(escalation, "root_cause_analysis", None)
    if not diagnosis or not str(diagnosis).strip():
        return ""
    text = str(diagnosis).strip()
    if text.lower() in ASSESSMENT_PLACEHOLDERS:
        return ""
    return f" — assessment: {text}"


def _render_item(value: object) -> str:
    """One entry of a gate's reason list, readable whatever shape it arrived in.

    A ReviewFinding is an object with a lens, a severity and a detail; `str()`
    on it produces a repr nobody wants to read in a status message.
    """
    def field(key: str) -> str:
        raw = (value.get(key) if isinstance(value, dict)
               else getattr(value, key, None))
        return str(raw) if raw else ""

    detail = field("detail")
    if not detail:
        return str(value)
    # Verdicts arrive as models from a live run and as plain dicts from
    # persisted or scripted state; both carry the same fields and both should
    # read the same way.
    label = "/".join(p for p in (field("severity"), field("lens"))
                     if p and p != "unknown")
    return f"[{label}] {detail}" if label else detail


class GraphExecutor:
    def __init__(
        self,
        spec: WorkflowSpec,
        runner: NodeRunner,
        settings_lookup: dict[str, Any] | None = None,
    ) -> None:
        self.spec = spec
        self.runner = runner
        # Conditional routing is evaluated here, where conditions live.
        if getattr(runner, "executor", None) is None:
            try:
                runner.executor = self
            except AttributeError:
                pass
        # Loop budgets may name a setting rather than hardcode a number, so the
        # same workflow file works across deployments with different limits.
        self.settings = settings_lookup or {}

    # ── conditions ────────────────────────────────────────────────────────

    def _scope(self, state: ExecutionState) -> dict[str, Any]:
        return {**state.outputs, "request": state.request, "iteration": state.iteration}

    def _test(self, condition: str, state: ExecutionState, node_id: str) -> bool:
        try:
            return evaluate(condition, self._scope(state))
        except ConditionError as exc:
            raise ConditionError(f"node '{node_id}': {exc}") from exc

    def _budget(self, node: Node) -> int:
        raw = node.max_iterations
        if raw is None:
            return 1
        if isinstance(raw, int):
            return raw
        if raw in self.settings:
            return int(self.settings[raw])
        raise ConditionError(
            f"loop '{node.id}' wants max_iterations from setting '{raw}', "
            f"which is not available; known: {sorted(self.settings)}"
        )

    # ── node kinds ────────────────────────────────────────────────────────

    def resolve_tier(self, node: Node, state: ExecutionState) -> str | None:
        """Which tier this node routes to on this run."""
        for condition, tier in node.tier_when.items():
            if self._test(condition, state, node.id):
                logger.debug("node %s routed to %s (%s)", node.id, tier, condition)
                return tier
        return node.tier

    async def _run_ai(self, node: Node, state: ExecutionState) -> None:
        output = await self.runner.run_ai(node, state)
        state.outputs[node.id] = output

    async def _run_check(self, node: Node, state: ExecutionState) -> None:
        result = await self.runner.run_check(node, state)
        # A check exposes its data to later conditions, plus `passed` so a gate
        # can branch on it directly.
        payload = dict(getattr(result, "data", {}) or {})
        payload["passed"] = bool(getattr(result, "passed", False))
        payload["detail"] = getattr(result, "detail", "")
        # Ruling D9: after judges_agree, detect abstention from source outputs
        # so silence is never recorded as assent. The fold's DECISION is
        # unchanged (abstention does not fail the fold); only the RECORD gains
        # a third state.
        if node.check == "judges_agree" and payload.get("passed"):
            abstained_judges: dict[str, int] = {}
            for arg_name, arg_path in (node.args or {}).items():
                if not isinstance(arg_path, str):
                    continue
                source_id = arg_path.split(".")[0]
                source = state.outputs.get(source_id)
                if isinstance(source, dict) and source.get("abstained"):
                    abstained_judges[arg_name] = len(source["abstained"])
            if abstained_judges:
                payload["abstained_judges"] = abstained_judges
                payload["abstention_count"] = sum(abstained_judges.values())
                n = len(node.args or {})
                names = ", ".join(
                    f"{k} ({v})" for k, v in sorted(abstained_judges.items()))
                payload["detail"] = (
                    f"{n} judges agree, but {names} abstained — "
                    f"empty seat, not unanimous")
        state.outputs[node.id] = payload

    def _decide_gate(self, node: Node,
                     state: ExecutionState) -> tuple[bool, str | None]:
        """Settle a gate. Returns (run continues, node to route to).

        The routing itself is the caller's job, so that the sub-graph a closed
        gate hands off to is not billed to the gate's clock.
        """
        passed = self._test(node.condition or "", state, node.id)
        state.outputs[node.id] = {"passed": passed}
        if passed:
            return True, None
        if not node.on_fail:
            return False, None

        reason = node.on_fail_reason or f"gate '{node.id}' closed"
        detail = self._gate_detail(node, state)

        # A closed gate may route instead of ending. Before this, a blocking
        # review was the end of the run and its findings had nowhere to go —
        # three traces in four terminated there with the work unfixed and the
        # diagnosis unread (§15.1). Routing reuses the loop handoff path, so a
        # gate and an exhausted loop reach a recovery sub-graph the same way.
        if node.on_fail not in TERMINAL_STATUSES:
            logger.info("gate %s closed — routing to %s (%s)",
                        node.id, node.on_fail, reason)
            state.outputs[node.id] = {"passed": passed, "routed_to": node.on_fail,
                                      "reason": f"{reason}{detail}"}
            return False, node.on_fail

        state.end(node.on_fail, f"{reason}{detail}")
        return False, None

    def _gate_detail(self, node: Node, state: ExecutionState) -> str:
        """Pull a reason out of the thing the gate was testing, when there is one.

        A blocked run should say why in the terms the user cares about — the
        blockers the architect listed, not just that a condition was false.
        """
        root = (node.condition or "").split(".")[0].replace("not ", "").strip()
        source = state.outputs.get(root)
        if source is None:
            return ""

        # Verdicts are Pydantic models, not dicts. Checking only for dicts meant
        # a gate on a verdict said nothing at all — "Review found blocking
        # issues" with the actual findings sitting unread in the object.
        def field(key: str):
            if isinstance(source, dict):
                return source.get(key)
            return getattr(source, key, None)

        for key in ("blockers", "findings", "critical_issues", "detail",
                    "root_cause_analysis", "red_cause"):
            value = field(key)
            if not value:
                continue
            if isinstance(value, list):
                return f": {'; '.join(_render_item(v) for v in value)}"
            return f": {value}"
        return ""

    # ── sequencing ────────────────────────────────────────────────────────

    async def _execute(self, node: Node, state: ExecutionState) -> bool:
        """Run one node. Returns whether the run continues."""
        if state.finished:
            return False

        if node.when:
            if not self._test(node.when, state, node.id):
                state.trace.append(StepRecord(
                    node.id, node.kind.value, state.iteration,
                    skipped=True, reason=f"when: {node.when}",
                ))
                return True

        if node.is_loop:
            return await self._run_loop(node, state)

        record = StepRecord(node.id, node.kind.value, state.iteration)
        state.trace.append(record)
        started = time.perf_counter()
        route_to: str | None = None
        try:
            if node.kind is NodeKind.AI:
                await self._run_ai(node, state)
                return True
            if node.kind is NodeKind.CHECK:
                await self._run_check(node, state)
                return True
            proceed, route_to = self._decide_gate(node, state)
            if route_to is None:
                return proceed
        finally:
            # In a finally so a node that raises still reports what it cost —
            # the expensive failures are the ones worth timing.
            record.seconds = round(time.perf_counter() - started, 3)

        # Deliberately outside the timer. A gate's own work is one condition
        # test; the sub-graph it routes to is timed by its own nodes, and
        # wrapping the delegation in the gate's clock counted every one of them
        # twice. Measured: `review_clean` read 1,573 seconds of an 1,800-second
        # run, and the per-phase table summed to 3,374 — the table B3 named as
        # B7's deliverable, unusable in the run that needed it.
        return await self._run_from(route_to, state)

    async def _run_loop(self, node: Node, state: ExecutionState) -> bool:
        budget = self._budget(node)
        body = [self.spec.get(b) for b in node.body]

        for attempt in range(1, budget + 1):
            state.iteration = attempt
            logger.debug("loop %s: iteration %d of %d", node.id, attempt, budget)
            for member in body:
                if not await self._execute(member, state):
                    state.iteration = 0
                    return False
            if self._test(node.until or "", state, node.id):
                state.iteration = 0
                state.outputs[node.id] = {"converged": True, "iterations": attempt}
                return True

        state.iteration = 0
        state.outputs[node.id] = {"converged": False, "iterations": budget}
        logger.info("loop %s exhausted %d iterations", node.id, budget)

        if node.on_exhausted_status:
            state.end(node.on_exhausted_status,
                      f"'{node.id}' did not converge within {budget} iterations"
                      + _dissent_suffix(body, state)
                      + _criteria_suffix(state)
                      + _assessment_suffix(state))
            return False
        if node.on_exhausted:
            return await self._run_from(node.on_exhausted, state)
        return True

    async def _run_from(self, start_id: str, state: ExecutionState) -> bool:
        """Run a handoff sub-graph: the named node and whatever hangs off it.

        Provenance (Blueprint 016 A4): the pass this replaces walked the node
        list once, in file order, admitting a node only if its dependencies
        had already been admitted by that same pass. Three ways to lose a
        node, all silent: a handoff node declared before its dependency was
        never revisited; a handoff node could execute before the node it
        depends on; and a handoff-owned node with no declared dependencies
        was dropped unconditionally. Found by external assessment, verified
        by the advisor at 27cf116 — the one structural defect fifteen
        blueprints of instrumentation walked past, sitting under the
        gate-routing feature that is about to carry more traffic. Latent in
        every shipped workflow, because each declares its handoff sub-graphs
        in dependency order; tests/test_handoff_scheduler.py fails against
        the old code by construction.

        The ordering itself is the spec's (WorkflowSpec.handoff_subgraph),
        shared with the load-time validation in spec.parse — one definition
        of a sub-graph, run by the scheduler and checked by the loader.
        """
        for node in self.spec.handoff_subgraph(start_id):
            if not await self._execute(node, state):
                return False
        return True

    async def run(self, request: str) -> ExecutionState:
        state = ExecutionState(request=request)
        # Kept on the executor so a caller can recover what completed when this
        # raises. A transport error three nodes in used to discard every verdict
        # already paid for, which is the failure the results log exists to stop
        # — and the runs worth diagnosing are exactly the ones that broke.
        self.state = state
        for node in self.spec.execution_order():
            if not await self._execute(node, state):
                break
        if not state.finished:
            state.end("completed", _advisory_review_suffix(state) or None)
        return state


def resolve_args(node: Node, state: ExecutionState) -> dict[str, Any]:
    """Turn a check node's declared args into real values.

    String arguments are dotted paths into node outputs; anything else is a
    literal. A path that does not resolve raises rather than silently becoming
    the string itself — a typo in a workflow file should be loud.
    """
    scope = {**state.outputs, "request": state.request}
    resolved: dict[str, Any] = {}
    for key, value in node.args.items():
        if isinstance(value, str):
            if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
                resolved[key] = value[1:-1]
            else:
                resolved[key] = resolve_path(value, scope)
        else:
            resolved[key] = value
    return resolved
