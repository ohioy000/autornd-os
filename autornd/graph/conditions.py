"""A deliberately small expression language for graph conditions.

Conditions decide whether a node runs and when a loop stops, so they are
evaluated constantly and are written by whoever defines the workflow. That
rules out `eval`: a workflow file is configuration, and configuration must not
be able to execute arbitrary code.

The grammar is one comparison:

    <path> <op> <literal>        validate.green == true
    <path>                       plan.ready          (truthiness)
    not <path>                   not plan.ready

where <path> is a dotted lookup into node outputs (`triage.risk`,
`plan.success_criteria`), <op> is one of == != < <= > >= in, and <literal> is
a quoted string, number, true/false/null, or a [comma, separated, list].
"""

from __future__ import annotations

import re
from typing import Any

__all__ = ["ConditionError", "evaluate", "resolve_path"]


class ConditionError(ValueError):
    """A condition is malformed, or references something that does not exist."""


_COMPARISON = re.compile(
    r"^\s*(?P<left>[A-Za-z_][\w.]*)\s*"
    r"(?P<op>==|!=|<=|>=|<|>|\bin\b)\s*"
    r"(?P<right>.+?)\s*$"
)
_PATH_ONLY = re.compile(r"^\s*(?P<neg>not\s+)?(?P<path>[A-Za-z_][\w.]*)\s*$")

_LITERALS: dict[str, Any] = {"true": True, "false": False, "null": None, "none": None}


def resolve_path(path: str, scope: dict[str, Any]) -> Any:
    """Walk a dotted path through dicts and objects. Missing keys raise."""
    current: Any = scope
    walked: list[str] = []
    for part in path.split("."):
        walked.append(part)
        if isinstance(current, dict):
            if part not in current:
                raise ConditionError(
                    f"'{'.'.join(walked)}' is not available; "
                    f"known at this level: {sorted(current)}"
                )
            current = current[part]
        else:
            if not hasattr(current, part):
                raise ConditionError(f"'{'.'.join(walked)}' is not available")
            current = getattr(current, part)
    return current


def _literal(raw: str) -> Any:
    text = raw.strip()
    if text.lower() in _LITERALS:
        return _LITERALS[text.lower()]
    if len(text) >= 2 and text[0] == text[-1] and text[0] in "\"'":
        return text[1:-1]
    if text.startswith("[") and text.endswith("]"):
        inner = text[1:-1].strip()
        return [_literal(p) for p in inner.split(",")] if inner else []
    try:
        return int(text)
    except ValueError:
        pass
    try:
        return float(text)
    except ValueError as exc:
        raise ConditionError(
            f"cannot read {text!r} as a value; quote it if it is a string"
        ) from exc


def evaluate(condition: str, scope: dict[str, Any]) -> bool:
    """Evaluate a condition against node outputs, returning a bool."""
    if not condition or not condition.strip():
        raise ConditionError("condition is empty")

    bare = _PATH_ONLY.match(condition)
    if bare:
        value = resolve_path(bare.group("path"), scope)
        return not bool(value) if bare.group("neg") else bool(value)

    match = _COMPARISON.match(condition)
    if not match:
        raise ConditionError(
            f"cannot parse condition {condition!r}. Expected "
            f"'<path> <op> <value>', for example 'validate.green == true'"
        )

    left = resolve_path(match.group("left"), scope)
    op = match.group("op").strip()
    right = _literal(match.group("right"))

    try:
        if op == "==":
            return left == right
        if op == "!=":
            return left != right
        if op == "in":
            return left in right  # type: ignore[operator]
        if op == "<":
            return left < right
        if op == "<=":
            return left <= right
        if op == ">":
            return left > right
        return left >= right
    except TypeError as exc:
        raise ConditionError(
            f"cannot compare {left!r} {op} {right!r} — incompatible types"
        ) from exc
