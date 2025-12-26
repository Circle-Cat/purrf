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

        self.dummy_users = [
            UsersEntity(
                first_name="Alice",
                last_name="Admin",
                timezone=UserTimezone.ASIA_SHANGHAI,
                timezone_updated_at=self.now,
                communication_channel=CommunicationMethod.EMAIL,
                primary_email="alice@example.com",
                subject_identifier=str(uuid.uuid4()),
                is_active=True,
                updated_timestamp=self.now,
            ),
            UsersEntity(
                first_name="Bob",
                last_name="Smith",
                timezone=UserTimezone.AMERICA_NEW_YORK,
                timezone_updated_at=self.now,
                communication_channel=CommunicationMethod.EMAIL,
                primary_email="bob@example.com",
                subject_identifier=str(uuid.uuid4()),
                is_active=True,
                updated_timestamp=self.now,
            ),
        ]

        await self.insert_entities(self.dummy_users)

        self.dummy_preferences = PreferenceEntity(
            user_id=self.dummy_users[0].user_id,
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
            self.session, self.dummy_users[0].user_id
        )

        self.assertIsNotNone(result)
        self.assertEqual(result.user_id, self.dummy_users[0].user_id)
        self.assertTrue(result.resume_guidance)
        self.assertFalse(result.technical_skills)
        self.assertEqual(
            result.specific_industry, self.dummy_preferences.specific_industry
        )

    async def test_get_preferences_by_user_id_non_existent(self):
        """Test passing a non-existent user ID returns None"""
        result = await self.repo.get_preferences_by_user_id(self.session, 9999)

        self.assertIsNone(result)

    async def test_upsert_new_preference(self):
        """Test inserting a new PreferenceEntity"""
        new_preference = PreferenceEntity(
            user_id=self.dummy_users[1].user_id, resume_guidance=True
        )

        result = await self.repo.upsert_preference(self.session, new_preference)

        self.assertIsNotNone(result.preferences_id)
        self.assertEqual(result.user_id, self.dummy_users[1].user_id)

    async def test_upsert_existing_preference(self):
        """Test updating a existing PreferenceEntity"""
        self.dummy_preferences.soft_skills = False

        result = await self.repo.upsert_preference(self.session, self.dummy_preferences)
        self.assertFalse(result.soft_skills)
        self.assertEqual(result.user_id, self.dummy_users[0].user_id)


if __name__ == "__main__":
    unittest.main()
