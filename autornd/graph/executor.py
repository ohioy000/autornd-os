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

import asyncio
import logging
import time
from dataclasses import asdict, dataclass, field
from typing import Any, Protocol

from autornd.graph.conditions import ConditionError, evaluate, resolve_path
from autornd.graph.spec import TERMINAL_STATUSES, Node, NodeKind, WorkflowSpec

logger = logging.getLogger(__name__)

__all__ = ["ExecutionState", "GraphExecutor", "NodeRunner", "StepRecord",
           "WatchdogRecord", "WATCHDOG_RESERVE_SECONDS",
           "_advisory_review_suffix", "_assessment_suffix", "_criteria_suffix"]


# Ruling D38: the time the watchdog leaves between cutting a call and the
# budget's end, for writing the terminal. Derived from a measurement, not a
# guess (convention 1).
#
# Measured 2026-09-30 on the real path (real GraphExecutor, real
# engineering-rnd.yaml, real PhaseRunner, a billing double whose judge call
# sleeps past the cut), in two passes of 30 cuts each:
#   cut point to the terminal written: max 0.0027 s, median 0.0012-0.0015 s
#   cut point to executor.run() returning: max 0.0031 s
# And through the real OpenRouterClient against a local socket that never
# answers (the part of a live cut the double cannot reach: httpx abandoning
# an in-flight request), in two passes of 20 cuts each:
#   timer expiry to the client's await raising: max 0.0039 s, median
#   0.0019-0.0027 s; the server saw the connection closed after 40 of 40.
# tests/test_watchdog.py::TestTheReserveIsMeasured re-measures the first on
# every suite run and fails if a cut ever takes a quarter of the reserve.
#
# Arithmetic: the largest reading is 0.0039 s; 0.0039 x 100 = 0.39 s, rounded
# up to 0.4 s. The 100x margin is a choice, made for what neither
# measurement sees: a TLS close to a remote provider on a loaded machine. It
# costs 0.4 s of the 600 s DEFAULT_TIMEOUT_SECONDS (0.07%) and of 094's
# 3,600 s deadline (0.011%).
WATCHDOG_RESERVE_SECONDS = 0.4

# Ruling D40: a call is flagged, never cancelled, when it runs past this
# multiple of its own node's slowest earlier call in this run. Measured by
# ARCH-20260930-098's three runs: same-node ratios reached 1.624 (engineering,
# n=4) and 1.118 (judge, n=3); the tier-keyed 5.733 and 3.030 compared
# implement with feasibility and review with validate, different work.
# Provisional at 3 to 4 observations per node; revisit at 10. Until D40 this
# was 1.0 against the tier's pace, so every first implement was flagged.
SLOW_CALL_MULTIPLE = 2.0

# The node whose output is the deliverable. The adapter reads it under this
# id throughout (state.outputs["implement"]); the watchdog's pointer compares
# the latest one with the one the build judges agreed on.
ARTIFACT_NODE = "implement"

# The ship-deciding judges an agreed implementation can meet after its build
# judges agreed: the main flow's review, and the rework_review inside each
# rework or recovery iteration (D38: "names which later gates it did or did
# not pass"). Both are workflow node ids. A workflow without them reports
# neither.
LATER_GATES = ("review", "rework_review")

# D38: "The watchdog stops the wait; whether the provider stops billing an
# abandoned call is unknown, and the record says so." Carried by every
# cancelled cut, verbatim.
ABANDONED_CALL_BILLING = (
    "unknown — the watchdog stopped the wait; whether the provider stops "
    "billing an abandoned call is not observable from the harness")


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
    # The tier a model-calling node routed to on this run, as resolve_tier
    # gave it; None for checks and gates. Measured need: 094's record could
    # only ESTIMATE the judges' pace (3,078 s over 14 calls, split evenly),
    # because per-phase totals cannot say which call took how long.
    tier: str | None = None
    # True when the D38 watchdog cut this node mid-flight. Its `seconds` are
    # then the time it ran before the cut, not a completed call's duration.
    cancelled: bool = False


@dataclass
class WatchdogRecord:
    """Ruling D38's typed record: how a budgeted run's clock was spent.

    Present on every run, so an absent block and a quiet watchdog cannot be
    confused (convention 28). `armed` says whether a budget was declared, and
    `fired` whether the watchdog ended the run. The cut fields are None until
    it fires. `slow_calls` is filled on any run, budgeted or not, because a
    flag changes nothing about what the run does.
    """

    armed: bool = False
    budget_seconds: float | None = None
    reserve_seconds: float | None = None
    fired: bool = False
    # "not_started": the pre-start rule; this run's pace for the tier said the
    # call could not finish inside budget less reserve, or no time was left.
    # "cancelled": the mid-flight rule; the call was running when the cut
    # point arrived.
    rule: str | None = None
    node: str | None = None
    iteration: int | None = None
    tier: str | None = None
    # The serving the call was configured to use. The serving that actually
    # answers is known only from a response, and a cut call has none, so it
    # is labelled configured and never observed.
    serving_configured: dict[str, Any] | None = None
    serving_observed: str | None = None
    # Seconds since the run started, when the rule decided.
    elapsed_seconds: float | None = None
    # What the rule compared against. For not_started, budget less elapsed
    # less reserve at the decision. For cancelled, the time the call was
    # granted at its start.
    available_seconds: float | None = None
    # The tier's pace when the rule decided: the longest completed
    # model-calling step of that tier in this run. None means no such step
    # had completed, so only the mid-flight rule guarded the call.
    pace_seconds: float | None = None
    # Ruling D40: 'node' when pace_seconds is this node's own slowest
    # completed call in this run, 'tier' when the node had none yet and the
    # tier's slowest completed call stood in. None with no pace.
    pace_basis: str | None = None
    # Seconds since the run started, when the terminal was written. A
    # watchdog end whose terminal lands after its budget falsifies D38.
    terminal_seconds: float | None = None
    billing: str | None = None
    # The last implementation the build judges agreed on. Computed when the
    # watchdog fires; None otherwise, because nothing was cut.
    approved: dict[str, Any] | None = None
    slow_calls: list[dict[str, Any]] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


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
    # Ruling D38: the watchdog's typed record. Set at the start of every run
    # by GraphExecutor.run, armed or not.
    watchdog: WatchdogRecord | None = None

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


def _summary(verdict: object) -> str | None:
    """An implementation's deliverable text, from a verdict or a plain dict."""
    if verdict is None:
        return None
    if isinstance(verdict, dict):
        return verdict.get("summary")
    return getattr(verdict, "summary", None)


def _watchdog_reason(record: "WatchdogRecord") -> str:
    """The watchdog's terminal in a plain sentence. The typed record is
    the source of truth; nothing reads this for control flow."""
    where = f"'{record.node}'"
    if record.iteration:
        where += f" (iteration {record.iteration})"
    tier = f"{record.tier} " if record.tier else ""
    budget = f"the {record.budget_seconds:g}s budget"
    if record.rule == "not_started":
        if record.pace_seconds is not None and record.available_seconds > 0:
            whose = ("this node's " if record.pace_basis == "node"
                     else f"this run's {tier}")
            what = (f"the {tier}call at {where} was not started: {whose}"
                    f"pace is {record.pace_seconds:.3f}s and only "
                    f"{record.available_seconds:.3f}s of {budget} remain "
                    f"before the {record.reserve_seconds:g}s reserve")
        else:
            what = (f"the {tier}call at {where} was not started: no time of "
                    f"{budget} remains before the {record.reserve_seconds:g}s "
                    f"reserve")
    else:
        what = (f"the {tier}call at {where} was cancelled at "
                f"{record.elapsed_seconds:.3f}s of {budget}, leaving the "
                f"{record.reserve_seconds:g}s reserve to write this terminal")
    approved = record.approved or {}
    if approved.get("agreed"):
        gates = ", ".join(f"{g}: {v.replace('_', ' ')}"
                          for g, v in (approved.get("gates") or {}).items())
        where_agreed = (f"{approved.get('loop')} iteration "
                        f"{approved.get('iteration')}"
                        + (f" ({gates})" if gates else ""))
        # A14 (ARCH-20261001-101): a build-approved implementation a later
        # gate refused says so in the same sentence, and 'judge-approved'
        # never stands unqualified for it (D22). 098 run 2 read "last
        # judge-approved implementation ... (review: failed ...)".
        if "failed" in (approved.get("gates") or {}).values():
            pointer = ("last implementation agreed by the build judges, "
                       "refused by the final review: not approved: "
                       + where_agreed)
        else:
            pointer = f"last judge-approved implementation: {where_agreed}"
        # A2 (ARCH-20260930-100): 'dissented' and 'unjudged' are both NOT
        # APPROVED, and the sentence says so, with the finer label beside it.
        # D38's "labelled unjudged" meant a not-approved artifact must never
        # read as approved.
        if approved.get("latest_differs"):
            pointer += (f"; the latest implementation differs and is not "
                        f"approved ({approved.get('latest')})")
    elif approved.get("agreed") is False:
        pointer = "no implementation was agreed by the build judges"
        if approved.get("latest"):
            pointer += (f"; the latest implementation is not approved "
                        f"({approved.get('latest')})")
    else:
        pointer = "this runner keeps no iteration history to point at"
    return f"stopped by the deliberation watchdog (Ruling D38): {what}; {pointer}"


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
        time_budget: float | None = None,
        reserve_seconds: float | None = None,
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
        # Ruling D38: a run with a declared time budget ends by its own
        # terminal. None means no budget, and then nothing below is consulted:
        # the run behaves exactly as it did before the watchdog existed.
        self.time_budget = time_budget
        # Read from the module at construction, not frozen into a default
        # argument, so a test can set the constant the runner path uses.
        self.reserve_seconds = (WATCHDOG_RESERVE_SECONDS if reserve_seconds is None
                                else reserve_seconds)
        self._started = 0.0
        self._pace: dict[str | None, float] = {}
        # Ruling D40: the slowest completed call per (node, tier).
        self._node_pace: dict[tuple[str, str | None], float] = {}
        self._history_base = 0
        self._history_tags: list[dict[str, Any]] = []
        self._loops: list[str] = []
        self._ships: dict[int, bool] = {}

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

    # ── the deliberation watchdog (Ruling D38) ────────────────────────────

    def _elapsed(self) -> float:
        return time.perf_counter() - self._started

    def _available(self) -> float:
        """Budget less elapsed less reserve: how long a call may still run."""
        return float(self.time_budget) - self._elapsed() - self.reserve_seconds

    def _step_tier(self, node: Node, state: ExecutionState) -> str | None:
        """The tier for the record, without changing what the run does.

        resolve_tier is the adapter's own answer. A condition that cannot be
        evaluated yet would raise here, where nothing raised before the
        watchdog existed; the record says None instead, and the adapter
        still raises on the real path exactly as it always did.
        """
        try:
            return self.resolve_tier(node, state)
        except ConditionError:
            return None

    def _calls(self) -> int | None:
        """The client's call counter, when the runner exposes one."""
        calls = getattr(getattr(self.runner, "client", None), "calls", None)
        return calls if isinstance(calls, int) else None

    def _configured_serving(self, tier: str | None) -> dict[str, Any] | None:
        """Which model and pin a call on this tier is configured to use.

        The same two lookups OpenRouterClient.chat makes when it builds the
        request, so the record names what the request would have asked for.
        """
        client = getattr(self.runner, "client", None)
        if tier is None or client is None or not hasattr(client, "get_model"):
            return None
        from autornd.routing.openrouter import (
            provider_fallbacks_allowed, provider_order_for,
        )
        return {"model": client.get_model(tier),
                "provider_order": provider_order_for(tier),
                "allow_fallbacks": provider_fallbacks_allowed()}

    def _makes_call(self, node: Node, state: ExecutionState) -> bool:
        """Whether this AI node will make a model call, when the runner can
        say. A runner that cannot is assumed to call, which is the pre-start
        rule's behaviour before A1."""
        probe = getattr(self.runner, "makes_call", None)
        if probe is None:
            return True
        try:
            return bool(probe(node, state))
        except Exception:
            return True

    def _refuse_to_start(self, node: Node, state: ExecutionState,
                         tier: str | None) -> bool:
        """D38's pre-start rule. True when the call is not started.

        A call is not started when this run's own pace for its tier says it
        cannot finish inside the budget less the reserve. With no completed
        step of that tier yet, there is no pace, so the call starts and only
        the mid-flight rule guards it. When the cut point has already passed,
        no call can finish, and starting one only to cancel it at once would
        bill a request for nothing.
        """
        if self.time_budget is None:
            return False
        available = self._available()
        pace, basis = self._pace_for(node.id, tier)
        if available > 0 and (pace is None or pace <= available):
            return False
        self._cut(state, "not_started", node, tier,
                  available=available, pace=pace, basis=basis)
        return True

    def _pace_for(self, node_id: str, tier: str | None
                  ) -> tuple[float | None, str | None]:
        """Ruling D40: this node's slowest completed call in this tier and
        run; failing that, the tier's; and which of the two it is."""
        own = self._node_pace.get((node_id, tier))
        if own is not None:
            return own, "node"
        shared = self._pace.get(tier)
        if shared is not None:
            return shared, "tier"
        return None, None

    async def _watched(self, work, node: Node, state: ExecutionState,
                       record: StepRecord) -> bool:
        """Run one node's work. Under a budget, cut it at the reserve.

        False when the watchdog ended the run. With no budget this is a bare
        await: no timer is entered, so an unbudgeted run behaves as before.
        """
        if self.time_budget is None:
            await work(node, state)
            return True
        granted = self._available()
        try:
            async with asyncio.timeout(max(granted, 0.0)) as guard:
                await work(node, state)
        except TimeoutError:
            # Only the watchdog's own expiry is a cut. A TimeoutError raised
            # inside the phase is the phase's, and travels on unchanged.
            if not guard.expired():
                raise
            record.cancelled = True
            pace, basis = self._pace_for(node.id, record.tier)
            self._cut(state, "cancelled", node, record.tier,
                      available=granted, pace=pace, basis=basis)
            return False
        return True

    def _after_step(self, node: Node, record: StepRecord, completed: bool,
                    calls_before: int | None, state: ExecutionState,
                    trace_index: int) -> None:
        """Bookkeeping after a node: pace, slow-call flags, history tags.

        Read-only with respect to the run: nothing here changes a decision
        already taken. Only a completed node's output is read, because a node
        that raised or was cut leaves the PREVIOUS iteration's verdict under
        its id. Pace counts only steps that made a model call, when the
        counter can say so: a domain_review with no peers to ask takes 0 s
        and calls nothing, and a pace of 0 s from it would misstate the tier.
        """
        if completed and node.kind is NodeKind.AI:
            output = state.outputs.get(node.id)
            ship = (output.get("ship") if isinstance(output, dict)
                    else getattr(output, "ship", None))
            if isinstance(ship, bool):
                self._ships[trace_index] = ship

        history = getattr(self.runner, "iterations", None)
        if isinstance(history, list):
            loop = self._loops[-1] if self._loops else None
            while self._history_base + len(self._history_tags) < len(history):
                self._history_tags.append({"loop": loop, "trace_index": trace_index})

        if node.kind is not NodeKind.AI or not (completed or record.cancelled):
            return
        calls_after = self._calls()
        called = (calls_before is None or calls_after is None
                  or calls_after > calls_before)
        if not called and not record.cancelled:
            return
        key = (node.id, record.tier)
        # Ruling D40: a call is compared with its own node's earlier calls
        # only. A node's first call has none and flags nothing. A pace of
        # 0 s (inside the record's millisecond rounding) has no ratio.
        own = self._node_pace.get(key)
        if own and record.seconds > own * SLOW_CALL_MULTIPLE:
            watchdog = state.watchdog
            if watchdog is not None:
                watchdog.slow_calls.append({
                    "node": node.id, "iteration": record.iteration,
                    "tier": record.tier, "seconds": record.seconds,
                    "pace_seconds": own, "pace_basis": "node",
                    "ratio": round(record.seconds / own, 3),
                    "cancelled": record.cancelled,
                })
        if not record.cancelled:
            self._node_pace[key] = max(own or 0.0, record.seconds)
            self._pace[record.tier] = max(self._pace.get(record.tier) or 0.0,
                                          record.seconds)

    def _approved_pointer(self, state: ExecutionState) -> dict[str, Any]:
        """D38: the last implementation the build judges agreed on.

        'Agreed' is an iteration whose dissent list is empty, as the adapter's
        iteration history records it. A runner that keeps no history makes
        the pointer BLIND, not empty: `history` says which. No agreed
        iteration is stated as agreed: false, never left absent
        (convention 28).
        """
        history = getattr(self.runner, "iterations", None)
        latest = _summary(state.outputs.get(ARTIFACT_NODE))
        if not isinstance(history, list):
            return {"history": "absent", "agreed": None, "index": None,
                    "loop": None, "iteration": None, "gates": None,
                    "latest_differs": None, "latest": None}
        entries = history[self._history_base:]
        agreed_at = None
        for position in range(len(entries) - 1, -1, -1):
            if entries[position].get("dissenting") == []:
                agreed_at = position
                break

        # What the latest implementation is, judged against the record: the
        # one the judges agreed on, one they judged and dissented from, or
        # one no judge finished reading.
        latest_label = None
        if latest is not None:
            if agreed_at is not None and latest == entries[agreed_at].get("implement_summary"):
                latest_label = "approved"
            elif entries and latest == entries[-1].get("implement_summary"):
                latest_label = "dissented"
            else:
                latest_label = "unjudged"

        if agreed_at is None:
            # Nothing was agreed, so there is nothing for the latest to differ
            # from; its label still says whether a judge finished reading it.
            return {"history": "present", "agreed": False, "index": None,
                    "loop": None, "iteration": None, "gates": None,
                    "latest_differs": None, "latest": latest_label}

        entry = entries[agreed_at]
        tag = (self._history_tags[agreed_at]
               if agreed_at < len(self._history_tags) else {})
        return {
            "history": "present",
            "agreed": True,
            # Into the unit record's `iterations` list, which is this history.
            "index": self._history_base + agreed_at,
            "loop": tag.get("loop"),
            "iteration": entry.get("iteration"),
            "gates": self._later_gates(state, tag.get("trace_index")),
            "latest_differs": (None if latest is None
                               else latest != entry.get("implement_summary")),
            "latest": latest_label,
        }

    def _later_gates(self, state: ExecutionState,
                     after: int | None) -> dict[str, str]:
        """For each LATER_GATES node, what it said about the agreed work.

        The window runs from the step whose judging appended the agreed
        iteration up to the next implementation. A later implement produces
        a different artifact, and a gate after it judged that one, not this.
        Values: passed, failed, cut (the watchdog stopped it mid-call),
        not_reached.
        """
        gates = {g: "not_reached" for g in LATER_GATES if g in self.spec.ids}
        if after is None:
            return gates
        for index in range(after + 1, len(state.trace)):
            step = state.trace[index]
            if step.skipped:
                continue
            if step.node_id == ARTIFACT_NODE:
                break
            if step.node_id in gates and gates[step.node_id] == "not_reached":
                if step.cancelled:
                    gates[step.node_id] = "cut"
                elif index in self._ships:
                    gates[step.node_id] = "passed" if self._ships[index] else "failed"
        return gates

    def _cut(self, state: ExecutionState, rule: str, node: Node,
             tier: str | None, available: float, pace: float | None,
             basis: str | None = None) -> None:
        """End the run now: status blocked, typed record, everything kept."""
        watchdog = state.watchdog
        watchdog.fired = True
        watchdog.rule = rule
        watchdog.node = node.id
        watchdog.iteration = state.iteration
        watchdog.tier = tier
        watchdog.serving_configured = self._configured_serving(tier)
        watchdog.serving_observed = None
        watchdog.elapsed_seconds = round(self._elapsed(), 4)
        watchdog.available_seconds = round(available, 4)
        watchdog.pace_seconds = pace
        watchdog.pace_basis = basis
        watchdog.billing = ABANDONED_CALL_BILLING if rule == "cancelled" else None
        watchdog.approved = self._approved_pointer(state)
        state.end("blocked", _watchdog_reason(watchdog))
        watchdog.terminal_seconds = round(self._elapsed(), 4)
        logger.info("watchdog: %s at %s (%.3fs of %.3fs)", rule, node.id,
                    watchdog.elapsed_seconds, watchdog.budget_seconds)

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

        tier = self._step_tier(node, state) if node.kind is NodeKind.AI else None
        # Ruling D38, before the call: a call this run's own pace says cannot
        # finish is never started, so it is not in the trace. It did not run.
        # A1 (ARCH-20260930-100): only a node that will make a call is judged.
        # A node that makes none cannot overrun, and naming it misattributes
        # the cause: 098 run 1 named domain_review, which had no peers to ask.
        if (node.kind is NodeKind.AI and self._makes_call(node, state)
                and self._refuse_to_start(node, state, tier)):
            return False

        record = StepRecord(node.id, node.kind.value, state.iteration, tier=tier)
        state.trace.append(record)
        trace_index = len(state.trace) - 1
        calls_before = self._calls()
        started = time.perf_counter()
        route_to: str | None = None
        completed = False
        try:
            # Checks are watched as well as model calls. Three of them make
            # paid lookups (build_context, verify_grounding, the re-grounding
            # lookup); 094's context took 22.5 s. D38 says a budgeted run is
            # never killed from outside mid-call.
            if node.kind is NodeKind.AI:
                completed = await self._watched(self._run_ai, node, state, record)
                return completed
            if node.kind is NodeKind.CHECK:
                completed = await self._watched(self._run_check, node, state, record)
                return completed
            completed = True
            proceed, route_to = self._decide_gate(node, state)
            if route_to is None:
                return proceed
        finally:
            # In a finally so a node that raises still reports what it cost —
            # the expensive failures are the ones worth timing.
            record.seconds = round(time.perf_counter() - started, 3)
            self._after_step(node, record, completed, calls_before, state,
                             trace_index)

        # Deliberately outside the timer. A gate's own work is one condition
        # test; the sub-graph it routes to is timed by its own nodes, and
        # wrapping the delegation in the gate's clock counted every one of them
        # twice. Measured: `review_clean` read 1,573 seconds of an 1,800-second
        # run, and the per-phase table summed to 3,374 — the table B3 named as
        # B7's deliverable, unusable in the run that needed it.
        return await self._run_from(route_to, state)

    async def _run_loop(self, node: Node, state: ExecutionState) -> bool:
        # Which loop is running, so the watchdog's pointer can say which loop
        # an agreed iteration belonged to. A stack because a loop's
        # on_exhausted hands off to a sub-graph that holds loops of its own.
        self._loops.append(node.id)
        try:
            return await self._run_loop_body(node, state)
        finally:
            self._loops.pop()

    async def _run_loop_body(self, node: Node, state: ExecutionState) -> bool:
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
        # Ruling D38: the run's clock starts here, and so does its record.
        self._started = time.perf_counter()
        self._pace = {}
        self._node_pace = {}
        self._ships = {}
        self._history_tags = []
        self._loops = []
        history = getattr(self.runner, "iterations", None)
        self._history_base = len(history) if isinstance(history, list) else 0
        armed = self.time_budget is not None
        state.watchdog = WatchdogRecord(
            armed=armed,
            budget_seconds=float(self.time_budget) if armed else None,
            reserve_seconds=self.reserve_seconds if armed else None)
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
