"""Subject + HTML body for the leave request emails.

Emails carry no links -- the backend holds no frontend base URL to build one
from -- so the body names where to go instead: "Time off" is the card's title
on the Personal Dashboard, and "Approvals" is the button on it that a manager
decides from.

Everything a person wrote (the employee's reason, the manager's comment) and
every name is HTML-escaped before it reaches a body. Nothing person-written
reaches a subject.
"""

import html

_FOOTER = (
    "<p>This is an automated message from Purrf. Please do not reply "
    "directly to this email as this inbox is not monitored.</p>"
)

_TYPE_LABELS = {
    "paid": "paid leave",
    "sick": "sick leave",
    "exchange": "a holiday exchange",
}


def _what(leave_type: str | None) -> str:
    return _TYPE_LABELS.get(leave_type or "", "leave")


def _when(start_date: str | None, end_date: str | None) -> str:
    if not start_date:
        return ""
    if not end_date or end_date == start_date:
        return f"on {start_date}"
    return f"from {start_date} to {end_date}"


def _quoted(label: str, text: str | None) -> str:
    text = (text or "").strip()
    return f"<p>{label}: {html.escape(text)}</p>" if text else ""


def request_submitted(
    employee: str,
    leave_type: str | None,
    start_date: str | None,
    end_date: str | None,
    hours: str | None,
    reason: str | None,
) -> tuple[str, str]:
    """The email a manager gets when a request is filed with them.

    Args:
        employee (str): Who filed it, already HTML-escaped.
        leave_type (str | None): paid, sick or exchange.
        start_date (str | None): First day, ISO.
        end_date (str | None): Last day, ISO.
        hours (str | None): The hours it covers.
        reason (str | None): The employee's reason.

    Returns:
        tuple[str, str]: Subject and HTML body.
    """
    covers = f" ({html.escape(hours)} hours)" if hours else ""
    return (
        "A leave request is waiting for your decision",
        f"<p>{employee} asked for {_what(leave_type)} "
        f"{_when(start_date, end_date)}{covers}.</p>"
        + _quoted("Their reason", reason)
        + "<p>Open Approvals on the Time off card in Purrf to approve or "
        "reject it.</p>" + _FOOTER,
    )


def request_decided(
    manager: str,
    decision: str,
    leave_type: str | None,
    start_date: str | None,
    end_date: str | None,
    comment: str | None,
) -> tuple[str, str]:
    """The email an employee gets when their manager decides their request.

    Args:
        manager (str): Who decided it, already HTML-escaped.
        decision (str): "approved" or "rejected".
        leave_type (str | None): paid, sick or exchange.
        start_date (str | None): First day, ISO.
        end_date (str | None): Last day, ISO.
        comment (str | None): The manager's reason, required to reject.

    Returns:
        tuple[str, str]: Subject and HTML body.
    """
    outcome = "approved" if decision == "approved" else "rejected"
    return (
        f"Your leave request was {outcome}",
        f"<p>{manager} {outcome} your request for {_what(leave_type)} "
        f"{_when(start_date, end_date)}.</p>"
        + _quoted("Their reason", comment)
        + "<p>Your requests are on the Time off card in Purrf.</p>"
        + _FOOTER,
    )


def request_withdrawn(
    employee: str,
    leave_type: str | None,
    start_date: str | None,
    end_date: str | None,
) -> tuple[str, str]:
    """The email a manager gets when a request waiting on them is withdrawn.

    Args:
        employee (str): Who withdrew it, already HTML-escaped.
        leave_type (str | None): paid, sick or exchange.
        start_date (str | None): First day, ISO.
        end_date (str | None): Last day, ISO.

    Returns:
        tuple[str, str]: Subject and HTML body.
    """
    return (
        "A leave request was withdrawn",
        f"<p>{employee} withdrew their request for {_what(leave_type)} "
        f"{_when(start_date, end_date)}. There is nothing left for you to "
        "do.</p>" + _FOOTER,
    )


def sick_leave_auto_approved(
    employee: str,
    start_date: str | None,
    end_date: str | None,
    hours: str | None,
    reason: str | None,
) -> tuple[str, str]:
    """The email a manager gets when sick leave filed with them is approved on
    submission, which it is up to three days.

    Args:
        employee (str): Who is off sick, already HTML-escaped.
        start_date (str | None): First day, ISO.
        end_date (str | None): Last day, ISO.
        hours (str | None): The hours it covers.
        reason (str | None): The employee's reason.

    Returns:
        tuple[str, str]: Subject and HTML body.
    """
    covers = f" ({html.escape(hours)} hours)" if hours else ""
    return (
        "Sick leave was approved automatically",
        f"<p>{employee} took sick leave {_when(start_date, end_date)}{covers}. "
        "Sick leave of three days or less is approved automatically, so there "
        "is nothing for you to decide.</p>"
        + _quoted("Their reason", reason)
        + "<p>It is under Decided in Approvals on the Time off card in "
        "Purrf.</p>" + _FOOTER,
    )


def _signed(hours: str | None) -> str:
    """Puts a plus on a gain; a loss already carries its minus. The sign is
    the point of an adjustment."""
    hours = (hours or "").strip()
    if not hours or hours.startswith("-"):
        return hours
    return f"+{hours}"


def balance_adjusted(
    admin: str,
    hours: str | None,
    effective_date: str | None,
    note: str | None,
    balance_hours: str | None,
) -> tuple[str, str]:
    """The email an employee gets when an admin corrects their balance,
    which is also how an opening balance arrives.

    Args:
        admin (str): Who made the correction, already HTML-escaped.
        hours (str | None): The signed change, e.g. "8.00" or "-16.00".
        effective_date (str | None): The day it counts from, ISO.
        note (str | None): The admin's reason, always given.
        balance_hours (str | None): The balance right after the correction.

    Returns:
        tuple[str, str]: Subject and HTML body.
    """
    dated = f", counted from {html.escape(effective_date)}" if effective_date else ""
    now = (
        f"<p>Your balance is now {html.escape(balance_hours)} hours.</p>"
        if balance_hours
        else ""
    )
    return (
        "Your leave balance was adjusted",
        f"<p>{admin} adjusted your leave balance by "
        f"{html.escape(_signed(hours))} hours{dated}.</p>"
        + _quoted("Their note", note)
        + now
        + "<p>Every change to your balance is listed in your balance history "
        "on the Time off card in Purrf.</p>" + _FOOTER,
    )
