"""add leave management tables

Revision ID: c4d81b2fa906
Revises: 6a1f3c58d92b
Create Date: 2026-08-13

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "c4d81b2fa906"
down_revision: Union[str, Sequence[str], None] = "6a1f3c58d92b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_REQUEST_TYPE_ENUM = "leave_request_type_enum"
_REQUEST_STATUS_ENUM = "leave_request_status_enum"
_ENTRY_TYPE_ENUM = "leave_entry_type_enum"


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "leave_holiday",
        sa.Column("leave_holiday_id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("is_exchangeable", sa.Boolean(), nullable=False),
        sa.CheckConstraint(
            "year = EXTRACT(YEAR FROM date)",
            name=op.f("ck_leave_holiday_year_agrees_with_date"),
        ),
        sa.PrimaryKeyConstraint("leave_holiday_id", name=op.f("pk_leave_holiday")),
        sa.UniqueConstraint("year", "date", name=op.f("uq_leave_holiday_year")),
    )

    op.create_table(
        "leave_request",
        sa.Column("leave_request_id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column(
            "type",
            sa.Enum("paid", "sick", "exchange", name=_REQUEST_TYPE_ENUM),
            nullable=False,
        ),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=False),
        sa.Column("start_time", sa.Time(), nullable=True),
        sa.Column("end_time", sa.Time(), nullable=True),
        sa.Column("hours", sa.Numeric(precision=5, scale=2), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "pending",
                "approved",
                "rejected",
                "withdrawn",
                "cancel_pending",
                "cancelled",
                name=_REQUEST_STATUS_ENUM,
            ),
            nullable=False,
        ),
        sa.Column("approver_user_id", sa.Integer(), nullable=False),
        sa.Column("reason", sa.String(), nullable=True),
        sa.Column(
            "is_overdraft",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        sa.Column(
            "is_late_notice",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        sa.Column("decided_by", sa.Integer(), nullable=True),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_timestamp",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_timestamp",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "start_date = end_date OR (start_time IS NULL AND end_time IS NULL)",
            name=op.f("ck_leave_request_times_only_on_a_single_day"),
        ),
        sa.CheckConstraint(
            "end_date >= start_date", name=op.f("ck_leave_request_dates_ordered")
        ),
        sa.ForeignKeyConstraint(
            ["approver_user_id"],
            ["users.user_id"],
            name=op.f("fk_leave_request_approver_user_id_users"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["decided_by"],
            ["users.user_id"],
            name=op.f("fk_leave_request_decided_by_users"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.user_id"],
            name=op.f("fk_leave_request_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("leave_request_id", name=op.f("pk_leave_request")),
    )
    op.create_index(
        op.f("ix_leave_request_user_id"), "leave_request", ["user_id"], unique=False
    )
    op.create_index(
        op.f("ix_leave_request_approver_user_id"),
        "leave_request",
        ["approver_user_id"],
        unique=False,
    )

    op.create_table(
        "leave_ledger",
        sa.Column("leave_ledger_id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column(
            "entry_type",
            sa.Enum(
                "weekly_accrual",
                "leave_deduction",
                "exchange_credit",
                "manual_adjustment",
                "reversal",
                "carryover_forfeit",
                name=_ENTRY_TYPE_ENUM,
            ),
            nullable=False,
        ),
        sa.Column("hours", sa.Numeric(precision=6, scale=2), nullable=False),
        sa.Column("effective_date", sa.Date(), nullable=False),
        sa.Column("source_request_id", sa.Integer(), nullable=True),
        sa.Column("note", sa.String(), nullable=True),
        sa.Column("created_by", sa.Integer(), nullable=True),
        sa.Column(
            "created_timestamp",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["created_by"],
            ["users.user_id"],
            name=op.f("fk_leave_ledger_created_by_users"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["source_request_id"],
            ["leave_request.leave_request_id"],
            name=op.f("fk_leave_ledger_source_request_id_leave_request"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.user_id"],
            name=op.f("fk_leave_ledger_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("leave_ledger_id", name=op.f("pk_leave_ledger")),
    )
    op.create_index(
        op.f("ix_leave_ledger_user_id"), "leave_ledger", ["user_id"], unique=False
    )
    op.create_index(
        op.f("ix_leave_ledger_source_request_id"),
        "leave_ledger",
        ["source_request_id"],
        unique=False,
    )
    # Partial on purpose: it guards the two types a cron writes, so a job that
    # runs twice cannot grant or forfeit twice. Manual adjustments stay outside
    # it -- an admin may book several corrections for one person on one day.
    op.create_index(
        "uq_leave_ledger_job_written_entry",
        "leave_ledger",
        ["user_id", "entry_type", "effective_date"],
        unique=True,
        postgresql_where=sa.text(
            "entry_type IN ('weekly_accrual', 'carryover_forfeit')"
        ),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("uq_leave_ledger_job_written_entry", table_name="leave_ledger")
    op.drop_index(op.f("ix_leave_ledger_source_request_id"), table_name="leave_ledger")
    op.drop_index(op.f("ix_leave_ledger_user_id"), table_name="leave_ledger")
    op.drop_table("leave_ledger")

    op.drop_index(op.f("ix_leave_request_approver_user_id"), table_name="leave_request")
    op.drop_index(op.f("ix_leave_request_user_id"), table_name="leave_request")
    op.drop_table("leave_request")

    op.drop_table("leave_holiday")

    # Dropping a table does not drop the type it uses, so a re-run of upgrade()
    # would fail on "type already exists" without this.
    for enum_name in (_ENTRY_TYPE_ENUM, _REQUEST_STATUS_ENUM, _REQUEST_TYPE_ENUM):
        op.execute(f"DROP TYPE {enum_name}")
