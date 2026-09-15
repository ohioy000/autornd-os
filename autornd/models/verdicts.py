"""Structured verdict schemas for each workflow phase.

Every phase outputs a typed Pydantic model — not prose. The workflow engine
checks fields like `green` and `ship` directly, no English parsing needed.
"""

from __future__ import annotations

import json
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field, field_validator, model_validator, field_validator


class RiskLevel(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


def normalise_key(value: object) -> str:
    """One spelling for a vocabulary term, whether enum member or plain string.

    Both open vocabularies — domains and roles — normalise identically, and
    enum members keep working because Domain and SpecialistRole subclass str.
    """
    raw = getattr(value, "value", value)
    return str(raw).strip().lower().replace(" ", "_").replace("-", "_")


def domain_key(value: object) -> str:
    """One spelling for a domain.

    Domains are open-ended: R&D spans more subjects than any fixed list can
    name, so triage may return one that is not in the Domain enum. Everything
    downstream keys on the normalised string.
    """
    return normalise_key(value)


def role_key(value: object) -> str:
    """One spelling for a specialist role.

    Roles are open-ended for the same reason domains are, and measured the same
    way: asked to staff a firmware signing-key rotation, triage returned
    `infrastructure_engineer`, which is not a role this harness ships. A legal
    team wants a paralegal and a marketing team a copywriter, and no shipped
    list of engineering roles will ever contain them.
    """
    return normalise_key(value)


class Domain(str, Enum):
    """The default domain vocabulary.

    A starting set, not a closed one. Triage prefers these, a profile can
    declare its own, and an unrecognised domain resolves to the architect
    rather than being forced into the nearest label.
    """

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
    # Open-ended on purpose. Measured over twelve subjects, nine had no fitting
    # label in the enum and eight of those were forced to "hardware" — civil
    # engineering as hardware, a latency budget as firmware. Triage was not
    # guessing badly; it was picking the least-wrong option from a list that did
    # not contain the answer.
    domains: list[str]
    risk: RiskLevel
    # Open for the same measured reason the domains are: triage returned
    # `infrastructure_engineer` for a signing-key rotation and the domain value
    # `documentation` in this field. The shipped roles stay the default roster,
    # a profile declares the roles its own team actually has, and an undeclared
    # role resolves to a generalist rather than failing the workflow.
    specialists: list[str]
    # Risk asks whether a wrong answer harms someone. This asks a separate
    # question: can it be taken back? A signed firmware rollout to 40,000
    # devices injures nobody and cannot be recalled, so it stays `high` and
    # earns one more independent pass instead of diluting `critical`.
    unrecallable: bool = False
    summary: str = Field(description="One-line classification of the request")

    @field_validator("domains", mode="before")
    @classmethod
    def normalise_domains(cls, value: object) -> object:
        if not isinstance(value, list):
            return value
        seen: list[str] = []
        for item in value:
            key = domain_key(item)
            if key and key not in seen:
                seen.append(key)
        return seen

    @field_validator("specialists", mode="before")
    @classmethod
    def normalise_specialists(cls, value: object) -> object:
        if not isinstance(value, list):
            return value
        seen: list[str] = []
        for item in value:
            key = role_key(item)
            if key and key not in seen:
                seen.append(key)
        return seen


# ── Plan ──

# A plan whose criteria are "...", "TBD" or similar passes a non-empty check but
# leaves validate with nothing to check against — it reds the work every
# iteration, exhausts the loop and escalates. Treat a degenerate criterion as a
# malformed plan so the retry path asks for a real one.
_PLACEHOLDER_WORDS = {
    "tbd", "todo", "n/a", "na", "none", "placeholder", "criterion",
    "criteria", "unknown", "pending", "...", "etc",
}


def _is_placeholder(value: object) -> bool:
    """Does this criterion carry no checkable content?

    Judged on substance rather than length — "BOM < $45" is a real criterion
    and "success criteria 2" is not, though the second is longer.
    """
    if not isinstance(value, str):
        return True
    text = value.strip().strip(".…-–—*•[]() ").strip()
    if not text:
        return True

    tokens = text.lower().split()
    meaningful = [t for t in tokens if any(ch.isalnum() for ch in t)]
    if len(meaningful) < 2:
        # a single word is only a criterion if it is not one of the usual stubs
        return not meaningful or meaningful[0] in _PLACEHOLDER_WORDS

    # "criterion 1", "TBD - todo" and friends: nothing but stubs and numbers
    words = [t for t in meaningful if not t.isdigit()]
    return bool(words) and all(w in _PLACEHOLDER_WORDS for w in words)


class PlanVerdict(BaseModel):
    ready: bool
    # Empty is valid when the plan is not ready: a request too underspecified to
    # plan has no plan text, and the prompt tells the architect to say so in
    # blockers. Requiring it here made the model right and the schema wrong —
    # it refused three times, correctly, and each refusal was rejected.
    plan: str = Field(default="", description="Implementation plan text")
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
        if not self.ready:
            if not self.blockers:
                raise ValueError(
                    "a plan that is not ready must say why in blockers"
                )
            return self
        if not self.plan.strip():
            raise ValueError(
                "a ready plan must contain the plan itself; "
                "use ready=false with blockers if it cannot be written"
            )
        if not self.success_criteria:
            raise ValueError(
                "a ready plan must provide success_criteria; "
                "use ready=false with blockers if the work cannot be specified"
            )
        placeholders = [c for c in self.success_criteria if _is_placeholder(c)]
        if placeholders:
            raise ValueError(
                f"success_criteria contains placeholders rather than real "
                f"criteria: {placeholders!r}. Every criterion must be a "
                f"concrete, checkable statement about the implementation."
            )
        return self


# ── Implement ──

def _coerce_str(v: Any) -> str:
    if isinstance(v, str):
        return v
    return json.dumps(v, indent=2)


class ImplementVerdict(BaseModel):
    # Required, and staying required: nothing else in the verdict implies
    # whether the work is finished. The 006 death on this class predated the
    # schema being wired into the retry loop, which is the mechanism that
    # covers an omission of genuinely independent information.
    done: bool
    # Optional and resolved from red_cause — see the truth table above.
    green: Optional[bool] = None
    red_cause: Optional[str] = None
    # Defaulted, not required. `run_implement` overwrites this with the loop's
    # own counter the moment the reply lands, so demanding the model echo a
    # number we are about to discard buys nothing — and cost a full retry
    # whenever it echoed one we would not have accepted.
    # Upper bound is settings.max_iterations (1-20).
    iteration: int = Field(default=1, ge=1)
    summary: str
    domain_concerns: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _green_from_red_cause(self):
        return _resolve_green(self)

    @field_validator("summary", "red_cause", mode="before")
    @classmethod
    def coerce_strings(cls, v: Any) -> Any:
        if v is None:
            return v
        return _coerce_str(v)


# ── Validate ──

# ── green/red_cause resolution ──────────────────────────────────────────────
#
# `green` is not independent information. Every prompt that asks for it says so
# in the same breath — "green: true if it satisfies the criteria; red_cause:
# null if green, otherwise what is wrong" — so a verdict carrying a red_cause
# has already said it is red, and one carrying none has already said it is
# green. The model supplies the cause and omits the flag.
#
# Measured twice, four blueprints apart. In 006 two of four convergence traces
# died on `ImplementVerdict` rejecting a reply that had `done` and `red_cause`
# and no `green`; the schema was then wired into the retry loop so the model
# would be told what was wrong and asked again. In 010 two of four died the same
# way **after all three retries were spent**, each attempt carrying the rejection
# text and each coming back without the field. The wiring worked and the model
# did not comply.
#
# So: tolerate the omission of a derivable field, and refuse the loss of a
# non-derivable one. `done` stays required because nothing in the verdict
# implies it. The resolution is counted rather than silent — a normalization is
# a fact about the model, and a fix that hides its own trigger stops anyone
# noticing when it stops being needed.
_normalisations = 0


def normalisations() -> int:
    return _normalisations


def reset_normalisations() -> None:
    global _normalisations
    _normalisations = 0


def _resolve_green(verdict: Any) -> Any:
    """The ruled truth table, applied after construction."""
    global _normalisations
    has_cause = bool((verdict.red_cause or "").strip())

    if verdict.green is None:
        verdict.green = not has_cause
        _normalisations += 1
        return verdict

    if verdict.green and has_cause:
        # The conservative side. A false red costs an iteration; a false green
        # ships work nobody checked.
        verdict.green = False
        _normalisations += 1
        return verdict

    if not verdict.green and not has_cause:
        # The one case that loses information: something is wrong and the
        # verdict does not say what. The retry machinery exists to ask.
        raise ValueError(
            "a red verdict must name its cause in red_cause"
        )
    return verdict


class ValidateVerdict(BaseModel):
    # Optional and resolved, for the reason recorded above. Validate's prompt
    # carries the identical contract to implement's, verified before this was
    # applied to it: "green: true if every success criterion is satisfied;
    # red_cause: null if green, otherwise the specific failure cause".
    green: Optional[bool] = None
    red_cause: Optional[str] = None
    evidence: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _green_from_red_cause(self):
        return _resolve_green(self)


# ── Review ──

class ReviewFinding(BaseModel):
    """One thing a reviewer found.

    Tolerant about shape on the way in, because reviewers write findings a
    dozen ways and a required key is a whole review lost to a synonym. Measured
    live: a review returned findings with no `detail` field, the schema
    rejected it three times, and the workflow died at the last phase with the
    findings in hand.
    """

    lens: str = "unknown"
    severity: str = "medium"
    detail: str = ""

    @model_validator(mode="before")
    @classmethod
    def accept_the_shapes_reviewers_use(cls, value: Any) -> Any:
        # A bare string is the most common shape of all.
        if isinstance(value, str):
            return {"detail": value}
        if not isinstance(value, dict):
            return value

        data = dict(value)
        if not str(data.get("detail") or "").strip():
            # Same content, different key. Take the first that carries text.
            for alias in ("issue", "description", "finding", "concern",
                          "text", "problem", "note", "summary", "message"):
                candidate = data.get(alias)
                if isinstance(candidate, str) and candidate.strip():
                    data["detail"] = candidate.strip()
                    break
        return data

    @field_validator("lens", "severity", "detail", mode="before")
    @classmethod
    def coerce_to_text(cls, value: Any) -> Any:
        if value is None:
            return ""
        return value if isinstance(value, str) else _coerce_str(value)


class ReviewVerdict(BaseModel):
    ship: bool
    findings: list[ReviewFinding] = Field(default_factory=list)
    verdict: str = Field(description="Final synthesis statement")

    @field_validator("findings", mode="before")
    @classmethod
    def drop_empty_findings(cls, value: Any) -> Any:
        """A finding with nothing in it is not a finding.

        Kept separate from the tolerance above: that recovers content written
        under another name, this discards entries that carry none — so a
        reviewer padding its list cannot turn into a blocking issue with no
        text against it.
        """
        if not isinstance(value, list):
            return value
        kept = []
        for item in value:
            if isinstance(item, str) and not item.strip():
                continue
            if isinstance(item, dict) and not any(
                    str(v or "").strip() for v in item.values()):
                continue
            kept.append(item)
        return kept


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
