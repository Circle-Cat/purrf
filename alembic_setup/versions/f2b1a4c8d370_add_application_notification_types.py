"""add application notification types

Revision ID: f2b1a4c8d370
Revises: c9cfc7fcaf61
Create Date: 2026-07-30 00:00:00.000000

A posting's owners now get told when an application lands, with distinct
types for the three outcomes: one needing human review, one already
auto-rejected by screening or the blacklist, and one already auto-hired.
Autogenerate cannot see new enum values, so the ALTER TYPE statements are
written by hand.
"""

from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "f2b1a4c8d370"
down_revision: Union[str, Sequence[str], None] = "c9cfc7fcaf61"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add the three application-outcome values to notification_type_enum.

    Postgres allows ADD VALUE inside a transaction as long as the new value
    is not *used* in the same transaction; this migration only adds, so the
    default transactional behaviour is fine. IF NOT EXISTS keeps the
    migration idempotent if it is ever re-run against a partially migrated
    database.
    """
    for value in (
        "application_submitted",
        "application_auto_rejected",
        "application_auto_hired",
    ):
        op.execute(
            f"ALTER TYPE notification_type_enum ADD VALUE IF NOT EXISTS '{value}'"
        )


def downgrade() -> None:
    """No-op: Postgres cannot remove a value from an enum type.

    Undoing this would mean recreating notification_type_enum without the
    three values and rewriting every notification.type that references
    them -- destructive, and pointless because a surplus enum value is
    inert. Rows of the new types, if any exist, are the actual thing a
    rollback would have to deal with, and deleting user-visible
    notifications is not something a downgrade should do silently.
    """
