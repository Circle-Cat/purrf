"""drop notification read_at

Revision ID: b8d2f5a91c37
Revises: e1c8a3d4f6b2
Create Date: 2026-07-18 12:00:00.000000

Notifications became light reminders: dismissing one deletes the row
instead of stamping it read, so every surviving row is unread by
construction and read_at can never be non-null. Nothing reads the column
anymore, so it goes.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "b8d2f5a91c37"
down_revision: Union[str, Sequence[str], None] = "e1c8a3d4f6b2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Drop the retired read_at column."""
    op.drop_column("notification", "read_at")


def downgrade() -> None:
    """Re-add read_at as nullable NULL.

    No backfill is possible: rows that were dismissed under the
    delete-on-read model are gone, and every surviving row was unread.
    """
    op.add_column(
        "notification",
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
    )
