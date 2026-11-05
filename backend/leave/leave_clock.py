"""The single source of "today" for the leave system.

Business dates -- a leave date, a holiday date, the day a ledger entry counts
for -- are Beijing civil days. The pods run on UTC and every cron schedule in
helm is written in UTC, so between 00:00 and 08:00 Beijing the two disagree,
and each way of getting it wrong fails silently: a past-date check lets one
extra day through, a ledger row lands a day off the unique index it is meant
to collide with, a 1 January job stamps 30 December.

Asia/Shanghai has no daylight saving. The offset is always +08:00, so nothing
here has to handle a transition.
"""

from datetime import date, datetime

from backend.leave.employment_profile import BUSINESS_TIMEZONE


def business_today() -> date:
    """Today, as a Beijing calendar day.

    Returns:
        The current date in Asia/Shanghai.
    """
    return datetime.now(BUSINESS_TIMEZONE).date()
