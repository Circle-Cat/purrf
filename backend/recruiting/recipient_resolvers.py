"""Who needs to know about each recruiting event.

Recipients are derived from data already in the database -- job owners,
current assignees, and the participants named on a review or a comment --
rather than from a subscription table.

Notifications are internal only, and the only recipient ``record_event``
subtracts is the actor. An internal member who owns a posting and applies to
it is therefore still resolved as an owner of their own application; the
legacy write sites excluded that case explicitly.

Importing this module registers every resolver. ``fast_app_factory`` imports
it once at startup for that side effect.
"""

from sqlalchemy import ScalarSelect, Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.common.recruiting_enums import RecruitingEvent
from backend.entity.application_assignment_entity import (
    ApplicationAssignmentEntity,
)
from backend.entity.application_comment_mention_entity import (
    ApplicationCommentMentionEntity,
)
from backend.entity.application_entity import ApplicationEntity
from backend.entity.event_entity import EventEntity
from backend.entity.job_entity import JobEntity
from backend.entity.job_review_entity import JobReviewEntity
from backend.entity.users_entity import UsersEntity
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


def _current_assignee_ids_query(application_id: int) -> Select:
    """Statement aggregating who is responsible for an application right now.

    Scoped to the application's current stage and round, and to active users.
    ``application_assignment`` keeps one row per (application, stage, round)
    and reassignment only overwrites within that key, so the rows accumulate
    as an application walks the pipeline -- unscoped, a round-1 screener stays
    a recipient for every later event, and an offboarded interviewer keeps
    accruing notifications.

    Args:
        application_id (int): The application whose assignees are wanted.

    Returns:
        Select: Statement yielding one row: an array of assignee ids, NULL
            when nobody active is assigned to the current stage and round.
    """
    return (
        select(func.array_agg(ApplicationAssignmentEntity.assignee_id))
        .select_from(ApplicationAssignmentEntity)
        .join(
            ApplicationEntity,
            ApplicationEntity.application_id
            == ApplicationAssignmentEntity.application_id,
        )
        .join(
            UsersEntity,
            UsersEntity.user_id == ApplicationAssignmentEntity.assignee_id,
        )
        .where(
            ApplicationAssignmentEntity.application_id == application_id,
            ApplicationAssignmentEntity.stage == ApplicationEntity.stage,
            ApplicationAssignmentEntity.round == ApplicationEntity.current_round,
            UsersEntity.is_active,
        )
    )


def _required_id(event: EventEntity, key: str) -> int:
    """Read an id that the event must carry in ``details``.

    Args:
        event (EventEntity): The event being recorded.
        key (str): The details key naming the row the recipients come from.

    Returns:
        int: The id stored under ``key``.

    Raises:
        ValueError: If the key is absent or null. An event of this type
            without its pointer can only resolve to nobody, and this is the
            one place that can still say so out loud -- a write site that
            spells the key differently would otherwise notify no one, with no
            exception and no log.
    """
    value = event.details.get(key)
    if value is None:
        raise ValueError(f"{event.event_type!r} requires details[{key!r}]")
    return value


async def _review_participant(
    session: AsyncSession, event: EventEntity, column
) -> set[int]:
    """Resolve one participant of the review the event names.

    The review row is the truth about who opened it and who is waiting on it,
    so the event carries only its id.

    Args:
        session (AsyncSession): Session inside the caller's open transaction.
        event (EventEntity): The event being recorded; ``details["reviewId"]``
            names the review.
        column: The ``JobReviewEntity`` column holding the user id wanted.

    Returns:
        set[int]: The single user id in that column.

    Raises:
        ValueError: If the event carries no review id, or names a review that
            does not exist.
    """
    review_id = _required_id(event, "reviewId")
    result = await session.execute(
        select(column).where(JobReviewEntity.review_id == review_id)
    )
    user_id = result.scalar_one_or_none()
    if user_id is None:
        raise ValueError(f"{event.event_type!r} names unknown review {review_id}")
    return {user_id}


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
        statement = statement.add_columns(
            _current_assignee_ids_query(assignees_of).scalar_subquery()
        )

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
    """Resolve recipients as the job's owners plus whoever is responsible now.

    Args:
        session (AsyncSession): Session inside the caller's open transaction.
        event (EventEntity): The event being recorded; ``subject_id`` is an
            application id.

    Returns:
        set[int]: Union of owner user ids and current assignee user ids.
    """
    return await _job_owners(
        session,
        _job_id_of_application(event.subject_id),
        assignees_of=event.subject_id,
    )


async def _assignees_only(session: AsyncSession, event: EventEntity) -> set[int]:
    """Resolve recipients as whoever is responsible for the application now.

    Owners are excluded: the events resolved this way accompany another event
    that already reaches them, and notifying them twice for one action reads
    as duplicate applications in the bell.

    Args:
        session (AsyncSession): Session inside the caller's open transaction.
        event (EventEntity): The event being recorded; ``subject_id`` is an
            application id.

    Returns:
        set[int]: Current assignee user ids (empty if nobody active holds it).
    """
    result = await session.execute(_current_assignee_ids_query(event.subject_id))
    return set(result.scalar_one_or_none() or ())


@register_recipients(RecruitingEvent.REVIEW_OPENED, subject_type="job")
async def _review_opened(session: AsyncSession, event: EventEntity) -> set[int]:
    """Whoever can decide the review, read off the review row.

    Args:
        session (AsyncSession): Session inside the caller's open transaction.
        event (EventEntity): The event being recorded; ``subject_id`` is a job
            id and ``details["reviewId"]`` names the review.

    Returns:
        set[int]: The reviewer's user id.

    Raises:
        ValueError: If the event carries no review id, or names no review.
    """
    return await _review_participant(session, event, JobReviewEntity.reviewer_id)


@register_recipients(RecruitingEvent.REVIEW_DECIDED, subject_type="job")
async def _review_decided(session: AsyncSession, event: EventEntity) -> set[int]:
    """Whoever submitted the review and is waiting on the verdict.

    Not the job's owners: submitting for review is gated on permission rather
    than ownership, so the person waiting need not be an owner of the posting
    they sent up.

    Args:
        session (AsyncSession): Session inside the caller's open transaction.
        event (EventEntity): The event being recorded; ``subject_id`` is a job
            id and ``details["reviewId"]`` names the review.

    Returns:
        set[int]: The submitter's user id.

    Raises:
        ValueError: If the event carries no review id, or names no review.
    """
    return await _review_participant(session, event, JobReviewEntity.submitted_by)


@register_recipients(RecruitingEvent.MENTIONED, subject_type="application")
async def _mentioned(session: AsyncSession, event: EventEntity) -> set[int]:
    """The users named in the comment, read off the mention rows.

    ``add_comment`` persists one ``application_comment_mention`` row per
    mention in the same transaction, so the comment id is all the event needs
    to carry. The author is not excluded here -- ``record_event`` already
    subtracts the actor.

    Args:
        session (AsyncSession): Session inside the caller's open transaction.
        event (EventEntity): The event being recorded; ``subject_id`` is an
            application id and ``details["commentId"]`` names the comment.

    Returns:
        set[int]: The mentioned user ids.

    Raises:
        ValueError: If the event carries no comment id, or the comment has no
            mention rows -- an @-mention event that reaches nobody is a write
            site bug, not a state worth recording silently.
    """
    comment_id = _required_id(event, "commentId")
    result = await session.execute(
        select(ApplicationCommentMentionEntity.mentioned_user_id).where(
            ApplicationCommentMentionEntity.comment_id == comment_id
        )
    )
    mentioned = set(result.scalars().all())
    if not mentioned:
        raise ValueError(
            f"{event.event_type!r} names comment {comment_id}, which mentions nobody"
        )
    return mentioned


_APPLICATION_RESOLVERS: dict[str, Resolver] = {
    RecruitingEvent.APPLICATION_SUBMITTED: _owners_only,
    RecruitingEvent.AUTO_REJECTED: _owners_only,
    RecruitingEvent.BLACKLISTED: _owners_only,
    RecruitingEvent.SUB_STATUS_CHANGED: _owners_only,
    RecruitingEvent.EVALUATION_CONFIRMED: _owners_only,
    RecruitingEvent.STAGE_CHANGED: _owners_and_assignees,
    RecruitingEvent.ROUND_ADVANCED: _owners_and_assignees,
    RecruitingEvent.REASSIGNED: _owners_and_assignees,
    RecruitingEvent.INTERVIEW_SCHEDULED: _owners_and_assignees,
    RecruitingEvent.INTERVIEW_UPDATED: _owners_and_assignees,
    RecruitingEvent.INTERVIEW_CANCELLED: _owners_and_assignees,
    RecruitingEvent.AUTO_ASSIGNED: _assignees_only,
}


def _register_application_resolvers() -> None:
    """Register every event type whose subject is an application.

    The wiring is a table, one row per event type, so which shape an event
    gets is read rather than traced. Types whose subject is something else
    use the ``register_recipients`` decorator directly.
    """
    for event_type, resolver in _APPLICATION_RESOLVERS.items():
        register_recipients(event_type, subject_type="application")(resolver)


_register_application_resolvers()
