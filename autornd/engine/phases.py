"""Phase implementations — triage, plan, implement, validate, review.

Each function takes a request context + OpenRouter client, calls the appropriate
specialist(s), and returns a typed verdict.
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

from pydantic import ValidationError

from autornd.config import settings
from autornd.models.verdicts import (
    domain_key,
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
# The criteria-are-fixed clause is measured, not stylistic. 007's
# requires_execution trace: the criterion demanded a test at exactly 101 req/s,
# the implementation used 121, and validate returned
#
#   "Criterion 2 (exactly 100 and 101 req/s): PASS — Test Case 1 covers
#    100 req/s; Test Case 2 corrected to 121 req/s, with 101 req/s explicitly
#    noted as not causing rejection."
#
# — marking PASS while stating in the same sentence that the test had been
# changed away from what the criterion asked for. The domain reviewer caught it
# and the final review blocked on it; validate was the judge that was wrong, and
# a false pass is the expensive direction because it stops the loop.
#
# Expect this to need live iterations, as the risk guide did four times over.
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
the text in front of you and say what you found.

The success criteria are the contract you assess against, and they are fixed. \
You may not correct, reinterpret, relax or substitute a criterion, and you may \
not accept work that changed one. Where the work and a criterion disagree, that \
criterion FAILS — whichever of the two looks more sensible to you. Saying a \
criterion is wrong, ambiguous or impossible is legitimate and belongs in \
evidence; passing work against a criterion you have quietly amended is a false \
assessment, and a false pass is worse than a wrong criterion because it ends \
the loop."""


def enforce_triage_composition(verdict: TriageVerdict) -> None:
    """Add the specialists the rules require, whatever the model returned.

    Measured over five live runs, triage omitted the test engineer on
    safety-relevant hardware work three times out of five. These two rules are
    not judgement calls, so they are not left to a model: risky work gets a test
    engineer, and work spanning domains gets an architect.

    Applied here rather than in a caller, because a rule enforced in one code
    path and not another is a rule that quietly stops existing — which is what
    happened when the engine moved to the graph.
    """
    if verdict.risk in (RiskLevel.CRITICAL, RiskLevel.HIGH):
        if SpecialistRole.TEST_ENGINEER not in verdict.specialists:
            verdict.specialists.append(SpecialistRole.TEST_ENGINEER)
    if len(verdict.domains) > 1:
        if SpecialistRole.SYSTEMS_ARCHITECT not in verdict.specialists:
            verdict.specialists.append(SpecialistRole.SYSTEMS_ARCHITECT)


def _domain_vocabulary() -> str:
    """The domains to offer triage: the shipped defaults plus the profile's own.

    Offered, not enforced. Forcing a closed list is what turned civil
    engineering into "hardware" and a latency budget into "firmware".
    """
    from autornd.profiles import get_profile

    names = [d.value for d in Domain]
    for extra in get_profile().domain_vocabulary():
        if extra not in names:
            names.append(extra)
    return ", ".join(names)


def _role_vocabulary() -> str:
    """The roles to offer triage: the shipped roster plus the profile's own.

    Offered, not enforced — for the same reason the domains are. Asked to staff
    a firmware signing-key rotation, triage returned `infrastructure_engineer`,
    which this harness does not ship; a legal team wants a paralegal and no
    shipped list of engineering roles will ever contain one.
    """
    from autornd.profiles import get_profile

    names = [r.value for r in SpecialistRole]
    for extra in get_profile().role_vocabulary():
        if extra not in names:
            names.append(extra)
    return ", ".join(names)


async def run_triage(
    client: OpenRouterClient, request: str
) -> tuple[TriageVerdict, ModelResponse]:
    prompt = f"""\
Classify this engineering request. Return JSON with:
- domains: applicable domains. Prefer these: {_domain_vocabulary()}.
  If none of them genuinely fits the subject, name the domain yourself in one or
  two lowercase words rather than forcing the closest available label.
- risk: one of [{', '.join(r.value for r in RiskLevel)}]
- specialists: who to assign. A specialist is a person's function on the team,
  not a subject — the subject goes in `domains`. Prefer these:
  {_role_vocabulary()}. If none of them covers the function this work needs,
  name the role in one or two lowercase words.
- unrecallable: true when a wrong answer cannot be taken back once released —
  a signed firmware rollout, a mass migration, a public release. Scale alone is
  not the test; the test is whether it can be recalled.
- summary: one-line classification

Risk guide — judge the consequence of being wrong, not the subject matter.
Ask these two questions in order.

First: if this answer is wrong, can a person be harmed, or does it breach a
rule that exists to prevent harm — structural loading, food contact,
sterility, pressure vessels, electrical code, emissions? If so it is critical,
at every stage. A lintel carrying a wall, a sterilisation protocol and a
food-contact material are critical while still on paper, because the paper is
what gets built and audited.

Not every published standard is one of those. A standard that exists for
quality, consistency or interoperability — broadcast loudness, file formats,
naming conventions, style guides — is not a harm rule, however formally it is
written and however much a breach embarrasses someone. Ask what the rule is
protecting, not whether a rule exists.

Second, if nobody can be harmed: has anything been committed to yet?
- high: the answer changes the physical world — wiring, installing, actuating
  or modifying equipment — or is safety-critical in function even while still a
  drawing, such as a control surface or a load path; or it ships as core system
  behaviour, a security boundary, or data integrity. Routing power to a sensor
  on a machine stays there, and someone stands next to it
- medium: the answer is still a decision, reversible until an order is placed
  or a part is cut — selecting a component, sizing a part, calculating a
  budget, setting a tolerance, taking a measurement
- low: presentation, copy, documentation or configuration that is trivially
  reversible and cannot hurt anyone

Work on something whose purpose is to protect — a backup, an interlock, an
alarm, a containment, a life-support system — is judged by what it protects,
not by the stage it is at. Sizing the backup aeration for a tank of live stock
is sizing work, and a wrong answer loses the entire stock, so it is at least
high rather than medium. It is critical only if a person can be harmed: losing
stock, equipment or money, however much of it, is high.

A protocol, schedule, policy, setpoint band or limit that will be followed
repeatedly carries the consequence of everything it governs. Judge it by what
happens when it is followed, not by the fact that it is a document. A
sterilisation protocol, a return-to-play progression and a style guide are all
paperwork: if following it can harm someone or breach a regulated requirement
it is critical, and if the worst case is rework or an unhappy audience it stays
low or medium.

Do not escalate because a subject sounds technical, expensive or unfamiliar.

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
    enforce_triage_composition(verdict)
    return verdict, response


async def run_plan(
    client: OpenRouterClient,
    request: str,
    triage: TriageVerdict,
    specialists: list[Specialist],
    tier: str | None = None,
    context: str | None = None,
) -> tuple[PlanVerdict, ModelResponse]:
    specialist_names = ", ".join(s.name for s in specialists)
    # Grounding is assembled once per workflow by its own node and passed in.
    # Rebuilding it here ran the whole research pipeline a second time —
    # expansion, ranking, briefing and any lookups — for an identical result.
    if context is None:
        context = await build_phase_context(
            request, triage.domains, triage.specialists, client=client
        )
    context_block = f"\n\nProject context:\n{context}" if context else ""
    prompt = f"""\
Create an implementation plan for this engineering request.

{OUTPUT_CONTRACT}

Triage classification:
- Domains: {', '.join(domain_key(d) for d in triage.domains)}
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


# Applied when a domain has no checks of its own — which, before profiles could
# declare them, was every domain outside the seven shipped ones. Validation was
# reaching those with no lenses at all.
#
# The unit question earns its place: `14 dBm` ERP where the source meant EIRP is
# well-formed, 2.15 dB wrong, and the difference between a compliant
# transmitter and a failed certification. No deterministic check catches it.
GENERIC_CHECKS: tuple[str, ...] = (
    "Do the stated quantities, rates and totals reconcile with each other?",
    "Is every stated constraint and success criterion addressed?",
    "Are units and conventions stated, and used consistently throughout?",
)


def build_domain_checks(domains: list[object]) -> str:
    """Deterministic checks for the domains in play, de-duplicated, order-stable.

    Built-in checks, plus any the profile declares for that domain. A domain
    with neither falls back to the generic set rather than contributing nothing.
    """
    from autornd.profiles import get_profile

    profile = get_profile()
    seen: list[str] = []
    for domain in domains:
        specific = tuple(DOMAIN_CHECKS.get(domain_key(domain), ())) \
            + profile.get_domain_checks(domain)
        for check in specific or GENERIC_CHECKS:
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


def lead_for_domain(domain: object) -> str:
    """Which specialist leads this domain, as a normalised role name.

    Profile vocabulary first, then the shipped defaults, then the architect —
    which is the right answer for a domain nobody has mapped, since
    cross-domain and unfamiliar work is exactly what that role is for. An
    unrecognised domain must never raise: triage is allowed to name a subject
    this harness has never seen.

    A profile-declared lead is returned as declared. Validating it against the
    shipped enum here is what made a profile mapping `legal_ops` to `paralegal`
    silently review with the architect instead — the roster is a default, not a
    limit, and the registry resolves a declared or undeclared role either way.
    """
    from autornd.models.verdicts import domain_key, role_key
    from autornd.profiles import get_profile

    key = domain_key(domain)

    declared = get_profile().get_domain_lead(key)
    if declared:
        return role_key(declared)

    for domain, role in DOMAIN_LEAD_MAP.items():
        if domain_key(domain) == key:
            return role_key(role)
    return role_key(SpecialistRole.SYSTEMS_ARCHITECT)


def select_lead(
    specialists: list[Specialist], primary_domain: Domain | None
) -> tuple[Specialist, list[Specialist]]:
    """Pick who implements and who reviews.

    One specialist writes the implementation so it is internally coherent; the
    rest review it without proposing an alternative. Splitting the roles is
    what stopped parallel specialists producing contradictory designs.
    """
    lead = specialists[0]
    reviewers: list[Specialist] = []
    if primary_domain and len(specialists) > 1:
        target_role = lead_for_domain(primary_domain)
        for candidate in specialists:
            if candidate.role == target_role:
                lead = candidate
                break
        reviewers = [s for s in specialists if s is not lead]
    return lead, reviewers


def build_domain_review_prompt(
    request: str, plan: PlanVerdict, summary: str, context: str = ""
) -> str:
    context_block = f"\n\nProject context:\n{context}" if context else ""
    return f"""\
Review this implementation from your domain perspective. Do NOT produce an alternative design.

{ASSESSMENT_CONTRACT}
{context_block}

Implementation summary:
{summary}

Success criteria:
{json.dumps(plan.success_criteria)}

Return JSON with:
- concerns: list of specific domain concerns (empty list if none)
- critical: true if any concern is a hard blocker that would cause failure

Original request:
{request}"""


async def run_domain_review(
    client: OpenRouterClient,
    request: str,
    plan: PlanVerdict,
    summary: str,
    reviewers: list[Specialist],
    context: str = "",
) -> tuple[list[str], bool, list[ModelResponse]]:
    """Reviewers examine one implementation in parallel.

    Returns (concerns, any_critical, responses). A critical concern is the
    caller's cue to flip the implementation red; non-critical ones are recorded
    and passed to the validator.
    """
    if not reviewers:
        return [], False, []

    prompt = build_domain_review_prompt(request, plan, summary, context)
    responses: list[ModelResponse] = []

    async def _review(spec: Specialist) -> dict[str, Any]:
        data, resp = await spec.run(client, prompt)
        responses.append(resp)
        return data

    results = await asyncio.gather(*[_review(s) for s in reviewers])

    concerns: list[str] = []
    critical = False
    for result in results:
        concerns.extend(c for c in result.get("concerns", []) if isinstance(c, str))
        if result.get("critical"):
            critical = True
    return concerns, critical, responses


# Measured 006-D1(b): when a critical domain review flipped the implementation
# red, the entire feedback the next iteration received was the fixed sentence
# "Domain reviewer flagged critical concern". The concerns themselves were in
# hand at the mutation site and went onto a field nothing downstream read. One
# generic string cannot tell an implementer which of its choices was wrong, so
# the next attempt rewrote from the same information as the last one.
#
# Mechanical inclusion of what the reviewer already said. No new judgement, no
# summarising call — the strings are copied, joined and capped.
DOMAIN_CONCERN_BUDGET = 1200

# Measured §15.1: validate returns ONE red_cause while its `evidence` field
# already holds a verdict for every criterion, and only the red_cause reached
# the next attempt. With six criteria reported one at a time the loop played
# whack-a-mole — numeric_consistency went red twice naming a different criterion
# each round (cost-section arithmetic, then an unused burst duration) while the
# evidence for both was sitting in the failure log, recorded and unread. These
# budgets are generous because the lines are short by construction: validate is
# told at most 25 words per criterion.
EVIDENCE_BUDGET = 2000
REVIEW_FINDINGS_BUDGET = 2000


def _capped(lines: list[str], budget: int) -> tuple[str, int]:
    """Join what fits, and say how many did not rather than dropping them silently."""
    kept: list[str] = []
    used = 0
    for line in lines:
        if used + len(line) + 1 > budget and kept:
            break
        kept.append(line)
        used += len(line) + 1
    return "\n".join(kept), len(lines) - len(kept)


def render_validate_evidence(evidence: list[str]) -> str:
    """Every criterion validate judged, not just the one it named as the cause."""
    lines = [f"- {str(e).strip()}" for e in (evidence or []) if str(e).strip()]
    if not lines:
        return ""
    body, dropped = _capped(lines, EVIDENCE_BUDGET)
    tail = f"\n(+{dropped} further line(s) omitted for length)" if dropped else ""
    return f"""

VALIDATION FOUND, criterion by criterion — address EVERY failing one, not only
the cause named above:
{body}{tail}"""


def render_review_findings(findings: list[Any]) -> str:
    """What review blocked on, in review's own words."""
    lines: list[str] = []
    for f in findings or []:
        if isinstance(f, dict):
            sev = str(f.get("severity") or "").strip()
            lens = str(f.get("lens") or "").strip()
            detail = str(f.get("detail") or "").strip()
        else:
            sev = str(getattr(f, "severity", "") or "").strip()
            lens = str(getattr(f, "lens", "") or "").strip()
            detail = str(getattr(f, "detail", "") or "").strip()
        if not detail:
            continue
        label = "/".join(x for x in (sev, lens) if x)
        lines.append(f"- [{label}] {detail}" if label else f"- {detail}")
    if not lines:
        return ""
    body, dropped = _capped(lines, REVIEW_FINDINGS_BUDGET)
    tail = f"\n(+{dropped} further finding(s) omitted for length)" if dropped else ""
    return f"""

REVIEW BLOCKED THE PREVIOUS ATTEMPT on these findings — resolve each one:
{body}{tail}"""


def render_domain_concerns(concerns: list[str]) -> str:
    """The reviewer's own words, as the reason the implementation is red."""
    cleaned = [str(c).strip() for c in (concerns or []) if str(c).strip()]
    if not cleaned:
        return "Domain reviewer flagged critical concern"
    body = "; ".join(cleaned)
    if len(body) > DOMAIN_CONCERN_BUDGET:
        body = body[:DOMAIN_CONCERN_BUDGET].rsplit(" ", 1)[0] + " […]"
    return f"Domain reviewer flagged critical concern: {body}"


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
    evidence: list[str] | None = None,
    review_findings: list[Any] | None = None,
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
    # Mechanical inclusion of fields already recorded. No new judgement and no
    # extra call — the material was in the failure log the whole time.
    feedback += render_validate_evidence(evidence or [])
    feedback += render_review_findings(review_findings or [])

    feasibility_block = ""
    if plan.blockers:
        feasibility_block = f"""

FEASIBILITY CONCERNS (from domain specialist review — address these):
{chr(10).join(f'- {b}' for b in plan.blockers)}"""

    context_block = f"\n\nProject context:\n{context}" if context else ""
    # The blocked_on sentence below is RULED text (Blueprint 016 B2), carried
    # verbatim by instruction — it is the one judgment-steering sentence added
    # to this prompt, and it is not to be paraphrased. The blocked_on line in
    # the JSON contract is mechanical shape, like every other field's line.
    implement_prompt = f"""\
Produce the implementation for the following plan. This is iteration {iteration}.

{OUTPUT_CONTRACT}

Plan:
{plan.plan}

Success criteria:
{json.dumps(plan.success_criteria)}

If a criterion cannot be honestly satisfied with the grounding available, name it in blocked_on rather than producing something that satisfies it on paper.
{feasibility_block}
{feedback}
{context_block}

Return JSON with:
- done: true if the implementation is complete
- green: true if you believe it satisfies the success criteria
- red_cause: null if green, otherwise a short string describing what is wrong
- blocked_on: list of success criteria the work cannot satisfy, each entry
  naming the criterion (quote it or give its number) and why it cannot be
  satisfied; an empty list when there are none
- iteration: {iteration}
- summary: the implementation itself — the design, code, schema, procedure or
  calculation, in full. This field is the deliverable and is what the validate
  phase and every downstream reviewer will read, so write the work out rather
  than describing it in the abstract.

Original request:
{request}"""

    responses: list[ModelResponse] = []

    lead, reviewers = select_lead(specialists, primary_domain)

    # Step 1: Lead implements.
    #
    # The schema goes INTO the call, not just around the result. Without it a
    # reply missing one field was fatal on the first attempt, while every other
    # schema-bearing phase got three tries and a note saying what was rejected —
    # measured twice in one four-trace run (a verdict with no `green`, another
    # with no `done`), each killing a workflow outright. The post-reply
    # mutations below are unaffected: chat_json returns the parsed dict after
    # validating it, so validating in the retry and constructing afterwards are
    # the same two steps in the same order, exactly as run_validate does it.
    lead_data, lead_resp = await lead.run(
        client, implement_prompt, schema=ImplementVerdict,
    )
    responses.append(lead_resp)
    lead_data["iteration"] = iteration
    domain_concerns: list[str] = []

    # The verdict's green is resolved at construction, and this reads the raw
    # dict before that — so an omitted green would read as falsy here and skip
    # domain review entirely, which is the opposite of what an unqualified
    # reply should mean. Apply the same rule the verdict applies.
    if lead_data.get("green") is None:
        lead_data["green"] = not str(lead_data.get("red_cause") or "").strip()

    # Step 2: Domain review (only if the lead succeeded and there are reviewers)
    if lead_data.get("green") and reviewers:
        domain_concerns, critical, review_responses = await run_domain_review(
            client, request, plan, lead_data.get("summary", ""), reviewers, context
        )
        responses.extend(review_responses)
        if critical:
            lead_data["green"] = False
            lead_data["red_cause"] = render_domain_concerns(domain_concerns)

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
    max_tokens: int | None = None,
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
- evidence: one line per criterion, at most 25 words each, naming the criterion,
  the verdict, and the specific thing you saw. Not an essay — the finding is the
  value, and a long verdict costs as much to produce as the work it judges:
    "Backoff capped at 60s: PASS — step 2 sets max_interval=60"
    "Jitter applied per attempt: FAIL — step 2 sets a fixed delay, no jitter"

Original request:
{request}"""

    data, response = await test_eng.run(
        client, prompt, schema=ValidateVerdict,
        max_tokens=max_tokens or settings.validate_max_tokens,
    )
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
            # Normalise before reading a key off it. ReviewFinding accepts a
            # bare string, and a dict carrying its detail under any of eight
            # aliases — leniency added because a review using `issue` instead of
            # `detail` lost three whole reviews at the final phase. That
            # leniency was unreachable from here: `f.get("severity")` on a bare
            # string raises AttributeError *after* every reviewer has been paid,
            # so the shape the schema was widened to accept was the shape that
            # crashed the aggregation.
            try:
                finding = ReviewFinding.model_validate(f)
            except ValidationError:
                logger.warning("Unusable review finding from %s: %r", result, f)
                continue
            all_findings.append(finding.model_dump())
            if finding.severity in ("critical", "high"):
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
        function="independent",
        system_prompt=system_prompt,
        user_message=user_message,
        schema=DoubleCheckVerdict,
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
- Domains: {', '.join(domain_key(d) for d in triage.domains)}
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

    # The same bypass as implement, in the worst possible place: the longest and
    # messiest input in the system, read at the most expensive moment a run can
    # reach — after the loop has already burned every iteration it was given.
    # A malformed autopsy there lost the whole run and everything it had paid
    # for. Extras are safe to pass through: no verdict forbids them, and this
    # prompt asks for more than the verdict names.
    data, response = await client.chat_json(
        function="escalation",
        system_prompt=system_prompt,
        user_message=user_message,
        temperature=0.1,
        max_tokens=settings.escalation_max_tokens,
        schema=EscalationVerdict,
    )
    verdict = EscalationVerdict(**data)
    return verdict, response
