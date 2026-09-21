"""Project profile system — configurable domain grounding for specialists."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from autornd.config import settings

logger = logging.getLogger(__name__)

PROFILES_DIR = Path(__file__).resolve().parent.parent / "profiles"


@dataclass
class ProjectProfile:
    name: str = "AutoRnD"
    description: str = ""
    site_url: str = ""
    stack: list[str] = field(default_factory=list)
    constraints: list[str] = field(default_factory=list)
    specialists: dict[str, dict[str, Any]] = field(default_factory=dict)
    # Domain name -> either the role that leads it, or a mapping carrying that
    # lead plus the validation questions this domain is judged by. R&D spans
    # more subjects than any shipped list can name, so a project declares the
    # vocabulary its own work actually uses.
    #
    #   domains:
    #     mechanical: hardware_engineer
    #     legal_ops:
    #       lead: paralegal
    #       checks:
    #         - "Is every retention period tied to a named statute?"
    domains: dict[str, Any] = field(default_factory=dict)
    # Role name -> its definition, for the roles a team has that this harness
    # does not ship. Same shape as the built-in templates, so a declared role
    # is built by exactly the same path.
    #
    #   roles:
    #     paralegal:
    #       name: "Paralegal"
    #       domain: "Records retention, statutory schedules"
    #       tier: engineering
    #       expertise: "..."
    roles: dict[str, dict[str, Any]] = field(default_factory=dict)
    # The two roles this harness reaches for STRUCTURALLY — regardless of who
    # triage staffed — because two rules are not judgement calls: risky work is
    # checked by someone, and work spanning domains has someone holding the
    # system-level view. Until B14 those two roles were the shipped engineering
    # ones, hardcoded, and they bound on every profile: measured, 77 of 108
    # wide-suite units were assigned a test engineer in BOTH arms of a
    # studio/control comparison, identical, because the injection never
    # consulted the profile (§24.1(d)).
    #
    # The RULES are domain-neutral and unchanged. Only their operands move.
    #
    #   structural_roles:
    #     checks_work: editor          # engineering default: test_engineer
    #     holds_system_view: strategist  # default: systems_architect
    #
    # Undeclared means the shipped default, so a profile that says nothing
    # behaves exactly as it did before B14.
    structural_roles: dict[str, str] = field(default_factory=dict)

    def role_that_checks_work(self) -> str:
        """Who is added when risk is high enough that somebody must check."""
        from autornd.models.verdicts import SpecialistRole, role_key
        declared = (self.structural_roles or {}).get("checks_work")
        return role_key(declared) if declared else role_key(
            SpecialistRole.TEST_ENGINEER)

    def role_that_holds_system_view(self) -> str:
        """Who is added when the work spans domains, or when nobody else fits."""
        from autornd.models.verdicts import SpecialistRole, role_key
        declared = (self.structural_roles or {}).get("holds_system_view")
        return role_key(declared) if declared else role_key(
            SpecialistRole.SYSTEMS_ARCHITECT)

    def build_context(self) -> str:
        if not self.description and not self.stack:
            return ""
        lines = [f"{self.name}: {self.description}" if self.description else self.name]
        if self.stack:
            lines.append("Stack:")
            lines.extend(f"  - {s}" for s in self.stack)
        if self.constraints:
            lines.append("Constraints:")
            lines.extend(f"  - {c}" for c in self.constraints)
        return "\n".join(lines)

    def _domain_entry(self, domain: str) -> Any | None:
        from autornd.models.verdicts import domain_key

        key = domain_key(domain)
        for name, entry in self.domains.items():
            if domain_key(name) == key:
                return entry
        return None

    def get_domain_lead(self, domain: str) -> str | None:
        """Which specialist leads a profile-declared domain, if any."""
        entry = self._domain_entry(domain)
        if isinstance(entry, dict):
            lead = entry.get("lead")
            return str(lead) if lead else None
        return str(entry) if entry else None

    def get_domain_checks(self, domain: str) -> tuple[str, ...]:
        """The validation questions this domain is judged by, if declared.

        Built-in checks only cover the seven shipped domains, so work in any
        other subject reached validation with no lenses at all.
        """
        entry = self._domain_entry(domain)
        if not isinstance(entry, dict):
            return ()
        checks = entry.get("checks") or []
        if isinstance(checks, str):
            checks = [checks]
        return tuple(str(c).strip() for c in checks if str(c).strip())

    def domain_vocabulary(self) -> list[str]:
        """Profile-declared domain names, for the triage prompt."""
        from autornd.models.verdicts import domain_key

        return [domain_key(name) for name in self.domains]

    def get_role(self, role: str) -> dict[str, Any] | None:
        """A profile-declared role's definition, if it has one."""
        from autornd.models.verdicts import role_key

        key = role_key(role)
        for name, definition in self.roles.items():
            if role_key(name) == key:
                return dict(definition or {})
        return None

    def role_vocabulary(self) -> list[str]:
        """Profile-declared role names, for the triage prompt."""
        from autornd.models.verdicts import role_key

        return [role_key(name) for name in self.roles]

    def get_specialist_context(self, role: str) -> str | None:
        spec_cfg = self.specialists.get(role, {})
        return spec_cfg.get("context")

    def get_docs_dir(self) -> str:
        return self.name.lower().replace(" ", "_")


DEFAULT_PROFILE = ProjectProfile()

_active_profile: ProjectProfile | None = None


def load_profile(name: str) -> ProjectProfile:
    path = PROFILES_DIR / f"{name}.yaml"
    if not path.exists():
        path = PROFILES_DIR / f"{name}.yml"
    if not path.exists():
        raise FileNotFoundError(f"Profile not found: {name} (looked in {PROFILES_DIR})")

    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return ProjectProfile(
        name=data.get("name", name),
        description=data.get("description", ""),
        site_url=data.get("site_url", ""),
        stack=data.get("stack", []),
        constraints=data.get("constraints", []),
        specialists=data.get("specialists", {}),
        domains=data.get("domains", {}) or {},
        roles=data.get("roles", {}) or {},
        structural_roles=data.get("structural_roles", {}) or {},
    )


def list_profiles() -> list[str]:
    if not PROFILES_DIR.exists():
        return []
    return sorted(
        p.stem for p in PROFILES_DIR.iterdir()
        if p.suffix in (".yaml", ".yml") and p.is_file()
    )


def get_profile() -> ProjectProfile:
    global _active_profile
    if _active_profile is not None:
        return _active_profile

    profile_name = settings.autornd_profile
    if profile_name:
        try:
            _active_profile = load_profile(profile_name)
            logger.info("Loaded profile: %s", _active_profile.name)
        except FileNotFoundError:
            logger.warning("Profile '%s' not found, using default", profile_name)
            _active_profile = DEFAULT_PROFILE
    else:
        _active_profile = DEFAULT_PROFILE

    return _active_profile


def set_profile(profile: ProjectProfile) -> None:
    global _active_profile
    _active_profile = profile


def reset_profile() -> None:
    global _active_profile
    _active_profile = None
