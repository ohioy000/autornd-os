"""Wires graph nodes to the phases that do the work.

The executor knows sequencing; this knows AutoRnD. It resolves which specialist
runs a node, calls the existing phase function, records cost, and hands the
typed verdict back. Keeping it separate is what lets the executor be tested
without a model and this be tested without a scheduler.

Verdicts are stored as objects rather than dicts, so a condition like
`plan.ready == true` reads the real attribute and a typo fails loudly.
"""

from __future__ import annotations

import logging
from typing import Any, Callable

from autornd.config import settings
from autornd.engine import phases
from autornd.graph.checks import Result, get_check, registry
from autornd.graph.executor import ExecutionState, resolve_args
from autornd.graph.spec import (
    FANOUT_ASSIGNED,
    FANOUT_BUILDERS,
    FANOUT_PEERS,
    FANOUT_REVIEWERS,
    LEAD,
    Node,
)
from autornd.knowledge.context import (
    build_phase_context,
    criteria_demand_verification,
)
from autornd.models.verdicts import Domain, SpecialistRole
from autornd.routing.openrouter import ModelResponse, OpenRouterClient
from autornd.specialists.base import Specialist
from autornd.specialists.registry import get_specialists

logger = logging.getLogger(__name__)

__all__ = ["PhaseRunner", "UnknownPromptError"]


class UnknownPromptError(KeyError):
    """A node names a prompt with no phase behind it."""


class PhaseRunner:
    """Runs graph nodes against the real engine.

    `on_phase` is called with (node_id, verdict, responses, iteration) after
    each ai node, which is where persistence and cost accounting hang.
    """

    def __init__(
        self,
        client: OpenRouterClient,
        on_phase: Callable[..., Any] | None = None,
        executor: Any | None = None,
    ) -> None:
        self.client = client
        # Set by the executor so conditional tier routing can be evaluated.
        self.executor = executor
        self.on_phase = on_phase
        self.context: str = ""
        # Every failed attempt, for the escalation autopsy to read.
        self.failure_log: list[dict[str, Any]] = []
        self.resolution_directive: str | None = None
        # Every build-loop iteration, failed or not, for the results log to
        # keep. `failure_log` records only reds and is cleared at escalation,
        # and `state.outputs` is last-write-wins — so a three-iteration run left
        # exactly one implement verdict behind and the question "did the
        # implementation actually change between attempts?" was unanswerable
        # from a finished run. This is the history, retained.
        self.iterations: list[dict[str, Any]] = []
        self._spend_at_last_iteration = 0.0
        # Blocking gaps the risk gate declined to look up, kept so the
        # verifiability override can look them up if the plan demands it
        # (Blueprint 016 B1). A declined lookup is deferred, not discarded.
        self.deferred_gaps: list[str] = []
        self.verification_lookup_done = False

    @property
    def total_cost(self) -> float:
        """What this run has spent, read from the client rather than tallied here.

        It used to accumulate in `_record`, which only sees nodes that go
        through `run_ai` — so research lookups, context expansion and reranking
        never counted. Reading the client's own total means a call cannot be
        made without being priced.
        """
        return self.client.spend

    @property
    def total_calls(self) -> int:
        return self.client.calls

    # ── casts off the shared state ────────────────────────────────────────

    def _triage(self, state: ExecutionState):
        verdict = state.outputs.get("triage")
        if verdict is None:
            raise UnknownPromptError(
                "triage has not run; nodes that need domains or specialists "
                "must depend on it"
            )
        return verdict

    def _specialists(self, state: ExecutionState) -> list[Specialist]:
        return get_specialists(self._triage(state).specialists)

    def _primary_domain(self, state: ExecutionState) -> Domain | None:
        domains = self._triage(state).domains
        return domains[0] if domains else None

    def _builders(self, state: ExecutionState) -> list[Specialist]:
        """Who produces the implementation.

        The test engineer validates the work, so it does not build it or review
        the build — that would be marking its own homework. If triage assigned
        nobody else, it builds after all rather than leaving the roster empty.
        """
        assigned = self._triage(state).specialists
        builders = [s for s in assigned if s != SpecialistRole.TEST_ENGINEER]
        return get_specialists(builders or assigned)

    def _resolve_who(self, node: Node, state: ExecutionState) -> list[Specialist]:
        """Which specialists run this node."""
        who = node.specialist

        if who in (None, FANOUT_ASSIGNED):
            return self._specialists(state)
        if who == FANOUT_BUILDERS:
            return self._builders(state)
        if who == LEAD:
            lead, _ = phases.select_lead(self._builders(state), self._primary_domain(state))
            return [lead]
        if who == FANOUT_PEERS:
            _, peers = phases.select_lead(self._builders(state), self._primary_domain(state))
            return peers
        if who == FANOUT_REVIEWERS:
            from autornd.engine.review_composition import get_review_team

            triage = self._triage(state)
            return get_specialists(get_review_team(
                triage.risk, triage.domains, triage.specialists))
        # A workflow may name any role, including one a profile declares —
        # SpecialistRole(who) raised for everything outside the shipped enum.
        return get_specialists([who])

    def _max_tokens(self, node: Node) -> int | None:
        """A node's output ceiling. An int is literal; a string names a setting."""
        raw = node.max_tokens
        if raw is None or isinstance(raw, int):
            return raw
        return getattr(settings, str(raw), None)

    def _record(
        self, node: Node, verdict: Any, responses: list[ModelResponse], state: ExecutionState
    ) -> None:
        # Cost is accounted by the client as each request is made; nothing to
        # tally here.
        if self.on_phase:
            self.on_phase(node.id, verdict, responses, state.iteration)

    # ── node kinds ────────────────────────────────────────────────────────

    async def run_ai(self, node: Node, state: ExecutionState) -> Any:
        handler = getattr(self, f"_phase_{node.prompt}", None)
        if handler is None:
            raise UnknownPromptError(
                f"node '{node.id}' names prompt '{node.prompt}', which has no "
                f"phase behind it. Known: "
                f"{sorted(n[7:] for n in dir(self) if n.startswith('_phase_'))}"
            )
        verdict, responses = await handler(node, state)
        self._record(node, verdict, responses, state)
        return verdict

    async def run_check(self, node: Node, state: ExecutionState) -> Result:
        if node.check == "build_context":
            return await self._build_context(state)
        if node.check == "verify_grounding":
            return await self._verify_grounding(state)
        if node.check == "blocked_on_unmet":
            return self._blocked_on_unmet(node, state)
        if node.check not in registry:
            raise KeyError(
                f"node '{node.id}' names unknown check '{node.check}'; "
                f"registered: {sorted(registry)}"
            )
        return get_check(node.check)(**resolve_args(node, state))

    async def _build_context(self, state: ExecutionState) -> Result:
        """Assemble grounding once, for every phase that follows.

        Grounding is the cheapest quality lever there is — deterministic docs
        cost nothing — so it gets its own node rather than being a side effect
        of whichever phase happened to need it first.
        """
        triage = self._triage(state)
        # Risk reaches the grounding decision. It is settled by triage before
        # this runs, and it was not being passed — so a low-risk copy change
        # bought the same paid lookups as a reactor monitoring spec.
        deferred: list[str] = []
        self.context = await build_phase_context(
            state.request, triage.domains, triage.specialists,
            client=self.client, risk=triage.risk,
            deferred_gaps=deferred,
        )
        self.deferred_gaps = deferred
        return Result(
            True,
            f"{len(self.context)} characters of context assembled",
            chars=len(self.context),
            grounded=bool(self.context),
        )

    async def _verify_grounding(self, state: ExecutionState) -> Result:
        """One bundled lookup when the plan's criteria demand a citation.

        B13's override (Blueprint 016 B1). The risk gate zeroes lookups at low
        risk, and the measured failure is what happened next: the plan wrote a
        criterion demanding a citable source, and the implementer — denied any
        means of verifying anything — fabricated sources for six iterations
        rather than refusing. The demand is detected for free, deterministically,
        over the criteria text; the lookup itself is the standard bundled one at
        the medium-risk budget, under MAX_LOOKUPS=1, whatever the triage risk.
        REJECTED alternatives, recorded per the blueprint: a blanket low-risk
        lookup budget (spends where nobody asked) and forbidding verifiability
        criteria at low risk (hides the need; the claims get written either
        way — §6.3's exact danger).

        Runs once, after the plan exists — the criteria that trigger it do not
        exist when the context phase assembles grounding, which is why this is
        its own node rather than a branch of build_context.
        """
        plan = state.outputs.get("plan")
        criteria = list(getattr(plan, "success_criteria", None) or [])
        demanded = criteria_demand_verification(criteria)
        looked_up = 0
        if demanded and self.deferred_gaps and not self.verification_lookup_done:
            from autornd.knowledge.research import render_findings, research_gaps

            findings = await research_gaps(
                self.client, state.request, list(self.deferred_gaps),
                max_tokens=settings.search_max_tokens,
            )
            looked_up = len(findings)
            if findings:
                self.context = (self.context + "\n\n"
                                + render_findings(findings)).strip()
        self.verification_lookup_done = True
        if not demanded:
            return Result(True, "no citation demand detected — no lookup",
                          demanded=False, looked_up=0)
        # The detail names all three facts separately, because two of them used
        # to collapse. "criteria demand verifiability" was written on every path,
        # including the one where there was nothing to look up and nothing was
        # looked up — which reads at a glance as though something had been
        # verified. It misled the executor's own reading of its own traces
        # (ARCH-20260920-004): four zero-lookup runs were reported as an override
        # that fired and found nothing, when the override had correctly declined
        # to spend. Detection, gaps and lookup are now three separate clauses,
        # and "verif-" never appears on a path that looked nothing up.
        gaps = len(self.deferred_gaps)
        if looked_up or gaps:
            spent = f"lookup performed: {looked_up} finding(s)"
        else:
            spent = "nothing to look up, no lookup performed"
        return Result(
            True,
            f"citation demand detected; {gaps} deferred gap(s) — {spent}",
            demanded=True, looked_up=looked_up,
            deferred_gaps=gaps,
        )

    def _blocked_on_unmet(self, node: Node, state: ExecutionState) -> Result:
        """The honest-refusal gate's check, plus its failure-log write.

        B3's invariant is that escalation's verdict carries blocked_on in the
        failure log it reads — but the block fires right after implement,
        BEFORE validate, and validate was the only phase that wrote failure-log
        entries. Routed cold, the autopsy would read a log with nothing in it
        about the block and would diagnose from silence. So the adapter writes
        the entry here, on the real path only; the check itself stays a pure
        registry function the executor and the tests drive directly.
        """
        result = get_check("blocked_on_unmet")(**resolve_args(node, state))
        if not result.passed:
            implement = state.outputs.get("implement")
            summary = getattr(implement, "summary", None)
            if summary is None and isinstance(implement, dict):
                summary = implement.get("summary", "")
            self.failure_log.append({
                "iteration": state.iteration,
                "implement_summary": str(summary or ""),
                "red_cause": (
                    "implementation blocked on a criterion it cannot satisfy"),
                "evidence": [f"blocked: {b}" for b in result.data["blocked"]],
                "blocked_on": list(result.data["blocked"]),
            })
        return result

    # ── phases ────────────────────────────────────────────────────────────

    async def _phase_triage(self, node: Node, state: ExecutionState):
        verdict, response = await phases.run_triage(self.client, state.request)
        return verdict, [response]

    def _tier(self, node: Node, state: ExecutionState) -> str | None:
        if self.executor is not None:
            return self.executor.resolve_tier(node, state)
        return node.tier

    async def _phase_plan(self, node: Node, state: ExecutionState):
        verdict, response = await phases.run_plan(
            self.client, state.request, self._triage(state), self._specialists(state),
            tier=self._tier(node, state), context=self.context,
        )
        return verdict, [response]

    async def _phase_feasibility(self, node: Node, state: ExecutionState):
        plan = state.outputs["plan"]
        responses = await phases.run_plan_feasibility(
            self.client, state.request, self._triage(state), plan,
            self._specialists(state), self.context,
        )
        # Feasibility mutates the plan's blockers rather than producing a
        # verdict of its own; the gate downstream reads plan.ready.
        return {"reviewed": len(responses), "blockers": list(plan.blockers)}, responses

    async def _phase_implement(self, node: Node, state: ExecutionState):
        lead = self._resolve_who(node, state)
        last = self.failure_log[-1] if self.failure_log else {}
        verdict, responses = await phases.run_implement(
            self.client, state.request, state.outputs["plan"], lead,
            iteration=state.iteration or 1,
            red_cause=last.get("red_cause"),
            # Every criterion validate judged, and whatever review blocked on —
            # both recorded in the failure log already, neither previously read
            # back. §15.1 measured the loop rediscovering one criterion at a
            # time while the rest sat in the log unread.
            evidence=last.get("evidence"),
            review_findings=last.get("review_findings"),
            resolution_directive=self.resolution_directive,
            context=self.context,
            primary_domain=None,      # the lead is already resolved
        )
        return verdict, responses

    async def _phase_domain_review(self, node: Node, state: ExecutionState):
        implement = state.outputs["implement"]
        reviewers = self._resolve_who(node, state)
        concerns, critical, responses = await phases.run_domain_review(
            self.client, state.request, state.outputs["plan"],
            implement.summary, reviewers, self.context,
        )
        # A critical concern flips the implementation red, exactly as it did
        # when the two steps lived in one function.
        implement.domain_concerns = concerns
        if critical:
            implement.green = False
            # The reviewer's own words rather than a fixed sentence — see
            # phases.render_domain_concerns. 006-D1(b) measured this channel
            # carrying one generic string, so the next attempt could not know
            # which choice was objected to.
            implement.red_cause = phases.render_domain_concerns(concerns)
        return {"concerns": concerns, "critical": critical,
                "reviewers": len(reviewers)}, responses

    async def _phase_validate(self, node: Node, state: ExecutionState):
        triage = self._triage(state)
        implement = state.outputs["implement"]
        verdict, response = await phases.run_validate(
            self.client, state.request, state.outputs["plan"], implement,
            context=self.context, domains=triage.domains,
            max_tokens=self._max_tokens(node),
        )
        # Record any iteration that failed, for any judge's reason. This used
        # to fire only on a red validate, which was sufficient while the loop
        # exited on validate alone. It is not now: the fold keeps iterating when
        # the implementation is red and the validator is green, and in that case
        # nothing was written here — so the next attempt read a stale entry, or
        # none, and was told nothing about why it was going round again.
        if not verdict.green or not implement.green:
            self.failure_log.append({
                "iteration": state.iteration,
                "implement_summary": implement.summary,
                "red_cause": verdict.red_cause or implement.red_cause,
                "evidence": verdict.evidence,
                # B3's invariant: the autopsy reads the failure log, so an
                # honest refusal travels with it — escalation must be able to
                # see what the implementer said it could not satisfy.
                "blocked_on": list(getattr(implement, "blocked_on", None) or []),
            })

        # Validate closes an iteration, so this is where one is complete enough
        # to record. Cost is a delta on the client's running total, which counts
        # every path including research and rerank.
        spend = self.client.spend
        # Which judge blocked the exit. Two things were wrong with the first
        # attempt at this, and both made it record nothing for 64 iterations:
        # a check's output is a plain dict in `state.outputs`, not an object,
        # so `getattr(coverage, "passed", None)` was None every time; and the
        # fold cannot be read here at all, because `judges` is the node *after*
        # validate in the loop body, so the only fold in `outputs` belongs to
        # the previous iteration. The dissent is therefore derived from the four
        # judges themselves, all of which have run by now — which is what the
        # fold does anyway, and cannot go stale.
        coverage = state.outputs.get("coverage") or {}
        consistency = state.outputs.get("consistency") or {}
        coverage_passed = coverage.get("passed")
        consistency_passed = consistency.get("passed")
        coverage_abstained = coverage.get("abstained", [])
        judged = {
            "implement": implement.green,
            "validate": verdict.green,
            "coverage": coverage_passed,
            "consistency": consistency_passed,
        }
        self.iterations.append({
            "iteration": state.iteration,
            "dissenting": sorted(name for name, green in judged.items()
                                 if green is False),
            "coverage_passed": coverage_passed,
            "coverage_abstained_count": len(coverage_abstained),
            "consistency_passed": consistency_passed,
            "implement_green": implement.green,
            "implement_red_cause": implement.red_cause,
            "implement_summary": implement.summary,
            "domain_concerns": list(implement.domain_concerns or []),
            "validate_green": verdict.green,
            "validate_red_cause": verdict.red_cause,
            "validate_evidence": list(verdict.evidence or []),
            "cost": round(spend - self._spend_at_last_iteration, 6),
        })
        self._spend_at_last_iteration = spend
        return verdict, [response]

    async def _phase_escalation(self, node: Node, state: ExecutionState):
        verdict, response = await phases.run_escalation_autopsy(
            self.client, state.request, state.outputs["plan"],
            self._triage(state), self.failure_log, self.context,
        )
        # A fresh directive, and a clean slate: the recovery attempts should not
        # inherit the failures that prompted the autopsy.
        self.resolution_directive = verdict.resolution_directive
        self.failure_log = []
        return verdict, [response]

    async def _phase_review(self, node: Node, state: ExecutionState):
        verdict, responses = await phases.run_review(
            self.client, state.request, self._triage(state), state.outputs["plan"],
            state.outputs["implement"], self._resolve_who(node, state), self.context,
        )
        # A blocking review is a failed attempt like any other, and the rework
        # loop downstream reads the failure log. Without this it would rework
        # against the last validate failure while the thing that actually
        # blocked the run sat unread — the same defect as §15.1's evidence, one
        # phase later.
        if not verdict.ship:
            self.failure_log.append({
                "iteration": state.iteration,
                "implement_summary": state.outputs["implement"].summary,
                "red_cause": f"Review blocked: {verdict.verdict}".strip(),
                "evidence": [],
                "review_findings": [f.model_dump() for f in verdict.findings],
            })
        return verdict, responses

    async def _phase_doublecheck(self, node: Node, state: ExecutionState):
        """One independent pass, on a model that has seen no prior review.

        Reached only when triage marks the work unrecallable. A signed rollout
        or a mass migration harms nobody and cannot be taken back, so it stays
        `high` rather than inflating `critical`, and buys one more reviewer
        instead of a larger team.

        The tier resolves to premium when configured and the architecture tier
        otherwise — a different family from the engineering tier that produced
        the work. It resolves to nothing when that would land on the engineering
        model itself, and then this records a skip: a review by the model under
        review is not a second opinion, and claiming one would be worse than
        admitting there is none. A node that raised here would make a correctly
        classified request fail for want of configuration.
        """
        if self.client.independent_model() is None:
            return {
                "skipped": True,
                "reason": ("no model available for an independent pass that is "
                           "not the engineering model itself"),
            }, []
        verdict, response = await phases.run_doublecheck(
            self.client, state.request, state.outputs["plan"],
            state.outputs["implement"], self.context,
        )
        return verdict, [response]
