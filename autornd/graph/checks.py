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
