"""Subject + HTML body for the mentorship admission email.

Separate from ``recruiting/notification_email_copy.py`` because the audience
is: this is the first notification Purrf sends to someone outside the
company. The recruiting bodies are written for staff working a pipeline, and
their footer wording, their "you own this posting" framing and their habit of
naming the candidate in the third person all read wrong to the candidate.

Emails carry no links -- the backend holds no frontend base URL to build
one from -- so the body names the sidebar destination instead. "Personal
Dashboard" is the label verbatim from ``navItems`` in
``frontend/src/components/layout/Sidebar.jsx`` -- a reader who goes looking
for a menu with any other name finds nothing.

Both variants share a subject line so that someone admitted more than once
keeps one mail thread.
"""

_FOOTER = (
    "<p>This is an automated message from Purrf. Please do not reply "
    "directly to this email as this inbox is not monitored.</p>"
)

_SUBJECT = "Welcome to Circle Cat Mentorship! Your application has been approved"

_OPENING = (
    "<p>Thank you for applying to be a mentor at Circle Cat. We are thrilled "
    "to let you know that your application has been approved—welcome to the "
    "mentorship program!</p>"
)


def _greeting(display_name: str) -> str:
    """ "Dear {name}," or a bare "Hello," when the name resolved to nothing.

    Args:
        display_name (str): The recipient's display name, possibly "".

    Returns:
        str: The greeting paragraph. Never "Dear ," and never a placeholder
            standing in for a person -- an email addressed to "Dear A
            candidate," reads worse than one addressed to nobody.
    """
    if not display_name.strip():
        return "<p>Hello,</p>"
    return f"<p>Dear {display_name.strip()},</p>"


def _registration_form(round_name: str | None) -> str:
    """ "the mentorship registration form for 2026 Fall" -- or without the round.

    ``mentorship_round.name`` is non-nullable but nothing checks it for
    emptiness, and "for " with nothing after it would read as a bug in the
    email rather than a gap in the data.

    Args:
        round_name (str | None): The round's name, possibly blank.

    Returns:
        str: The noun phrase, ending in a full stop.
    """
    if round_name and round_name.strip():
        return f"complete the mentorship registration form for {round_name.strip()}."
    return "complete the mentorship registration form."


def mentor_admitted_with_round(
    display_name: str,
    round_name: str | None,
    deadline: str,
    matching_date: str,
) -> tuple[str, str]:
    """The admission email when a round is open for registration.

    Args:
        display_name (str): Who to greet, possibly "".
        round_name (str | None): The open round's name, possibly blank.
        deadline (str): The registration deadline, already rendered in the
            recipient's timezone with the zone named.
        matching_date (str): The expected matching date, already rendered.

    Returns:
        tuple[str, str]: Subject and HTML body.
    """
    return (
        _SUBJECT,
        f"{_greeting(display_name)}"
        f"{_OPENING}"
        "<p>There is just one final step before we can pair you with a "
        "mentee. Please log in to Purrf, go to your Personal Dashboard, and "
        f"{_registration_form(round_name)} This form helps us understand "
        "your preferences and expertise so we can find the best possible "
        "match for you. Please note that we won't be able to match you "
        "without it.</p>"
        "<p>Key Dates:</p>"
        "<ul>"
        f"<li>Registration Deadline: {deadline}</li>"
        f"<li>Matching Results: Expected on {matching_date}</li>"
        "</ul>"
        f"{_FOOTER}",
    )


def mentor_admitted_without_round(display_name: str) -> tuple[str, str]:
    """The admission email when no round is open yet.

    States no dates at all rather than a half-filled Key Dates block: this is
    also what a round with an unusable date falls back to, and a body missing
    one of its two dates reads as a mistake.

    The promise to follow up is kept by hand: nothing in Purrf notifies
    admitted mentors when a round opens, and nothing is meant to.

    Args:
        display_name (str): Who to greet, possibly "".

    Returns:
        tuple[str, str]: Subject and HTML body.
    """
    return (
        _SUBJECT,
        f"{_greeting(display_name)}"
        f"{_OPENING}"
        "<p>Registration for the upcoming round is not open just yet, but we "
        "will notify you as soon as it goes live. Once it opens, you'll need "
        "to complete a quick mentorship registration form on your Personal "
        "Dashboard. This will help us learn more about your topic "
        "preferences and ideal mentee match so we can pair you "
        "successfully.</p>"
        "<p>We will be in touch soon with the next steps!</p>"
        f"{_FOOTER}",
    )
