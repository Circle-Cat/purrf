import unittest
from datetime import datetime, timedelta

from backend.repository.training_repository import TrainingRepository
from backend.entity.training_entity import TrainingEntity
from backend.entity.users_entity import UsersEntity
from backend.common.mentorship_enums import (
    TrainingStatus,
    TrainingCategory,
    UserTimezone,
)
from tests.backend_test.repository_test.base_repository_test_lib import (
    BaseRepositoryTestLib,
)


class TestTrainingRepository(BaseRepositoryTestLib):
    async def asyncSetUp(self):
        await super().asyncSetUp()
        self.repo = TrainingRepository()

        now = datetime.utcnow()

        dummy_users = [
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
                last_name="MultiRole",
                timezone=UserTimezone.AMERICA_LOS_ANGELES,
                communication_channel="slack",
                primary_email="bob@example.com",
                alternative_emails=["b1@example.com", "b2@example.com"],
                is_active=True,
                updated_timestamp=datetime.utcnow(),
                subject_identifier="sub2",
            ),
        ]
        await self.insert_entities(dummy_users)

        self.user1 = dummy_users[0]
        self.user2 = dummy_users[1]

        trainings = [
            TrainingEntity(
                user_id=self.user1.user_id,
                category=TrainingCategory.CORPORATE_CULTURE_COURSE,
                completed_timestamp=now,
                status=TrainingStatus.TO_DO,
                deadline=now + timedelta(days=7),
                link="http://example.com/1",
            ),
            TrainingEntity(
                user_id=self.user1.user_id,
                category=TrainingCategory.RESIDENCY_PROGRAM_ONBOARDING,
                completed_timestamp=now,
                status=TrainingStatus.DONE,
                deadline=now + timedelta(days=10),
                link="http://example.com/2",
            ),
            TrainingEntity(
                user_id=self.user2.user_id,
                category=TrainingCategory.CORPORATE_CULTURE_COURSE,
                completed_timestamp=now,
                status=TrainingStatus.TO_DO,
                deadline=now + timedelta(days=7),
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


if __name__ == "__main__":
    unittest.main()
