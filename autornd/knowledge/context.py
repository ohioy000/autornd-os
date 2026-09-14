"""Context loader — builds relevant context for each workflow phase.

Combines two sources:
1. Deterministic docs from docs/manifest.json (always loaded for matching domains)
2. ChromaDB retrieval (semantic search for query-specific context)
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Optional

from autornd.config import settings
from autornd.models.verdicts import domain_key, role_key
from autornd.knowledge.store import retrieve
from autornd.models.verdicts import Domain, SpecialistRole

logger = logging.getLogger(__name__)

DOCS_DIR = Path(__file__).resolve().parent.parent.parent / "docs"
MAX_CONTEXT_CHARS = 32000


def _load_manifest() -> dict:
    from autornd.profiles import get_profile

    profile = get_profile()
    profile_manifest = DOCS_DIR / profile.get_docs_dir() / "manifest.json"
    if profile_manifest.exists():
        return json.loads(profile_manifest.read_text(encoding="utf-8"))

    fallback = DOCS_DIR / "manifest.json"
    if fallback.exists():
        return json.loads(fallback.read_text(encoding="utf-8"))

    return {"global": [], "domains": {}, "specialist_extras": {}}


def _read_doc(relative_path: str) -> str | None:
    full_path = DOCS_DIR / relative_path
    if not full_path.exists():
        logger.warning("Doc not found: %s", full_path)
        return None
    return full_path.read_text(encoding="utf-8", errors="replace")


def load_docs_context(
    domains: list[Domain],
    specialists: list[SpecialistRole] | None = None,
) -> str:
    """Load deterministic doc context based on triage domains and specialists."""
    manifest = _load_manifest()
    seen_paths: set[str] = set()
    sections: list[str] = []

    for path in manifest.get("global", []):
        if path not in seen_paths:
            content = _read_doc(path)
            if content:
                sections.append(f"--- {path} ---\n{content}")
                seen_paths.add(path)

    for domain in domains:
        domain_paths = manifest.get("domains", {}).get(domain_key(domain), [])
        for path in domain_paths:
            if path not in seen_paths:
                content = _read_doc(path)
                if content:
                    sections.append(f"--- {path} ---\n{content}")
                    seen_paths.add(path)

    if specialists:
        for spec in specialists:
            extra_paths = manifest.get("specialist_extras", {}).get(role_key(spec), [])
            for path in extra_paths:
                if path not in seen_paths:
                    content = _read_doc(path)
                    if content:
                        sections.append(f"--- {path} ---\n{content}")
                        seen_paths.add(path)

    combined = "\n\n".join(sections)
    if len(combined) > MAX_CONTEXT_CHARS:
        combined = combined[:MAX_CONTEXT_CHARS] + "\n\n[... context truncated ...]"
    return combined


# Embedding distance is a blunt relevance signal: it reliably surfaces chunks
# that are *about* the right subject and reliably fails to rank them against
# each other. Retrieving a wide candidate set and ranking it with a model
# recovers the precision, and costs one call per workflow.
RERANK_CANDIDATES = 20

RERANK_PROMPT = """\
Rank these documentation excerpts by how directly they help an engineer carry
out the request below. Judge usefulness for this specific task, not general
topical similarity: a excerpt that states a constraint, an interface, or a
value the work must respect outranks one that merely mentions the same subject.

Request:
{query}

Excerpts:
{excerpts}

Return JSON with:
- ranking: list of excerpt numbers, most useful first, length {keep}. Omit any
  excerpt that would not actually inform the work, even if that returns fewer
  than {keep} entries."""


def _rank_tier() -> str | None:
    """Which tier ranks retrieved context, if any.

    The ranker tier owns this job. If it is unset but a research model exists,
    that model ranks instead rather than losing the capability entirely.
    """
    if settings.model_ranker:
        return "ranker"
    if settings.model_research:
        return "research"
    return None


# Which ranking strategy works here. Probed at most once per strategy:
#   None        untried
#   "native"    the ranking model serves the rerank API
#   "listwise"  it does not, but it can rank in a chat prompt
#   "distance"  neither works — use the order retrieval already gave us
#
# Two states were not enough. A single transient failure of the native call
# latched "not supported", and every workflow after that fell through to a
# listwise chat call against a rerank-only model, which cannot answer it. One
# hiccup turned into a guaranteed wasted call on every workflow for the life of
# the process.
_rerank_mode: str | None = None


def reset_rerank_mode() -> None:
    """Forget what was probed. For tests, and for a deliberate re-probe."""
    global _rerank_mode
    _rerank_mode = None

RERANK_CANDIDATES = 20

RERANK_PROMPT = """\
Rank these documentation excerpts by how directly they help an engineer carry
out the request below. Judge usefulness for this specific task, not general
topical similarity: an excerpt stating a constraint, an interface, or a value
the work must respect outranks one merely mentioning the same subject.

Request:
{query}

Excerpts:
{excerpts}

Return JSON with:
- ranking: list of excerpt numbers, most useful first, length {keep}. Omit any
  excerpt that would not actually inform the work, even if that returns fewer
  than {keep} entries."""


QUERY_PROMPT = """\
An engineer is about to work on the request below. Write the search queries
that would pull the most useful material out of this project's documentation.

Target what the work will actually need settled — interfaces it must match,
constraints it must respect, existing behaviour it must not break — rather
than restating the request.

Request:
{request}

Return JSON with:
- queries: 2 to 4 short search queries, most important first."""


def worth_a_lookup(risk: object) -> bool:
    """Is this work consequential enough to pay a search fee for?

    Low risk means a wrong answer is trivially reversible and cannot hurt
    anyone — copy, configuration, presentation. Confabulation there costs a
    correction, not a board revision, so it does not justify the most expensive
    call this harness makes.

    Everything else does. The two measured confabulations that justify research
    at all — a charger IC named confidently and wrongly, and ERP quoted as EIRP
    — were both selection work at medium risk, so the floor sits below that
    deliberately.
    """
    from autornd.models.verdicts import RiskLevel

    if risk is None:
        return True          # unknown risk is not a licence to skip grounding
    return str(getattr(risk, "value", risk)).strip().lower() != RiskLevel.LOW.value


BRIEFING_PROMPT = """\
Write a short grounding briefing for an engineer about to start this request,
using only the project documentation excerpts below.

State what the documentation establishes that bears on this work: constraints
to respect, interfaces to match, values and limits, prior decisions. Be
specific and quote real values. If the excerpts do not cover something the
work will clearly need, say so plainly in `gaps` rather than guessing.

A gap belongs in `blocking_gaps` only if a wrong assumption about it would
change the answer — a figure that sets a dimension, a limit that decides
compliance, a convention that decides a unit. Most gaps are not that: they are
things it would be nice to know. Looking one up costs real money, so name only
the ones that would actually change what gets built.

Request:
{request}

Documentation excerpts:
{excerpts}

Return JSON with:
- briefing: the grounding text, at most 400 words
- gaps: list of things this work needs that the documentation does not cover
- blocking_gaps: the subset of those where a wrong assumption changes the
  answer. Often empty. Never more than three."""


async def expand_queries(client, request: str) -> list[str]:
    """Turn a request into targeted documentation queries (research tier).

    Falls back to searching the raw request, which is what retrieval did before
    any research model existed.
    """
    if client is None or not settings.model_research:
        return [request]
    try:
        data, _ = await client.chat_json(
            function="research",
            system_prompt=(
                "You write search queries that retrieve engineering "
                "documentation. Respond with JSON only."
            ),
            user_message=QUERY_PROMPT.format(request=request),
            temperature=0.0,
        )
        queries = [q for q in data.get("queries", []) if isinstance(q, str) and q.strip()]
        return queries[:4] or [request]
    except Exception as exc:
        logger.warning("Query expansion failed (%s) — searching the raw request", exc)
        return [request]


async def synthesize_briefing(client, request: str, chunks: list[dict],
                              risk: object = None) -> str:
    """Read the ranked excerpts and write a grounded briefing (research tier).

    Falls back to handing the excerpts through verbatim, which is what every
    phase received before the research tier did any work.
    """
    raw = "\n\n".join(
        f"[{c['tag']}] (distance: {c['distance']:.3f})\n{c['text']}" for c in chunks
    )
    if client is None or not settings.model_research or not chunks:
        return raw

    excerpts = "\n\n".join(f"[{c['tag']}] {c['text']}" for c in chunks)
    try:
        data, _ = await client.chat_json(
            function="research",
            system_prompt=(
                "You brief engineers from project documentation. You never "
                "invent facts the documentation does not contain. "
                "Respond with JSON only."
            ),
            user_message=BRIEFING_PROMPT.format(request=request, excerpts=excerpts),
            temperature=0.1,
        )
        briefing = (data.get("briefing") or "").strip()
        if not briefing:
            return raw
        gaps = [g for g in data.get("gaps", []) if isinstance(g, str)]
        blocking = [g for g in data.get("blocking_gaps", [])
                    if isinstance(g, str) and g.strip()][:3]
        out = briefing
        if gaps:
            out += "\n\nNot covered by project documentation:\n" + "\n".join(
                f"- {g}" for g in gaps
            )
        out += "\n\nSources: " + ", ".join(sorted({c["tag"] for c in chunks if c["tag"]}))

        # Only the gaps that change the answer are looked up. Every gap is
        # still shown above, because an engineer wants to know what is missing
        # whether or not it was worth a search fee.
        if blocking and settings.model_search and worth_a_lookup(risk):
            from autornd.knowledge.research import render_findings, research_gaps

            findings = await research_gaps(client, request, blocking)
            if findings:
                out += "\n\n" + render_findings(findings)
        return out
    except Exception as exc:
        logger.warning("Briefing synthesis failed (%s) — passing excerpts through", exc)
        return raw


async def rerank_chunks(
    client, query: str, candidates: list[dict], keep: int
) -> list[dict]:
    """Order candidates by usefulness, best first (ranker tier).

    Three strategies, each tried at most once: a purpose-built rerank model if
    the ranking tier holds one, a listwise ranking prompt if it holds a chat
    model, and embedding-distance order if neither works. Once a strategy is
    known to fail it is never attempted again, because context selection must
    never be the thing that fails a workflow — and must not quietly cost a call
    per workflow either.
    """
    global _rerank_mode

    tier = _rank_tier()
    if client is None or tier is None or len(candidates) <= keep:
        return candidates[:keep]

    if _rerank_mode == "distance":
        return candidates[:keep]

    model = settings.model_ranker if tier == "ranker" else settings.model_research

    # ── native rerank API ──
    if _rerank_mode in (None, "native"):
        try:
            scored = await client.rerank(
                model=model,
                query=query,
                documents=[c["text"] for c in candidates],
                top_n=keep,
            )
            picked = [candidates[i] for i, _ in scored if 0 <= i < len(candidates)]
            if picked:
                if _rerank_mode is None:
                    logger.info("Ranking via the rerank API (%s)", model)
                _rerank_mode = "native"
                return picked[:keep]
            logger.warning("Rerank API returned nothing usable for %s", model)
        except Exception as exc:
            if _rerank_mode is None:
                logger.info(
                    "%s does not serve the rerank API (%s) — trying listwise "
                    "ranking once", model, type(exc).__name__,
                )
        if _rerank_mode == "native":
            # It worked before and failed now: a transient fault, not a
            # capability change. Keep the mode and fall through this once.
            logger.warning("Rerank API call failed for %s — using distance order "
                           "for this workflow", model)
            return candidates[:keep]

    # ── listwise ranking by a chat model ──
    excerpts = "\n\n".join(
        f"[{i}] ({c['tag']}) {c['text'][:600]}" for i, c in enumerate(candidates)
    )
    try:
        data, _ = await client.chat_json(
            function=tier,
            system_prompt=(
                "You rank reference material by usefulness for a specific "
                "engineering task. Respond with JSON only."
            ),
            user_message=RERANK_PROMPT.format(
                query=query, excerpts=excerpts, keep=keep
            ),
            temperature=0.0,
        )
        order = data.get("ranking", [])
        picked = [
            candidates[i] for i in order
            if isinstance(i, int) and 0 <= i < len(candidates)
        ]
        if picked:
            if _rerank_mode is None:
                logger.info("Ranking listwise via %s", model)
            _rerank_mode = "listwise"
            return picked[:keep]
        logger.warning("Listwise ranking returned no usable order")
    except Exception as exc:
        logger.warning("Listwise ranking failed (%s)", exc)

    # Neither strategy works with this model. Stop paying to rediscover that.
    if _rerank_mode != "listwise":
        logger.info(
            "Neither the rerank API nor listwise ranking works with %s — "
            "using retrieval order from here on", model,
        )
        _rerank_mode = "distance"
    return candidates[:keep]


async def load_retrieval_context(query: str, n_results: int = 5, client=None,
                                 risk: object = None) -> str:
    """Research the project docs for a request: expand, retrieve, rank, brief."""
    queries = await expand_queries(client, query)

    seen: dict[str, dict] = {}
    for q in queries:
        for chunk in retrieve(q, n_results=max(n_results, RERANK_CANDIDATES)):
            seen.setdefault(chunk["text"], chunk)
    candidates = sorted(seen.values(), key=lambda c: c["distance"])
    if not candidates:
        return ""

    ranked = await rerank_chunks(client, query, candidates, n_results)
    return await synthesize_briefing(client, query, ranked, risk=risk)


SCOPING_PROMPT = """\
An engineer is about to plan and carry out the request below. There is no
project documentation available, so your job is to scope the work rather than
to report facts about the project.

Do exactly three things, and invent nothing:

1. Restate the objective precisely, in one or two sentences.
2. List what the request leaves unspecified that the work genuinely needs
   settled — interfaces, limits, targets, formats, environments.
3. List the assumptions a competent engineer would proceed on anyway, written
   so a reader can challenge each one.

Never state a project fact you were not given. An unknown belongs in the
unknowns list, never in an assumption dressed as fact.
{profile_block}
Request:
{request}

Return JSON with:
- objective: the restated objective
- unknowns: list of things the work needs but the request does not specify
- blocking_unknowns: the subset of unknowns where a wrong assumption would
  change the answer rather than merely being nice to know — a figure that sets
  a dimension, a limit that decides compliance, a convention that decides a
  unit. Often empty. Never more than three.
- assumptions: list of stated assumptions, each one challengeable
- considerations: list of factors this kind of work usually has to address"""


async def analyze_request(client, request: str) -> tuple[str, list[str]]:
    """Scope a request when there is no documentation to ground it (research tier).

    Returns the scoping text and, separately, only the unknowns worth paying to
    look up — the ones a wrong assumption would actually change the answer for.

    Most installs have an empty knowledge store, which used to leave every phase
    running on the raw request alone. Scoping does not need documents: naming
    what is unspecified, and what is being assumed instead, is useful on its own
    and keeps assumptions visible rather than buried in a plan.

    The two lists are deliberately different sizes. Every unknown appears in the
    scoping text, because knowing what is unspecified is the point. Only the
    blocking ones reach a search fee — asking a model "what is unknown here?"
    always returns a list, which is why research used to fire on every workflow
    whether or not anything needed looking up.
    """
    if client is None or not settings.model_research:
        return "", []

    from autornd.profiles import get_profile

    profile_ctx = get_profile().build_context()
    profile_block = f"\nProject profile:\n{profile_ctx}\n" if profile_ctx else ""

    try:
        data, _ = await client.chat_json(
            function="research",
            system_prompt=(
                "You scope engineering requests. You surface what is unknown "
                "rather than filling it in, and you never assert project facts "
                "you were not given. Respond with JSON only."
            ),
            user_message=SCOPING_PROMPT.format(
                request=request, profile_block=profile_block
            ),
            temperature=0.1,
        )
    except Exception as exc:
        logger.warning("Request scoping failed (%s) — phases run on the request alone", exc)
        return "", []

    objective = (data.get("objective") or "").strip()
    # Two lists, two jobs. Every unknown is shown to the engineer, because
    # knowing what is unspecified is the point of scoping. Only the blocking
    # ones are worth paying to look up, and asking a model "what is unknown
    # here?" always produces a list — which is why research used to fire on
    # every workflow regardless of whether anything needed it.
    unknowns = [u for u in data.get("unknowns", []) if isinstance(u, str) and u.strip()]
    blocking = [u for u in data.get("blocking_unknowns", [])
                if isinstance(u, str) and u.strip()]
    # A model that names no blocking unknowns has said the work can proceed on
    # stated assumptions. Take it at its word rather than looking up the rest.
    lookup_worthy = blocking[:3]
    sections = []
    if objective:
        sections.append(f"Objective: {objective}")
    for key, heading in (
        ("unknowns", "Unspecified — the plan must decide or ask"),
        ("assumptions", "Assumed unless corrected"),
        ("considerations", "Usually relevant to this kind of work"),
    ):
        items = [i for i in data.get(key, []) if isinstance(i, str) and i.strip()]
        if items:
            sections.append(heading + ":\n" + "\n".join(f"- {i}" for i in items))
    return "\n\n".join(sections), lookup_worthy


async def build_phase_context(
    request: str,
    domains: list[Domain],
    specialists: list[SpecialistRole] | None = None,
    include_retrieval: bool = True,
    client=None,
    risk: object = None,
) -> str:
    """Build full context string for a workflow phase.

    Combines deterministic docs (always) + ChromaDB retrieval (when available).
    """
    parts: list[str] = []

    docs_ctx = load_docs_context(domains, specialists)
    if docs_ctx:
        parts.append("=== PROJECT DOCUMENTATION ===\n" + docs_ctx)

    if include_retrieval:
        retrieval_ctx = await load_retrieval_context(request, client=client,
                                                     risk=risk)
        if retrieval_ctx:
            parts.append("=== RELEVANT KNOWLEDGE ===\n" + retrieval_ctx)
        else:
            # Nothing ingested, or nothing matched. Scoping still helps, and it
            # is labelled as analysis so no phase mistakes it for documentation.
            scoping, unknowns = await analyze_request(client, request)
            if scoping:
                parts.append("=== REQUEST ANALYSIS (no project documentation "
                             "available — assumptions, not facts) ===\n" + scoping)

            # An empty knowledge store is how this ships, and it is the case
            # that most needs looking things up. The unknowns scoping found are
            # the queries — the same mechanism as documentation gaps, from the
            # only other place that knows what is missing.
            if unknowns and settings.model_search and worth_a_lookup(risk):
                from autornd.knowledge.research import render_findings, research_gaps

                findings = await research_gaps(client, request, unknowns)
                if findings:
                    parts.append(render_findings(findings))

    return "\n\n".join(parts)
