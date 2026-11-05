import unittest
from unittest.mock import AsyncMock, Mock, patch

from backend.common.ops_enums import OPS_ALERT_SUBJECT_TYPE, OpsEvent
from backend.notification_management import recipient_registry
from backend.ops import recipient_resolvers  # noqa: F401 (registers)
from backend.repository.user_permissions_repository import UserPermissionsRepository


class OpsAlertRecipientsTest(unittest.IsolatedAsyncioTestCase):
    async def test_recipients_are_the_holders_of_ops_maintain(self):
        session = Mock()
        event = Mock(
            event_type=OpsEvent.GMAIL_SYNC_ALERT, subject_type=OPS_ALERT_SUBJECT_TYPE
        )
        with patch.object(
            UserPermissionsRepository,
            "get_active_users_with_permission",
            new_callable=AsyncMock,
            return_value=[Mock(user_id=11), Mock(user_id=12)],
        ) as lookup:
            recipients = await recipient_registry.resolve_recipients(session, event)

        self.assertEqual(recipients, {11, 12})
        lookup.assert_awaited_once_with(session, "ops.maintain")


if __name__ == "__main__":
    unittest.main()
