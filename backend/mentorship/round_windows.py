"""The windows a mentorship round's dates open and close.

Each rule is defined here once, so the dashboard, the round list and the
endpoints that accept writes all agree, and all on the server's clock.
"""

from datetime import datetime, timedelta
from typing import NamedTuple

from dateutil.relativedelta import relativedelta

from backend.common.mentorship_enums import RoundStatus
from backend.entity.mentorship_round_entity import MentorshipRoundEntity

# Logging stays open this long past the meetings deadline, so a meeting held
# right up against it can still be recorded.
MEETING_LOG_GRACE = timedelta(days=1)


class FeedbackWindow(NamedTuple):
    """When a round's program feedback can be written. Either bound may be
    None, meaning unbounded on that side."""

    opens_at: datetime | None
    closes_at: datetime | None


def round_status(r: MentorshipRoundEntity, now: datetime) -> RoundStatus | None:
    """Where a round's meeting window stands at ``now``.

    The window opens at ``match_notification_at`` (``promotion_start_at``
    when a round has none) and closes at ``meetings_completion_deadline_at``,
    both inclusive. A round missing the bound a status needs has none.

    Args:
        r (MentorshipRoundEntity): The round.
        now (datetime): The aware instant to evaluate at.

    Returns:
        RoundStatus | None: The round's status, or None.
    """
    start = r.match_notification_at or r.promotion_start_at
    end = r.meetings_completion_deadline_at
    if start and end and start <= now <= end:
        return RoundStatus.ACTIVE
    if start and now < start:
        return RoundStatus.UPCOMING
    if end and now > end:
        return RoundStatus.COMPLETED
    return None


def feedback_window(r: MentorshipRoundEntity) -> FeedbackWindow:
    """The span in which a round's program feedback can be written.

    It opens at ``meeting_log_reminder_at``, halfway through the round, so
    people can write while the round is still fresh. ``feedback_start_at`` is
    only the day the feedback email goes out; people may answer before it.
    It closes at ``feedback_deadline_at``. Both are optional in the round
    form, so each falls back to a month either side of the meetings deadline.
    A round with none of these dates has no bound on that side, so a
    half-filled timeline cannot lock anyone out.

    Args:
        r (MentorshipRoundEntity): The round.

    Returns:
        FeedbackWindow: The opening and closing instants, both inclusive.
    """
    end = r.meetings_completion_deadline_at
    opens_at = r.meeting_log_reminder_at or (
        end - relativedelta(months=1) if end else None
    )
    closes_at = r.feedback_deadline_at or (
        end + relativedelta(months=1) if end else None
    )
    return FeedbackWindow(opens_at=opens_at, closes_at=closes_at)


def is_feedback_open(r: MentorshipRoundEntity, now: datetime) -> bool:
    """Whether a round's feedback window has opened by ``now``.

    Past its close the window stays open for reading; see
    ``is_feedback_editable`` for writing.

    Args:
        r (MentorshipRoundEntity): The round.
        now (datetime): The aware instant to evaluate at.

    Returns:
        bool: True once the window has opened. False for a round with no
            dates to open it from.
    """
    opens_at = feedback_window(r).opens_at
    return opens_at is not None and now >= opens_at


def is_feedback_editable(r: MentorshipRoundEntity, now: datetime) -> bool:
    """Whether feedback for a round can be written at ``now``.

    Args:
        r (MentorshipRoundEntity): The round.
        now (datetime): The aware instant to evaluate at.

    Returns:
        bool: True inside the window, bounds included; a missing bound does
            not restrict.
    """
    opens_at, closes_at = feedback_window(r)
    return (opens_at is None or now >= opens_at) and (
        closes_at is None or now <= closes_at
    )


def meeting_log_closes_at(r: MentorshipRoundEntity) -> datetime | None:
    """The last instant a meeting can be logged for a round.

    Args:
        r (MentorshipRoundEntity): The round.

    Returns:
        datetime | None: The meetings deadline plus the grace period, or None
            when the round has no meetings deadline and logging is unbounded.
    """
    end = r.meetings_completion_deadline_at
    return end + MEETING_LOG_GRACE if end else None


def is_meeting_log_open(r: MentorshipRoundEntity, now: datetime) -> bool:
    """Whether a meeting can be logged for a round at ``now``.

    Args:
        r (MentorshipRoundEntity): The round.
        now (datetime): The aware instant to evaluate at.

    Returns:
        bool: True up to and including ``meeting_log_closes_at``.
    """
    closes_at = meeting_log_closes_at(r)
    return closes_at is None or now <= closes_at
