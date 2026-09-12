"""Episodic memory — stores workflow outcomes for future reference.

Past workflow outcomes help specialists avoid repeated mistakes and
reuse approaches that worked before.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

from sqlalchemy import Integer, Float, String, Text, Boolean, DateTime, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from autornd.database import Base

logger = logging.getLogger(__name__)


class Episode(Base):
    __tablename__ = "episodes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    workflow_id: Mapped[int] = mapped_column(Integer, nullable=False)
    request: Mapped[str] = mapped_column(Text, nullable=False)
    domains: Mapped[str] = mapped_column(Text, nullable=False)
    risk: Mapped[str] = mapped_column(String(20), nullable=False)
    iterations: Mapped[int] = mapped_column(Integer, default=1)
    shipped: Mapped[bool] = mapped_column(Boolean, default=False)
    verdict: Mapped[str] = mapped_column(Text, nullable=False)
    findings_count: Mapped[int] = mapped_column(Integer, default=0)
    total_cost: Mapped[float] = mapped_column(Float, default=0.0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )


async def save_episode(
    session: AsyncSession,
    workflow_id: int,
    request: str,
    domains: list[str],
    risk: str,
    iterations: int,
    shipped: bool,
    verdict: str,
    findings_count: int,
    total_cost: float,
):
    episode = Episode(
        workflow_id=workflow_id,
        request=request,
        domains=json.dumps(domains),
        risk=risk,
        iterations=iterations,
        shipped=shipped,
        verdict=verdict,
        findings_count=findings_count,
        total_cost=total_cost,
    )
    session.add(episode)
    await session.flush()
    logger.info("Saved episode for workflow %d (shipped=%s)", workflow_id, shipped)


async def get_recent_episodes(
    session: AsyncSession, limit: int = 10
) -> list[Episode]:
    stmt = select(Episode).order_by(Episode.created_at.desc()).limit(limit)
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def get_similar_episodes(
    session: AsyncSession, domains: list[str], limit: int = 5
) -> list[Episode]:
    """Find past episodes with overlapping domains."""
    all_episodes = await get_recent_episodes(session, limit=50)
    scored = []
    for ep in all_episodes:
        ep_domains = set(json.loads(ep.domains))
        overlap = len(ep_domains & set(domains))
        if overlap > 0:
            scored.append((overlap, ep))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [ep for _, ep in scored[:limit]]


def format_episodes_context(episodes: list[Episode]) -> str:
    """Format episodes as context for specialist prompts."""
    if not episodes:
        return ""

    lines = ["=== PAST WORKFLOW OUTCOMES ==="]
    for ep in episodes:
        status = "SHIPPED" if ep.shipped else "BLOCKED"
        lines.append(
            f"- [{status}] {ep.request[:100]} "
            f"(risk={ep.risk}, iterations={ep.iterations}, "
            f"findings={ep.findings_count}, cost=${ep.total_cost:.2f})"
        )
        if not ep.shipped:
            lines.append(f"  Verdict: {ep.verdict[:150]}")
    return "\n".join(lines)
