"""Phase implementations — triage, plan, implement, validate, review.

Each function takes a request context + OpenRouter client, calls the appropriate
specialist(s), and returns a typed verdict.
"""

from __future__ import annotations

import asyncio
import math
import json
import logging
from typing import Any

from pydantic import ValidationError

from autornd.config import settings
from autornd.graph.checks import dissent_anchored, quote_anchors
from autornd.models.verdicts import (
    AsksVerdict,
    BlockedOnAsk,
    DomainConcern,
    RED_NO_ANCHOR,
    UNANCHORED_DISSENT,
    UNVERIFIED_DISSENT,
    Ask,
    count_normalisation,
    dissent_kind,
    domain_key,
    Domain,
    DoubleCheckVerdict,
    EscalationVerdict,
    ImplementVerdict,
    PlanVerdict,
    RecomputeVerdict,
    ReviewFinding,
    ReviewVerdict,
    RiskLevel,
    SpecialistRole,
    TriageVerdict,
    role_key,
    ValidateVerdict,
)
from autornd.knowledge.context import build_phase_context
from autornd.routing.openrouter import BudgetExceeded, ModelResponse, OpenRouterClient
from autornd.specialists.base import Specialist
from autornd.specialists.registry import get_specialist, get_specialists

logger = logging.getLogger(__name__)


# AutoRnD's deliverable is the engineering artifact as text. Models have no
# repository, shell or build tools — and a model that answers "I cannot make
# changes" produces an empty implementation that validate then correctly
# rejects, burning the entire iteration budget and escalating a healthy
# request. Every producing prompt states this contract explicitly.
def output_contract() -> str:
    f = framing()
    return f"""\
You have no repository, file system, shell, or build tools, and you are not \
expected to. Nothing you write is executed or applied automatically.

Your response IS the deliverable. Produce the actual engineering work as text \
— the design, the code, the schema, the procedure, the calculation — in enough \
detail that a competent engineer could apply it directly. Never reply that you \
are unable to make changes or lack access: describing the work precisely is \
the task.""".replace("engineering work", f["work"]).replace(
    "the design, the code, the schema, the procedure, the calculation",
    f["deliverables"],
).replace("a competent engineer", f["competent_practitioner"])

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
# Ruling D51 rewrote this contract whole: the yardstick is the
# request's anchored asks, not the plan's criteria.
#
# Expect this to need live iterations, as the risk guide did four times over.
ASSESSMENT_CONTRACT = """\
You are assessing a written implementation, not a running system. You cannot \
execute code, run tests, or inspect a repository, and the absence of a live \
system is not itself a defect.

Judge whether the implementation as written answers each ask, correctly. Mark it \
red only for substantive problems: an ask it does not answer, an ask it answers \
wrongly, a logical error in what it states, or a contradiction with the request. \
Do not mark it red merely because the work has not been run.

Be exacting about the difference. "The request caps the delay at 60 s but the \
answer sets 600 s" is red. "I cannot confirm this without running it" is not — \
decide from the text in front of you and say what you found.

The asks are the contract you assess against, and they are fixed: they are the \
request's own words. You may not reinterpret, relax or add to an ask, and you may \
not accept work that changed one. Where the work and an ask disagree, that ask \
fails — whichever of the two looks more sensible to you. Judging the work against \
anything the request does not ask — a method you prefer, a check it did not \
request, a plan's own devices — is not an assessment: it is a note, and a note \
cannot make the work red."""


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
    from autornd.profiles import get_profile

    profile = get_profile()
    present = {role_key(s) for s in verdict.specialists}

    # B14: the rules are unchanged; their operands come from the profile.
    # Undeclared resolves to the shipped engineering role, so a profile that
    # says nothing behaves exactly as it did before.
    if verdict.risk in (RiskLevel.CRITICAL, RiskLevel.HIGH):
        checker = profile.role_that_checks_work()
        if checker not in present:
            # Appended as a normalised str, not as an enum member. The field is
            # list[str]; appending the enum after construction bypassed Pydantic
            # and left the verdict holding a mixed list (recorded unfixed since
            # §26, and explicitly deferred to this change).
            verdict.specialists.append(checker)
            present.add(checker)
    if len(verdict.domains) > 1:
        architect = profile.role_that_holds_system_view()
        if architect not in present:
            verdict.specialists.append(architect)
            present.add(architect)


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


def _ask_field(ask: Any, key: str) -> Any:
    """One field of an ask, whether it arrived as a dict or a model.

    The asks node's proposals are Ask models; the anchored asks that
    reach every judge are the check's dicts. Both carry the same two
    fields, and the prompts render either.
    """
    if isinstance(ask, dict):
        return ask.get(key)
    return getattr(ask, key, None)


def render_asks(asks: list[Any] | None) -> str:
    """The anchored asks, numbered from 1, one per line, each
    followed by its kind in brackets (Ruling D51 (1)).

    The fallback ask — the whole request as the one ask, when nothing
    the model proposed anchored — carries no kind: it is every kind at
    once, and a bracket would lie about which one it is.
    """
    lines: list[str] = []
    for i, ask in enumerate(asks or [], start=1):
        quote = str(_ask_field(ask, "quote") or "").strip()
        if not quote:
            continue
        kind = _ask_field(ask, "kind")
        kind = str(getattr(kind, "value", kind) or "").strip()
        lines.append(f"{i}. {quote}" + (f" [{kind}]" if kind else ""))
    if not lines:
        return "(none)"
    return "\n".join(lines)


async def run_triage(
    client: OpenRouterClient, request: str
) -> tuple[TriageVerdict, ModelResponse]:
    from autornd.profiles import framing, get_profile
    f = framing()
    profile = get_profile()
    domain_vocabulary = _domain_vocabulary()
    if domain_vocabulary:
        domains_block = (
            f"- domains: applicable domains. Prefer these: {domain_vocabulary}.\n"
            "  If none of them genuinely fits the subject, name the domain yourself in one or\n"
            "  two lowercase words rather than forcing the closest available label."
        )
    else:
        domains_block = (
            "- domains: applicable domains. Name each domain yourself in one or two\n"
            "  lowercase words."
        )
    specialists_vocabulary = _role_vocabulary()
    if specialists_vocabulary:
        specialists_block = (
            "- specialists: who to assign. A specialist is a person's function on the team,\n"
            "  not a subject — the subject goes in `domains`. Prefer these:\n"
            f"  {specialists_vocabulary}. If none of them covers the function this work needs,\n"
            "  name the role in one or two lowercase words."
        )
    else:
        specialists_block = (
            "- specialists: who to assign. A specialist is a person's function on the team,\n"
            "  not a subject — the subject goes in `domains`. Name each role yourself in\n"
            "  one or two lowercase words."
        )
    prompt = f"""\
Classify this {f['request_kind']}. Return JSON with:
- domains: {domains_block}
- risk: one of [{', '.join(r.value for r in RiskLevel)}]
- specialists: {specialists_block}
- unrecallable: true when a wrong answer cannot be taken back once released —
  {f['unrecallable_examples']}. Scale alone is
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

Always include {profile.role_that_checks_work()} for high/critical risk.
Always include {profile.role_that_holds_system_view()} for multi-domain requests.

Request:
{request}"""

    data, response = await client.chat_json(
        function="triage",
        system_prompt=f"You are a triage classifier for {f['team']}. Respond with JSON only.",
        user_message=prompt,
       schema=TriageVerdict,
    )
    verdict = TriageVerdict(**data)
    enforce_triage_composition(verdict)
    return verdict, response


async def run_asks(
    client: OpenRouterClient,
    request: str,
    max_tokens: int | None = None,
) -> tuple[AsksVerdict, ModelResponse]:
    """The asks node (Ruling D51 (1), text (R-a)).

    A model on the triage tier proposes the request's asks as verbatim
    quotes, each with its kind. The anchoring is NOT this phase's job:
    the free check `asks_anchored` keeps a quote only if it occurs in
    the request, and the anchored asks are the run's only success
    criteria. Quoting is what a cheap model is good at; anchoring is
    what a substring check cannot get wrong.
    """
    from autornd.profiles import framing, get_profile
    f = framing()
    profile = get_profile()
    prompt = f"""\
List what this request asks the answer to give or to satisfy.

Each ask is a verbatim quote of the request: copy its words exactly, without paraphrase, so that the quote can be found in the request as written. Give one ask per entry — one value, verdict, step, constraint or format — with its kind:
- value: a figure, quantity or selection the answer must state
- verdict: a judgement the answer must reach
- step: an action the answer must include, in the order the request gives it
- constraint: a condition the answer must respect, such as a limit, tolerance, rule or prohibition
- format: a form the request asks the answer to take, such as a sign convention, a unit or a list

Quote only what the request says. Do not add checks, deliverables, methods or presentation the request does not ask for. Do not list the data the request supplies — given values, readings, dimensions — unless the request asks the answer to state them or to use them in a stated way.

Return JSON: {{"asks": [{{"quote": "...", "kind": "value"}}]}}

Request:
{request}"""

    data, response = await client.chat_json(
        function="triage",
        system_prompt=f"You are {f['request_analyst']}. Respond with JSON only.",
        user_message=prompt,
        schema=AsksVerdict,
    )
    verdict = AsksVerdict(**data)
    return verdict, response


async def run_plan(
    client: OpenRouterClient,
    request: str,
    triage: TriageVerdict,
    specialists: list[Specialist],
    tier: str | None = None,
    context: str | None = None,
    max_tokens: int | None = None,
    asks: list[Any] | None = None,
) -> tuple[PlanVerdict, ModelResponse]:
    from autornd.profiles import framing, get_profile
    f = framing()
    profile = get_profile()
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
Create an implementation plan for this {f['request_kind']}.

{output_contract()}

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

Rules for the plan (each measured 2026-09-30, each a loop-killer when broken):

1. DERIVE FROM DEMAND, NEVER FROM THE CEILING. Size from workload
   (Little's Law: concurrency = throughput x duration; budget divided by
   workers with the remainder named) — never by dividing a server cap. A
   plan that bakes the cap into the answer fails review and blocks the
   run. Show every derivation inline with the arithmetic, not just the
   result.

2. UNKNOWN IS A BLOCKER, NOT AN ASSUMPTION. If a load-bearing input is
   missing (topology, current settings, reserves, durations), name it in
   blockers and set ready: false — do not stipulate it and derive on top
   of it. If you must proceed conditionally, label each assumption with
   a kill trigger (e.g. "if 2 GiB is shared, 24 x 780 MiB oversubscribes
   9x: stop and re-plan") so feasibility can test it instead of
   discovering it.

3. ONE NUMBER EVERYWHERE. Every figure that appears in more than one
   section (rates, counts, sizes, costs, thresholds) must agree exactly —
   state the canonical value once, reference it elsewhere. A plan whose
   sections disagree with each other is internally refuted.

4. NAME THE FALSIFIER. State the single metric, with threshold and
   window, that proves the sizing wrong if it fires (e.g. p99
   checkout-wait over 250 ms sustained, or wait-queue depth above zero
   for 60 s). A plan with no disprovable claim cannot be validated.

You do not write the test this work is judged by. The request is that test, and the asks quoted from it are listed below: every later judgment is made against them and nothing else. Plan how to answer them. The four rules above govern how you reason; they add nothing to what the answer must contain.

The asks, quoted from the request:
{render_asks(asks)}

Request:
{request}"""

    architect = get_specialist(SpecialistRole.SYSTEMS_ARCHITECT)
    data, response = await client.chat_json(
        function="architecture",
        system_prompt=architect.system_prompt,
        user_message=prompt,
        max_tokens=max_tokens or settings.plan_max_tokens,
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
) -> tuple[list[ModelResponse], list[str]]:
    """Domain specialists review the architect's plan for feasibility.

    Each specialist checks the plan against the constraints of their own
    domain. Returns (responses for cost tracking, the hard blockers the
    reviewers named) — Ruling D46 (2): the concerns are this phase's own
    output now; the plan's blockers stay the architect's.
    """
    from autornd.profiles import framing, get_profile
    f = framing()
    profile = get_profile()
    architect_role = SpecialistRole.SYSTEMS_ARCHITECT
    reviewers = [s for s in specialists if s.role != architect_role]
    if not reviewers:
        return [], []

    context_block = f"\n\nProject context:\n{context}" if context else ""
    bom_block = (
        f"Cost estimate (USD): {plan.cost_estimate}\n\n"
        if plan.cost_estimate is not None else ""
    )
    prompt = f"""\
Review this implementation plan from your specialist perspective for feasibility.
{context_block}

Plan produced by {get_specialist(get_profile().role_that_holds_system_view()).name}:
{plan.plan}

{bom_block}Return JSON with:
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

    # Ruling D46 (2): feasibility runs after the plan gate and cannot stop a
    # run, so its concerns no longer write plan.blockers — where they were
    # misrecorded as the architect's and could never gate anything. They
    # travel in feasibility's own output and reach the implementer as
    # considerations a reviewer raised, not requirements.
    return responses, all_blockers


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
    request: str, summary: str, asks: list[Any] | None = None,
    context: str = "",
) -> str:
    context_block = f"\n\nProject context:\n{context}" if context else ""
    return f"""\
Review this implementation from your domain perspective. Do NOT produce an alternative design.

{ASSESSMENT_CONTRACT}
{context_block}

Implementation summary:
{summary}

The asks, quoted from the request:
{render_asks(asks)}

Judge the answer against the request from your domain. A concern can be critical only if it is anchored:
- it names the ask it concerns, by number, and what the answer states or omits against it; or
- it quotes the request's own words, exactly, for something the answer gets wrong or leaves out; or
- it is a hazard: something the answer states or instructs that would, if followed as written, injure a person or damage equipment. Quote those words of the answer.
If the answer gives something for an ask and you say it is false, set kind: wrong_fact and quote, in source_quote, the words of the request or of the provided sources that show it is false. If you cannot quote them, it is a note.
An omission is never a hazard. If the request asked for what is missing, quote the request; if it did not, it is a note, and a note is never critical.

Return JSON with:
- concerns: list of objects, each with:
  - detail: the concern
  - ask: the number of the ask the concern names, when it names one
  - quote: the request's own words, verbatim, when the concern is anchored by them
  - hazard: true only when the concern is a hazard
  - hazard_quote: when hazard is true, the answer's own words that state or instruct it, verbatim
  - kind: the concern's kind — unmet_ask (the answer gives nothing for the ask), wrong_fact (the answer gives something for the ask and you say it is false), or hazard
  - source_quote: for wrong_fact, the request's or the sources' own words that contradict the answer, verbatim
  - critical: true only when the concern is anchored and blocks the work
- critical: true if any concern is a hard blocker that would cause failure

Original request:
{request}"""


async def run_domain_review(
    client: OpenRouterClient,
    request: str,
    summary: str,
    reviewers: list[Specialist],
    context: str = "",
    function: str | None = None,
    asks: list[Any] | None = None,
) -> tuple[list[DomainConcern], bool, list[ModelResponse]]:
    """Reviewers examine one implementation in parallel.

    Returns (concerns, any_critical, responses). A critical concern is the
    caller's cue to flip the implementation red; non-critical ones are recorded
    and passed to the validator.

    Ruling D51 (3), text (R-f): a concern is critical only if it is
    anchored — it names the ask by number, quotes the request's own
    words, or is a hazard. An unanchored critical concern is demoted
    to a note before the caller sees it: counted, kept in the returned
    list at critical=false, never the reason the work goes red.
    """
    if not reviewers:
        return [], False, []

    prompt = build_domain_review_prompt(request, summary, asks, context)
    responses: list[ModelResponse] = []

    async def _review(spec: Specialist) -> dict[str, Any]:
        data, resp = await spec.run(client, prompt, function=function)
        responses.append(resp)
        return data

    results = await asyncio.gather(*[_review(s) for s in reviewers])

    concerns: list[DomainConcern] = []
    critical = False
    for result in results:
        for raw in result.get("concerns", []):
            try:
                concern = DomainConcern.model_validate(raw)
            except ValidationError:
                logger.warning(
                    "Unusable domain concern from a reviewer: %r", raw)
                continue
            if concern.critical and not dissent_anchored(
                    concern.ask, concern.quote, concern.hazard,
                    asks, request, summary, concern.hazard_quote,
                    concern.kind, concern.source_quote, context):
                # A note, never critical — a judgment that names no
                # anchor carries no information about the request
                # (convention 21). R2 (2026-10-15): a wrong_fact
                # that shows no source is an unverified dissent —
                # the run cannot check the claim, so under D51 (5)
                # it is unavailable — and counts as its own kind.
                if dissent_kind(concern.kind, concern.hazard) == "wrong_fact":
                    count_normalisation(UNVERIFIED_DISSENT)
                else:
                    count_normalisation(UNANCHORED_DISSENT)
                concern.critical = False
            concerns.append(concern)
            if concern.critical:
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
# Ruling D21 (2026-09-25): recovery must carry the failure forward. The
# recovery implement attempt receives the previous iteration's unmet criteria
# quoted, so it knows what stayed unsatisfied rather than rediscovering it.
# Same budget as the evidence and findings channels — the lines are criteria,
# short by construction.
UNMET_CRITERIA_BUDGET = 2000


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


def render_domain_concerns(concerns: list[DomainConcern]) -> str:
    """The reviewer's own words, as the reason the implementation is red."""
    cleaned = [str(c.detail).strip() for c in (concerns or [])
               if str(c.detail).strip()]
    if not cleaned:
        return "Domain reviewer flagged critical concern"
    body = "; ".join(cleaned)
    if len(body) > DOMAIN_CONCERN_BUDGET:
        body = body[:DOMAIN_CONCERN_BUDGET].rsplit(" ", 1)[0] + " […]"
    return f"Domain reviewer flagged critical concern: {body}"


def render_unmet_criteria(missed: list[str]) -> str:
    """Ruling D21: the previous iteration's unmet criteria, quoted verbatim.

    MEASURED, not assessed — these are the presence test's own output
    (`coverage.missed`), carried forward so the recovery attempt knows what
    stayed unsatisfied rather than rediscovering it one criterion at a time.
    Empty when nothing is recorded as missed, so build-loop iterations (no
    prior failure) and runs without a coverage node read no new text.
    """
    lines = [f"- '{str(m).strip()}'" for m in (missed or []) if str(m).strip()]
    if not lines:
        return ""
    body, dropped = _capped(lines, UNMET_CRITERIA_BUDGET)
    tail = f"\n(+{dropped} further criteri(on/a) omitted for length)" if dropped else ""
    return f"""

THE PREVIOUS ATTEMPT LEFT THESE SUCCESS CRITERIA UNMET — satisfy each one:
{body}{tail}"""


async def run_implement(
    client: OpenRouterClient,
    request: str,
    plan: PlanVerdict | None,
    specialists: list[Specialist],
    iteration: int,
    red_cause: str | None = None,
    resolution_directive: str | None = None,
    context: str = "",
    primary_domain: Domain | None = None,
    evidence: list[str] | None = None,
    review_findings: list[Any] | None = None,
    unmet_criteria: list[str] | None = None,
    prior_summary: str | None = None,
    considerations: list[str] | None = None,
    max_tokens: int | None = None,
    asks: list[Any] | None = None,
    results: bool = False,
) -> tuple[ImplementVerdict, list[ModelResponse]]:
    from autornd.profiles import framing, get_profile
    f = framing()
    profile = get_profile()
    # Ruling D33: on every iteration after the first, implement REVISES its own
    # prior artifact rather than regenerating from the plan. The fixer must see
    # the artifact that contains the failure it is told to fix — the diagnosis
    # ("kappa=17.99 against your threshold 17") is unactionable when the artifact
    # holding that value is not in the prompt, and a blind regenerate re-rolls
    # the consistency dice. The instruction changes from produce to revise, and
    # is explicit about preserving what passed, not only fixing what failed —
    # a model told to produce regenerates regardless of what it is shown.
    feedback = ""
    if prior_summary:
        feedback += f"""

REVISION TASK — you are editing your previous implementation, not writing a new one. It is reproduced verbatim below. Preserve every part that the success criteria judged correct; change ONLY what the diagnosis and the unmet criteria require. Do not regenerate the work from the plan.

YOUR PREVIOUS IMPLEMENTATION (revise this):
{prior_summary}"""
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
    feedback += render_unmet_criteria(unmet_criteria or [])
    feedback += render_validate_evidence(evidence or [])
    feedback += render_review_findings(review_findings or [])

    # Ruling D48 (2): the plan's own blockers did not stop the plan gate, so
    # they are not requirements either — but 111 dropped them from the prompt
    # entirely (106's IA unit carried five of them). They arrive under their
    # own heading, before the reviewers' considerations and framed the same
    # way: weigh them; nothing is judged against them. Feasibility's concerns
    # never appear here, and these never appear there.
    open_points_block = ""
    if plan and plan.blockers:
        open_points_block = f"""

OPEN POINTS THE PLAN ITSELF NAMED (the plan passed its gate with these; not requirements — weigh them; nothing is judged against them):
{chr(10).join(f'- {b}' for b in plan.blockers)}"""

    # Ruling D46 (2): feasibility's concerns are a reviewer's considerations
    # now. The old heading — "FEASIBILITY CONCERNS (from domain specialist
    # review — address these):" — was a requirements channel opening after
    # D43 closed the plan's scope: "address these" made them demands. This
    # heading says what they are and what they are not.
    feasibility_block = ""
    if considerations:
        feasibility_block = f"""

CONSIDERATIONS A REVIEWER RAISED (not requirements — weigh them; nothing is judged against them):
{chr(10).join(f'- {b}' for b in considerations)}"""

    context_block = f"\n\nProject context:\n{context}" if context else ""
    # Ruling D33: produce on the first pass, revise once a prior artifact exists.
    # Iteration 1 has no prior_summary, so this line is byte-identical to the
    # pre-ruling prompt.
    #
    # Ruling D51 (8): under verify-first there is no plan, so the
    # task names the request, and the 'Plan:' section below is
    # omitted — the asks are the whole yardstick.
    if prior_summary:
        task_line = (
            "Revise your previous implementation for the following "
            + ("plan (reproduced below)." if plan
               else "request (reproduced below).")
        )
    elif plan:
        task_line = "Produce the implementation for the following plan."
    else:
        task_line = "Produce the answer to the following request."
    # The plan section exists only when a plan exists. Under
    # verify-first (D51 (8)) it is omitted: the request and its
    # asks are the whole input.
    plan_block = (
        f"\nPlan:\n{plan.plan}\n" if plan else ""
    )
    # Ruling D53: the answer-and-recompute workflow's implement node
    # states its results as typed values, so the recompute vote can
    # compare the answer against blind recomputation field by field.
    # The instruction is gated on the node's args (args: {results: true}
    # in workflows/answer-and-recompute.yaml): every other workflow's
    # implement prompt is byte-identical to what it was without it.
    results_instruction = ""
    if results:
        results_instruction = (
            "In results, give one entry for each ask of kind value or "
            "verdict listed above: ask = its number, value = the final "
            "number or the identifier you chose, unit = the unit of the "
            "number (empty for an identifier). These are the values your "
            "summary states.")
    # The blocked_on sentence below is RULED text (Ruling D51 (h),
    # replacing Blueprint 016 B2's sentence by this ruling) — it is
    # carried verbatim by instruction and is not to be paraphrased.
    # The blocked_on line in the JSON contract is mechanical shape,
    # like every other field's line.
    implement_prompt = f"""\
{task_line} This is iteration {iteration}.

{output_contract()}
{plan_block}
The asks, quoted from the request — the answer is judged against these and nothing else:
{render_asks(asks)}
{results_instruction}
If an ask cannot be honestly answered with the grounding available, name it by its number in blocked_on rather than producing something that answers it on paper.
Answer the request, and include the plan's falsifiers, kill triggers or assumption tables only if the request asks for them.
{open_points_block}{feasibility_block}
{feedback}
{context_block}

Return JSON with:
- reasoning: fill this FIRST, before every other field. Think step by step here — how you will satisfy each ask, and, critically, verify that every numeric value you will state agrees with every threshold, bound and other value in the deliverable (the failure this guards against is a value that violates a limit the same deliverable sets, e.g. a computed figure exceeding a stated threshold). If a previous implementation is shown above, state exactly what was inconsistent, why its logic was wrong, and the specific change you will make to fix it WITHOUT breaking what already passed. This field is a private scratchpad: it is not the deliverable and is not read downstream.
- done: true if the implementation is complete
- green: true if you believe it satisfies the asks
- red_cause: null if green, otherwise a short string describing what is wrong
- blocked_on: list of asks the work cannot honestly answer, each entry
  naming the ask (its number or its quote) and why it cannot be
  answered; an empty list when there are none
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
        max_tokens=max_tokens or settings.plan_max_tokens,
    )
    responses.append(lead_resp)
    lead_data["iteration"] = iteration
    domain_concerns: list[DomainConcern] = []

    # The verdict's green is resolved at construction, and this reads the raw
    # dict before that — so an omitted green would read as falsy here and skip
    # domain review entirely, which is the opposite of what an unqualified
    # reply should mean. Apply the same rule the verdict applies.
    if lead_data.get("green") is None:
        lead_data["green"] = not str(lead_data.get("red_cause") or "").strip()

    # Step 2: Domain review (only if the lead succeeded and there are reviewers)
    if lead_data.get("green") and reviewers:
        domain_concerns, critical, review_responses = await run_domain_review(
            client, request, lead_data.get("summary", ""), reviewers,
            context, asks=asks,
        )
        responses.extend(review_responses)
        if critical:
            lead_data["green"] = False
            lead_data["red_cause"] = render_domain_concerns(domain_concerns)

    lead_data["domain_concerns"] = domain_concerns
    verdict = ImplementVerdict(**lead_data)

    # Ruling D51, THE FOLD: the implementer's own red counts only
    # when it names an ask — a blocked_on entry that names one,
    # by number or by an anchored quote — or when an anchored
    # critical domain concern flipped it (R-f): after the domain
    # review's own demotion, a concern still critical IS anchored.
    # Any other red is a note: counted, never blocking, and not
    # sent to the next revision. The judges, not the implementer,
    # decide whether the work fails; the raw reply still carries
    # the implementer's own words for the record.
    if not verdict.green and not any(
            c.critical for c in verdict.domain_concerns) and not any(
            b.ask is not None
            or (bool(str(b.quote).strip())
                and quote_anchors(str(b.quote), request))
            for b in verdict.blocked_on):
        count_normalisation(UNANCHORED_DISSENT)
        verdict.green = True
        verdict.red_cause = None
    return verdict, responses


def _render_recompute_asks(asks: list[Any] | None) -> str:
    """The anchored asks of kind value and verdict, at their own
    numbers (Ruling D53).

    The numbers the answer's results use — the anchored asks'
    own — not a renumbered list: a result naming ask 4 names
    ask 4 whether or not the asks before it were of another
    kind. Step, constraint and format asks are left out: the
    recompute computes values and verdicts, and the vote
    compares what it can state.
    """
    lines: list[str] = []
    for ask in asks or []:
        kind = _ask_field(ask, "kind")
        kind = str(getattr(kind, "value", kind) or "").strip().lower()
        if kind not in ("value", "verdict"):
            continue
        quote = str(_ask_field(ask, "quote") or "").strip()
        if not quote:
            continue
        lines.append(f"{_ask_field(ask, 'number')}. {quote} [{kind}]")
    return "\n".join(lines)


async def run_recompute(
    client: OpenRouterClient,
    request: str,
    context: str = "",
    asks: list[Any] | None = None,
    max_tokens: int | None = None,
    samples: int = 3,
) -> tuple[dict[str, Any], list[ModelResponse]]:
    """The recompute node (Ruling D53): blind recomputation.

    `samples` separate calls on the recompute tier, each one
    recomputing the anchored asks of kind value and verdict from
    the request and the grounding alone. Isolation is structural,
    not enforced: the prompt is built from the request, the
    context and the asks, and nothing else — no sample sees the
    answer, its results, the plan or another sample's output,
    because none of them is an input to this phase. The vote is
    the check downstream; this phase only computes.

    Each call goes through the client's reservation path like
    every other call (D45, D47): its worst case is reserved
    before dispatch and released by its own identity on
    reconciliation, so three samples reserve three worst cases.
    """
    from autornd.profiles import framing, get_profile
    f = framing()
    profile = get_profile()
    context_block = f"\n\nProject context:\n{context}" if context else ""
    prompt = f"""\
{request}{context_block}

The asks, quoted from the request — compute each one yourself:
{_render_recompute_asks(asks)}

Compute the answer yourself. Return JSON with results: one entry per listed ask, {{"ask": its number, "value": your final number or the identifier you chose, "unit": the unit of the number, empty for an identifier}}."""

    responses: list[ModelResponse] = []
    sample_results: list[dict[str, Any]] = []
    for _ in range(samples):
        data, response = await client.chat_json(
            function="recompute",
            system_prompt=f"You are {f['senior_practitioner']}.",
            user_message=prompt,
            schema=RecomputeVerdict,
            max_tokens=max_tokens or settings.recompute_max_tokens,
        )
        responses.append(response)
        sample_results.append(dict(data))
    return ({"skipped": False, "reason": "",
             "samples": sample_results}, responses)


async def run_validate(
    client: OpenRouterClient,
    request: str,
    implement: ImplementVerdict,
    context: str = "",
    domains: list[Domain] | None = None,
    max_tokens: int | None = None,
    function: str | None = None,
    asks: list[Any] | None = None,
) -> tuple[ValidateVerdict, ModelResponse]:
    test_eng = get_specialist(SpecialistRole.TEST_ENGINEER)
    from autornd.profiles import framing, get_profile
    f = framing()
    profile = get_profile()
    context_block = f"\n\nProject context:\n{context}" if context else ""
    checks_block = build_domain_checks(domains or [])
    concerns_block = ""
    if implement.domain_concerns:
        concerns_block = f"""

DOMAIN REVIEW CONCERNS (flagged by specialist reviewers — verify these):
{chr(10).join(f'- {c.detail}' for c in implement.domain_concerns)}"""

    prompt = f"""\
Validate this implementation against the asks.

{ASSESSMENT_CONTRACT}
{context_block}

The asks, quoted from the request:
{render_asks(asks)}

Implementation summary (iteration {implement.iteration}):
{implement.summary}
{concerns_block}

The asks below are quoted from the request and numbered. Judge the answer against each ask in turn, and against nothing else.

For each ask, decide:
- pass: the answer gives or satisfies it, correctly;
- fail: the answer states something wrong for it, or leaves it out — name the ask's number and what the answer states or omits;
- unavailable: deciding it needs something you do not have, such as a source text, a measurement or an execution. Judge what the answer states as far as you can and say what you could not check. Unavailable is not a failure.

Where the arithmetic is present, do it and show it. If the answer gets wrong, or leaves out, something the request asks for that the list lacks, quote the request's own words for it, exactly: that counts as a failed ask. Anything else you notice is a note for evidence; it cannot make this red.
If the answer gives something for an ask and you say it is false, set kind: wrong_fact and quote, in source_quote, the words of the request or of the provided sources that show it is false. If you cannot quote them, it is a note.
{checks_block}

Return JSON with:
- green: true if every ask is satisfied
- red_cause: null if green, otherwise the specific failure cause
- failed_ask: the number of the ask the work fails, when the failure is one ask's
- anchor_quote: the request's own words, verbatim, for what the answer gets wrong or leaves out, when the failure is not one ask's number
- hazard: true only when the answer states or instructs something that would, followed as written, injure a person or damage equipment
- hazard_quote: when hazard is true, the answer's own words that state or instruct it, verbatim
- kind: the dissent's kind — unmet_ask (the answer gives nothing for the ask), wrong_fact (the answer gives something for the ask and you say it is false), or hazard
- source_quote: for wrong_fact, the request's or the sources' own words that contradict the answer, verbatim
- unavailable_asks: numbers of the asks whose verification needs something you do not have — a source text, a measurement or an execution. Unavailable is neither pass nor fail, and never blocks
- evidence: one line per ask, at most 25 words each, naming the ask,
  the verdict, and the specific thing you saw. Not an essay — the finding is the
  value, and a long verdict costs as much to produce as the work it judges:
    "Backoff capped at 60s: PASS — the answer sets max_interval=60"
    "Jitter applied per attempt: FAIL — the answer sets a fixed delay, no jitter"

Original request:
{request}"""

    data, response = await test_eng.run(
        client, prompt, schema=ValidateVerdict,
        max_tokens=max_tokens or settings.validate_max_tokens,
        function=function,
    )
    # Ruling D51 (3), text (R-d): validate is red only when it
    # names a failed ask — the ask's number, the request's own
    # quoted words, or a hazard. A red that names no anchor is a
    # note: counted, never blocking, and not sent to the next
    # revision. The demotion happens before construction, because
    # construction would resolve a red_cause into green=false.
    wants_red = (data.get("green") is False
                 or bool(str(data.get("red_cause") or "").strip()))
    if wants_red and not dissent_anchored(
            data.get("failed_ask"), data.get("anchor_quote"),
            data.get("hazard"), asks, request,
            implement.summary, data.get("hazard_quote"),
            data.get("kind"), data.get("source_quote"), context):
        # R2 (2026-10-15): a wrong_fact red that shows no
        # source is an unverified dissent — the run cannot
        # check the claim, so under D51 (5) it is
        # unavailable — and counts as its own kind.
        if dissent_kind(data.get("kind"), bool(data.get("hazard"))) == "wrong_fact":
            count_normalisation(UNVERIFIED_DISSENT)
        else:
            count_normalisation(RED_NO_ANCHOR)
        data["green"] = True
        data["red_cause"] = None
    verdict = ValidateVerdict(**data)
    return verdict, response


async def run_review(
    client: OpenRouterClient,
    request: str,
    triage: TriageVerdict,
    implement: ImplementVerdict,
    specialists: list[Specialist],
    context: str = "",
    max_tokens: int | None = None,
    function: str | None = None,
    asks: list[Any] | None = None,
) -> tuple[ReviewVerdict, list[ModelResponse]]:
    from autornd.profiles import framing, get_profile
    f = framing()
    profile = get_profile()
    adversarial = triage.risk in (RiskLevel.CRITICAL, RiskLevel.HIGH)
    review_mode = "ADVERSARIAL — actively search for failure modes" if adversarial else "COLLABORATIVE"
    context_block = f"\n\nProject context:\n{context}" if context else ""

    prompt = f"""\
Review this {f['work']} from your specialist lens.

{ASSESSMENT_CONTRACT}
{context_block}

Review mode: {review_mode}
Risk level: {triage.risk.value}

The asks, quoted from the request:
{render_asks(asks)}

Judge the answer against the request. A finding can block only if it is anchored:
- it names the ask it concerns, by number, and what the answer states or omits against it; or
- it quotes the request's own words, exactly, for something the answer gets wrong or leaves out; or
- it is a hazard: something the answer states or instructs that would, if followed as written, injure a person or damage equipment. Quote those words of the answer.
If the answer gives something for an ask and you say it is false, set kind: wrong_fact and quote, in source_quote, the words of the request or of the provided sources that show it is false. If you cannot quote them, it is a note.
An omission is never a hazard. If the request asked for what is missing, quote the request; if it did not, it is a note.
Use severity critical or high only for an anchored finding. Everything else is a note, at severity medium or low, and cannot block.

Implementation summary:
{implement.summary}

Return JSON with:
- findings: list of objects, each with:
  - lens: your specialist role (e.g. "{f['role_example']}")
  - severity: one of [critical, high, medium, low]
  - detail: specific finding
  - ask: the number of the ask the finding concerns, when it names one
  - quote: the request's own words, verbatim, when the finding is anchored by them
  - hazard: true only when the finding is a hazard
  - hazard_quote: when hazard is true, the answer's own words that state or instruct it, verbatim
  - kind: the finding's kind — unmet_ask (the answer gives nothing for the ask), wrong_fact (the answer gives something for the ask and you say it is false), or hazard
  - source_quote: for wrong_fact, the request's or the sources' own words that contradict the answer, verbatim
- ship: true if safe to ship with no blocking findings
- verdict: one-sentence synthesis

{"Search for failure modes. What breaks under load, at the boundaries, on partial failure, or when an assumption the answer makes turns out to be false?" if adversarial else "Focus on correctness and completeness."}

Original request:
{request}"""

    responses: list[ModelResponse] = []
    all_findings: list[dict[str, Any]] = []
    any_blocking = False
    # Ruling D42: a reviewer that fails is not a finding. It is retried once;
    # a second failure is recorded here, with its class, and never enters the
    # findings or the blocking decision.
    not_reviewed: list[dict[str, str]] = []

    async def _review(spec: Specialist) -> dict[str, Any] | None:
        for attempt in (1, 2):
            try:
                data, resp = await spec.run(
                    client, prompt,
                    max_tokens=max_tokens or settings.plan_max_tokens,
                    function=function,
                )
                responses.append(resp)
                return data
            except BudgetExceeded:
                # A spend stop is the run's terminal, not a reviewer failure,
                # and a retry would spend past the cap. 102's Q2: the run
                # crossed its ceiling mid-review, and this handler's former
                # `except Exception` turned that into a 'high' finding that
                # refused a correct answer.
                raise
            except Exception as exc:
                logger.exception("Specialist %s failed during review (attempt %d)",
                                 spec.name, attempt)
                if attempt == 2:
                    not_reviewed.append({"specialist": spec.name,
                                         "failure_class": type(exc).__name__})
        return None

    results = await asyncio.gather(*[_review(s) for s in specialists])
    successful = [r for r in results if r is not None]
    # D42's quorum: at least half the assigned reviewers, rounded up.
    quorum = math.ceil(len(specialists) / 2)
    quorate = len(successful) >= quorum

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
            # Ruling D51 (3), text (R-e): a finding blocks only
            # when it is critical or high AND anchored — it names
            # the ask by number, quotes the request's own words,
            # or is a hazard. An unanchored critical or high
            # finding is demoted to a note at severity medium
            # before the blocking decision: counted, kept in the
            # record, never blocking.
            if finding.severity in ("critical", "high") and not dissent_anchored(
                    finding.ask, finding.quote, finding.hazard,
                    asks, request, implement.summary,
                    finding.hazard_quote, finding.kind,
                    finding.source_quote, context):
                # R2 (2026-10-15): a wrong_fact that
                # shows no source is an unverified
                # dissent — the run cannot check the
                # claim, so under D51 (5) it is
                # unavailable — and counts as its own
                # kind.
                if dissent_kind(finding.kind, finding.hazard) == "wrong_fact":
                    count_normalisation(UNVERIFIED_DISSENT)
                else:
                    count_normalisation(UNANCHORED_DISSENT)
                finding.severity = "medium"
            all_findings.append(finding.model_dump())
            if finding.severity in ("critical", "high"):
                any_blocking = True

    # Ruling D51, THE FOLD: the blocking decision rests on the
    # anchored findings alone. A reviewer's own `ship: false`
    # with no anchored finding is an unanchored judgment — a
    # note, never blocking — so the raw field is not a channel
    # into the verdict's ship.
    ship = quorate and not any_blocking

    verdicts_text = " | ".join(r.get("verdict", "") for r in successful)
    who = ", ".join(f"{n['specialist']} ({n['failure_class']})" for n in not_reviewed)
    if not quorate:
        synthesis = (f"Blocked. The review did not complete: {len(successful)} of "
                     f"{len(specialists)} reviewers completed, below the quorum of "
                     f"{quorum}; not reviewed: {who}. {verdicts_text}").strip()
    elif ship:
        synthesis = f"Ship. {verdicts_text}"
    else:
        synthesis = f"Blocked. {verdicts_text}"
    if not_reviewed and quorate:
        synthesis += f" | not reviewed: {who}"

    findings = [ReviewFinding(**f) for f in all_findings]
    verdict = ReviewVerdict(ship=ship, findings=findings, verdict=synthesis,
                            not_reviewed=not_reviewed,
                            reviewers_assigned=len(specialists),
                            reviewers_completed=len(successful))
    return verdict, responses


async def run_doublecheck(
    client: OpenRouterClient,
    request: str,
    implement: ImplementVerdict,
    context: str = "",
    asks: list[Any] | None = None,
) -> tuple[DoubleCheckVerdict, ModelResponse]:
    from autornd.profiles import framing, get_profile
    f = framing()
    profile = get_profile()
    context_block = f"\n\nProject context:\n{context}" if context else ""
    system_prompt = (
        f"You are {f['independent_reviewer']}. "
        "You have NOT seen any previous review of this work. "
        "Evaluate this implementation for correctness, safety, and completeness. "
        "Be thorough and adversarial — look for failure modes, edge cases, and spec violations."
    )
    user_message = f"""\
Review this {f['implementation']} independently.

{ASSESSMENT_CONTRACT}
{context_block}

The asks, quoted from the request:
{render_asks(asks)}

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
Direct, do not produce: the directive names what the implementer must do, never
the implementation itself — an autopsy that delivers the work bypasses the
validation the work still has to pass.

Before you direct anything, rule on each open dissent in the failure log: does it hold against its anchor — the ask, or the request's quoted words — reading the answer as written? A dissent that judges the answer against something the request does not ask does not hold. Your directive addresses only the upheld dissents. If none is upheld, say so in root_cause_analysis and direct the implementer to keep the answer as it is.

You MUST respond with a JSON object containing exactly these fields:
{{
  "root_cause_analysis": "The fundamental logic or architectural flaw causing the consecutive failures. Conclusion only, no reasoning steps.",
  "architectural_correction": "Corrected logic or missing dependencies if the original plan was flawed. null if plan was sound.",
  "resolution_directive": "Specific, step-by-step instructions for the Implementation model to succeed on its next attempt.",
  "requires_human": false,
  "rulings": [{{"dissent": <number>, "upheld": true, "reason": "<one line>"}}]
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
    asks: list[Any] | None = None,
) -> tuple[EscalationVerdict, ModelResponse]:
    system_prompt = ESCALATION_SYSTEM_PROMPT.format(n=len(failure_log))
    context_block = f"\n\nProject context:\n{context}" if context else ""
    system_prompt += f"""

Architect's Plan:
{plan.plan}

Triage Classification:
- Domains: {', '.join(domain_key(d) for d in triage.domains)}
- Risk: {triage.risk.value}

The asks, quoted from the request:
{render_asks(asks)}
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

