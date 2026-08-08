"""Who needs to know about each recruiting event.

Recipients are derived from data already in the database -- job owners and
assignees -- rather than from a subscription table. Notifications are
internal: nobody is a recipient by virtue of being the candidate. Someone
who applied to a posting they own is still notified, because owning it is
what puts them on the list.

Importing this module registers every resolver. ``fast_app_factory`` imports
it once at startup for that side effect.
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.entity.application_assignment_entity import (
    ApplicationAssignmentEntity,
)
from backend.entity.application_entity import ApplicationEntity
from backend.entity.event_entity import EventEntity
from backend.entity.job_entity import JobEntity
from backend.notification_management.recipient_registry import register_recipients
from backend.recruiting.pipeline_owners import normalized_owner_ids


async def _job_owners_for_application(
    session: AsyncSession, application_id: int
) -> set[int]:
    """Owner ids of the job the application belongs to.

    Owners are not a column: they live in the job's ``pipeline_config`` JSONB,
    under ``ownerIds`` on new configs and a scalar ``ownerId`` on ones saved
    before multi-owner. ``normalized_owner_ids`` is the single reader every
    consumer goes through, so both shapes keep working.

    Args:
        session (AsyncSession): Session inside the caller's open transaction.
        application_id (int): The application whose job's owners are wanted.

    Returns:
        set[int]: Owner user ids (empty if the job has none configured).
    """
    result = await session.execute(
        select(JobEntity.pipeline_config)
        .join(ApplicationEntity, ApplicationEntity.job_id == JobEntity.job_id)
        .where(ApplicationEntity.application_id == application_id)
    )
    return set(normalized_owner_ids(result.scalar_one_or_none()))


async def _assignees(session: AsyncSession, application_id: int) -> set[int]:
    """Everyone currently assigned to the application, any stage or round.

    Args:
        session (AsyncSession): Session inside the caller's open transaction.
        application_id (int): The application whose assignees are wanted.

    Returns:
        set[int]: Assignee user ids (empty if nobody is assigned).
    """
    result = await session.execute(
        select(ApplicationAssignmentEntity.assignee_id).where(
            ApplicationAssignmentEntity.application_id == application_id
        )
    )
    return set(result.scalars().all())


async def _owners_only(session: AsyncSession, event: EventEntity) -> set[int]:
    """Resolve recipients as just the job's owners.

    An owner who is also the applicant still counts: they are being told
    about a posting they are accountable for, in that capacity.

    Args:
        session (AsyncSession): Session inside the caller's open transaction.
        event (EventEntity): The event being recorded; ``subject_id`` is an
            application id.

    Returns:
        set[int]: The job's owner user ids.
    """
    return await _job_owners_for_application(session, event.subject_id)


async def _owners_and_assignees(session: AsyncSession, event: EventEntity) -> set[int]:
    """Resolve recipients as the job's owners plus every current assignee.

    Args:
        session (AsyncSession): Session inside the caller's open transaction.
        event (EventEntity): The event being recorded; ``subject_id`` is an
            application id.

    Returns:
        set[int]: Union of owner user ids and assignee user ids.
    """
    return await _job_owners_for_application(
        session, event.subject_id
    ) | await _assignees(session, event.subject_id)


for _event_type in (
    "recruiting.application_submitted",
    "recruiting.auto_rejected",
    "recruiting.blacklisted",
    "recruiting.sub_status_changed",
    "recruiting.evaluation_confirmed",
):
    register_recipients(_event_type)(_owners_only)

for _event_type in (
    "recruiting.stage_changed",
    "recruiting.round_advanced",
    "recruiting.reassigned",
    "recruiting.auto_assigned",
    "recruiting.interview_scheduled",
    "recruiting.interview_updated",
    "recruiting.interview_cancelled",
):
    register_recipients(_event_type)(_owners_and_assignees)


@register_recipients("recruiting.review_opened")
async def _review_opened(session: AsyncSession, event: EventEntity) -> set[int]:
    """Whoever can decide the review -- carried on the event, set by JobService.

    Args:
        session (AsyncSession): Session inside the caller's open transaction.
        event (EventEntity): The event being recorded; ``details["reviewerIds"]``
            lists who can decide it.

    Returns:
        set[int]: The reviewer user ids carried on the event.
    """
    return set(event.details.get("reviewerIds", []))


@register_recipients("recruiting.mentioned")
async def _mentioned(session: AsyncSession, event: EventEntity) -> set[int]:
    """The users named on the event -- carried on it, set by ``board_service.add_comment``.

    ``mentionedIds`` is a cross-task contract: Task 8's migration of
    ``board_service.add_comment`` onto ``record_event`` is the sole producer
    of this key. Who was mentioned is a property of the comment itself, not
    something derivable from the application afterwards, so it travels on
    the event rather than being queried -- same shape as
    ``recruiting.review_opened``. If Task 8 spells the key differently or
    nests it, this resolver returns an empty set with no exception and no
    log: @-mentions silently stop notifying anyone. The author is not
    excluded here -- ``record_event`` already subtracts the actor.

    Args:
        session (AsyncSession): Session inside the caller's open transaction.
        event (EventEntity): The event being recorded; ``subject_id`` is an
            application id.

    Returns:
        set[int]: The mentioned user ids carried on the event.
    """
    return set(event.details.get("mentionedIds", []))


@register_recipients("recruiting.review_decided")
async def _review_decided(session: AsyncSession, event: EventEntity) -> set[int]:
    """The job's owners, who are waiting on the verdict.

    Subject is the job itself here, not an application.

    Args:
        session (AsyncSession): Session inside the caller's open transaction.
        event (EventEntity): The event being recorded; ``subject_id`` is a
            job id.

    Returns:
        set[int]: The job's owner user ids.
    """
    result = await session.execute(
        select(JobEntity.pipeline_config).where(JobEntity.job_id == event.subject_id)
    )
    return set(normalized_owner_ids(result.scalar_one_or_none()))
