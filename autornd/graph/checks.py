"""Deterministic checks: the questions that have a right answer.

A `check` node runs one of these instead of a model call. They are free, they
are instant, and they are correct — three properties no prompt has. Whatever a
check can settle, the model never has to be asked, which is the whole of
"frugal and accurate": every question moved out of the model costs less *and*
is more reliable.

A check returns (passed, detail, data). `detail` is written for a human reading
a blocked workflow; `data` is exposed to later conditions as `<node_id>.<key>`.

Register new checks with @check("name"). Keep them honest: a check must be able
to be *wrong* in a way you could point at. Anything requiring judgement is an
`ai` node, not a check.
"""

from __future__ import annotations

import re
from typing import Any, Callable, Protocol

__all__ = ["CheckResult", "get_check", "registry", "check"]


class CheckResult(Protocol):
    passed: bool
    detail: str
    data: dict[str, Any]


class Result:
    __slots__ = ("passed", "detail", "data")

    def __init__(self, passed: bool, detail: str = "", **data: Any) -> None:
        self.passed = passed
        self.detail = detail
        self.data = data

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"Result(passed={self.passed}, detail={self.detail!r}, data={self.data!r})"


registry: dict[str, Callable[..., Result]] = {}


def check(name: str) -> Callable[[Callable[..., Result]], Callable[..., Result]]:
    def register(fn: Callable[..., Result]) -> Callable[..., Result]:
        if name in registry:
            raise ValueError(f"check '{name}' is already registered")
        registry[name] = fn
        return fn

    return register


def get_check(name: str) -> Callable[..., Result]:
    try:
        return registry[name]
    except KeyError:
        raise KeyError(
            f"no check named '{name}'; registered: {sorted(registry)}"
        ) from None


# ── helpers ───────────────────────────────────────────────────────────────

# Words too common to carry meaning when matching a criterion to prose.
_STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "by", "for", "from", "has",
    "have", "in", "is", "it", "its", "must", "not", "of", "on", "or", "should",
    "that", "the", "then", "this", "to", "was", "were", "will", "with", "within",
    "all", "any", "each", "every", "no", "shall",
}

# The unit capture is a whole word, not four characters: truncating "5 second"
# to "seco" made it a different unit from "60s" and hid a real contradiction
# between a plan and its implementation.
_NUMBER = re.compile(r"(?<![\w.])(\d+(?:\.\d+)?)\s*([a-zA-Z%$µΩ°]*)")

# Written forms of the same unit must compare equal, or a check that exists to
# catch "the plan says 60s and the code says 5 seconds" never fires.
_UNIT_ALIASES = {
    "s": "s", "sec": "s", "secs": "s", "second": "s", "seconds": "s",
    "ms": "ms", "millisecond": "ms", "milliseconds": "ms",
    "min": "min", "mins": "min", "minute": "min", "minutes": "min",
    "h": "h", "hr": "h", "hrs": "h", "hour": "h", "hours": "h",
    "v": "v", "volt": "v", "volts": "v",
    "mv": "mv", "millivolt": "mv", "millivolts": "mv",
    "a": "a", "amp": "a", "amps": "a", "ampere": "a", "amperes": "a",
    "ma": "ma", "milliamp": "ma", "milliamps": "ma",
    "w": "w", "watt": "w", "watts": "w",
    "hz": "hz", "hertz": "hz",
    "khz": "khz", "kilohertz": "khz",
    "mhz": "mhz", "megahertz": "mhz",
    "ghz": "ghz", "gigahertz": "ghz",
    "b": "b", "byte": "b", "bytes": "b",
    "kb": "kb", "mb": "mb", "gb": "gb", "tb": "tb",
    "m": "m", "meter": "m", "meters": "m", "metre": "m", "metres": "m",
    "km": "km", "kilometer": "km", "kilometers": "km",
    "mm": "mm", "cm": "cm",
    "c": "c", "celsius": "c", "degc": "c", "°c": "c",
    "%": "%", "$": "$",
}


def _canonical_unit(raw: str) -> str:
    """One spelling per unit, so written and symbolic forms compare equal.

    An unrecognised word is kept as itself, with a trailing plural stripped:
    "3 retries" and "3 retry" are the same claim, and comparing them is still
    worth doing even though "retry" is not a unit.
    """
    unit = raw.strip().lower()
    if not unit:
        return ""
    if unit in _UNIT_ALIASES:
        return _UNIT_ALIASES[unit]
    return unit[:-3] + "y" if unit.endswith("ies") else unit.rstrip("s") or unit


def _normalize(value: str) -> str:
    """'60.0' and '60' are the same number; '60' and '600' are not.

    Stripping trailing zeros textually would collapse the second pair too,
    which silently hid a plan/implementation contradiction.
    """
    number = float(value)
    return str(int(number)) if number.is_integer() else str(number)


def _terms(text: str) -> set[str]:
    """Significant lowercase terms: words over two characters, plus any number."""
    words = re.findall(r"[A-Za-z_][\w\-]*|\d+(?:\.\d+)?", text.lower())
    return {w for w in words if len(w) > 2 and w not in _STOPWORDS}


# ── checks ────────────────────────────────────────────────────────────────

@check("judges_agree")
def judges_agree(**judges: Any) -> Result:
    """Green only if every judge the loop produced says green.

    The exit condition used to read one verdict. Measured 2026-09-14 on the
    `requires_execution` trace (n=1, and it only takes one): validate returned
    green while `implement.green` sat False in the same state — the domain
    reviewer had flagged a critical concern and flipped it — and the loop exited
    satisfied. Reading validate's own evidence afterwards showed it had marked
    a criterion PASS while stating in the same sentence that the test case had
    been changed from the demanded 101 req/s to 121. Two of the judges present
    were right, one was wrong, and `until` consulted the wrong one.

    So the loop stops when they agree, not when the most optimistic one does.
    Each argument is one judge's green signal: a bool, or a check `Result`,
    or anything else truthy — resolved from the workflow file, so a loop folds
    exactly the judges its own body produces and no list here needs updating
    when a body changes.

    A missing judge is not treated as agreement. `resolve_args` already raises
    on a path that does not exist, which is the loud failure a silently-absent
    judge would deserve anyway.
    """
    if not judges:
        return Result(False, "no judges to fold — refusing to call that agreement")

    def verdict(value: Any) -> bool:
        passed = getattr(value, "passed", None)
        return bool(passed if passed is not None else value)

    dissenting = sorted(name for name, value in judges.items() if not verdict(value))
    if dissenting:
        return Result(
            False,
            "not agreed — " + ", ".join(f"{n} is red" for n in dissenting),
            green=False, dissenting=dissenting, judges=sorted(judges),
        )
    return Result(
        True, f"all {len(judges)} judges agree",
        green=True, dissenting=[], judges=sorted(judges),
    )


@check("blocked_on_unmet")
def blocked_on_unmet(blocked_on: list[str], criteria: list[str]) -> Result:
    """Did the implementer refuse on a criterion the plan itself demands?

    The B13 honest-refusal gate (Blueprint 016 B2/B3). `blocked_on` is the
    implementer's ruled channel for saying "this criterion cannot be honestly
    satisfied with what is available". The ruled loop semantics: a block naming
    a plan success criterion routes to escalation immediately, because the
    measured alternative was six iterations of fabricating citations against an
    impossible criterion. A block that names NO plan criterion is the
    implementer's judgement about something else, and the loop treats it like
    any other dissent — the fold judges it.

    Three deterministic ways an entry names a criterion, all deliberately
    uncalibrated because no live corpus of refusals exists yet:

    - by index — "criterion 2", "criterion_2", "Criteria 2" — any spelling,
      with the number inside the plan's range;
    - by containment — the significant terms of the entry are a subset of a
      criterion's (a quote or fragment), or the criterion's are a subset of the
      entry's (a full restatement). Single significant terms match, on purpose:
      a one-word entry like "backoff" naming the backoff criterion is a
      reference.
    - by shared majority — at least half of the smaller term set appears in the
      larger. The exhibit is the first scripted paraphrase this check met,
      "cannot provide a citable source for each claim": three of its five
      significant terms are criterion 1's, and a pure subset rule matched
      nothing. A real refusal carries filler the criterion does not have, so
      subset-only was the check's fault, not the entry's (convention 17). Half
      of the smaller set is the deterministic line, and it is pinned from both
      sides in tests/test_blocked_on.py.

    The bias throughout is toward matching. A false positive routes to
    escalation — honest and bounded. A false negative continues the fabrication
    loop — the measured harm. No stemming: "capped" and "cap" are different
    terms, and pretending otherwise is a leniency with no exhibit behind it.
    """
    entries = [str(b).strip() for b in (blocked_on or []) if str(b).strip()]
    if not entries:
        return Result(True, "nothing blocked on", blocked=[])

    criteria = list(criteria or [])
    wanted = [(i + 1, _terms(c)) for i, c in enumerate(criteria)]

    def names_a_criterion(entry: str) -> bool:
        for m in _CRITERION_REF.finditer(entry):
            n = int(m.group(1))
            if 1 <= n <= len(criteria):
                return True
        entry_terms = _terms(entry)
        if not entry_terms:
            return False
        for _, criterion_terms in wanted:
            if not criterion_terms:
                continue
            smaller, larger = sorted((entry_terms, criterion_terms), key=len)
            if smaller <= larger:
                return True
            overlap = len(smaller & larger)
            if overlap * 2 >= len(smaller):
                return True
        return False

    matched = [e for e in entries if names_a_criterion(e)]
    if matched:
        return Result(
            False,
            "implementation names a plan criterion it cannot satisfy: "
            + "; ".join(matched),
            blocked=matched,
        )
    return Result(
        True,
        "no blocked entry names a plan criterion — the fold will judge them",
        blocked=[],
    )


# "criterion 3", "criterion_3", "Criteria 3", "CRITERION-3" — one spelling.
_CRITERION_REF = re.compile(r"criteri(?:a|on)[_\s\-]*(\d+)", re.IGNORECASE)


@check("criteria_addressed")
def criteria_addressed(
    criteria: list[str], text: str, threshold: float = 0.5
) -> Result:
    """Does the implementation visibly address every success criterion?

    Term overlap, not comprehension: this cannot tell you a criterion was met,
    only that the implementation never mentions what the criterion is about.
    That is a cheap, reliable signal — an implementation that never uses the
    word "backoff" has not addressed a backoff criterion — and it catches the
    failure we kept hitting, where work drifts off the plan without anyone
    noticing until a model reads it three phases later.
    """
    if not criteria:
        return Result(False, "no success criteria to check against")

    body = _terms(text or "")
    missed: list[str] = []
    coverage: dict[str, float] = {}

    for criterion in criteria:
        wanted = _terms(criterion)
        if not wanted:
            continue
        overlap = len(wanted & body) / len(wanted)
        coverage[criterion] = round(overlap, 2)
        if overlap < threshold:
            missed.append(criterion)

    if missed:
        listed = "; ".join(f"{c!r} ({coverage[c]:.0%} of its terms appear)" for c in missed)
        return Result(
            False,
            f"{len(missed)} of {len(criteria)} success criteria are not visibly "
            f"addressed by the implementation: {listed}",
            missed=missed, coverage=coverage, addressed=len(criteria) - len(missed),
        )
    return Result(
        True,
        f"all {len(criteria)} success criteria are addressed",
        missed=[], coverage=coverage, addressed=len(criteria),
    )


@check("numbers_consistent")
def numbers_consistent(plan: str, implementation: str) -> Result:
    """Do values carried from the plan into the implementation still agree?

    Looks for `<number><unit>` pairs that share a unit and differ in value —
    the plan capping something at 60s while the implementation sets 600s. It
    reports contradictions, never absence: a plan value the implementation
    simply does not mention is not a conflict.
    """
    def indexed(text: str) -> dict[str, set[str]]:
        found: dict[str, set[str]] = {}
        for value, raw_unit in _NUMBER.findall(text or ""):
            unit = _canonical_unit(raw_unit)
            if not unit:
                continue
            found.setdefault(unit, set()).add(_normalize(value))
        return found

    planned, built = indexed(plan), indexed(implementation)
    conflicts = [
        f"{unit}: plan says {sorted(planned[unit])}, implementation says {sorted(built[unit])}"
        for unit in planned.keys() & built.keys()
        if planned[unit] != built[unit] and not (planned[unit] & built[unit])
    ]

    if conflicts:
        return Result(
            False,
            "values disagree between plan and implementation — " + "; ".join(conflicts),
            conflicts=conflicts,
        )
    return Result(True, "no contradicting values between plan and implementation",
                  conflicts=[])


@check("totals_reconcile")
def totals_reconcile(text: str, tolerance: float = 0.01) -> Result:
    """Does a stated total match the numbers said to add up to it?

    Matches "total ... 47.20" against the currency amounts preceding it. Purely
    arithmetic, and exactly the kind of thing the original design wanted checked
    and that nobody should pay a reasoning model to do.
    """
    amounts = [float(v) for v, u in _NUMBER.findall(text or "")
               if _canonical_unit(u) in {"$", ""}]
    stated = re.search(r"total[^0-9$]{0,20}\$?\s*(\d+(?:\.\d+)?)", text or "", re.I)
    if not stated or len(amounts) < 2:
        return Result(True, "no stated total to reconcile", checked=False)

    claimed = float(stated.group(1))
    parts = [a for a in amounts if abs(a - claimed) > 1e-9]
    if not parts:
        return Result(True, "no component values to sum", checked=False)

    summed = sum(parts)
    if abs(summed - claimed) <= max(tolerance, claimed * tolerance):
        return Result(True, f"components sum to the stated total ({claimed})",
                      checked=True, claimed=claimed, summed=round(summed, 4))
    return Result(
        False,
        f"stated total {claimed} does not match the sum of its parts "
        f"({round(summed, 4)}, from {len(parts)} values)",
        checked=True, claimed=claimed, summed=round(summed, 4),
    )
