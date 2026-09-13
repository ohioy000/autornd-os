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
from autornd.knowledge.store import ingest_text

logger = logging.getLogger(__name__)

__all__ = ["Finding", "research_gaps"]

# A lookup costs about half a cent. A wrong component in a BOM costs a board
# revision, so the ceiling here is about bounding a runaway, not about thrift.
MAX_LOOKUPS = 4

LOOKUP_PROMPT = """\
Answer this engineering question from authoritative sources — manufacturer
datasheets, standards documents, official specifications.

{question}

Rules:
- Give the figures, with their units exactly as the source states them.
- Distinguish units that are commonly confused. ERP is not EIRP. Typical is not
  maximum. Absolute maximum ratings are not operating ranges.
- Name the source document for every figure.
- If authoritative sources disagree, say so and give both.
- If you cannot find it, say so plainly. An admitted gap is useful; a plausible
  guess is worse than nothing, because everything downstream will trust it.
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
) -> list[Finding]:
    """Look up the gaps a briefing identified, and keep what comes back.

    Returns findings in gap order. Failure of a single lookup is not fatal: a
    workflow with three of four facts is better off than one that aborted, and
    the missing one stays visible as a gap.
    """
    if client is None or not settings.model_search or not gaps:
        return []

    findings: list[Finding] = []
    for question in gaps[:max_lookups]:
        try:
            answer, citations, model = await _lookup(client, request, question)
        except Exception as exc:
            logger.warning("Lookup failed for %r: %s", question[:60], exc)
            continue
        if not answer:
            continue
        finding = Finding(question=question, answer=answer,
                          citations=citations, model=model)
        findings.append(finding)
        _remember(finding)

    if findings:
        grounded = sum(1 for f in findings if f.grounded)
        logger.info(
            "Researched %d gap(s): %d grounded in sources, %d unverified",
            len(findings), grounded, len(findings) - grounded,
        )
    return findings


async def _lookup(client, request: str, question: str) -> tuple[str, list[str], str]:
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
        max_tokens=settings.search_max_tokens,
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
