"""relax application job user uniqueness to active rows

Revision ID: cbfb424b9abb
Revises: e8a04c2f6b71
Create Date: 2026-07-15 03:53:58.243213

Replaces `uq_application_job_user` (unique on every row) with the partial
unique index `uq_application_job_user_active` (unique on job_id, user_id
WHERE stage != 'rejected'). Rejected attempts now accumulate as history
instead of forcing a re-apply to mutate the old row; at most one non-
rejected application may still exist per (job, user).

Note: downgrade fails if any (job, user) pair already has more than one
rejected row (the plain unique constraint can't be restored while
duplicate keys exist) — an acceptable expand-contract caveat.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "cbfb424b9abb"
down_revision: Union[str, Sequence[str], None] = "e8a04c2f6b71"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_constraint("uq_application_job_user", "application", type_="unique")
    op.create_index(
        "uq_application_job_user_active",
        "application",
        ["job_id", "user_id"],
        unique=True,
        postgresql_where=sa.text("stage != 'rejected'"),
    )


def downgrade() -> None:
    op.drop_index("uq_application_job_user_active", table_name="application")
    op.create_unique_constraint(
        "uq_application_job_user", "application", ["job_id", "user_id"]
    )
