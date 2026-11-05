"""allow attendance on hand-logged meetings

Revision ID: 2941d8e9c8f3
Revises: fe4433f214dd
Create Date: 2026-10-31 03:40:22.656758

"""

from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "2941d8e9c8f3"
down_revision: Union[str, Sequence[str], None] = "fe4433f214dd"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# Autogenerate does not compare CHECK constraints, so this body is written
# against MentorshipMeetingEntity's _GOOGLE_ONLY_COLUMNS by hand.
_GOOGLE_ONLY = (
    "source = 'google' OR (meet_link IS NULL AND google_meeting_code IS NULL"
    " AND entry_points IS NULL AND last_sync_at IS NULL)"
)
_GOOGLE_ONLY_WITH_ATTENDANCE = (
    "source = 'google' OR (meet_link IS NULL AND google_meeting_code IS NULL"
    " AND entry_points IS NULL AND absent_user_id IS NULL"
    " AND late_user_ids IS NULL AND has_unknown_absent IS NULL"
    " AND has_unknown_late IS NULL AND has_insufficient_duration IS NULL"
    " AND last_sync_at IS NULL)"
)


def upgrade() -> None:
    """Upgrade schema."""
    op.drop_constraint("google_fields", "mentorship_meeting", type_="check")
    op.create_check_constraint("google_fields", "mentorship_meeting", _GOOGLE_ONLY)


def downgrade() -> None:
    """Downgrade schema."""
    # The old constraint refuses attendance on non-Google rows, so an admin's
    # marks on hand-logged meetings are dropped first.
    op.execute(
        """
        UPDATE mentorship_meeting
        SET absent_user_id = NULL, late_user_ids = NULL,
            has_unknown_absent = NULL, has_unknown_late = NULL,
            has_insufficient_duration = NULL
        WHERE source <> 'google'
        """
    )
    op.drop_constraint("google_fields", "mentorship_meeting", type_="check")
    op.create_check_constraint(
        "google_fields", "mentorship_meeting", _GOOGLE_ONLY_WITH_ATTENDANCE
    )
