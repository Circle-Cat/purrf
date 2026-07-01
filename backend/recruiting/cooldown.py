from datetime import date, timedelta
from backend.common.recruiting_enums import JobKind

# Mentorship program round-start months, recurring annually (Feb / May / Sep).
ROUND_START_MONTHS = (2, 5, 9)


def _month_first(d: date) -> date:
    """First day of the month containing ``d``."""
    return date(d.year, d.month, 1)


def _month_before(d: date) -> date:
    """First day of the month immediately before ``d``'s month."""
    if d.month == 1:
        return date(d.year - 1, 12, 1)
    return date(d.year, d.month - 1, 1)


def _first_round_start(after: date, inclusive: bool) -> date:
    """Earliest round-start (1st of a ROUND_START_MONTHS month) at/after ``after``.

    Args:
        after (date): The reference date.
        inclusive (bool): When True a round-start equal to ``after``'s month
            counts; when False only strictly-later starts count.

    Returns:
        date: The first day of the qualifying round-start month.
    """
    floor = _month_first(after)
    for year in (after.year, after.year + 1):
        for month in ROUND_START_MONTHS:
            candidate = date(year, month, 1)
            if (candidate >= floor) if inclusive else (candidate > floor):
                return candidate
    raise AssertionError("unreachable: a round start always exists within a year")


def compute_thaw(
    kind: JobKind,
    application_date: date,
    last_rejected_at: date,
    cooldown_days: int | None,
) -> date:
    """Compute the cold-freeze thaw date for a rejected application.

    Activity (mentorship) postings thaw one month before the round that follows
    the round the applicant applied for. Other postings thaw a fixed number of
    days after the rejection.

    Args:
        kind (JobKind): The posting kind.
        application_date (date): When the (rejected) application was submitted.
        last_rejected_at (date): When it was rejected.
        cooldown_days (int | None): Fixed window for non-activity postings.

    Returns:
        date: The date on/after which the applicant is no longer tagged.
    """
    if kind == JobKind.ACTIVITY:
        target = _first_round_start(application_date, inclusive=True)
        following = _first_round_start(target, inclusive=False)
        return _month_before(following)
    return last_rejected_at + timedelta(days=cooldown_days or 0)


def is_in_cooldown(now: date, thaw: date) -> bool:
    """Return True when ``now`` is before the thaw date."""
    return now < thaw
