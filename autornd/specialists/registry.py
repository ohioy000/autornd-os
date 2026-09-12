"""Engineering specialists with profile-driven system prompts."""

from __future__ import annotations

from autornd.models.verdicts import SpecialistRole
from autornd.specialists.base import Specialist

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
            "You write, review, and validate firmware for embedded devices. You understand "
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
            "You write, review, and validate backend code. You consider data flow, "
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
            "You write, review, and validate frontend code. You consider usability, "
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

_specialists: dict[SpecialistRole, Specialist] | None = None


def _build_prompt(role: SpecialistRole, template: dict) -> str:
    from autornd.profiles import get_profile

    profile = get_profile()
    project_ctx = profile.build_context()
    specialist_ctx = profile.get_specialist_context(role.value)

    parts = [f"You are the {template['name']}."]

    if project_ctx:
        parts.append(f"\n{project_ctx}")

    if specialist_ctx:
        parts.append(f"\n{specialist_ctx}")

    parts.append(f"\n{template['expertise']}")
    parts.append("\nAlways respond with valid JSON matching the schema requested in the user message.")

    return "\n".join(parts)


def _build_specialists() -> dict[SpecialistRole, Specialist]:
    result = {}
    for role, template in _PROMPT_TEMPLATES.items():
        result[role] = Specialist(
            role=role,
            name=template["name"],
            domain=template["domain"],
            router_function=template["router_function"],
            system_prompt=_build_prompt(role, template),
        )
    return result


def _ensure_built() -> dict[SpecialistRole, Specialist]:
    global _specialists
    if _specialists is None:
        _specialists = _build_specialists()
    return _specialists


def reload_specialists() -> None:
    global _specialists
    _specialists = _build_specialists()


def get_specialist(role: SpecialistRole) -> Specialist:
    return _ensure_built()[role]


def get_specialists(roles: list[SpecialistRole]) -> list[Specialist]:
    built = _ensure_built()
    return [built[r] for r in roles]


def __getattr__(name: str):
    if name == "SPECIALISTS":
        return _ensure_built()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
