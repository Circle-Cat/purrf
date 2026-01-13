import unittest
from unittest.mock import AsyncMock, MagicMock
from backend.mentorship.registration_service import RegistrationService
from backend.dto.registration_create_dto import (
    RegistrationCreateDto,
    GlobalPreferencesDto,
    RoundPreferencesDto,
)
from backend.dto.preference_dto import SpecificIndustryDto, SkillsetsDto
from backend.entity.preference_entity import PreferenceEntity


class TestRegistrationService(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.mock_repo = MagicMock()
        self.mock_repo.get_preferences_by_user_id = AsyncMock()
        self.mock_repo.upsert_preference = AsyncMock()

        self.mock_logger = MagicMock()
        self.mock_session = MagicMock()

        self.service = RegistrationService(
            logger=self.mock_logger, preferences_repository=self.mock_repo
        )

        self.sample_dto = RegistrationCreateDto(
            global_preferences=GlobalPreferencesDto(
                specific_industry=SpecificIndustryDto(swe=True, uiux=False),
                skillsets=SkillsetsDto(project_management=True, networking=False),
            ),
            round_preferences=RoundPreferencesDto(
                participant_role="mentee", max_partners=1
            ),
        )
        self.user_id = 123

    async def test_update_preferences_new_user(self):
        """Test: When the user does not have existing preferences, create a new entity."""

        self.mock_repo.get_preferences_by_user_id.return_value = None
        self.mock_repo.upsert_preference.return_value = {"status": "success"}

        await self.service.update_skill_and_industry_preferences(
            session=self.mock_session, user_id=self.user_id, data=self.sample_dto
        )

        self.mock_repo.get_preferences_by_user_id.assert_called_once_with(
            session=self.mock_session, user_id=self.user_id
        )
        _, kwargs = self.mock_repo.upsert_preference.call_args
        upserted_entity = kwargs["entity"]

        self.assertIsInstance(upserted_entity, PreferenceEntity)
        self.assertEqual(upserted_entity.user_id, self.user_id)
        self.assertTrue(upserted_entity.project_management)
        self.assertEqual(
            upserted_entity.specific_industry,
            {"swe": True, "uiux": False, "ds": False, "pm": False},
        )

    async def test_update_preferences_existing_user(self):
        """Test: When the user already has preferences, update the existing entity."""
        existing_entity = PreferenceEntity(
            user_id=self.user_id, project_management=False
        )
        self.mock_repo.get_preferences_by_user_id.return_value = existing_entity

        await self.service.update_skill_and_industry_preferences(
            session=self.mock_session, user_id=self.user_id, data=self.sample_dto
        )

        self.assertTrue(existing_entity.project_management)
        self.mock_repo.upsert_preference.assert_called_once_with(
            session=self.mock_session, entity=existing_entity
        )

    async def test_update_preferences_clears_industry_if_none(self):
        """Test: When specific industry is None, the database field should be cleared."""
        self.sample_dto.global_preferences.specific_industry = None

        existing_entity = PreferenceEntity(
            user_id=self.user_id, specific_industry={"old": "data"}
        )
        self.mock_repo.get_preferences_by_user_id.return_value = existing_entity

        await self.service.update_skill_and_industry_preferences(
            session=self.mock_session, user_id=self.user_id, data=self.sample_dto
        )

        self.assertIsNone(existing_entity.specific_industry)


if __name__ == "__main__":
    unittest.main()
