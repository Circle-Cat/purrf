"""add current_round to application

Revision ID: 205cf4cb5f2f
Revises: b0e98c2dd68c
Create Date: 2026-07-03 08:00:10.293854

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "205cf4cb5f2f"
down_revision: Union[str, Sequence[str], None] = "b0e98c2dd68c"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "application",
        sa.Column("current_round", sa.Integer(), server_default="1", nullable=False),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("application", "current_round")
