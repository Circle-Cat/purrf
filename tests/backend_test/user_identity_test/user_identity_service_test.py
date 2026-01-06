import unittest
from unittest.mock import AsyncMock
from datetime import datetime, timezone

from backend.user_identity.user_identity_service import UserIdentityService
from backend.entity.users_entity import UsersEntity
from backend.common.mentorship_enums import UserTimezone, CommunicationMethod


class TestUserIdentityService(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.repo = AsyncMock()
        self.session = AsyncMock()

        self.service = UserIdentityService(self.repo)

        self.users_entity = UsersEntity(
            first_name="Alice",
            last_name="Admin",
            timezone=UserTimezone.ASIA_SHANGHAI,
            timezone_updated_at=datetime.now(timezone.utc),
            communication_channel=CommunicationMethod.EMAIL,
            primary_email="alice@example.com",
            is_active=True,
            updated_timestamp=datetime.now(timezone.utc),
        )

    async def test_get_user_by_subject_identifier(self):
        """Test retrieve a existing users entity by subject."""
        self.repo.get_user_by_subject_identifier.return_value = self.users_entity
        result = await self.service.get_user_by_subject_identifier(
            self.session, self.users_entity.subject_identifier
        )

        self.assertIs(result, self.users_entity)
        self.assertEqual(
            result.subject_identifier, self.users_entity.subject_identifier
        )
        self.repo.get_user_by_subject_identifier.assert_awaited_once_with(
            self.session, self.users_entity.subject_identifier
        )

    async def test_get_user_by_subject_identifier_not_found(self):
        """Test passing an invalid subject returns None."""
        self.repo.get_user_by_subject_identifier.return_value = None

        result = await self.service.get_user_by_subject_identifier(
            self.session, "non-existent-sub"
        )

        self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()
