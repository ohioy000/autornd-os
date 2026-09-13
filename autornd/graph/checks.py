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

_NUMBER = re.compile(r"(?<![\w.])(\d+(?:\.\d+)?)\s*([a-zA-Z%$]{0,4})")


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
        for value, unit in _NUMBER.findall(text or ""):
            unit = unit.lower()
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
    amounts = [float(v) for v, u in _NUMBER.findall(text or "") if u in {"$", ""}]
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
