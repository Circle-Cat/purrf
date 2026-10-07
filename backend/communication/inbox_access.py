"""Which permission covers each Inbox service, and so who sees which threads."""

from backend.common.communication_enums import InboxService
from backend.common.permissions import Permission
from backend.dto.user_context_dto import UserContextDto

SERVICE_PERMISSION: dict[InboxService, Permission] = {
    InboxService.MENTORSHIP: Permission.MENTORSHIP_ADMIN_WRITE,
    InboxService.RECRUITING: Permission.RECRUITING_APPLICATION_ADVANCE,
    InboxService.INQUIRIES: Permission.INQUIRIES_MANAGE,
}

# Any one of these opens the Inbox; each thread is then checked by its service.
INBOX_GATE: list[Permission] = list(SERVICE_PERMISSION.values())


def visible_services(user: UserContextDto) -> list[InboxService]:
    """The services whose threads ``user`` may see, in enum order.

    Args:
        user (UserContextDto): The viewer.

    Returns:
        list[InboxService]: Empty when the viewer holds none of the permissions.
    """
    return [s for s in InboxService if user.has_permission(SERVICE_PERMISSION[s])]
