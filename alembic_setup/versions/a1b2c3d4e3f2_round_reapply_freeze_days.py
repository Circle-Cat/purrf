"""round reapply_freeze_days

Revision ID: a1b2c3d4e3f2
Revises: a1b2c3d4e2f1
Create Date: 2026-06-23 00:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e3f2"
down_revision: Union[str, None] = "a1b2c3d4e2f1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "mentorship_round",
        sa.Column(
            "reapply_freeze_days", sa.Integer(), server_default="90", nullable=False
        ),
    )


def downgrade() -> None:
    op.drop_column("mentorship_round", "reapply_freeze_days")
