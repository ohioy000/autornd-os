"""Engineering specialists with profile-driven system prompts."""

from __future__ import annotations

import logging

from autornd.models.verdicts import SpecialistRole, role_key
from autornd.specialists.base import Specialist

logger = logging.getLogger(__name__)

_PROMPT_TEMPLATES: dict[SpecialistRole, dict] = {
    SpecialistRole.SYSTEMS_ARCHITECT: {
        "name": "Systems Architect",
        "domain": "Architecture, integration, trade-off analysis",
        "router_function": "architecture",
        "expertise": (
            "Your domain: system architecture, protocol design, service orchestration, "
            "cross-domain integration, and trade-off analysis. You consider resource "
            "constraints, power budgets, bandwidth limits, and reliability requirements.\n\n"
            "You produce implementation plans, evaluate architectural trade-offs, and "
            "review designs from a system-level perspective."
        ),
    },
    SpecialistRole.FIRMWARE_ENGINEER: {
        "name": "Firmware Engineer",
        "domain": "Embedded systems, microcontrollers, RTOS, power management",
        "router_function": "engineering",
        "expertise": (
            "Your domain: embedded firmware development, microcontroller programming, "
            "RTOS task management, deep sleep and power management, OTA update mechanisms, "
            "and build systems.\n\n"
            "You specify, review, and validate firmware designs for embedded devices. You understand "
            "communication protocols, ADC calibration, and sensor data encoding."
        ),
    },
    SpecialistRole.HARDWARE_ENGINEER: {
        "name": "Hardware Engineer",
        "domain": "PCB design, BOM, schematic, thermal",
        "router_function": "engineering",
        "expertise": (
            "Your domain: PCB layout and design review, BOM analysis, schematic review, "
            "connector selection, enclosure design, weatherproofing, thermal analysis, "
            "antenna placement, and manufacturing constraints.\n\n"
            "You evaluate hardware designs for producibility, reliability in target "
            "environments, and cost targets."
        ),
    },
    SpecialistRole.BACKEND_ENGINEER: {
        "name": "Backend Engineer",
        "domain": "Backend services, APIs, databases, data pipelines",
        "router_function": "engineering",
        "expertise": (
            "Your domain: backend service development, API design, database management, "
            "data pipeline architecture, message broker integration, and alert engine design.\n\n"
            "You specify, review, and validate backend implementations. You consider data flow, "
            "error handling, and performance at the application layer."
        ),
    },
    SpecialistRole.FRONTEND_ENGINEER: {
        "name": "Frontend Engineer",
        "domain": "UI frameworks, data visualization, responsive design",
        "router_function": "engineering",
        "expertise": (
            "Your domain: frontend development, data visualization, responsive design, "
            "and user interface architecture.\n\n"
            "You specify, review, and validate frontend implementations. You consider usability, "
            "accessibility, performance, and the target user environment."
        ),
    },
    SpecialistRole.TEST_ENGINEER: {
        "name": "Test Engineer",
        "domain": "Validation plans, test protocols, quality assurance",
        "router_function": "engineering",
        "expertise": (
            "Your domain: test plan creation, test protocols, regression test suites, "
            "validation criteria, and deployment testing. You evaluate implementations "
            "against success criteria defined in the plan phase.\n\n"
            "You run deterministic checks where possible: resource budget math, pin "
            "assignment conflicts, cost vs target, API schema validation, routing "
            "correctness. For hardware, you define bench test procedures."
        ),
    },
    SpecialistRole.SUPPLY_CHAIN: {
        "name": "Supply Chain",
        "domain": "BOM costing, sourcing, compliance",
        "router_function": "engineering",
        "expertise": (
            "Your domain: BOM costing and optimization, component sourcing, regulatory "
            "compliance, tariff analysis, lead time tracking, and vendor management.\n\n"
            "You evaluate designs for cost, sourcing risk (single-source components), "
            "and regulatory compliance."
        ),
    },
}

# Stated on every specialist's system prompt. Without it the role framing
# ("you specify firmware", "you review designs") leaves a model free to assume
# it should be editing a repository, and it answers that it cannot — which the
# validate phase then reads as a failed implementation.
SPECIALIST_OUTPUT_CONTRACT = (
    "You work entirely in writing. You have no repository, file system, shell "
    "or build tools, and you never need them: your written output is the "
    "deliverable that a human or a downstream system applies. Produce the "
    "engineering work itself, in full, rather than reporting on what you would "
    "do or noting that you lack access."
)


# Keyed on the normalised role name, not the enum, because the roster is open:
# a profile declares the roles its own team has, and triage may name one that
# nobody declared.
_specialists: dict[str, Specialist] | None = None

# Roles synthesized on demand, logged once each so an operator learns which
# roles their profile ought to declare without a line per workflow.
_synthesized: dict[str, Specialist] = {}


def _build_prompt(role: object, template: dict) -> str:
    from autornd.profiles import get_profile

    profile = get_profile()
    project_ctx = profile.build_context()
    specialist_ctx = profile.get_specialist_context(role_key(role))

    parts = [f"You are the {template['name']}."]

    if project_ctx:
        parts.append(f"\n{project_ctx}")

    if specialist_ctx:
        parts.append(f"\n{specialist_ctx}")

    parts.append(f"\n{template['expertise']}")
    parts.append(f"\n{SPECIALIST_OUTPUT_CONTRACT}")
    parts.append("\nAlways respond with valid JSON matching the schema requested in the user message.")

    return "\n".join(parts)


def _profile_templates() -> dict[str, dict]:
    """Profile-declared roles, in the same shape as the built-in templates.

    A declared role goes through `_build_prompt` like any other, so it inherits
    the project context and the output contract rather than being a second-class
    prompt assembled somewhere else.
    """
    from autornd.profiles import get_profile

    templates: dict[str, dict] = {}
    for name, definition in (get_profile().roles or {}).items():
        key = role_key(name)
        definition = definition or {}
        templates[key] = {
            "name": definition.get("name") or _title(key),
            "domain": definition.get("domain", ""),
            "router_function": definition.get("tier")
            or definition.get("router_function")
            or "engineering",
            "expertise": definition.get("expertise", "")
            or f"Your domain: {definition.get('domain') or _title(key)}.",
        }
    return templates


def _title(key: str) -> str:
    return key.replace("_", " ").title()


def _build_specialists() -> dict[str, Specialist]:
    result: dict[str, Specialist] = {}
    templates: dict[str, dict] = {
        role_key(role): template for role, template in _PROMPT_TEMPLATES.items()
    }
    # Profile roles are layered last, so a project can refine a shipped role as
    # well as add one.
    templates.update(_profile_templates())
    for key, template in templates.items():
        result[key] = Specialist(
            role=key,
            name=template["name"],
            domain=template["domain"],
            router_function=template["router_function"],
            system_prompt=_build_prompt(key, template),
        )
    return result


def _ensure_built() -> dict[str, Specialist]:
    global _specialists
    if _specialists is None:
        _specialists = _build_specialists()
    return _specialists


def reload_specialists() -> None:
    global _specialists, _synthesized
    _specialists = _build_specialists()
    _synthesized = {}


def _synthesize(key: str) -> Specialist:
    """A working specialist for a role nobody declared.

    Measured live: triage staffed a signing-key rotation with
    `infrastructure_engineer`, which this harness does not ship. Raising a
    KeyError there would fail a whole workflow over a role name, and silently
    dropping the role would lose the judgement triage actually made — so the
    role is honoured as a generalist and the operator is told once that their
    profile should declare it.
    """
    if key in _synthesized:
        return _synthesized[key]
    name = _title(key)
    template = {
        "name": name,
        "domain": name,
        "router_function": "engineering",
        "expertise": (
            f"You are acting as the {name} on this team. Work within that "
            f"function: bring what someone in that role would bring, and say so "
            f"plainly where the request falls outside it."
        ),
    }
    specialist = Specialist(
        role=key, name=name, domain=name,
        router_function=template["router_function"],
        system_prompt=_build_prompt(key, template),
    )
    _synthesized[key] = specialist
    logger.info(
        "No role %r is shipped or declared — acting as a generalist. Declare it "
        "under `roles:` in your profile to give it real grounding.", key,
    )
    return specialist


def get_specialist(role: object) -> Specialist:
    key = role_key(role)
    built = _ensure_built()
    if key in built:
        return built[key]
    return _synthesize(key)


def get_specialists(roles: list[object]) -> list[Specialist]:
    return [get_specialist(r) for r in roles]


def __getattr__(name: str):
    if name == "SPECIALISTS":
        return _ensure_built()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
