import unittest
from datetime import datetime, timedelta


from backend.repository.users_repository import UsersRepository
from backend.entity.users_entity import UsersEntity
from backend.entity.training_entity import TrainingEntity
from backend.entity.experience_entity import ExperienceEntity
from backend.common.mentorship_enums import (
    TrainingStatus,
    TrainingCategory,
    UserTimezone,
)
from tests.backend_test.repository_test.base_repository_test_lib import (
    BaseRepositoryTestLib,
)


class TestUsersRepository(BaseRepositoryTestLib):
    async def asyncSetUp(self):
        await super().asyncSetUp()

        now = datetime.utcnow()

        # repo instance
        self.repo = UsersRepository()

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
                alternative_emails=["b1@example.com", "b2@example.com"],
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

        self.user_entity = self.users[0]

        self.experiences = [
            ExperienceEntity(
                user_id=self.users[0].user_id,
                education={"school": "Harvard"},
                work_experience={"company": "OpenAI"},
            ),
            ExperienceEntity(
                user_id=self.users[1].user_id,
                education={"school": "MIT"},
                work_experience={"company": "Google"},
            ),
            # user 3 has no experience
        ]

        await self.insert_entities(self.experiences)

        trainings = [
            TrainingEntity(
                user_id=self.users[0].user_id,
                category=TrainingCategory.CORPORATE_CULTURE_COURSE,
                completed_timestamp=now,
                status=TrainingStatus.TO_DO,
                deadline=now + timedelta(days=7),
                link="http://example.com/1",
            ),
            TrainingEntity(
                user_id=self.users[0].user_id,
                category=TrainingCategory.RESIDENCY_PROGRAM_ONBOARDING,
                completed_timestamp=now,
                status=TrainingStatus.DONE,
                deadline=now + timedelta(days=10),
                link="http://example.com/2",
            ),
            TrainingEntity(
                user_id=self.users[1].user_id,
                category=TrainingCategory.CORPORATE_CULTURE_COURSE,
                completed_timestamp=now,
                status=TrainingStatus.TO_DO,
                deadline=now + timedelta(days=7),
                link="http://example.com/3",
            ),
        ]
        await self.insert_entities(trainings)

    async def test_get_user_by_user_id(self):
        """Test retrieving an existing user by user ID."""
        user = await self.repo.get_user_by_user_id(
            self.session, self.user_entity.user_id
        )

        self.assertEqual(user, self.user_entity)

    async def test_get_user_by_user_id_not_found(self):
        """Test retrieving a non-existent user returns None."""
        user = await self.repo.get_user_by_user_id(self.session, 999)

        self.assertIsNone(user)

    async def test_get_user_by_user_id_is_None(self):
        """Test passing None as user_id returns None."""
        user = await self.repo.get_user_by_user_id(self.session, None)

        self.assertIsNone(user)

    async def test_get_user_by_subject_identifier(self):
        """Test retrieving an existing user by subject identifier"""
        user = await self.repo.get_user_by_subject_identifier(
            self.session, self.user_entity.subject_identifier
        )

        self.assertEqual(user, self.user_entity)

    async def test_get_user_by_subject_identifier_not_found(self):
        """Test retrieving a non-existent subject identifier returns None."""
        user = await self.repo.get_user_by_subject_identifier(self.session, "Sub1")
        self.assertIsNone(user)

        user = await self.repo.get_user_by_subject_identifier(
            self.session, "nonexistent"
        )
        self.assertIsNone(user)

    async def test_get_user_by_subject_identifier_is_None(self):
        """Test passing None as subject identifier returns None."""
        user = await self.repo.get_user_by_subject_identifier(self.session, None)
        self.assertIsNone(user)

        user = await self.repo.get_user_by_subject_identifier(self.session, "")
        self.assertIsNone(user)

    async def test_upsert_users_insert_user_entity(self):
        """Test insert a new UserEntity"""
        new_user = UsersEntity(
            first_name="Dave",
            last_name="New",
            timezone=UserTimezone.ASIA_SHANGHAI,
            communication_channel="email",
            primary_email="dave@example.com",
            is_active=True,
            updated_timestamp=datetime.utcnow(),
            subject_identifier="sub4",
        )

        user_in_db = await self.repo.get_user_by_subject_identifier(
            self.session, new_user.subject_identifier
        )
        self.assertIsNone(user_in_db)

        inserted_user = await self.repo.upsert_users(self.session, new_user)

        self.assertIsNotNone(inserted_user.user_id)

    async def test_upsert_users_update_user_entity(self):
        """Test update a existed UserEntity"""
        updated_entity = UsersEntity(
            user_id=self.user_entity.user_id,
            is_active=False,
        )
        user = await self.repo.upsert_users(self.session, updated_entity)

        self.assertFalse(user.is_active)
        self.assertEqual(user.subject_identifier, self.user_entity.subject_identifier)

    async def test_get_training_by_user_id_existing(self):
        """Test retrieving TrainingEntities for an existing user ID"""
        result = await self.repo.get_training_by_user_id(
            self.session, self.users[0].user_id
        )

        self.assertEqual(len(result), 2)
        self.assertTrue(all(t.user_id == self.users[0].user_id for t in result))

    async def test_get_training_by_user_id_non_existent(self):
        """Test pass a non-existent user ID returns an empty list"""
        result = await self.repo.get_training_by_user_id(self.session, 9999)
        self.assertEqual(result, [])


if __name__ == "__main__":
    unittest.main()
