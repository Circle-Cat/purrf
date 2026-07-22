"""add users.is_internal

Revision ID: cb7074b198ec
Revises: 9b509b737039
Create Date: 2026-07-22 03:43:21.981007

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'cb7074b198ec'
down_revision: Union[str, Sequence[str], None] = '9b509b737039'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "users",
        sa.Column(
            "is_internal",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
    )
    # Backfill from the legacy signal before it stops being written (Task 4):
    # any user that today has an INTERNAL identity row is an internal employee.
    op.execute(
        """
        UPDATE users SET is_internal = TRUE
        WHERE EXISTS (
            SELECT 1 FROM user_identities ui
            WHERE ui.user_id = users.user_id
              AND ui.identity_type = 'internal'
        )
        """
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("users", "is_internal")
