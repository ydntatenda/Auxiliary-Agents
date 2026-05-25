"""initial schema

Revision ID: 0001_initial
Revises:
Create Date: 2026-05-10
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "workflows",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("unit", sa.Text(), nullable=False),
        sa.Column("source_modality", sa.Text(), nullable=False),
        sa.Column("source_transcript", sa.Text(), nullable=True),
        sa.Column("status", sa.Text(), nullable=False, server_default="capturing"),
        sa.Column("graph", postgresql.JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("source_modality IN ('text','voice','screen')", name="ck_workflows_modality"),
        sa.CheckConstraint(
            "status IN ('capturing','transcribing','transcribed','extracting','clarifying','done','failed')",
            name="ck_workflows_status",
        ),
    )
    op.create_table(
        "clarification_history",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "workflow_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("workflows.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("role", sa.Text(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("role IN ('question','answer')", name="ck_clarification_role"),
    )
    op.create_index(
        "idx_clarification_workflow",
        "clarification_history",
        ["workflow_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("idx_clarification_workflow", table_name="clarification_history")
    op.drop_table("clarification_history")
    op.drop_table("workflows")

