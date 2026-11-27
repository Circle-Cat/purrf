"""Who needs to know about each leave request event.

The same rule every approval follows: a filed request goes to the manager it
waits on, a decision goes to the employee, and a withdrawal goes back to the
manager. Recipients come from the approval row the event names.

Sick leave approved on submission has no approval row; its manager is read off
the request itself, and it goes to the employee as well: no decision reaches
them otherwise. An admin adjustment goes to the person whose balance it is.

Importing this module registers every resolver. ``fast_app_factory`` imports
it once at startup for that side effect.
"""

from sqlalchemy.ext.asyncio import AsyncSession

from backend.common.approval_enums import ApprovalRequestStatus
from backend.common.leave_enums import (
    LEAVE_LEDGER_SUBJECT,
    LEAVE_REQUEST_SUBJECT,
    LeaveEvent,
)
from backend.entity.event_entity import EventEntity
from backend.notification_management.recipient_registry import register_recipients
from backend.repository.approval_request_repository import (
    ApprovalRequestRepository,
)
from backend.repository.leave_ledger_repository import LeaveLedgerRepository
from backend.repository.leave_request_repository import LeaveRequestRepository

# Stateless, so one module-level instance serves every resolver.
_approval_request_repository = ApprovalRequestRepository()
_leave_request_repository = LeaveRequestRepository()
_leave_ledger_repository = LeaveLedgerRepository()


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


@register_recipients(LeaveEvent.REQUEST_SUBMITTED, subject_type=LEAVE_REQUEST_SUBJECT)
async def _the_manager(session: AsyncSession, event: EventEntity) -> set[int]:
    """The manager the request waits on.

    Args:
        session (AsyncSession): Session inside the caller's open transaction.
        event (EventEntity): The event; its subject is the leave request.

    Returns:
        set[int]: The manager's user id.
    """
    return {(await _approval_request(session, event)).reviewer_id}


@register_recipients(LeaveEvent.REQUEST_DECIDED, subject_type=LEAVE_REQUEST_SUBJECT)
async def _the_other_side(session: AsyncSession, event: EventEntity) -> set[int]:
    """The employee once their manager has decided; the manager when the
    employee withdrew it.

    Args:
        session (AsyncSession): Session inside the caller's open transaction.
        event (EventEntity): The event; its subject is the leave request.

    Returns:
        set[int]: The one person waiting on the outcome.
    """
    row = await _approval_request(session, event)
    if event.details.get("decision") == ApprovalRequestStatus.WITHDRAWN.value:
        return {row.reviewer_id}
    return {row.raised_by}


@register_recipients(
    LeaveEvent.SICK_LEAVE_AUTO_APPROVED, subject_type=LEAVE_REQUEST_SUBJECT
)
async def _both_sides(session: AsyncSession, event: EventEntity) -> set[int]:
    """The manager the sick leave was filed with, and the employee.

    Nobody decided it, so the event has no actor and nobody is subtracted:
    the employee hears that it went through just as the manager hears that it
    happened.

    Args:
        session (AsyncSession): Session inside the caller's open transaction.
        event (EventEntity): The event; its subject is the leave request.

    Returns:
        set[int]: The manager's and the employee's user ids.

    Raises:
        ValueError: The request does not exist. Failing loudly beats telling
            nobody.
    """
    leave = await _leave_request_repository.get_by_id(session, event.subject_id)
    if leave is None:
        raise ValueError(
            f"{event.event_type!r} names unknown leave request {event.subject_id}"
        )
    return {leave.approver_user_id, leave.user_id}


@register_recipients(LeaveEvent.BALANCE_ADJUSTED, subject_type=LEAVE_LEDGER_SUBJECT)
async def _the_balance_owner(session: AsyncSession, event: EventEntity) -> set[int]:
    """The person whose balance the adjustment changed.

    Args:
        session (AsyncSession): Session inside the caller's open transaction.
        event (EventEntity): The event; its subject is the ledger row.

    Returns:
        set[int]: That person's user id.

    Raises:
        ValueError: The row does not exist. Failing loudly beats telling
            nobody.
    """
    entry = await _leave_ledger_repository.get_by_id(session, event.subject_id)
    if entry is None:
        raise ValueError(
            f"{event.event_type!r} names unknown ledger row {event.subject_id}"
        )
    return {entry.user_id}
