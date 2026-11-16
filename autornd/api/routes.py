"""REST API endpoints for AutoRnD."""

from __future__ import annotations

import asyncio
import difflib
import json
import math
import re
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from autornd.api.auth import _is_loopback
from autornd.config import settings
from autornd.database import get_session
from autornd.engine.workflow import (
    WorkflowEngine, WorkflowNotOffered, offered_workflows, requested_workflow,
    workflow_path,
)
from autornd.models.workflow import PhaseResult, Workflow, WorkflowStatus
from autornd.routing.openrouter import OpenRouterClient

router = APIRouter(prefix="/api")


def _get_user_id(request: Request) -> int | None:
    return getattr(request.state, "user_id", None)


def _caller_key(request: Request) -> tuple:
    """Who is asking: their account when they have one, else their address."""
    user_id = _get_user_id(request)
    if user_id is not None:
        return ("user", user_id)
    return ("host", (request.client.host if request.client else "") or "")


class _RunGate:
    """Ruling D45 (6): a per-run ceiling bounds one run, not a caller who
    submits many. At most `settings.max_concurrent_runs` API runs in flight at
    once, and never twice the same request text through the same workflow
    from the same caller. Ruling D55 (6) added the workflow: the same request
    run through two workflows, to compare them, is two runs.

    Admission is refused BEFORE a Workflow row exists — a refused submission
    must leave nothing behind — and released when the run it admitted ends,
    whatever way it ends."""

    def __init__(self) -> None:
        self._in_flight: dict[tuple, set[tuple[str, str]]] = {}

    def count(self) -> int:
        return sum(len(runs) for runs in self._in_flight.values())

    def admit(self, caller: tuple, request_text: str,
              workflow: str) -> str | None:
        """None when admitted (and registered); else 'duplicate' or 'cap'."""
        mine = self._in_flight.setdefault(caller, set())
        if (request_text, workflow) in mine:
            return "duplicate"
        if self.count() >= settings.max_concurrent_runs:
            return "cap"
        mine.add((request_text, workflow))
        return None

    def release(self, caller: tuple, request_text: str,
                workflow: str) -> None:
        mine = self._in_flight.get(caller)
        if mine:
            mine.discard((request_text, workflow))
            if not mine:
                self._in_flight.pop(caller, None)


_run_gate = _RunGate()


def _admit_run(request: Request, request_text: str, workflow: str) -> tuple:
    """Register an API run with the gate or refuse it with a sentence."""
    caller = _caller_key(request)
    verdict = _run_gate.admit(caller, request_text, workflow)
    if verdict == "duplicate":
        raise HTTPException(
            409,
            "This request is already running through this workflow for this "
            "caller; wait for it to finish or submit different work.")
    if verdict == "cap":
        raise HTTPException(
            429,
            f"At most {settings.max_concurrent_runs} runs are in flight at "
            f"once (Ruling D45); wait for one to finish and submit again.")
    return caller


def _bound_client() -> OpenRouterClient:
    """A client for an API run, carrying the run's spend ceiling.

    Every client the API creates — both submit paths and doublecheck — is
    bounded (Ruling D45 (2)), so no call on this endpoint spends past the
    run's ceiling."""
    client = OpenRouterClient()
    client.spend_ceiling = settings.run_spend_ceiling_usd
    return client


# Ruling D45 (3): runtime settings can only tighten. A ceiling raised at
# runtime raises it for every run in flight, and any caller the middleware
# admits could do it — which is review A's F8. These are the values the
# process started with: a numeric ceiling may be lowered below them and never
# raised above them while the server runs. Non-numeric fields (profiles,
# workflow names, log level) steer nothing spend-shaped and are unchanged.
_STARTUP_VALUES = {
    name: getattr(settings, name) for name in settings.RUNTIME_MUTABLE
}


def _only_tightens(name: str, value) -> bool:
    startup = _STARTUP_VALUES.get(name)
    if isinstance(startup, bool) or not isinstance(startup, (int, float)):
        return True
    return value <= startup


# ── Auth endpoints ──

class RegisterRequest(BaseModel):
    username: str = Field(min_length=3, max_length=64)
    email: EmailStr
    # NIST SP 800-63B floor. Raise it in your own deployment if you want a
    # stricter policy — the harness shouldn't impose one on downstream users.
    password: str = Field(min_length=8, max_length=256)


class LoginRequest(BaseModel):
    username: str
    password: str


@router.post("/auth/register", status_code=201)
async def register(body: RegisterRequest, session: AsyncSession = Depends(get_session)):
    from autornd.api.auth import create_token, hash_password
    from autornd.config import settings
    from autornd.models.user import User

    if not settings.registration_enabled:
        raise HTTPException(403, "Registration is disabled")

    existing = await session.execute(
        select(User).where((User.username == body.username) | (User.email == body.email))
    )
    if existing.scalar_one_or_none():
        raise HTTPException(409, "Username or email already taken")

    user = User(
        username=body.username,
        email=body.email,
        password_hash=hash_password(body.password),
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)

    token = create_token(user.id, user.username)
    return {"data": {"id": user.id, "username": user.username, "token": token}}


@router.post("/auth/login")
async def login(body: LoginRequest, session: AsyncSession = Depends(get_session)):
    from autornd.api.auth import create_token, verify_password
    from autornd.models.user import User

    result = await session.execute(select(User).where(User.username == body.username))
    user = result.scalar_one_or_none()
    if not user or not verify_password(body.password, user.password_hash):
        raise HTTPException(401, "Invalid username or password")

    token = create_token(user.id, user.username)
    return {"data": {"id": user.id, "username": user.username, "token": token}}


@router.get("/auth/me")
async def get_me(request: Request):
    user_id = _get_user_id(request)
    username = getattr(request.state, "username", None)
    if not user_id:
        return {"data": {"id": None, "username": None, "anonymous": True}}
    return {"data": {"id": user_id, "username": username, "anonymous": False}}


# ── Workflow endpoints ──

class WorkflowRequest(BaseModel):
    request: str
    # Ruling D55 (1): the name of an offered workflow, as GET
    # /api/workflows/offered lists them. Unset runs the configured default.
    workflow: str | None = None


def _requested_workflow(body: WorkflowRequest) -> tuple[str, str | None]:
    """The workflow a submission runs: its name for the gate, and its file.

    Called before the gate, so a refused name holds no slot and leaves no row
    (Ruling D45 (6), D55 (3)). A request that names none runs the configured
    default, under that default's name, so naming the default is the same
    run as naming nothing.
    """
    if body.workflow is None:
        return Path(workflow_path()).stem, None
    try:
        path = requested_workflow(body.workflow)
    except WorkflowNotOffered as exc:
        raise HTTPException(422, str(exc)) from None
    return body.workflow, path


class WorkflowSummary(BaseModel):
    id: int
    request: str
    status: str
    error: str | None = None
    risk_level: str | None
    iteration: int
    total_cost: float
    # ARCH-20261002-116 (property 9): the worst case of
    # calls that failed after dispatch, kept apart from
    # booked spend. Additive to the response — a consumer
    # that does not read it is unchanged.
    unreconciled_liability: float = 0.0
    created_at: str
    updated_at: str


class PhaseDetail(BaseModel):
    phase: str
    iteration: int
    verdict: dict
    model_used: str | None
    cost: float
    created_at: str


class WorkflowDetail(WorkflowSummary):
    phases: list[PhaseDetail]
    # Ruling D57 (3): a run that ended without a delivered answer keeps its
    # last one, unendorsed, with its open dissents. None when the run
    # completed or ended before any answer existed.
    candidate: dict | None = None
    # The answer itself, so a caller need not dig it out of the phases: the
    # last implement summary, and only when the run completed. A run that
    # ended any other way has no delivered answer; its draft is `candidate`.
    answer: str | None = None
    # The recompute vote's last record (Ruling D53), a note beside the
    # answer: flagged, unchecked or agreed. None when no vote ran.
    recompute_vote: dict | None = None
    # Every decision switch the run asked, in order: the switch, what it
    # was asked about, the probability, the model's choice, the switch's
    # mode and the route it gave. A route of `default` means nothing acted
    # on it. Empty when no decision tier is configured.
    decisions: list[dict] = Field(default_factory=list)
    # What each lookup read (Ruling D56): per question, the pages quoted,
    # whether each was fetched and whether its quote was found there.
    sources: list[dict] = Field(default_factory=list)
    # What a reader should know before relying on the answer, in plain
    # sentences: a vote that flagged or compared nothing, a lookup that did
    # not run or read nothing, a figure that is on no page read, two pages
    # that give different figures for one thing. For people; nothing routes
    # on it.
    cautions: list[str] = Field(default_factory=list)
    # What was checked against a source, in plain sentences (owner's ruling,
    # 2026-11-15): the asks whose figures stand in a passage found on its
    # page. For people; nothing routes on it.
    confirmations: list[str] = Field(default_factory=list)


# A number as an answer states it, and the word that follows it, if any.
_FIGURE = re.compile(r"(\d+(?:\.\d+)?)(?:[\s-]*([A-Za-z]{3,}))?")


def _figures(result: dict) -> list[tuple[str, str]]:
    """The numbers one answer result states, each with the start of the word
    after it ("1 year" gives ("1", "year")), from its value and its unit."""
    value = result.get("value")
    if isinstance(value, bool) or value is None:
        return []
    if isinstance(value, (int, float)):
        value = f"{value:g}"
    text = f"{value} {result.get('unit') or ''}".replace(",", "")
    return list(dict.fromkeys(
        (number, word[:4].casefold()) for number, word in _FIGURE.findall(text)))


def _stands(number: str, word: str, found: str) -> bool:
    """Is this number in the found passages, as a whole number?

    A number of two digits or more is taken on its own. A single digit is on
    every page ("5", "(1)"), so it counts only with its word beside it: "1"
    with "year", "5" with "rems".
    """
    whole = rf"(?<![\d.]){re.escape(number)}(?!\d|\.\d)"
    if len(number) >= 2:
        return re.search(whole, found) is not None
    return bool(word) and re.search(
        whole + rf"[\s-]{{0,3}}{re.escape(word)}", found) is not None


def _handed_on(sources: list[dict], beside_the_point: bool = False,
               ) -> list[tuple[str, str]]:
    """The text a lookup handed on that stands on its page: an address and
    the passage, for every quote found there. A passage quote_answers judged
    beside the point is left out unless asked for. `whole` is the passage
    past the record's first 600 characters, kept since 2026-11-15 because
    the excerpts of the lookup that reads the documents run to twice that."""
    return [(str(quote.get("url") or ""),
             str(quote.get("whole") or quote.get("text") or ""))
            for source in sources for finding in source.get("findings") or []
            for quote in finding.get("quotes") or []
            if isinstance(quote, dict) and quote.get("status") == "found"
            and (beside_the_point or quote.get("answers_question") is not False)]


def _checked_figures(results: object, sources: list[dict],
                     differing: list[dict]) -> tuple[list[int], list[dict]]:
    """The asks whose figures stand in the text handed on, and the figures
    that do not.

    Owner's ruling of 2026-11-15, after the professional baseline: 45 of 45
    answers were right, 38 carried a caution, and the one disagreement the
    vote raised was two samples from memory against the regulator's own
    sentence. An ask is backed when its answer states a number and every
    number it states stands in the found passages (`_stands`). Free and
    deterministic; it reads typed results and quoted text, never the
    answer's prose.

    The owner's plan of 2026-11-15 added the other side. A figure of the
    answer's value that is nowhere in the found passages is named, and an
    ask is not backed when the passages themselves give different figures
    for the thing it states (`_differing`). On the harder professional run
    a wrong 9 hours stood beside a found passage that said 10, and the
    delivery spoke only of quotes in general.

    Between the two a figure is neither confirmed nor named: a single digit
    that is on the page without its word beside it ("8 cumulative hours"
    for an answer of 8 hours, right 3 times of 3 on that run). Being absent
    is read loosely on purpose, by the number's value and with a number
    written as a word counted, so the caution is true of the page. It is
    said only of a value that is one number (`_single_figure`).
    """
    if not isinstance(results, list):
        return [], []
    every = [text for _, text in _handed_on(sources, beside_the_point=True)]
    if not every:
        return [], []  # nothing was read, and the cautions say that once
    found = " ".join(text.replace(",", "") for _, text in
                     _handed_on(sources)).casefold()
    # A passage quote_answers judged beside the point backs nothing, and its
    # numbers are still on a page that was read.
    on_the_pages = {float(token) for text in every
                    for _, numbers, _ in _sentences(text, 0)
                    for token in numbers}
    disputed = {float(number) for d in differing for number in d["figures"]}
    backed: list[int] = []
    unconfirmed: dict[int, list[str]] = {}
    for result in results:
        if not isinstance(result, dict) or not isinstance(result.get("ask"), int):
            continue
        figures = _figures(result)
        if figures and all(_stands(n, w, found) for n, w in figures):
            if not disputed.intersection(float(n) for n, _ in figures):
                backed.append(result["ask"])
            continue
        number = _single_figure(result.get("value"))
        if number is not None and number not in on_the_pages:
            unit = str(result.get("unit") or "").strip()
            unconfirmed.setdefault(result["ask"], []).append(
                f"{number:g} {unit if len(unit) <= SHORT_UNIT_CHARS else ''}".strip())
    backed = sorted(set(backed))
    return backed, [{"ask": ask, "figures": list(dict.fromkeys(figures))}
                    for ask, figures in sorted(unconfirmed.items())
                    if ask not in backed]


# The longest unit a caution prints beside its figure. Longer ones are
# descriptions ("grams of alcohol per 210 L of breath").
SHORT_UNIT_CHARS = 16


def _single_figure(value: object) -> float | None:
    """The one number an answer's value is, or None.

    A value that is a sentence or a list is not read for the caution that a
    figure is on no page. Read off the recorded runs of 2026-11-15: such
    values are mostly citations ("14 CFR 65.91(c)(1)-(5)"), whose numbers a
    page prints after a section sign or not at all, and every caution drawn
    from one stood beside a right answer. Nought is the answer "none",
    which a page states in words.
    """
    if isinstance(value, bool) or value is None:
        return None
    try:
        number = float(str(value).replace(",", "").strip())
    except ValueError:
        return None
    return number if number and math.isfinite(number) else None


# How the passages are read for figures that differ. A paragraph's own label
# ("(b)(1)", "(2)") and a section's number ("§ 50.19") are not figures of
# the rule; a number written as a word is ("nine consecutive hours", on the
# regulator's own page).
_LABEL = re.compile(r"\((?:[a-z]{1,4}|\d{1,3})\)|§+\s*\d+(?:\.\d+)?")
_SENTENCE = re.compile(r"(?<=[.;:?!])\s+|\n+")
# A number joined to a letter is a mark, not a figure: the "F1" of an
# amendment note, the 3 of "O3".
_TOKEN = re.compile(r"(?<![a-z])\d+(?:\.\d+)?(?![a-z])|[a-z]+")
_NUMBER_WORD = {word: str(n) for n, word in enumerate(
    "zero one two three four five six seven eight nine ten eleven "
    "twelve".split())}
# Two sentences state the same thing when this share of their words agree,
# in order. Set on the 283 recorded answers of 2026-11-15 (both professional
# sets, both lookups, and the inspection-authorization request). At 0.8 the
# 2012 and the current edition of one paragraph, which differ by a nine-word
# clause and one figure, are one thing; at 0.9 they are not, and that pair
# is the case this was built for. At 0.7 seven more pairs come in, none of
# them one thing.
SAME_SENTENCE_RATIO = 0.8
SAME_SENTENCE_MIN_WORDS = 8
# And the words right beside the figure that differs must be the same ones.
# On the same answers the ratio alone raised 9 cautions; this leaves 5 and
# drops the 4 that were not one thing: "transmitter power exceeding 1.5 kW
# PEP" beside "transmitter power output exceeding 200 W PEP", two paragraphs
# of one rule, three times, and two test methods' numbers once. The 5 left
# are the flight attendant's 10 hours beside 9 (twice), an ozone standard
# of 0.070 beside its predecessor's 0.075 (twice), and a driver's 10 hours
# off duty beside a sister rule's 8.
SAME_WORDS_BEFORE = 3
SAME_WORDS_AFTER = 2
# The most of a sentence a caution prints.
DIFFERING_SENTENCE_CHARS = 240


def _page(url: str) -> str:
    """One name for a page however its address was written."""
    return re.sub(r"^https?://(?:www\.)?", "", url.strip().casefold()).rstrip("/")


def _sentences(text: str, min_words: int = SAME_SENTENCE_MIN_WORDS,
               ) -> list[tuple[tuple[str, ...], tuple[str, ...], str]]:
    """Each sentence of a passage that states a number: its words with every
    number put aside, the numbers in order, and the sentence as printed."""
    out = []
    for sentence in _SENTENCE.split(text):
        tokens = [_NUMBER_WORD.get(t, t) for t in _TOKEN.findall(
            _LABEL.sub(" ", sentence.casefold().replace(",", "")))]
        numbers = tuple(t for t in tokens if t[0].isdigit())
        words = tuple("#" if t[0].isdigit() else t for t in tokens)
        if numbers and len(words) - len(numbers) >= min_words:
            out.append((words, numbers, " ".join(sentence.split())))
    return out


def _differing(sources: list[dict]) -> list[dict]:
    """Where two pages handed on give different figures for the same thing.

    Measured 2026-11-15 on the harder professional run: the current rule
    said 10 hours, its 2012 edition said 9 in the same sentence, both were
    found on their pages word for word, and the answer took the 9. A passage
    found on its page can be out of date. Two sentences from different pages
    are the same thing when their words agree (SAME_SENTENCE_RATIO), they
    state as many numbers, and exactly one number differs. Free and
    deterministic; it says the pages differ, not which is right.
    """
    pages: dict[str, list] = {}
    for url, text in _handed_on(sources, beside_the_point=True):
        pages.setdefault(_page(url), []).extend(_sentences(text))
    out: list[dict] = []
    seen: set = set()
    names = list(pages)
    for i, first in enumerate(names):
        for second in names[i + 1:]:
            for words_a, numbers_a, printed in pages[first]:
                for words_b, numbers_b, _ in pages[second]:
                    apart = [n for n, (a, b) in enumerate(zip(numbers_a, numbers_b))
                             if float(a) != float(b)]
                    if len(numbers_a) != len(numbers_b) or len(apart) != 1:
                        continue
                    pair = (numbers_a[apart[0]], numbers_b[apart[0]])
                    if frozenset(map(float, pair)) in seen:
                        continue
                    at_a = [k for k, w in enumerate(words_a) if w == "#"][apart[0]]
                    at_b = [k for k, w in enumerate(words_b) if w == "#"][apart[0]]
                    if (words_a[max(0, at_a - SAME_WORDS_BEFORE):at_a]
                            != words_b[max(0, at_b - SAME_WORDS_BEFORE):at_b]
                            or words_a[at_a + 1:at_a + 1 + SAME_WORDS_AFTER]
                            != words_b[at_b + 1:at_b + 1 + SAME_WORDS_AFTER]):
                        continue
                    match = difflib.SequenceMatcher(None, words_a, words_b,
                                                    autojunk=False)
                    if (match.quick_ratio() >= SAME_SENTENCE_RATIO
                            and match.ratio() >= SAME_SENTENCE_RATIO):
                        seen.add(frozenset(map(float, pair)))
                        out.append({"figures": list(pair),
                                    "pages": [first, second],
                                    "sentence": printed})
    return out


def _confirmations(backed: list[int], has_answer: bool) -> list[str]:
    if not has_answer or not backed:
        return []
    asks = ", ".join(map(str, backed))
    return [f"The figures this answer gives for ask {asks} stand in a passage "
            f"found on its page."]


def _settled(verdicts: list[tuple[str, Any]], vote: dict | None,
             sources: list[dict]) -> dict | None:
    """Apply what the live switches settled to the delivery, as labels.

    The owner's ruling of 2026-11-14 on
    docs/reviews/2026-11-13-lookup-quotes.md, where same_meaning said yes
    on 6 of 6 flags the vote raised on right answers for their wording, and
    all 21 confident no's of quote_answers over three runs were right. An
    ask same_meaning cleared is listed in the vote's `cleared`, and the
    vote is `flagged` only if a disagreement is left; what the vote itself
    found stays in `flagged_by_vote` and `disagreements`. A quote that
    quote_answers judged not to answer its question carries
    `answers_question: false`. The stored phase rows are not changed.
    """
    last = next((v for _, v in reversed(verdicts) if isinstance(v, dict)
                 and isinstance(v.get("cleared"), list)
                 and isinstance(v.get("not_answering"), list)), None)
    if last is None:
        return vote
    marks = [(m.get("url"), m.get("passage")) for m in last["not_answering"]
             if isinstance(m, dict)]
    for source in sources:
        for finding in source.get("findings") or []:
            for quote in finding.get("quotes") or []:
                if (isinstance(quote, dict) and quote.get("status") == "found"
                        and (quote.get("url"), quote.get("text")) in marks):
                    quote["answers_question"] = False
    if vote is None or not last["cleared"]:
        return vote
    disagreements = vote.get("disagreements") or []
    cleared = [d.get("ask") for d in disagreements
               if f"ask {d.get('ask')}" in last["cleared"]]
    return dict(vote, cleared=cleared,
                flagged_by_vote=bool(vote.get("flagged")),
                flagged=bool(vote.get("flagged"))
                and len(cleared) < len(disagreements))


def _cautions(vote: dict | None, sources: list[dict],
              has_answer: bool, asks: int = 0,
              unconfirmed: list[dict] | None = None,
              differing: list[dict] | None = None) -> list[str]:
    """The cautions beside an answer, read off the typed records.

    Measured live 2026-11-12: a completed run delivered a wrong figure with
    a vote that had compared nothing and no lookup behind it, and nothing in
    the delivery said so short of reading the phase records.

    Rebuilt 2026-11-15 on the owner's plan, around the text handed on: with
    the harness reading the documents, not one of 62 harder-set answers came
    without a caution, 61 of them right, because the cautions counted a
    model's quotes. They now say which figure could not be confirmed, where
    the pages differ, and when nothing was read; they no longer count
    quotes, nor repeat quote_answers' judgement of a passage.
    """
    if not has_answer:
        return []
    out: list[str] = []
    if vote is not None:
        # A vote that could not compare an ask says nothing a found passage
        # has not already settled (owner's ruling, 2026-11-15). A vote that
        # disagrees is said whatever the passages hold: the rule that took a
        # found passage over it never fired on 184 recorded answers, and in
        # its one near case would have silenced a true alarm.
        backed = vote.get("backed_by_source") or []
        cleared = [a for a in vote.get("cleared") or [] if a not in backed]
        if cleared:
            out.append("The recompute vote worded ask "
                       + ", ".join(map(str, cleared))
                       + " differently from this answer; a decision model "
                         "judged the two to say the same thing.")
        if vote.get("flagged"):
            flagged = ", ".join(str(d.get("ask")) for d in
                                vote.get("disagreements") or []
                                if d.get("ask") not in (vote.get("cleared") or []))
            out.append("The recompute vote disagrees with this answer"
                       + (f" on ask {flagged}." if flagged else "."))
        elif vote.get("skipped"):
            out.append("The recompute vote did not run, so no figure in "
                       "this answer was recomputed.")
        elif vote.get("unchecked") or not vote.get("checked"):
            # Said only when nothing else checked the answer either: no
            # passage was found on any page, or a figure of the answer is on
            # no page read (owner's ruling, 2026-11-15). Replayed on 283
            # recorded answers it stood beside 71, nearly all right, and was
            # the largest caution left; an answer read from a page that was
            # found does not rest on the vote.
            if unconfirmed or not _handed_on(sources, beside_the_point=True):
                out.append("The recompute vote compared nothing, so no figure "
                           "in this answer was recomputed independently.")
        else:
            open_asks = [a for a in vote.get("no_consensus") or []
                         if a not in backed]
            if open_asks:
                listed = ", ".join(map(str, open_asks))
                out.append(f"The recompute vote reached no majority on ask "
                           f"{listed}; that part of the answer was not compared.")
            open_asks = [a for a in vote.get("not_comparable") or []
                         if a not in backed]
            if open_asks:
                listed = ", ".join(map(str, open_asks))
                out.append(f"The recompute vote could not compare ask {listed}: "
                           f"the answer did not state it as a single value.")
    findings = [f for s in sources for f in s.get("findings") or []]
    if not findings:
        out.append("No lookup ran: figures and citations in this answer "
                   "come from the model's memory and were not checked "
                   "against a source.")
        return out
    quotes = [q for f in findings for q in f.get("quotes") or []]
    if not any(q.get("status") == "found" for q in quotes):
        # Nothing was read. Which of three things happened is said, because
        # each sends the reader somewhere else. Seen twice on the harder
        # professional run: a lookup that quoted nothing was reported as
        # "no page it quoted could be read".
        if not quotes:
            why = "it quoted no passage"
        elif all(q.get("status") == "unfetched" for q in quotes):
            why = "no page it named could be read"
        else:
            why = "none of its passages was found on its page"
        out.append(f"A lookup ran, but {why}, so nothing in this answer was "
                   f"checked against a source.")
    withheld = sum(1 for f in findings if f.get("withheld"))
    if withheld:
        out.append(f"{withheld} lookup answer"
                   f"{'s' if withheld > 1 else ''} had no passage found "
                   f"on a page that could be read, and "
                   f"{'were' if withheld > 1 else 'was'} withheld from "
                   f"the answer.")
    for d in differing or []:
        out.append(f"Two pages handed on give different figures for the same "
                   f"thing: {d['figures'][0]} on {d['pages'][0]} and "
                   f"{d['figures'][1]} on {d['pages'][1]}. The first reads: "
                   f"\"{d['sentence'][:DIFFERING_SENTENCE_CHARS]}\"")
    for u in unconfirmed or []:
        figures = ", ".join(u["figures"])
        out.append(f"The answer gives {figures} for ask {u['ask']}, and "
                   f"that figure is in none of the passages found on their "
                   f"pages.")
    return out


def _summarize(w: Workflow) -> WorkflowSummary:
    return WorkflowSummary(
        id=w.id,
        request=w.request[:200],
        status=w.status.value,
        error=w.error,
        risk_level=w.risk_level,
        iteration=w.iteration,
        total_cost=round(w.total_cost, 4),
        unreconciled_liability=round(w.unreconciled_liability, 4),
        created_at=w.created_at.isoformat(),
        updated_at=w.updated_at.isoformat(),
    )


@router.post("/workflows", status_code=202)
async def submit_workflow(
    body: WorkflowRequest,
    request: Request,
    background: BackgroundTasks,
    session: AsyncSession = Depends(get_session),
):
    # Ruling D45 (6): refused here, before the row exists — a submission that
    # is not admitted must leave nothing behind. Ruling D47: a slot admitted
    # is a slot released — if the commit or the scheduling raises, the gate is
    # restored before the error reaches the caller.
    name, path = _requested_workflow(body)
    caller = _admit_run(request, body.request, name)
    try:
        workflow = Workflow(
            request=body.request,
            status=WorkflowStatus.PENDING,
            user_id=_get_user_id(request),
        )
        session.add(workflow)
        await session.commit()

        background.add_task(_run_workflow_bg, workflow.id, caller,
                            body.request, name, path)
    except BaseException:
        _run_gate.release(caller, body.request, name)
        raise

    return {
        "data": _summarize(workflow),
        "meta": {"message": "Workflow queued for execution"},
    }


async def _run_workflow_bg(workflow_id: int, caller: tuple, request_text: str,
                           name: str, path: str | None):
    from autornd.database import async_session

    try:
        async with async_session() as session:
            stmt = select(Workflow).where(Workflow.id == workflow_id)
            result = await session.execute(stmt)
            workflow = result.scalar_one()

            client = _bound_client()
            engine = WorkflowEngine(client, session)
            try:
                # The row the caller was handed is the row the run writes —
                # one submission, one record (ARCH-20261002-109).
                await engine.execute(workflow.request, workflow=workflow,
                                     workflow_file=path)
            finally:
                await client.close()
    finally:
        _run_gate.release(caller, request_text, name)


@router.post("/workflows/sync")
async def submit_workflow_sync(
    body: WorkflowRequest,
    request: Request,
    session: AsyncSession = Depends(get_session),
):
    """Execute a workflow synchronously and return the full result."""
    name, path = _requested_workflow(body)
    caller = _admit_run(request, body.request, name)

    try:
        workflow = Workflow(
            request=body.request,
            status=WorkflowStatus.PENDING,
            user_id=_get_user_id(request),
        )
        session.add(workflow)
        await session.commit()
    except BaseException:
        _run_gate.release(caller, body.request, name)
        raise

    client = _bound_client()
    engine = WorkflowEngine(client, session)
    try:
        workflow = await engine.execute(body.request, workflow=workflow,
                                        workflow_file=path)
    finally:
        await client.close()
        _run_gate.release(caller, body.request, name)

    await session.refresh(workflow, ["phases"])
    return {"data": _detail(workflow)}


@router.get("/workflows")
async def list_workflows(
    request: Request,
    limit: int = 20,
    offset: int = 0,
    session: AsyncSession = Depends(get_session),
):
    stmt = select(Workflow).order_by(Workflow.created_at.desc())
    user_id = _get_user_id(request)
    if user_id is not None:
        stmt = stmt.where(Workflow.user_id == user_id)
    stmt = stmt.limit(limit).offset(offset)
    result = await session.execute(stmt)
    workflows = result.scalars().all()
    return {
        "data": [_summarize(w) for w in workflows],
        "meta": {"count": len(workflows), "limit": limit, "offset": offset},
    }


@router.get("/workflows/offered")
async def list_offered_workflows():
    """The workflows a request may name, with what each one is (Ruling D55
    (4)). Declared before /workflows/{workflow_id}, so that route is
    unchanged."""
    return {"data": [
        {"name": name, "description": spec.description.strip()}
        for name, spec in offered_workflows().items()]}


async def _load_owned_workflow(
    workflow_id: int, request: Request, session: AsyncSession
) -> Workflow:
    """Load a workflow by id, scoped to the caller when one is authenticated.

    Missing and not-yours both return 404 so ids stay non-enumerable.
    """
    stmt = (
        select(Workflow)
        .where(Workflow.id == workflow_id)
        .options(selectinload(Workflow.phases))
    )
    user_id = _get_user_id(request)
    if user_id is not None:
        stmt = stmt.where(Workflow.user_id == user_id)
    result = await session.execute(stmt)
    workflow = result.scalar_one_or_none()
    if not workflow:
        raise HTTPException(404, "Workflow not found")
    return workflow


@router.get("/workflows/{workflow_id}")
async def get_workflow(
    workflow_id: int,
    request: Request,
    session: AsyncSession = Depends(get_session),
):
    workflow = await _load_owned_workflow(workflow_id, request, session)
    return {"data": _detail(workflow)}


def _detail(w: Workflow) -> WorkflowDetail:
    phases = sorted(w.phases, key=lambda p: p.created_at)
    candidate = next((json.loads(p.verdict_json) for p in reversed(phases)
                      if p.phase == "candidate"), None)
    verdicts = [(p.phase, json.loads(p.verdict_json)) for p in phases]
    answer = None
    if w.status.value == "completed":
        answer = next((v.get("summary") for name, v in reversed(verdicts)
                       if name == "implement" and isinstance(v, dict)), None)
    vote = next((v for name, v in reversed(verdicts)
                 if name == "recompute_vote"), None)
    sources = [v for name, v in verdicts if name == "sources"]
    vote = _settled(verdicts, vote, sources)
    backed: list[int] = []
    unconfirmed: list[dict] = []
    differing: list[dict] = []
    asked = 0
    if answer is not None:
        results = next((v.get("results") for name, v in reversed(verdicts)
                        if name == "implement" and isinstance(v, dict)), None)
        differing = _differing(sources)
        backed, unconfirmed = _checked_figures(results, sources, differing)
        if vote is not None and backed:
            vote = dict(vote, backed_by_source=backed)
        asked = next((len(v.get("asks") or []) for name, v in reversed(verdicts)
                      if name == "asks" and isinstance(v, dict)), 0)
    return WorkflowDetail(
        candidate=candidate,
        answer=answer,
        recompute_vote=vote,
        decisions=[dict(record, where=v.get("where") or name)
                   for name, v in verdicts
                   if isinstance(v, dict) and isinstance(v.get("records"), list)
                   for record in v["records"] if isinstance(record, dict)
                   and "switch" in record],
        sources=sources,
        cautions=_cautions(vote, sources, answer is not None, asked,
                           unconfirmed, differing),
        confirmations=_confirmations(backed, answer is not None),
        id=w.id,
        request=w.request,
        status=w.status.value,
        error=w.error,
        risk_level=w.risk_level,
        iteration=w.iteration,
        total_cost=round(w.total_cost, 4),
        unreconciled_liability=round(w.unreconciled_liability, 4),
        created_at=w.created_at.isoformat(),
        updated_at=w.updated_at.isoformat(),
        phases=[
            PhaseDetail(
                phase=p.phase,
                iteration=p.iteration,
                verdict=json.loads(p.verdict_json),
                model_used=p.model_used,
                cost=round(p.cost, 6),
                created_at=p.created_at.isoformat(),
            )
            for p in phases
        ],
    )


@router.get("/workflows/{workflow_id}/doublecheck/estimate")
async def estimate_doublecheck(
    workflow_id: int,
    request: Request,
    session: AsyncSession = Depends(get_session),
):
    from autornd.config import settings
    if not settings.model_premium:
        raise HTTPException(404, "Premium model not configured")

    workflow = await _load_owned_workflow(workflow_id, request, session)
    if workflow.status.value not in ("completed", "escalated", "blocked"):
        raise HTTPException(400, "Workflow is still running")

    payload_chars = len(workflow.request)
    for p in workflow.phases:
        payload_chars += len(p.verdict_json)
    est_tokens = payload_chars // 3
    # Ruling D47 (2): every route that CAN spend passes the run gate. This one
    # makes no call — _estimate_cost is local arithmetic over the catalogue
    # rate — so there is nothing to admit and nothing to count.
    client = OpenRouterClient()
    cost = client._estimate_cost(settings.model_premium, est_tokens, est_tokens // 2)
    return {"data": {"estimated_cost": round(cost, 4), "model": settings.model_premium}}


@router.post("/workflows/{workflow_id}/doublecheck")
async def run_doublecheck_endpoint(
    workflow_id: int,
    request: Request,
    session: AsyncSession = Depends(get_session),
):
    from autornd.config import settings
    from autornd.engine.phases import run_doublecheck
    from autornd.models.verdicts import ImplementVerdict

    if not settings.model_premium:
        raise HTTPException(404, "Premium model not configured")

    workflow = await _load_owned_workflow(workflow_id, request, session)
    if workflow.status.value not in ("completed", "escalated", "blocked"):
        raise HTTPException(400, "Workflow is still running")

    impl_data = None
    for p in sorted(workflow.phases, key=lambda x: x.created_at):
        v = json.loads(p.verdict_json)
        if p.phase == "implement":
            impl_data = v

    # The implement phase's presence proves the workflow produced
    # an answer to doublecheck. The plan is not required —
    # verify-first has none, and Ruling D51 (R-d) took the plan
    # out of the prompt the doublecheck reads, so only the
    # implementation's verdict is constructed.
    if not impl_data:
        raise HTTPException(400, "Workflow missing implement phase")

    implement = ImplementVerdict(**impl_data)

    # Ruling D47 (2): the doublecheck can spend, so it passes the same run
    # gate as the submit paths and counts against max_concurrent_runs — no
    # caller multiplies the per-run bounds by calling this many times at once.
    # The dedupe key is the workflow's own request text, under the name
    # "doublecheck" (Ruling D55 (6) keys the gate by workflow too): a second
    # doublecheck of a workflow the caller already has in flight is a
    # duplicate (409).
    caller = _admit_run(request, workflow.request, "doublecheck")
    try:
        client = _bound_client()
        try:
            verdict, response = await run_doublecheck(
                client, workflow.request, implement,
            )
        finally:
            await client.close()

        phase_result = PhaseResult(
            workflow_id=workflow.id,
            phase="doublecheck",
            iteration=1,
            verdict_json=json.dumps(verdict.model_dump()),
            model_used=response.model,
            cost=response.cost,
        )
        session.add(phase_result)
        workflow.total_cost += response.cost
        await session.commit()

        return {
            "data": {
                "verdict": verdict.model_dump(),
                "model": response.model,
                "cost": round(response.cost, 4),
            }
        }
    finally:
        _run_gate.release(caller, workflow.request, "doublecheck")


# ── Settings endpoints ──

SENSITIVE_FIELDS = {"openrouter_api_key", "api_key", "jwt_secret"}


@router.get("/settings")
async def get_settings():
    from autornd.config import Settings, settings

    data = {}
    for field_name in Settings.model_fields:
        if field_name in ("model_config", "RUNTIME_MUTABLE"):
            continue
        val = getattr(settings, field_name)
        if field_name in SENSITIVE_FIELDS and val:
            val = "****" + val[-4:] if len(val) > 4 else "****"
        data[field_name] = val
    return {
        "data": data,
        "meta": {"runtime_mutable": sorted(settings.RUNTIME_MUTABLE)},
    }


class SettingsUpdate(BaseModel):
    max_iterations: int | None = None
    escalation_max_tokens: int | None = None
    escalation_recovery_attempts: int | None = None
    autornd_profile: str | None = None
    log_level: str | None = None


@router.put("/settings")
async def update_settings(body: SettingsUpdate, request: Request):
    import logging

    from autornd.config import settings

    # Ruling D45 (3): loopback only. A runtime change applies to every run in
    # flight, so it is not a remote caller's to make.
    if not _is_loopback(request):
        raise HTTPException(
            403, "Runtime settings are for loopback callers only (Ruling "
                 "D45); change them in .env or from this machine.")

    updates = body.model_dump(exclude_none=True)
    if not updates:
        raise HTTPException(400, "No settings to update")

    bad = set(updates) - settings.RUNTIME_MUTABLE
    if bad:
        raise HTTPException(400, f"Cannot change at runtime: {', '.join(sorted(bad))}")

    if "max_iterations" in updates:
        v = updates["max_iterations"]
        if not 1 <= v <= 20:
            raise HTTPException(422, "max_iterations must be between 1 and 20")

    if "log_level" in updates:
        valid = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        if updates["log_level"].upper() not in valid:
            raise HTTPException(422, f"log_level must be one of {sorted(valid)}")
        updates["log_level"] = updates["log_level"].upper()

    # After the validators: an invalid value is still 422. This is the rule
    # itself — Ruling D45 (3): a ceiling may be lowered at runtime and never
    # raised above its startup value, because a raise applies to every run in
    # flight and any caller the middleware admits could make it (review F8).
    raised = [name for name, value in updates.items()
              if not _only_tightens(name, value)]
    if raised:
        raise HTTPException(
            400,
            "Runtime settings can only tighten (Ruling D45); "
            f"{', '.join(sorted(raised))} would be raised above its startup "
            f"value. Change it in .env and restart.")

    profile_changed = False
    for key, val in updates.items():
        if key == "autornd_profile" and val != settings.autornd_profile:
            profile_changed = True
        setattr(settings, key, val)

    if "log_level" in updates:
        logging.getLogger("autornd").setLevel(updates["log_level"])

    if profile_changed and settings.autornd_profile:
        from autornd.profiles import load_profile, set_profile
        from autornd.specialists.registry import reload_specialists
        profile = load_profile(settings.autornd_profile)
        set_profile(profile)
        reload_specialists()

    return {"data": {"updated": list(updates.keys())}}


@router.get("/health")
async def health():
    from autornd.config import settings
    from autornd.routing.openrouter import get_model_status

    model_status = get_model_status()
    # `None` means the catalogue check itself failed — that is a degraded state,
    # not a healthy one. Only an explicit True counts as verified.
    unverified = [
        fn for fn, st in model_status.items() if st.get("available") is not True
    ]
    return {
        "status": "degraded" if unverified else "ok",
        "unverified_models": unverified,
        "service": "autornd",
        "premium_model": settings.model_premium or None,
        # Ruling D45 (1): the override is reported here and logged at
        # startup, so an open server cannot be mistaken for a closed one.
        "authentication_configured": bool(settings.api_key or settings.jwt_secret),
        "allow_unauthenticated_remote": settings.allow_unauthenticated_remote,
        "models": model_status,
    }


@router.get("/profiles")
async def get_profiles():
    from autornd.profiles import get_profile, list_profiles
    active = get_profile()
    return {
        "data": {
            "active": active.name,
            "available": list_profiles(),
        }
    }


@router.post("/profiles/{name}")
async def switch_profile(name: str, request: Request):
    from autornd.profiles import load_profile, set_profile
    from autornd.specialists.registry import reload_specialists

    # Ruling D45 (3): swapping the profile rewrites every specialist prompt
    # for every run in flight — loopback only, like the settings it shadows.
    if not _is_loopback(request):
        raise HTTPException(
            403, "Switching profiles is for loopback callers only (Ruling "
                 "D45); set AUTORND_PROFILE in .env or use this machine.")
    profile = load_profile(name)
    set_profile(profile)
    reload_specialists()
    return {"data": {"active": profile.name}}


@router.get("/knowledge/stats")
async def knowledge_stats():
    from autornd.knowledge.store import get_stats
    return {"data": get_stats()}


@router.get("/episodes")
async def list_episodes(
    request: Request,
    limit: int = 10,
    session: AsyncSession = Depends(get_session),
):
    from autornd.knowledge.episodic import get_recent_episodes

    # Ruling D45 (4): a caller sees their own runs, as /api/workflows does.
    episodes = await get_recent_episodes(
        session, limit=limit, user_id=_get_user_id(request))
    return {
        "data": [
            {
                "id": ep.id,
                "workflow_id": ep.workflow_id,
                "request": ep.request[:200],
                "domains": ep.domains,
                "risk": ep.risk,
                "iterations": ep.iterations,
                "shipped": ep.shipped,
                "verdict": ep.verdict[:200],
                "findings_count": ep.findings_count,
                "total_cost": round(ep.total_cost, 4),
                "created_at": ep.created_at.isoformat(),
            }
            for ep in episodes
        ],
        "meta": {"count": len(episodes)},
    }
