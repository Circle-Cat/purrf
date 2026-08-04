"""drop users primary_email

Revision ID: a7c4e9f21b56
Revises: d253214bee6a
Create Date: 2026-07-17 11:05:00.000000

The user's contact address lives in user_emails (primary row, else the claim
seeded from their login), every read has been cut over, first logins seed a
claim for every sub type, and the global one-email-one-account invariant
moved onto uq_user_emails_email (d253214bee6a). Nothing reads or needs the
legacy column anymore, so it goes — along with its unique constraint, which
PostgreSQL drops with the column.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "a7c4e9f21b56"
down_revision: Union[str, Sequence[str], None] = "d253214bee6a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Drop the retired legacy column (and, with it, uq_users_primary_email)."""
    op.drop_column("users", "primary_email")


def downgrade() -> None:
    """Re-add the column as nullable and backfill it from user_emails.

    Nullable (the original was NOT NULL) because users created after the drop
    have no value to restore; the backfill recovers each user's contact
    address — primary row first, else their oldest claim. No unique
    constraint is recreated: uq_user_emails_email now owns that invariant.
    """
    op.add_column(
        "users",
        sa.Column("primary_email", sa.String(), nullable=True),
    )
    op.execute(
        sa.text(
            """
            UPDATE users u
            SET primary_email = ue.email
            FROM (
                SELECT DISTINCT ON (user_id) user_id, email
                FROM user_emails
                ORDER BY user_id, is_primary DESC, email_id ASC
            ) ue
            WHERE ue.user_id = u.user_id
            """
        )
    )
