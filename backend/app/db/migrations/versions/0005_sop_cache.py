"""SOP cache columns on the workflow row.

Revision ID: 0005_sop_cache
Revises: 0004_capture_v2
Create Date: 2026-06-05

Adds two nullable columns to support caching the rendered SOP markdown:
sop_cache holds the markdown string, sop_cache_graph_hash holds the
SHA-256 of the graph JSON the cache was generated from (gaps stripped,
to match what the renderer actually reads). Hash mismatch invalidates
the cache, so any graph mutation forces a fresh render.

No backfill: existing rows have null in both columns, which the SOP
endpoints treat as "no cache yet" and fall through to a real render.
"""
from alembic import op
import sqlalchemy as sa

revision = "0005_sop_cache"
down_revision = "0004_capture_v2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("workflows", sa.Column("sop_cache", sa.Text(), nullable=True))
    op.add_column(
        "workflows",
        sa.Column("sop_cache_graph_hash", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("workflows", "sop_cache_graph_hash")
    op.drop_column("workflows", "sop_cache")
