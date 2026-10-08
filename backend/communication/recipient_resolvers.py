"""Who hears about Inbox events.

Importing this module registers the resolvers. ``fast_app_factory`` imports it
once at startup for that side effect. ASSIGNED, UNASSIGNED, ARCHIVED,
UNARCHIVED and MOVED have no resolver: they stay on the trail and notify nobody.
"""

from sqlalchemy.ext.asyncio import AsyncSession

from backend.common.communication_enums import InboxService
from backend.common.inbox_enums import INBOX_SUBJECT_TYPE, InboxEvent
from backend.common.permissions import Permission
from backend.entity.event_entity import EventEntity
from backend.notification_management.recipient_registry import register_recipients
from backend.repository.user_permissions_repository import UserPermissionsRepository

_permissions = UserPermissionsRepository()

_SERVICE_PERMISSION = {
    InboxService.MENTORSHIP: Permission.MENTORSHIP_ADMIN_WRITE,
    InboxService.RECRUITING: Permission.RECRUITING_APPLICATION_ADVANCE,
    InboxService.INQUIRIES: Permission.INQUIRIES_MANAGE,
}


@register_recipients(InboxEvent.NEEDS_REPLY, subject_type=INBOX_SUBJECT_TYPE)
async def _service_holders(session: AsyncSession, event: EventEntity) -> set[int]:
    """Everyone who holds the permission of the thread's service.

    Args:
        session (AsyncSession): Session inside the caller's open transaction.
        event (EventEntity): The event; ``details["service"]`` names the service.

    Returns:
        set[int]: Active holders; super-admins are included, blocked users not.

    Raises:
        ValueError: If the event names no known service.
    """
    service = event.details.get("service")
    if service not in _SERVICE_PERMISSION:
        raise ValueError(f"{event.event_type!r} names unknown service {service!r}")
    holders = await _permissions.get_active_users_with_permission(
        session, _SERVICE_PERMISSION[InboxService(service)]
    )
    return {user.user_id for user in holders}


@register_recipients(InboxEvent.BOUNCED, subject_type=INBOX_SUBJECT_TYPE)
async def _bounced_sender(session: AsyncSession, event: EventEntity) -> set[int]:
    """Whoever sent the message that bounced, through Purrf; nobody if unknown.

    Args:
        session (AsyncSession): Unused; the sender is in ``details``.
        event (EventEntity): The event; ``details["senderUserId"]`` names the sender.

    Returns:
        set[int]: The sender, or empty.
    """
    del session
    sender = event.details.get("senderUserId")
    return {sender} if sender is not None else set()
