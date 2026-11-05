"""move round timeline into columns

Revision ID: 9aebcd77b2b4
Revises: 24cf994c2693
Create Date: 2026-09-24 00:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = "9aebcd77b2b4"
down_revision: Union[str, Sequence[str], None] = "24cf994c2693"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


COLUMNS = (
    "promotion_start_at",
    "mentor_application_deadline_at",
    "mentee_application_deadline_at",
    "onboarding_notification_at",
    "onboarding_deadline_at",
    "match_notification_at",
    "first_meeting_deadline_at",
    "meeting_log_reminder_at",
    "meetings_completion_deadline_at",
    "feedback_start_at",
    "feedback_deadline_at",
)

# Each column's JSONB keys, first match wins. first_meeting_deadline_at has
# none: the matching_completed_at key held the first-contact deadline on
# rounds made with the form and the real matching date on imported ones, and
# the two cannot be told apart.
SOURCE_KEYS = {
    "promotion_start_at": ("promotion_start_at",),
    "mentor_application_deadline_at": (
        "mentor_application_deadline_at",
        "application_deadline_at",
    ),
    "mentee_application_deadline_at": (
        "mentee_application_deadline_at",
        "application_deadline_at",
    ),
    "onboarding_notification_at": (
        "onboarding_notification_at",
        "training_notification_at",
    ),
    "onboarding_deadline_at": ("onboarding_deadline_at", "training_deadline_at"),
    "match_notification_at": ("match_notification_at",),
    "meeting_log_reminder_at": ("meeting_log_reminder_at",),
    "meetings_completion_deadline_at": ("meetings_completion_deadline_at",),
    "feedback_start_at": ("feedback_start_at",),
    "feedback_deadline_at": ("feedback_deadline_at",),
}


def _parse(key: str) -> str:
    """SQL turning one JSONB timeline value into a timestamptz.

    Three shapes occur. A bare YYYY-MM-DD (the one-off import) becomes 23:59:59
    Pacific on that day, the rule the round form applies (toPTEndOfDay). A
    timestamp with an offset or Z (the form) is taken as is. A timestamp with
    no offset is read as UTC, as participation_service always did. The bare
    date is tested first because its trailing "-DD" would otherwise pass for
    an offset.
    """
    value = f"NULLIF(description ->> '{key}', '')"
    return (
        f"CASE"
        f" WHEN {value} ~ '^\\d{{4}}-\\d{{2}}-\\d{{2}}$'"
        f" THEN ({value}::date + time '23:59:59') AT TIME ZONE 'America/Los_Angeles'"
        f" WHEN {value} ~ '(Z|[+-]\\d{{2}}(:?\\d{{2}})?)$'"
        f" THEN {value}::timestamptz"
        f" ELSE {value}::timestamp AT TIME ZONE 'UTC'"
        f" END"
    )


def upgrade() -> None:
    """Copy the timeline out of ``description`` into one column per date.

    ``description`` itself is left untouched: backend/backfill/ still reads it.

    ``onboarding_deadline_at`` closes registration, so every row needs one.
    A round that never had a training deadline gets mentee application
    deadline + 2 days, the date registration used to derive from it. A round
    with neither aborts the whole migration with its id named.
    """
    for column in COLUMNS:
        op.add_column(
            "mentorship_round",
            sa.Column(column, sa.DateTime(timezone=True), nullable=True),
        )

    assignments = ",\n    ".join(
        f"{column} = COALESCE({', '.join(_parse(key) for key in keys)})"
        for column, keys in SOURCE_KEYS.items()
    )
    op.execute(
        f"UPDATE mentorship_round SET\n    {assignments}\nWHERE description IS NOT NULL"
    )
    op.execute(
        "UPDATE mentorship_round"
        " SET onboarding_deadline_at = mentee_application_deadline_at + interval '2 days'"
        " WHERE onboarding_deadline_at IS NULL"
    )
    op.execute(
        """
        DO $$
        DECLARE missing text;
        BEGIN
            SELECT string_agg(round_id::text, ', ' ORDER BY round_id) INTO missing
            FROM mentorship_round WHERE onboarding_deadline_at IS NULL;
            IF missing IS NOT NULL THEN
                RAISE EXCEPTION
                    'mentorship_round % have no onboarding, training or mentee '
                    'application deadline to derive onboarding_deadline_at from',
                    missing;
            END IF;
        END $$;
        """
    )
    op.alter_column("mentorship_round", "onboarding_deadline_at", nullable=False)


def downgrade() -> None:
    """Write the columns back into ``description``, then drop them.

    Edits made after the upgrade live only in the columns, so they are merged
    back under the keys the previous code reads (training_* for onboarding_*)
    before the columns go. first_meeting_deadline_at had no key and is lost.
    """
    back = {
        column: column.replace("onboarding_", "training_")
        for column in COLUMNS
        if column != "first_meeting_deadline_at"
    }
    # A timestamptz becomes an ISO 8601 string with its offset in jsonb.
    pairs = ", ".join(f"'{key}', {column}" for column, key in back.items())
    op.execute(
        "UPDATE mentorship_round SET description = "
        f"COALESCE(description, '{{}}'::jsonb) || jsonb_strip_nulls(jsonb_build_object({pairs}))"
    )
    for column in reversed(COLUMNS):
        op.drop_column("mentorship_round", column)
