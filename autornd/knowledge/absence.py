"""Proofs of absence: words that are not in the full text of a document read in full.

The owner's ruling of 2026-11-21, option C of the "none stated" question. A run that cannot answer an
ask must name it in blocked_on, and any blocked ask ends the run with no answer. That is right when the
pages read did not hold the answer by chance, and wrong when the document states none: on the ATmega328P
datasheet, whose key says "a search of its full text for 'junction', 'thermal resistance', 'dissipation'
and degC/W finds none", the hold-out run blocked twice and gave an invented figure once (X41, three
draws), because a model cannot tell "I did not find it" from "it is not there". Allowing "none stated"
on the model's word would turn every thin lookup into a confident wrong answer, so only a proof allows it,
and the proof is made here, by code, not by a model.

The proof is a search. A model names, for each ask, the words a document prints where it states the
answer (a typed list, `name_terms`); the harness looks for every one of them in the text of each page the
lookup read in FULL (a `Source` is `fetched` only when every page of a PDF was read, or the whole page of
anything else, so a page that timed out or was refused proves nothing) and, for each page where none of
them is, hands on a line saying so (`Proof`). The answer step may then say "none stated" for that ask,
naming that page, and only then: the check in `graph/checks.py` ends the run blocked on a claim with no
proof, as a block ends it today.

What a proof does not say: it is a fact about one page, as fetched, and not about a document the lookup
did not read or about every document. Whether the page is the one the ask is about is the answer step's
judgement, which is why the line names the page, its size and its hash. And it is only as wide as the
words: a document that names the thing in words the model did not list passes as "absent". So all the words
must be absent (any one present is a veto), at least `MIN_TERMS` of them are needed, they are printed in
the line, and the search ignores what a page's layout does to a word (case, spaces, hyphens, a line break
in the middle of "resis-tance", ligatures).
"""
from __future__ import annotations

import logging
import unicodedata
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, Field, field_validator

from autornd.routing.openrouter import BudgetExceeded

logger = logging.getLogger(__name__)

# The fewest words a proof is made from. A document that states the answer prints at least one of the
# words a model lists, but one word is one guess at what the document calls it. Not measured: the key of
# X41, the case that set this ruling, searched four ('junction', 'thermal resistance', 'dissipation',
# degC/W), and three is the least that is not a single guess.
MIN_TERMS = 3
# Words past this are not kept, and a word longer than MAX_TERM_CHARS is a sentence, not a word. More
# words only make a proof harder to form, so the caps bound the line a reader has to read, not the safety.
MAX_TERMS = 16
MAX_TERM_CHARS = 60
# A word of at least this many letters and digits is looked for with every space, hyphen, break and mark
# inside it ignored ("thermal resistance" is found in "Thermal Resis-\ntance" and in "thermal-resistance").
# A shorter one (a symbol, a unit: "K/W", "°C/W") is looked for as written with only whitespace ignored,
# because with the marks dropped it would be a pair of letters found inside any text. A short word is
# found inside longer words, which only makes a proof harder to form, never easier.
SQUASH_FROM = 6

# The asks that can be answered "the document states none": a figure, a name or a verdict. A step, a
# constraint or a format is something to do, not something a document states. The fallback ask (the whole
# request, when nothing anchored) has no kind and is every kind at once.
PROVABLE_KINDS = ("value", "verdict", "")

TERMS_MAX_TOKENS = 2000

TERMS_PROMPT = """\
Below is a request and its asks, numbered. For each ask that wants a figure, a name, a date or a rule, \
give the words a document prints where it states the answer: the name of the thing asked for and its \
other names, its usual symbols and abbreviations, and its unit. A document that states the answer \
prints at least one of them. Give 3 to 8 for each ask, copied the way a document prints them, and \
prefer a name to a common word. For an ask that no document would state (a step to take, a form to \
follow), give an empty list.

Reply with JSON only: {{"terms": [{{"ask": 1, "any_of": ["...", "..."]}}]}}

Request:
{request}

Asks:
{asks}"""


# The words a page prints and a model writes differently without changing the word: the degree sign is
# printed as a masculine ordinal or a ring above, and NFKC would turn the ordinal into the letter o.
_DEGREE = str.maketrans({"\u00ba": "°", "\u02da": "°", "\u1d52": "°"})
# After NFKC (the non-breaking hyphen is already the hyphen then): every dash is the hyphen, and
# the characters that take no room in a word are gone. A short word keeps its punctuation, so
# both matter.
_SAME_CHARACTER = str.maketrans({
    "\u2010": "-", "\u2012": "-", "\u2013": "-", "\u2014": "-", "\u2212": "-",
    "\u00ad": None, "\u200b": None, "\u200c": None, "\u200d": None, "\u2060": None, "\ufeff": None,
})


def _fold(text: str) -> str:
    """One form for each character, and no case. Greek theta in all its forms becomes one letter."""
    return unicodedata.normalize("NFKC", text.translate(_DEGREE)).translate(_SAME_CHARACTER).casefold()


def _letters(text: str) -> str:
    """Only the letters and digits, folded."""
    return "".join(ch for ch in _fold(text) if ch.isalnum())


def _flat(text: str) -> str:
    """Folded, with no whitespace at all."""
    return "".join(_fold(text).split())


class Searchable:
    """One document's text, folded the two ways a word is looked for in it. Built once per page."""

    def __init__(self, text: str) -> None:
        folded = _fold(text)
        self.letters = "".join(ch for ch in folded if ch.isalnum())
        self.flat = "".join(folded.split())

    def has(self, term: str) -> bool:
        """Is this word in the text, under the rules at SQUASH_FROM?"""
        letters = _letters(term)
        if len(letters) >= SQUASH_FROM:
            return letters in self.letters
        flat = _flat(term)
        return bool(flat) and flat in self.flat


def clean_terms(raw: object) -> list[str]:
    """The words a model listed, kept as typed data: strings only, one space between words, no word of
    fewer than two letters or digits (it says nothing about what a document calls a thing), none longer
    than MAX_TERM_CHARS, none twice, at most MAX_TERMS."""
    if not isinstance(raw, list):
        return []
    kept: list[str] = []
    seen: set[str] = set()
    for item in raw:
        if not isinstance(item, str):
            continue
        term = " ".join(item.split())
        letters = _letters(term)
        if len(letters) < 2 or len(term) > MAX_TERM_CHARS:
            continue
        key = letters if len(letters) >= SQUASH_FROM else _flat(term)
        if key in seen:
            continue
        seen.add(key)
        kept.append(term)
    return kept[:MAX_TERMS]


class AskTerms(BaseModel):
    ask: int
    # Any type inside the list: a stray number among the words is dropped by `clean_terms`, not a
    # reason to ask the model again.
    any_of: list[Any] = Field(default_factory=list)

    @field_validator("any_of", mode="before")
    @classmethod
    def _a_null_list_is_none_listed(cls, value: Any) -> Any:
        return [] if value is None else value


class TermsVerdict(BaseModel):
    """The words a document prints, by ask. An ask left out, or given none, is one nothing is proven for."""

    terms: list[AskTerms] = Field(default_factory=list)

    @field_validator("terms", mode="before")
    @classmethod
    def _a_null_list_is_none_listed(cls, value: Any) -> Any:
        return [] if value is None else value


def _field(ask: Any, key: str) -> Any:
    return ask.get(key) if isinstance(ask, dict) else getattr(ask, key, None)


def provable_asks(asks: list[Any] | None) -> dict[int, str]:
    """The numbered asks a document can state an answer to, by number: their quotes."""
    found: dict[int, str] = {}
    for ask in asks or []:
        number = _field(ask, "number")
        quote = str(_field(ask, "quote") or "").strip()
        kind = _field(ask, "kind")
        kind = str(getattr(kind, "value", kind) or "").strip().lower()
        if isinstance(number, int) and not isinstance(number, bool) and quote \
                and kind in PROVABLE_KINDS:
            found[number] = quote
    return found


async def name_terms(client, request: str, asks: list[Any] | None) -> dict[int, list[str]]:
    """Ask a model, once, for the words a document prints where it states each ask's answer.

    The cheapest tier does it (a triage call cost about '$0.00015' in the hold-out run), after the pages
    are read and only when one was read in full, so a lookup that read nothing pays nothing. Any failure
    is no words, and so no proof: a failure here can only leave an ask blocked as it is today. A spend
    refusal is the run's, and goes up.
    """
    wanted = provable_asks(asks)
    if not wanted:
        return {}
    listing = "\n".join(f"{number}. {quote}" for number, quote in sorted(wanted.items()))
    try:
        data, _ = await client.chat_json(
            function="triage",
            system_prompt="You list the words a document uses for what a question asks. "
                          "Respond with JSON only.",
            user_message=TERMS_PROMPT.format(request=request, asks=listing),
            temperature=0.0,
            max_tokens=TERMS_MAX_TOKENS,
            schema=TermsVerdict,
            # Thinking off (owner's "do it" of 2026-11-23, probed the same day): the cheapest tier is a
            # reasoning model, and at the default it spent all 2000 tokens thinking and returned no text,
            # three tries in a row, on all three requests probed, so the words, and with them every proof,
            # were missing for 188 of the 199 eligible units of the second hold-out run (the swallowed
            # failure below is why nobody saw it). With thinking off the same three requests came back in
            # 48 to 76 tokens at about '$0.00002' each, the words being the ones the key of X41 lists.
            # Medium effort and a budget of 6000 both still returned nothing.
            reasoning={"enabled": False},
        )
        verdict = TermsVerdict(**data)
    except BudgetExceeded:
        raise
    except Exception as exc:
        logger.warning("The words for a proof of absence were not named (%s): %s",
                       type(exc).__name__, exc)
        return {}
    terms: dict[int, list[str]] = {}
    for entry in verdict.terms:
        if entry.ask in wanted and entry.ask not in terms:
            terms[entry.ask] = clean_terms(entry.any_of)
    return terms


@dataclass(frozen=True)
class Proof:
    """None of the words of one ask is anywhere in the full text of one page."""

    ask: int
    terms: tuple[str, ...]
    url: str
    chars: int
    pages: int           # 0 when the page has no page count (it is not a PDF read in processes)
    fetched_at: str
    sha256: str

    def render(self) -> str:
        words = ", ".join(f'"{t}"' for t in self.terms)
        size = (f"{self.pages:,} pages, " if self.pages else "") + f"{self.chars:,} characters"
        return (f"- Ask {self.ask}: none of {words} is anywhere in the full text of {self.url} "
                f"({size}; fetched {self.fetched_at}, sha256 {self.sha256[:12]}).")

    def as_record(self) -> dict[str, Any]:
        return {"ask": self.ask, "terms": list(self.terms), "url": self.url, "chars": self.chars,
                "pages": self.pages, "fetched_at": self.fetched_at, "sha256": self.sha256}


def prove(terms: dict[int, list[str]], read: dict[str, Any]) -> list[Proof]:
    """The proofs: for each ask with at least MIN_TERMS words, each page read in full that has none.

    `read` is the pages read in full, by address (a `Source` that was fetched); a page that was not read
    in full is not in it and so proves nothing. Free and deterministic: no model reads a page here.
    """
    proofs: list[Proof] = []
    texts = {url: Searchable(page.text) for url, page in read.items()}
    for ask in sorted(terms):
        words = terms[ask]
        if len(words) < MIN_TERMS:
            continue
        for url, page in read.items():
            if any(texts[url].has(word) for word in words):
                continue
            proofs.append(Proof(
                ask=ask, terms=tuple(words), url=url, chars=len(page.text),
                pages=int(getattr(page, "pages", 0) or 0), fetched_at=page.fetched_at,
                sha256=page.sha256))
    return proofs


def render_proofs(proofs: list[Proof]) -> list[str]:
    """The lines a lookup hands on for its proofs. No line, and no heading, when there are none."""
    if not proofs:
        return []
    return [
        "Proofs of absence, made by the harness (not a model) by searching the full text of pages it "
        "read in full; asks are numbered as in the request's list of asks. Each is about the page it "
        "names and no other:",
        *(proof.render() for proof in proofs)]
