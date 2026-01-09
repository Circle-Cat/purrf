import unittest
from unittest.mock import AsyncMock, MagicMock

from backend.entity.users_entity import UsersEntity
from backend.dto.user_context_dto import UserContextDto
from backend.dto.profile_dto import ProfileDto
from backend.profile.profile_query_service import ProfileQueryService


class TestProfileQueryService(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.mock_user_identity_service = MagicMock()
        self.mock_user_identity_service.get_user = AsyncMock()

        self.mock_experience_repo = MagicMock()
        self.mock_experience_repo.get_experience_by_user_id = AsyncMock()

        self.mock_training_repo = MagicMock()
        self.mock_training_repo.get_training_by_user_id = AsyncMock()

        self.mock_mapper = MagicMock()

        self.service = ProfileQueryService(
            user_identity_service=self.mock_user_identity_service,
            experience_repository=self.mock_experience_repo,
            training_repository=self.mock_training_repo,
            profile_mapper=self.mock_mapper,
        )

        self.session = AsyncMock()
        self.user_context = UserContextDto(
            sub="auth0|123", primary_email="user@example.com"
        )
        self.user_id = 99
        self.mock_user = MagicMock(spec=UsersEntity, user_id=self.user_id)
        self.mock_profile_dto = MagicMock(spec=ProfileDto, user_id=self.user_id)

    async def test_get_profile_should_commit_true(self):
        """Returns ProfileDto and propagates the should_commit flag from UserIdentityService."""
        self.mock_user_identity_service.get_user.return_value = (
            self.mock_user,
            True,
        )
        self.mock_mapper.map_to_profile_dto.return_value = self.mock_profile_dto

        profile_dto, should_commit = await self.service.get_profile(
            self.session, self.user_context, False, False, False
        )

        self.assertTrue(should_commit)
        self.assertEqual(profile_dto, self.mock_profile_dto)
        self.mock_user_identity_service.get_user.assert_called_once()

    async def test_get_profile_full_load(self):
        """Load a full profile when all include flags are True."""
        self.mock_user_identity_service.get_user.return_value = (
            self.mock_user,
            False,
        )

        mock_exp = MagicMock()
        mock_trainings = [MagicMock(), MagicMock()]
        self.mock_experience_repo.get_experience_by_user_id.return_value = mock_exp
        self.mock_training_repo.get_training_by_user_id.return_value = mock_trainings
        self.mock_mapper.map_to_profile_dto.return_value = self.mock_profile_dto

        profile_dto, _ = await self.service.get_profile(
            self.session,
            self.user_context,
            include_training=True,
            include_work_history=True,
            include_education=True,
        )

        self.assertEqual(profile_dto, self.mock_profile_dto)
        self.mock_experience_repo.get_experience_by_user_id.assert_called_once_with(
            self.session, self.user_id
        )
        self.mock_training_repo.get_training_by_user_id.assert_called_once_with(
            self.session, self.user_id
        )
        self.mock_mapper.map_to_profile_dto.assert_called_once()

    async def test_get_profile_only_user(self):
        """Load only the user without any related data."""
        self.mock_user_identity_service.get_user.return_value = (
            self.mock_user,
            False,
        )
        self.mock_mapper.map_to_profile_dto.return_value = self.mock_profile_dto

        await self.service.get_profile(
            self.session, self.user_context, False, False, False
        )

        self.mock_experience_repo.get_experience_by_user_id.assert_not_called()
        self.mock_training_repo.get_training_by_user_id.assert_not_called()
        self.mock_mapper.map_to_profile_dto.assert_called_once()

    async def test_get_profile_include_education_triggers_experience_repo(self):
        """Even if work history is excluded, including education should still trigger
        the experience repository call.
        """
        self.mock_user_identity_service.get_user.return_value = (
            self.mock_user,
            False,
        )
        self.mock_mapper.map_to_profile_dto.return_value = self.mock_profile_dto

        await self.service.get_profile(
            self.session, self.user_context, False, False, True
        )

        self.mock_experience_repo.get_experience_by_user_id.assert_called_once()
        self.mock_training_repo.get_training_by_user_id.assert_not_called()


if __name__ == "__main__":
    unittest.main()
