"""Pure arithmetic behind the two leave accrual jobs.

Everything here is a function of its arguments alone: no database, no clock
except :func:`business_today`, no Graph. The jobs that call these are thin
loops, which is deliberate -- every way this module can be wrong produces a
silently wrong number rather than an error, so the arithmetic is the part that
has to be pinned by tests.

Accrual is target-based, not incremental::

    owed now = target(today) - what the engine has already granted this year

That buys two properties worth protecting: 80h over 52 weeks does not divide
evenly, and the final week closes the gap exactly; and a job run that never
happened is made up by the next one instead of being lost forever.

Both properties depend on "already granted" being counted correctly, and it has
two limits that are each easy to drop -- see :func:`weekly_accrual_hours`.
"""

from datetime import date, datetime
from decimal import ROUND_HALF_UP, Decimal

from backend.leave.employment_profile import BUSINESS_TIMEZONE

WEEKS_PER_YEAR = 52

HOURS_QUANTUM = Decimal("0.01")

NO_HOURS = Decimal("0.00")


def business_today() -> date:
    """The current Beijing calendar day.

    The single source of "today" for anything leave-related. Business dates are
    Beijing civil days while the pods run on UTC, so between 00:00 and 08:00
    Beijing time the two disagree -- and the cron schedules in helm are written
    in UTC, which makes that window easy to land in.

    Returns:
        Today's date in Asia/Shanghai.
    """
    return datetime.now(BUSINESS_TIMEZONE).date()


def accrual_start_date(year: int, hire_date: date, system_start_date: date) -> date:
    """Where the accrual clock starts for one person in one year.

    The go-live date has to be in this maximum. Without it, the first run after
    launch pays out the whole year to date for everyone who was already
    employed -- and that stretch is already covered by the opening balance an
    admin keyed in by hand, so it lands twice. "We do not backfill" is enforced
    here, not by holding the job back.

    It expires on its own: from the following January the year start is always
    the later date.

    Args:
        year: The year being accrued for.
        hire_date: Their Beijing hire date.
        system_start_date: The global go-live date.

    Returns:
        The latest of the three.
    """
    return max(date(year, 1, 1), hire_date, system_start_date)


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
) -> Decimal:
    """What this run owes one person, or zero when it owes nothing.

    ``granted_this_year`` carries the two limits the whole engine rests on, and
    the caller supplies it, so this is where they are written down:

    * **Only ``weekly_accrual`` rows.** Manual adjustments, opening balances,
      exchange credits, deductions, reversals and carryover forfeits are all
      balance, not entitlement. Counting an opening balance here would cancel
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
        annual_hours: Their level's annual entitlement.
        start_date: From :func:`accrual_start_date`.
        today: The Beijing date this run is accruing for.
        granted_this_year: Sum of their ``weekly_accrual`` hours dated in the
            year of ``today``.

    Returns:
        Hours to write, or zero to write nothing.
    """
    target = accrual_target_hours(annual_hours, weeks_passed(start_date, today))
    owed = target - granted_this_year
    return owed if owed > NO_HOURS else NO_HOURS


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
