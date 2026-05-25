"""add reviewing status

Revision ID: 0002_add_reviewing_status
Revises: 0001_initial
Create Date: 2026-05-13
"""
from alembic import op

revision = "0002_add_reviewing_status"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint("ck_workflows_status", "workflows", type_="check")
    op.create_check_constraint(
        "ck_workflows_status",
        "workflows",
        "status IN ('capturing','transcribing','transcribed','extracting','clarifying','reviewing','done','failed')",
    )


def downgrade() -> None:
    op.execute("UPDATE workflows SET status = 'done' WHERE status = 'reviewing'")
    op.drop_constraint("ck_workflows_status", "workflows", type_="check")
    op.create_check_constraint(
        "ck_workflows_status",
        "workflows",
        "status IN ('capturing','transcribing','transcribed','extracting','clarifying','done','failed')",
    )
