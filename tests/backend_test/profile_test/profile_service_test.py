import unittest
from unittest.mock import AsyncMock, MagicMock
from datetime import datetime

from backend.common.constants import ProfileField
from backend.common.mentorship_enums import CommunicationMethod, UserTimezone
from backend.dto.profile_dto import ProfileDto
from backend.dto.users_dto import UsersDto
from backend.dto.user_context_dto import UserContextDto
from backend.profile.profile_service import ProfileService
from backend.dto.profile_create_dto import (
    UsersRequestDto,
    WorkHistoryRequestDto,
    EducationRequestDto,
    ProfileCreateDto,
)


class TestProfileService(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.query_service = AsyncMock()
        self.command_service = AsyncMock()
        self.user_identity_service = AsyncMock()
        self.session = AsyncMock()

        self.service = ProfileService(
            query_service=self.query_service,
            command_service=self.command_service,
            user_identity_service=self.user_identity_service,
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

    async def test_update_profile_all_fields_success(self):
        """Tests a full update where all profile sections are provided and all command methods are called."""
        mock_user_entity = MagicMock()
        mock_user_entity.user_id = 1
        self.user_identity_service.get_user_by_subject_identifier.return_value = (
            mock_user_entity
        )
        self.query_service.get_profile.return_value = self.profile_dto

        update_dto = ProfileCreateDto(
            user=UsersRequestDto(
                first_name="New",
                last_name="Name",
                timezone=UserTimezone.AMERICA_LOS_ANGELES,
                communication_method=CommunicationMethod.EMAIL,
            ),
            education=[MagicMock(spec=EducationRequestDto)],
            work_history=[MagicMock(spec=WorkHistoryRequestDto)],
        )

        result = await self.service.update_profile(
            session=self.session,
            user_sub="user_sub",
            profile=update_dto,
        )

        self.user_identity_service.get_user_by_subject_identifier.assert_awaited_once_with(
            session=self.session, subject="user_sub"
        )

        self.command_service.update_users.assert_awaited_once_with(
            session=self.session,
            latest_profile=update_dto,
            users=mock_user_entity,
        )
        self.command_service.update_education.assert_awaited_once_with(
            session=self.session,
            latest_profile=update_dto,
            user_id=1,
        )
        self.command_service.update_work_history.assert_awaited_once_with(
            session=self.session,
            latest_profile=update_dto,
            user_id=1,
        )

        self.session.commit.assert_awaited_once()
        self.query_service.get_profile.assert_awaited_once_with(
            session=self.session,
            user_sub="user_sub",
            include_training=True,
            include_work_history=True,
            include_education=True,
        )
        self.assertEqual(result, self.profile_dto)

    async def test_update_profile_partial_update_only_user(self):
        """Tests a partial update where only user information is updated."""
        mock_user_entity = MagicMock()
        mock_user_entity.user_id = 1
        self.user_identity_service.get_user_by_subject_identifier.return_value = (
            mock_user_entity
        )
        self.query_service.get_profile.return_value = self.profile_dto

        update_dto = ProfileCreateDto(
            user=UsersRequestDto(
                first_name="Only",
                last_name="User",
                timezone=UserTimezone.AMERICA_LOS_ANGELES,
                communication_method=CommunicationMethod.EMAIL,
            )
        )

        await self.service.update_profile(
            session=self.session,
            user_sub="user_sub",
            profile=update_dto,
        )

        self.command_service.update_users.assert_awaited_once()
        self.command_service.update_education.assert_not_awaited()
        self.command_service.update_work_history.assert_not_awaited()
        self.session.commit.assert_awaited_once()

    async def test_update_profile_empty_dto_skips_commands(self):
        """Tests an empty update where no command methods are called but the transaction is committed."""
        mock_user_entity = MagicMock()
        self.user_identity_service.get_user_by_subject_identifier.return_value = (
            mock_user_entity
        )

        update_dto = ProfileCreateDto()

        await self.service.update_profile(
            session=self.session,
            user_sub="user_sub",
            profile=update_dto,
        )

        self.command_service.update_users.assert_not_awaited()
        self.command_service.update_education.assert_not_awaited()
        self.command_service.update_work_history.assert_not_awaited()

        self.session.commit.assert_awaited_once()
        self.query_service.get_profile.assert_awaited_once()


if __name__ == "__main__":
    unittest.main()
