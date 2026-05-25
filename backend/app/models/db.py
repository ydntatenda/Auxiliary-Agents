from datetime import datetime
from uuid import UUID as PyUUID
from uuid import uuid4

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class WorkflowRow(Base):
    __tablename__ = "workflows"
    __table_args__ = (
        CheckConstraint("source_modality IN ('text','voice','screen')", name="ck_workflows_modality"),
        CheckConstraint(
            "status IN ('capturing','transcribing','transcribed','extracting','clarifying','done','failed')",
            name="ck_workflows_status",
        ),
    )

    id: Mapped[PyUUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    unit: Mapped[str] = mapped_column(Text, nullable=False)
    source_modality: Mapped[str] = mapped_column(Text, nullable=False)
    source_transcript: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text, nullable=False, default="capturing")
    graph: Mapped[dict | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class ClarificationHistoryRow(Base):
    __tablename__ = "clarification_history"
    __table_args__ = (
        CheckConstraint("role IN ('question','answer')", name="ck_clarification_role"),
        Index("idx_clarification_workflow", "workflow_id", "created_at"),
    )

    id: Mapped[PyUUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    workflow_id: Mapped[PyUUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("workflows.id", ondelete="CASCADE"), nullable=False
    )
    role: Mapped[str] = mapped_column(Text, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
