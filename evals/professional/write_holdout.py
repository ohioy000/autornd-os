"""Write the second hold-out set with two models, and check it, without showing a key.

    python evals/professional/write_holdout.py WORKDIR STAGES --author MODEL --author-provider TAG \
        --worker MODEL --worker-provider TAG --budget DOLLARS [--groups 1,2] [--date 2026-11-21] \
        [--parallel 4] [--effort-author medium] [--effort-check low] [--again] [--dry-run]

Run it from the repo, where `.env` is. The harness's own client reads the key from there: this script
never reads it, prints it or writes it (tests/test_write_holdout.py checks the source never names it).
The two models are the owner's choice and come in on the command line, never from this file. The
author writes and repairs questions; the worker does the grunt work (copying passages out of pages,
checking). Each is pinned to the provider tag given, with no fallback, so one provider serves each,
and the tag is looked up before any call.

STAGES is a comma-separated list, run in this order; each saves its result in WORKDIR, so a run can
stop and be run again and only the missing work is done:

    balance   what the provider account holds                                     free
    plan      the author names documents for each group of 14 questions           paid
    open      the harness's own fetch reads each; short or unreadable ones go     free
    extract   the worker copies passages out of each page; code finds each word   paid
              for word in the page text with the harness's own quote check
    write     the author writes the 14 questions of a group from those passages   paid
              (the prompt is Prompt A of docs/holdout-2-prompts.md, as written)
    check     the worker checks each group twice (Prompt B, as written)           paid
    fix       the author repairs or replaces what code or a checker flagged, and  paid
              the worker checks those again; one round only (--again for another)
    assemble  the draft set, the review file and the cost                          free

Nine groups of 14 are Y1 to Y126, three times the 42 of the first hold-out: six that cover the first
set's ground twice over, and three engineering subjects the owner added on 2026-11-21, each described
in detail (groups 7 to 9) so that the plan names documents across the whole of its ground. A question
reaches the draft only if code finds every cited passage on the page it names, every figure in a key
answer is on the cited pages (unless the key marks it derived), and both checks say OK. Anything else
is held back and listed in review.md with the reason. The draft says "Draft, not approved": the
runner refuses it until the owner signs the keys (D44). Pages are read with a longer limit than the
harness's 60 s, so the set is not made only of pages the harness reads quickly.

Paid stages need the owner's word and a stated amount: --budget is the total for WORKDIR, counted from
calls.jsonl across every run, and no call starts that could pass it. --dry-run asks nothing and says
what each stage would ask and about what it would cost.
"""
from __future__ import annotations

import argparse
import asyncio
import difflib
import json
import logging
import math
import re
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from autornd.config import settings  # noqa: E402
from autornd.knowledge import fetch  # noqa: E402
from autornd.knowledge.research import _normalise, quote_found  # noqa: E402
from autornd.routing.openrouter import (  # noqa: E402
    BudgetExceeded, OpenRouterClient, check_models)

logger = logging.getLogger(__name__)

PROMPTS = ROOT / "docs" / "holdout-2-prompts.md"
EARLIER_SETS = [ROOT / "evals" / "professional" / name for name in (
    "questions.json", "hard-questions.json", "misleading-questions.json",
    "holdout-questions.json")] + [ROOT / "evals" / "tier2" / "questions.json"]

PER_GROUP = 14
AUTHOR_FN, WORKER_FN = "author", "worker"          # the names the provider pins are given under
VERDICTS = ("OK", "FIX", "DROP")

# A page with less text than this is a stub, a login wall or a redirect, not a document to ask about.
MIN_PAGE_CHARS = 3000
# The harness reads a page for 60 s; the authoring read waits longer so that a large standard is not
# left out for being slow (a set made only of quick pages would flatter the harness).
OPEN_TIMEOUT_SECONDS = 240.0
OPEN_PARALLEL = 4
OPEN_PAUSE_SECONDS = 0.5                 # between one page and the next, for the sites
# Documents named, and documents wanted kept, for a group (a question uses one or two of them).
ASK_FIRST, ASK_MORE, DOCS_WANTED = 30, 20, 16
# The worker reads a page in parts of this size, at most this many parts a page (the first 600,000
# characters), and returns at most this many passages from a part.
CHUNK_CHARS, MAX_CHUNKS, PASSAGES_PER_CHUNK = 200_000, 3, 8
PASSAGE_MIN_CHARS, PASSAGE_MAX_CHARS = 60, 600
# The author is shown at most this many passages from one document, and needs this many documents.
PASSAGES_SHOWN, MIN_PAGES_TO_WRITE = 12, 8
# What one checker call may carry of page text, in characters (about 600,000 tokens), so a call stays
# well inside the worker's context; a page past its share is cut and the checker is told so.
CHECK_PAGE_CHARS = 2_400_000
# Naming documents from memory is recall, not reasoning, so the plan call does not think. The first
# live run (2026-11-21) asked for the low level and the endpoint ignored it: all nine replies spent the
# whole 12,000 tokens on thought and returned nothing ('$0.1365' for nothing). One probe each at off,
# minimal and none, capped at 4,000 tokens, showed that only off answered (31 documents in 2,405
# tokens for '$0.0033'); the other two were cut off with an empty reply, as low had been.
PLAN_EFFORT = "off"
# Output ceilings: the author writes 14 questions and may reason first; the rest are short. A plan
# reply of 30 documents is about 2,500 tokens, and the first live run's longest ran past 12,000 (161
# documents), so the plan ceiling is 5,000: a reply that runs on is cut there and its finished
# entries are kept, which costs under '$0.01' where 12,000 cost '$0.015' for entries never used.
AUTHOR_MAX_TOKENS, PLAN_MAX_TOKENS, WORKER_MAX_TOKENS = 48_000, 5_000, 16_000
# The HTTP wait for one reply: a long answer from a reasoning model takes minutes, and the client's
# own 120 s was set for short ones.
REPLY_TIMEOUT_SECONDS = 900.0
# For --dry-run only: characters to a token, and the share of its limit a reply is guessed to use.
CHARS_PER_TOKEN, GUESSED_REPLY_SHARE = 3.5, 0.4
NEAR_DUPLICATE = 0.6
FIGURE = re.compile(r"\d[\d.,/]*\d|\d")


@dataclass(frozen=True)
class Group:
    number: int
    area: str
    first: int                      # the number of its first question: Y{first}

    @property
    def ids(self) -> list[str]:
        return [f"Y{self.first + i}" for i in range(PER_GROUP)]


# Groups 1 to 6 are the first set's three areas, each cut in two, so that 84 questions spread over the
# same ground. Groups 7 to 9 are three engineering subjects the owner added on 2026-11-21, and each is
# described in detail, not as a bare label such as "electrical systems": the plan call names documents
# from this text alone, and a long list of the topics and of the kinds of publisher is what makes it
# spread them over the whole subject instead of over its best-known corner.
GROUPS = [
    Group(1, "EU law and standards: products, energy, environment, transport, finance", 1),
    Group(2, "international law and standards: treaties and conventions and the public texts of "
             "the UN and its agencies (UNECE, ICAO, IMO, ITU, WHO), Codex, OECD and the "
             "standards bodies' free pages", 15),
    Group(3, "software, security and internet standards", 29),
    Group(4, "software and infrastructure documentation: language, database, network and "
             "cloud-service manuals and specifications", 43),
    Group(5, "physical engineering, units, datasheets and manuals", 57),
    Group(6, "national rules and codes: the United States, the United Kingdom, Canada, Australia, "
             "Japan, India and others", 71),
    Group(7, "electrical power systems and installations: conductor sizing and ampacity; overcurrent, "
             "earth-fault and arc-flash protection; earthing and bonding; clearances and working "
             "distances; grid and generator connection rules (voltage and frequency ride-through, "
             "harmonics, flicker, reactive power); transformer and motor efficiency limits and their "
             "test conditions; battery storage and charger installation; electromagnetic-compatibility "
             "emission limits. From the free texts of regulators, grid operators and agencies (OSHA, "
             "FERC and NERC, DOE, FCC, the UK Electricity Safety, Quality and Continuity Regulations "
             "and Grid Code, the Australian and Canadian regulators)", 85),
    Group(8, "mechanical, thermal and materials engineering: pressure vessels, boilers and piping "
             "(design, test and relief pressures, allowable stresses, inspection intervals); lifting "
             "equipment (rated loads, proof tests, sling, chain and hook criteria, inspection); "
             "fatigue and fracture; threaded fasteners and bolted joints (preload, torque); welding "
             "and weld-inspection acceptance criteria; heat exchangers; refrigeration and HVAC "
             "limits (refrigerant leak-repair thresholds, charge and efficiency requirements); "
             "material properties and test methods. From the free texts of safety regulators and "
             "agencies (OSHA, the UK HSE, EPA, DOE, NASA and US defence handbooks and standards, "
             "NIST)", 99),
    Group(9, "civil, structural and geotechnical engineering: highway and bridge design (design "
             "loads, clearances, geometric design values, pavement design); concrete, steel and "
             "timber design provisions; wind, snow and seismic design parameters; foundations, "
             "retaining walls and soil classification; drainage, hydrology and design storms; dams, "
             "levees and scour. From the free manuals and guides of transport agencies, geological "
             "surveys and emergency-management agencies (FHWA, state transport departments, USGS, "
             "FEMA, NRCS, National Highways standards, the EU Joint Research Centre's Eurocode "
             "background documents, Austroads and the New Zealand Transport Agency)", 113),
]


# ---------------------------------------------------------------------------------------------
# What the prompts say. They live in docs/holdout-2-prompts.md and are used as written there.

def load_prompts(text: str) -> tuple[str, str]:
    """Prompt A and Prompt B: the first fenced block after each heading."""
    found = []
    for heading in ("## Prompt A", "## Prompt B"):
        at = text.index(heading)
        block = re.search(r"```\n(.*?)\n```", text[at:], re.S)
        if block is None:
            raise ValueError(f"no fenced prompt under {heading}")
        found.append(block.group(1))
    return found[0], found[1]


def covered_areas(prompt_a: str) -> str:
    """The paragraph of areas the earlier sets cover, so there is one copy of the list."""
    block = re.search(r"AREAS ALREADY COVERED\.[^\n]*\n(.*?)\n\nFOR EACH QUESTION GIVE",
                      prompt_a, re.S)
    if block is None:
        raise ValueError("Prompt A no longer has its 'AREAS ALREADY COVERED' paragraph")
    return block.group(1).strip()


# Prompt A asks the author to open every page itself. Here code opened them, so the pages come in the
# message, and the three things that change are said first and plainly. Nothing in the prompt is cut.
AUTHOR_PREFACE = """\
IN THIS SESSION you cannot open pages. Code opened them for you: the message gives each page's
address and passages copied from it word for word, and that is all there is. Where the instructions
below say to open a page yourself, use these. Every passage you cite must be copied word for word
from the list. If the mix below cannot be met from these pages, write plain lookups instead and say
so in your note. Mark a key entry "derived": true when its answer is worked out from the passages
(a sum, a conversion, or an absence) and is not printed on the page.

"""

# Prompt A's opening sentence, which a repair call replaces: it asks for 14 questions and a repair is
# a few. The rest of the prompt, what a good question is above all, is the same.
WRITE_ASK = "Write 14 questions in this group: {GROUP}. Number them {FIRST} to {LAST}."
REPAIR_ASK = ("Repair or replace the questions the message names, in this group: {GROUP}. Keep "
              "their ids ({FIRST} to {LAST} are the group's).")


def author_system(prompt_a: str, group: Group, date: str, repair: bool = False) -> str:
    """Prompt A with its four blanks filled; the braces of its JSON shape are left alone."""
    if WRITE_ASK not in prompt_a:
        raise ValueError("Prompt A no longer opens with its 'Write 14 questions' sentence")
    template = prompt_a.replace(WRITE_ASK, REPAIR_ASK) if repair else prompt_a
    filled = (template.replace("{GROUP}", group.area).replace("{FIRST}", group.ids[0])
              .replace("{LAST}", group.ids[-1]).replace("{DATE}", date))
    return AUTHOR_PREFACE + filled


CHECK_TAIL = """\

IN THIS SESSION you do not open the pages: the full text of each cited page follows the file, under
its address, and is all there is. Where the instructions above say to open a page, read it there. If
a page is marked cut, say that you could not check what lies past the cut instead of guessing. A
question is OK only if you checked everything above and found nothing wrong.
DELIVER one JSON object and nothing else:
{"verdicts": [{"id": "Y1", "verdict": "OK", "problem": "", "fix": ""}]}
with one entry for every question in the file; verdict is OK, FIX or DROP; for a FIX or a DROP give
the problem in one sentence and the exact fix.
"""


def checker_system(prompt_b: str) -> str:
    if "THE FILE:" not in prompt_b:
        raise ValueError("Prompt B no longer ends with 'THE FILE:'")
    return prompt_b.split("THE FILE:")[0].rstrip() + "\n" + CHECK_TAIL


PLAN_SYSTEM = (
    "You help build a fair exam for a research tool that answers working engineers' questions from "
    "public documents. You cannot browse. You name public documents from memory, at addresses you "
    "are sure are real: a wrong address wastes a check, so name fewer rather than guess. Reply "
    "with one JSON object and nothing else.")

PLAN_USER = """\
Today is {DATE}. The area: {AREA}.

Name exactly {COUNT} different public documents in this area, and no more. Each one must be:
- free to read, with no login and no paywall, on the site of the body that publishes it, and the
  law, standard, specification, datasheet or manual itself, not a page that describes it;
- at an address you are confident is real and stable (for example an EUR-Lex CELEX address, an
  RFC-editor address, a legislation.gov.uk address, an eCFR address, a W3C TR address, or a maker's
  own datasheet PDF);
- full of checkable figures, dates, limits, conditions, definitions or scope clauses.
Spread them over many publishers and many topics inside the area.

Do not choose from these areas, which earlier sets already cover:
{COVERED}
{AVOID}
Reply: {"documents": [{"url": "https://...", "title": "name of the document", "why": "the kind of rule or figure a question could ask, in under 15 words"}]}
"""

EXTRACT_SYSTEM = (
    "You read one public document and copy out passages that could anchor an exam question. Reply "
    "with one JSON object and nothing else.")

EXTRACT_USER = """\
Document: {TITLE}
Address: {URL}
Part {PART} of {PARTS} of its text follows.

List up to {COUNT} passages from this text. Each passage:
- is copied word for word from the text, one to three sentences, 60 to 500 characters, with nothing
  added or left out;
- states a specific checkable figure, limit, date, condition, definition, scope or exclusion (prefer
  a figure with its unit);
- is not a table of contents, a heading, a notice, a navigation line or boilerplate.
Take them from different places in the text, not all from one section.
Reply: {"passages": [{"passage": "...", "kind": "figure | limit | date | rule | scope | definition", "topic": "four to eight words"}]}

TEXT:
{TEXT}
"""

WRITE_USER = """\
Today is {DATE}.
THE PAGES, each with passages copied from it word for word. Use only these pages and passages.

{MATERIALS}
Write the {COUNT} questions now: {FIRST} to {LAST}. Deliver one JSON object, then a short note.
"""

FIX_USER = """\
Today is {DATE}.
THE PAGES, each with passages copied from it word for word. Use only these pages and passages.

{MATERIALS}
QUESTIONS ALREADY ACCEPTED IN THIS GROUP (do not repeat their topics):
{ACCEPTED}

QUESTIONS TO REPAIR, each with what was found wrong:
{FLAGGED}

For each, deliver a corrected question with the same id if what was found can be fixed using only the
pages and passages above. If it cannot be fixed, deliver a NEW question with the same id on a
different passage. Deliver one JSON object {"questions": [...]} with each question in the shape
given above, then a short note.
"""


# ---------------------------------------------------------------------------------------------
# Reading what a model sent back, and checking a question. Pure functions: no call, no network.

def first_json(text: str) -> tuple[object, str]:
    """The first complete JSON object or array in a reply, and the text after it (a note, a fence).

    Tried at each opening brace in turn, because a reply may speak of braces before it holds any.
    """
    decoder = json.JSONDecoder()
    at = 0
    while True:
        starts = [i for i in (text.find("{", at), text.find("[", at)) if i >= 0]
        if not starts:
            raise ValueError("no JSON in the reply")
        at = min(starts)
        try:
            value, end = decoder.raw_decode(text, at)
        except json.JSONDecodeError:
            at += 1
            continue
        return value, text[end:].strip().strip("`").strip()


def plan_entries(reply: str) -> list:
    """The documents a plan reply names: its whole JSON when it is whole, and otherwise every entry
    that was finished before the cut. The first live run's replies named 91 and 161 documents when 30
    were asked for, and one stopped at its limit in the middle of an entry."""
    try:
        value, _ = first_json(reply)
    except ValueError:
        value = None
    documents = value.get("documents") if isinstance(value, dict) else value
    if isinstance(documents, list):
        return documents
    key = reply.find('"documents"')
    start = reply.find("[", key if key >= 0 else 0)
    if start < 0:
        return []
    decoder, at, found = json.JSONDecoder(), start + 1, []
    while True:
        while at < len(reply) and reply[at] in " \t\r\n,":
            at += 1
        if at >= len(reply) or reply[at] != "{":
            return found
        try:
            entry, at = decoder.raw_decode(reply, at)
        except ValueError:
            return found
        found.append(entry)


def clean_question(raw: object) -> dict | None:
    """The question in the first set's shape, or None if it is not a question at all."""
    if not isinstance(raw, dict):
        return None
    difficulty = raw.get("difficulty")
    if isinstance(difficulty, str):
        difficulty = [difficulty]
    sources = [{"url": str(s.get("url", "")).strip(), "passage": str(s.get("passage", "")).strip()}
               for s in raw.get("sources") or [] if isinstance(s, dict)]
    key = []
    for item in raw.get("key") or []:
        if isinstance(item, dict):
            entry = {"item": str(item.get("item", "")).strip(),
                     "answer": str(item.get("answer", "")).strip()}
            if item.get("derived") is True:
                entry["derived"] = True
            key.append(entry)
    return {"id": str(raw.get("id", "")).strip(), "field": str(raw.get("field", "")).strip(),
            "difficulty": [str(d) for d in difficulty or []],
            "question": str(raw.get("question", "")).strip(), "sources": sources, "key": key,
            "commonly_confused": str(raw.get("commonly_confused", "")).strip()}


def read_questions(reply: str, ids: list[str]) -> tuple[list[dict], str]:
    """The questions in a reply, cleaned, and its note. Ids the author wrote that are not among the
    group's are replaced in order: an id is only a label, and the prompt told it which to use."""
    value, note = first_json(reply)
    rows = value.get("questions") if isinstance(value, dict) else value
    cleaned = [q for q in map(clean_question, rows if isinstance(rows, list) else []) if q]
    if sorted(q["id"] for q in cleaned) != sorted(set(q["id"] for q in cleaned)) or any(
            q["id"] not in ids for q in cleaned):
        cleaned = [dict(q, id=qid) for qid, q in zip(ids, cleaned)]
    return sorted(cleaned, key=lambda q: ids.index(q["id"])), note


def find_url(url: str, known) -> str | None:
    """The page this address names among those that were opened, tolerating a trailing slash."""
    if url in known:
        return url
    wanted = url.rstrip("/")
    return next((u for u in known if u.rstrip("/") == wanted), None)


def problems(question: dict, texts: dict[str, str]) -> list[str]:
    """What code finds wrong with a question. Empty: it may go to the checkers.

    `texts` maps the address of each page that was opened to its full text. A passage is looked for
    with the harness's own quote check; a figure in a key answer must be on a cited page unless the
    key marks it derived (a sum, a conversion or an absence), as verify_keys.py does for the others.
    """
    found: list[str] = []
    for name in ("id", "field", "question", "commonly_confused"):
        if not question.get(name):
            found.append(f"no {name}")
    if not question.get("difficulty"):
        found.append("no difficulty tags")
    if not question.get("key"):
        found.append("no key")
    elif any(not item["item"] or not item["answer"] for item in question["key"]):
        found.append("a key entry has no item or no answer")
    if not question.get("sources"):
        found.append("no sources")
    cited = ""
    for source in question.get("sources", []):
        url = find_url(source["url"], texts)
        if url is None:
            found.append(f"source {source['url'][:80]} is not a page that was opened")
            continue
        if not quote_found(source["passage"], texts[url]):
            found.append(f"passage not on the page {url[:80]}: {source['passage'][:60]}")
        cited += " " + _normalise(texts[url]).replace(",", "")
    missing = [n for item in question.get("key", []) if not item.get("derived")
               for n in (m.replace(",", "") for m in FIGURE.findall(item["answer"]))
               if n.casefold() not in cited]
    if cited and missing:
        found.append(f"figures not on the cited pages: {sorted(set(missing))}")
    return found


def parse_verdicts(text: str, asked: list[str]) -> dict[str, dict]:
    """A checker's reply as {id: {verdict, problem, fix}}; an id it did not answer is MISSING."""
    value, _ = first_json(text)
    rows = value.get("verdicts") if isinstance(value, dict) else value
    out: dict[str, dict] = {}
    for row in rows if isinstance(rows, list) else []:
        if isinstance(row, dict) and str(row.get("id", "")).strip() in asked:
            verdict = str(row.get("verdict", "")).strip().upper()
            out[str(row["id"]).strip()] = {
                "verdict": verdict if verdict in VERDICTS else "UNREADABLE",
                "problem": str(row.get("problem", "")).strip(),
                "fix": str(row.get("fix", "")).strip()}
    for qid in asked:
        out.setdefault(qid, {"verdict": "MISSING", "problem": "the checker gave no verdict",
                             "fix": ""})
    return out


def urls_and_questions(*paths: Path) -> tuple[set[str], list[tuple[str, str]]]:
    """Every address and every (id, question text) in the earlier sets, whatever their shape."""
    urls: set[str] = set()
    questions: list[tuple[str, str]] = []

    def walk(node: object) -> None:
        if isinstance(node, dict):
            if isinstance(node.get("question"), str):
                questions.append((str(node.get("id", "")), node["question"]))
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for value in node:
                walk(value)
        elif isinstance(node, str) and node.startswith(("http://", "https://")):
            urls.add(node.rstrip("/"))

    for path in paths:
        if path.exists():
            walk(json.loads(path.read_text(encoding="utf-8")))
    return urls, questions


def duplicates(question: dict, urls: set[str], earlier: list[tuple[str, str]],
               ) -> tuple[list[str], list[str]]:
    """(near-duplicates, same pages): which earlier questions this one is nearly, and which earlier
    addresses it cites. The first holds a question back; the second is only said."""
    near = []
    for qid, text in earlier:
        ratio = difflib.SequenceMatcher(
            None, question["question"].casefold(), text.casefold()).ratio()
        if ratio >= NEAR_DUPLICATE:
            near.append(f"{qid or 'an earlier question'} ({ratio:.2f})")
    same = [s["url"] for s in question["sources"] if s["url"].rstrip("/") in urls]
    return near, same


# ---------------------------------------------------------------------------------------------
# The run: where things are saved, what was spent, and the one place a model is called.

class DryRun(Exception):
    """Raised by ask() when --dry-run is set, so no stage can make a call by accident."""


class ReplyCutOff(ValueError):
    """A reply ended at its token limit, so what it holds cannot be trusted whole."""


@dataclass
class Run:
    work: Path
    author: str
    author_provider: str
    worker: str
    worker_provider: str
    date: str
    budget: float | None
    parallel: int
    effort_author: str
    effort_check: str
    again: bool
    dry: bool
    groups: list[Group]
    prompt_a: str
    prompt_b: str
    client: object | None = None
    stopped: bool = False            # the budget ran out: the stage stops starting calls
    seq: int = 0                     # numbers the raw replies
    errors: list[str] = field(default_factory=list)
    prices: dict[str, tuple[float, float]] = field(default_factory=dict)
    guess: dict[str, list[float]] = field(default_factory=dict)    # --dry-run: stage -> sums

    def path(self, name: str) -> Path:
        return self.work / name

    def load(self, name: str, default: object) -> object:
        path = self.path(name)
        return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default

    def save(self, name: str, value: object) -> None:
        path = self.path(name)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value, indent=1, ensure_ascii=False), encoding="utf-8")

    def calls(self) -> list[dict]:
        path = self.path("calls.jsonl")
        if not path.exists():
            return []
        return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]

    def spent(self) -> float:
        return sum(call.get("cost") or 0.0 for call in self.calls())


def reasoning_for(effort: str) -> dict | None:
    """The provider's own option for how much to think: a level, or off."""
    if effort == "default":
        return None
    return {"enabled": False} if effort == "off" else {"effort": effort}


def _append(run: Run, record: dict) -> None:
    with run.path("calls.jsonl").open("a", encoding="utf-8") as log:
        log.write(json.dumps(record) + "\n")


async def ask(run: Run, stage: str, group: Group | None, function: str, system: str, user: str, *,
              max_tokens: int, temperature: float = 0.3, json_mode: bool = False,
              effort: str = "default", keep_cut: bool = False) -> str:
    """One model call. Its cost goes to calls.jsonl at once and its reply to raw/, whatever follows.

    A reply that stopped at its limit is refused, because what it holds cannot be trusted whole, unless
    the caller says it can use what came before the cut (the plan, which is a list)."""
    model = run.author if function == AUTHOR_FN else run.worker
    if run.dry:
        rate_in, rate_out = run.prices.get(model, (0.0, 0.0))
        tokens_in = (len(system) + len(user)) / CHARS_PER_TOKEN
        row = run.guess.setdefault(stage, [0, 0.0, 0.0, 0.0])
        row[0] += 1
        row[1] += tokens_in
        row[2] += tokens_in * rate_in + max_tokens * rate_out
        row[3] += tokens_in * rate_in + GUESSED_REPLY_SHARE * max_tokens * rate_out
        raise DryRun()
    if run.stopped:
        raise BudgetExceeded("the budget ran out earlier in this stage")
    started = time.time()
    record = {"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "stage": stage,
              "group": group.number if group else None, "function": function, "model": model}
    try:
        response = await run.client.chat(
            function=function, system_prompt=system, user_message=user,
            response_format={"type": "json_object"} if json_mode else None,
            temperature=temperature, max_tokens=max_tokens, model=model,
            reasoning=reasoning_for(effort))
    except Exception as exc:
        record.update(ok=False, error=type(exc).__name__, seconds=round(time.time() - started, 1))
        _append(run, record)
        if isinstance(exc, BudgetExceeded):
            run.stopped = True
        raise
    if not run.seq:
        run.seq = len(run.calls())
    run.seq += 1
    name = f"raw/{run.seq:04d}-{stage}-g{group.number if group else 0}.txt"
    run.path("raw").mkdir(parents=True, exist_ok=True)
    run.path(name).write_text(response.content or "", encoding="utf-8")
    record.update(ok=True, provider=response.provider, finish_reason=response.finish_reason,
                  prompt_tokens=response.prompt_tokens, completion_tokens=response.completion_tokens,
                  cost=response.cost, seconds=round(time.time() - started, 1), raw=name)
    _append(run, record)
    if response.finish_reason == "length" and not keep_cut:
        raise ReplyCutOff(f"the {stage} reply stopped at its limit of {max_tokens} tokens")
    return response.content or ""


async def guarded(run: Run, label: str, coro) -> bool:
    """Run one unit of a stage. A failure is recorded and the stage goes on; the budget ends it."""
    try:
        await coro
        return True
    except DryRun:
        return False
    except BudgetExceeded as exc:
        run.stopped = True
        run.errors.append(f"{label}: stopped by the budget ({exc})")
    except Exception as exc:    # one bad reply must not lose the rest of a paid stage
        run.errors.append(f"{label}: {type(exc).__name__}: {str(exc)[:200]}")
    return False


async def each(run: Run, jobs: list[tuple[str, object]]) -> int:
    """Run the jobs, `parallel` at a time; how many finished."""
    gate = asyncio.Semaphore(run.parallel)

    async def one(label: str, make) -> bool:
        async with gate:
            return await guarded(run, label, make())

    results = await asyncio.gather(*(one(label, make) for label, make in jobs))
    return sum(results)


async def http_of(run: Run) -> httpx.AsyncClient:
    """The client's own HTTP session, which carries the key in its headers: used, never read."""
    return await run.client._get_client()                   # noqa: SLF001


async def verify_pins(run: Run) -> None:
    """Stop before any call if a model is unknown or a provider tag is not one that serves it."""
    base = settings.openrouter_base_url.rstrip("/")
    async with httpx.AsyncClient(timeout=30.0) as http:
        for model, tag in ((run.author, run.author_provider), (run.worker, run.worker_provider)):
            reply = await http.get(f"{base}/models/{model}/endpoints")
            if reply.status_code != 200:
                raise SystemExit(f"the provider does not list a model named {model}")
            endpoints = reply.json().get("data", {}).get("endpoints", [])
            tags = {e.get("tag") for e in endpoints} | {e.get("provider_name") for e in endpoints}
            if tag not in tags:
                raise SystemExit(f"{model} is not served by {tag}; its providers are "
                                 f"{sorted(t for t in tags if t)}")


async def load_prices(run: Run) -> None:
    """The two models' rates from the public catalogue, for a dry run's estimate."""
    base = settings.openrouter_base_url.rstrip("/")
    async with httpx.AsyncClient(timeout=30.0) as http:
        catalogue = (await http.get(f"{base}/models")).json().get("data", [])
    for entry in catalogue:
        if entry["id"] in (run.author, run.worker):
            pricing = entry.get("pricing") or {}
            run.prices[entry["id"]] = (float(pricing.get("prompt") or 0),
                                       float(pricing.get("completion") or 0))


async def open_client(run: Run) -> None:
    """The harness's own client, with the two pins and the budget; the key is read by the harness."""
    await verify_pins(run)
    settings.openrouter_provider_order = (
        f"{AUTHOR_FN}:{run.author_provider},{WORKER_FN}:{run.worker_provider}")
    settings.openrouter_provider_fallbacks = ""          # a hard pin: no other provider serves a call
    await check_models()                                  # loads the prices the spend guard needs
    run.client = OpenRouterClient()
    if run.budget is not None:
        run.client.spend_ceiling = max(0.0, run.budget - run.spent())
    (await http_of(run)).timeout = httpx.Timeout(REPLY_TIMEOUT_SECONDS)


# ---------------------------------------------------------------------------------------------
# The stages.

def kept_pages(run: Run, group: Group) -> list[dict]:
    return [page for page in run.load(f"opened-g{group.number}.json", []) if page["ok"]]


def page_texts(run: Run, group: Group) -> dict[str, str]:
    return {page["url"]: run.path(page["file"]).read_text(encoding="utf-8")
            for page in kept_pages(run, group)}


async def stage_balance(run: Run) -> None:
    """What the account holds and what this key may still spend: numbers only, never the key."""
    http = await http_of(run)
    reply = await http.get("/credits")
    if reply.status_code == 200:
        data = reply.json().get("data", {})
        bought, used = data.get("total_credits"), data.get("total_usage")
        print(f"account: credits bought {bought}, used {used}, left {round((bought or 0) - (used or 0), 4)}")
    reply = await http.get("/key")
    data = reply.json().get("data", {}) if reply.status_code == 200 else {}
    print("this key: limit", data.get("limit"), "used", data.get("usage"),
          "left", data.get("limit_remaining"))
    print(f"spent so far in {run.work}: {round(run.spent(), 4)}")


async def stage_plan(run: Run) -> None:
    async def plan_group(group: Group) -> None:
        plan = run.load(f"plan-g{group.number}.json", {"asked": 0, "documents": []})
        opened = run.load(f"opened-g{group.number}.json", [])
        if sum(page["ok"] for page in opened) >= DOCS_WANTED:
            return
        named = [d["url"] for d in plan["documents"]]
        failed = [p["url"] for p in opened if not p["ok"]]
        avoid = ""
        if named:
            avoid = ("\nAlready named, so do not name them again: " + "; ".join(named) + "\n"
                     + ("These did not open, so name nothing like them: " + "; ".join(failed) + "\n"
                        if failed else ""))
        count = ASK_MORE if named else ASK_FIRST
        user = (PLAN_USER.replace("{DATE}", run.date).replace("{AREA}", group.area)
                .replace("{COUNT}", str(count))
                .replace("{COVERED}", covered_areas(run.prompt_a)).replace("{AVOID}", avoid))
        reply = await ask(run, "plan", group, AUTHOR_FN, PLAN_SYSTEM, user, max_tokens=PLAN_MAX_TOKENS,
                          json_mode=True, effort=PLAN_EFFORT, keep_cut=True)
        have, added = set(named), 0
        for doc in plan_entries(reply):
            if added >= count:             # ask for 30, take 30: every page taken is paid for again
                break                      # when the worker copies passages out of it
            if not isinstance(doc, dict):
                continue
            url, title = str(doc.get("url", "")).strip(), str(doc.get("title", "")).strip()
            if url.startswith(("http://", "https://")) and title and url not in have:
                have.add(url)
                added += 1
                plan["documents"].append({"url": url, "title": title,
                                          "why": str(doc.get("why", "")).strip(),
                                          "round": plan["asked"] + 1})
        plan["asked"] += 1
        run.save(f"plan-g{group.number}.json", plan)

    done = await each(run, [(f"plan g{g.number}", (lambda g=g: plan_group(g))) for g in run.groups])
    print(f"plan: {done} of {len(run.groups)} groups asked")


async def stage_open(run: Run) -> None:
    fetch.FETCH_TIMEOUT_SECONDS = OPEN_TIMEOUT_SECONDS
    used_urls, _ = urls_and_questions(*EARLIER_SETS)
    gate = asyncio.Semaphore(OPEN_PARALLEL)

    async def open_one(group: Group, doc: dict, index: int) -> dict:
        entry = {"url": doc["url"], "title": doc["title"], "ok": False}
        if doc["url"].rstrip("/") in used_urls:
            return dict(entry, reason="a page an earlier set asks about")
        async with gate:
            source = await fetch.fetch_source(doc["url"])
            await asyncio.sleep(OPEN_PAUSE_SECONDS)
        if not source.fetched:
            return dict(entry, reason=f"{source.status}: {source.reason}"[:160])
        if len(source.text.strip()) < MIN_PAGE_CHARS:
            return dict(entry, reason=f"only {len(source.text.strip())} characters of text")
        name = f"pages/g{group.number}/{index:03d}.txt"
        run.path(name).parent.mkdir(parents=True, exist_ok=True)
        run.path(name).write_text(source.text, encoding="utf-8")
        return dict(entry, ok=True, file=name, chars=len(source.text), sha256=source.sha256,
                    final_url=source.final_url, fetched_at=source.fetched_at)

    for group in run.groups:
        plan = run.load(f"plan-g{group.number}.json", {"documents": []})
        opened = run.load(f"opened-g{group.number}.json", [])
        done = {page["url"] for page in opened}
        todo = [(i, d) for i, d in enumerate(plan["documents"]) if d["url"] not in done]
        results = await asyncio.gather(*(open_one(group, d, i) for i, d in todo))
        seen = {page["sha256"] for page in opened if page["ok"]}
        for page in results:
            if page["ok"] and page["sha256"] in seen:      # the same bytes under another address
                run.path(page.pop("file")).unlink(missing_ok=True)
                page.update(ok=False, reason="the same document as one already opened")
            elif page["ok"]:
                seen.add(page["sha256"])
        opened += results
        run.save(f"opened-g{group.number}.json", opened)
        print(f"open g{group.number}: {sum(p['ok'] for p in opened)} read of {len(opened)} named")


async def stage_extract(run: Run) -> None:
    async def extract_page(group: Group, page: dict) -> None:
        text = run.path(page["file"]).read_text(encoding="utf-8")
        parts = min(MAX_CHUNKS, max(1, math.ceil(len(text) / CHUNK_CHARS)))
        found, seen = [], set()
        for part in range(parts):
            chunk = text[part * CHUNK_CHARS:(part + 1) * CHUNK_CHARS]
            user = (EXTRACT_USER.replace("{TITLE}", page["title"]).replace("{URL}", page["url"])
                    .replace("{PART}", str(part + 1)).replace("{PARTS}", str(parts))
                    .replace("{COUNT}", str(PASSAGES_PER_CHUNK)).replace("{TEXT}", chunk))
            reply = await ask(run, "extract", group, WORKER_FN, EXTRACT_SYSTEM, user,
                              max_tokens=WORKER_MAX_TOKENS, json_mode=True, effort="off")
            value, _ = first_json(reply)
            for row in (value.get("passages") if isinstance(value, dict) else None) or []:
                passage = str(row.get("passage", "")).strip() if isinstance(row, dict) else ""
                if (PASSAGE_MIN_CHARS <= len(passage) <= PASSAGE_MAX_CHARS and passage not in seen
                        and quote_found(passage, text)):
                    seen.add(passage)
                    found.append({"passage": passage, "kind": str(row.get("kind", "")).strip(),
                                  "topic": str(row.get("topic", "")).strip()})
        passages = run.load(f"passages-g{group.number}.json", {})
        passages[page["url"]] = found
        run.save(f"passages-g{group.number}.json", passages)

    jobs = []
    for group in run.groups:
        have = run.load(f"passages-g{group.number}.json", {})
        jobs += [(f"extract g{group.number} {page['url'][:60]}",
                  (lambda g=group, p=page: extract_page(g, p)))
                 for page in kept_pages(run, group) if page["url"] not in have]
    done = await each(run, jobs)
    print(f"extract: {done} of {len(jobs)} pages read")


def materials(run: Run, group: Group) -> tuple[str, list[dict]]:
    """The pages the author may use, with their passages, as text; and the pages in that order."""
    passages = run.load(f"passages-g{group.number}.json", {})
    pages = [page for page in kept_pages(run, group) if len(passages.get(page["url"], [])) >= 3]
    lines = []
    for number, page in enumerate(pages, 1):
        lines.append(f"[{number}] {page['title']}\n    address: {page['url']}")
        for index, row in enumerate(passages[page["url"]][:PASSAGES_SHOWN], 1):
            lines.append(f"    ({number}.{index}) [{row['kind']}] {row['passage']}")
        lines.append("")
    return "\n".join(lines), pages


def effective(run: Run, group: Group) -> dict[str, dict]:
    """The question each id now has: the author's first version, or its repair if there is one."""
    out: dict[str, dict] = {}
    for name in (f"draft-g{group.number}.json", f"fixed-g{group.number}.json"):
        for question in run.load(name, {"questions": []})["questions"]:
            out[question["id"]] = question
    return out


async def stage_write(run: Run) -> None:
    async def write_group(group: Group) -> None:
        text, pages = materials(run, group)
        if len(pages) < MIN_PAGES_TO_WRITE:
            raise ValueError(f"only {len(pages)} pages have passages; plan, open and extract more")
        user = (WRITE_USER.replace("{DATE}", run.date).replace("{MATERIALS}", text)
                .replace("{COUNT}", str(PER_GROUP)).replace("{FIRST}", group.ids[0])
                .replace("{LAST}", group.ids[-1]))
        reply = await ask(run, "write", group, AUTHOR_FN, author_system(run.prompt_a, group, run.date),
                          user, max_tokens=AUTHOR_MAX_TOKENS, temperature=0.5, effort=run.effort_author)
        questions, note = read_questions(reply, group.ids)
        run.save(f"draft-g{group.number}.json", {"questions": questions, "note": note})
        for stale in run.work.glob(f"*-g{group.number}-?.json"):    # checks of an older draft
            stale.unlink()
        run.path(f"fixed-g{group.number}.json").unlink(missing_ok=True)

    jobs = [(f"write g{g.number}", (lambda g=g: write_group(g))) for g in run.groups
            if not run.path(f"draft-g{g.number}.json").exists()]
    done = await each(run, jobs)
    print(f"write: {done} of {len(jobs)} groups written")


def check_user(questions: list[dict], texts: dict[str, str], reverse: bool) -> str:
    """The file and the pages it cites, in full; a page past its share is cut and marked."""
    ordered = list(reversed(questions)) if reverse else questions
    urls: list[str] = []
    for question in ordered:
        for source in question["sources"]:
            url = find_url(source["url"], texts)
            if url and url not in urls:
                urls.append(url)
    share = CHECK_PAGE_CHARS // max(1, len(urls))
    pages = []
    for url in urls:
        cut = len(texts[url]) > share
        pages.append(f"=== {url} ===\n{texts[url][:share]}"
                     + ("\n[the page is cut here: it goes on]" if cut else ""))
    return ("THE FILE:\n" + json.dumps({"questions": ordered}, ensure_ascii=False, indent=1)
            + "\n\nTHE PAGES:\n\n" + "\n\n".join(pages))


async def check_group(run: Run, group: Group, name: str, questions: list[dict]) -> None:
    """Two readings of these questions by the worker, saved as {name}-g{N}-{1,2}.json.

    The same model reads twice, so the second reading takes the questions in the other order and a
    higher temperature: a miss that is chance is less likely to repeat."""
    texts = page_texts(run, group)
    ids = [q["id"] for q in questions]
    for k in (1, 2):
        if run.path(f"{name}-g{group.number}-{k}.json").exists() and not run.again:
            continue
        reply = await ask(run, name, group, WORKER_FN, checker_system(run.prompt_b),
                          check_user(questions, texts, reverse=(k == 2)),
                          max_tokens=WORKER_MAX_TOKENS, temperature=0.2 + 0.4 * (k - 1),
                          effort=run.effort_check)
        run.save(f"{name}-g{group.number}-{k}.json", parse_verdicts(reply, ids))


async def stage_check(run: Run) -> None:
    async def job(group: Group) -> None:
        texts = page_texts(run, group)
        valid = [q for q in effective(run, group).values() if not problems(q, texts)]
        if valid:
            await check_group(run, group, "check", valid)

    done = await each(run, [(f"check g{g.number}", (lambda g=g: job(g))) for g in run.groups])
    print(f"check: {done} of {len(run.groups)} groups done (a group with nothing valid to read is done)")


def verdicts_for(run: Run, group: Group, qid: str) -> list[dict]:
    """The latest two verdicts on a question: the re-check's if there was one, else the first."""
    for name in ("recheck", "check"):
        rows = [run.load(f"{name}-g{group.number}-{k}.json", {}).get(qid) for k in (1, 2)]
        if all(rows):
            return rows
    return []


@dataclass
class Flag:
    """Why an id is not yet an accepted question."""
    written: bool = True                          # False: no question was written for the id
    code: list[str] = field(default_factory=list)  # what the code check found
    rows: list[dict] = field(default_factory=list)  # the two checkers' verdicts, if any
    unchecked: bool = False                       # valid, but no checker has read it

    def notes(self) -> list[str]:
        if not self.written:
            return ["no question was written for this id"]
        out = [f"code: {p}" for p in self.code]
        if self.unchecked:
            out.append("the checkers have not read it")
        out += [f"checker {k}: {row['verdict']}: {row['problem']} Fix: {row['fix']}"
                for k, row in enumerate(self.rows, 1) if row["verdict"] != "OK"]
        return out


def flags(run: Run, group: Group) -> dict[str, Flag]:
    """Every id of the group that is not yet an accepted question."""
    texts, have = page_texts(run, group), effective(run, group)
    found: dict[str, Flag] = {}
    for qid in group.ids:
        question = have.get(qid)
        if question is None:
            found[qid] = Flag(written=False)
            continue
        flag = Flag(code=problems(question, texts), rows=verdicts_for(run, group, qid))
        flag.unchecked = not flag.code and not flag.rows
        if flag.code or flag.unchecked or any(row["verdict"] != "OK" for row in flag.rows):
            found[qid] = flag
    return found


async def stage_fix(run: Run) -> None:
    async def job(group: Group) -> None:
        if run.path(f"fixed-g{group.number}.json").exists() and not run.again:
            return
        if not run.path(f"draft-g{group.number}.json").exists():
            raise ValueError("there is no draft to repair: run the write stage first")
        flagged = flags(run, group)
        if not flagged:
            return
        if any(flag.unchecked for flag in flagged.values()):
            raise ValueError("some questions have not been checked: run the check stage first")
        have, texts = effective(run, group), page_texts(run, group)
        text, _ = materials(run, group)
        accepted_text = "\n".join(f"{qid}: {q['question']}" for qid, q in have.items()
                                  if qid not in flagged)
        broken = "\n".join(f"{qid}: {json.dumps(have.get(qid), ensure_ascii=False)}\n  found: "
                           + " | ".join(flag.notes()) for qid, flag in flagged.items())
        user = (FIX_USER.replace("{DATE}", run.date).replace("{MATERIALS}", text)
                .replace("{ACCEPTED}", accepted_text or "(none)").replace("{FLAGGED}", broken))
        reply = await ask(run, "fix", group, AUTHOR_FN,
                          author_system(run.prompt_a, group, run.date, repair=True), user,
                          max_tokens=AUTHOR_MAX_TOKENS, temperature=0.5, effort=run.effort_author)
        questions, note = read_questions(reply, list(flagged))    # it was told to keep these ids
        run.save(f"fixed-g{group.number}.json", {"questions": questions, "note": note})
        fresh = [q for q in questions if not problems(q, texts)]
        if fresh:
            await check_group(run, group, "recheck", fresh)

    done = await each(run, [(f"fix g{g.number}", (lambda g=g: job(g))) for g in run.groups])
    print(f"fix: {done} of {len(run.groups)} groups repaired and read again")


def accepted(run: Run, group: Group, urls: set[str], earlier: list[tuple[str, str]],
             ) -> tuple[list[dict], dict[str, list[str]]]:
    """The questions that may go in the draft, and why each other id is held back."""
    held = {qid: flag.notes() for qid, flag in flags(run, group).items()}
    have = effective(run, group)
    good = []
    for qid in group.ids:
        if qid in held:
            continue
        near, _ = duplicates(have[qid], urls, earlier)
        if near:
            held[qid] = ["near-duplicate of " + ", ".join(near)]
        else:
            good.append(have[qid])
    return good, held


def cost_lines(run: Run) -> list[str]:
    by: dict[tuple[str, str], list[float]] = {}
    for call in run.calls():
        row = by.setdefault((call["stage"], call["model"]), [0, 0.0, 0])
        row[0] += 1
        row[1] += call.get("cost") or 0.0
        row[2] += 0 if call.get("ok") else 1
    lines = [f"| {stage} | {model} | {n} | {failed} | {cost:.4f} |"
             for (stage, model), (n, cost, failed) in sorted(by.items())]
    return lines + [f"| total | | {sum(r[0] for r in by.values())} | {sum(r[2] for r in by.values())} "
                    f"| {run.spent():.4f} |"]


async def stage_assemble(run: Run) -> None:
    urls, earlier = urls_and_questions(*EARLIER_SETS)
    final, report = [], []
    for group in run.groups:
        good, held = accepted(run, group, urls, earlier)
        final += good
        opened = run.load(f"opened-g{group.number}.json", [])
        report.append(f"## Group {group.number}: {group.area}\n\n"
                      f"{len(good)} accepted of {PER_GROUP}. Documents named {len(opened)}, read "
                      f"{sum(p['ok'] for p in opened)}.\n")
        for question in good:
            rows = verdicts_for(run, group, question["id"])
            _, same = duplicates(question, urls, earlier)
            said = " ".join(row["problem"] for row in rows if row["problem"])
            report.append(f"- **{question['id']}** accepted ({question['field']}; "
                          f"{', '.join(question['difficulty'])}); both checkers OK"
                          + (f"; cites a page an earlier set cites: {same[0][:80]}" if same else "")
                          + (f". Checkers said: {said}" if said else "."))
        for qid, notes in held.items():
            report.append(f"- **{qid}** HELD BACK: " + " | ".join(notes))
        report.append("")
    draft = {
        "version": "professional-holdout-2", "status": "Draft, not approved",
        "drafted": run.date, "passages_verified_against_live_pages": run.date,
        "purpose": "A hold-out set: questions written after the harness was tuned, by authors who "
                   "never saw its answers, across fields the other sets do not cover.",
        "questions": final}
    run.save("holdout2-questions.json", draft)
    review = (f"# Review of the draft set, {run.date}\n\n{len(final)} questions accepted of "
              f"{PER_GROUP * len(run.groups)}. Every cited passage was found on its page by the "
              f"harness's own quote check, every non-derived figure is on a cited page, and both "
              f"checkers said OK. The keys are not signed.\n\n"
              + "\n".join(report) + "\n## Cost\n\n| stage | model | calls | failed | dollars |\n"
              "|---|---|---|---|---|\n" + "\n".join(cost_lines(run)) + "\n")
    run.path("review.md").write_text(review, encoding="utf-8")
    print(f"assemble: {len(final)} questions in holdout2-questions.json; see review.md")


STAGES = {"balance": stage_balance, "plan": stage_plan, "open": stage_open,
          "extract": stage_extract, "write": stage_write, "check": stage_check,
          "fix": stage_fix, "assemble": stage_assemble}
ORDER = list(STAGES)
FREE = {"open", "assemble"}               # no model call; balance asks the account, which costs nothing


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("work", type=Path)
    parser.add_argument("stages", help="comma-separated, from: " + ", ".join(ORDER))
    parser.add_argument("--author", required=True)
    parser.add_argument("--author-provider", required=True)
    parser.add_argument("--worker", required=True)
    parser.add_argument("--worker-provider", required=True)
    parser.add_argument("--budget", type=float, help="dollars for the whole WORKDIR, all runs")
    # Every group, so that a group added to GROUPS is run without anyone having to say so.
    parser.add_argument("--groups", default=",".join(str(g.number) for g in GROUPS))
    parser.add_argument("--date", default=time.strftime("%Y-%m-%d"))
    parser.add_argument("--parallel", type=int, default=4)
    parser.add_argument("--effort-author", default="medium",
                        choices=("off", "low", "medium", "high", "default"))
    parser.add_argument("--effort-check", default="low",
                        choices=("off", "low", "medium", "high", "default"))
    parser.add_argument("--again", action="store_true", help="redo a fix or check already saved")
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args(argv)


def print_guess(run: Run, stage: str) -> None:
    calls, tokens, worst, likely = run.guess.pop(stage, [0, 0.0, 0.0, 0.0])
    print(f"would ask {int(calls)} calls, about {int(tokens):,} tokens in; at most ${worst:.4f} "
          f"(every reply at its limit), about ${likely:.4f} if replies use "
          f"{int(GUESSED_REPLY_SHARE * 100)}% of the limit (a guess)")


async def main(argv: list[str]) -> int:
    args = parse_args(argv)
    stages = [s.strip() for s in args.stages.split(",") if s.strip()]
    unknown = [s for s in stages if s not in STAGES]
    if unknown:
        raise SystemExit(f"unknown stage {unknown}; stages are {ORDER}")
    stages.sort(key=ORDER.index)
    paid = [s for s in stages if s not in FREE and s != "balance"]
    if paid and args.budget is None and not args.dry_run:
        raise SystemExit("a paid stage needs --budget: the owner's amount, stated before the spend")
    wanted = {int(n) for n in args.groups.split(",")}
    prompt_a, prompt_b = load_prompts(PROMPTS.read_text(encoding="utf-8"))
    args.work.mkdir(parents=True, exist_ok=True)
    run = Run(work=args.work.resolve(), author=args.author, author_provider=args.author_provider,
              worker=args.worker, worker_provider=args.worker_provider, date=args.date,
              budget=args.budget, parallel=args.parallel, effort_author=args.effort_author,
              effort_check=args.effort_check, again=args.again, dry=args.dry_run,
              groups=[g for g in GROUPS if g.number in wanted], prompt_a=prompt_a, prompt_b=prompt_b)
    if run.dry:
        await load_prices(run)
    elif set(stages) - FREE:
        await open_client(run)
    try:
        for stage in stages:
            print(f"--- {stage}" + (" (dry run: nothing is asked)" if run.dry else ""))
            if run.dry and stage == "balance":
                continue
            await STAGES[stage](run)
            if run.dry and stage not in FREE:
                print_guess(run, stage)
            if run.errors:
                print(f"{len(run.errors)} problem(s):")
                for line in run.errors:
                    print("  ", line)
                run.errors.clear()
    finally:
        if run.client is not None:
            await run.client.close()
    print(f"spent so far in {run.work}: {round(run.spent(), 4)}"
          + (f" of {args.budget}" if args.budget is not None else ""))
    return 0


if __name__ == "__main__":
    logging.basicConfig(level=logging.WARNING)
    sys.exit(asyncio.run(main(sys.argv[1:])))
