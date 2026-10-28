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
from collections import Counter
from typing import Any, Callable, Protocol

__all__ = ["CheckResult", "get_check", "registry", "check"]

from autornd.models.verdicts import (
    BLOCKED_ON_NO_ASK,
    CONSISTENCY_NOTE,
    COVERAGE_NOTE,
    UNANCHORED_ASK_QUOTE,
    count_normalisation,
    dissent_kind,
    normalise_key,
)


class CheckResult(Protocol):
    passed: bool
    checked: bool
    detail: str
    data: dict[str, Any]


class Result:
    __slots__ = ("passed", "detail", "data", "checked")

    def __init__(self, passed: bool, detail: str = "", *,
                 checked: bool = True, **data: Any) -> None:
        self.passed = passed
        self.detail = detail
        # Ruling D46 (3): did this check actually compare anything? A check
        # whose inputs were empty says so — it still reports its pass or fail
        # exactly as before, but it is recorded as NOT CHECKED, the fold
        # treats it as non-blocking, and the run's record lists it.
        # Also kept in `data`, which is how check outputs reach later
        # conditions and the run record (totals_reconcile has read it there
        # since it was written).
        self.checked = checked
        self.data = data
        self.data.setdefault("checked", checked)

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return (f"Result(passed={self.passed}, checked={self.checked}, "
                f"detail={self.detail!r}, data={self.data!r})")


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

# F2 (ARCH-20261001-104): numbers_consistent reads a figure whole. _NUMBER's
# lookbehind admits a number straight after '^' or ',', so 102's Q3 plan
# '80.0 × 10^9 Pa' was read as 9 Pa, and the implementation's '20,371,800 Pa'
# as 800 Pa: a false conflict that dissented on a correct answer. This
# pattern takes digit groups, decimals and an exponent (x10^n, ×10ⁿ, e±n) as
# one figure, and never starts inside one. _NUMBER is kept for
# totals_reconcile, which F2 does not touch.
_SUPERSCRIPT = str.maketrans("⁰¹²³⁴⁵⁶⁷⁸⁹⁻", "0123456789-")
_FIGURE = re.compile(
    r"(?<![\w.,^⁰¹²³⁴⁵⁶⁷⁸⁹])"
    r"(\d{1,3}(?:,\d{3})+|\d+)(\.\d+)?"
    r"(?:\s*[×xX*]\s*10\s*(?:\^\s*([-−]?\d+)|([⁻]?[⁰¹²³⁴⁵⁶⁷⁸⁹]+))"
    r"|[eE]([-+]?\d+)(?![a-zA-Z]))?"
    r"\s*([a-zA-Z%$µΩ°]*)")


def _figures(text: str) -> list[tuple[float, int, str]]:
    """Every (value, significant figures, raw unit) written in the text."""
    out = []
    for whole, frac, caret, sup, e_exp, unit in _FIGURE.findall(text or ""):
        digits = whole.replace(",", "") + (frac or "")
        mantissa = float(digits)
        exp = caret.replace("−", "-") if caret else (
            sup.translate(_SUPERSCRIPT) if sup else e_exp)
        value = mantissa * (10 ** int(exp)) if exp else mantissa
        significant = len(digits.replace(".", "").lstrip("0")) or 1
        out.append((value, significant, unit))
    return out


def _agree(a: tuple[float, int], b: tuple[float, int]) -> bool:
    """Equal at the precision of the less precise figure: 20.4 and 20.3718
    agree; 80.0 and 70.0 do not."""
    (x, sx), (y, sy) = a, b
    if x == y:
        return True
    if x == 0 or y == 0:
        return False
    figures = min(sx, sy)
    return float(f"{x:.{figures}g}") == float(f"{y:.{figures}g}")

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


# ── anchors (Ruling D51 (1), (3)) ─────────────────────────────────
#
# The asks are the yardstick, and every dissent that fails work
# must point at the request's own words. Two primitives serve
# both the free check that anchors the asks and the phases that
# anchor dissents, so a quote anchors the same way everywhere:
# the matcher below is asks_anchored's own matcher, and the
# phases import it rather than re-deriving it.

def _normalise_quote(text: str) -> str:
    """The normalisation the checks apply to a quote.

    Case-folded, whitespace-collapsed, and LaTeX-stripped: the
    '$' math delimiters, the \\, \\; \\: \\! and "\\ " spacing
    commands, the degree forms, the \\mathrm/\\text/\\textrm
    wrappers and the braces they leave behind. A quote wrapped
    for math mode anchors the words it wraps — "a
    $600\\,\\mathrm{s}$ timer" normalises to "a 600 s timer",
    which is the request's own words. The review of 2026-10-14:
    the old three-step normalisation left LaTeX-wrapped quotes
    unanchored, so a validator quoting the request's math could
    not anchor it. The floor a quote must clear is unchanged.
    """
    text = str(text or "").replace("$", "")
    for command in (r"\,", r"\;", r"\:", r"\!", "\\ "):
        text = text.replace(command, " ")
    text = text.replace(r"^{\circ}", "°").replace(r"^\circ", "°")
    text = re.sub(r"\\(?:mathrm|text|textrm)\{([^{}]*)\}", r"\1", text)
    text = text.replace("{", "").replace("}", "")
    return " ".join(text.casefold().split())


# The floor a quote must clear before it anchors anything: at
# least 3 words and 12 characters after normalisation. Below it,
# a quote like "mm" or "the answer" anchors by accident — any
# request of a dozen words contains "the answer" somewhere — and
# an anchor that short cannot name what the answer gets wrong.
# Pinned from both sides in tests/test_anchor_floor.py.
_ANCHOR_MIN_WORDS = 3
_ANCHOR_MIN_CHARS = 12


def quote_anchors(quote: str, request: str) -> bool:
    """Does this quote occur in the request, as written?

    Ruling D51 (1): a quote anchors only when the free check
    finds it in the request under the normalisation the checks
    already apply, and it clears the floor. A paraphrase does not
    anchor — the yardstick cannot drift off the request's words —
    and a quote under the floor anchors nothing.
    """
    needle = _normalise_quote(quote)
    if not needle:
        return False
    if len(needle.split()) < _ANCHOR_MIN_WORDS:
        return False
    if len(needle) < _ANCHOR_MIN_CHARS:
        return False
    return needle in _normalise_quote(request)


def dissent_anchored(
    ask: Any, quote: str, hazard: bool,
    asks: list[Any] | None, request: str,
    answer: str = "", hazard_quote: str = "",
    kind: str = "", source_quote: str = "",
    grounding: str = "",
) -> bool:
    """Is this dissent anchored? (Ruling D51 (3); the review
    of 2026-10-14: a hazard anchors only when quoted; the
    ruling of 2026-10-15, R2: a wrong_fact anchors only
    through its source.)

    The kind decides the anchor, and a dissent that states
    no kind is read as wrong_fact (dissent_kind). unmet_ask
    — the answer gives nothing for the ask — anchors by the
    ask's number in the anchored asks, or by a quote of the
    request's own words under the same free check the asks
    pass. hazard anchors only through the answer's own words
    that state or instruct it — `hazard_quote`, anchored
    against the answer the judge was given; a hazard the
    judge did not quote is a note. wrong_fact — the answer
    gives something for the ask and the judge says it is
    false — anchors only through `source_quote`: words of
    the request or of the grounding the judge was given that
    contradict the answer, verbatim, found by the same free
    check in the request or in the grounding text. Without
    an anchored source_quote the claim is a note, counted as
    unverified_dissent: the run cannot check the claim, so
    under D51 (5) it is unavailable, never blocking. An
    omission is never a hazard and never an anchor: if the
    request asked for what is missing, it is an ask, and
    the dissent names it by number.
    """
    effective = dissent_kind(kind, hazard)
    if effective == "hazard":
        if str(hazard_quote or "").strip():
            return quote_anchors(hazard_quote, answer)
        return False
    if effective == "unmet_ask":
        if isinstance(ask, int) and not isinstance(ask, bool):
            if 1 <= ask <= len(asks or []):
                return True
        if str(quote or "").strip() and quote_anchors(quote, request):
            return True
        return False
    # wrong_fact — the ruling's default kind: the claim
    # shows its source, or it is a note.
    if str(source_quote or "").strip():
        if quote_anchors(source_quote, request):
            return True
        if str(grounding or "").strip():
            return quote_anchors(source_quote, grounding)
    return False


def _ask_field(ask: Any, key: str) -> Any:
    """Read a field off an ask, whichever shape it arrives in.

    The asks node's proposals are Ask models; the anchored asks that
    reach every judge are this check's dicts. Both carry the same
    fields, and the phases render either.
    """
    if isinstance(ask, dict):
        return ask.get(key)
    return getattr(ask, key, None)


# ── checks ──────────────────────────────────────────────────────────

@check("asks_anchored")
def asks_anchored(asks: list[Any], request: str) -> Result:
    """Which of the asks node's proposals anchor in the request?
    (Ruling D51 (1).)

    The asks node proposes; this free check disposes. A proposal
    anchors when its quote occurs in the request under the
    normalisation the checks already apply and clears the floor
    (three words, twelve characters) — the same primitives the
    phases use to anchor dissents, so an ask anchors the same way
    everywhere. A proposal that does not anchor is demoted: counted,
    never judged. The yardstick cannot drift off the request's own
    words, and a paraphrase of the request is not the request.

    When nothing anchors, the whole request is the one ask — the
    ruling's own fallback, word for word. It carries no kind: it is
    every kind at once, and a bracket would lie about which one it
    is. The Result carries `fallback` true in that case, so the
    coverage check that reads the anchored asks can recognize what
    it was given: the review of 2026-10-14 measured the fallback
    judged by word presence failing 5 of 7 correct answers on Q15,
    and coverage over a fallback ask is passed and NOT CHECKED —
    the whole request cannot be judged by the words it contains.

    The check never fails. It filters a proposal list; it does not
    judge work, so `passed` is vacuously true whatever anchors — a
    loop gate reading it would loop on the judges, not on the
    anchoring, and no shipped workflow gates on it.
    """
    anchored: list[dict[str, Any]] = []
    demoted: list[str] = []
    for proposal in asks or []:
        quote = str(_ask_field(proposal, "quote") or "").strip()
        if quote_anchors(quote, request):
            kind = _ask_field(proposal, "kind")
            anchored.append({
                "number": len(anchored) + 1,
                "quote": quote,
                "kind": str(getattr(kind, "value", kind) or "").strip(),
            })
        elif quote:
            demoted.append(quote)
            count_normalisation(UNANCHORED_ASK_QUOTE)
    fallback = not anchored
    if fallback:
        anchored = [{"number": 1, "quote": str(request), "kind": ""}]
    return Result(
        True,
        f"{len(anchored)} ask(s) anchored"
        + (f"; {len(demoted)} proposal(s) did not anchor"
           if demoted else ""),
        anchored=anchored,
        quotes=[a["quote"] for a in anchored],
        demoted=demoted,
        fallback=fallback,
    )


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

    def checked(value: Any) -> bool:
        """Ruling D46 (3): did this judge compare anything?

        Its record says checked false. Ruling D48 (1): that keeps it out of
        the "judges that checked" count and lists it, but a false verdict is a
        dissent however it was reached — only a pass needs to have checked.
        """
        if isinstance(value, dict):
            return bool(value.get("checked", True))
        return bool(getattr(value, "checked", True))

    def verdict(value: Any) -> bool:
        if isinstance(value, dict):
            passed = value.get("passed")
            return bool(passed if passed is not None else value)
        passed = getattr(value, "passed", None)
        return bool(passed if passed is not None else value)

    not_checked = sorted(name for name, value in judges.items() if not checked(value))
    # Ruling D48 (1): a judge dissents when its verdict is false, WHETHER OR
    # NOT it checked. An unchecked pass is not a dissent (its verdict is
    # true); an unchecked failure is, exactly as it was before D46 — the
    # correction to 111's constraint [4], which let a failing check that
    # compared nothing vote the work through.
    dissenting = sorted(
        name for name, value in judges.items() if not verdict(value))
    if dissenting:
        return Result(
            False,
            "not agreed — " + ", ".join(f"{n} is red" for n in dissenting)
            + (f"; unchecked: {', '.join(not_checked)}" if not_checked else ""),
            green=False, dissenting=dissenting, judges=sorted(judges),
            unchecked=not_checked,
        )
    agree = [n for n in judges if checked(judges[n])]
    if not not_checked:
        return Result(
            True, f"all {len(judges)} judges agree",
            green=True, dissenting=[], judges=sorted(judges),
            unchecked=not_checked,
        )
    return Result(
        True,
        f"all {len(agree)} judges that checked agree"
        f" ({', '.join(not_checked)} did not check)",
        green=True, dissenting=[], judges=sorted(judges),
        unchecked=not_checked,
    )


@check("blocked_on_unmet")
def blocked_on_unmet(blocked_on: list[Any], asks: list[Any],
                     request: str) -> Result:
    """Did the implementer refuse on an ask? (Ruling D51 (5).)

    The B13 honest-refusal gate, re-anchored. The old check asked
    "does this entry name a plan criterion" and matched by term
    overlap — a prose channel, and Ruling D51 retires the plan as
    a yardstick at the same time, so both its input and its matcher
    were wrong. An entry now names an ask in exactly two typed
    ways, never by prose:

    - by number — `ask` is an integer inside the anchored asks'
      range (1..len(asks));
    - by quote — `ask` is a string that anchors in the request
      under the same free check the asks themselves pass.

    An entry that names an ask routes the run to escalation
    immediately — the measured alternative was six iterations of
    fabricating citations against an impossible ask. An entry that
    names none is the implementer's judgement about something else:
    a note, counted (BLOCKED_ON_NO_ASK), recorded, and routed
    nowhere — the fold judges it like any other dissent.

    The bias toward matching is gone with the term overlap: a
    false positive now needs the request's own words or a number,
    and a false negative is a note, not a fabrication loop. The
    typed contract is pinned from both sides in
    tests/test_blocked_on.py.
    """
    asks = list(asks or [])
    entries = [b for b in (blocked_on or []) if b is not None]
    if not entries:
        return Result(True, "nothing blocked on", blocked=[])

    def names_an_ask(entry: Any) -> bool:
        ask = _ask_field(entry, "ask")
        if isinstance(ask, int) and not isinstance(ask, bool):
            return 1 <= ask <= len(asks)
        if isinstance(ask, str) and ask.strip():
            return quote_anchors(ask, request)
        return False

    def rendered(entry: Any) -> str:
        """The entry as the failure log and the gate read it: the
        ask it names, and its reason."""
        ask = _ask_field(entry, "ask")
        why = str(_ask_field(entry, "why") or "").strip()
        if isinstance(ask, int) and not isinstance(ask, bool):
            head = f"ask {ask}"
        else:
            # An anchored quote: the ask's own number when the
            # quote is one of the anchored asks verbatim, the
            # request's words otherwise — both name the ask.
            head = f"ask '{ask}'"
            for a in asks:
                if _normalise_quote(str(_ask_field(a, "quote") or "")) == \
                        _normalise_quote(ask):
                    head = f"ask {_ask_field(a, 'number')}"
                    break
        return f"{head}: {why}" if why else head

    named = [e for e in entries if names_an_ask(e)]
    for e in entries:
        if not names_an_ask(e):
            count_normalisation(BLOCKED_ON_NO_ASK)

    if named:
        return Result(
            False,
            "implementation names an ask it cannot satisfy: "
            + "; ".join(rendered(e) for e in named),
            blocked=[{"ask": _ask_field(e, "ask"),
                      "why": str(_ask_field(e, "why") or "")}
                     for e in named],
        )
    return Result(
        True,
        "no blocked entry names an ask — the fold will judge them",
        blocked=[],
    )


# ── criterion shape (ruling B17-R1, §29) ──────────────────────────────────
#
# Term overlap is a valid test only when a criterion is satisfied by the
# PRESENCE of the terms it names. Two other classes exist and the check used to
# treat all three identically, which killed a run: measured 2026-09-21 on the
# B14 demonstration, criterion 6 ("avoids the banned words ('leverage',
# 'seamless', 'robust', 'in today's fast-paced world')") carries 17 significant
# terms, 6 of which are tokens the criterion FORBIDS the draft to contain and 8
# more of which are meta-vocabulary about the rule. 14 of 17 are unreachable for
# a compliant draft, capping it at 65% against a 50% threshold; a correct draft
# scored 40%. Satisfying the criterion is what made it fail the check. The run
# died at the call ceiling — 42 calls, $0.1783, no terminal — with
# `implement.green` true on all seven iterations.
#
# The fix is not a threshold. 14/17 unreachable means no threshold separates
# compliant from non-compliant here, and lowering it would let through the class
# this check exists to catch: "names every topic while committing to nothing",
# measured at 0–33% against 71–100% for real work.

# A prohibition marker alone is not enough. Criterion 4 of the same plan — "No
# claim about a named competitor appears without a clear flag" — reads as a
# prohibition and has no forbidden tokens to test: it prohibits a *situation*,
# not a vocabulary. It scored 64% and passed on overlap, correctly. So the
# classification demands BOTH a marker and an extractable token list, and
# anything short of both falls back to presence, which fails closed.
_PROHIBITION_MARKER = re.compile(
    r"\b(?:avoid(?:s|ed|ing)?|banned|forbidden|prohibit(?:s|ed)?|disallow(?:s|ed)?"
    r"|excludes?|must\s+not|may\s+not|never\s+uses?|no\s+use\s+of"
    # -031 corpus: 1 occurrence, the -027 criterion — the only genuine
    # invertible prohibition in 597 distinct criteria (0.17%).
    r"|contains?\s+no\s+instances?\s+of"
    # -031 corpus: 2 occurrences (index criteria, no tokens, stays presence).
    r"|does\s+not\s+(?:include|contain)"
    r")\b",
    re.IGNORECASE,
)

# The one committed exhibit quotes its forbidden tokens inside parentheses. So
# that is the only form accepted, per convention 21 — exhibits precede leniency.
# An unquoted enumeration after "avoids" is NOT read as a token list, because
# nothing in the record shows one and guessing at it would widen the strongest
# test in the check on speculation.
_QUOTE_CHARS = "\"'\u2018\u2019\u201c\u201d"

# Field vocabulary: words that describe what an artifact CARRIES rather than
# words it contains. A real citation holds an organization's name, not the word
# "organization" — which is why criterion 3 scored 37% on a draft whose
# citations were complete. This is the form class.
_FIELD_VOCAB = frozenset({
    "author", "authors", "byline", "citation", "citations", "date", "identifier",
    "location", "organisation", "organization", "publisher", "source", "sources",
    "timestamp", "title", "url", "version",
})

# A field name on its own proves nothing — "the source of the regression" is not
# a form criterion. The structural verb is what turns a field list into a claim
# about an artifact's shape, and two distinct fields are demanded so that a
# single incidental noun cannot buy an abstention.
_STRUCTURAL_VERB = re.compile(
    r"\b(?:includ(?:e|es|ing)|contain(?:s|ing)?|accompanied\s+by|comprises?"
    r"|consist(?:s|ing)\s+of|in\s+the\s+form\s+of|formatted\s+as)\b",
    re.IGNORECASE,
)

PRESENCE, PROHIBITION, FORM = "presence", "prohibition", "form"

# Must-be-present signals (ARCH-20260922-040, Ruling D2). A quoted token after
# one of these is something the artifact MUST CONTAIN, not something it must
# avoid. Two kinds: clear-polarity (the criterion explicitly says to include
# the token) and ambiguous (an example or enumeration whose intent is mixed).
# Ruling D2: clear polarity → test by presence (term overlap); ambiguous →
# abstain. Measured over the 597-criterion corpus (-031): zero corpus criteria
# currently hit either case, so this is prophylaxis, not a live defect repair.
_CLEAR_MUST_PRESENT = re.compile(
    r"\b(?:must|should)\s+(?:include|contain|have|use)\b",
    re.IGNORECASE,
)
_AMBIGUOUS_MUST_PRESENT = re.compile(
    r"(?:\be\.g\.(?=[\s,;:)\]]|$)"
    r"|\b(?:for\s+example|such\s+as)\b)",
    re.IGNORECASE,
)

# Cardinality: a criterion asserting a count or numeric threshold. Term overlap
# cannot count, so R2'(b) clause (iii) abstains on these.
#
# Corpus-derived (-031): 34 criteria carry one of these forms. "exactly N" (10),
# "N%" (8), "at least N" (6), "up to N" (6), "greater/more than N" (5),
# "maximum/minimum of N" (2), "within N units" (1), "between N and M" (1).
# Word-form numbers (one…ten) are matched because the corpus uses them
# interchangeably with digits — "exactly one headline", "at least three
# concrete features".
_NUM = r"(?:\d+|one|two|three|four|five|six|seven|eight|nine|ten)"
_CARDINALITY = re.compile(
    r"\b(?:exactly|at\s+least|up\s+to|(?:greater|more|fewer|less)\s+than"
    r"|(?:maximum|minimum)\s+of|no\s+(?:more|fewer)\s+than"
    r"|between|within)\s+" + _NUM + r"\b"
    r"|\b\d+\s*%",
    re.IGNORECASE,
)

# Tier 1 compute (Ruling D3, D5, ARCH-20260922-037): word count is the one
# genuinely computable form in the corpus. "between 350 and 450 words" is the
# exhibited surface form (-027 criterion 3). The regex covers the corpus forms
# from -031: "between N and M words", "at least N words", "exactly N words",
# "up to / no more than N words", "greater/more than N words".
_WORD_BOUND = re.compile(
    r"(?:between\s+(\d+)\s+and\s+(\d+)"
    r"|at\s+least\s+(\d+)"
    r"|(?:exactly|precisely)\s+(\d+)"
    r"|(?:up\s+to|no\s+more\s+than|at\s+most)\s+(\d+)"
    r"|(?:(?:greater|more)\s+than)\s+(\d+)"
    r"|(?:(?:fewer|less)\s+than)\s+(\d+))"
    r"\s+words\b",
    re.IGNORECASE,
)


def _try_word_count(criterion: str, text: str) -> tuple[bool, str] | None:
    """If the criterion asserts a word count, compute it. None if not."""
    m = _WORD_BOUND.search(criterion)
    if not m:
        return None
    count = len(text.split())
    lo, hi = m.group(1), m.group(2)
    if lo and hi:
        ok = int(lo) <= count <= int(hi)
        return ok, f"word count {count}, required {lo}–{hi}"
    at_least = m.group(3)
    if at_least:
        ok = count >= int(at_least)
        return ok, f"word count {count}, required ≥{at_least}"
    exactly = m.group(4)
    if exactly:
        ok = count == int(exactly)
        return ok, f"word count {count}, required exactly {exactly}"
    at_most = m.group(5)
    if at_most:
        ok = count <= int(at_most)
        return ok, f"word count {count}, required ≤{at_most}"
    more_than = m.group(6)
    if more_than:
        ok = count > int(more_than)
        return ok, f"word count {count}, required >{more_than}"
    less_than = m.group(7)
    if less_than:
        ok = count < int(less_than)
        return ok, f"word count {count}, required <{less_than}"
    return None


# A token is QUOTED only when its opening mark sits at a boundary — start of the
# group, or after whitespace, a comma or an open bracket — and its closing mark
# is followed by a boundary. That is what separates a quotation from a
# possessive or a contraction, which are the same character mid-word.
#
# Measured 2026-09-22 over the 597-criterion corpus (B24, ARCH-20260922-031).
# The previous rule was "the group contains a quote character somewhere", and
# it produced forbidden tokens out of prose:
#
#   "avoids table locks (CrateDB's default non-blocking behavior)"
#       -> ["CrateDB's default non-blocking behavior"]
#   "avoids jargon (don't use it, it's bad)"
#       -> ["don't use it", "it's bad"]
#   "avoids competitor names without a note (e.g., 'Pending legal review')"
#       -> ["e.g.", "Pending legal review"]      <- "e.g." was never quoted
#
# Each of those is a FALSE PROHIBITION, and a false prohibition fails work that
# merely mentions the phrase while passing work that omits what the criterion
# actually required. That is the opposite direction from B17, which fails
# correct work: these pass incorrect work.
# The single-quote arm allows an apostrophe INSIDE the token when a word
# character follows it, so a contraction or possessive inside a genuine quoted
# token survives. Without that clause the pattern drops the fourth token of
# B17's own exhibit — "'in today's fast-paced world'" — which would trade one
# false-prohibition bug for a false-negative on the single genuine prohibition
# in the corpus.
_QUOTED_TOKEN = re.compile(
    r"""(?:(?<=^)|(?<=[\s,(\[]))       # opening mark sits at a boundary
        (?:'((?:[^']|'(?=\w))+)'
          |"([^"]+)"
          |‘([^’]+)’
          |“([^”]+)”)
        (?=$|[\s,.;:)\]])""",          # closing mark is followed by one
    re.VERBOSE,
)


def _forbidden_tokens(criterion: str) -> list[str]:
    """Tokens a prohibition criterion forbids, or [] if it names none.

    Tries parenthesised groups first, then falls back to quoted tokens anywhere
    after the marker. The parenthesised path takes the first group containing
    at least one properly QUOTED token. The fallback fires only when no
    parenthesised tokens exist — measured over the 597-criterion corpus (-031),
    zero existing marker-matched criteria have non-parenthesised quoted tokens,
    so the fallback is safe for the current corpus and catches new phrasings
    like the -027 criterion's "contains no instances of 'x', 'y'".

    The quote requirement is what keeps criterion 6's SECOND parenthesis —
    "(sentence case headings, no H4+, numbers as words below 10, dates as
    '12 March 2026')", which is a presence-shaped aside — from being read as a
    forbidden list.

    **Quoted means delimited, not merely containing a quote character** (B24).
    The earlier rule split the whole parenthetical on commas and stripped quote
    characters from each part, so a possessive, a contraction or an unquoted
    aside became a forbidden token. See the comment above `_QUOTED_TOKEN` for
    the three measured exhibits.

    **Polarity** (ARCH-20260922-040, Ruling D2): a quoted token that must be
    PRESENT rather than absent is not a forbidden token. In "avoids competitor
    names without a note (e.g., 'Pending legal review')" the token is a thing
    the work must contain; inverting it would pass work that omits the
    annotation and fail work that includes it. A parenthetical whose text
    contains a must-be-present signal (``_MUST_BE_PRESENT``) is skipped.

    **Word content** (ARCH-20260922-040): a token containing no word characters
    (purely punctuation, e.g. ``'...'`` or ``'---'``) is not a meaningful
    prohibition and is filtered out. If filtering leaves an empty list, the
    criterion abstains rather than testing against garbage.
    """
    marker = _PROHIBITION_MARKER.search(criterion)
    if not marker:
        return []
    tail = criterion[marker.end():]
    for group in re.finditer(r"\(([^()]*)\)", tail):
        group_text = group.group(1)
        if _CLEAR_MUST_PRESENT.search(group_text) or _AMBIGUOUS_MUST_PRESENT.search(group_text):
            continue
        tokens = [
            next(g for g in match.groups() if g is not None).strip()
            for match in _QUOTED_TOKEN.finditer(group.group(1))
        ]
        tokens = [t for t in tokens if t and re.search(r"\w", t)]
        if tokens:
            return tokens
    # Fallback: the -027 criterion quotes its tokens directly after the marker,
    # not inside parentheses.  Measured over the 597-criterion corpus (-031):
    # zero existing marker-matched criteria have non-parenthesised quoted tokens,
    # so this path fires only for new phrasings like "contains no instances of
    # 'x', 'y'".
    if _CLEAR_MUST_PRESENT.search(tail) or _AMBIGUOUS_MUST_PRESENT.search(tail):
        return []
    tokens = [
        next(g for g in match.groups() if g is not None).strip()
        for match in _QUOTED_TOKEN.finditer(tail)
    ]
    return [t for t in tokens if t and re.search(r"\w", t)]


def _classify(criterion: str) -> tuple[str, list[str]]:
    """(shape, forbidden tokens). Fail-safe direction is presence.

    Implements B17-R2'(b)'s doubt predicate — four clauses, in order:

      (i)   negation signal present, no forbidden tokens → FORM (abstain)
      (ii)  structural signal present, field-vocab intersection EMPTY → FORM
      (iii) cardinality or numeric threshold → FORM (abstain)
      (iv)  no signal at all → PRESENCE, unchanged

    Clause (iv) is deliberate: the fallthrough stays presence. Making it
    abstain is the change that disables the check (-029), explicitly rejected.

    Prohibition is checked first because it is the strictly stronger test,
    and a criterion carrying both a forbidden list and presence language
    (criterion 6 does) is better served by the test that cannot be gamed.
    """
    forbidden = _forbidden_tokens(criterion)
    if forbidden:
        return PROHIBITION, forbidden
    # Clause (i): negation signal present, no tokens extractable.
    if _PROHIBITION_MARKER.search(criterion):
        # Ruling D2: clear must-be-present polarity → presence, not abstention.
        if _CLEAR_MUST_PRESENT.search(criterion):
            return PRESENCE, []
        return FORM, []
    # Original FORM + clause (ii).
    if _STRUCTURAL_VERB.search(criterion):
        fields = _FIELD_VOCAB & _terms(criterion)
        if len(fields) >= 2:
            return FORM, []
        if not fields:
            return FORM, []
        # Exactly 1 field: not enough for form, not empty — presence.
        return PRESENCE, []
    # Clause (iii): cardinality or numeric threshold.
    if _CARDINALITY.search(criterion):
        return FORM, []
    # Clause (iv): no signal at all — presence, unchanged.
    return PRESENCE, []


def _forbidden_present(token: str, text: str) -> bool:
    """Is a forbidden token present in the artifact?

    A multi-word token is matched as a phrase — "in today's fast-paced world"
    is one banned thing, not four — with runs of whitespace collapsed so a line
    break inside the phrase does not hide it. That last part is deliberate: a
    guard asserting a phrase that spanned a line break failed on correct text
    once this week, and the same shape would make this test silently lenient.
    """
    parts = [re.escape(w) for w in token.lower().split()]
    if not parts:
        return False
    pattern = r"\b" + r"\s+".join(parts) + r"\b"
    return re.search(pattern, " ".join(text.lower().split())) is not None


@check("criteria_addressed")
def criteria_addressed(
    criteria: list[str], text: str, threshold: float = 0.5,
    fallback: bool = False,
) -> Result:
    """Does the implementation visibly address every success criterion?

    Term overlap, not comprehension: this cannot tell you a criterion was met,
    only that the implementation never mentions what the criterion is about.
    That is a cheap, reliable signal — an implementation that never uses the
    word "backoff" has not addressed a backoff criterion — and it catches the
    failure we kept hitting, where work drifts off the plan without anyone
    noticing until a model reads it three phases later.

    `fallback` marks the asks node's fallback — nothing anchored, so the
    criterion list is the whole request. Word presence cannot judge a whole
    request: every word of it is about the answer, so the check is passed
    and NOT CHECKED — recorded, never a gate (the review of 2026-10-14:
    judged by word presence, the fallback failed 5 of 7 correct answers on
    Q15).
    """
    if fallback:
        return Result(
            True,
            "the whole request is the ask; word presence "
            "cannot judge it",
            checked=False,
        )
    if not criteria:
        # Ruling D46 (3): with no criteria there is nothing to check against.
        # The verdict is unchanged — it fails exactly as it always has — but
        # it is recorded as NOT CHECKED, and the fold treats it as
        # non-blocking rather than looping the work for a comparison that
        # could not happen.
        return Result(False, "no success criteria to check against",
                      checked=False)

    artifact = text or ""
    body = _terms(artifact)
    missed: list[str] = []
    coverage: dict[str, float] = {}
    shapes: dict[str, str] = {}
    abstained: list[dict[str, str]] = []
    why: dict[str, str] = {}
    # Convention 28 / retry_reconciliation() pattern: state the subject before
    # stating the conclusion. A score without its extraction is a conclusion a
    # reader cannot verify without re-running the extractor by hand (-029).
    extractions: dict[str, dict[str, Any]] = {}

    for criterion in criteria:
        wanted = _terms(criterion)
        if not wanted:
            continue
        shape, forbidden = _classify(criterion)
        shapes[criterion] = shape

        if shape == FORM:
            extractions[criterion] = {
                "terms": sorted(wanted), "forbidden_tokens": [],
            }
            # R2'(b): clause-specific reason. R2'(c): never silent.
            if _PROHIBITION_MARKER.search(criterion):
                reason = ("negation signal present but no forbidden tokens "
                          "extractable — cannot invert what is not named")
            elif _STRUCTURAL_VERB.search(criterion):
                if len(_FIELD_VOCAB & wanted) >= 2:
                    reason = ("names the fields an artifact must carry, not "
                              "words it contains — term overlap is not a "
                              "valid test")
                else:
                    reason = ("structural signal present but no "
                              "field-vocabulary terms matched — term overlap "
                              "measures the wrong thing")
            else:
                # Tier 1 compute (Ruling D3, D5): try word count before
                # abstaining on a cardinality criterion.
                wc = _try_word_count(criterion, artifact)
                if wc is not None:
                    ok, detail = wc
                    shapes[criterion] = "computed"
                    extractions[criterion] = {
                        "terms": sorted(wanted), "forbidden_tokens": [],
                        "computed": detail,
                    }
                    coverage[criterion] = 1.0 if ok else 0.0
                    if not ok:
                        missed.append(criterion)
                        why[criterion] = detail
                    continue
                reason = ("asserts a cardinality or numeric threshold — "
                          "term overlap cannot count")
            abstained.append({
                "criterion": criterion,
                "shape": FORM,
                "reason": reason,
            })
            continue

        if shape == PROHIBITION:
            present = [t for t in forbidden if _forbidden_present(t, artifact)]
            extractions[criterion] = {
                "terms": sorted(wanted), "forbidden_tokens": list(forbidden),
            }
            coverage[criterion] = 0.0 if present else 1.0
            if present:
                missed.append(criterion)
                why[criterion] = "uses " + ", ".join(repr(t) for t in present)
            continue

        extractions[criterion] = {
            "terms": sorted(wanted), "forbidden_tokens": [],
        }
        overlap = len(wanted & body) / len(wanted)
        coverage[criterion] = round(overlap, 2)
        if overlap < threshold:
            missed.append(criterion)
            why[criterion] = f"{overlap:.0%} of its terms appear"

    measured = len(coverage)
    data = dict(
        missed=missed, coverage=coverage, addressed=measured - len(missed),
        shapes=shapes, abstained=abstained, extractions=extractions,
    )

    if missed:
        listed = "; ".join(f"{c!r} ({why[c]})" for c in missed)
        note = f" ({len(abstained)} abstained on shape)" if abstained else ""
        # "visibly" is the word that keeps the presence test honest — it can
        # only say the implementation never mentions what a criterion is about,
        # never that the criterion was met. It is wrong for a prohibition,
        # where the failure is a banned token that IS visible, so the verb
        # follows the shapes that actually failed rather than being one word
        # for two different findings.
        verb = ("not visibly addressed by"
                if all(shapes[c] == PRESENCE for c in missed)
                else "not met by")
        # Ruling of 2026-10-15 (R1): coverage left the judges'
        # fold. Its result is still recorded here — the detail
        # and the data are unchanged — but a fail is counted as
        # a note, like consistency's since 2026-10-14, so the
        # run's record says how often it fired while nothing
        # loops on it and no veto reads it.
        count_normalisation(COVERAGE_NOTE)
        return Result(
            False,
            f"{len(missed)} of {measured} measurable success criteria are "
            f"{verb} the implementation{note}: {listed}",
            **data,
        )
    if abstained and not measured:
        # Every criterion was form-shaped. Per B17-R1 an abstention never fails
        # the check, so this passes — but a plan whose whole contract this
        # instrument cannot read is a finding, not a clean bill, and the detail
        # says so rather than reading as "all criteria addressed".
        return Result(
            True,
            f"nothing measurable: all {len(abstained)} success criteria abstained "
            f"on shape — the paid validator is the only judge of this plan",
            all_abstained=True, **data,
        )
    suffix = f", {len(abstained)} abstained on shape" if abstained else ""
    return Result(
        True,
        f"all {measured} measurable success criteria are addressed{suffix}",
        **data,
    )


@check("numbers_consistent")
def numbers_consistent(reference: str, implementation: str) -> Result:
    """Do values carried from the request into the implementation
    still agree? (Ruling D51 (4): consistency's reference is the
    request's stated figures — the plan is reasoning, not a
    yardstick.)

    Looks for `<number><unit>` pairs that share a unit and differ in value —
    the request stating 60s while the implementation sets 600s. It
    reports contradictions, never absence: a request value the implementation
    simply does not mention is not a conflict.

    The review of 2026-10-14: the figure extractor's unit class
    admits '$', so a LaTeX math delimiter read as a currency unit —
    the request's "$750$" indexed under "$" while the implementation's
    bare "750" indexed under no unit, and five correct answers (the
    reading sheet's entries 3, 11, 42, 46, 50) failed on a unit the
    request never states. The delimiter is math markup, not a unit: it
    is stripped from both texts before figures are extracted. And a
    disagreement this check finds is a note, not a veto — it is out of
    the judges' fold (the workflows record it; nothing loops on it),
    counted like every other demotion so the run's record says how
    often it fired.
    """
    def indexed(text: str) -> dict[str, list[tuple[float, int]]]:
        found: dict[str, list[tuple[float, int]]] = {}
        for value, significant, raw_unit in _figures(text):
            unit = _canonical_unit(raw_unit)
            if not unit:
                continue
            found.setdefault(unit, []).append((value, significant))
        return found

    def shown(values: list[tuple[float, int]]) -> list[str]:
        return sorted({_normalize(f"{v:.{s}g}") for v, s in values})

    requested, built = indexed(str(reference or "").replace("$", "")), \
        indexed(str(implementation or "").replace("$", ""))
    # Ruling D46 (3): with no shared unit there is nothing to compare. It
    # passes exactly as it did — reporting absence as conflict would be a
    # different check — but it is recorded as NOT CHECKED, the fold treats it
    # as non-blocking, and the run's record lists it.
    if not (requested.keys() & built.keys()):
        return Result(
            True,
            "no shared unit between request and implementation — "
            "compared nothing",
            checked=False, conflicts=[],
        )
    # A conflict is a shared unit whose request and implementation
    # figures have no value in common, as before; "in common" now
    # means equal at the precision of the less precise figure.
    conflicts = [
        f"{unit}: request says {shown(requested[unit])}, "
        f"implementation says {shown(built[unit])}"
        for unit in requested.keys() & built.keys()
        if not any(_agree(p, b) for p in requested[unit]
                   for b in built[unit])
    ]

    if conflicts:
        # Out of the fold since the review of 2026-10-14: the
        # disagreement is recorded and counted as a note, so the
        # run's record says how often it fired, but it no longer
        # judges the work — nothing loops on it and no veto reads it.
        count_normalisation(CONSISTENCY_NOTE)
        return Result(
            False,
            "values disagree between request and implementation — "
            + "; ".join(conflicts),
            conflicts=conflicts,
        )
    return Result(
        True,
        "no contradicting values between request and implementation",
        conflicts=[],
    )


@check("reground_context")
def reground_context(ready: bool = False, risk: str | None = None,
                     blockers: list[str] | None = None,
                     asked: list[str] | None = None,
                     rounds: int = 0) -> Result:
    """Should the plan get one more grounding round before it is judged?

    Ruling D37 (owner-supplied, recorded by the advisor, 2026-09-30). Pure
    registered check, driven exactly like build_loop's fold: all inputs
    arrive as resolved args, no adapter import, no module state. The loop
    exits when this returns False, so every stay-out reason is False here:

    - plan already ready: nothing to re-ground;
    - low risk: the risk policy buys no search calls there;
    - no blocker novel against the asked history: re-asking is the spin
      this harness has died on before (normalized compare);
    - a round already ran: once is ruled, whatever the blockers say.

    Free, deterministic, no store, no spend. Reports which blockers are
    novel; the paid lookup is the separate node that runs only after this
    check passed, and it sends only the novel ones.
    """
    if ready:
        return Result(False, "plan ready — no re-grounding needed",
                      novel=False, fresh=[])
    if str(risk or "").strip().lower() == "low":
        return Result(False, "low risk — no paid re-grounding",
                      novel=False, fresh=[])
    if (rounds or 0) >= 1:
        return Result(False, "re-grounding round already ran — once is ruled",
                      novel=False, fresh=[])
    asked_set = {_normalize_question(q) for q in (asked or []) if q}
    fresh = []
    for raw in blockers or []:
        text = str(raw or "").strip()
        if not text:
            continue
        if _normalize_question(text) not in asked_set:
            fresh.append(text)
    if not fresh:
        return Result(False, "no novel blocking unknown — planning on current grounding",
                      novel=False, fresh=[])
    return Result(True, f"{len(fresh)} novel blocking unknown(s) to re-ground",
                  novel=True, fresh=fresh)


def _normalize_question(text: str) -> str:
    return " ".join(str(text).lower().strip().rstrip("?.!").split())


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


# ── the recompute vote (Ruling D53) ─────────────────────────────────

# The vote's tolerance, as the tier-4 probe measured it
# (evals/tier4/probes/recompute_vote.py, TOL): two numbers
# agree within 3% of the candidate's own magnitude.
_RECOMPUTE_TOL = 0.03


def _recompute_ident(text: Any) -> str:
    """An identifier, normalised for the vote.

    recompute_check.ident (evals/tier4/probes/
    recompute_check.py), the rule Ruling D53 §2 (4) adopts:
    case, spacing and punctuation dropped, the words
    'in parallel' dropped (a configuration stated with them
    is the configuration stated without them — the recorded
    T4-24 answer says '5 × EPC-1200-60 in parallel' against
    samples' '5 × EPC-1200-60', and the probe's measurement
    reads them as one selection), and the multiplication
    sign and a count's 'x' (5 x EPC) read as separators.
    'VL-42' and 'vl 42' are one identifier.
    """
    t = str(text).upper().replace("IN PARALLEL", "").replace("×", " ")
    t = re.sub(r"^\s*(\d+)\s*X\s+", r"\1 ", t)
    return re.sub(r"[^A-Z0-9]", "", t)


def _recompute_number(text: Any) -> float | None:
    """The number a value states, or None if it states none.

    The probe's num(): a number is itself, and text states
    its first number, commas read as thousands separators.
    A bool is neither — it is an identifier-shaped answer.
    """
    if isinstance(text, bool):
        return None
    if isinstance(text, (int, float)):
        return float(text)
    m = re.search(r"-?\d+(?:\.\d+)?(?:[eE]-?\d+)?",
                  str(text).replace(",", ""))
    return float(m.group()) if m else None


def _recompute_field(entry: Any, key: str) -> Any:
    """A field off a result entry, whichever shape it arrives in.

    The answer's results are ResultValue models; a sample's
    results are the dicts its reply parsed into. Both carry
    ask, value and unit.
    """
    if isinstance(entry, dict):
        return entry.get(key)
    return getattr(entry, key, None)


def _sample_results(sample: Any) -> Any:
    """A sample's results list, whichever shape the sample arrives in."""
    if isinstance(sample, dict):
        return sample.get("results")
    return getattr(sample, "results", None)


def _recompute_ask_index(asks: list[Any]) -> dict[str, int]:
    """The anchored asks' quotes, normalised, keyed by number."""
    return {
        _normalise_quote(str(_ask_field(a, "quote") or "")):
            _ask_field(a, "number")
        for a in (asks or [])
        if str(_ask_field(a, "quote") or "").strip()
    }


def _recompute_names(named: Any, number: Any,
                     quote_index: dict[str, int]) -> bool:
    """Does this result entry name the anchored ask at `number`?

    The way blocked_on does (D51 (5)): by its number, or by
    its quote — the anchored ask's own words, verbatim under
    the normalisation the checks apply.
    """
    if isinstance(named, int) and not isinstance(named, bool):
        return named == number
    if isinstance(named, str) and named.strip():
        return quote_index.get(_normalise_quote(named)) == number
    return False


def _recompute_majority(values: list[Any],
                        identity: bool) -> tuple[Any, int] | None:
    """The value at least 2 of the samples agree on, or None.

    The tier-4 probe's majority(), ported: identifiers agree
    exactly, after normalisation; numbers agree within the
    tolerance, and the majority is the mean of the agreeing
    group — the first group of at least two, in the order
    the samples answered. The second element is the group's
    size, the majority's support.
    """
    vals = [v for v in values if v is not None]
    if identity:
        counts: Counter[str] = Counter(_recompute_ident(v)
                                       for v in vals)
        top = counts.most_common(1)
        if top and top[0][1] >= 2:
            return top[0][0], top[0][1]
        return None
    nums = [n for n in (_recompute_number(v) for v in vals)
            if n is not None]
    for a in nums:
        agree = [b for b in nums
                 if abs(a - b) <= _RECOMPUTE_TOL * max(abs(a), 1e-9)]
        if len(agree) >= 2:
            return sum(agree) / len(agree), len(agree)
    return None


@check("recompute_vote")
def recompute_vote(results: list[Any], samples: list[Any],
                   asks: list[Any], request: str,
                   skipped: bool = False,
                   reason: str = "") -> Result:
    """The recompute vote (Ruling D53): does a majority of blind
    recomputations agree with the answer?

    The samples recomputed the anchored asks of kind value and
    verdict from the request and the grounding alone. This check
    compares, for each ask the answer's results name, the answer's
    value against the samples' majority — the value at least 2 of
    the samples that answered the ask matched. A verdict ask, or
    any ask whose values in play are stated as text, compares as
    identifiers; numbers compare within the tolerance, and only
    when the units are equal after normalise_key — an ask whose
    units differ has no consensus to compare against.

    The vote is a note (D53 §2 (5)): it never blocks, routes or
    revises, and the run's status is decided without it. A flag is
    recorded here and in the delivery, and nothing reads it.
    `passed` is false exactly when the vote found a disagreement —
    the finding is the check's own answer, not a gate — and a skip
    is never a pass: it is recorded as skipped, with the reason the
    node gave. Fewer than two parseable samples, or an answer whose
    results name no anchored ask, leaves the vote unchecked.
    """
    # A skip is a skip, never a pass: the tier is not configured,
    # no sample ran, and the vote compared nothing.
    if skipped:
        return Result(
            False,
            "recompute vote did not run — "
            + (str(reason).strip()
               or "no model configured for the recompute tier"),
            checked=False, skipped=True, flagged=False,
            unchecked=False, disagreements=[], no_consensus=[],
            samples_parsed=0, samples_failed=0,
        )

    quote_index = _recompute_ask_index(asks)
    # A sample is parseable when its results are a list — an empty
    # one is a sample that stated nothing, which is a shape it
    # parsed, not a failure to.
    parsed = [s for s in (samples or [])
              if isinstance(_sample_results(s), list)]
    samples_parsed = len(parsed)
    # A failed sample (ARCH-20261021-124) is recorded by the recompute as
    # {failed: true, error}; it states no results, so it never parses.
    samples_failed = sum(1 for s in (samples or [])
                         if isinstance(s, dict) and s.get("failed") is True)

    # The anchored asks of kind value or verdict that the answer's
    # results name — the asks the samples were given, so the only
    # ones the vote can compare. The first entry naming an ask is
    # the answer's entry for it.
    wanted: dict[int, Any] = {}
    for entry in (results or []):
        named = _recompute_field(entry, "ask")
        for ask in (asks or []):
            number = _ask_field(ask, "number")
            kind = str(getattr(_ask_field(ask, "kind"), "value",
                               _ask_field(ask, "kind")) or ""
                       ).strip().lower()
            if kind not in ("value", "verdict"):
                continue
            if _recompute_names(named, number, quote_index):
                wanted.setdefault(number, entry)
                break

    # Fewer than two parseable samples, or no answer result naming
    # an anchored ask: the vote compared nothing (D46 (3)) —
    # unchecked, and flagged false.
    if samples_parsed < 2 or not wanted:
        failed = f", {samples_failed} failed" if samples_failed else ""
        why = (f"fewer than 2 parseable samples ({samples_parsed} "
               f"parsed{failed})" if samples_parsed < 2
               else "no answer result names an anchored ask")
        return Result(
            True,
            f"recompute vote unchecked — {why}",
            checked=False, skipped=False, flagged=False,
            unchecked=True, disagreements=[], no_consensus=[],
            samples_parsed=samples_parsed, samples_failed=samples_failed,
        )

    disagreements: list[dict[str, Any]] = []
    no_consensus: list[int] = []
    for number in sorted(wanted):
        answer = wanted[number]
        ask = next(a for a in (asks or [])
                   if _ask_field(a, "number") == number)
        kind = str(getattr(_ask_field(ask, "kind"), "value",
                           _ask_field(ask, "kind")) or ""
                   ).strip().lower()
        answer_value = _recompute_field(answer, "value")
        # One value per sample that answered this ask.
        sample_values: list[Any] = []
        sample_units: list[str] = []
        for sample in parsed:
            for entry in (_sample_results(sample) or []):
                if _recompute_names(_recompute_field(entry, "ask"),
                                    number, quote_index):
                    sample_values.append(
                        _recompute_field(entry, "value"))
                    sample_units.append(
                        str(_recompute_field(entry, "unit") or ""))
                    break
        # Identity or numbers: a verdict ask, or any value in play
        # stated as text, compares as an identifier.
        identity = kind == "verdict" or any(
            isinstance(v, (str, bool))
            for v in [answer_value, *sample_values])
        if not identity:
            # Numbers compare only when the units are equal after
            # normalise_key; otherwise the ask is no consensus.
            units = {normalise_key(u) for u in
                     ([str(_recompute_field(answer, "unit") or "")]
                      + sample_units)}
            if len(units) > 1:
                no_consensus.append(number)
                continue
        majority, support = _recompute_majority(sample_values, identity) \
            or (None, 0)
        if majority is None:
            no_consensus.append(number)
            continue
        differs = (_recompute_ident(answer_value) != majority
                   if identity else
                   (_recompute_number(answer_value) is not None
                    and abs(_recompute_number(answer_value)
                            - majority)
                    > _RECOMPUTE_TOL * max(abs(majority), 1e-9)))
        if differs:
            disagreements.append({
                "ask": number,
                "answer": answer_value,
                "majority": majority,
                "support": support,
            })

    flagged = bool(disagreements)
    if flagged:
        detail = (
            f"recompute vote flagged {len(disagreements)} of "
            f"{len(wanted)} voted ask(s): "
            + "; ".join(
                f"ask {d['ask']}: answer {d['answer']!r} vs "
                f"majority {d['majority']!r} "
                f"({d['support']} of {samples_parsed} samples)"
                for d in disagreements))
    else:
        detail = (f"recompute vote: no disagreement — "
                  f"{samples_parsed} sample(s) voted on "
                  f"{len(wanted)} ask(s)")
    if no_consensus:
        detail += ("; no consensus on ask(s) "
                   + ", ".join(str(n) for n in no_consensus))
    return Result(
        not flagged,
        detail,
        checked=True, skipped=False, flagged=flagged,
        unchecked=False, disagreements=disagreements,
        no_consensus=no_consensus, samples_parsed=samples_parsed,
        samples_failed=samples_failed,
    )
