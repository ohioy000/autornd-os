"""Phase implementations — triage, plan, implement, validate, review.

Each function takes a request context + OpenRouter client, calls the appropriate
specialist(s), and returns a typed verdict.
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

from autornd.config import settings
from autornd.models.verdicts import (
    Domain,
    EscalationVerdict,
    ImplementVerdict,
    PlanVerdict,
    ReviewFinding,
    ReviewVerdict,
    RiskLevel,
    SpecialistRole,
    TriageVerdict,
    ValidateVerdict,
)
from autornd.knowledge.context import build_phase_context
from autornd.routing.openrouter import ModelResponse, OpenRouterClient
from autornd.specialists.base import Specialist
from autornd.specialists.registry import get_specialist, get_specialists

logger = logging.getLogger(__name__)


async def run_triage(
    client: OpenRouterClient, request: str
) -> tuple[TriageVerdict, ModelResponse]:
    prompt = f"""\
Classify this engineering request. Return JSON with:
- domains: list of applicable domains from [{', '.join(d.value for d in Domain)}]
- risk: one of [{', '.join(r.value for r in RiskLevel)}]
- specialists: list of specialists to assign from [{', '.join(s.value for s in SpecialistRole)}]
- summary: one-line classification

Risk guide:
- critical: safety, regulatory, battery chemistry, livestock proximity
- high: hardware irreversible (PCB, antenna, enclosure), firmware core (LoRa MAC, deep sleep, OTA)
- medium: backend data (schema, MQTT topics, decoders), infrastructure (Docker, systemd)
- low: frontend UI, documentation

Always include test_engineer for high/critical risk.
Always include systems_architect for multi-domain requests.

Request:
{request}"""

    data, response = await client.chat_json(
        function="triage",
        system_prompt="You are a triage classifier for an engineering team. Respond with JSON only.",
        user_message=prompt,
    )
    verdict = TriageVerdict(**data)
    return verdict, response


async def run_plan(
    client: OpenRouterClient,
    request: str,
    triage: TriageVerdict,
    specialists: list[Specialist],
) -> tuple[PlanVerdict, ModelResponse]:
    specialist_names = ", ".join(s.name for s in specialists)
    context = build_phase_context(request, triage.domains, triage.specialists)
    context_block = f"\n\nProject context:\n{context}" if context else ""
    prompt = f"""\
Create an implementation plan for this engineering request.

Triage classification:
- Domains: {', '.join(d.value for d in triage.domains)}
- Risk: {triage.risk.value}
- Assigned specialists: {specialist_names}
{context_block}

Return JSON with:
- ready: true if plan is feasible, false if blocked
- plan: detailed implementation plan (step by step)
- blockers: list of blocking issues (empty if ready)
- bom_estimate: estimated BOM cost in USD if hardware is involved, null otherwise
- success_criteria: list of measurable criteria the validate phase will check

Request:
{request}"""

    architect = get_specialist(SpecialistRole.SYSTEMS_ARCHITECT)
    data, response = await client.chat_json(
        function="architecture",
        system_prompt=architect.system_prompt,
        user_message=prompt,
    )
    verdict = PlanVerdict(**data)
    return verdict, response


async def run_plan_feasibility(
    client: OpenRouterClient,
    request: str,
    triage: TriageVerdict,
    plan: PlanVerdict,
    specialists: list[Specialist],
    context: str = "",
) -> list[ModelResponse]:
    """Domain specialists review the architect's plan for feasibility.

    Hardware Engineer checks BOM constraints, Supply Chain validates sourcing
    and cost, other domain specialists check their area of concern.
    Returns responses for cost tracking; side-effects update the plan's blockers.
    """
    architect_role = SpecialistRole.SYSTEMS_ARCHITECT
    reviewers = [s for s in specialists if s.role != architect_role]
    if not reviewers:
        return []

    context_block = f"\n\nProject context:\n{context}" if context else ""
    prompt = f"""\
Review this implementation plan from your specialist perspective for feasibility.
{context_block}

Plan produced by Systems Architect:
{plan.plan}

BOM estimate: {plan.bom_estimate}
Success criteria: {json.dumps(plan.success_criteria)}

Return JSON with:
- feasible: true if the plan is feasible from your domain's perspective
- concerns: list of specific concerns or constraints from your domain
- blockers: list of hard blockers that would prevent implementation (empty if feasible)

Original request:
{request}"""

    responses: list[ModelResponse] = []
    all_blockers: list[str] = []

    async def _check(spec: Specialist) -> dict:
        data, resp = await spec.run(client, prompt)
        responses.append(resp)
        return data

    results = await asyncio.gather(*[_check(s) for s in reviewers])

    for result in results:
        for b in result.get("blockers", []):
            all_blockers.append(b)

    if all_blockers:
        plan.blockers.extend(all_blockers)

    return responses


async def run_implement(
    client: OpenRouterClient,
    request: str,
    plan: PlanVerdict,
    specialists: list[Specialist],
    iteration: int,
    red_cause: str | None = None,
    resolution_directive: str | None = None,
    context: str = "",
) -> tuple[ImplementVerdict, list[ModelResponse]]:
    feedback = ""
    if resolution_directive:
        feedback += f"""

PRINCIPAL ARCHITECT DIRECTIVE (from root-cause autopsy):
{resolution_directive}"""
    if red_cause:
        feedback += f"""

PREVIOUS ITERATION FAILED. Cause: {red_cause}
Address this specific failure in your implementation."""

    feasibility_block = ""
    if plan.blockers:
        feasibility_block = f"""

FEASIBILITY CONCERNS (from domain specialist review — address these):
{chr(10).join(f'- {b}' for b in plan.blockers)}"""

    context_block = f"\n\nProject context:\n{context}" if context else ""
    prompt = f"""\
Implement the following plan. This is iteration {iteration}.

Plan:
{plan.plan}

Success criteria:
{json.dumps(plan.success_criteria)}
{feasibility_block}
{feedback}
{context_block}

Return JSON with:
- done: true if implementation is complete
- green: true if you believe this passes the success criteria
- red_cause: null if green, otherwise a short string describing what's wrong
- iteration: {iteration}
- summary: what was done in this iteration

Original request:
{request}"""

    responses: list[ModelResponse] = []

    async def _run_specialist(spec: Specialist) -> dict[str, Any]:
        data, resp = await spec.run(client, prompt)
        responses.append(resp)
        return data

    if len(specialists) == 1:
        data = await _run_specialist(specialists[0])
    else:
        results = await asyncio.gather(
            *[_run_specialist(s) for s in specialists]
        )
        data = results[0]
        for extra in results[1:]:
            if extra.get("red_cause"):
                data["green"] = False
                data["red_cause"] = extra["red_cause"]
            data["summary"] = data.get("summary", "") + "\n" + extra.get("summary", "")

    data["iteration"] = iteration
    verdict = ImplementVerdict(**data)
    return verdict, responses


async def run_validate(
    client: OpenRouterClient,
    request: str,
    plan: PlanVerdict,
    implement: ImplementVerdict,
    context: str = "",
) -> tuple[ValidateVerdict, ModelResponse]:
    test_eng = get_specialist(SpecialistRole.TEST_ENGINEER)
    context_block = f"\n\nProject context:\n{context}" if context else ""
    prompt = f"""\
Validate this implementation against the plan's success criteria.
{context_block}

Success criteria:
{json.dumps(plan.success_criteria)}

Implementation summary (iteration {implement.iteration}):
{implement.summary}

Run deterministic checks where possible:
- Does the power budget math work?
- Do pin assignments conflict?
- Does the BOM stay under target ({plan.bom_estimate})?
- Are all API schemas correct?
- Are MQTT topics properly routed?

Return JSON with:
- green: true if all success criteria pass
- red_cause: null if green, otherwise the specific failure cause
- evidence: list of evidence strings (e.g. "Total BOM $47.20 exceeds target $42.50")

Original request:
{request}"""

    data, response = await test_eng.run(client, prompt)
    verdict = ValidateVerdict(**data)
    return verdict, response


async def run_review(
    client: OpenRouterClient,
    request: str,
    triage: TriageVerdict,
    plan: PlanVerdict,
    implement: ImplementVerdict,
    specialists: list[Specialist],
    context: str = "",
) -> tuple[ReviewVerdict, list[ModelResponse]]:
    adversarial = triage.risk in (RiskLevel.CRITICAL, RiskLevel.HIGH)
    review_mode = "ADVERSARIAL — actively search for failure modes" if adversarial else "COLLABORATIVE"
    context_block = f"\n\nProject context:\n{context}" if context else ""

    prompt = f"""\
Review this engineering work from your specialist lens.
{context_block}

Review mode: {review_mode}
Risk level: {triage.risk.value}

Plan:
{plan.plan}

Implementation summary:
{implement.summary}

Return JSON with:
- findings: list of objects, each with:
  - lens: your specialist role (e.g. "firmware_engineer")
  - severity: one of [critical, high, medium, low]
  - detail: specific finding
- ship: true if safe to ship with no blocking findings
- verdict: one-sentence synthesis

{"Search for failure modes. What could go wrong in production? In extreme weather? With intermittent power? With low battery?" if adversarial else "Focus on correctness and completeness."}

Original request:
{request}"""

    responses: list[ModelResponse] = []
    all_findings: list[dict[str, Any]] = []
    any_blocking = False
    failed_specialists: list[str] = []

    async def _review(spec: Specialist) -> dict[str, Any] | None:
        try:
            data, resp = await spec.run(client, prompt)
            responses.append(resp)
            return data
        except Exception:
            logger.exception("Specialist %s failed during review", spec.name)
            failed_specialists.append(spec.name)
            return None

    results = await asyncio.gather(*[_review(s) for s in specialists])
    successful = [r for r in results if r is not None]

    for result in successful:
        for f in result.get("findings", []):
            all_findings.append(f)
            if f.get("severity") in ("critical", "high"):
                any_blocking = True

    if failed_specialists:
        any_blocking = True
        for name in failed_specialists:
            all_findings.append({
                "lens": "workflow_engine",
                "severity": "high",
                "detail": f"Specialist {name} failed to complete review — manual review required",
            })

    ship = not any_blocking and all(r.get("ship", True) for r in successful)

    verdicts_text = " | ".join(r.get("verdict", "") for r in successful)
    if failed_specialists:
        verdicts_text += f" | {len(failed_specialists)} specialist(s) failed"
    if ship:
        synthesis = f"Ship. {verdicts_text}"
    else:
        synthesis = f"Blocked. {verdicts_text}"

    findings = [ReviewFinding(**f) for f in all_findings]
    verdict = ReviewVerdict(ship=ship, findings=findings, verdict=synthesis)
    return verdict, responses


K3_ESCALATION_PROMPT = """\
You are the Principal Systems Architect for AutoRnD.
The Implementation agent has failed {n} consecutive validation attempts.
Your objective is to perform a root-cause autopsy and generate a resolution directive.
You must not write the raw code patch yourself. You must guide the subordinate agent.

You MUST respond with a JSON object containing exactly these fields:
{{
  "root_cause_analysis": "The fundamental logic or architectural flaw causing the consecutive failures. Conclusion only, no reasoning steps.",
  "architectural_correction": "Corrected logic or missing dependencies if the original plan was flawed. null if plan was sound.",
  "resolution_directive": "Specific, step-by-step instructions for the Implementation model to succeed on its next attempt.",
  "requires_human": false
}}
Set requires_human to true ONLY if the fix requires external API keys, manual hardware intervention, or falls entirely outside the current architecture scope."""


async def run_escalation_autopsy(
    client: OpenRouterClient,
    request: str,
    plan: PlanVerdict,
    triage: TriageVerdict,
    failure_log: list[dict[str, Any]],
    context: str = "",
) -> tuple[EscalationVerdict, ModelResponse]:
    system_prompt = K3_ESCALATION_PROMPT.format(n=len(failure_log))
    context_block = f"\n\nProject context:\n{context}" if context else ""
    system_prompt += f"""

Architect's Plan:
{plan.plan}

Triage Classification:
- Domains: {', '.join(d.value for d in triage.domains)}
- Risk: {triage.risk.value}
- Success Criteria: {json.dumps(plan.success_criteria)}
{context_block}"""

    user_message = f"""\
The following {len(failure_log)} implementation attempts all failed validation.
Analyze the failure pattern and produce a resolution directive.

Failure Log:
{json.dumps(failure_log, indent=2)}

Original Request:
{request}"""

    data, response = await client.chat_json(
        function="escalation",
        system_prompt=system_prompt,
        user_message=user_message,
        temperature=0.1,
        max_tokens=settings.escalation_max_tokens,
    )
    verdict = EscalationVerdict(**data)
    return verdict, response
