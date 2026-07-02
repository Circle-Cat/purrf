"""add blacklist audit columns

Revision ID: a654c3a8b8b4
Revises: 95b36bb95db2
Create Date: 2026-07-02 12:21:43.297714

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "a654c3a8b8b4"
down_revision: Union[str, Sequence[str], None] = "95b36bb95db2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("users", sa.Column("blocked_by", sa.Integer(), nullable=True))
    op.add_column(
        "users", sa.Column("blocked_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column("users", sa.Column("blocked_reason", sa.String(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("users", "blocked_reason")
    op.drop_column("users", "blocked_at")
    op.drop_column("users", "blocked_by")
