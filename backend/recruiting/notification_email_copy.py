"""Subject + HTML body for one in-app notification, as an email.

Deliberately a second copy of the wording the bell renders in
``NotificationBell.describe()``, not a shared source. The two have
different jobs: the bell renders whenever the user opens the popover --
possibly days later -- while an email is rendered milliseconds after the
event, so only the email can safely state point-in-time facts like the
stage an evaluation was assigned at.

Emails carry no links (decided 2026-07-30), so each body has to stand on
its own: what happened, who and which posting it concerns, and where in
Purrf to act on it.

That last part is a promise about the UI, so the destination has to be
the sidebar label the recipient will actually see -- verbatim, from
``navItems`` in ``frontend/src/components/layout/Sidebar.jsx``. The
sidebar is one flat list with no groups, so a body must never spell a
path like "Recruiting -> Postings": there is nothing called Recruiting to
open, and a reader who goes looking for it finds no such menu.

``NotificationDto.actor_name`` carries a three-way distinction that must
not be collapsed by a truthiness check: ``None`` means ``actor_user_id``
was NULL (the row was written by the system, e.g. a stage's default
assignee being materialised) -- there is genuinely nobody to name.
``""`` means there was an actor, but their user row is gone or otherwise
unresolvable -- claiming the event was automatic would be a lie, so this
case falls back to ``_MISSING_ACTOR``. A real string names them.
"""

from backend.common.recruiting_enums import (
    ApplicationStage,
    JobKind,
)

_FOOTER = (
    "<p>This is an automated message from Purrf. Replies to this address "
    "aren't monitored.</p>"
)

_MISSING_ACTOR = "Someone"
_MISSING_APPLICANT = "A candidate"


def stage_label(stage: ApplicationStage | None, kind: JobKind | None) -> str:
    """Display label for an application stage, mirroring the frontend.

    Must stay identical to ``stageLabel`` in
    ``frontend/src/pages/Recruiting/board/stageFormat.js``: underscores to
    spaces, first letter capitalised, and an activity posting's terminal
    success stage reading "Admitted" rather than "Hired" (a display-only
    rename -- the stored value is always ``hired``). An email that invented
    friendlier labels than the board would leave recipients looking for a
    stage that does not appear in the UI.

    Args:
        stage (ApplicationStage | None): The stage, or None when the
            notification is not application-scoped.
        kind (JobKind | None): The posting's kind, for the Hired/Admitted
            rename.

    Returns:
        str: The label, or "" when stage is None.
    """
    if stage is None:
        return ""
    if kind == JobKind.ACTIVITY and stage == ApplicationStage.HIRED:
        return "Admitted"
    spaced = stage.value.replace("_", " ")
    return spaced[:1].upper() + spaced[1:]


def _round_suffix(round_number: int | None) -> str:
    """ ", session N" past the first session, "" otherwise (session 1 is noise)."""
    if round_number is None or round_number <= 1:
        return ""
    return f", session {round_number}"


def _candidate_line(dto) -> str:
    """The "Candidate: ..." paragraph, or "" when there is no address.

    A display name is mutable and not unique, so naming the candidate's
    address gives the reader a handle that survives a rename and can be
    pasted into the board's search. It is its own paragraph rather than
    inlined because every body names the candidate possessively
    ("{applicant}'s interview"), where an inlined address would read
    "Ada Lovelace (ada@example.com)'s interview".

    Args:
        dto: The display fields, carrying applicant_name and applicant_email.

    Returns:
        str: "<p>Candidate: Name (address)</p>", "<p>Candidate: address</p>"
            when the name resolved to nothing, or "" when no address is on
            file -- a name-only line would only repeat the body.
    """
    if not dto.applicant_email:
        return ""
    if not dto.applicant_name:
        return f"<p>Candidate: {dto.applicant_email}</p>"
    return f"<p>Candidate: {dto.applicant_name} ({dto.applicant_email})</p>"


def _assigned_to_evaluate(dto, stage):
    applicant = dto.applicant_name or _MISSING_APPLICANT
    if dto.actor_name is None:
        # actor_user_id was NULL: the row was written by the system when a
        # stage's configured default assignee was materialised, so there is
        # genuinely nobody to name.
        opening = (
            f"You were automatically assigned to evaluate {applicant} for "
            f"{dto.job_title}, as the posting's default assignee for this stage."
        )
    else:
        # Someone did assign it; their name is just unresolvable (a deleted
        # user row resolves to ""). "Someone" is truer than claiming the
        # assignment was automatic.
        actor = dto.actor_name or _MISSING_ACTOR
        opening = f"{actor} assigned you to evaluate {applicant} for {dto.job_title}."
    return (
        f"Evaluation assigned: {applicant} ({dto.job_title})",
        f"<p>{opening}</p>"
        f"{_candidate_line(dto)}"
        f"<p>Stage: {stage_label(stage, dto.job_kind)}"
        f"{_round_suffix(dto.round)}.</p>"
        "<p>Open My Interview Evaluations in Purrf to submit your "
        "evaluation.</p>",
    )


def _mentioned(dto, stage):
    actor = dto.actor_name or _MISSING_ACTOR
    applicant = dto.applicant_name or _MISSING_APPLICANT
    return (
        f"{actor} mentioned you: {applicant} ({dto.job_title})",
        f"<p>{actor} mentioned you in a comment on {applicant}'s "
        f"application for {dto.job_title}.</p>"
        f"{_candidate_line(dto)}"
        "<p>Open the application in Purrf and go to its Comments tab to "
        "read the thread and reply.</p>",
    )


def _job_review_requested(dto, stage):
    actor = dto.actor_name or _MISSING_ACTOR
    return (
        f"Posting review requested: {dto.job_title}",
        f'<p>{actor} submitted the posting "{dto.job_title}" for your '
        "review. It is waiting on your decision.</p>"
        "<p>Open My Posting Reviews in Purrf to approve or reject it.</p>",
    )


def _job_review_approved(dto, stage):
    actor = dto.actor_name or _MISSING_ACTOR
    return (
        f"Posting approved: {dto.job_title}",
        f"<p>{actor} approved your submission for the posting "
        f'"{dto.job_title}".</p>'
        "<p>Open Job Postings in Purrf to see its current state.</p>",
    )


def _job_review_rejected(dto, stage):
    actor = dto.actor_name or _MISSING_ACTOR
    return (
        f"Posting rejected: {dto.job_title}",
        f"<p>{actor} rejected your submission for the posting "
        f'"{dto.job_title}".</p>'
        "<p>Open Job Postings in Purrf to see the outcome and any comment "
        "the reviewer left.</p>",
    )


def _application_submitted(dto, stage):
    applicant = dto.applicant_name or _MISSING_APPLICANT
    return (
        f"New application: {applicant} for {dto.job_title}",
        f"<p>{applicant} applied to {dto.job_title}. The application is "
        f"waiting for review at the {stage_label(stage, dto.job_kind)} "
        "stage.</p>"
        f"{_candidate_line(dto)}"
        "<p>You're receiving this because you own this posting. Open the "
        "Applications Board in Purrf to review it.</p>",
    )


def _application_auto_rejected(dto, stage):
    applicant = dto.applicant_name or _MISSING_APPLICANT
    return (
        f"Application auto-rejected: {applicant} ({dto.job_title})",
        f"<p>{applicant} applied to {dto.job_title} and was rejected "
        "automatically, with no human review.</p>"
        f"{_candidate_line(dto)}"
        "<p>The reason is recorded on the application's timeline in Purrf. "
        "No action is needed unless you want to overturn it.</p>",
    )


def _application_auto_hired(dto, stage):
    applicant = dto.applicant_name or _MISSING_APPLICANT
    # Same display-only rename as stage_label: an activity posting admits,
    # it does not hire.
    verb = "admitted" if dto.job_kind == JobKind.ACTIVITY else "hired"
    return (
        f"Application auto-{verb}: {applicant} ({dto.job_title})",
        f"<p>{applicant} applied to {dto.job_title} and was {verb} "
        "automatically, with no human review.</p>"
        f"{_candidate_line(dto)}"
        "<p>The matching screening rule is recorded on the application's "
        "timeline in Purrf.</p>",
    )


# ---------------------------------------------------------------------------
# Templates are dispatched by event_type, not from this file -- see
# backend/recruiting/notification_renderers.py, which builds the ``dto`` each
# of these takes from EventEntity.details.
#
# The 7 existing functions above cover the other 7 notifying event types
# verbatim (reassigned/auto_assigned share _assigned_to_evaluate;
# review_decided picks _job_review_approved/_job_review_rejected by
# ``details["decision"]``) -- untouched, per the standing rule that shipped
# template English does not change once live.
# ---------------------------------------------------------------------------


def _humanize(value: str) -> str:
    """ "in_progress" -> "In progress". Mirrors frontend/.../stageFormat.js's ``humanize``.

    Used for sub-status values, which (like stages) are snake_case and have
    no friendlier rename table of their own.
    """
    spaced = value.replace("_", " ")
    return spaced[:1].upper() + spaced[1:]


def _format_utc(instant) -> str:
    """ "2026-08-12 15:00 UTC" -- a meeting instant, always in UTC.

    Interview times have no stored booking timezone the way an email
    renderer could safely reuse (see ``ApplicationInterviewEntity``'s own
    docstring on why): the wall clock a recruiter typed is not necessarily
    the zone of every owner/assignee this email goes to. UTC is the one
    reading that is never wrong, at the cost of not being the reader's own
    time -- the same trade every other surface in this codebase resolves the
    other way only because it knows who the *viewer* is; a static email body
    does not.

    Args:
        instant (datetime): A timezone-aware instant (UTC).

    Returns:
        str: The formatted instant.
    """
    return instant.strftime("%Y-%m-%d %H:%M UTC")


def _blacklisted(dto, stage):
    actor = dto.actor_name or _MISSING_ACTOR
    applicant = dto.applicant_name or _MISSING_APPLICANT
    return (
        f"Application blacklisted: {applicant} ({dto.job_title})",
        f"<p>{actor} blacklisted {applicant} and rejected their application "
        f'for {dto.job_title}, with the reason: "{dto.reason}".</p>'
        f"{_candidate_line(dto)}"
        "<p>Open the Blacklist page in Purrf to review the block.</p>",
    )


def _stage_changed(dto, stage):
    actor = dto.actor_name or _MISSING_ACTOR
    applicant = dto.applicant_name or _MISSING_APPLICANT
    return (
        f"Stage changed: {applicant} ({dto.job_title})",
        f"<p>{actor} moved {applicant}'s application for {dto.job_title} to "
        f"the {stage_label(stage, dto.job_kind)} stage.</p>"
        f"{_candidate_line(dto)}"
        "<p>Open the Applications Board in Purrf to see it.</p>",
    )


def _round_advanced(dto, stage):
    actor = dto.actor_name or _MISSING_ACTOR
    applicant = dto.applicant_name or _MISSING_APPLICANT
    return (
        f"Round advanced: {applicant} ({dto.job_title})",
        f"<p>{actor} advanced {applicant}'s {stage_label(stage, dto.job_kind)} "
        f"round for {dto.job_title} to round {dto.round}.</p>"
        f"{_candidate_line(dto)}"
        "<p>Open the Applications Board in Purrf to see it.</p>",
    )


def _sub_status_changed(dto, stage):
    actor = dto.actor_name or _MISSING_ACTOR
    applicant = dto.applicant_name or _MISSING_APPLICANT
    return (
        f"Status changed: {applicant} ({dto.job_title})",
        f"<p>{actor} moved {applicant}'s {stage_label(stage, dto.job_kind)} "
        f"status for {dto.job_title} to {_humanize(dto.to_sub_status)}.</p>"
        f"{_candidate_line(dto)}"
        "<p>Open the Applications Board in Purrf to see it.</p>",
    )


def _evaluation_confirmed(dto, stage):
    actor = dto.actor_name or _MISSING_ACTOR
    applicant = dto.applicant_name or _MISSING_APPLICANT
    return (
        f"Evaluation submitted: {applicant} ({dto.job_title})",
        f"<p>{actor} submitted their evaluation of {applicant} for "
        f"{dto.job_title}.</p>"
        f"{_candidate_line(dto)}"
        f"<p>Stage: {stage_label(stage, dto.job_kind)}{_round_suffix(dto.round)}.</p>"
        "<p>Open the Applications Board in Purrf to read it.</p>",
    )


def _interview_scheduled(dto, stage):
    actor = dto.actor_name or _MISSING_ACTOR
    applicant = dto.applicant_name or _MISSING_APPLICANT
    return (
        f"Interview scheduled: {applicant} ({dto.job_title})",
        f"<p>{actor} scheduled an interview with {applicant} for "
        f"{dto.job_title}, on {_format_utc(dto.start_at)}.</p>"
        f"{_candidate_line(dto)}"
        f"<p>Stage: {stage_label(stage, dto.job_kind)}{_round_suffix(dto.round)}.</p>"
        "<p>Open the Applications Board in Purrf to see it.</p>",
    )


def _interview_updated(dto, stage):
    actor = dto.actor_name or _MISSING_ACTOR
    applicant = dto.applicant_name or _MISSING_APPLICANT
    return (
        f"Interview rescheduled: {applicant} ({dto.job_title})",
        f"<p>{actor} rescheduled {applicant}'s interview for {dto.job_title} "
        f"to {_format_utc(dto.start_at)}.</p>"
        f"{_candidate_line(dto)}"
        f"<p>Stage: {stage_label(stage, dto.job_kind)}{_round_suffix(dto.round)}.</p>"
        "<p>Open the Applications Board in Purrf to see it.</p>",
    )


def _interview_cancelled(dto, stage):
    actor = dto.actor_name or _MISSING_ACTOR
    applicant = dto.applicant_name or _MISSING_APPLICANT
    return (
        f"Interview cancelled: {applicant} ({dto.job_title})",
        f"<p>{actor} cancelled {applicant}'s interview for {dto.job_title}, "
        f"which was set for {_format_utc(dto.start_at)}.</p>"
        f"{_candidate_line(dto)}"
        f"<p>Stage: {stage_label(stage, dto.job_kind)}{_round_suffix(dto.round)}.</p>"
        "<p>Open the Applications Board in Purrf to see it.</p>",
    )
