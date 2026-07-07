from datetime import date, timedelta


def compute_thaw(last_rejected_at: date, cooldown_days: int | None) -> date:
    """Compute the cold-freeze thaw date for a rejected application.

    Args:
        last_rejected_at (date): When the application was rejected.
        cooldown_days (int | None): Days before the applicant may reapply;
            None/unset behaves as 0 (reapply allowed immediately).

    Returns:
        date: The date on/after which the applicant is no longer tagged.
    """
    return last_rejected_at + timedelta(days=cooldown_days or 0)


def is_in_cooldown(now: date, thaw: date) -> bool:
    """Return True when ``now`` is before the thaw date."""
    return now < thaw
