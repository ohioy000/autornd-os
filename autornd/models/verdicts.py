"""Structured verdict schemas for each workflow phase.

Every phase outputs a typed Pydantic model — not prose. The workflow engine
checks fields like `green` and `ship` directly, no English parsing needed.
"""

from __future__ import annotations

import json
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field, model_validator, field_validator


class RiskLevel(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class Domain(str, Enum):
    FIRMWARE = "firmware"
    HARDWARE = "hardware"
    BACKEND = "backend"
    FRONTEND = "frontend"
    SUPPLY_CHAIN = "supply_chain"
    INFRASTRUCTURE = "infrastructure"
    DOCUMENTATION = "documentation"


class SpecialistRole(str, Enum):
    SYSTEMS_ARCHITECT = "systems_architect"
    FIRMWARE_ENGINEER = "firmware_engineer"
    HARDWARE_ENGINEER = "hardware_engineer"
    BACKEND_ENGINEER = "backend_engineer"
    FRONTEND_ENGINEER = "frontend_engineer"
    TEST_ENGINEER = "test_engineer"
    SUPPLY_CHAIN = "supply_chain"


# ── Triage ──

class TriageVerdict(BaseModel):
    domains: list[Domain]
    risk: RiskLevel
    specialists: list[SpecialistRole]
    summary: str = Field(description="One-line classification of the request")


# ── Plan ──

class PlanVerdict(BaseModel):
    ready: bool
    plan: str = Field(description="Implementation plan text")
    blockers: list[str] = Field(default_factory=list)
    # Generic on purpose: a bill of materials is one instance of "what will
    # this cost to build", not the general case.
    cost_estimate: Optional[float] = None
    success_criteria: list[str] = Field(default_factory=list)

    @field_validator("plan", mode="before")
    @classmethod
    def coerce_plan(cls, v: Any) -> str:
        if isinstance(v, str):
            return v
        return json.dumps(v, indent=2)

    @model_validator(mode="after")
    def ready_plans_need_criteria(self) -> "PlanVerdict":
        """A ready plan must say how to tell it succeeded.

        Validation checks the implementation against these criteria. With an
        empty list there is nothing to check, the validator cannot return green
        on any evidence, and the loop burns every iteration before escalating —
        so an empty list is a malformed plan, not an acceptable one.
        """
        if self.ready and not self.success_criteria:
            raise ValueError(
                "a ready plan must provide success_criteria; "
                "use ready=false with blockers if the work cannot be specified"
            )
        return self


# ── Implement ──

def _coerce_str(v: Any) -> str:
    if isinstance(v, str):
        return v
    return json.dumps(v, indent=2)


class ImplementVerdict(BaseModel):
    done: bool
    green: bool
    red_cause: Optional[str] = None
    iteration: int = Field(ge=1)  # upper bound is settings.max_iterations (1-20)
    summary: str
    domain_concerns: list[str] = Field(default_factory=list)

    @field_validator("summary", "red_cause", mode="before")
    @classmethod
    def coerce_strings(cls, v: Any) -> Any:
        if v is None:
            return v
        return _coerce_str(v)


# ── Validate ──

class ValidateVerdict(BaseModel):
    green: bool
    red_cause: Optional[str] = None
    evidence: list[str] = Field(default_factory=list)


# ── Review ──

class ReviewFinding(BaseModel):
    lens: str = "unknown"
    severity: str = "medium"
    detail: str


class ReviewVerdict(BaseModel):
    ship: bool
    findings: list[ReviewFinding] = Field(default_factory=list)
    verdict: str = Field(description="Final synthesis statement")


# ── Escalation ──

class DoubleCheckVerdict(BaseModel):
    ship: bool
    confidence: str = Field(description="high, medium, or low")
    critical_issues: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    verdict: str


class EscalationVerdict(BaseModel):
    root_cause_analysis: str = Field(
        ...,
        description="The fundamental logic or architectural flaw causing the consecutive failures. Conclusion only, no reasoning steps.",
    )
    architectural_correction: str | None = Field(
        None,
        description="Corrected logic or missing dependencies if the original plan was flawed.",
    )
    resolution_directive: str = Field(
        ...,
        description="Specific, step-by-step instructions for the Implementation model to succeed on its next attempt.",
    )
    requires_human: bool = Field(
        ...,
        description="True ONLY if the fix requires external API keys, manual hardware intervention, or falls entirely outside the current architecture scope.",
    )
