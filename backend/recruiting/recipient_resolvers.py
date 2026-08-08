"""Who needs to know about each recruiting event.

Recipients are derived from data already in the database -- job owners and
assignees -- rather than from a subscription table. The candidate is never
a recipient: notifications are internal only.

Importing this module registers every resolver. ``fast_app_factory`` imports
it once at startup for that side effect.
"""

from sqlalchemy import ScalarSelect, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.entity.application_assignment_entity import (
    ApplicationAssignmentEntity,
)
from backend.entity.application_entity import ApplicationEntity
from backend.entity.event_entity import EventEntity
from backend.entity.job_entity import JobEntity
from backend.notification_management.recipient_registry import (
    Resolver,
    register_recipients,
)
from backend.recruiting.pipeline_owners import normalized_owner_ids


def _job_id_of_application(application_id: int) -> ScalarSelect:
    """Subquery selecting the job an application belongs to.

    Args:
        application_id (int): The application whose job is wanted.

    Returns:
        ScalarSelect: Yields the job id, NULL if there is no such application.
    """
    return (
        select(ApplicationEntity.job_id)
        .where(ApplicationEntity.application_id == application_id)
        .scalar_subquery()
    )


def _assignee_ids_of(application_id: int) -> ScalarSelect:
    """Subquery aggregating everyone assigned to an application.

    Every stage and round, not just the current one.

    Args:
        application_id (int): The application whose assignees are wanted.

    Returns:
        ScalarSelect: Yields an array of assignee ids, NULL if nobody is
            assigned.
    """
    return (
        select(func.array_agg(ApplicationAssignmentEntity.assignee_id))
        .where(ApplicationAssignmentEntity.application_id == application_id)
        .scalar_subquery()
    )


async def _job_owners(
    session: AsyncSession,
    job_id: int | ScalarSelect,
    *,
    assignees_of: int | None = None,
) -> set[int]:
    """Owner ids of a job, plus one application's assignees when asked.

    Owners are not a column: they live in the job's ``pipeline_config`` JSONB,
    under ``ownerIds`` on new configs and a scalar ``ownerId`` on ones saved
    before multi-owner. ``normalized_owner_ids`` is the single reader every
    consumer goes through, so both shapes keep working.

    One round trip either way -- with ``assignees_of`` the assignee ids ride
    along as an aggregated subquery on the same statement.

    Args:
        session (AsyncSession): Session inside the caller's open transaction.
        job_id (int | ScalarSelect): The job, as an id or as a subquery
            selecting one -- see ``_job_id_of_application``.
        assignees_of (int | None): Application whose assignees join the owners.
            Omit to resolve owners alone.

    Returns:
        set[int]: Owner user ids, unioned with the assignee ids when asked
            (empty if the job has no owners configured).
    """
    statement = select(JobEntity.pipeline_config).where(JobEntity.job_id == job_id)
    if assignees_of is not None:
        statement = statement.add_columns(_assignee_ids_of(assignees_of))

    row = (await session.execute(statement)).first()
    if row is None:
        return set()

    owners = set(normalized_owner_ids(row[0]))
    if assignees_of is None:
        return owners
    return owners | set(row[1] or ())


async def _owners_only(session: AsyncSession, event: EventEntity) -> set[int]:
    """Resolve recipients as just the job's owners.

    Args:
        session (AsyncSession): Session inside the caller's open transaction.
        event (EventEntity): The event being recorded; ``subject_id`` is an
            application id.

    Returns:
        set[int]: The job's owner user ids.
    """
    return await _job_owners(session, _job_id_of_application(event.subject_id))


async def _owners_and_assignees(session: AsyncSession, event: EventEntity) -> set[int]:
    """Resolve recipients as the job's owners plus every current assignee.

    Args:
        session (AsyncSession): Session inside the caller's open transaction.
        event (EventEntity): The event being recorded; ``subject_id`` is an
            application id.

    Returns:
        set[int]: Union of owner user ids and assignee user ids.
    """
    return await _job_owners(
        session,
        _job_id_of_application(event.subject_id),
        assignees_of=event.subject_id,
    )


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
    """The users named on the event -- carried on it, set by the write site.

    Who was mentioned is a property of the comment itself, not something
    derivable from the application afterwards, so it travels on the event
    rather than being queried -- same shape as ``recruiting.review_opened``.
    A missing ``mentionedIds`` yields an empty set: nobody is notified. The
    author is not excluded here -- ``record_event`` already subtracts the
    actor.

    Args:
        session (AsyncSession): Session inside the caller's open transaction.
        event (EventEntity): The event being recorded; ``details["mentionedIds"]``
            lists who was named and ``subject_id`` is an application id.

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
    return await _job_owners(session, event.subject_id)


_SHARED_RESOLVERS: dict[str, Resolver] = {
    "recruiting.application_submitted": _owners_only,
    "recruiting.auto_rejected": _owners_only,
    "recruiting.blacklisted": _owners_only,
    "recruiting.sub_status_changed": _owners_only,
    "recruiting.evaluation_confirmed": _owners_only,
    "recruiting.stage_changed": _owners_and_assignees,
    "recruiting.round_advanced": _owners_and_assignees,
    "recruiting.reassigned": _owners_and_assignees,
    "recruiting.auto_assigned": _owners_and_assignees,
    "recruiting.interview_scheduled": _owners_and_assignees,
    "recruiting.interview_updated": _owners_and_assignees,
    "recruiting.interview_cancelled": _owners_and_assignees,
}


def _register_shared_resolvers() -> None:
    """Register every event type served by one of the two shared resolvers.

    The wiring is a table, one row per event type, so which shape an event
    gets is read rather than traced. Types needing their own resolver use the
    ``register_recipients`` decorator instead.
    """
    for event_type, resolver in _SHARED_RESOLVERS.items():
        register_recipients(event_type)(resolver)


_register_shared_resolvers()
