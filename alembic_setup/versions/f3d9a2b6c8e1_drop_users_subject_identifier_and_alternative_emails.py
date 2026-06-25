"""Drop legacy users.subject_identifier and users.alternative_emails

Contract step of retiring both legacy columns. Application code no longer reads
or writes either: the real Auth0 sub lives on user_identities (relaxed in
4c1e7a9b2f30, stop-using shipped earlier) and alternative emails are non-primary
user_emails rows. The ORM attributes have been removed, so nothing references
these columns anymore; this revision drops them.

Revision ID: f3d9a2b6c8e1
Revises: 4c1e7a9b2f30
Create Date: 2026-06-25 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "f3d9a2b6c8e1"
down_revision: Union[str, Sequence[str], None] = "4c1e7a9b2f30"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Drop the two retired legacy columns from users."""
    op.drop_column("users", "subject_identifier")
    op.drop_column("users", "alternative_emails")


def downgrade() -> None:
    """Re-add the columns as nullable (their state just before this drop).

    subject_identifier comes back without its old UNIQUE constraint (that was
    already dropped in 4c1e7a9b2f30). Both are nullable, so existing rows are
    valid; the original values are not recovered.
    """
    op.add_column(
        "users",
        sa.Column("subject_identifier", sa.String(), nullable=True),
    )
    op.add_column(
        "users",
        sa.Column(
            "alternative_emails",
            postgresql.ARRAY(sa.String()),
            nullable=True,
        ),
    )
