"""add stage_entered_at to application

Revision ID: 82498a573699
Revises: b78bd7956d7a
Create Date: 2026-07-22 09:12:35.207305

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "82498a573699"
down_revision: Union[str, Sequence[str], None] = "b78bd7956d7a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "application",
        sa.Column(
            "stage_entered_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index(
        "ix_application_job_stage_entered",
        "application",
        [
            "job_id",
            "stage",
            sa.text("stage_entered_at DESC"),
            sa.text("application_id DESC"),
        ],
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_application_job_stage_entered", table_name="application")
    op.drop_column("application", "stage_entered_at")
