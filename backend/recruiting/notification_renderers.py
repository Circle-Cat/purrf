"""Renders one recruiting event into (subject, HTML body) for delivery.

Bridges the domain-neutral ``render_registry``/``DeliveryService`` to
``notification_email_copy``'s per-type template functions. ``NotificationDto``
served that role for the old ``NotificationType``-keyed model;
``EventEntity.event_type`` replaces it here, so this module resolves the same
display fields (applicant_name/job_title/actor_name/job_kind/stage/round)
from ``subject_id`` + ``event.details`` instead of from ``NotificationEntity``'s
legacy columns, and hands them to the template functions as a plain
``SimpleNamespace`` rather than a ``NotificationDto`` (whose ``type`` field a
new-model row has no value for).

Stage and round are read from ``event.details`` -- the value captured at the
instant the write site recorded the event -- never re-queried live. A Pub/Sub
redelivery can render this notification hours after the event (see
``EXPIRY`` in ``delivery_service.py``), by which point the application may
have moved to a different stage or round; a live read would misreport a
point-in-time fact as current. This is exactly the risk
``notification_email_copy``'s module docstring calls out for the old model's
near-immediate worker, sharpened by how much slower Pub/Sub delivery can be.
The ``details`` keys each renderer below reads are a cross-task contract
with the write-site migration (record_event's future callers): every key is
taken from that call site's *existing* (pre-migration) activity-log
``details`` dict, on the theory that the migration swaps the API call and
keeps the payload. If a future write site spells or nests a key
differently, the affected renderer raises ``KeyError``/``ValueError``, which
``DeliveryService`` treats as a transient failure (retried, then expired
after 24h) rather than a silent wrong render.

Importing this module registers every renderer. ``fast_app_factory`` imports
it once at startup for that side effect, alongside ``recipient_resolvers``.
"""

from datetime import datetime

from types import SimpleNamespace

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.common.recruiting_enums import ApplicationStage
from backend.entity.application_entity import ApplicationEntity
from backend.entity.event_entity import EventEntity
from backend.entity.job_entity import JobEntity
from backend.entity.users_entity import UsersEntity
from backend.notification_management.render_registry import register_render
from backend.recruiting import notification_email_copy as copy


async def _display_name(session: AsyncSession, user_id: int) -> str:
    """Resolve a user id to "First Last", or "" if the row is gone.

    Args:
        session (AsyncSession): Session inside the caller's open transaction.
        user_id (int): The user to resolve.

    Returns:
        str: "First Last" (whitespace-trimmed), or "" if no such user.
    """
    result = await session.execute(
        select(UsersEntity.first_name, UsersEntity.last_name).where(
            UsersEntity.user_id == user_id
        )
    )
    row = result.first()
    return f"{row[0]} {row[1]}".strip() if row is not None else ""


async def _application_context(session: AsyncSession, application_id: int):
    """job_title/job_kind/applicant_name for an application-scoped event.

    Returns ("", None, "") if the application (or its job) is gone --
    same "resolved to nothing" convention ``RecruitingNotificationService
    ._to_dto`` uses for the bell.
    """
    result = await session.execute(
        select(JobEntity.title, JobEntity.kind, ApplicationEntity.user_id)
        .join(ApplicationEntity, ApplicationEntity.job_id == JobEntity.job_id)
        .where(ApplicationEntity.application_id == application_id)
    )
    row = result.first()
    if row is None:
        return "", None, ""
    job_title, job_kind, candidate_id = row
    return job_title, job_kind, await _display_name(session, candidate_id)


async def _job_context(session: AsyncSession, job_id: int):
    """job_title/job_kind for a job-scoped event. ("", None) if the job is gone."""
    result = await session.execute(
        select(JobEntity.title, JobEntity.kind).where(JobEntity.job_id == job_id)
    )
    row = result.first()
    return row if row is not None else ("", None)


async def _base_dto(session: AsyncSession, event: EventEntity) -> SimpleNamespace:
    """The display fields every renderer below starts from, resolved once.

    Args:
        session (AsyncSession): Session inside the caller's open transaction.
        event (EventEntity): The event being rendered.

    Returns:
        SimpleNamespace: job_title/job_kind/applicant_name/actor_name, plus
            whatever event-type-specific fields the caller adds afterwards.
    """
    actor_name = await _display_name(session, event.actor_id)
    if event.subject_type == "application":
        job_title, job_kind, applicant_name = await _application_context(
            session, event.subject_id
        )
    elif event.subject_type == "job":
        job_title, job_kind = await _job_context(session, event.subject_id)
        applicant_name = ""
    else:
        job_title, job_kind, applicant_name = "", None, ""
    return SimpleNamespace(
        job_title=job_title,
        job_kind=job_kind,
        applicant_name=applicant_name,
        actor_name=actor_name,
    )


def _stage(details: dict, key: str = "stage") -> ApplicationStage:
    """``ApplicationStage(details[key])`` -- see the module docstring on why
    this reads the event's own snapshot rather than the application's live
    stage."""
    return ApplicationStage(details[key])


def _with_footer(rendered: tuple[str, str]) -> tuple[str, str]:
    """Append the standard automated-message footer, same text every
    NotificationType-keyed template gets via render()."""
    subject, body = rendered
    return subject, body + copy._FOOTER


# --- application_submitted / auto_rejected -----------------------------


@register_render("recruiting.application_submitted")
async def _render_application_submitted(session, event):
    """A landing application, worded by how it landed.

    One event type covers both a plain submission and one a screen rule hired
    outright, because both are the same thing happening to the application.
    They read differently to an owner though -- one is work waiting on the
    board, the other is already decided -- so the auto-hire marker in the
    details selects the copy.
    """
    dto = await _base_dto(session, event)
    stage = _stage(event.details)
    if "screenAutoHireRuleId" in event.details:
        return _with_footer(copy._application_auto_hired(dto, stage))
    return _with_footer(copy._application_submitted(dto, stage))


@register_render("recruiting.auto_rejected")
async def _render_auto_rejected(session, event):
    dto = await _base_dto(session, event)
    return _with_footer(copy._application_auto_rejected(dto, None))


# --- reassigned / auto_assigned -> _assigned_to_evaluate ----------------


async def _render_assigned_to_evaluate(session, event):
    dto = await _base_dto(session, event)
    dto.round = event.details.get("round")
    return _with_footer(copy._assigned_to_evaluate(dto, _stage(event.details)))


register_render("recruiting.reassigned")(_render_assigned_to_evaluate)
register_render("recruiting.auto_assigned")(_render_assigned_to_evaluate)


# --- mentioned -----------------------------------------------------------


@register_render("recruiting.mentioned")
async def _render_mentioned(session, event):
    dto = await _base_dto(session, event)
    return _with_footer(copy._mentioned(dto, None))


# --- review_opened / review_decided (subject is the job) ----------------


@register_render("recruiting.review_opened")
async def _render_review_opened(session, event):
    dto = await _base_dto(session, event)
    return _with_footer(copy._job_review_requested(dto, None))


@register_render("recruiting.review_decided")
async def _render_review_decided(session, event):
    dto = await _base_dto(session, event)
    template = (
        copy._job_review_approved
        if event.details["decision"] == "approved"
        else copy._job_review_rejected
    )
    return _with_footer(template(dto, None))


# --- the 8 new event types -----------------------------------------------
#
# None of these go through notification_email_copy.render() -- that
# function dispatches by NotificationType, not event_type, and is the one
# thing this module must not touch. render() is also the only place that
# appends copy._FOOTER, so each wrapper below does it explicitly instead.


@register_render("recruiting.blacklisted")
async def _render_blacklisted(session, event):
    dto = await _base_dto(session, event)
    dto.reason = event.details["reason"]
    return _with_footer(copy._blacklisted(dto, None))


@register_render("recruiting.stage_changed")
async def _render_stage_changed(session, event):
    dto = await _base_dto(session, event)
    return _with_footer(copy._stage_changed(dto, _stage(event.details, "toStage")))


@register_render("recruiting.round_advanced")
async def _render_round_advanced(session, event):
    dto = await _base_dto(session, event)
    dto.round = event.details["toRound"]
    return _with_footer(copy._round_advanced(dto, _stage(event.details)))


@register_render("recruiting.sub_status_changed")
async def _render_sub_status_changed(session, event):
    dto = await _base_dto(session, event)
    dto.to_sub_status = event.details["toSubStatus"]
    return _with_footer(copy._sub_status_changed(dto, _stage(event.details)))


@register_render("recruiting.evaluation_confirmed")
async def _render_evaluation_confirmed(session, event):
    dto = await _base_dto(session, event)
    dto.round = event.details["round"]
    return _with_footer(copy._evaluation_confirmed(dto, _stage(event.details)))


async def _render_interview(session, event, template):
    dto = await _base_dto(session, event)
    dto.round = event.details["round"]
    dto.start_at = datetime.fromisoformat(event.details["startAt"])
    return _with_footer(template(dto, _stage(event.details)))


@register_render("recruiting.interview_scheduled")
async def _render_interview_scheduled(session, event):
    return await _render_interview(session, event, copy._interview_scheduled)


@register_render("recruiting.interview_updated")
async def _render_interview_updated(session, event):
    return await _render_interview(session, event, copy._interview_updated)


@register_render("recruiting.interview_cancelled")
async def _render_interview_cancelled(session, event):
    return await _render_interview(session, event, copy._interview_cancelled)
