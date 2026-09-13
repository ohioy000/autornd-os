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
    DoubleCheckVerdict,
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


# AutoRnD's deliverable is the engineering artifact as text. Models have no
# repository, shell or build tools — and a model that answers "I cannot make
# changes" produces an empty implementation that validate then correctly
# rejects, burning the entire iteration budget and escalating a healthy
# request. Every producing prompt states this contract explicitly.
OUTPUT_CONTRACT = """\
You have no repository, file system, shell, or build tools, and you are not \
expected to. Nothing you write is executed or applied automatically.

Your response IS the deliverable. Produce the actual engineering work as text \
— the design, the code, the schema, the procedure, the calculation — in enough \
detail that a competent engineer could apply it directly. Never reply that you \
are unable to make changes or lack access: describing the work precisely is \
the task."""

# The mirror of the above for the assessing phases. Without it, validators
# reject work for "not having been executed", which is never achievable here.
ASSESSMENT_CONTRACT = """\
You are assessing a written implementation, not a running system. You cannot \
execute code, run tests, or inspect a repository, and the absence of a live \
system is not itself a defect.

Judge whether the implementation as described would satisfy each success \
criterion if applied as written. Mark it red only for substantive problems: a \
criterion it does not address, a logical error, a contradiction with the plan, \
or a missing step. Do not mark it red merely because the work has not been run.

Be exacting about the difference. "The plan says cap at 60s but the code sets \
600s" is red. "I cannot confirm this without running it" is not — decide from \
the text in front of you and say what you found."""


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
- critical: safety, regulatory or compliance exposure; irreversible physical or
  financial consequence; anything affecting human wellbeing
- high: expensive or impossible to reverse; core system behaviour; security
  boundaries; data integrity
- medium: data model and schema changes, service configuration, integrations
- low: presentation, styling, copy, documentation

Always include test_engineer for high/critical risk.
Always include systems_architect for multi-domain requests.

Request:
{request}"""

    data, response = await client.chat_json(
        function="triage",
        system_prompt="You are a triage classifier for an engineering team. Respond with JSON only.",
        user_message=prompt,
       schema=TriageVerdict,
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
    context = await build_phase_context(
        request, triage.domains, triage.specialists, client=client
    )
    context_block = f"\n\nProject context:\n{context}" if context else ""
    prompt = f"""\
Create an implementation plan for this engineering request.

{OUTPUT_CONTRACT}

Triage classification:
- Domains: {', '.join(d.value for d in triage.domains)}
- Risk: {triage.risk.value}
- Assigned specialists: {specialist_names}
{context_block}

Return JSON with:
- ready: true if plan is feasible, false if blocked
- plan: detailed implementation plan (step by step)
- blockers: list of blocking issues (empty if ready)
- cost_estimate: estimated material or resource cost in USD where the work
  implies one (components, licences, capacity), null where it does not
- success_criteria: 3 to 6 concrete criteria the validate phase will check

The success criteria are the most important thing you produce. Every later
phase is judged against them and nothing else, so write them as real sentences
about the finished work — never placeholders, never "...", never "TBD".

Each one must be settleable by reading the implementation rather than by
running it: "reconnect loop applies exponential backoff capped at 60s with
jitter", not "reconnects within 30s in production".

If you cannot state real criteria, return ready: false and say why in blockers.

Request:
{request}"""

    architect = get_specialist(SpecialistRole.SYSTEMS_ARCHITECT)
    data, response = await client.chat_json(
        function="architecture",
        system_prompt=architect.system_prompt,
        user_message=prompt,
       schema=PlanVerdict,
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

    Each specialist checks the plan against the constraints of their own domain.
    Returns responses for cost tracking; side-effects update the plan's blockers.
    """
    architect_role = SpecialistRole.SYSTEMS_ARCHITECT
    reviewers = [s for s in specialists if s.role != architect_role]
    if not reviewers:
        return []

    context_block = f"\n\nProject context:\n{context}" if context else ""
    bom_block = (
        f"Cost estimate (USD): {plan.cost_estimate}\n"
        if plan.cost_estimate is not None else ""
    )
    prompt = f"""\
Review this implementation plan from your specialist perspective for feasibility.
{context_block}

Plan produced by Systems Architect:
{plan.plan}

{bom_block}
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


# Checks a reviewer can actually settle by reading a written implementation:
# arithmetic that either reconciles or does not, and structural properties that
# are either present or absent. Injected only for the domains a request touches
# — asking about connector pinouts on a copy change is how a validator learns
# to ignore this section.
DOMAIN_CHECKS: dict[Domain, tuple[str, ...]] = {
    Domain.HARDWARE: (
        "Do quantities, tolerances and costs sum to the stated totals?",
        "Do any two components contend for the same connection, pin or space?",
        "Does the design stay inside every stated physical, power or thermal budget?",
    ),
    Domain.FIRMWARE: (
        "Do timing, memory and power figures reconcile against the stated budget?",
        "Is every state in a described state machine both reachable and exitable?",
        "Are concurrency, interrupt and buffer-ownership rules stated and consistent?",
    ),
    Domain.BACKEND: (
        "Are schema, field and type changes consistent everywhere they appear?",
        "Is every error and failure path in the described flow handled?",
        "Do the described keys, indexes and queries serve the stated access pattern?",
    ),
    Domain.FRONTEND: (
        "Is every state the interface can enter — empty, loading, error, overflow — accounted for?",
        "Does the described view only use data the system actually provides?",
    ),
    Domain.INFRASTRUCTURE: (
        "Are the described configuration values internally consistent?",
        "Is startup, shutdown and failure behaviour specified for each component?",
    ),
    Domain.SUPPLY_CHAIN: (
        "Do unit costs, quantities and totals reconcile?",
        "Is every single-sourced or long-lead item identified as such?",
    ),
    Domain.DOCUMENTATION: (
        "Does the text match the behaviour the plan actually describes?",
    ),
}


def build_domain_checks(domains: list[Domain]) -> str:
    """Deterministic checks for the domains in play, de-duplicated, order-stable."""
    seen: list[str] = []
    for domain in domains:
        for check in DOMAIN_CHECKS.get(domain, ()):
            if check not in seen:
                seen.append(check)
    if not seen:
        return ""
    return (
        "\n\nWhen judging the criteria above, these are the questions that "
        "usually decide\nthem in this domain. They are lenses, not extra "
        "criteria: something here\nthat the success criteria do not cover is a "
        "note, never a reason to fail\nthe work.\n"
        + "\n".join(f"- {c}" for c in seen)
    )


DOMAIN_LEAD_MAP: dict[Domain, SpecialistRole] = {
    Domain.FIRMWARE: SpecialistRole.FIRMWARE_ENGINEER,
    Domain.HARDWARE: SpecialistRole.HARDWARE_ENGINEER,
    Domain.BACKEND: SpecialistRole.BACKEND_ENGINEER,
    Domain.FRONTEND: SpecialistRole.FRONTEND_ENGINEER,
    Domain.SUPPLY_CHAIN: SpecialistRole.SUPPLY_CHAIN,
    Domain.INFRASTRUCTURE: SpecialistRole.SYSTEMS_ARCHITECT,
    Domain.DOCUMENTATION: SpecialistRole.BACKEND_ENGINEER,
}


async def run_implement(
    client: OpenRouterClient,
    request: str,
    plan: PlanVerdict,
    specialists: list[Specialist],
    iteration: int,
    red_cause: str | None = None,
    resolution_directive: str | None = None,
    context: str = "",
    primary_domain: Domain | None = None,
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
    implement_prompt = f"""\
Produce the implementation for the following plan. This is iteration {iteration}.

{OUTPUT_CONTRACT}

Plan:
{plan.plan}

Success criteria:
{json.dumps(plan.success_criteria)}
{feasibility_block}
{feedback}
{context_block}

Return JSON with:
- done: true if the implementation is complete
- green: true if you believe it satisfies the success criteria
- red_cause: null if green, otherwise a short string describing what is wrong
- iteration: {iteration}
- summary: the implementation itself — the design, code, schema, procedure or
  calculation, in full. This field is the deliverable and is what the validate
  phase and every downstream reviewer will read, so write the work out rather
  than describing it in the abstract.

Original request:
{request}"""

    responses: list[ModelResponse] = []

    # Select lead specialist based on primary domain
    lead = specialists[0]
    reviewers: list[Specialist] = []
    if primary_domain and len(specialists) > 1:
        target_role = DOMAIN_LEAD_MAP.get(primary_domain)
        if target_role:
            for s in specialists:
                if s.role == target_role:
                    lead = s
                    break
        reviewers = [s for s in specialists if s is not lead]

    # Step 1: Lead implements
    lead_data, lead_resp = await lead.run(client, implement_prompt)
    responses.append(lead_resp)
    lead_data["iteration"] = iteration
    domain_concerns: list[str] = []

    # Step 2: Domain review (only if lead succeeded and there are reviewers)
    if lead_data.get("green") and reviewers:
        review_prompt = f"""\
Review this implementation from your domain perspective. Do NOT produce an alternative design.

{ASSESSMENT_CONTRACT}
{context_block}

Implementation summary:
{lead_data.get("summary", "")}

Success criteria:
{json.dumps(plan.success_criteria)}

Return JSON with:
- concerns: list of specific domain concerns (empty list if none)
- critical: true if any concern is a hard blocker that would cause failure

Original request:
{request}"""

        async def _domain_review(spec: Specialist) -> dict[str, Any]:
            data, resp = await spec.run(client, review_prompt)
            responses.append(resp)
            return data

        review_results = await asyncio.gather(
            *[_domain_review(s) for s in reviewers]
        )
        for result in review_results:
            for c in result.get("concerns", []):
                if isinstance(c, str):
                    domain_concerns.append(c)
            if result.get("critical"):
                lead_data["green"] = False
                lead_data["red_cause"] = "Domain reviewer flagged critical concern"

    lead_data["domain_concerns"] = domain_concerns
    verdict = ImplementVerdict(**lead_data)
    return verdict, responses


async def run_validate(
    client: OpenRouterClient,
    request: str,
    plan: PlanVerdict,
    implement: ImplementVerdict,
    context: str = "",
    domains: list[Domain] | None = None,
) -> tuple[ValidateVerdict, ModelResponse]:
    test_eng = get_specialist(SpecialistRole.TEST_ENGINEER)
    context_block = f"\n\nProject context:\n{context}" if context else ""
    checks_block = build_domain_checks(domains or [])
    concerns_block = ""
    if implement.domain_concerns:
        concerns_block = f"""

DOMAIN REVIEW CONCERNS (flagged by specialist reviewers — verify these):
{chr(10).join(f'- {c}' for c in implement.domain_concerns)}"""

    prompt = f"""\
Validate this implementation against the plan's success criteria.

{ASSESSMENT_CONTRACT}
{context_block}

Success criteria:
{json.dumps(plan.success_criteria)}

Implementation summary (iteration {implement.iteration}):
{implement.summary}
{concerns_block}

Check the implementation against each success criterion in turn, and judge the
work on those criteria alone. Where a criterion is quantitative and the numbers
are present, do the arithmetic and show it. Where it is structural, check the
design actually has the property.

Only a stated success criterion can make this red. Anything else you notice —
a better approach, a missing extra, a concern outside the criteria — belongs in
evidence as a note. If the criteria themselves are unusable, say so in
red_cause rather than substituting criteria of your own.
{checks_block}

Return JSON with:
- green: true if every success criterion is satisfied
- red_cause: null if green, otherwise the specific failure cause
- evidence: list of evidence strings, one per criterion, each naming the
  criterion and what you found. Give a verdict for every criterion, whether it
  passed or failed, e.g.
    "Backoff capped at 60s: PASS — step 2 sets max_interval=60"
    "Jitter applied per attempt: FAIL — step 2 sets a fixed delay, no jitter"

Original request:
{request}"""

    data, response = await test_eng.run(client, prompt, schema=ValidateVerdict)
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

{ASSESSMENT_CONTRACT}
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

{"Search for failure modes. What breaks under load, at the boundaries, on partial failure, or when an assumption in the plan turns out to be false?" if adversarial else "Focus on correctness and completeness."}

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


async def run_doublecheck(
    client: OpenRouterClient,
    request: str,
    plan: PlanVerdict,
    implement: ImplementVerdict,
    context: str = "",
) -> tuple[DoubleCheckVerdict, ModelResponse]:
    context_block = f"\n\nProject context:\n{context}" if context else ""
    system_prompt = (
        "You are an independent senior engineering reviewer. "
        "You have NOT seen any previous review of this work. "
        "Evaluate this implementation for correctness, safety, and completeness. "
        "Be thorough and adversarial — look for failure modes, edge cases, and spec violations."
    )
    user_message = f"""\
Review this engineering implementation independently.

{ASSESSMENT_CONTRACT}
{context_block}

Plan:
{plan.plan}

Success criteria:
{json.dumps(plan.success_criteria)}

Implementation summary:
{implement.summary}

Return JSON with:
- ship: true if safe to ship with no blocking issues
- confidence: "high", "medium", or "low"
- critical_issues: list of critical issues found (empty if none)
- recommendations: list of improvement recommendations
- verdict: one-sentence final assessment

Original request:
{request}"""

    data, response = await client.chat_json(
        function="premium",
        system_prompt=system_prompt,
        user_message=user_message,
    )
    verdict = DoubleCheckVerdict(**data)
    return verdict, response


ESCALATION_SYSTEM_PROMPT = """\
You are the Principal Systems Architect for AutoRnD.
The Implementation agent has failed {n} consecutive validation attempts.
Your objective is to perform a root-cause autopsy and generate a resolution directive.
You must not produce the implementation yourself. You direct the implementing agent.

You MUST respond with a JSON object containing exactly these fields:
{{
  "root_cause_analysis": "The fundamental logic or architectural flaw causing the consecutive failures. Conclusion only, no reasoning steps.",
  "architectural_correction": "Corrected logic or missing dependencies if the original plan was flawed. null if plan was sound.",
  "resolution_directive": "Specific, step-by-step instructions for the Implementation model to succeed on its next attempt.",
  "requires_human": false
}}
Set requires_human to true ONLY if the fix requires access, credentials or a
real-world action that no amount of further specification can supply, or falls
entirely outside the scope of the current architecture."""


async def run_escalation_autopsy(
    client: OpenRouterClient,
    request: str,
    plan: PlanVerdict,
    triage: TriageVerdict,
    failure_log: list[dict[str, Any]],
    context: str = "",
) -> tuple[EscalationVerdict, ModelResponse]:
    system_prompt = ESCALATION_SYSTEM_PROMPT.format(n=len(failure_log))
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
