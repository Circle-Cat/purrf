import unittest
from unittest.mock import AsyncMock, MagicMock
from datetime import datetime, timezone

from backend.user_identity.user_identity_service import UserIdentityService
from backend.entity.users_entity import UsersEntity
from backend.dto.user_context_dto import UserContextDto
from backend.common.user_role import UserRole
from backend.common.mentorship_enums import UserTimezone, CommunicationMethod
from backend.common.constants import (
    INTERNAL_MICROSOFT_ACCOUNT_DOMAIN,
    INTERNAL_GOOGLE_ACCOUNT_DOMAIN,
)


class TestUserIdentityService(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.repo = AsyncMock()
        self.session = AsyncMock()
        self.logger = MagicMock()

        self.service = UserIdentityService(
            logger=self.logger, users_repository=self.repo
        )

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

        self.user_info = UserContextDto(
            sub="sub123", primary_email="alice@example.com", roles=[UserRole.MENTORSHIP]
        )

        self.existing_user = MagicMock(
            spec=UsersEntity,
            user_id=10,
            primary_email=self.user_info.primary_email,
            subject_identifier="",
        )

    async def test_get_user_success(self):
        """Test retrieve a existing users entity by subject."""
        self.repo.get_user_by_subject_identifier.return_value = self.users_entity

        saved_user, should_commit = await self.service.get_user(
            self.session, self.user_info
        )

        self.assertIs(saved_user, self.users_entity)
        self.assertFalse(should_commit)
        self.repo.get_user_by_subject_identifier.assert_awaited_once_with(
            session=self.session, sub=self.user_info.sub
        )
        self.repo.upsert_users.assert_not_awaited()

    async def test_get_user_sync_fail(self):
        """Scenario: sync user raise error, should not try to create new user."""
        self.repo.get_user_by_subject_identifier.return_value = None
        self.repo.get_user_by_primary_email.return_value = self.existing_user

        self.repo.upsert_users.side_effect = Exception("DB Error")

        with self.assertRaises(Exception) as context:
            await self.service.get_user(self.session, self.user_info)

        self.assertEqual(str(context.exception), "DB Error")
        self.logger.error.assert_called_once_with(
            "[UserIdentityService] failed to sync historical user ID %s: %s",
            10,
            "DB Error",
        )
        self.repo.upsert_users.assert_awaited_once()

    async def test_get_user_create_new(self):
        """Scenario: create a new user when no existing user is found."""
        # Repository returns None to indicate no historical record found
        self.repo.get_user_by_subject_identifier.return_value = None
        self.repo.get_user_by_primary_email.return_value = None

        # Repository returns the saved entity
        mock_user = MagicMock(spec=UsersEntity, user_id=99)
        self.repo.upsert_users.return_value = mock_user

        saved_user, should_commit = await self.service.get_user(
            self.session, self.user_info
        )

        self.assertTrue(should_commit)
        self.assertEqual(saved_user.user_id, 99)
        self.repo.upsert_users.assert_awaited_once()

    async def test_get_user_sync_success(self):
        """Scenario: historical user exists by email only, perform sync logic."""
        # Simulate an existing historical record created by manual backfill
        # where subject_identifier is not the real Auth provider sub
        self.repo.get_user_by_subject_identifier.return_value = None
        self.repo.get_user_by_primary_email.return_value = self.existing_user
        self.repo.upsert_users.return_value = self.existing_user

        saved_user, should_commit = await self.service.get_user(
            self.session, self.user_info
        )

        self.assertTrue(should_commit)
        self.assertEqual(saved_user.user_id, 10)
        self.repo.upsert_users.assert_awaited_once()

    async def test_get_user_internal_user_email_conversion(self):
        """Scenario: convert Microsoft email to Google email for internal user."""
        user_info = UserContextDto(
            sub="sub_internal",
            primary_email=f"internal{INTERNAL_MICROSOFT_ACCOUNT_DOMAIN}",
            roles=[UserRole.MENTORSHIP],
        )

        self.repo.get_user_by_subject_identifier.return_value = None
        self.repo.get_user_by_primary_email.return_value = None
        self.repo.upsert_users.return_value = MagicMock(spec=UsersEntity)

        await self.service.get_user(self.session, user_info)

        self.assertTrue(
            self.repo.get_user_by_primary_email.call_args[0][1].endswith(
                INTERNAL_GOOGLE_ACCOUNT_DOMAIN
            )
        )
        self.assertTrue(
            self.repo.upsert_users.call_args[0][1].primary_email.endswith(
                INTERNAL_GOOGLE_ACCOUNT_DOMAIN
            )
        )


if __name__ == "__main__":
    unittest.main()
