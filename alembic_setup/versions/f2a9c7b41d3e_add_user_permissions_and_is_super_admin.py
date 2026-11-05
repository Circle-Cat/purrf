"""Add user_permissions table and users.is_super_admin

Revision ID: f2a9c7b41d3e
Revises: dee5e8b0c892
Create Date: 2026-05-30 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "f2a9c7b41d3e"
down_revision: Union[str, Sequence[str], None] = "dee5e8b0c892"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "user_permissions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("permission_name", sa.String(length=64), nullable=False),
        sa.Column("granted_source", sa.String(length=32), nullable=False),
        sa.Column("granted_by", sa.Integer(), nullable=True),
        sa.Column(
            "granted_timestamp",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("revoked_by", sa.Integer(), nullable=True),
        sa.Column("revoked_timestamp", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.user_id"],
            name=op.f("fk_user_permissions_user_id_users"),
        ),
        sa.ForeignKeyConstraint(
            ["granted_by"],
            ["users.user_id"],
            name=op.f("fk_user_permissions_granted_by_users"),
        ),
        sa.ForeignKeyConstraint(
            ["revoked_by"],
            ["users.user_id"],
            name=op.f("fk_user_permissions_revoked_by_users"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_user_permissions")),
    )
    op.create_index(
        "user_permissions_user_id_idx", "user_permissions", ["user_id"], unique=False
    )
    op.create_index(
        "user_permissions_permission_name_idx",
        "user_permissions",
        ["permission_name"],
        unique=False,
    )
    op.create_index(
        "user_permissions_active_idx",
        "user_permissions",
        ["user_id"],
        unique=False,
        postgresql_where=sa.text("revoked_timestamp IS NULL"),
    )
    op.add_column(
        "users",
        sa.Column(
            "is_super_admin",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("users", "is_super_admin")
    op.drop_index("user_permissions_active_idx", table_name="user_permissions")
    op.drop_index("user_permissions_permission_name_idx", table_name="user_permissions")
    op.drop_index("user_permissions_user_id_idx", table_name="user_permissions")
    op.drop_table("user_permissions")
