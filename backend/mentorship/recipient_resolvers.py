"""Who needs to know about each mentorship event.

Same derivation rule as ``recruiting/recipient_resolvers.py`` -- recipients
come from data already in the database, not a subscription table -- with one
difference that matters: this domain's recipient is a candidate, not staff.

Importing this module registers every resolver. ``fast_app_factory`` imports
it once at startup for that side effect.
"""

from sqlalchemy.ext.asyncio import AsyncSession

from backend.common.inbox_enums import INBOX_SUBJECT_TYPE
from backend.common.mentorship_email_enums import MENTORSHIP_EMAIL_SEND_SUBJECT_TYPE
from backend.common.mentorship_enums import MentorshipEvent
from backend.common.permissions import Permission
from backend.communication.thread_recipients import thread_senders, thread_senders_else
from backend.entity.event_entity import EventEntity
from backend.notification_management.recipient_registry import register_recipients
from backend.repository.application_repository import ApplicationRepository
from backend.repository.approval_request_repository import (
    ApprovalRequestRepository,
)
from backend.repository.mentorship_email_repository import MentorshipEmailRepository
from backend.repository.user_permissions_repository import UserPermissionsRepository

# Stateless, so these module-level instances serve every resolver.
_application_repository = ApplicationRepository()
_approval_request_repository = ApprovalRequestRepository()
_mentorship_email_repository = MentorshipEmailRepository()
_user_permissions_repository = UserPermissionsRepository()


@register_recipients(MentorshipEvent.MENTOR_ADMITTED, subject_type="application")
async def _admitted_applicant(session: AsyncSession, event: EventEntity) -> set[int]:
    """The admitted person, and nobody else.

    Staff are not recipients here: the accompanying
    ``recruiting.stage_changed`` already tells the pipeline that the
    application moved, and this event exists to reach the person outside the
    company.

    Safe only because the event is always recorded with ``actor_id=None``.
    ``record_event`` discards the actor from the recipients, and on the
    auto-hire paths the acting user *is* this applicant -- recording them as
    the actor would leave nobody to notify, silently.

    Args:
        session (AsyncSession): Session inside the caller's open transaction.
        event (EventEntity): The admission event; its subject is the
            application.

    Returns:
        set[int]: The applicant's user id, or empty if the application is gone.
    """
    application = await _application_repository.get_by_id(session, event.subject_id)
    return set() if application is None else {application.user_id}


@register_recipients(
    MentorshipEvent.MATCHING_RUN_COMPLETED, subject_type="mentorship_round"
)
async def _run_starter(session: AsyncSession, event: EventEntity) -> set[int]:
    """Whoever started the run, and nobody else.

    Read from the event's own details rather than looked up: nothing outside
    the run records who asked for it, and by the time this resolves, the run's
    Redis keys are not this function's to reach -- a resolver is handed a
    session and an event, which is the shape that keeps every domain's
    recipients answerable from the database.

    Safe only because the event is recorded with ``actor_id=None``.
    ``record_event`` discards the actor from the recipients, and the actor
    here would be the very person being told.

    Args:
        session (AsyncSession): Session inside the caller's open transaction.
        event (EventEntity): The completion event; its subject is the round.

    Returns:
        set[int]: The starter's user id, or empty when the run carried none --
            a run started by a tool rather than a person has nobody to tell.
    """
    del session
    raw = event.details.get("triggeredByUserId")
    if raw is None:
        return set()
    try:
        return {int(raw)}
    except (TypeError, ValueError):
        return set()


async def _approval_request(session: AsyncSession, event: EventEntity):
    """The approval request an event names in ``details["requestId"]``.

    Raises:
        ValueError: The event names no request, or one that does not exist.
            Failing loudly beats telling nobody about a request.
    """
    request_id = event.details.get("requestId")
    if request_id is None:
        raise ValueError(f"{event.event_type!r} requires details['requestId']")
    row = await _approval_request_repository.get(session, int(request_id))
    if row is None:
        raise ValueError(f"{event.event_type!r} names unknown request {request_id}")
    return row


@register_recipients(
    MentorshipEvent.APPROVAL_REQUESTED, subject_type="mentorship_round"
)
async def _approval_reviewer(session: AsyncSession, event: EventEntity) -> set[int]:
    """The reviewer the request names: it is waiting on them.

    Args:
        session (AsyncSession): Session inside the caller's open transaction.
        event (EventEntity): The event; its subject is the round.

    Returns:
        set[int]: The reviewer's user id.
    """
    return {(await _approval_request(session, event)).reviewer_id}


@register_recipients(
    MentorshipEvent.APPROVAL_REASSIGNED, subject_type="mentorship_round"
)
async def _approval_new_reviewer(session: AsyncSession, event: EventEntity) -> set[int]:
    """The reviewer the request was handed to. Read after the move, so the
    row already names them; the reviewer it was taken from is not told.

    Args:
        session (AsyncSession): Session inside the caller's open transaction.
        event (EventEntity): The event; its subject is the round.

    Returns:
        set[int]: The new reviewer's user id.
    """
    return {(await _approval_request(session, event)).reviewer_id}


@register_recipients(MentorshipEvent.APPROVAL_DECIDED, subject_type="mentorship_round")
async def _approval_other_side(session: AsyncSession, event: EventEntity) -> set[int]:
    """Whoever the closing of a request is news to: the raiser when the
    reviewer decided it, the reviewer when the raiser withdrew it.

    Args:
        session (AsyncSession): Session inside the caller's open transaction.
        event (EventEntity): The event; ``details["decision"]`` is approved,
            rejected or withdrawn.

    Returns:
        set[int]: One user id.
    """
    row = await _approval_request(session, event)
    if event.details.get("decision") == "withdrawn":
        return {row.reviewer_id}
    return {row.raised_by}


@register_recipients(
    MentorshipEvent.EMAIL_SEND_PREPARED,
    subject_type=MENTORSHIP_EMAIL_SEND_SUBJECT_TYPE,
)
async def _send_creator(session: AsyncSession, event: EventEntity) -> set[int]:
    """Whoever created the Kit send, and nobody else.

    Safe only because the event is recorded with ``actor_id=None``; the
    creator is the person being told.

    Args:
        session (AsyncSession): Session inside the caller's open transaction.
        event (EventEntity): The event; its subject is the send.

    Returns:
        set[int]: The creator's user id, or empty if the send is gone.
    """
    send = await _mentorship_email_repository.get_send(session, event.subject_id)
    return set() if send is None else {send.created_by}


@register_recipients(MentorshipEvent.EMAIL_RECEIVED, subject_type=INBOX_SUBJECT_TYPE)
async def _participant_email_senders_else_writers(
    session: AsyncSession, event: EventEntity
) -> set[int]:
    """Whoever wrote into the thread through Purrf, else every mentorship writer.

    A thread assigned from the Inbox before anyone answered has no one
    waiting on the reply, so everyone who may answer it is told.

    Args:
        session (AsyncSession): Session inside the caller's open transaction.
        event (EventEntity): The event; its subject is the email thread.

    Returns:
        set[int]: The senders, or the active MENTORSHIP_ADMIN_WRITE holders.
    """

    async def writers():
        holders = await _user_permissions_repository.get_active_users_with_permission(
            session, Permission.MENTORSHIP_ADMIN_WRITE
        )
        return [user.user_id for user in holders]

    return await thread_senders_else(session, event.subject_id, writers)


@register_recipients(MentorshipEvent.EMAIL_BOUNCED, subject_type=INBOX_SUBJECT_TYPE)
async def _participant_email_senders(
    session: AsyncSession, event: EventEntity
) -> set[int]:
    """Whoever wrote into the thread through Purrf; nobody when no one did.

    Args:
        session (AsyncSession): Session inside the caller's open transaction.
        event (EventEntity): The event; its subject is the email thread.

    Returns:
        set[int]: The senders.
    """
    return await thread_senders(session, event.subject_id)
