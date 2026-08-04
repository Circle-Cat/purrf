"""add notification email_sent_at

Revision ID: d3f81b0a6c47
Revises: 1677977acf62
Create Date: 2026-08-04 07:00:00.000000

Turns the notification table into the email outbox: NULL means "not yet
emailed", and NotificationEmailWorker claims those rows out of band instead
of the request path sending inline.

Every pre-existing row is stamped as already emailed. They were sent
inline at the time they were written, so leaving them NULL would make the
worker's first pass re-send the entire history of recruiting notifications
to every recipient at once.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "d3f81b0a6c47"
down_revision: Union[str, Sequence[str], None] = "1677977acf62"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add email_sent_at, backfill existing rows, index the unsent ones."""
    op.add_column(
        "notification",
        sa.Column("email_sent_at", sa.DateTime(timezone=True), nullable=True),
    )
    # Backfill before the worker can ever run against this schema. created_at
    # rather than now(): these rows were emailed when they were written, and
    # the stamp should say so.
    op.execute("UPDATE notification SET email_sent_at = created_at")
    # Partial index: the worker's claim query only ever looks for NULLs, and
    # that set is near-empty in the steady state, so the index stays tiny
    # while the table grows.
    op.create_index(
        "ix_notification_email_unsent",
        "notification",
        ["created_at"],
        unique=False,
        postgresql_where=sa.text("email_sent_at IS NULL"),
    )


def downgrade() -> None:
    """Drop the index and the column.

    Anything unsent at this moment is lost as an email; the in-app
    notification row itself survives, which is the authoritative copy.
    """
    op.drop_index("ix_notification_email_unsent", table_name="notification")
    op.drop_column("notification", "email_sent_at")
