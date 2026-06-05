"""capture v2: library, versioning, collaborators, notifications, archive

Revision ID: 0004_capture_v2
Revises: 0003_workflow_sources
Create Date: 2026-06-05

Adds the structural support for the library + update lifecycle: a version
counter and description on the workflow row, an embedding column for
semantic search, approval metadata, soft-delete columns, and three new
tables for collaborators, version snapshots, and notifications. Status
check constraint expands to allow 'pending_update' and 'approved'.

Existing workflows backfill cleanly: version=1, everything else null or
default. No data migration is needed beyond the column adds.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0004_capture_v2"
down_revision = "0003_workflow_sources"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Workflow row extensions.
    op.add_column(
        "workflows",
        sa.Column("description", sa.Text(), nullable=True),
    )
    op.add_column(
        "workflows",
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
    )
    op.add_column(
        "workflows",
        sa.Column("embedding", postgresql.JSONB(), nullable=True),
    )
    op.add_column(
        "workflows",
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "workflows",
        sa.Column("approved_by", sa.Text(), nullable=True),
    )
    op.add_column(
        "workflows",
        sa.Column(
            "archived",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )
    op.add_column(
        "workflows",
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
    )

    # Status constraint: expand to include 'pending_update' and 'approved'.
    op.drop_constraint("ck_workflows_status", "workflows", type_="check")
    op.create_check_constraint(
        "ck_workflows_status",
        "workflows",
        "status IN ("
        "'capturing','transcribing','transcribed','extracting',"
        "'clarifying','reviewing','pending_update','approved','done','failed'"
        ")",
    )

    # New table: workflow_collaborators.
    op.create_table(
        "workflow_collaborators",
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
        sa.Column("member_id", sa.Text(), nullable=False),
        sa.Column("contribution_role", sa.Text(), nullable=False),
        sa.Column("added_by", sa.Text(), nullable=False),
        sa.Column(
            "added_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "notified",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.CheckConstraint(
            "contribution_role IN ('contributor','reviewer','approver')",
            name="ck_collab_role",
        ),
        sa.UniqueConstraint("workflow_id", "member_id", name="uq_collab_workflow_member"),
    )
    op.create_index(
        "idx_collab_member_notified",
        "workflow_collaborators",
        ["member_id", "notified"],
    )

    # New table: workflow_versions.
    op.create_table(
        "workflow_versions",
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
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("graph_snapshot", postgresql.JSONB(), nullable=False),
        sa.Column("sop_snapshot", sa.Text(), nullable=True),
        sa.Column("change_summary", sa.Text(), nullable=True),
        sa.Column("changed_by", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint("workflow_id", "version", name="uq_versions_workflow_version"),
    )

    # New table: workflow_notifications.
    op.create_table(
        "workflow_notifications",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("member_id", sa.Text(), nullable=False),
        sa.Column(
            "workflow_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("workflows.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("type", sa.Text(), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column(
            "read",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint(
            "type IN ('added_as_collaborator','update_requested','approved','needs_review')",
            name="ck_notif_type",
        ),
    )
    op.create_index(
        "idx_notif_member_read",
        "workflow_notifications",
        ["member_id", "read"],
    )


def downgrade() -> None:
    op.drop_index("idx_notif_member_read", table_name="workflow_notifications")
    op.drop_table("workflow_notifications")
    op.drop_table("workflow_versions")
    op.drop_index("idx_collab_member_notified", table_name="workflow_collaborators")
    op.drop_table("workflow_collaborators")

    # Status constraint: drop the new statuses. Any rows in those states
    # collapse back to 'done' for 'approved' and 'clarifying' for
    # 'pending_update'.
    op.execute("UPDATE workflows SET status = 'done' WHERE status = 'approved'")
    op.execute(
        "UPDATE workflows SET status = 'clarifying' WHERE status = 'pending_update'"
    )
    op.drop_constraint("ck_workflows_status", "workflows", type_="check")
    op.create_check_constraint(
        "ck_workflows_status",
        "workflows",
        "status IN ("
        "'capturing','transcribing','transcribed','extracting',"
        "'clarifying','reviewing','done','failed'"
        ")",
    )

    op.drop_column("workflows", "archived_at")
    op.drop_column("workflows", "archived")
    op.drop_column("workflows", "approved_by")
    op.drop_column("workflows", "approved_at")
    op.drop_column("workflows", "embedding")
    op.drop_column("workflows", "version")
    op.drop_column("workflows", "description")
