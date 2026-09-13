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
from autornd.knowledge.context import build_phase_context
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
        self.total_cost: float = 0.0

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
        for response in responses:
            self.total_cost += response.cost
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
        self.context = await build_phase_context(
            state.request, triage.domains, triage.specialists, client=self.client
        )
        return Result(
            True,
            f"{len(self.context)} characters of context assembled",
            chars=len(self.context),
            grounded=bool(self.context),
        )

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
            implement.red_cause = "Domain reviewer flagged critical concern"
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
        if not verdict.green:
            self.failure_log.append({
                "iteration": state.iteration,
                "implement_summary": implement.summary,
                "red_cause": verdict.red_cause,
                "evidence": verdict.evidence,
            })
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
        return verdict, responses

    async def _phase_doublecheck(self, node: Node, state: ExecutionState):
        """One independent pass, on a model that has seen no prior review.

        Reached only when triage marks the work unrecallable. A signed rollout
        or a mass migration harms nobody and cannot be taken back, so it stays
        `high` rather than inflating `critical`, and buys one more reviewer
        instead of a larger team.

        The premium tier is optional, so an unconfigured one records a skip. A
        node that raised here would make a correctly-classified request fail for
        want of configuration.
        """
        from autornd.config import settings

        if not settings.model_premium:
            return {
                "skipped": True,
                "reason": "no premium tier configured for the independent pass",
            }, []
        verdict, response = await phases.run_doublecheck(
            self.client, state.request, state.outputs["plan"],
            state.outputs["implement"], self.context,
        )
        return verdict, [response]
