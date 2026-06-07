"""Ownership columns: workflows.created_by, workflow_sources.added_by

Revision ID: 0006_ownership
Revises: 0005_sop_cache
Create Date: 2026-06-05

Adds a creator column to the workflow row and a contributor column to
the source row. The authz helper treats `created_by` as the workflow's
owner (creator = owner; admins always pass), and `added_by` as the
identity that can edit a given source (along with the workflow owner
and any admin).

Backfill: every existing workflow inherits CURRENT_USER_ID ('tatenda')
as its owner so legacy rows have a definite owner rather than a null
that the authz layer would have to treat as "admin only". Existing
source rows stay null on `added_by`, which the authz layer treats as
"only the workflow owner or an admin can change it" – the safest
interpretation when the provenance is unknown.
"""
from alembic import op
import sqlalchemy as sa


revision = "0006_ownership"
down_revision = "0005_sop_cache"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "workflows",
        sa.Column("created_by", sa.Text(), nullable=True),
    )
    op.add_column(
        "workflow_sources",
        sa.Column("added_by", sa.Text(), nullable=True),
    )
    op.execute(
        "UPDATE workflows SET created_by = 'tatenda' WHERE created_by IS NULL"
    )


def downgrade() -> None:
    op.drop_column("workflow_sources", "added_by")
    op.drop_column("workflows", "created_by")
