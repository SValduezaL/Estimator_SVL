"""Ingestion jobs and pseudonym mappings tables (S6)."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0002_ingestion_jobs_and_mappings"
down_revision: Union[str, None] = "0001_initial_schema"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "pseudonym_mappings",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("entity_type", sa.String(64), nullable=False),
        sa.Column("original_hash", sa.String(128), nullable=False),
        sa.Column("pseudonym", sa.String(255), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint("entity_type", "original_hash", name="uq_mappings_entity_hash"),
    )
    op.create_index(
        "idx_mappings_lookup",
        "pseudonym_mappings",
        ["entity_type", "original_hash"],
    )

    op.create_table(
        "ingestion_jobs",
        sa.Column("job_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("source_name", sa.String(128), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="pending"),
        sa.Column("documents_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("error_message", sa.String(2048), nullable=True),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("idx_jobs_status", "ingestion_jobs", ["status"])


def downgrade() -> None:
    op.drop_index("idx_jobs_status", table_name="ingestion_jobs")
    op.drop_table("ingestion_jobs")
    op.drop_index("idx_mappings_lookup", table_name="pseudonym_mappings")
    op.drop_table("pseudonym_mappings")
