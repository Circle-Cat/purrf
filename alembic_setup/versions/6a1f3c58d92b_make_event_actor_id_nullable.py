"""make event actor_id nullable

Revision ID: 6a1f3c58d92b
Revises: 2ec9de850734
Create Date: 2026-08-11

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "6a1f3c58d92b"
down_revision: Union[str, Sequence[str], None] = "2ec9de850734"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.alter_column(
        "event",
        "actor_id",
        existing_type=sa.Integer(),
        nullable=True,
    )


def downgrade() -> None:
    """Downgrade schema."""
    # Events the system recorded under its own rules have no actor to put
    # back, so restoring NOT NULL means dropping them.
    op.execute("DELETE FROM event WHERE actor_id IS NULL")
    op.alter_column(
        "event",
        "actor_id",
        existing_type=sa.Integer(),
        nullable=False,
    )
