"""backfill applied stage to recruiter_screening

Revision ID: b0e98c2dd68c
Revises: a654c3a8b8b4
Create Date: 2026-07-02 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "b0e98c2dd68c"
down_revision: Union[str, Sequence[str], None] = "a654c3a8b8b4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Land pre-existing 'applied' rows on the new board's first stage.

    Submissions now land at ``stage_machine.first_stage(job.pipeline_config)``
    with ``sub_status = "pending"`` instead of the old ``ApplicationStage.
    APPLIED`` landing spot, so the board (which only reads configured
    pipeline stages) can see them. Dogfood rows created before this change
    still sit at ``applied`` and would otherwise be invisible to the new
    board; move them to ``recruiter_screening`` (the pipeline's universal
    first stage) and give them a ``pending`` sub_status if they don't
    already have one.
    """
    op.execute(
        "UPDATE application SET stage = 'recruiter_screening', "
        "sub_status = COALESCE(sub_status, 'pending') WHERE stage = 'applied'"
    )


def downgrade() -> None:
    """No-op: which backfilled rows were originally 'applied' is unrecoverable."""
    # The reverse mapping is ambiguous — rows already legitimately at
    # recruiter_screening (created after this change) are indistinguishable
    # from backfilled ones, so there is no safe way to move rows back to
    # 'applied'.
    pass
