import unittest
import uuid
from datetime import datetime, timezone

from backend.repository.preferences_repository import PreferencesRepository
from backend.entity.preference_entity import PreferenceEntity
from backend.entity.users_entity import UsersEntity
from backend.common.mentorship_enums import CommunicationMethod, UserTimezone
from tests.backend_test.repository_test.base_repository_test_lib import (
    BaseRepositoryTestLib,
)


class TestPreferencesRepository(BaseRepositoryTestLib):
    async def asyncSetUp(self):
        await super().asyncSetUp()
        self.repo = PreferencesRepository()

        self.now = datetime.now(timezone.utc)

        self.dummy_user = UsersEntity(
            first_name="Alice",
            last_name="Admin",
            timezone=UserTimezone.ASIA_SHANGHAI,
            timezone_updated_at=self.now,
            communication_channel=CommunicationMethod.EMAIL,
            primary_email="alice@example.com",
            subject_identifier=str(uuid.uuid4()),
            is_active=True,
            updated_timestamp=self.now,
        )

        await self.insert_entities([self.dummy_user])

        self.dummy_preferences = PreferenceEntity(
            user_id=self.dummy_user.user_id,
            resume_guidance=True,
            career_path_guidance=True,
            experience_sharing=False,
            industry_trends=True,
            technical_skills=False,
            soft_skills=True,
            networking=False,
            project_management=True,
            specific_industry={"industry": "Data Science"},
        )

        await self.insert_entities([self.dummy_preferences])

    async def test_get_preferences_by_user_id_existing(self):
        """Test retrieving PreferenceEntity for an existing user ID"""
        result = await self.repo.get_preferences_by_user_id(
            self.session, self.dummy_user.user_id
        )

        self.assertIsNotNone(result)
        self.assertEqual(result.user_id, self.dummy_user.user_id)
        self.assertTrue(result.resume_guidance)
        self.assertFalse(result.technical_skills)
        self.assertEqual(
            result.specific_industry, self.dummy_preferences.specific_industry
        )

    async def test_get_preferences_by_user_id_non_existent(self):
        """Test passing a non-existent user ID returns None"""
        result = await self.repo.get_preferences_by_user_id(self.session, 9999)

        self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()
