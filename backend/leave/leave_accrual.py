"""Pure arithmetic behind the two leave accrual jobs.

Everything here is a function of its arguments alone: no database, no clock, no
Graph. "Today" is passed in, from
:func:`backend.leave.leave_clock.business_today`. The jobs that call these are
thin loops, which is deliberate -- every way this module can be wrong produces a
silently wrong number rather than an error, so the arithmetic is the part that
has to be pinned by tests.

Accrual is target-based, not incremental::

    owed now = target(today) - what the engine has already granted this year

That buys two properties worth protecting: 80h over 52 weeks does not divide
evenly, and week 52 closes the gap exactly; and a job run that never happened is
made up by the next one instead of being lost forever.

Both stop at 31 December. Week 52 is only reached once 364 days have elapsed --
31 December, or the 30th in a leap year -- and the weekly job runs on one fixed
weekday, so it lands there roughly one year in seven. Every other year the last
run of the year stops at week 51, and the reset on 1 January puts the remaining
1.54h out of reach: the catch-up property does not cross the year boundary.
Closing the old year out is the annual job's first step, before it applies the
carryover ceiling.

Both properties also depend on "already granted" being counted correctly, and
that count has two limits which are each easy to drop -- see
:func:`weekly_accrual_hours`.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal

WEEKS_PER_YEAR = 52

DAYS_PER_YEAR = 7 * WEEKS_PER_YEAR

HOURS_QUANTUM = Decimal("0.01")

NO_HOURS = Decimal("0.00")


@dataclass(frozen=True)
class LevelChange:
    """One change of annual entitlement, as the ledger recorded it.

    The hours on either side are recorded rather than looked up from the level,
    so a year can be recomputed later from the ledger alone: the cached profile
    only says what somebody is entitled to now.
    """

    effective_date: date
    annual_hours_before: int
    annual_hours_after: int


def format_hours(value: Decimal) -> str:
    """Writes an hour count down: fixed two decimals, never a float.

    Every hour figure that leaves this module -- a run's report, a wire
    response -- goes through here, so a balance reads the same wherever it is
    shown. Formatting a Decimal keeps the trailing zero that ``str`` would drop
    and never introduces the binary rounding a float would.
    """
    return f"{value:.2f}"


def accrual_start_date(year: int, hire_date: date) -> date:
    """Where the accrual clock starts for one person in one year.

    The year the system launches is not treated specially, and there is no
    go-live date in this maximum. The engine computes the whole year from 1
    January and pays the difference on its first run, which for someone already
    employed is most of a year in one entry. That is the intended behaviour: it
    makes this year's figure something the engine derives and can reproduce,
    rather than something an admin works out by hand.

    What is keyed in by hand at launch is the balance carried in from the
    previous year, and none of this year's accrual -- so there is nothing here
    to land on top of. Adding a go-live date back into this maximum without
    changing that convention at the same time turns a double payment into a
    missing one.

    Args:
        year: The year being accrued for.
        hire_date: Their Beijing hire date.

    Returns:
        The later of the year's start and their hire date.
    """
    return max(date(year, 1, 1), hire_date)


def weeks_passed(start_date: date, today: date) -> int:
    """Whole weeks between the start of accrual and today.

    Partial weeks do not count: a week is credited once seven full days have
    elapsed, so someone hired on the 28th of December finishes that year with
    nothing. The target-based formula makes that self-correcting rather than
    permanent -- the following January starts them at week zero anyway.

    Args:
        start_date: From :func:`accrual_start_date`.
        today: A Beijing date in the same year as ``start_date``.

    Returns:
        A count between 0 and 52. It cannot reach 53: the longest possible span
        is a leap year's 365 elapsed days, which floors to 52.
    """
    return max(0, (today - start_date).days // 7)


def accrual_target_hours(annual_hours: int, weeks: int) -> Decimal:
    """Everything this person should have been granted by ``weeks``.

    Rounded rather than truncated, and rounded on the target rather than on the
    weekly difference, so the series lands on the annual figure exactly at week
    52 instead of drifting a cent short. No target ever falls on a rounding tie.

    Args:
        annual_hours: Their level's annual entitlement. Zero is ordinary.
        weeks: From :func:`weeks_passed`.

    Returns:
        Hours to two decimal places.
    """
    return (Decimal(annual_hours) * weeks / WEEKS_PER_YEAR).quantize(
        HOURS_QUANTUM, ROUND_HALF_UP
    )


def weekly_accrual_hours(
    annual_hours: int,
    start_date: date,
    today: date,
    granted_this_year: Decimal,
    level_changes: Sequence[LevelChange] = (),
) -> Decimal:
    """What this run owes one person, or zero when it owes nothing.

    ``granted_this_year`` carries the two limits the whole engine rests on, and
    the caller supplies it, so this is where they are written down:

    * **Only ``weekly_accrual`` rows.** Manual adjustments, opening balances,
      exchange credits, deductions and carryover forfeits are all balance,
      not entitlement. Counting an opening balance here would cancel
      out the accrual it was supposed to sit alongside.
    * **Only rows dated inside the year of** ``today``. The target resets every
      January while the ledger keeps accumulating, so a sum taken across years
      compares this January's target against last year's full entitlement, goes
      negative, and pays nothing at all -- for the entire year, without raising
      anything. The following year the gap doubles.

    Never returns a negative number. A shortfall means the ledger already holds
    more than the target -- a level that went down, or a row somebody inserted
    by hand -- and clawing hours back out of an append-only ledger is not
    something a scheduled job should do unattended.

    Args:
        annual_hours: Their level's annual entitlement, as it stands now. Only
            read for somebody with no level change on record.
        start_date: From :func:`accrual_start_date`.
        today: The Beijing date this run is accruing for.
        granted_this_year: Sum of their ``weekly_accrual`` hours dated in the
            year of ``today``.
        level_changes: Every entitlement change on record for them, oldest
            first, including any dated after ``today``. Empty for almost
            everybody.

    Returns:
        Hours to write, or zero to write nothing.
    """
    owed = (
        _target_hours(annual_hours, start_date, today, level_changes)
        - granted_this_year
    )
    return owed if owed > NO_HOURS else NO_HOURS


def _target_hours(
    annual_hours: int,
    start_date: date,
    today: date,
    level_changes: Sequence[LevelChange],
) -> Decimal:
    """Everything this person should have been granted by ``today``.

    The credited days are the whole weeks since ``start_date``, as for anybody,
    and each is paid at the entitlement held on it. With no change on record
    that is :func:`accrual_target_hours`, since ``annual * 7w / 364`` is
    ``annual * w / 52``.

    Splitting by days rather than counting whole weeks on each side of a change
    is what keeps both edges: the days between the last run and the change are
    paid at the old rate, and a change does not restart the week count, so the
    year still ends on week 52.
    """
    weeks = weeks_passed(start_date, today)
    if not level_changes:
        return accrual_target_hours(annual_hours, weeks)
    end = start_date + timedelta(days=7 * weeks)
    boundaries = sorted({
        change.effective_date
        for change in level_changes
        if start_date < change.effective_date < end
    })
    day_hours = 0
    segment_start = start_date
    for segment_end in [*boundaries, end]:
        rate = _annual_hours_on(segment_start, annual_hours, level_changes)
        day_hours += rate * (segment_end - segment_start).days
        segment_start = segment_end
    return (Decimal(day_hours) / DAYS_PER_YEAR).quantize(HOURS_QUANTUM, ROUND_HALF_UP)


def _annual_hours_on(
    day: date, annual_hours: int, level_changes: Sequence[LevelChange]
) -> int:
    """The annual entitlement somebody held on ``day``.

    The latest change on or before the day says what it became. Failing that,
    the earliest change after it says what it was before -- which is what keeps
    a year being closed late from reading a promotion made after it ended.
    Only somebody with no change at all falls back to the current level.
    """
    held = [change for change in level_changes if change.effective_date <= day]
    if held:
        return held[-1].annual_hours_after
    later = [change for change in level_changes if change.effective_date > day]
    if later:
        return later[0].annual_hours_before
    return annual_hours


def carryover_forfeit_hours(balance: Decimal, cap: Decimal | None) -> Decimal:
    """How much of a year-end balance is cut, as a negative number.

    Only a positive overshoot is cut. A balance under the cap is untouched, and
    so is a negative one: people on a zero entitlement are expected to sit in
    the red, and the new year's accrual fills that in. Year end is not debt
    forgiveness.

    Cutting is not reversible. The ledger only ever grows, so raising the cap
    afterwards returns nothing and an admin has to key the hours back in
    one person at a time.

    Args:
        balance: Their whole ledger summed to December 31st.
        cap: The global carryover ceiling, or None for no ceiling.

    Returns:
        A negative number of hours, or zero to write nothing.
    """
    if cap is None or balance <= cap:
        return NO_HOURS
    return -(balance - cap)


def carryover_effective_date(today: date) -> date:
    """The date a forfeit row is stamped with.

    December 31st of the year being closed, not January 1st. The hours being
    cut are last year's leftovers and belong on last year's ledger; dated to
    the 1st they read as the new year opening by docking someone.

    Args:
        today: The Beijing date the annual job is running on.

    Returns:
        December 31st of the preceding year.
    """
    return date(today.year - 1, 12, 31)
