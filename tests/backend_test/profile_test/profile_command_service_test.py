import unittest
from unittest.mock import AsyncMock, MagicMock

from sqlalchemy.ext.asyncio import AsyncSession

from backend.profile.profile_command_service import ProfileCommandService
from backend.entity.users_entity import UsersEntity
from backend.dto.user_context_dto import UserContextDto
from backend.common.user_role import UserRole


class TestProfileCommandService(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.users_repository = AsyncMock()
        self.logger = MagicMock()

        self.service = ProfileCommandService(
            users_repository=self.users_repository, logger=self.logger
        )

        self.session = AsyncMock(spec=AsyncSession)

        self.user_info = UserContextDto(
            sub="sub123", primary_email="alice@example.com", roles=[UserRole.MENTORSHIP]
        )

    async def test_create_user_new_record_success(self):
        """Scenario: user does not exist, create a brand new record."""
        # Repository returns None to indicate no historical record found
        self.users_repository.get_user_by_primary_email.return_value = None

        # Repository returns the saved entity
        mock_saved_user = UsersEntity(
            user_id=99,
            subject_identifier=self.user_info.sub,
            primary_email=self.user_info.primary_email,
        )
        self.users_repository.upsert_users.return_value = mock_saved_user

        result = await self.service.create_user(self.session, self.user_info)

        self.users_repository.get_user_by_primary_email.assert_awaited_once_with(
            self.session, self.user_info.primary_email
        )
        self.users_repository.upsert_users.assert_awaited_once()

        called_user = self.users_repository.upsert_users.await_args[0][1]
        self.assertEqual(called_user.subject_identifier, self.user_info.sub)
        self.assertEqual(result.user_id, 99)

    async def test_create_user_sync_existing_success(self):
        """Scenario: historical user exists by email only, perform sync logic."""
        # Simulate an existing historical record created by manual backfill
        # where subject_identifier is not the real Auth provider sub
        existing_user = UsersEntity(
            user_id=10,
            subject_identifier="",
            primary_email=self.user_info.primary_email,
            first_name="Old",
            last_name="Name",
        )
        self.users_repository.get_user_by_primary_email.return_value = existing_user

        # Return the same entity after upsert
        self.users_repository.upsert_users.side_effect = lambda s, u: u

        result = await self.service.create_user(self.session, self.user_info)

        self.users_repository.get_user_by_primary_email.assert_awaited_once()

        # Verify upsert is called with the original entity and updated sub
        self.users_repository.upsert_users.assert_awaited_once()
        updated_user = self.users_repository.upsert_users.await_args[0][1]

        self.assertEqual(updated_user.user_id, 10)
        self.assertEqual(updated_user.subject_identifier, "sub123")
        self.assertEqual(result.user_id, 10)

    async def test_sync_user_subject_identifier_fail_logs_error(self):
        """Scenario: database error occurs during sync."""
        existing_user = UsersEntity(user_id=10, primary_email="alice@example.com")
        self.users_repository.get_user_by_primary_email.return_value = existing_user

        self.users_repository.upsert_users.side_effect = Exception("DB Error")

        result = await self.service._sync_user_subject_identifier(
            self.session, "alice@example.com", "sub123"
        )

        self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()
