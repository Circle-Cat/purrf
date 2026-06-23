"""create application table

Revision ID: a1b2c3d4e5f4
Revises: a1b2c3d4e4f3
Create Date: 2026-06-23 00:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e5f4"
down_revision: Union[str, None] = "a1b2c3d4e4f3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create application_stage_enum, the application table, and its indexes."""
    stage = sa.Enum(
        "applied", "recruiter_screening", "behavioral", "tech", "board_review",
        "offer", "hired", "rejected", "offer_declined", "blacklisted",
        name="application_stage_enum",
    )
    stage.create(op.get_bind(), checkfirst=True)
    op.create_table(
        "application",
        sa.Column("application_id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False),
        sa.Column("job_id", sa.Integer(), sa.ForeignKey("job.job_id"), nullable=False),
        sa.Column("round_id", sa.Integer(), sa.ForeignKey("mentorship_round.round_id"), nullable=False),
        sa.Column("stage", stage, nullable=False),
        sa.Column("form_answers", postgresql.JSONB(), nullable=True),
        sa.Column("snapshot", postgresql.JSONB(), nullable=True),
        sa.Column("is_viewed", sa.Boolean(), server_default="false", nullable=False),
        sa.Column(
            "previous_application_id",
            sa.Integer(),
            sa.ForeignKey("application.application_id"),
            nullable=True,
        ),
        sa.Column(
            "rejected_round_id",
            sa.Integer(),
            sa.ForeignKey("mentorship_round.round_id"),
            nullable=True,
        ),
        sa.Column("rejected_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_datetime", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_timestamp", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_application_user_id", "application", ["user_id"])
    op.create_index("ix_application_job_id", "application", ["job_id"])
    op.create_index(
        "uq_application_active_user_job",
        "application",
        ["user_id", "job_id"],
        unique=True,
        postgresql_where=sa.text("stage NOT IN ('hired', 'rejected')"),
    )


def downgrade() -> None:
    """Drop the application table and application_stage_enum."""
    op.drop_table("application")
    sa.Enum(name="application_stage_enum").drop(op.get_bind(), checkfirst=True)
