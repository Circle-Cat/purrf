import unittest
from unittest.mock import AsyncMock
from datetime import datetime

from backend.common.constants import ProfileField
from backend.common.mentorship_enums import CommunicationMethod, UserTimezone
from backend.dto.profile_dto import ProfileDto
from backend.dto.users_dto import UsersDto
from backend.dto.user_context_dto import UserContextDto
from backend.profile.profile_service import ProfileService
from backend.profile.profile_query_service import ProfileQueryService
from backend.profile.profile_command_service import ProfileCommandService


class TestProfileService(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.query_service = AsyncMock(spec=ProfileQueryService)
        self.command_service = AsyncMock(spec=ProfileCommandService)
        self.session = AsyncMock()

        self.service = ProfileService(
            query_service=self.query_service,
            command_service=self.command_service,
        )

        self.user_context = UserContextDto(
            sub="user_sub", primary_email="user@example.com"
        )

        self.user_dto = UsersDto(
            id=1,
            first_name="Alice",
            last_name="Smith",
            preferred_name="Ally",
            timezone=UserTimezone.AMERICA_LOS_ANGELES,
            communication_method=CommunicationMethod.EMAIL,
            timezone_updated_at=datetime.now(),
            updated_timestamp=datetime.now(),
            primary_email="alice@example.com",
            alternative_emails=[],
            linkedin_link=None,
        )

        self.profile_dto = ProfileDto(
            id=1, user=self.user_dto, training=[], work_history=[], education=[]
        )

    async def test_get_profile_user_exists(self):
        """Test when user exists, query_service.get_profile returns profile."""
        self.query_service.get_profile.return_value = self.profile_dto

        profile = await self.service.get_profile(
            session=self.session, user_context=self.user_context
        )

        self.query_service.get_profile.assert_awaited_once_with(
            session=self.session,
            user_sub="user_sub",
            include_training=True,
            include_work_history=True,
            include_education=True,
        )
        self.assertEqual(profile, self.profile_dto)
        self.command_service.create_user.assert_not_awaited()
        self.session.commit.assert_not_awaited()

    async def test_get_profile_user_not_exists_creates_user(self):
        """Test when user does not exist, command_service.create_user is called."""
        self.query_service.get_profile.side_effect = [None, self.profile_dto]
        self.command_service.create_user.return_value = self.user_dto

        profile = await self.service.get_profile(
            session=self.session, user_context=self.user_context
        )

        self.command_service.create_user.assert_awaited_once_with(
            self.session, self.user_context
        )
        self.assertEqual(self.query_service.get_profile.await_count, 2)
        self.assertEqual(profile, self.profile_dto)
        self.session.commit.assert_awaited_once()

    async def test_get_profile_with_fields(self):
        """Test requesting only specific fields."""
        self.query_service.get_profile.return_value = self.profile_dto

        profile = await self.service.get_profile(
            session=self.session,
            user_context=self.user_context,
            fields={ProfileField.TRAINING, ProfileField.WORK_HISTORY},
        )

        self.query_service.get_profile.assert_awaited_once_with(
            session=self.session,
            user_sub="user_sub",
            include_training=True,
            include_work_history=True,
            include_education=False,
        )
        self.assertEqual(profile, self.profile_dto)
        self.command_service.create_user.assert_not_awaited()
        self.session.commit.assert_not_awaited()


if __name__ == "__main__":
    unittest.main()
