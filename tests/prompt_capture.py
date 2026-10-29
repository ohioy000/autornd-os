"""Golden-prompt capture for Ruling D54 (command ARCH-20261021-125, TASK 1).

The capture is the yardstick for "engineering is unchanged": TASK 2 turns it
into profiles/engineering.yaml, and the prompts that profile renders must be
byte-identical to the ones captured here, from main's code, before any D54
edit.

Every prompt site the harness has is captured once, through a recording
double that bills nothing and reaches no network: the system and user message
each call sent, taken from the first call that site made.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock

from autornd.engine import phases
from autornd.knowledge import context as knowledge_context, research
from autornd.config import settings
from autornd.models.verdicts import (
    AsksVerdict,
    DoubleCheckVerdict,
    EscalationVerdict,
    ImplementVerdict,
    PlanVerdict,
    ReviewVerdict,
    RiskLevel,
    SpecialistRole,
    TriageVerdict,
    ValidateVerdict,
)
from autornd.routing.openrouter import ModelResponse, OpenRouterClient
from autornd.specialists.registry import get_specialist, get_specialists
from tests.conftest import make_mock_response, seal_double

REQUEST = (
    "Size the backoff timer for the reconnect path. Give "
    "the cap in seconds and state whether jitter applies."
)
CONTEXT = (
    "The reconnect path's timer is sized by the request "
    "alone; no corpus was consulted for it."
)
SUMMARY = (
    "Cap the timer at 60 s using a full jitter exponential "
    "schedule; jitter applies: yes."
)
ASKS = [
    {"number": 1, "quote": "Give the cap in seconds", "kind": "value"},
    {"number": 2, "quote": "state whether jitter applies", "kind": "verdict"},
]

TRIAGE_MEDIUM = TriageVerdict(
    domains=["subject_area"],
    risk=RiskLevel.MEDIUM,
    specialists=["lead"],
    summary="Sizing a backoff timer.",
)
TRIAGE_HIGH = TriageVerdict(
    domains=["subject_area"],
    risk=RiskLevel.HIGH,
    specialists=["lead"],
    summary="Sizing a backoff timer around live risk.",
)
PLAN = PlanVerdict(
    ready=True,
    plan="Cap the timer at 60 s.",
    blockers=[],
    cost_estimate=None,
    success_criteria=[],
)
IMPLEMENT = ImplementVerdict(
    done=True,
    green=True,
    summary=SUMMARY,
    blocked_on=[],
)
FAILURE_LOG = [
    {"iteration": 1, "red_cause": "the cap was never stated"},
    {"iteration": 2, "red_cause": "the jitter direction was never stated"},
]
CHUNKS = [
    {"tag": "t", "text": "The reconnect path's timer is sized by the request alone."},
    {"tag": "t", "text": "The reconnect path's timer is sized by the request alone."},
    {"tag": "t", "text": "The reconnect path's timer is sized by the request alone."},
]

# The 16 model-calling functions capture_all reaches. The call-site test
# proves no other function in autornd/ calls a model.
SITE_FUNCTIONS = frozenset({
    "run_triage", "run_asks", "run_plan", "run_plan_feasibility",
    "run_domain_review", "run_implement", "run_recompute", "run_validate",
    "run_review", "run_doublecheck", "run_escalation_autopsy",
    "expand_queries", "rerank_chunks", "synthesize_briefing",
    "analyze_request", "_lookup",
})

# The specialist each seat is given. ENGINEERING_SEATS are the ones the golden
# fixtures were captured with. NEUTRAL_SEATS name no engineering role, so the
# leak scans under general and studio see only what the harness itself writes.
ENGINEERING_SEATS: dict[str, object] = {
    "plan": SpecialistRole.SYSTEMS_ARCHITECT,
    "feasibility": SpecialistRole.FIRMWARE_ENGINEER,
    "domain_review": SpecialistRole.TEST_ENGINEER,
    "implement": SpecialistRole.BACKEND_ENGINEER,
    "review": SpecialistRole.SYSTEMS_ARCHITECT,
}
NEUTRAL_SEATS: dict[str, object] = {seat: "lead" for seat in ENGINEERING_SEATS}

CALLS: list[dict[str, str]] = []


def _reply(function: str = "", schema: Any = None, user_message: str = "") -> dict[str, Any]:
    """The smallest dict the calling function accepts is the reply."""
    if schema is TriageVerdict:
        return {
            "domains": ["subject_area"],
            "risk": "medium",
            "specialists": ["lead"],
            "summary": "Sizing a backoff timer.",
        }
    if schema is AsksVerdict:
        return {"asks": []}
    if schema is PlanVerdict:
        return {
            "ready": True,
            "plan": "Cap the timer at 60 s.",
            "blockers": [],
            "cost_estimate": None,
            "success_criteria": [],
        }
    if schema is ImplementVerdict:
        return {"done": True, "green": True, "summary": SUMMARY, "blocked_on": []}
    if schema is ValidateVerdict:
        return {
            "green": True,
            "evidence": [],
            "failed_ask": None,
            "anchor_quote": "",
            "hazard": False,
            "kind": "",
            "source_quote": "",
            "unavailable_asks": [],
        }
    if schema is ReviewVerdict:
        return {
            "ship": True,
            "findings": [],
            "verdict": "The implementation satisfies the asks.",
        }
    if schema is DoubleCheckVerdict:
        return {
            "ship": True,
            "confidence": "high",
            "critical_issues": [],
            "recommendations": [],
            "verdict": "The implementation satisfies the asks.",
        }
    if schema is EscalationVerdict:
        return {
            "root_cause_analysis": "The failure was a sizing error.",
            "architectural_correction": "Cap the timer at 60 s and state the jitter direction.",
            "resolution_directive": "Cap the timer at 60 s and state the jitter direction.",
            "requires_human": False,
            "rulings": [],
        }
    lowered = user_message.lower()
    if "search queries" in lowered:
        return {"queries": ["backoff timer cap", "full jitter exponential backoff"]}
    if "briefing" in lowered:
        return {
            "briefing": "The reconnect path applies a full jitter exponential backoff timer capped at 60 seconds.",
            "gaps": [],
            "blocking_gaps": [],
        }
    if "objective" in lowered or "scope" in lowered:
        return {
            "objective": "Size the backoff timer and state whether jitter applies.",
            "unknowns": [],
            "blocking_unknowns": [],
            "assumptions": [],
            "considerations": [],
        }
    return {}


def recording_client() -> OpenRouterClient:
    """A hand-built double: every model method stubbed, nothing billed for real."""
    client = OpenRouterClient(api_key="test")

    async def chat_json(
        function: str,
        system_prompt: str,
        user_message: str,
        temperature: float = 0.3,
        max_tokens: int = 16384,
        max_retries: int = 3,
        schema: Any = None,
    ) -> tuple[dict[str, Any], ModelResponse]:
        CALLS.append({"function": function, "system": system_prompt, "user": user_message})
        data = _reply(function=function, schema=schema, user_message=user_message)
        response = make_mock_response(data, f"mock-{function}")
        client._account(function, response.cost)
        return data, response

    async def chat(
        function: str,
        system_prompt: str,
        user_message: str,
        **kwargs: Any,
    ) -> ModelResponse:
        CALLS.append({"function": function, "system": system_prompt, "user": user_message})
        return ModelResponse(content="a", model="m", prompt_tokens=1, completion_tokens=1, cost=0.0)

    client.chat_json = AsyncMock(side_effect=chat_json)
    client.chat = AsyncMock(side_effect=chat)
    seal_double(client)
    return client


async def capture_all(seats: dict[str, object] | None = None) -> dict[str, dict[str, str]]:
    """Capture every prompt site once, plus every specialist's prompt."""
    seats = seats or ENGINEERING_SEATS
    client = recording_client()
    captured: dict[str, dict[str, str]] = {}

    def take(site: str) -> dict[str, str]:
        if not CALLS:
            raise AssertionError(f"the {site} prompt site made no model call")
        first = CALLS[0]
        captured[site] = {"system": first["system"], "user": first["user"]}
        CALLS.clear()
        return captured[site]

    triage, _ = await phases.run_triage(client, REQUEST)
    take("triage")

    asks, _ = await phases.run_asks(client, REQUEST)
    take("asks")

    plan, _ = await phases.run_plan(
        client,
        REQUEST,
        triage,
        get_specialists([seats["plan"]]),
        tier=None,
        context=CONTEXT,
        max_tokens=None,
        asks=ASKS,
    )
    take("plan")

    responses, blockers = await phases.run_plan_feasibility(
        client,
        REQUEST,
        triage,
        plan,
        get_specialists([seats["feasibility"]]),
        context=CONTEXT,
    )
    take("feasibility")

    concerns, critical, _ = await phases.run_domain_review(
        client,
        REQUEST,
        SUMMARY,
        get_specialists([seats["domain_review"]]),
        context=CONTEXT,
        function=None,
        asks=ASKS,
    )
    take("domain_review")

    implement, _ = await phases.run_implement(
        client,
        REQUEST,
        None,
        get_specialists([seats["implement"]]),
        iteration=1,
        context=CONTEXT,
        asks=ASKS,
        results=False,
    )
    take("implement")

    implement_results, _ = await phases.run_implement(
        client,
        REQUEST,
        None,
        get_specialists([seats["implement"]]),
        iteration=1,
        context=CONTEXT,
        asks=ASKS,
        results=True,
    )
    take("implement_results")

    recompute, responses = await phases.run_recompute(
        client, REQUEST, CONTEXT, ASKS, max_tokens=None, samples=1,
    )
    take("recompute")

    validate, _ = await phases.run_validate(
        client,
        REQUEST,
        IMPLEMENT,
        context=CONTEXT,
        domains=None,
        max_tokens=None,
        function=None,
        asks=ASKS,
    )
    take("validate")

    review, responses = await phases.run_review(
        client,
        REQUEST,
        TRIAGE_MEDIUM,
        IMPLEMENT,
        get_specialists([seats["review"]]),
        context=CONTEXT,
        max_tokens=None,
        function=None,
        asks=ASKS,
    )
    take("review_collaborative")

    review, responses = await phases.run_review(
        client,
        REQUEST,
        TRIAGE_HIGH,
        IMPLEMENT,
        get_specialists([seats["review"]]),
        context=CONTEXT,
        max_tokens=None,
        function=None,
        asks=ASKS,
    )
    take("review_adversarial")

    doublecheck, _ = await phases.run_doublecheck(
        client, REQUEST, IMPLEMENT, context=CONTEXT, asks=ASKS,
    )
    take("doublecheck")

    escalation, _ = await phases.run_escalation_autopsy(
        client,
        REQUEST,
        PLAN,
        TRIAGE_MEDIUM,
        FAILURE_LOG,
        context=CONTEXT,
        asks=ASKS,
    )
    take("escalation")

    queries = await knowledge_context.expand_queries(client, REQUEST)
    take("query_expansion")

    chunks = [
        {"tag": "t", "text": CHUNKS[0]["text"], "distance": 0.1},
        {"tag": "t", "text": CHUNKS[1]["text"], "distance": 0.2},
        {"tag": "t", "text": CHUNKS[2]["text"], "distance": 0.3},
    ]
    await knowledge_context.rerank_chunks(client, queries[0], chunks, keep=2)
    take("rerank")

    briefing = await knowledge_context.synthesize_briefing(
        client, REQUEST, chunks, TRIAGE_MEDIUM.risk, None, None,
    )
    take("briefing")

    scoping, unknowns = await knowledge_context.analyze_request(client, REQUEST)
    take("scoping")

    answer, citations, model, quotes = await research._lookup(
        client, REQUEST, "the backoff cap in seconds", max_tokens=None,
    )
    take("lookup")

    from autornd.specialists import registry as specialists_registry

    for key in sorted(specialists_registry.SPECIALISTS):
        captured[f"role:{key}"] = {"system": get_specialist(key).system_prompt, "user": ""}
    captured["role:synthesized"] = {
        "system": get_specialist("unlisted_role").system_prompt,
        "user": "",
    }

    return captured
