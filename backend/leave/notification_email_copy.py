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
