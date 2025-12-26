import unittest
from unittest.mock import AsyncMock, MagicMock

from backend.profile.profile_query_service import ProfileQueryService


class TestProfileQueryService(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.mock_users_repo = MagicMock()
        self.mock_experience_repo = MagicMock()
        self.mock_training_repo = MagicMock()
        self.mock_mapper = MagicMock()

        self.service = ProfileQueryService(
            users_repository=self.mock_users_repo,
            experience_repository=self.mock_experience_repo,
            training_repository=self.mock_training_repo,
            profile_mapper=self.mock_mapper,
        )

        self.session = AsyncMock()
        self.user_sub = "auth0|123"
        self.user_id = 99

    async def test_get_profile_user_not_found(self):
        """When the user does not exist, the method should return None immediately."""
        self.mock_users_repo.get_user_by_subject_identifier = AsyncMock(
            return_value=None
        )

        result = await self.service.get_profile(
            self.session, self.user_sub, True, True, True
        )

        self.assertIsNone(result)
        self.mock_experience_repo.get_experience_by_user_id.assert_not_called()
        self.mock_training_repo.get_training_by_user_id.assert_not_called()

    async def test_get_profile_full_load(self):
        """Load a full profile when all include flags are True."""
        mock_user = MagicMock()
        mock_user.user_id = self.user_id
        self.mock_users_repo.get_user_by_subject_identifier = AsyncMock(
            return_value=mock_user
        )

        mock_exp = MagicMock()
        mock_trainings = [MagicMock(), MagicMock()]
        self.mock_experience_repo.get_experience_by_user_id = AsyncMock(
            return_value=mock_exp
        )
        self.mock_training_repo.get_training_by_user_id = AsyncMock(
            return_value=mock_trainings
        )

        mock_dto = MagicMock()
        self.mock_mapper.map_to_profile_dto.return_value = mock_dto

        result = await self.service.get_profile(
            self.session,
            self.user_sub,
            include_training=True,
            include_work_history=True,
            include_education=True,
        )

        self.assertEqual(result, mock_dto)
        self.mock_experience_repo.get_experience_by_user_id.assert_called_once_with(
            self.session, self.user_id
        )
        self.mock_training_repo.get_training_by_user_id.assert_called_once_with(
            self.session, self.user_id
        )
        self.mock_mapper.map_to_profile_dto.assert_called_once_with(
            user=mock_user,
            experience=mock_exp,
            trainings=mock_trainings,
            include_work_history=True,
            include_education=True,
        )

    async def test_get_profile_only_user(self):
        """Load only the user without any related data."""
        mock_user = MagicMock()
        mock_user.user_id = self.user_id
        self.mock_users_repo.get_user_by_subject_identifier = AsyncMock(
            return_value=mock_user
        )

        await self.service.get_profile(
            self.session,
            self.user_sub,
            include_training=False,
            include_work_history=False,
            include_education=False,
        )

        self.mock_experience_repo.get_experience_by_user_id.assert_not_called()
        self.mock_training_repo.get_training_by_user_id.assert_not_called()
        self.mock_mapper.map_to_profile_dto.assert_called_once_with(
            user=mock_user,
            experience=None,
            trainings=None,
            include_work_history=False,
            include_education=False,
        )

    async def test_get_profile_include_education_triggers_experience_repo(self):
        """Even if work history is excluded, including education should still trigger
        the experience repository call.
        """
        mock_user = MagicMock()
        mock_user.user_id = self.user_id
        self.mock_users_repo.get_user_by_subject_identifier = AsyncMock(
            return_value=mock_user
        )
        self.mock_experience_repo.get_experience_by_user_id = AsyncMock(
            return_value=None
        )

        await self.service.get_profile(
            self.session,
            self.user_sub,
            include_training=False,
            include_work_history=False,
            include_education=True,
        )

        self.mock_experience_repo.get_experience_by_user_id.assert_called_once()
        self.mock_training_repo.get_training_by_user_id.assert_not_called()


if __name__ == "__main__":
    unittest.main()
