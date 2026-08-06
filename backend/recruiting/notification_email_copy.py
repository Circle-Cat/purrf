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
    NotificationType,
)
from backend.dto.notification_dto import NotificationDto

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
        "<p>You're receiving this because you own this posting. Open the "
        "Applications Board in Purrf to review it.</p>",
    )


def _application_auto_rejected(dto, stage):
    applicant = dto.applicant_name or _MISSING_APPLICANT
    return (
        f"Application auto-rejected: {applicant} ({dto.job_title})",
        f"<p>{applicant} applied to {dto.job_title} and was rejected "
        "automatically, with no human review.</p>"
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
        "<p>The matching screening rule is recorded on the application's "
        "timeline in Purrf.</p>",
    )


TEMPLATES = {
    NotificationType.ASSIGNED_TO_EVALUATE: _assigned_to_evaluate,
    NotificationType.MENTIONED: _mentioned,
    NotificationType.JOB_REVIEW_REQUESTED: _job_review_requested,
    NotificationType.JOB_REVIEW_APPROVED: _job_review_approved,
    NotificationType.JOB_REVIEW_REJECTED: _job_review_rejected,
    NotificationType.APPLICATION_SUBMITTED: _application_submitted,
    NotificationType.APPLICATION_AUTO_REJECTED: _application_auto_rejected,
    NotificationType.APPLICATION_AUTO_HIRED: _application_auto_hired,
}


def render(dto: NotificationDto, stage: ApplicationStage | None) -> tuple[str, str]:
    """Render one notification as (subject, HTML body).

    Args:
        dto (NotificationDto): The resolved notification, whose display
            fields (job_title/applicant_name/actor_name/job_kind) are
            already looked up.
        stage (ApplicationStage | None): The application's stage at the
            moment of the event. None for notifications that are not
            application-scoped; only the two types that mention a stage
            read it.

    Returns:
        tuple[str, str]: Subject line and HTML body, footer included.

    Raises:
        KeyError: If dto.type has no template. Deliberately not a silent
            fallback -- a blank email is worse than a loud failure, and the
            exhaustiveness test makes this unreachable.
    """
    subject, body = TEMPLATES[dto.type](dto, stage)
    return subject, body + _FOOTER
