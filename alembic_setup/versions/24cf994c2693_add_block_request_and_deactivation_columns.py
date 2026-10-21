"""add block_request and deactivation columns

Revision ID: 24cf994c2693
Revises: c3a8e5d17b42
Create Date: 2026-09-05 09:34:10.224130

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "24cf994c2693"
down_revision: Union[str, Sequence[str], None] = "c3a8e5d17b42"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    sa.Enum(
        "pending",
        "approved",
        "rejected",
        "superseded",
        name="block_request_status_enum",
    ).create(op.get_bind())
    op.create_table(
        "block_request",
        sa.Column("request_id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("target_user_id", sa.Integer(), nullable=False),
        sa.Column("raised_by", sa.Integer(), nullable=False),
        sa.Column("raised_from", sa.String(length=64), nullable=False),
        sa.Column("reason", sa.String(), nullable=False),
        sa.Column("reviewer_id", sa.Integer(), nullable=False),
        sa.Column(
            "status",
            postgresql.ENUM(
                "pending",
                "approved",
                "rejected",
                "superseded",
                name="block_request_status_enum",
                create_type=False,
            ),
            server_default="pending",
            nullable=False,
        ),
        sa.Column("decided_by", sa.Integer(), nullable=True),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("decision_note", sa.String(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["decided_by"],
            ["users.user_id"],
            name=op.f("fk_block_request_decided_by_users"),
        ),
        sa.ForeignKeyConstraint(
            ["raised_by"],
            ["users.user_id"],
            name=op.f("fk_block_request_raised_by_users"),
        ),
        sa.ForeignKeyConstraint(
            ["reviewer_id"],
            ["users.user_id"],
            name=op.f("fk_block_request_reviewer_id_users"),
        ),
        sa.ForeignKeyConstraint(
            ["target_user_id"],
            ["users.user_id"],
            name=op.f("fk_block_request_target_user_id_users"),
        ),
        sa.PrimaryKeyConstraint("request_id", name=op.f("pk_block_request")),
    )
    op.add_column("users", sa.Column("deactivated_by", sa.Integer(), nullable=True))
    op.add_column(
        "users", sa.Column("deactivated_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column("users", sa.Column("deactivated_reason", sa.String(), nullable=True))
    op.create_foreign_key(
        op.f("fk_users_deactivated_by_users"),
        "users",
        "users",
        ["deactivated_by"],
        ["user_id"],
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint(
        op.f("fk_users_deactivated_by_users"), "users", type_="foreignkey"
    )
    op.drop_column("users", "deactivated_reason")
    op.drop_column("users", "deactivated_at")
    op.drop_column("users", "deactivated_by")
    op.drop_table("block_request")
    sa.Enum(
        "pending",
        "approved",
        "rejected",
        "superseded",
        name="block_request_status_enum",
    ).drop(op.get_bind())
