"""Subject + HTML body for the mentorship emails.

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

Two audiences now live here. The admission bodies below are written for
someone outside the company; ``matching_run_*`` is written for the
administrator who started a run, and departs from the rules in two ways that
the audience earns: the round's name reaches the subject, because results from
two different rounds threading together is worse than an administrator-written
string in a header, and no destination is named because there is no screen to
review a result on yet.

Both admission variants share a subject line so that someone admitted more
than once keeps one mail thread. It is a constant, so nothing person-written reaches
a subject here; the two values that do reach a body -- the recipient's own
name and the round's name -- are HTML-escaped, the same rule the recruiting
copy and ``user_identity/notification_renderers`` follow.
"""

import html

from backend.common.mentorship_email_enums import (
    MentorshipEmailFailure,
    MentorshipEmailRecipientResult,
    MentorshipEmailStage,
)

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
    return f"<p>Dear {html.escape(display_name.strip())},</p>"


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
        return (
            "complete the mentorship registration form for "
            f"{html.escape(round_name.strip())}."
        )
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


def _run_round(round_name: str | None) -> str:
    """ "for Mentorship 2026 Fall", or nothing when the round has no usable name."""
    if round_name and round_name.strip():
        return f" for {html.escape(round_name.strip())}"
    return ""


def _minutes(seconds: int | None) -> str:
    """ "and took 48 minutes", or nothing when the timestamps did not parse.

    A run that reports impossible timestamps should drop the sentence rather
    than tell an administrator it finished in -3 minutes.
    """
    if seconds is None or seconds <= 0:
        return ""
    minutes = max(1, round(seconds / 60))
    return f" and took {minutes} minute{'' if minutes == 1 else 's'}"


def matching_run_succeeded(
    round_name: str | None,
    mentee_count: int,
    mentor_count: int,
    seconds: int | None,
) -> tuple[str, str]:
    """The email an administrator gets when their run produced results.

    Args:
        round_name (str | None): The round's name, possibly blank.
        mentee_count (int): Mentees the run scored.
        mentor_count (int): Mentors they were scored against.
        seconds (int | None): How long it took, if the timestamps parsed.

    Returns:
        tuple[str, str]: Subject and HTML body.
    """
    round_phrase = _run_round(round_name)
    return (
        f"Mentorship matching has finished{round_phrase}",
        "<p>Hello,</p>"
        f"<p>The matching run you started{round_phrase} has finished.</p>"
        f"<p>It scored {mentee_count} mentees against {mentor_count} mentors"
        f"{_minutes(seconds)}.</p>"
        # Said plainly because the email arrives an hour after the button was
        # pressed, which is long enough to assume the pairings are live.
        "<p>Nothing has been published yet. No pairing exists until somebody "
        "reviews these results and applies them.</p>" + _FOOTER,
    )


def matching_run_failed(round_name: str | None, error: str | None) -> tuple[str, str]:
    """The email an administrator gets when their run stopped early.

    The design only called for a completion notice, but somebody who waited an
    hour needs the failure more than the success.

    Args:
        round_name (str | None): The round's name, possibly blank.
        error (str | None): What the matcher reported, if anything.

    Returns:
        tuple[str, str]: Subject and HTML body.
    """
    round_phrase = _run_round(round_name)
    reported = (
        f"<p><code>{html.escape(error.strip())}</code></p>"
        if error and error.strip()
        else "<p>It did not say why.</p>"
    )
    return (
        f"Mentorship matching did not finish{round_phrase}",
        "<p>Hello,</p>"
        f"<p>The matching run you started{round_phrase} stopped before it "
        "produced results.</p>" + reported + "<p>Nothing was changed. Starting "
        "a new run for this round is safe.</p>" + _FOOTER,
    )


def _approval_ask(
    action: str, round_name: str | None, person_name: str | None = None
) -> str:
    """What a mentorship approval asks for, as the object of "to ...", with
    the round and the person HTML-escaped."""
    name = (round_name or "").strip()
    in_round = f" in {html.escape(name)}" if name else ""
    if action == "exempt_matching":
        person = html.escape((person_name or "").strip() or "someone")
        return f"exempt {person} from the matching history check{in_round}"
    if action == "withdraw_participant":
        person = html.escape((person_name or "").strip() or "someone")
        return f"withdraw {person} from {html.escape(name) if name else 'their round'}"
    if action == "mark_no_show":
        person = html.escape((person_name or "").strip() or "someone")
        return f"mark {person} as a no show{in_round}"
    if action == "mark_red_flag":
        person = html.escape((person_name or "").strip() or "someone")
        return f"raise a red flag on {person}{in_round}"
    if action == "end_pair":
        pair = html.escape((person_name or "").strip() or "a pair")
        return f"end the pair of {pair}{in_round}"
    if action == "publish_matching":
        return (
            f"publish the matching result for {html.escape(name)}"
            if name
            else ("publish the matching result")
        )
    return "make a change"


def _approval_subject_round(round_name: str | None) -> str:
    name = (round_name or "").strip()
    return f": {name}" if name else ""


def _quoted(label: str, text: str | None) -> str:
    text = (text or "").strip()
    return f"<p>{label}: {html.escape(text)}</p>" if text else ""


_APPROVAL_WHERE = "<p>Open Mentorship Management in Purrf to review it.</p>"


def approval_requested(
    action: str,
    round_name: str | None,
    actor: str,
    reason: str | None,
    person_name: str | None = None,
) -> tuple[str, str]:
    """The email a reviewer gets when a mentorship request names them.

    Args:
        action (str): What is asked for.
        round_name (str | None): The round's name, possibly blank.
        actor (str): Who asked, already HTML-escaped.
        reason (str | None): Their reason.
        person_name (str | None): Who the request is about, for an exemption, a withdrawal or a mark.

    Returns:
        tuple[str, str]: Subject and HTML body.
    """
    return (
        f"Mentorship approval requested{_approval_subject_round(round_name)}",
        "<p>Hello,</p>"
        f"<p>{actor} asked you to approve a request to "
        f"{_approval_ask(action, round_name, person_name)}. It is waiting on your "
        "decision.</p>" + _quoted("Their reason", reason) + _APPROVAL_WHERE + _FOOTER,
    )


def approval_reassigned(
    action: str,
    round_name: str | None,
    actor: str,
    reason: str | None,
    person_name: str | None = None,
) -> tuple[str, str]:
    """The email a reviewer gets when a request is handed to them.

    Says a handover happened, since the request may have been waiting on
    somebody else for a while.

    Args:
        action (str): What is asked for.
        round_name (str | None): The round's name, possibly blank.
        actor (str): Who handed it over, already HTML-escaped.
        reason (str | None): The raiser's reason.
        person_name (str | None): Who the request is about, for an exemption, a withdrawal or a mark.

    Returns:
        tuple[str, str]: Subject and HTML body.
    """
    return (
        f"Mentorship approval reassigned to you{_approval_subject_round(round_name)}",
        "<p>Hello,</p>"
        f"<p>{actor} moved a request to "
        f"{_approval_ask(action, round_name, person_name)} to "
        "you. It is waiting on your decision.</p>"
        + _quoted("The reason given", reason)
        + _APPROVAL_WHERE
        + _FOOTER,
    )


def approval_decided(
    action: str,
    round_name: str | None,
    actor: str,
    decision: str,
    comment: str | None,
    person_name: str | None = None,
) -> tuple[str, str]:
    """The email the other side gets when a request is closed: the raiser
    for an approval or a rejection, the reviewer for a withdrawal.

    Args:
        action (str): What was asked for.
        round_name (str | None): The round's name, possibly blank.
        actor (str): Who closed it, already HTML-escaped.
        decision (str): approved, rejected or withdrawn.
        comment (str | None): The reviewer's reason, for a rejection.
        person_name (str | None): Who the request is about, for an exemption, a withdrawal or a mark.

    Returns:
        tuple[str, str]: Subject and HTML body.
    """
    ask = _approval_ask(action, round_name, person_name)
    subject_round = _approval_subject_round(round_name)
    if decision == "withdrawn":
        return (
            f"Mentorship approval withdrawn{subject_round}",
            "<p>Hello,</p>"
            f"<p>{actor} withdrew their request to {ask}. Nothing is waiting "
            "on you any more.</p>" + _FOOTER,
        )
    if decision == "rejected":
        return (
            f"Mentorship approval rejected{subject_round}",
            "<p>Hello,</p>"
            f"<p>{actor} rejected your request to {ask}.</p>"
            + _quoted("Their reason", comment)
            + "<p>Open Mentorship Management in Purrf to make changes and ask "
            "again.</p>" + _FOOTER,
        )
    return (
        f"Mentorship approval approved{subject_round}",
        "<p>Hello,</p>"
        f"<p>{actor} approved your request to {ask}. It has been done.</p>" + _FOOTER,
    )


_SEND_STAGE_LABELS = {
    MentorshipEmailStage.ROUND_RECRUITMENT: "New round invitation",
    MentorshipEmailStage.ADMISSION: "Admission & onboarding",
    MentorshipEmailStage.ONBOARDING_REMINDER: "Onboarding reminder",
    MentorshipEmailStage.MATCH_RESULT: "Match result",
    MentorshipEmailStage.FIRST_CONTACT_REMINDER: "First contact reminder",
    MentorshipEmailStage.MENTOR_CHECK_IN: "Mentor check-in",
    MentorshipEmailStage.MIDTERM_REMINDER: "Mid-term reminder",
    MentorshipEmailStage.FINAL_FOLLOWUP: "Final follow-up",
    MentorshipEmailStage.FEEDBACK_INVITE: "Feedback invitation",
}

_SEND_FAILURES = {
    MentorshipEmailFailure.DRAFT_CHANGED: "Purrf's copy of the draft was changed in Kit after you confirmed it.",
    MentorshipEmailFailure.DRAFT_TAMPERED: (
        "The recipients or sender of Purrf's copy were changed in Kit."
    ),
    MentorshipEmailFailure.DRAFT_GONE: "Purrf's copy of the draft was deleted in Kit.",
    MentorshipEmailFailure.COUNT_MISMATCH: (
        "Kit counted a different number of recipients than Purrf handed to it."
    ),
    MentorshipEmailFailure.TIME_PASSED: (
        "The send time passed while people were being added to Kit."
    ),
    MentorshipEmailFailure.NO_RECIPIENTS: (
        "Nobody could receive it: everyone selected was unsubscribed, bounced, "
        "had no email address or could not be added to Kit."
    ),
    MentorshipEmailFailure.KIT_ERROR: "Something went wrong talking to Kit.",
}

_SEND_WHERE = "<p>Open Mentorship Management in Purrf to see the Participants card.</p>"


def send_failure_reason(failure_code: str | None) -> str:
    """Why a confirmed send never reached Kit's schedule, in one sentence."""
    return _SEND_FAILURES.get(failure_code, "Preparing it stopped unexpectedly.")


def send_stage_label(stage: str | None) -> str:
    """The stage as the send dialog names it, or the raw value if unknown."""
    return _SEND_STAGE_LABELS.get(stage, stage or "")


def unreached_reason(result: str | None, failure_reason: str | None) -> str:
    """Why one person was not handed to Kit, in a few plain words."""
    if result == MentorshipEmailRecipientResult.UNSUBSCRIBED:
        if failure_reason == "complained":
            return "marked an earlier email as spam"
        if failure_reason == "inactive":
            return "inactive in Kit"
        return "unsubscribed"
    if result == MentorshipEmailRecipientResult.BOUNCED:
        return "email bounced"
    reason = failure_reason or ""
    if reason == "no_email":
        return "no email address"
    if reason == "kit_not_found":
        return "could not be added to Kit (Kit could not find them)"
    if reason.startswith("kit_state_"):
        return f"could not be added to Kit (Kit status: {reason[10:]})"
    if reason.startswith("kit_") and reason[4:].isdigit():
        return f"could not be added to Kit (Kit error {reason[4:]})"
    return "could not be added to Kit" + (f" ({reason})" if reason else "")


def _send_subject(prefix: str, round_name: str | None, stage: str | None) -> str:
    parts = [p for p in (send_stage_label(stage), (round_name or "").strip()) if p]
    return f"{prefix}: {' · '.join(parts)}" if parts else prefix


def _send_facts(round_name: str | None, stage: str | None, subject: str | None):
    rows = [
        ("Round", (round_name or "").strip()),
        ("Stage", send_stage_label(stage)),
        ("Kit draft", (subject or "").strip()),
    ]
    return [f"<li>{label}: {html.escape(value)}</li>" for label, value in rows if value]


def email_send_scheduled(
    round_name: str | None,
    stage: str | None,
    subject: str | None,
    send_at: str | None,
    handed: int,
    not_handed: list[tuple[str, str]],
) -> tuple[str, str]:
    """The email the admin who created a Kit send gets once Kit has it scheduled.

    Args:
        round_name (str | None): The round's name, possibly blank.
        stage (str | None): The send's stage value.
        subject (str | None): The Kit draft's subject.
        send_at (str | None): When Kit sends it, already written in Pacific time.
        handed (int): People handed to Kit.
        not_handed (list[tuple[str, str]]): (name, reason) for everyone else.

    Returns:
        tuple[str, str]: Subject and HTML body.
    """
    facts = _send_facts(round_name, stage, subject)
    if send_at:
        facts.append(f"<li>Sends at: {html.escape(send_at)}</li>")
    facts.append(
        f"<li>Handed to Kit: {handed} {'person' if handed == 1 else 'people'}</li>"
    )
    if not_handed:
        left_out = (
            f"<p>Not handed to Kit ({len(not_handed)}), so Kit will not email "
            "them:</p><ul>"
            + "".join(
                f"<li>{html.escape(name or 'Unnamed person')}: {html.escape(reason)}</li>"
                for name, reason in not_handed
            )
            + "</ul>"
        )
    else:
        left_out = "<p>Everyone you selected was handed to Kit.</p>"
    return (
        _send_subject("Kit email scheduled", round_name, stage),
        "<p>Hello,</p>"
        "<p>The email you confirmed is scheduled in Kit.</p>"
        f"<ul>{''.join(facts)}</ul>" + left_out + _SEND_WHERE + _FOOTER,
    )


def email_send_failed(
    round_name: str | None,
    stage: str | None,
    subject: str | None,
    failure_code: str | None,
    error_message: str | None,
    may_still_be_scheduled: bool = False,
) -> tuple[str, str]:
    """The email the admin who created a Kit send gets when it could not be
    scheduled.

    Args:
        round_name (str | None): The round's name, possibly blank.
        stage (str | None): The send's stage value.
        subject (str | None): The Kit draft's subject.
        failure_code (str | None): A ``MentorshipEmailFailure`` value.
        error_message (str | None): What the prepare step recorded; shown only
            for a Kit error, where it is the only explanation there is.
        may_still_be_scheduled (bool): Purrf could not confirm the Kit draft is
            unscheduled, so Kit may still send it.

    Returns:
        tuple[str, str]: Subject and HTML body.
    """
    reason = send_failure_reason(failure_code)
    details = ""
    if (
        failure_code == MentorshipEmailFailure.KIT_ERROR
        and (error_message or "").strip()
    ):
        details = f"<p>Details: {html.escape(error_message.strip())}</p>"
    if may_still_be_scheduled:
        outcome = (
            "<p>Kit may still send this email: Purrf could not confirm that the "
            "draft in Kit is unscheduled. Check it in Kit and unschedule it there "
            "if needed before sending a new notification.</p>"
        )
    else:
        outcome = (
            "<p>No email was sent. To try again, select the people on the "
            "Participants card in Mentorship Management and send a new "
            "notification.</p>"
        )
    return (
        _send_subject("Kit email not scheduled", round_name, stage),
        "<p>Hello,</p>"
        "<p>The email you confirmed could not be scheduled in Kit.</p>"
        f"<ul>{''.join(_send_facts(round_name, stage, subject))}</ul>"
        f"<p>Why: {html.escape(reason)}</p>" + details + outcome + _FOOTER,
    )
