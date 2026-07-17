"""make user_emails email globally unique

Revision ID: d253214bee6a
Revises: cbfb424b9abb
Create Date: 2026-07-17 09:22:14.659051

An address belongs to at most one account, confirmed or not. Until now that
one-email-one-account invariant lived on ``users.primary_email``'s unique
constraint (and, for confirmed rows only, in application-level checks); this
moves it onto ``user_emails`` itself so the legacy column can be retired.
The unique constraint also takes over the concurrent first-login race guard:
two simultaneous first logins with the same address now collide on the seeded
claim row instead of on ``users.primary_email``.

Pre-existing duplicate claims (the same address held by several accounts,
which the old rules allowed as long as at most one was confirmed) are
resolved before the constraint is created: per address, a confirmed row wins
over an unconfirmed one, a primary over a non-primary, and the oldest row
(lowest email_id) breaks ties; every other row is deleted. The ``downgrade``
restores the non-unique index but cannot resurrect the deleted rows.

The redundant-looking ``uq_user_emails_user_id_email`` stays: its
(user_id, email) btree doubles as the index for user_id lookups. The plain
``user_emails_email_idx`` is dropped — the unique constraint's index serves
email lookups.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "d253214bee6a"
down_revision: Union[str, Sequence[str], None] = "cbfb424b9abb"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Per address keep the best claim (confirmed > primary > oldest) and drop
    # the rest, so the unique constraint below can be created.
    op.execute(
        sa.text(
            """
            DELETE FROM user_emails ue
            USING (
                SELECT
                    email_id,
                    row_number() OVER (
                        PARTITION BY email
                        ORDER BY
                            otp_confirmed DESC,
                            is_primary DESC,
                            email_id ASC
                    ) AS rn
                FROM user_emails
            ) ranked
            WHERE ue.email_id = ranked.email_id
              AND ranked.rn > 1
            """
        )
    )
    op.drop_index(op.f("user_emails_email_idx"), table_name="user_emails")
    op.create_unique_constraint("uq_user_emails_email", "user_emails", ["email"])
    # With uq_user_emails_email owning the one-email-one-account invariant,
    # relax the legacy users.primary_email column (nullable, non-unique) so
    # the follow-up PR that stops writing it runs against this same schema;
    # it is dropped entirely once every read is cut over.
    op.execute(
        sa.text("ALTER TABLE users DROP CONSTRAINT IF EXISTS uq_users_primary_email")
    )
    op.alter_column("users", "primary_email", nullable=True)


def downgrade() -> None:
    """Downgrade schema. Rows deleted by the upgrade dedupe are not restored.

    users.primary_email stays nullable and non-unique: NULLs written while
    upgraded cannot satisfy the old NOT NULL/unique shape.
    """
    op.drop_constraint("uq_user_emails_email", "user_emails", type_="unique")
    op.create_index(
        op.f("user_emails_email_idx"), "user_emails", ["email"], unique=False
    )
