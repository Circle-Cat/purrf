import unittest
from datetime import datetime, timedelta, timezone

from backend.repository.training_repository import TrainingRepository
from backend.entity.training_entity import TrainingEntity
from backend.entity.users_entity import UsersEntity
from backend.common.mentorship_enums import (
    TrainingStatus,
    TrainingCategory,
    CommunicationMethod,
)
from tests.backend_test.repository_test.base_repository_test_lib import (
    BaseRepositoryTestLib,
)


class TestTrainingRepository(BaseRepositoryTestLib):
    async def asyncSetUp(self):
        await super().asyncSetUp()
        self.repo = TrainingRepository()

        self.now = datetime.now(timezone.utc)

        dummy_users = [
            UsersEntity(
                first_name="Alice",
                last_name="Admin",
                timezone="Asia/Shanghai",
                timezone_updated_at=self.now,
                communication_channel=CommunicationMethod.EMAIL,
                is_active=True,
                updated_timestamp=self.now,
            ),
            UsersEntity(
                first_name="Bob",
                last_name="MultiRole",
                timezone="America/Los_Angeles",
                timezone_updated_at=self.now,
                communication_channel=CommunicationMethod.EMAIL,
                is_active=True,
                updated_timestamp=self.now,
            ),
        ]
        await self.insert_entities(dummy_users)

        self.user1 = dummy_users[0]
        self.user2 = dummy_users[1]

        trainings = [
            TrainingEntity(
                user_id=self.user1.user_id,
                category=TrainingCategory.CORPORATE_CULTURE_COURSE,
                completed_timestamp=self.now,
                status=TrainingStatus.TO_DO,
                deadline=self.now + timedelta(days=7),
                link="http://example.com/1",
            ),
            TrainingEntity(
                user_id=self.user1.user_id,
                category=TrainingCategory.RESIDENCY_PROGRAM_ONBOARDING,
                completed_timestamp=self.now,
                status=TrainingStatus.DONE,
                deadline=self.now + timedelta(days=10),
                link="http://example.com/2",
            ),
            TrainingEntity(
                user_id=self.user2.user_id,
                category=TrainingCategory.CORPORATE_CULTURE_COURSE,
                completed_timestamp=self.now,
                status=TrainingStatus.TO_DO,
                deadline=self.now + timedelta(days=7),
                link="http://example.com/3",
            ),
        ]
        await self.insert_entities(trainings)

    async def test_get_training_by_user_id_existing(self):
        result = await self.repo.get_training_by_user_id(
            self.session, self.user1.user_id
        )

        self.assertEqual(len(result), 2)
        self.assertTrue(all(t.user_id == self.user1.user_id for t in result))

    async def test_get_training_by_user_id_non_existent(self):
        result = await self.repo.get_training_by_user_id(self.session, 9999)
        self.assertEqual(result, [])

    async def test_get_training_by_user_id_and_category_existing(self):
        result = await self.repo.get_training_by_user_id_and_category(
            self.session, self.user1.user_id, TrainingCategory.CORPORATE_CULTURE_COURSE
        )

        self.assertIsNotNone(result)
        self.assertEqual(result.user_id, self.user1.user_id)
        self.assertEqual(result.category, TrainingCategory.CORPORATE_CULTURE_COURSE)

    async def test_get_training_by_user_id_and_category_non_existent(self):
        result = await self.repo.get_training_by_user_id_and_category(
            self.session,
            self.user1.user_id,
            TrainingCategory.MENTORSHIP_MENTOR_ONBOARDING,
        )

        self.assertIsNone(result)

    async def test_upsert_training_insert(self):
        """Test inserting a new TrainingEntity with completed_timestamp=NULL and a link."""
        training = TrainingEntity(
            user_id=self.user1.user_id,
            category=TrainingCategory.MENTORSHIP_MENTOR_ONBOARDING,
            completed_timestamp=None,
            status=TrainingStatus.TO_DO,
            deadline=datetime.now(timezone.utc) + timedelta(days=2),
            link="https://learning.example.com/courses/mentor-onboarding",
        )

        saved = await self.repo.upsert_training(self.session, training)

        self.assertIsNotNone(saved.training_id)
        self.assertIsNone(saved.completed_timestamp)
        self.assertEqual(saved.status, TrainingStatus.TO_DO)
        self.assertEqual(
            saved.link, "https://learning.example.com/courses/mentor-onboarding"
        )

    async def test_upsert_training_update(self):
        """Test updating an existing TrainingEntity."""
        existing = await self.repo.get_training_by_user_id(
            self.session, self.user1.user_id
        )
        updated_entity = TrainingEntity(
            training_id=existing[0].training_id,
            user_id=self.user1.user_id,
            category=existing[0].category,
            completed_timestamp=self.now + timedelta(days=1),
            status=TrainingStatus.DONE,
            deadline=existing[0].deadline,
            link=existing[0].link,
        )

        updated = await self.repo.upsert_training(self.session, updated_entity)

        self.assertEqual(updated.status, TrainingStatus.DONE)
        self.assertIsNotNone(updated.completed_timestamp)

    async def test_get_training_by_user_ids_and_categories_empty_list(self):
        result = await self.repo.get_training_by_user_ids_and_categories(
            self.session, [], [TrainingCategory.CORPORATE_CULTURE_COURSE]
        )
        self.assertEqual(result, [])

    async def test_get_training_by_user_ids_and_categories_filters_by_category(self):
        result = await self.repo.get_training_by_user_ids_and_categories(
            self.session,
            [self.user1.user_id],
            [TrainingCategory.CORPORATE_CULTURE_COURSE],
        )
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].category, TrainingCategory.CORPORATE_CULTURE_COURSE)

    async def test_get_training_by_user_ids_and_categories_multiple_users(self):
        result = await self.repo.get_training_by_user_ids_and_categories(
            self.session,
            [self.user1.user_id, self.user2.user_id],
            [TrainingCategory.CORPORATE_CULTURE_COURSE],
        )
        self.assertEqual(len(result), 2)
        self.assertTrue(
            all(t.category == TrainingCategory.CORPORATE_CULTURE_COURSE for t in result)
        )

    async def test_get_training_by_user_ids_and_categories_unknown_id_excluded(self):
        result = await self.repo.get_training_by_user_ids_and_categories(
            self.session, [999], [TrainingCategory.CORPORATE_CULTURE_COURSE]
        )
        self.assertEqual(result, [])


if __name__ == "__main__":
    unittest.main()
