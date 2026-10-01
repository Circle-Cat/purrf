"""Who hears about operations events.

Importing this module registers the resolver. ``fast_app_factory`` imports it
once at startup for that side effect.
"""

from sqlalchemy.ext.asyncio import AsyncSession

from backend.common.ops_enums import OPS_ALERT_SUBJECT_TYPE, OpsEvent
from backend.common.permissions import Permission
from backend.entity.event_entity import EventEntity
from backend.notification_management.recipient_registry import register_recipients
from backend.repository.user_permissions_repository import UserPermissionsRepository

# Stateless, so one module-level instance serves every resolver.
_permissions = UserPermissionsRepository()


@register_recipients(OpsEvent.GMAIL_SYNC_ALERT, subject_type=OPS_ALERT_SUBJECT_TYPE)
async def _ops_maintain_holders(session: AsyncSession, event: EventEntity) -> set[int]:
    """Everyone who currently holds ops.maintain.

    Args:
        session (AsyncSession): Session inside the caller's open transaction.
        event (EventEntity): The ``ops.gmail_sync_alert`` event.

    Returns:
        set[int]: Active holders; super-admins are included, blocked users not.
    """
    holders = await _permissions.get_active_users_with_permission(
        session, Permission.OPS_MAINTAIN
    )
    return {user.user_id for user in holders}
