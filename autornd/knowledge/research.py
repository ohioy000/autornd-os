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

Ruling D56 added the check the citations never were: a quoted passage is
looked for in the page it names, and only a found passage is kept for later
runs. Since the owner's rulings of 2026-11-15 and 16 there is one lookup: the
search model is asked where the answer is written, the harness fetches those
pages, and the passages handed on are the pages' own words. The earlier
lookup, which asked the search model for an answer and its quotes, was
removed on 2026-11-16: on 432 answers read blind it was right in 141 of 144
against 144 of 144 (docs/reviews/2026-11-16-misleading-set-run.md).
"""

from __future__ import annotations

import asyncio
import logging
import math
import re
import unicodedata
from urllib.parse import urlsplit
from dataclasses import dataclass, field

from autornd.config import settings
from autornd.knowledge.absence import Proof, name_terms, prove, render_proofs
from autornd.knowledge.fetch import Source, fetch_source
from autornd.knowledge.store import ingest_text, retrieve
from autornd.routing.openrouter import BudgetExceeded, extract_json
from autornd.routing.pins import tier_model

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


# A budget stop is a decision, not a failure. Every handler below exists so a
# lookup that breaks does not take the workflow with it, and each one would
# otherwise swallow the ceiling that was meant to end the run — leaving the
# sweep to keep spending after it had already been told to stop. Worse at the
# rerank sites, which latch their strategy off any exception: an abort would
# permanently mark a working rerank API as unsupported. §6.8 records that exact
# bug from the last time an exception type was caught too widely.

# Sites that refuse to be read, learned in this process, so a later lookup
# can be told to quote from somewhere else (settings.lookup_avoid_unreadable).
# A refusal is the site's answer to us, not to the page: "HTTP 403" or a
# challenge page. A missing page ("HTTP 404") says nothing about the site.
# One refusal is not enough, and a site that has been read here is never
# listed: in the sweep of 2026-11-14 one challenge page from ecfr.gov, which
# had been read all day, listed it, and the lookups told to avoid it then
# got the rule's figure wrong in 3 of 8 answers.
_unreadable_sites: dict[str, str] = {}
_refusals: dict[str, int] = {}
_read_sites: set[str] = set()
_REFUSALS = ("HTTP 401", "HTTP 403", "HTTP 429", "HTTP 451")
REFUSALS_TO_LIST = 2


def unreadable_sites() -> dict[str, str]:
    """The sites listed as refusing to be read, with the last reason."""
    return dict(_unreadable_sites)


def reset_unreadable_sites() -> None:
    _unreadable_sites.clear()
    _refusals.clear()
    _read_sites.clear()


def _site(url: str) -> str:
    host = (urlsplit(url).hostname or "").lower()
    return host[4:] if host.startswith("www.") else host


def _note_fetch(url: str, source) -> None:
    site = _site(url)
    if not site:
        return
    if source.fetched:
        _read_sites.add(site)
        _unreadable_sites.pop(site, None)
    elif (site not in _read_sites
          and (source.reason in _REFUSALS or "challenge page" in source.reason)):
        _refusals[site] = _refusals.get(site, 0) + 1
        if _refusals[site] >= REFUSALS_TO_LIST:
            _unreadable_sites[site] = source.reason


__all__ = ["Finding", "Quote", "quote_found", "research_gaps",
           "source_records"]

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

# The search model is asked where the answer
# is written, not what it is. The harness reads the pages itself.
DOCUMENTS_PROMPT = """\
Find the documents in which the answer to the request below is written. Do
not answer the request.

Request:
{request}

What the work needs settled:
{question}

Rules:
- Give the page of the rule, standard, specification or published document
  itself, in its current edition, ahead of any page that describes or
  summarises it.
- Give the most specific page there is: the section, not the whole part.
- Give only addresses that can be read as HTML, plain text or PDF.
- For each document, give a few words that stand in it right where the answer
  is, copied as the document prints them.

Reply with JSON only, at most {limit} documents, the best first:
{{"documents": [{{"url": "<the page's address>", "title": "<what it is>",
  "near": "<a few words from the passage that holds the answer>"}}]}}
"""

# Added to the request for documents when sites are known to refuse us.
DOCUMENTS_AVOID_PROMPT = """\


These sites refuse to be read from here: {sites}. Give no address on them.
Where a document is on one of them, give the same document on a site that
can be read."""

# How much of the fetched pages is handed on. A page this short is handed on
# whole; of a longer one, the stretches that share most words with the
# request and with the search model's own pointer. Set on the root-cause test
# of 2026-11-15, where 2,500 characters a page chosen by shared words was
# enough on one question and, with no pointer, missed on a misspelt one.
DOCUMENT_WHOLE_CHARS = 4000
DOCUMENT_EXCERPT_CHARS = 1200
DOCUMENT_EXCERPTS = 3
MAX_DOCUMENTS = 6

# The reader tier (owner's ruling, 2026-11-20). A page too long to hand on whole
# is cut into the READER_CHUNKS stretches that share the most words with the
# question, each READER_CHUNK_CHARS long, and each goes to its own call of the
# reader model, all at once (READER_CONCURRENCY at a time). The model copies back
# up to READER_PASSAGES stretches of its text, word for word, that bear on the
# question; each is put through quote_found and one not on the page is dropped.
# Sized from a free replay of 36 pages on 2026-11-20: a lookup's pages run to
# hundreds of thousands of characters and the PDF read, not the reading,
# takes the time, so what the reader is for is which stretches are handed on,
# not speed. 6 stretches of 6,000 characters is about 1,500 tokens a call and
# at most 36 calls a lookup, a few tenths of a cent at a small model's rate.
READER_CHUNK_CHARS = 6000
READER_CHUNKS = 6
READER_PASSAGES = 3
READER_CONCURRENCY = 8
READER_MAX_TOKENS = 1200
# The shortest pointer looked for on a page. Shorter ones ("the limit") are
# on most pages and tell nothing; the same floor as a quote's.
MIN_POINTER_CHARS = MIN_QUOTE_CHARS
_TERM = re.compile(r"[a-z0-9]{3,}")

_SAME_CHARACTER = str.maketrans({
    "\u2018": "'", "\u2019": "'", "\u201a": "'", "\u201b": "'", "\u2032": "'",
    "\u201c": '"', "\u201d": '"', "\u201e": '"', "\u201f": '"', "\u2033": '"',
    "\u2010": "-", "\u2011": "-", "\u2012": "-", "\u2013": "-", "\u2014": "-",
    "\u2212": "-", "\u00ad": None,
    # Zero-width characters: printed by pages, never by a model quoting them.
    "\u200b": None, "\u200c": None, "\u200d": None, "\u2060": None,
    "\ufeff": None,
})


# A page's own reference marks ("[3]", "[12]") sit inside sentences a model
# quotes without them, and the other way round. Not words of the passage.
_REFERENCE_MARK = re.compile(r"\[\d{1,3}\]")


def _normalise(text: str) -> str:
    """Text as the quote check compares it: one form for each character,
    one space for each run of whitespace, no case, and no reference marks."""
    text = unicodedata.normalize("NFKC", text).translate(_SAME_CHARACTER)
    text = _REFERENCE_MARK.sub("", text)
    return " ".join(text.split()).casefold()


def _passage(quote: str) -> str:
    # The closing mark of a sentence is where a model and a page most often
    # differ (a quote ended with a full stop the page follows with a comma),
    # and it changes no word, so it is not compared.
    return _normalise(quote).strip(" \"'").rstrip(".,;:").rstrip(" \"'")


# A line of dashes between a table's heading and its rows: layout, not words.
_TABLE_RULE = re.compile(r":?-+:?")


def _table_rows(quote: str) -> list[str] | None:
    """The rows of a quote written as a grid of cells, or None for prose.

    A search model quotes a table with a bar between the cells
    ("|(7) Nitrate|10 (as Nitrogen)|"); the page prints the same cells with
    a space between them. Measured 2026-11-15 (the lookup test): 11 quotes of
    one eCFR table held the answer and none was found, because the bars are
    not on the page. A quote is a grid only when every line of it is.
    """
    lines = [line.strip() for line in quote.splitlines() if line.strip()]
    if not lines or not all(len(line) > 1 and line.startswith("|")
                            and line.endswith("|") for line in lines):
        return None
    rows = []
    for line in lines:
        cells = [c.strip() for c in line.strip("|").split("|") if c.strip()]
        if cells and not all(_TABLE_RULE.fullmatch(c) for c in cells):
            rows.append(_normalise(" ".join(cells)))
    return rows or None


# Marks a search model adds when it quotes a page and the page does not
# print: emphasis stars and the hashes of a heading. Measured 2026-11-14 on
# the 74 quotes of three lookup tests that were not found on a page that was
# read: 12 were on the page word for word once the marks were dropped.
_EMPHASIS = re.compile(r"\*+")
_HEADING = re.compile(r"(?m)^\s*#{1,6}\s+")
# Three more of the same kind (owner's ruling, 2026-11-15), read off the 11
# quotes of the professional baseline that were on a page and not matched:
# the tildes of a subscript ("O~3~"), a backslash before a mark ("1\."),
# and a list mark at the start of a line ("1. ", "- ").
# And the carets of a superscript ("µg/m^3^"), which cost one question its
# passage in 3 runs of 3 on the harder professional run of 2026-11-15.
_SUBSCRIPT = re.compile(r"[~^]")
_ESCAPE = re.compile(r"\\(?=[^\w\s])")
_LIST_MARK = re.compile(r"(?m)^\s*(?:[-\u2022]|\d{1,2}[.)])\s+")


def _unmarked(quote: str) -> str:
    """A quote without the marks a search model adds and a page does not print."""
    quote = _ESCAPE.sub("", _SUBSCRIPT.sub("", _EMPHASIS.sub("", quote)))
    return _LIST_MARK.sub("", _HEADING.sub("", quote))


def _parts(quote: str) -> list[str]:
    """The pieces of a quote that must each be on the page, in order.

    A grid of cells gives one piece per row. Prose is one piece, without
    the model's own emphasis and heading marks. Words left out are still
    not allowed: a quote with a row of dots in it is looked for with the
    dots (Ruling D56 (3)).
    """
    rows = _table_rows(quote)
    if rows is not None:
        return rows
    part = _passage(_unmarked(quote))
    return [part] if part else []


def _checked_chars(quote: str) -> int:
    """How many characters of this quote the check compares."""
    return sum(len(part) for part in _parts(quote))


def quote_found(quote: str, page: str) -> bool:
    """Ruling D56 (3): is this passage in this page's text?

    Free and deterministic. Nothing is left out: a passage with a word
    missing or changed is not found. Spacing, case, curly quotes, dashes and
    soft hyphens are read alike, because pages and models print those
    differently without changing a word. So are the emphasis stars and
    heading hashes a model adds when it quotes.

    A quote written as a grid of cells is read row by row (owner's ruling,
    2026-11-14): every row must be on the page, its cells side by side and
    the rows in the order quoted. A row left out between two quoted rows is
    allowed, because the model quoted the rows it used; a cell changed is
    not.
    """
    text = _normalise(page)
    if _table_rows(quote) is None:
        # As written first: a page may print a star of its own.
        whole = _passage(quote)
        if len(whole) >= MIN_QUOTE_CHARS and whole in text:
            return True
    if _checked_chars(quote) < MIN_QUOTE_CHARS:
        return False
    at = 0
    for part in _parts(quote):
        at = text.find(part, at)
        if at < 0:
            return False
        at += len(part)
    return True


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
    # Ruling D56: the questions this lookup asked, numbered from 1; the
    # passages handed on.
    asked: list[str] = field(default_factory=list)
    quotes: list[Quote] = field(default_factory=list)
    # Each document the search model named, in the order tried: its address,
    # the words it pointed at, whether the page was read, and whether those
    # words are on it (None when it gave none).
    documents: list[dict] = field(default_factory=list)
    # Owner's ruling of 2026-11-21 (option C, knowledge/absence.py): the words searched for each ask
    # (by ask number, as the request's asks are numbered) and, for each page read in full that has none
    # of an ask's words, a proof. Empty unless the run gave the lookup its asks.
    searched: dict[int, list[str]] = field(default_factory=dict)
    proofs: list[Proof] = field(default_factory=list)

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

    def render(self) -> str:
        lines = [f"Q: {self.question}", f"A: {self.answer}"]
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
        lines += render_proofs(self.proofs)
        return "\n".join(lines)


async def research_gaps(
    client,
    request: str,
    gaps: list[str],
    max_lookups: int = MAX_LOOKUPS,
    max_tokens: int | None = None,
    asks: list | None = None,
) -> list[Finding]:
    """Look up the gaps a briefing identified, check them, and keep what holds.

    `asks` are the run's anchored asks (numbered dicts); given them, the lookup also searches the full
    text of every page it read in full for the words each ask's answer would be printed with, and
    hands on a proof for each page that has none (knowledge/absence.py).

    Returns findings in gap order. Failure of a single lookup is not fatal: a workflow
    with three of four facts is better off than one that aborted, and the
    missing one stays visible as a gap. A page that cannot be fetched never
    fails a lookup; it leaves its answer unverified.
    """
    if client is None or not tier_model("search", settings.model_search) or not gaps:
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
        finding = await _ask_documents(client, request, asked, max_tokens, asks)
        if finding is None:
            continue
        findings.append(finding)
        _remember(finding)   # recalled findings skip this: already stored

    if findings:
        checked = sum(len(f.checked()) for f in findings)
        unchecked = sum(len(f.unchecked()) for f in findings)
        logger.info(
            "Researched %d gap(s) in %d lookup(s): %d answer(s) backed by a "
            "passage found in its page, %d unverified",
            len(questions), len(findings), checked, unchecked,
        )
    return findings


# The longest request that is also put to the first lookup as a question of
# its own. Measured on the 111 questions in the evaluation sets: median 257
# characters, longest 1,091. Past this a request is a brief, not a question,
# and the gaps scoping named stand alone.
WHOLE_QUESTION_MAX_CHARS = 1500


def lookup_questions(request: str, gaps: list[str]) -> list[str]:
    """What a run's first lookup asks: the request itself, then each gap.

    The owner's ruling of 2026-11-21 ("also scope the whole question if it's
    still frugal"). Scoping rewrites a request into the unknowns it has to
    settle, and a rewrite can lose the words that say which document is meant.
    Read from the ten X12 draws kept from 2026-11-20 and 21 (a question that
    asks for the international rules for moving radioactive material): the
    three draws that asked the whole question all read IAEA pages; of the seven
    that asked scoping's rewrite, which no longer said "international", three
    read only US federal rules and all three gave a wrong answer. The search
    model is given the request as well, but it answers the question it is asked
    ("what the work needs settled"), so the whole question goes there too.

    Frugal by construction: the lookup stays one request that reads at most
    MAX_DOCUMENTS pages, so the only addition is one more numbered line in it.
    No gaps means no lookup was wanted, and none is made for the request alone;
    the request already among the gaps is not asked twice.
    """
    asked = [g.strip() for g in gaps if g and g.strip()]
    whole = (request or "").strip()
    if not asked or not whole or whole in asked or len(whole) > WHOLE_QUESTION_MAX_CHARS:
        return asked
    return [whole, *asked]


def _bundle(asked: list[str]) -> str:
    """The question text of one lookup: one question, or several numbered."""
    if len(asked) == 1:
        return asked[0]
    return "\n".join(f"{i}. {q}" for i, q in enumerate(asked, 1))


def _excerpts(text: str, terms: set[str], size: int = DOCUMENT_EXCERPT_CHARS,
              count: int = DOCUMENT_EXCERPTS) -> list[str]:
    """The stretches of a page to hand on, each in the page's own words.

    `size` and `count` are the stretch length and how many; the defaults are
    what a lookup hands on, and the reader tier asks for longer ones.
    """
    if len(text) <= DOCUMENT_WHOLE_CHARS:
        return [text.strip()] if text.strip() else []
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    words = [set(_TERM.findall(line.casefold())) for line in lines]
    # A word on every line of the page tells one line from another by
    # nothing; a word on few lines tells much. The search model's pointer
    # words are among the terms, so a request that shares no word with the
    # passage still finds it.
    weight = {term: math.log(len(lines) / sum(term in w for w in words))
              for term in terms if any(term in w for w in words)}
    scores = [sum(weight.get(term, 0.0) for term in w) for w in words]
    windows = []
    for start in range(len(lines)):
        end, used = start, 0
        while end < len(lines) and used + len(lines[end]) <= size:
            used += len(lines[end]) + 1
            end += 1
        if end > start:
            windows.append((sum(scores[start:end]), start, end))
    chosen: list[tuple[int, int]] = []
    for score, start, end in sorted(windows, key=lambda w: (-w[0], w[1])):
        if score <= 0 or len(chosen) >= count:
            break
        if all(end <= a or start >= b for a, b in chosen):
            chosen.append((start, end))
    return ["\n".join(lines[a:b]) for a, b in sorted(chosen)]


def _holds_pointer(near: str, text: str) -> bool | None:
    """Are the words the search model pointed at on this page?

    None when it pointed at nothing long enough to look for. Read as the
    quote check reads a quote, so spacing, case and a model's own marks
    change nothing.
    """
    pointer = _passage(_unmarked(near))
    if len(pointer) < MIN_POINTER_CHARS:
        return None
    return pointer in _normalise(text)


async def _name_documents(client, request: str, question: str,
                          max_tokens: int | None,
                          ) -> tuple[object, dict[str, str]] | None:
    """Ask the search model where the answer is written: its reply, and each
    address with the words it pointed at."""
    try:
        response = await client.chat(
            function="search",
            system_prompt=("You find the primary sources a question is "
                           "answered in. You do not answer from memory."),
            user_message=DOCUMENTS_PROMPT.format(
                request=request, question=question, limit=MAX_DOCUMENTS)
            + _avoid_clause(),
            temperature=0.0,
            max_tokens=max_tokens or settings.search_max_tokens,
        )
    except BudgetExceeded:
        raise
    except Exception as exc:
        global _refused_lookups
        _refused_lookups += 1
        logger.warning("Document lookup failed for %r: %s", question[:60], exc)
        return None
    near: dict[str, str] = {}
    try:
        data = extract_json((response.content or "").strip())
        for item in (data.get("documents") or []) if isinstance(data, dict) else []:
            if isinstance(item, dict) and str(item.get("url") or "").startswith("http"):
                near.setdefault(str(item["url"]).strip(), str(item.get("near") or ""))
    except ValueError as exc:
        logger.warning("Document lookup reply is not the typed format (%s); "
                       "its citations are used", exc)
    for url in getattr(response, "citations", None) or []:
        near.setdefault(str(url), "")
    return response, near


READER_PROMPT = """Below is one stretch of a page, and a question. Copy out, word for \
word and without changing a character, up to {limit} passages of the stretch \
that answer the question or give a figure, a name, a date or a rule it \
turns on. Each passage must be a whole sentence, row of a table or clause \
taken exactly as it is printed. Do not summarise, correct, translate or add \
anything. If nothing in the stretch bears on the question, return an empty \
list.

Question:
{question}

Stretch:
{chunk}

Reply with JSON only: {{"passages": ["...", "..."]}}"""


async def _read_chunk(client, question: str, chunk: str) -> list[str]:
    """One call of the reader model: the passages it copied from one stretch.

    A failure is no passages, not a failed lookup: the stretches chosen by
    shared words are handed on whatever the reader does. A spend refusal is
    the run's, and goes up.
    """
    try:
        response = await client.chat(
            function="reader",
            system_prompt=("You copy passages out of a text, exactly as "
                           "printed. You never summarise or rewrite."),
            user_message=READER_PROMPT.format(
                limit=READER_PASSAGES, question=question, chunk=chunk),
            temperature=0.0,
            max_tokens=READER_MAX_TOKENS,
            # Measured live 2026-11-20 on the first beta call: the reader
            # model reasoned through all 1,200 tokens of its budget and sent
            # no reply (finish "length"). Copying needs no reasoning. Off, the
            # same call used 23 output tokens, not 118, at about a quarter of
            # the cost.
            reasoning={"enabled": False},
        )
        data = extract_json((response.content or "").strip())
    except BudgetExceeded:
        raise
    except Exception as exc:
        logger.warning("Reader call failed (%s): %s", type(exc).__name__, exc)
        return []
    items = data.get("passages") if isinstance(data, dict) else None
    return [s.strip() for s in items if isinstance(s, str) and s.strip()][
        :READER_PASSAGES] if isinstance(items, list) else []


async def _read_with_readers(client, question: str, pages: dict[str, str],
                             terms: set[str]) -> dict[str, dict]:
    """What the reader tier copied from each long page, by address.

    Every stretch goes to its own call, all at once. A passage counts only
    where quote_found finds it on the page: the reader's words are never
    handed on on its say-so. Returns, for each page it read, the passages
    that held and how many calls and passages it made.
    """
    jobs: list[tuple[str, str]] = []
    for url, text in pages.items():
        if len(text) <= DOCUMENT_WHOLE_CHARS:
            continue  # handed on whole already; nothing to pick
        for chunk in _excerpts(text, terms, READER_CHUNK_CHARS, READER_CHUNKS):
            jobs.append((url, chunk))
    gate = asyncio.Semaphore(READER_CONCURRENCY)

    async def one(chunk: str) -> list[str]:
        async with gate:
            return await _read_chunk(client, question, chunk)

    results = await asyncio.gather(*(one(c) for _, c in jobs),
                                   return_exceptions=True)
    for result in results:
        if isinstance(result, BudgetExceeded):
            raise result
    out: dict[str, dict] = {}
    for (url, _), result in zip(jobs, results):
        entry = out.setdefault(url, {"calls": 0, "passages": [], "dropped": 0})
        entry["calls"] += 1
        if isinstance(result, BaseException):
            continue
        for passage in result:
            if len(passage) >= MIN_QUOTE_CHARS and quote_found(passage, pages[url]):
                if _normalise(passage) not in {_normalise(p) for p in entry["passages"]}:
                    entry["passages"].append(passage)
            else:
                entry["dropped"] += 1
    return out


async def _read_documents(near: dict[str, str], terms: set[str],
                          client=None, question: str = "",
                          read: dict[str, Source] | None = None,
                          ) -> tuple[list[Quote], list[dict]]:
    """Fetch the documents named and take the stretches to hand on.

    With the reader tier set and a client given, the long pages are also read
    by the reader model, and what it copied (and the page holds) is handed on
    beside the stretches chosen by shared words. `read`, when given, is filled
    with every page read in full, by address, for the proof of absence.
    """
    urls = [u for u in near
            if not (settings.lookup_avoid_unreadable
                     and _site(u) in _unreadable_sites)][:MAX_DOCUMENTS]
    pages = await asyncio.gather(*(fetch_source(u) for u in urls))
    quotes: list[Quote] = []
    documents: list[dict] = []
    read_by_reader: dict[str, dict] = {}
    if client is not None and tier_model("reader", settings.model_reader):
        read_by_reader = await _read_with_readers(
            client, question,
            {u: pg.text for u, pg in zip(urls, pages) if pg.fetched}, terms)
    for url, page in zip(urls, pages):
        _note_fetch(url, page)
        if read is not None and page.fetched:
            read[url] = page
        documents.append({
            "url": url, "near": near[url], "read": bool(page.fetched),
            "reason": "" if page.fetched else page.reason,
            "holds_pointer": (_holds_pointer(near[url], page.text)
                              if page.fetched else None),
            # Always 1: a second request for documents was measured on 432
            # answers, fired in 13 of 144 lookups and gained nothing, and was
            # removed (2026-11-16). Kept so records read as the traces do.
            "request": 1,
            # Only when the reader tier read the page: calls made, passages
            # that held, passages dropped for not being on the page.
            **({"reader": {"calls": read_by_reader[url]["calls"],
                           "passages": len(read_by_reader[url]["passages"]),
                           "dropped": read_by_reader[url]["dropped"]}}
               if url in read_by_reader else {})})
        if not page.fetched:
            quotes.append(Quote(1, near[url] or url, url, status="unfetched",
                                reason=page.reason))
            continue
        chosen = _excerpts(page.text, terms)
        seen = {_normalise(c) for c in chosen}
        # What the reader copied and the page holds, beside the stretches
        # chosen by shared words; a passage already among them is not repeated.
        chosen += [p for p in read_by_reader.get(url, {}).get("passages", [])
                   if _normalise(p) not in seen]
        for text in chosen:
            quotes.append(Quote(
                1, text, url, fetched_at=page.fetched_at, sha256=page.sha256,
                status="found" if quote_found(text, page.text) else "not_found"))
    return quotes, documents


async def _ask_documents(client, request: str, asked: list[str],
                         max_tokens: int | None,
                         asks: list | None = None) -> Finding | None:
    """One lookup: the harness reads the documents itself.

    The search model names where the answer is written; the harness fetches
    those pages and the finding carries stretches of their own text as its
    quotes. No model's summary is handed on, so a quote is the page's words
    by construction, and each is still put through the same check.
    """
    question = _bundle(asked)
    named = await _name_documents(client, request, question, max_tokens)
    if named is None:
        return None
    response, near = named
    read: dict[str, Source] = {}
    quotes, documents = await _read_documents(
        near, _terms(request, question, near), client, question, read)
    if not documents:
        return None
    # Free before paid (hard rule 5): the words are asked for only when a page was read in full, and
    # the search of those pages is code.
    searched: dict[int, list[str]] = {}
    proofs: list[Proof] = []
    if asks and read:
        searched = await name_terms(client, request, asks)
        proofs = prove(searched, read)
    return Finding(
        question=question, citations=[d["url"] for d in documents],
        model=response.model, asked=[question], quotes=quotes,
        documents=documents, searched=searched, proofs=proofs,
        answer=("No summary was made. The passages below are the pages' own "
                "words, fetched by the harness; read the answer from them."))


def _terms(request: str, question: str, near: dict[str, str]) -> set[str]:
    return set(_TERM.findall(" ".join([request, question, *near.values()]).casefold()))


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


def _avoid_clause() -> str:
    if not settings.lookup_avoid_unreadable or not _unreadable_sites:
        return ""
    return DOCUMENTS_AVOID_PROMPT.format(sites=", ".join(sorted(_unreadable_sites)))


# The most of one quoted passage a source record carries.
SOURCE_RECORD_QUOTE_CHARS = 600


def source_records(findings: list[Finding]) -> list[dict]:
    """What each lookup read, as plain data for the run's record.

    One entry per finding: the question, whether it was recalled
    from the store, the provider's own citations, and every quote with what
    the check found. "found" means the words are on the page fetched, not
    that the answer follows from them.
    """
    return [{
        "question": f.question,
        "recalled": f.recalled,
        "unverified_questions": f.unchecked(),
        "citations": list(f.citations),
        # A finding recalled from the store has none.
        **({"documents": [dict(d) for d in f.documents]} if f.documents else {}),
        # What was searched for each ask, and each page that has none of it (option C).
        **({"searched": {str(n): list(w) for n, w in f.searched.items()}}
           if f.searched else {}),
        **({"proofs": [p.as_record() for p in f.proofs]} if f.proofs else {}),
        "quotes": [{
            "question": q.question,
            # The words of the question this quote was given for. A bundled
            # lookup asks several, and the finding's own `question` is only
            # the first: read against it, a quote for the second question
            # looks off the point (measured 2026-11-13, three quotes).
            "question_text": (f._asked()[q.question - 1]
                              if 1 <= q.question <= len(f._asked())
                              else f.question),
            "text": q.text[:SOURCE_RECORD_QUOTE_CHARS],
            # The passage past that limit, when it is longer. The lookup that
            # reads the documents hands on excerpts of up to 1,200 characters
            # and a short page whole, and a check of the answer's figures
            # against the text handed on needs all of it (measured
            # 2026-11-15: with 600 kept, the governing passage could be shown
            # in only 45 of 62 runs). `text` stays as it was, because the
            # quote_answers switch reads it and its marks are matched on it.
            **({"whole": q.text[:DOCUMENT_WHOLE_CHARS]}
               if len(q.text) > SOURCE_RECORD_QUOTE_CHARS else {}),
            "url": q.url,
            "status": q.status,
            "reason": q.reason,
            "fetched_at": q.fetched_at,
            "sha256": q.sha256,
        } for q in f.quotes],
    } for f in findings]


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
