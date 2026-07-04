"""add round to evaluation

Revision ID: 7117e5bd407d
Revises: c1f4d8a2b6e9
Create Date: 2026-07-04 00:00:00.000001

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "7117e5bd407d"
down_revision: Union[str, Sequence[str], None] = "c1f4d8a2b6e9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "evaluation",
        sa.Column("round", sa.Integer(), server_default="1", nullable=False),
    )
    op.drop_constraint(
        "uq_evaluation_app_stage_evaluator",
        "evaluation",
        type_="unique",
    )
    op.create_unique_constraint(
        "uq_evaluation_app_stage_round_evaluator",
        "evaluation",
        ["application_id", "stage", "round", "evaluator_id"],
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint(
        "uq_evaluation_app_stage_round_evaluator",
        "evaluation",
        type_="unique",
    )
    op.create_unique_constraint(
        "uq_evaluation_app_stage_evaluator",
        "evaluation",
        ["application_id", "stage", "evaluator_id"],
    )
    op.drop_column("evaluation", "round")
