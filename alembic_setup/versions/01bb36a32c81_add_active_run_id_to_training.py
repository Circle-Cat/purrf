"""add active_run_id to training

Revision ID: 01bb36a32c81
Revises: 9aebcd77b2b4
Create Date: 2026-09-30 10:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "01bb36a32c81"
down_revision: Union[str, Sequence[str], None] = "9aebcd77b2b4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "training",
        sa.Column("active_run_id", sa.String(length=64), nullable=True),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("training", "active_run_id")
