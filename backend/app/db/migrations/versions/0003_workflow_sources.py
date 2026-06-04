"""multi-source capture: workflow_sources table, assembled_transcript on workflows

Revision ID: 0003_workflow_sources
Revises: 0002_add_reviewing_status
Create Date: 2026-06-04

A workflow now carries MANY sources of any modality. The single
source_modality / source_transcript columns on the workflow row are replaced
by rows in workflow_sources, plus a cached assembled_transcript on the
workflow itself. The cache is rebuilt by the assembly step whenever sources
change. Sources are the truth.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0003_workflow_sources"
down_revision = "0002_add_reviewing_status"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "workflow_sources",
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
        sa.Column("order", sa.Integer(), nullable=False),
        sa.Column("modality", sa.Text(), nullable=False),
        sa.Column("label", sa.Text(), nullable=True),
        sa.Column("raw_path", sa.Text(), nullable=True),
        sa.Column("assembled_text", sa.Text(), nullable=True),
        sa.Column("contributor_role", sa.Text(), nullable=True),
        sa.Column("status", sa.Text(), nullable=False, server_default="pending"),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("meta", postgresql.JSONB(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint(
            "modality IN ('text','voice','screen','document','chat','connector')",
            name="ck_sources_modality",
        ),
        sa.CheckConstraint(
            "status IN ('pending','processing','ready','failed')",
            name="ck_sources_status",
        ),
    )
    op.create_index(
        "idx_sources_workflow",
        "workflow_sources",
        ["workflow_id", "order"],
    )

    op.add_column(
        "workflows",
        sa.Column("assembled_transcript", sa.Text(), nullable=True),
    )

    # Backfill: every existing workflow becomes one source at order=0, carrying
    # its old modality and transcript. The same transcript also seeds the
    # workflow's assembled_transcript cache so extraction continues to work.
    op.execute(
        """
        INSERT INTO workflow_sources (
            id, workflow_id, "order", modality, label, raw_path,
            assembled_text, contributor_role, status, error, meta,
            created_at, updated_at
        )
        SELECT
            gen_random_uuid(),
            w.id,
            0,
            w.source_modality,
            NULL,
            NULL,
            w.source_transcript,
            NULL,
            CASE WHEN w.source_transcript IS NULL THEN 'pending' ELSE 'ready' END,
            NULL,
            NULL,
            w.created_at,
            w.updated_at
        FROM workflows w
        """
    )
    op.execute(
        "UPDATE workflows SET assembled_transcript = source_transcript"
    )

    op.drop_constraint("ck_workflows_modality", "workflows", type_="check")
    op.drop_column("workflows", "source_modality")
    op.drop_column("workflows", "source_transcript")


def downgrade() -> None:
    op.add_column(
        "workflows",
        sa.Column("source_modality", sa.Text(), nullable=True),
    )
    op.add_column(
        "workflows",
        sa.Column("source_transcript", sa.Text(), nullable=True),
    )

    # Restore the single-source view by collapsing back to the first ready
    # source per workflow. Workflows with no ready source fall back to 'text'
    # so the NOT NULL constraint below holds.
    op.execute(
        """
        UPDATE workflows w
        SET source_modality = CASE
                WHEN s.modality IN ('text','voice','screen') THEN s.modality
                ELSE 'text'
            END,
            source_transcript = COALESCE(w.assembled_transcript, s.assembled_text)
        FROM (
            SELECT DISTINCT ON (workflow_id) workflow_id, modality, assembled_text
            FROM workflow_sources
            WHERE status = 'ready'
            ORDER BY workflow_id, "order" ASC
        ) s
        WHERE s.workflow_id = w.id
        """
    )
    op.execute(
        "UPDATE workflows SET source_modality = 'text' WHERE source_modality IS NULL"
    )

    op.alter_column("workflows", "source_modality", nullable=False)
    op.create_check_constraint(
        "ck_workflows_modality",
        "workflows",
        "source_modality IN ('text','voice','screen')",
    )

    op.drop_column("workflows", "assembled_transcript")
    op.drop_index("idx_sources_workflow", table_name="workflow_sources")
    op.drop_table("workflow_sources")
