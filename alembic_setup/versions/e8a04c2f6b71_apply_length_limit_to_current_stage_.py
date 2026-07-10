"""apply length limit to current_stage and time_urgency

Revision ID: e8a04c2f6b71
Revises: 938f67fc6602
Create Date: 2026-07-10 00:05:00.000000

Backfills `7ab80335bdac`, which was supposed to apply this length limit
but shipped with empty upgrade()/downgrade() bodies. The entity has
declared String(100) since that migration's commit; the column itself
was never actually constrained.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "e8a04c2f6b71"
down_revision: Union[str, Sequence[str], None] = "938f67fc6602"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.alter_column(
        "mentorship_round_participants",
        "current_stage",
        existing_type=sa.String(),
        type_=sa.String(length=100),
        existing_nullable=True,
    )
    op.alter_column(
        "mentorship_round_participants",
        "time_urgency",
        existing_type=sa.String(),
        type_=sa.String(length=100),
        existing_nullable=True,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.alter_column(
        "mentorship_round_participants",
        "time_urgency",
        existing_type=sa.String(length=100),
        type_=sa.String(),
        existing_nullable=True,
    )
    op.alter_column(
        "mentorship_round_participants",
        "current_stage",
        existing_type=sa.String(length=100),
        type_=sa.String(),
        existing_nullable=True,
    )
