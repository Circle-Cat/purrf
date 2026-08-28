"""The leave policy constants, and the read-only view of them the page shows.

These live in code rather than in a table on purpose. The weekend never
changes with the year, and the carryover ceiling is irreversible: hours it cuts
on 1 January can only be handed back one person at a time by an admin. A pull
request and its history are a better gate for that than a number in an admin
form.

A pull request that changes ``MAX_CARRYOVER_HOURS`` has to carry the result of
"how many people would the next 1 January cut, and by how many hours" in its
description. Review is the only thing standing in front of an irreversible
operation here.
"""

from backend.dto.leave_holiday_dto import LeavePolicyDto
from backend.leave.employment_profile import ANNUAL_HOURS_BY_LEVEL

# datetime.weekday() numbering, where Monday is 0. The working week is Tuesday
# through Saturday.
WEEKEND_WEEKDAYS = (6, 0)

# Spelled out rather than derived from the numbers above: calendar.day_name and
# strftime both follow the process locale, and a server that came up under a
# non-English locale would render these into the interface in that language.
WEEKEND_LABELS = ("Sunday", "Monday")

HOURS_PER_DAY = 8

# None means the ceiling is not in force. It is not 0, which would mean not one
# hour may be carried over -- a different policy, and one that would cut
# everybody's balance to nothing every January.
MAX_CARRYOVER_HOURS: int | None = None

# The overdraft figure only warns; it never blocks a submission. An L1 has no
# annual entitlement at all, so blocking on it would leave them unable to take
# a single paid day.
MAX_OVERDRAFT_HOURS: int | None = None


def current_policy() -> LeavePolicyDto:
    """The constants as the calendar page reads them.

    The two ceilings are read here rather than captured at import, so a test
    can set one and see it arrive unchanged -- including 0, which must not
    collapse into "unset".

    Returns:
        The read-only policy view.
    """
    return LeavePolicyDto(
        weekend_weekdays=list(WEEKEND_WEEKDAYS),
        weekend_labels=list(WEEKEND_LABELS),
        hours_per_day=HOURS_PER_DAY,
        annual_hours_by_level=ANNUAL_HOURS_BY_LEVEL,
        max_carryover_hours=MAX_CARRYOVER_HOURS,
        max_overdraft_hours=MAX_OVERDRAFT_HOURS,
    )
