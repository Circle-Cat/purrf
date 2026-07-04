"""add round to application assignment

Revision ID: c1f4d8a2b6e9
Revises: 205cf4cb5f2f
Create Date: 2026-07-04 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "c1f4d8a2b6e9"
down_revision: Union[str, Sequence[str], None] = "205cf4cb5f2f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "application_assignment",
        sa.Column("round", sa.Integer(), server_default="1", nullable=False),
    )
    op.drop_constraint(
        "uq_application_assignment_app_stage",
        "application_assignment",
        type_="unique",
    )
    op.create_unique_constraint(
        "uq_application_assignment_app_stage_round",
        "application_assignment",
        ["application_id", "stage", "round"],
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint(
        "uq_application_assignment_app_stage_round",
        "application_assignment",
        type_="unique",
    )
    op.create_unique_constraint(
        "uq_application_assignment_app_stage",
        "application_assignment",
        ["application_id", "stage"],
    )
    op.drop_column("application_assignment", "round")
