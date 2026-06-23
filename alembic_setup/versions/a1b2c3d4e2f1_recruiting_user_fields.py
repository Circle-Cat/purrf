"""recruiting user fields

Revision ID: a1b2c3d4e2f1
Revises: b7e3c1d05a92
Create Date: 2026-06-23 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e2f1"
down_revision: Union[str, Sequence[str], None] = "b7e3c1d05a92"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    user_type_enum = sa.Enum("internal", "external", name="user_type_enum")
    user_type_enum.create(op.get_bind(), checkfirst=True)
    op.add_column(
        "users",
        sa.Column("user_type", user_type_enum, server_default="external", nullable=False),
    )
    op.add_column(
        "users",
        sa.Column("is_blocked", sa.Boolean(), server_default="false", nullable=False),
    )
    op.add_column("users", sa.Column("blocked_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("users", sa.Column("blocked_reason", sa.String(), nullable=True))
    op.alter_column(
        "users",
        "communication_channel",
        existing_type=postgresql.ENUM("email", "google_chat", name="communication_method"),
        nullable=True,
    )


def downgrade() -> None:
    op.alter_column(
        "users",
        "communication_channel",
        existing_type=postgresql.ENUM("email", "google_chat", name="communication_method"),
        nullable=False,
    )
    op.drop_column("users", "blocked_reason")
    op.drop_column("users", "blocked_at")
    op.drop_column("users", "is_blocked")
    op.drop_column("users", "user_type")
    sa.Enum(name="user_type_enum").drop(op.get_bind(), checkfirst=True)
