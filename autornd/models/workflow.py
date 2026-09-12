"""ORM models for workflow state persistence."""

from __future__ import annotations

import enum
from datetime import datetime, timezone

from sqlalchemy import Enum as SAEnum, ForeignKey, Integer, String, Text, DateTime, Float
from sqlalchemy.orm import Mapped, mapped_column, relationship

from autornd.database import Base


class WorkflowStatus(str, enum.Enum):
    PENDING = "pending"
    TRIAGE = "triage"
    PLAN = "plan"
    IMPLEMENT = "implement"
    VALIDATE = "validate"
    REVIEW = "review"
    COMPLETED = "completed"
    BLOCKED = "blocked"
    ESCALATED = "escalated"


class Workflow(Base):
    __tablename__ = "workflows"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    request: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[WorkflowStatus] = mapped_column(
        SAEnum(WorkflowStatus), default=WorkflowStatus.PENDING
    )
    risk_level: Mapped[str | None] = mapped_column(String(20), nullable=True)
    iteration: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
    total_cost: Mapped[float] = mapped_column(Float, default=0.0)

    phases: Mapped[list[PhaseResult]] = relationship(
        back_populates="workflow", cascade="all, delete-orphan"
    )


class PhaseResult(Base):
    __tablename__ = "phase_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    workflow_id: Mapped[int] = mapped_column(ForeignKey("workflows.id"), nullable=False)
    phase: Mapped[str] = mapped_column(String(20), nullable=False)
    iteration: Mapped[int] = mapped_column(Integer, default=1)
    verdict_json: Mapped[str] = mapped_column(Text, nullable=False)
    model_used: Mapped[str | None] = mapped_column(String(100), nullable=True)
    cost: Mapped[float] = mapped_column(Float, default=0.0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )

    workflow: Mapped[Workflow] = relationship(back_populates="phases")
