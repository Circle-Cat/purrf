import unittest
from datetime import datetime

from backend.repository.experience_repository import ExperienceRepository
from backend.entity.users_entity import UsersEntity
from backend.entity.experience_entity import ExperienceEntity
from backend.common.mentorship_enums import UserTimezone
from tests.backend_test.repository_test.base_repository_test_lib import (
    BaseRepositoryTestLib,
)


class TestExperienceRepository(BaseRepositoryTestLib):
    async def asyncSetUp(self):
        await super().asyncSetUp()

        self.repo = ExperienceRepository()

        self.users = [
            UsersEntity(
                first_name="Alice",
                last_name="Admin",
                timezone=UserTimezone.ASIA_SHANGHAI,
                communication_channel="email",
                primary_email="alice@example.com",
                is_active=True,
                updated_timestamp=datetime.utcnow(),
                subject_identifier="sub1",
            ),
            UsersEntity(
                first_name="Bob",
                last_name="Smith",
                timezone=UserTimezone.AMERICA_NEW_YORK,
                communication_channel="slack",
                primary_email="bob@example.com",
                is_active=True,
                updated_timestamp=datetime.utcnow(),
                subject_identifier="sub2",
            ),
            UsersEntity(
                first_name="Charlie",
                last_name="Inactive",
                timezone=UserTimezone.ASIA_SHANGHAI,
                communication_channel="email",
                primary_email="charlie@example.com",
                is_active=False,
                updated_timestamp=datetime.utcnow(),
                subject_identifier="sub3",
            ),
        ]

        await self.insert_entities(self.users)

        self.experiences = [
            ExperienceEntity(
                user_id=self.users[0].user_id,
                education=[{"school": "Harvard"}],
                work_history=[{"company": "OpenAI"}],
            ),
            ExperienceEntity(
                user_id=self.users[1].user_id,
                education=[{"school": "MIT"}],
                work_history=[{"company": "Google"}],
            ),
        ]

        await self.insert_entities(self.experiences)

    async def test_get_experience_by_user_id_existing(self):
        """Test retrieving ExperienceEntity for an existing user ID"""
        result = await self.repo.get_experience_by_user_id(
            self.session, self.users[0].user_id
        )

        self.assertIsNotNone(result)
        self.assertEqual(result.user_id, self.users[0].user_id)

    async def test_get_experience_by_user_id_single(self):
        """Test retrieving a single ExperienceEntity"""
        result = await self.repo.get_experience_by_user_id(
            self.session, self.users[1].user_id
        )

        self.assertIsNotNone(result)
        self.assertEqual(result.user_id, self.users[1].user_id)

    async def test_get_experience_by_user_id_non_existent(self):
        """Test passing a non-existent user ID returns None"""
        result = await self.repo.get_experience_by_user_id(self.session, 9999)

        self.assertIsNone(result)

    async def test_get_experience_by_user_id_is_none(self):
        """Test passing None as user ID returns None"""
        result = await self.repo.get_experience_by_user_id(self.session, None)

        self.assertIsNone(result)

    async def test_upsert_experience_insert_entity(self):
        """Test inset a new ExperienceEntity success"""
        result = await self.repo.upsert_experience(
            self.session,
            ExperienceEntity(
                user_id=self.users[2].user_id,
                education=[{"school": "Cornell"}],
                work_history=[{"company": "IBM"}],
            ),
        )

        self.assertIsNotNone(result.experience_id)
        self.assertEqual(result.user_id, self.users[2].user_id)
        self.assertEqual(result.work_history, [{"company": "IBM"}])

    async def test_upsert_experience_update_entity(self):
        """Test update an existing ExperienceEntity success"""
        result = await self.repo.upsert_experience(
            self.session,
            ExperienceEntity(
                experience_id=self.experiences[1].experience_id,
                user_id=self.users[1].user_id,
                education=[{"school": "Yale"}, {"school": "Stanford"}],
                work_history=[{"company": "Google"}, {"company": "TikTok"}],
            ),
        )

        self.assertEqual(
            result.education,
            [{"school": "Yale"}, {"school": "Stanford"}],
        )
        self.assertEqual(
            result.work_history,
            [{"company": "Google"}, {"company": "TikTok"}],
        )


if __name__ == "__main__":
    unittest.main()
