"""Outward research: look up what the project's own documents do not cover.

This is the anti-confabulation mechanism, and it exists because of a measured
failure. Asked which charger IC a specific board uses, a capable model answered
"IP5306" in bold with no hedge. A search-backed model answered "MCP73831" with
eighteen citations. Asked the EU 868 MHz limit, the same model gave "25 mW
(+14 dBm EIRP)" — conflating ERP with EIRP, two units 2.15 dB apart, which is
the difference between a compliant transmitter and a failed certification.

Both answers were confident. One was a wrong component in a bill of materials
and the other a non-compliant design, and nothing in either response signalled
doubt. That is the whole argument: apparent certainty does not correlate with
correctness, so there is no confidence signal to gate a lookup on. Look it up.

The loop is driven by gaps rather than by curiosity. The briefing already says
what the project documentation fails to cover; those gaps become the queries,
so the only thing ever searched is something known to be missing. Findings are
ingested, so a fact looked up once is local for every workflow after.

Ruling D56 adds the check the citations never were. Every answer quotes the
passage it rests on, and the harness fetches the page and looks for the
passage in it. An answer whose passage is found there is checked, and only a
found passage is kept for later runs. A question whose passage is not found is
asked once more; what is still not found is marked unverified.
"""

from __future__ import annotations

import asyncio
import logging
import unicodedata
from dataclasses import dataclass, field

from autornd.config import settings
from autornd.knowledge.fetch import MAX_FETCHES, fetch_source
from autornd.knowledge.store import ingest_text, retrieve
from autornd.models.verdicts import LookupVerdict, QuotedPassage

from autornd.routing.openrouter import BudgetExceeded, extract_json

logger = logging.getLogger(__name__)

# Lookups the provider refused, counted since process start.
#
# Swallowing a failed lookup is right — three facts out of four beats aborting,
# and the missing one stays visible as a gap — but it is silent, and silence
# scored whole eval arms in 007. A spend ceiling began refusing every completion
# partway through a sweep; the affected units ran, found nothing, and scored
# zero, which is indistinguishable from a model that found nothing. Only the
# per-unit lookup counts separated a poisoned run from a bad one, and they had
# to be gone looking for. A refusal is now counted where it is swallowed, so a
# result carries the reason it is empty.
_refused_lookups = 0


def refused_lookups() -> int:
    return _refused_lookups


def reset_refused_lookups() -> None:
    global _refused_lookups
    _refused_lookups = 0


# Ruling D56 (1): lookup replies that were not the typed format, counted since
# process start. Each is kept as an unverified answer; the count is how a
# search serving that ignores the format shows.
_untyped_replies = 0


def untyped_replies() -> int:
    return _untyped_replies


def reset_untyped_replies() -> None:
    global _untyped_replies
    _untyped_replies = 0

# A budget stop is a decision, not a failure. Every handler below exists so a
# lookup that breaks does not take the workflow with it, and each one would
# otherwise swallow the ceiling that was meant to end the run — leaving the
# sweep to keep spending after it had already been told to stop. Worse at the
# rerank sites, which latch their strategy off any exception: an abort would
# permanently mark a working rerank API as unsupported. §6.8 records that exact
# bug from the last time an exception type was caught too widely.

__all__ = ["Finding", "Quote", "quote_found", "research_gaps"]

# One request per workflow.
#
# Measured, not estimated: once every call was actually priced, search turned
# out to be 61% of a full workflow and 98% of a grounding run — $0.72 of a
# $0.74 eight-sector pass, about $0.024 a lookup at four lookups per workflow.
# Search is by a wide margin the most expensive thing this harness does.
#
# So the gaps are asked together rather than one at a time. A search-backed
# model answers a five-part question in one pass nearly as well as five
# separate ones, and one request carries one search fee. The token budget goes
# up to match, because a single answer now has to cover everything the work was
# missing rather than one figure.
MAX_LOOKUPS = 1

# Ruling D56 (4): a question whose quoted passage was not found in its page is
# asked once more, together with the others not found, in one more request.
# Two rounds at most, so one more search fee, and only when a check failed. An
# answer that quoted nothing is not asked again: the model did not follow the
# format, and the same request again buys little.
MAX_ROUNDS = 2

# Ruling D56 (3): a passage shorter than this checks nothing. "25 mW" is on
# many pages; a sentence is on few. Not measured: about the shortest passage
# that carries a figure, its unit and its condition.
MIN_QUOTE_CHARS = 20

# Ruling D56 (5): what is kept for later runs, and the only thing recalled. A
# new tag, so findings stored before D56, which nothing checked, are no longer
# recalled. They stay in the store.
RESEARCH_TAG = "research-quoted"

# How close a stored finding must be to count as already answering a gap.
# The collection is cosine (store.py creates it with hnsw:space cosine), so
# this is a cosine distance: 0 is the same text, smaller is nearer. The value
# was 0.35 while this comment called the distance squared L2. The embedder
# returns unit vectors, on which squared L2 is twice the cosine distance, so
# that intent, near-restatements only, is 0.175 here (Ruling D56 (5)). Set
# conservatively on purpose: reusing the wrong finding is a wrong figure in a
# design, while a needless lookup only costs money.
REUSE_DISTANCE = 0.175

LOOKUP_PROMPT = """\
Answer these {questions} from authoritative sources — {sources}.

{question}

Answer every question above. Each one is here because the work cannot proceed
on an assumption about it, so a partial answer leaves the work blocked.

Rules:
- Give the figures, with their units exactly as the source states them.
- Distinguish units that are commonly confused.{unit_examples}
- Name the source document for every figure.
- Name the standard or code that governs this class of work, even when the
  question does not mention one.
- Add what a practitioner would expect to see that the question did not ask
  for.{gap_examples} The
  person asking usually does not know what they left out.
- If authoritative sources disagree, say so and give both.
- If you cannot find it, say so plainly. An admitted gap is useful; a plausible
  guess is worse than nothing, because everything downstream will trust it.
  This applies to the additions above too: an element you cannot source is
  named as unverified, never stated as a specification.

Quote, for every answer, the passage it rests on: copied character for
character from the page, nothing left out and nothing reworded, at least a
full sentence. Give the address of that page itself, one that can be read as
HTML or plain text. Each page is fetched and each passage looked for in it; an
answer whose passage is not found there is marked unverified.

Reply with JSON only:
{{"answer": "<the full answer, written as the rules above ask>",
  "quotes": [{{"question": <the number of the question it answers, 1 if
  there is one>, "text": "<the passage, exactly as the page prints it>",
  "url": "<the page's address>"}}]}}
"""

# Ruling D56 (4): the second round's question, ahead of the questions asked
# again.
AGAIN_PROMPT = """\
An earlier answer to these could not be checked: no passage it quoted was
found in the page it named, or the page could not be read as HTML or plain
text. Answer them again, and quote each passage exactly as such a page prints
it.

{questions}"""

# Characters a passage and its page often print differently, read as one.
_SAME_CHARACTER = str.maketrans({
    "\u2018": "'", "\u2019": "'", "\u201a": "'", "\u201b": "'", "\u2032": "'",
    "\u201c": '"', "\u201d": '"', "\u201e": '"', "\u201f": '"', "\u2033": '"',
    "\u2010": "-", "\u2011": "-", "\u2012": "-", "\u2013": "-", "\u2014": "-",
    "\u2212": "-", "\u00ad": None,
})


def _normalise(text: str) -> str:
    """Text as the quote check compares it: one form for each character,
    one space for each run of whitespace, and no case."""
    text = unicodedata.normalize("NFKC", text).translate(_SAME_CHARACTER)
    return " ".join(text.split()).casefold()


def _passage(quote: str) -> str:
    return _normalise(quote).strip(" \"'")


def quote_found(quote: str, page: str) -> bool:
    """Ruling D56 (3): is this passage in this page's text?

    Free and deterministic. Nothing is left out: a passage with a word
    missing or changed is not found. Spacing, case, curly quotes, dashes and
    soft hyphens are read alike, because pages and models print those
    differently without changing a word.
    """
    passage = _passage(quote)
    return len(passage) >= MIN_QUOTE_CHARS and passage in _normalise(page)


@dataclass
class Quote:
    """A quoted passage, and what the check found (Ruling D56 (3)).

    `status` is "found" (the passage is in the page fetched), "not_found"
    (the page was read and the passage is not in it), "unfetched" (the page
    could not be read; `reason` says why) or "too_short" (under
    MIN_QUOTE_CHARS, so not checked). Found means the words are on the page,
    not that the answer follows from them.
    """

    question: int
    text: str
    url: str
    status: str = "unchecked"
    reason: str = ""
    fetched_at: str = ""
    sha256: str = ""


@dataclass
class Finding:
    question: str
    answer: str
    citations: list[str] = field(default_factory=list)
    model: str = ""
    # Ruling D56: the questions this lookup asked, numbered from 1 as the
    # prompt numbered them; the passages it quoted; the round that asked.
    asked: list[str] = field(default_factory=list)
    quotes: list[Quote] = field(default_factory=list)
    round: int = 1

    @property
    def grounded(self) -> bool:
        """Did anything back this up?

        An uncited finding is the failure mode this exists to prevent — a
        confident assertion with nothing behind it. Kept, because a model saying
        "I could not find this" is genuinely useful, but marked, because a
        reader must be able to tell the two apart.
        """
        return bool(self.citations)

    @property
    def recalled(self) -> bool:
        """Recalled from the store: a passage found in its page on an earlier run."""
        return self.model == "recalled"

    def _asked(self) -> list[str]:
        return self.asked or [self.question]

    def checked(self) -> set[int]:
        """The numbers of the questions a passage found in its page backs."""
        count = len(self._asked())
        return {q.question for q in self.quotes
                if q.status == "found" and 1 <= q.question <= count}

    def unchecked(self) -> list[int]:
        """The numbers of the questions no found passage backs."""
        if self.recalled:
            return []
        found = self.checked()
        return [n for n in range(1, len(self._asked()) + 1) if n not in found]

    def to_ask_again(self) -> list[str]:
        """Ruling D56 (4): the questions that quoted a passage and had none found."""
        quoted = {q.question for q in self.quotes}
        return [self._asked()[n - 1] for n in self.unchecked() if n in quoted]

    def render(self) -> str:
        label = "Q (asked again)" if self.round > 1 else "Q"
        lines = [f"{label}: {self.question}", f"A: {self.answer}"]
        found = [q for q in self.quotes if q.status == "found"]
        if self.citations:
            lines.append("Sources: " + ", ".join(self.citations[:5]))
        elif not found:
            lines.append("Sources: none found — treat as unverified")
        if found:
            lines.append("Passages quoted and found in the page fetched:")
            lines += [f'- [{q.question}] "{q.text}" — {q.url} (fetched '
                      f'{q.fetched_at}, sha256 {q.sha256[:12]})' for q in found]
        unchecked = self.unchecked()
        if unchecked and len(self._asked()) > 1:
            lines.append(
                "No quoted passage was found in its page for question"
                f"{'s' if len(unchecked) > 1 else ''} "
                f"{', '.join(map(str, unchecked))} — treat "
                f"{'those answers' if len(unchecked) > 1 else 'that answer'} "
                f"as unverified.")
        elif unchecked:
            lines.append("No quoted passage was found in its page — treat this "
                         "answer as unverified.")
        return "\n".join(lines)


async def research_gaps(
    client,
    request: str,
    gaps: list[str],
    max_lookups: int = MAX_LOOKUPS,
    max_tokens: int | None = None,
) -> list[Finding]:
    """Look up the gaps a briefing identified, check them, and keep what holds.

    Returns findings in gap order, a second round's finding right after the
    one it asks again. Failure of a single lookup is not fatal: a workflow
    with three of four facts is better off than one that aborted, and the
    missing one stays visible as a gap. A page that cannot be fetched never
    fails a lookup; it leaves its answer unverified.
    """
    if client is None or not settings.model_search or not gaps:
        return []

    # Ask everything in one request. Splitting the gaps would mean one search
    # fee each, and the fee is charged per request rather than per question.
    questions = [g.strip() for g in gaps if g and g.strip()]
    if not questions:
        return []
    if max_lookups <= 1 and len(questions) > 1:
        lookups = [questions]
    else:
        lookups = [[gap] for gap in gaps[:max_lookups]]

    findings: list[Finding] = []
    for asked in lookups:
        question = _bundle(asked)
        # Ask the store before paying anyone. Findings are ingested, so a fact
        # looked up once is local for every workflow after — and the cheapest
        # search is the one already answered. This is the same lever as
        # everywhere else: the local check is free and it is also more
        # consistent, because it returns the figure already cited rather than
        # re-asking and hoping for the same answer.
        reused = _recall(question)
        if reused is not None:
            findings.append(reused)
            continue
        finding = await _ask(client, request, asked, max_tokens)
        if finding is None:
            continue
        findings.append(finding)
        _remember(finding)   # recalled findings skip this: already stored
        again = finding.to_ask_again()
        if again and MAX_ROUNDS > 1:
            second = await _ask(client, request, again, max_tokens, round_=2)
            if second is not None:
                findings.append(second)
                _remember(second)

    if findings:
        checked = sum(len(f.checked()) for f in findings)
        unchecked = sum(len(f.unchecked()) for f in findings)
        logger.info(
            "Researched %d gap(s) in %d lookup(s): %d answer(s) backed by a "
            "passage found in its page, %d unverified",
            len(questions), len(findings), checked, unchecked,
        )
    return findings


def _bundle(asked: list[str]) -> str:
    """The question text of one lookup: one question, or several numbered."""
    if len(asked) == 1:
        return asked[0]
    return "\n".join(f"{i}. {q}" for i, q in enumerate(asked, 1))


async def _ask(client, request: str, asked: list[str], max_tokens: int | None,
               round_: int = 1) -> Finding | None:
    """One lookup, checked. None when it failed or found nothing."""
    question = _bundle(asked)
    prompt = question if round_ == 1 else AGAIN_PROMPT.format(questions=question)
    try:
        answer, citations, model, quotes = await _lookup(
            client, request, prompt, max_tokens=max_tokens)
    except BudgetExceeded:
        raise
    except Exception as exc:
        global _refused_lookups
        _refused_lookups += 1
        logger.warning("Lookup failed for %r: %s", question[:60], exc)
        return None
    if not answer:
        return None
    finding = Finding(question=question, answer=answer, citations=citations,
                      model=model, asked=list(asked), round=round_,
                      quotes=[Quote(q.question, q.text, q.url) for q in quotes])
    await _check(finding)
    return finding


async def _check(finding: Finding) -> None:
    """Ruling D56 (3): fetch each quoted page once, and look for each passage in it."""
    for quote in finding.quotes:
        if len(_passage(quote.text)) < MIN_QUOTE_CHARS:
            quote.status = "too_short"
    urls = list(dict.fromkeys(q.url for q in finding.quotes
                              if q.status != "too_short"))[:MAX_FETCHES]
    sources = dict(zip(urls, await asyncio.gather(*(fetch_source(u) for u in urls))))
    for quote in finding.quotes:
        if quote.status == "too_short":
            continue
        source = sources.get(quote.url)
        if source is None:
            quote.status = "unfetched"
            quote.reason = f"past the {MAX_FETCHES}-page fetch cap"
        elif not source.fetched:
            quote.status, quote.reason = "unfetched", source.reason
        else:
            quote.fetched_at, quote.sha256 = source.fetched_at, source.sha256
            quote.status = ("found" if quote_found(quote.text, source.text)
                            else "not_found")


def _recall(question: str) -> Finding | None:
    """A stored finding that already answers this gap, if there is one.

    Only previously researched material counts. Project documentation is
    already in the briefing that produced the gap, so treating a documentation
    chunk as an answer would mean the gap was never a gap.
    """
    try:
        hits = retrieve(question, n_results=1, where={"tag": RESEARCH_TAG})
    except Exception as exc:
        logger.debug("Could not check the store for %r: %s", question[:60], exc)
        return None
    if not hits:
        return None

    hit = hits[0]
    distance = hit.get("distance")
    if distance is None or distance > REUSE_DISTANCE:
        return None

    logger.info("Reusing a stored finding for %r (distance %.3f) — no lookup",
                question[:60], distance)
    return Finding(
        question=question,
        answer=hit["text"],
        citations=[hit["source"]] if hit.get("source") else [],
        model="recalled",
    )


async def _lookup(client, request: str, question: str,
                  max_tokens: int | None = None
                  ) -> tuple[str, list[str], str, list[QuotedPassage]]:
    """One search-backed lookup. Returns (answer, citations, model, quotes).

    Ruling D56 (1): the reply is typed, so its quotes are fields, never read
    out of prose. It stays a plain chat: the parameters it sends are the ones
    preflight checks the search serving for, and one reply is one search fee,
    with no retry for its shape.
    """
    from autornd.profiles import framing, get_profile
    f = framing()
    profile = get_profile()
    response = await client.chat(
        function="search",
        system_prompt=(
            f"You answer {f['questions']} from authoritative sources and "
            f"cite them. You never present a guess as a specification."
        ),
        user_message=LOOKUP_PROMPT.format(question=question, **framing())
        + f"\n\nThis is being looked up in service of: {request}",
        temperature=0.0,
        max_tokens=max_tokens or settings.search_max_tokens,
    )
    content = (response.content or "").strip()
    try:
        data = extract_json(content)
        if "answer" not in data:
            raise ValueError("the reply has no answer field")
        verdict = LookupVerdict.model_validate(data)
    except ValueError as exc:
        # Convention 21: a reply in prose loses no word of its answer, so it
        # is kept whole as the answer, with no quotes, which marks it
        # unverified. Counted, so a search serving that ignores the format
        # shows as one.
        global _untyped_replies
        _untyped_replies += 1
        logger.warning("Lookup reply is not the typed format (%s); kept as "
                       "an unverified answer", exc)
        verdict = LookupVerdict(answer=content)
    return (
        verdict.answer.strip(),
        list(getattr(response, "citations", None) or []),
        response.model,
        verdict.quotes,
    )


def _remember(finding: Finding) -> None:
    """Keep each passage found in its page, so the next workflow has it.

    Ruling D56 (5): only a found passage is kept, one entry per passage, under
    its own page's address, with the question it answers and the version
    read. An answer nothing checked is worth showing to the person running
    this workflow and is not worth becoming permanent context that later runs
    treat as project knowledge.
    """
    asked = finding.asked or [finding.question]
    for quote in finding.quotes:
        if quote.status != "found" or not 1 <= quote.question <= len(asked):
            continue
        try:
            ingest_text(
                f"Q: {asked[quote.question - 1]}\n"
                f'The page says: "{quote.text}"\n'
                f"Page: {quote.url} (fetched {quote.fetched_at}, "
                f"sha256 {quote.sha256})",
                tag=RESEARCH_TAG,
                source=quote.url,
            )
        except Exception as exc:
            logger.warning("Could not store finding: %s", exc)


def render_findings(findings: list[Finding]) -> str:
    """Findings as prompt context, with their provenance attached."""
    if not findings:
        return ""
    body = "\n\n".join(f.render() for f in findings)
    unverified = [f for f in findings if f.unchecked()]
    header = (
        "=== RESEARCHED FACTS (looked up because the project documentation did "
        "not cover them) ==="
    )
    if unverified:
        header += (
            f"\n{len(unverified)} of {len(findings)} have answers no passage found "
            f"in its page backs, marked unverified — do not treat those as "
            f"specifications."
        )
    return f"{header}\n{body}"
