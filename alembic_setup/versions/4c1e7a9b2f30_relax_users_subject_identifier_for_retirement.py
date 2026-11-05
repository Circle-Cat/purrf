"""Relax users.subject_identifier ahead of column retirement

Expand step of the users.subject_identifier retirement. Application code no
longer reads or writes this legacy column (the live sub lives on
user_identities); this revision drops its UNIQUE constraint and NOT NULL so
that new rows insert it as NULL without violating the schema. The column itself
is dropped by a later (contract) revision once this change is fully deployed and
no running pod references the column.

Revision ID: 4c1e7a9b2f30
Revises: b7e3c1d05a92
Create Date: 2026-06-25 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "4c1e7a9b2f30"
down_revision: Union[str, Sequence[str], None] = "b7e3c1d05a92"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Drop the UNIQUE constraint and NOT NULL on users.subject_identifier."""
    op.drop_constraint("uq_users_subject_identifier", "users", type_="unique")
    op.alter_column(
        "users",
        "subject_identifier",
        existing_type=sa.String(),
        nullable=True,
    )


def downgrade() -> None:
    """Restore NOT NULL and the UNIQUE constraint.

    Only succeeds if no NULL or duplicate subject_identifier rows were written
    while the column was relaxed; for a column already on its way out this is a
    best-effort inverse around the deploy boundary.
    """
    op.alter_column(
        "users",
        "subject_identifier",
        existing_type=sa.String(),
        nullable=False,
    )
    op.create_unique_constraint(
        "uq_users_subject_identifier", "users", ["subject_identifier"]
    )
