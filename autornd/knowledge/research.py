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
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from autornd.config import settings
from autornd.knowledge.store import ingest_text, retrieve

logger = logging.getLogger(__name__)

__all__ = ["Finding", "research_gaps"]

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

# How close a stored finding must be to count as already answering a gap.
# Chroma returns squared L2 distance here, so smaller is nearer; 0.35 keeps
# near-restatements and rejects merely related subject matter. Set
# conservatively on purpose: reusing the wrong finding is a wrong figure in a
# design, while a needless lookup only costs money.
REUSE_DISTANCE = 0.35

LOOKUP_PROMPT = """\
Answer these engineering questions from authoritative sources — manufacturer
datasheets, standards documents, official specifications.

{question}

Answer every question above. Each one is here because the work cannot proceed
on an assumption about it, so a partial answer leaves the work blocked.

Rules:
- Give the figures, with their units exactly as the source states them.
- Distinguish units that are commonly confused. ERP is not EIRP. Typical is not
  maximum. Absolute maximum ratings are not operating ranges.
- Name the source document for every figure.
- Name the standard or code that governs this class of work, even when the
  question does not mention one.
- Add what a practitioner would expect to see that the question did not ask
  for. Measured against published standards, the gaps were all of this kind: a
  pasteuriser answer with no flow-diversion valve, a partition answer with no
  flanking path, an interlocking answer with no safety-integrity level. The
  person asking usually does not know what they left out.
- If authoritative sources disagree, say so and give both.
- If you cannot find it, say so plainly. An admitted gap is useful; a plausible
  guess is worse than nothing, because everything downstream will trust it.
  This applies to the additions above too: an element you cannot source is
  named as unverified, never stated as a specification.
"""


@dataclass
class Finding:
    question: str
    answer: str
    citations: list[str] = field(default_factory=list)
    model: str = ""

    @property
    def grounded(self) -> bool:
        """Did anything back this up?

        An uncited finding is the failure mode this exists to prevent — a
        confident assertion with nothing behind it. Kept, because a model saying
        "I could not find this" is genuinely useful, but marked, because a
        reader must be able to tell the two apart.
        """
        return bool(self.citations)

    def render(self) -> str:
        lines = [f"Q: {self.question}", f"A: {self.answer}"]
        if self.citations:
            lines.append("Sources: " + ", ".join(self.citations[:5]))
        else:
            lines.append("Sources: none found — treat as unverified")
        return "\n".join(lines)


async def research_gaps(
    client,
    request: str,
    gaps: list[str],
    max_lookups: int = MAX_LOOKUPS,
    max_tokens: int | None = None,
) -> list[Finding]:
    """Look up the gaps a briefing identified, and keep what comes back.

    Returns findings in gap order. Failure of a single lookup is not fatal: a
    workflow with three of four facts is better off than one that aborted, and
    the missing one stays visible as a gap.
    """
    if client is None or not settings.model_search or not gaps:
        return []

    # Ask everything in one request. Splitting the gaps would mean one search
    # fee each, and the fee is charged per request rather than per question.
    questions = [g.strip() for g in gaps if g and g.strip()]
    if not questions:
        return []
    if max_lookups <= 1 and len(questions) > 1:
        bundled = "\n".join(f"{i}. {q}" for i, q in enumerate(questions, 1))
        gaps = [bundled]
        max_lookups = 1

    findings: list[Finding] = []
    for question in gaps[:max_lookups]:
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
        try:
            answer, citations, model = await _lookup(
                client, request, question, max_tokens=max_tokens)
        except Exception as exc:
            logger.warning("Lookup failed for %r: %s", question[:60], exc)
            continue
        if not answer:
            continue
        finding = Finding(question=question, answer=answer,
                          citations=citations, model=model)
        findings.append(finding)
        _remember(finding)   # recalled findings skip this: already stored

    if findings:
        grounded = sum(1 for f in findings if f.grounded)
        logger.info(
            "Researched %d gap(s): %d grounded in sources, %d unverified",
            len(findings), grounded, len(findings) - grounded,
        )
    return findings


def _recall(question: str) -> Finding | None:
    """A stored finding that already answers this gap, if there is one.

    Only previously researched material counts. Project documentation is
    already in the briefing that produced the gap, so treating a documentation
    chunk as an answer would mean the gap was never a gap.
    """
    try:
        hits = retrieve(question, n_results=1, where={"tag": "research"})
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
                  max_tokens: int | None = None) -> tuple[str, list[str], str]:
    """One search-backed lookup. Returns (answer, citations, model)."""
    response = await client.chat(
        function="search",
        system_prompt=(
            "You answer engineering questions from authoritative sources and "
            "cite them. You never present a guess as a specification."
        ),
        user_message=LOOKUP_PROMPT.format(question=question)
        + f"\n\nThis is being looked up in service of: {request}",
        temperature=0.0,
        max_tokens=max_tokens or settings.search_max_tokens,
    )
    return (
        (response.content or "").strip(),
        list(getattr(response, "citations", None) or []),
        response.model,
    )


def _remember(finding: Finding) -> None:
    """Keep a finding, so the next workflow on this subject already has it.

    Only cited findings are stored. An unverified answer is worth showing to the
    person running this workflow and is not worth becoming permanent context
    that later runs treat as project knowledge.
    """
    if not finding.grounded:
        return
    try:
        ingest_text(
            finding.render(),
            tag="research",
            source=finding.citations[0] if finding.citations else "research",
        )
    except Exception as exc:
        logger.warning("Could not store finding: %s", exc)


def render_findings(findings: list[Finding]) -> str:
    """Findings as prompt context, with their provenance attached."""
    if not findings:
        return ""
    body = "\n\n".join(f.render() for f in findings)
    unverified = [f for f in findings if not f.grounded]
    header = (
        "=== RESEARCHED FACTS (looked up because the project documentation did "
        "not cover them) ==="
    )
    if unverified:
        header += (
            f"\n{len(unverified)} of {len(findings)} could not be sourced and are "
            f"marked unverified — do not treat those as specifications."
        )
    return f"{header}\n{body}"
