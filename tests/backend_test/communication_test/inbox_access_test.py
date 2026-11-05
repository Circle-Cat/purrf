import unittest

from backend.common.communication_enums import InboxService
from backend.common.permissions import Permission
from backend.communication.inbox_access import (
    INBOX_GATE,
    SERVICE_PERMISSION,
    visible_services,
)
from backend.dto.user_context_dto import UserContextDto


def _user(*permissions):
    return UserContextDto(
        sub="s", primary_email="x@example.com", permissions=frozenset(permissions)
    )


class InboxAccessTest(unittest.TestCase):
    def test_each_service_has_one_permission(self):
        self.assertEqual(
            SERVICE_PERMISSION,
            {
                InboxService.MENTORSHIP: Permission.MENTORSHIP_ADMIN_WRITE,
                InboxService.RECRUITING: Permission.RECRUITING_APPLICATION_ADVANCE,
                InboxService.INQUIRIES: Permission.INQUIRIES_MANAGE,
            },
        )

    def test_the_gate_is_any_of_the_three(self):
        self.assertEqual(
            INBOX_GATE,
            [
                Permission.MENTORSHIP_ADMIN_WRITE,
                Permission.RECRUITING_APPLICATION_ADVANCE,
                Permission.INQUIRIES_MANAGE,
            ],
        )

    def test_visible_services_follow_permissions_in_enum_order(self):
        user = _user(Permission.INQUIRIES_MANAGE, Permission.MENTORSHIP_ADMIN_WRITE)

        self.assertEqual(
            visible_services(user), [InboxService.MENTORSHIP, InboxService.INQUIRIES]
        )

    def test_read_only_mentorship_admin_sees_nothing(self):
        self.assertEqual(visible_services(_user(Permission.MENTORSHIP_ADMIN_READ)), [])


if __name__ == "__main__":
    unittest.main()
