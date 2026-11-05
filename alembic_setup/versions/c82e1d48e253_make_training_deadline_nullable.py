"""make training deadline nullable

Revision ID: c82e1d48e253
Revises: f2b1a4c8d370
Create Date: 2026-07-31

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "c82e1d48e253"
down_revision: Union[str, Sequence[str], None] = "f2b1a4c8d370"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.alter_column(
        "training",
        "deadline",
        existing_type=postgresql.TIMESTAMP(timezone=True),
        nullable=True,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.alter_column(
        "training",
        "deadline",
        existing_type=postgresql.TIMESTAMP(timezone=True),
        nullable=False,
    )
