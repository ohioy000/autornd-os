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
