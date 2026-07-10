"""add application and application_submission schema

Revision ID: b3c7f1a9d4e2
Revises: 70d81c883d0c
Create Date: 2026-07-10 00:00:00.000000

Backfills the migration that PUR-505 #112 shipped without one — the
`application`/`application_submission` tables plus `users.is_blocked` and
`job.cooldown_days` were originally applied only via
`bazel run //tools:init_db`, so any environment that reached this point in
history purely through `alembic upgrade head` (staging) never got them,
and the later `b0e98c2dd68c` backfill migration crashes on
`relation "application" does not exist`. Environments that already have
these objects (test, CI) got them via `init_db` stamping straight to
head, so they never actually executed the chain through this point —
inserting here is safe for them.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "b3c7f1a9d4e2"
down_revision: Union[str, Sequence[str], None] = "70d81c883d0c"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    sa.Enum(
        "applied",
        "recruiter_screening",
        "behavioral",
        "tech",
        "board_review",
        "offer",
        "hired",
        "rejected",
        "blacklisted",
        name="application_stage_enum",
    ).create(op.get_bind())
    op.create_table(
        "application",
        sa.Column("application_id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("job_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column(
            "stage",
            postgresql.ENUM(
                "applied",
                "recruiter_screening",
                "behavioral",
                "tech",
                "board_review",
                "offer",
                "hired",
                "rejected",
                "blacklisted",
                name="application_stage_enum",
                create_type=False,
            ),
            server_default="applied",
            nullable=False,
        ),
        sa.Column("sub_status", sa.String(), nullable=True),
        sa.Column("tags", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "created_datetime",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("updated_timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["job_id"],
            ["job.job_id"],
            name=op.f("fk_application_job_id_job"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.user_id"],
            name=op.f("fk_application_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("application_id", name=op.f("pk_application")),
        sa.UniqueConstraint("job_id", "user_id", name="uq_application_job_user"),
    )
    op.create_index(
        op.f("ix_application_job_id"), "application", ["job_id"], unique=False
    )
    op.create_index(
        op.f("ix_application_user_id"), "application", ["user_id"], unique=False
    )
    op.create_table(
        "application_submission",
        sa.Column("submission_id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("application_id", sa.Integer(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("is_frozen", sa.Boolean(), nullable=False),
        sa.Column("submission", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("resume_object_key", sa.String(), nullable=True),
        sa.Column("resume_sha256", sa.String(), nullable=True),
        sa.Column(
            "submitted_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["application_id"],
            ["application.application_id"],
            name=op.f("fk_application_submission_application_id_application"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint(
            "submission_id", name=op.f("pk_application_submission")
        ),
    )
    op.create_index(
        op.f("ix_application_submission_application_id"),
        "application_submission",
        ["application_id"],
        unique=False,
    )
    op.add_column(
        "users",
        sa.Column(
            "is_blocked",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
    )
    op.add_column("job", sa.Column("cooldown_days", sa.Integer(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("job", "cooldown_days")
    op.drop_column("users", "is_blocked")
    op.drop_index(
        op.f("ix_application_submission_application_id"),
        table_name="application_submission",
    )
    op.drop_table("application_submission")
    op.drop_index(op.f("ix_application_user_id"), table_name="application")
    op.drop_index(op.f("ix_application_job_id"), table_name="application")
    op.drop_table("application")
    sa.Enum(
        "applied",
        "recruiter_screening",
        "behavioral",
        "tech",
        "board_review",
        "offer",
        "hired",
        "rejected",
        "blacklisted",
        name="application_stage_enum",
    ).drop(op.get_bind())
