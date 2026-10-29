"""Structured verdict schemas for each workflow phase.

Every phase outputs a typed Pydantic model — not prose. The workflow engine
checks fields like `green` and `ship` directly, no English parsing needed.
"""

from __future__ import annotations

import json
import re
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field, field_validator, model_validator


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


# ── Asks (Ruling D51 (1)) ─────────────────────────────────────────
#
# The request's asks, proposed by a model on the triage tier and
# anchored by a free deterministic check (asks_anchored,
# autornd/graph/checks.py). Each ask is a verbatim quote of the
# request with its kind. The anchored asks are the run's only
# success criteria — nothing the plan produces is judged against.
class AskKind(str, Enum):
    """The five kinds the asks prompt names. Closed by the ruling:
    the prompt fixes the vocabulary, and a reply naming a sixth kind
    is a non-compliant reply the retry path asks again."""

    VALUE = "value"
    VERDICT = "verdict"
    STEP = "step"
    CONSTRAINT = "constraint"
    FORMAT = "format"


class Ask(BaseModel):
    """One ask: a verbatim quote of the request, with its kind."""

    quote: str
    kind: AskKind

    @field_validator("kind", mode="before")
    @classmethod
    def _normalise_kind(cls, value: object) -> object:
        """'Value' and ' value ' are the kind the prompt named."""
        if isinstance(value, str):
            return value.strip().lower()
        return value


class AsksVerdict(BaseModel):
    """The `asks` node's verdict: what the request asks, quoted.

    The list may be empty — the anchoring check applies the ruled
    fallback (the whole request is the one ask) when nothing the
    model proposed anchors, so an empty proposal is a shape the
    check handles deterministically, not a malformed verdict.
    """

    asks: list[Ask] = Field(default_factory=list)


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

    @field_validator("cost_estimate", mode="before")
    @classmethod
    def coerce_cost_estimate(cls, v: Any) -> Any:
        """Ruling D26: coerce a recoverable numeric string, count it, or
        reject. '$989.88 per month ...' recovers 989.88 — the number is
        unambiguously carried, and rejecting it discarded a recoverable plan
        cost on the -049 live run (B28). 'Approximately one thousand'
        carries no digits and is rejected: a coercion must never invent a
        number the text does not carry. Non-strings pass through to the
        declared type (a list or object still rejects); None stays None."""
        import re
        if v is None or isinstance(v, (int, float)):
            return v
        if not isinstance(v, str):
            return v
        m = re.search(r"-?\$?\s*(\d{1,3}(?:,\d{3})*(?:\.\d+)?|\d+(?:\.\d+)?)", v)
        if not m:
            return v
        try:
            coerced = float(m.group(1).replace(",", ""))
        except ValueError:
            return v
        _count(COST_ESTIMATE_COERCED)
        return coerced

    @field_validator("plan", mode="before")
    @classmethod
    def coerce_plan(cls, v: Any) -> str:
        if isinstance(v, str):
            return v
        return json.dumps(v, indent=2)

    @model_validator(mode="after")
    def ready_plans_need_a_plan(self) -> "PlanVerdict":
        """A ready plan must contain the plan itself.

        Ruling D51 (4): the plan no longer writes success criteria,
        and a ready plan no longer needs them — the request's anchored
        asks are the run's only success criteria, so nothing here
        demands criteria (the field stays, so earlier records load).
        D36's four rules still govern how the plan is reasoned; they
        govern reasoning, not what the answer must contain. The
        placeholder check retired with the requirement it policed: a
        plan that writes no criteria cannot carry a placeholder one.
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
        return self


# ── Implement ──

def _coerce_str(v: Any) -> str:
    if isinstance(v, str):
        return v
    return json.dumps(v, indent=2)


class BlockedOnAsk(BaseModel):
    """One ask the work cannot honestly answer (Ruling D51 (5)).

    The entry NAMES the ask — by its number, or by its quote, which
    the anchoring check verifies against the request. An entry that
    names no ask is a note: counted, never blocking, routing nowhere
    (the ruled disposition of "an implementer's blocked_on entry must
    name an ask"). A bare string — the pre-D51 shape, and the shape a
    model that did not read the new contract returns — carries its
    reason in `why` and names nothing, which is exactly that note.
    """

    ask: int | str | None = None
    why: str = ""

    @model_validator(mode="before")
    @classmethod
    def _accept_the_shapes_the_channel_carries(cls, value: Any) -> Any:
        if isinstance(value, str):
            return {"why": value}
        if isinstance(value, int) and not isinstance(value, bool):
            return {"ask": value}
        return value

    @field_validator("why", mode="before")
    @classmethod
    def _coerce_why(cls, value: Any) -> str:
        if value is None:
            return ""
        return value if isinstance(value, str) else _coerce_str(value)


class DomainConcern(BaseModel):
    """One domain reviewer's concern (Ruling D51 (3), text (R-f);
    the review of 2026-10-14: a hazard needs its quote).

    A concern can be critical only if it is anchored: it names the
    ask it concerns by number, quotes the request's own words for
    something the answer gets wrong or leaves out, or it is a
    hazard — and a hazard anchors only through the answer's own
    words that state or instruct it, carried in `hazard_quote`.
    A critical concern with no anchor is a note — never critical —
    and cannot flip the implementation red. An omission is never a
    hazard; if the request asked for what is missing, it is an ask.
    """

    detail: str = ""
    ask: int | None = None
    quote: str = ""
    hazard: bool = False
    # The review of 2026-10-14: when hazard is true, the answer's
    # own words that state or instruct it, verbatim. The concern's
    # hazard anchors only when these words occur in the answer the
    # judge was given; a hazard without them is a note, counted as
    # unanchored dissent.
    hazard_quote: str = ""
    # Ruling of 2026-10-15 (R2), amending D51 (3): the
    # dissent's kind — unmet_ask (the answer gives nothing
    # for the ask), wrong_fact (the answer gives something
    # for the ask and the judge says it is false), or
    # hazard. A dissent that states no kind is read as
    # wrong_fact. A wrong_fact dissent anchors only through
    # `source_quote`, the request's or the grounding's own
    # words that contradict the answer, verbatim.
    kind: str = ""
    source_quote: str = ""
    critical: bool = False

    @model_validator(mode="before")
    @classmethod
    def _accept_the_shapes_reviewers_use(cls, value: Any) -> Any:
        # A bare string is the most common shape of all, and carries
        # no anchor: a note, never critical.
        if isinstance(value, str):
            return {"detail": value}
        if not isinstance(value, dict):
            return value
        data = dict(value)
        if not str(data.get("detail") or "").strip():
            for alias in ("issue", "description", "concern", "text",
                          "problem", "note", "summary", "message"):
                candidate = data.get(alias)
                if isinstance(candidate, str) and candidate.strip():
                    data["detail"] = candidate.strip()
                    break
        return data

    @field_validator("detail", "quote", "hazard_quote", "source_quote",
                     mode="before")
    @classmethod
    def _coerce_text(cls, value: Any) -> str:
        if value is None:
            return ""
        return value if isinstance(value, str) else _coerce_str(value)

    @field_validator("kind", mode="before")
    @classmethod
    def _coerce_kind(cls, value: Any) -> str:
        # Stored as stated: the record shows what the judge
        # declared. The effective kind — what an unstated or
        # unrecognised kind is read as — is derived at the
        # point of use, by dissent_kind below.
        if value is None:
            return ""
        return value if isinstance(value, str) else _coerce_str(value)


# ── Typed results (Ruling D53) ───────────────────────────────
#
# The answer's results, stated as typed values the recompute vote
# can check. One entry per ask of kind value or verdict: the ask
# named by its number or its quote — the way blocked_on does
# (D51 (5)) — the value (a number, or the identifier chosen for
# a verdict ask), and the value's unit, empty for an identifier.
class ResultValue(BaseModel):
    ask: int | str
    value: float | str
    unit: str = ""

    @field_validator("unit", mode="before")
    @classmethod
    def _coerce_unit(cls, value: Any) -> str:
        # A null unit is no unit — a bare number or an identifier —
        # not a missing field.
        if value is None:
            return ""
        return value if isinstance(value, str) else _coerce_str(value)


class RecomputeVerdict(BaseModel):
    """One blind recompute sample's verdict: its typed results.

    Ruling D53: the sample computed the anchored asks of kind value
    and verdict from the request and the grounding alone — never
    seeing the answer, its results, the plan or another sample's
    output — so what it states is an independent computation of the
    same asks, and the vote compares it with the answer field by
    field. An empty results list is a sample that stated nothing:
    parseable, and answering no ask.
    """

    results: list[ResultValue] = Field(default_factory=list)

    @field_validator("results", mode="before")
    @classmethod
    def _coerce_results(cls, value: Any) -> Any:
        # A null results field is no results — the sample stated
        # nothing — not a malformed verdict.
        if value is None:
            return []
        return value


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
    # Ruling D51 (3): typed concerns (DomainConcern). A concern
    # flips this verdict red only when it is critical AND anchored;
    # the adapter demotes an unanchored critical concern to a note
    # before it lands, so the list that arrives here holds what the
    # record keeps.
    domain_concerns: list[DomainConcern] = Field(default_factory=list)
    # Ruled (Blueprint 016 B2) — the honest-refusal channel. Asks
    # the work cannot satisfy with what is available, each naming the
    # ask by its number or its quote (Ruling D51 (5)). The measured
    # failure it exists for: a low-risk brief whose plan demanded "a
    # citable source a reader can use to verify the claim" while the risk gate
    # had already zeroed its lookups, and the implementer fabricated sources
    # for six iterations rather than refusing. Independent of `green` by
    # ruling: the loop routes on this field, not on the implementer's own
    # green self-assessment, so an implementer that blocks does not also have
    # to declare itself red. An entry that names no ask is a note,
    # counted, and routes nowhere.
    blocked_on: list[BlockedOnAsk] = Field(default_factory=list)
    # Ruling D53: the answer's typed results — one entry per ask of
    # kind value or verdict, naming the ask by its number or its
    # quote — so the recompute vote can compare the answer against
    # blind recomputation, field by field. Defaulted, not required:
    # every recorded ImplementVerdict predates the field and must
    # still parse, and an answer that states its results only in
    # prose has nothing to vote on (the vote is then unchecked,
    # never passed).
    results: list[ResultValue] = Field(default_factory=list)

    @model_validator(mode="after")
    def _green_from_red_cause(self):
        return _resolve_green(self)

    @field_validator("summary", "red_cause", mode="before")
    @classmethod
    def coerce_strings(cls, v: Any) -> Any:
        if v is None:
            return v
        return _coerce_str(v)

    @field_validator("results", mode="before")
    @classmethod
    def _coerce_results(cls, value: Any) -> Any:
        # A null results field is no results — the answer stated
        # none — not a malformed verdict.
        if value is None:
            return []
        return value


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
# Counted **by kind**, not as one number. Measured: a run came back with
# `normalised_verdicts: 2` and nothing could say whether the truth table had
# derived a missing `green`, coerced a contradictory one, or folded an object
# into evidence lines — three different facts about three different model
# behaviours, and the question C4 asked of that run was exactly which. A
# counter that cannot name what it counted answers "something happened".
_normalisations: dict[str, int] = {}

GREEN_DERIVED = "green_derived_from_red_cause"
GREEN_COERCED = "green_coerced_false_against_its_cause"
# Ruling D46 (1): an approval with nothing behind it — an empty validation
# assessment or an empty deliverable. The red_cause names which; this counts
# that it happened at all.
GREEN_REFUSED_NO_SUBSTANCE = "green_refused_no_substance"
EVIDENCE_FOLDED = "evidence_object_folded_to_lines"
COST_ESTIMATE_COERCED = "cost_estimate_string_coerced_to_float"
# Ruling D51 — the demotion kinds. Every demotion is counted here and
# surfaced in the run's record (normalised_by_kind), because a judgment
# that names no anchor carries no information about the request
# (convention 21), and a demotion that is silent stops anyone noticing
# when a serving stops anchoring its failures:
# - an unanchored ask quote: the asks model proposed a quote the
#   anchoring check cannot find in the request;
# - an unanchored dissent: a domain concern or review finding that
#   claims to fail the work with no anchor;
# - a red with no anchor after the schema's bounded retries: a
#   validator that returned red naming neither a failed ask, a request
#   quote nor a hazard;
# - a blocked_on entry with no ask: an implementer's refusal that
#   names no ask, and so routes nowhere;
# - a consistency note: numbers_consistent found figures that
#   disagree, and recorded it — out of the fold since the review
#   of 2026-10-14, so the disagreement is a note, never a veto.
UNANCHORED_ASK_QUOTE = "unanchored_ask_quote"
UNANCHORED_DISSENT = "unanchored_dissent"
RED_NO_ANCHOR = "red_with_no_anchor"
BLOCKED_ON_NO_ASK = "blocked_on_entry_names_no_ask"
CONSISTENCY_NOTE = "consistency_note"
# Ruling of 2026-10-15 (R1): coverage left the judges_agree
# fold. Its result is still recorded — a fail is counted here,
# a note, never a veto and never a revision trigger — the way
# consistency did on 2026-10-14.
COVERAGE_NOTE = "coverage_note"
# Ruling of 2026-10-15 (R2), amending D51 (3): a wrong_fact
# dissent — the answer gives something for an ask and the judge
# says it is false — anchors only through a source_quote that
# occurs in the request or the grounding the judge was given.
# Without one it is a note, counted here: the run cannot check
# the claim, so under D51 (5) it is unavailable, never blocking.
UNVERIFIED_DISSENT = "unverified_dissent"


def dissent_kind(kind: Any, hazard: bool = False) -> str:
    """The kind a dissent is read as (Ruling of 2026-10-15, R2).

    A dissent that states its kind — unmet_ask, wrong_fact or
    hazard — is read as it states it. One that states none is
    read as wrong_fact, the ruling's own default. A hazard the
    judge marked with the hazard bool but named no kind is read
    as a hazard, the hazard rule being unchanged. Anything else
    (an unrecognised word) is read as wrong_fact, so an unknown
    kind can never widen what a dissent may block on: wrong_fact
    is the kind that must show its source.
    """
    stated = str(kind or "").strip().lower()
    if stated in ("unmet_ask", "wrong_fact", "hazard"):
        return stated
    if hazard:
        return "hazard"
    return "wrong_fact"


def _count(kind: str) -> None:
    _normalisations[kind] = _normalisations.get(kind, 0) + 1


def count_normalisation(kind: str) -> None:
    """Record one normalization, by kind, from outside this module.

    The demotions Ruling D51 names happen in the phases and the free
    checks (autornd/engine/phases.py, autornd/graph/checks.py), which
    construct the verdicts that carry the demoted judgments. They count
    here, in the one place the run's record reads, so a demotion is
    visible in `normalised_by_kind` whatever module performed it.
    """
    _count(kind)


def normalisations() -> int:
    return sum(_normalisations.values())


def normalisations_by_kind() -> dict[str, int]:
    return dict(_normalisations)


def reset_normalisations() -> None:
    _normalisations.clear()


def _missing_substance(verdict: Any) -> str | None:
    """What an approval needs and did not get (Ruling D46 (1)), or None.

    The two verdicts that can approve carry their substance in different
    fields — a validation has `evidence`, an implementation has `summary` —
    and each gap names itself.
    """
    summary = getattr(verdict, "summary", None)
    if isinstance(summary, str) and not summary.strip():
        return "the implementation returned no deliverable"
    evidence = getattr(verdict, "evidence", None)
    # Ruling D49 (1), extending D46 (1) from empty to whitespace-only:
    # a list is an assessment only if one entry has content. ["   "]
    # held nothing the old `not evidence` could see, and a green built
    # on it shipped work nobody checked.
    if isinstance(evidence, list) and not any(
            isinstance(item, str) and item.strip() for item in evidence):
        return "the validator returned no assessment"
    return None


def _resolve_green(verdict: Any) -> Any:
    """The ruled truth table, applied after construction."""
    has_cause = bool((verdict.red_cause or "").strip())

    if verdict.green is None:
        verdict.green = not has_cause
        _count(GREEN_DERIVED)
    elif verdict.green and has_cause:
        # The conservative side. A false red costs an iteration; a false green
        # ships work nobody checked.
        verdict.green = False
        _count(GREEN_COERCED)
    elif not verdict.green and not has_cause:
        # The one case that loses information: something is wrong and the
        # verdict does not say what. The retry machinery exists to ask.
        raise ValueError(
            "a red verdict must name its cause in red_cause"
        )

    # Ruling D46 (1): green needs substance. An empty assessment approving
    # work and an empty deliverable approving itself are the same failure —
    # an approval that means nothing — and either resolves red with a cause
    # that names what was missing, counted under its own kind.
    if verdict.green:
        missing = _missing_substance(verdict)
        if missing:
            verdict.green = False
            verdict.red_cause = missing
            _count(GREEN_REFUSED_NO_SUBSTANCE)
    return verdict


def _natural_key(text: str) -> tuple:
    """Sort `criterion_2` before `criterion_10`, not after it.

    Plain lexical order puts "10" before "2", which would make the same dict
    fold into a different list depending on how many criteria a plan happened
    to have. Evidence order is what a human reads down; it has to be stable
    and it has to be right.
    """
    return tuple(int(part) if part.isdigit() else part.lower()
                 for part in re.split(r"(\d+)", text))


def _fold_evidence(value: Any) -> Any:
    """Accept the shape a live serving actually returns for `evidence`.

    **The exhibit.** Measured twice in one run (§18.1, `numeric_consistency`,
    OpenInference), the validator returned its evidence as an object keyed by
    criterion rather than a list of strings:

        {"criterion_1": "FAIL — the clearance table omits two combinations",
         "criterion_2": "PASS — the CTE is cited to ISO 286-2"}

    Twice rejected, twice re-asked with the type error fed back, and correct
    only on the third attempt. Two of eleven engineering calls in that run
    bought nothing, and at a measured 41 s per call each avoided retry is about
    41 seconds of a run budget that expires on the clock before it exhausts its
    money — which is what B7 turned out to be.

    **Convention 21.** Shape variance that preserves information is coerced
    deterministically and counted; shape variance that loses it is rejected. A
    criterion-keyed object loses nothing — the key is part of the finding — so
    it folds into `"key: value"` lines. Anything whose keys or values are not
    text does lose something, or means something this cannot know, so it is
    refused and the retry asks. No other field is coerced on speculation: the
    exhibit comes first, and the rejection log is what produces exhibits.
    """
    if isinstance(value, dict):
        if not all(isinstance(k, str) for k in value):
            raise ValueError(_EVIDENCE_SHAPES)
        if not all(isinstance(v, str) for v in value.values()):
            raise ValueError(_EVIDENCE_SHAPES)
        _count(EVIDENCE_FOLDED)
        return [f"{k}: {value[k]}" for k in sorted(value, key=_natural_key)]

    if isinstance(value, list) and not all(isinstance(x, str) for x in value):
        raise ValueError(_EVIDENCE_SHAPES)

    return value


_EVIDENCE_SHAPES = (
    "evidence must be either a list of strings, or an object whose keys and "
    "values are all strings (it is folded into \"key: value\" lines). A list "
    "mixing strings with other types, or an object with non-string keys or "
    "values, is not accepted — put each finding in its own string."
)


class ValidateVerdict(BaseModel):
    # Optional and resolved, for the reason recorded above. Validate's prompt
    # carries the identical contract to implement's, verified before this was
    # applied to it: "green: true if every success criterion is satisfied;
    # red_cause: null if green, otherwise the specific failure cause".
    green: Optional[bool] = None
    red_cause: Optional[str] = None
    # A criterion-keyed object is folded into "key: value" lines rather than
    # refused — measured twice on one live serving, costing two of eleven
    # engineering calls in that run. See _fold_evidence for the exhibit and
    # convention 21. At a measured 41 s per call, each avoided retry is about
    # 41 seconds of a run budget that expires on the clock, not on money.
    evidence: list[str] = Field(default_factory=list)
    # Ruling D51 (3), text (R-d): a red names the ask it fails
    # (its number), or quotes the request's own words for what the
    # answer gets wrong or leaves out, or is a hazard. Only an
    # anchored red fails the work; a red with no anchor is demoted
    # to a note before it lands (counted under red_with_no_anchor).
    failed_ask: int | None = None
    anchor_quote: str = ""
    hazard: bool = False
    # The review of 2026-10-14: when hazard is true, the answer's
    # own words that state or instruct it, verbatim. The validator's
    # hazard anchors only when these words occur in the answer the
    # judge was given; a hazard without them is a note, counted as
    # unanchored dissent, not a veto.
    hazard_quote: str = ""
    # Ruling of 2026-10-15 (R2), amending D51 (3): the
    # dissent's kind — unmet_ask, wrong_fact or hazard —
    # and, for a wrong_fact, the request's or the
    # grounding's own words that contradict the answer,
    # verbatim. Stored as stated; the effective kind is
    # derived by dissent_kind, and a wrong_fact anchors
    # only through a source_quote the free check finds.
    kind: str = ""
    source_quote: str = ""
    # Ruling D51 (5): asks whose verification needs what the run
    # does not have. Unavailable is neither pass nor fail, never
    # blocking, and listed in the run's record.
    unavailable_asks: list[int] = Field(default_factory=list)

    @field_validator("evidence", mode="before")
    @classmethod
    def _accept_the_shape_a_serving_returns(cls, value: Any) -> Any:
        return _fold_evidence(value)

    @field_validator("anchor_quote", "hazard_quote", "source_quote",
                     mode="before")
    @classmethod
    def _coerce_anchor_quote(cls, value: Any) -> str:
        if value is None:
            return ""
        return value if isinstance(value, str) else _coerce_str(value)

    @field_validator("kind", mode="before")
    @classmethod
    def _coerce_kind(cls, value: Any) -> str:
        # Stored as stated: the record shows what the judge
        # declared. The effective kind — what an unstated or
        # unrecognised kind is read as — is derived at the
        # point of use, by dissent_kind. A judge that answers
        # "kind": null has stated no kind, and the ruling
        # reads an unstated kind as wrong_fact: the parse
        # carries it, never crashes on it. Measured live on
        # the smoke run's first unit (2026-10-16): the
        # validate judge, finding nothing false in a correct
        # answer, answered kind: null and the string-typed
        # field refused it before the ruling's fallback could
        # read it, blocking the unit on the parse. The domain
        # concern and the review finding already coerce the
        # same null; this is the third model R2 armed.
        if value is None:
            return ""
        return value if isinstance(value, str) else _coerce_str(value)

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
    # Ruling D51 (3), text (R-e): a finding blocks only when it is
    # critical or high AND anchored — it names the ask it concerns
    # by number, quotes the request's own words, or is a hazard. An
    # unanchored critical or high finding is demoted to a note at
    # severity medium before the blocking decision (counted under
    # unanchored_dissent).
    ask: int | None = None
    quote: str = ""
    hazard: bool = False
    # The review of 2026-10-14: when hazard is true, the answer's
    # own words that state or instruct it, verbatim. The finding's
    # hazard anchors only when these words occur in the answer the
    # judge was given; a hazard without them is a note, counted as
    # unanchored dissent, not a block.
    hazard_quote: str = ""
    # Ruling of 2026-10-15 (R2), amending D51 (3): the
    # dissent's kind — unmet_ask, wrong_fact or hazard —
    # and, for a wrong_fact, the request's or the
    # grounding's own words that contradict the answer,
    # verbatim. Stored as stated; the effective kind is
    # derived by dissent_kind, and a wrong_fact anchors
    # only through a source_quote the free check finds.
    kind: str = ""
    source_quote: str = ""

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

    @field_validator("lens", "severity", "detail", "hazard_quote",
                     "source_quote", mode="before")
    @classmethod
    def coerce_to_text(cls, value: Any) -> Any:
        if value is None:
            return ""
        return value if isinstance(value, str) else _coerce_str(value)

    @field_validator("kind", mode="before")
    @classmethod
    def _coerce_kind(cls, value: Any) -> str:
        # Stored as stated; the effective kind is derived
        # at the point of use, by dissent_kind.
        if value is None:
            return ""
        return value if isinstance(value, str) else _coerce_str(value)


class ReviewVerdict(BaseModel):
    ship: bool
    findings: list[ReviewFinding] = Field(default_factory=list)
    verdict: str = Field(description="Final synthesis statement")
    # Ruling D42: reviewers that failed twice, with their failure class. They
    # are not findings and never block; the quorum below decides whether the
    # review completed. Set by the aggregation, never by a model.
    not_reviewed: list[dict[str, str]] = Field(default_factory=list)
    reviewers_assigned: int | None = None
    reviewers_completed: int | None = None

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
    # Ruling D57 (2): an issue is a ReviewFinding, so it carries its anchor
    # in the same typed fields a review finding does. A bare string still
    # loads, as its detail, and anchors nothing. run_doublecheck keeps here
    # only the anchored issues and moves the rest to notes.
    critical_issues: list[ReviewFinding] = Field(default_factory=list)
    notes: list[ReviewFinding] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    verdict: str

    @property
    def vetoed(self) -> bool:
        """Ruling D48 (3): the gate's typed veto.

        True only when the check RAN and said do not ship — a computed
        property, not a field, so the schema and the model's output are
        unchanged. A skip records no ship at all and vetoes nothing; the gate
        reads this same path on both branches (`not independent_check.vetoed`),
        so a skipped check and a shipped one pass, and only a real do-not-ship
        blocks the run.
        """
        return not self.ship


class EscalationRuling(BaseModel):
    """One escalation ruling on one open dissent (Ruling D51 (6)).

    `dissent` is the dissent's number in the run's dissent ledger —
    the counter the adapter keeps, one per anchored dissent, the same
    number the iteration record and the failure log carry. `upheld`
    decides whether the directive addresses it.
    """

    dissent: int
    upheld: bool
    reason: str = ""


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
    # Ruling D51 (6): one ruling per open dissent — {"dissent":
    # <number>, "upheld": true|false, "reason": "<one line>"}.
    # The directive addresses only the upheld dissents; a dissent
    # the escalation does not uphold is a note about the work, not
    # a fact about the request, and the revision is not spent on it.
    rulings: list[EscalationRuling] = Field(default_factory=list)


class QuotedPassage(BaseModel):
    """One passage a lookup quoted, and the page it says it is on (Ruling D56 (1)).

    `question` is the question's number in the lookup, counted from 1. The
    harness fetches `url` and looks for `text` in it; nothing here is taken
    on the model's word.
    """

    question: int = 1
    text: str
    url: str


class LookupVerdict(BaseModel):
    """A search lookup's reply (Ruling D56 (1)).

    `answer` is the prose every phase reads, as before. `quotes` are what the
    answer rests on, each to be found in its own page before the answer to
    its question counts as checked. An empty answer is a lookup that found
    nothing.
    """

    answer: str = ""
    quotes: list[QuotedPassage] = Field(default_factory=list)
