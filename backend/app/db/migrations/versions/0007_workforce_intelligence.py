"""Worker profiles and organisational assessments.

Revision ID: 0007_workforce_intelligence
Revises: 0006_ownership
Create Date: 2026-09-09
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "0007_workforce_intelligence"
down_revision = "0006_ownership"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "worker_profiles",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("member_id", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("current_role", sa.Text(), nullable=True),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("skills", postgresql.JSONB(), nullable=False),
        sa.Column("experience", postgresql.JSONB(), nullable=False),
        sa.Column("qualifications", postgresql.JSONB(), nullable=False),
        sa.Column("career_preferences", postgresql.JSONB(), nullable=False),
        sa.Column("provenance", postgresql.JSONB(), nullable=False),
        sa.Column("source_filename", sa.Text(), nullable=True),
        sa.Column("source_path", sa.Text(), nullable=True),
        sa.Column("source_text", sa.Text(), nullable=True),
        sa.Column("status", sa.Text(), nullable=False, server_default="draft"),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("status IN ('draft','confirmed')", name="ck_worker_profiles_status"),
        sa.UniqueConstraint("member_id", name="uq_worker_profiles_member"),
    )
    op.create_table(
        "organisational_assessments",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("workflow_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("workflows.id", ondelete="CASCADE"), nullable=False),
        sa.Column("workflow_version", sa.Integer(), nullable=False),
        sa.Column("report", postgresql.JSONB(), nullable=False),
        sa.Column("created_by", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index(
        "idx_assessments_workflow_created",
        "organisational_assessments",
        ["workflow_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("idx_assessments_workflow_created", table_name="organisational_assessments")
    op.drop_table("organisational_assessments")
    op.drop_table("worker_profiles")
