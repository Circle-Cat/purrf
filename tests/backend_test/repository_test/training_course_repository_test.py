"""The course catalogue's per-row headcounts."""

import unittest
from datetime import datetime, timezone

from backend.common.mentorship_enums import CommunicationMethod, TrainingStatus
from backend.entity.training_course_entity import TrainingCourseEntity
from backend.entity.training_entity import TrainingEntity
from backend.entity.users_entity import UsersEntity
from backend.repository.training_course_repository import TrainingCourseRepository
from tests.backend_test.repository_test.base_repository_test_lib import (
    BaseRepositoryTestLib,
)


class TestTrainingCourseRepository(BaseRepositoryTestLib):
    async def asyncSetUp(self):
        await super().asyncSetUp()
        self.repo = TrainingCourseRepository()
        self.now = datetime.now(timezone.utc)

        users = [self._user(f"Learner{i}") for i in range(4)]
        await self.insert_entities(users)
        self.user_ids = [u.user_id for u in users]
        self._next_user_index = len(users)

        courses = [
            TrainingCourseEntity(name="Mentor Onboarding", is_active=True),
            TrainingCourseEntity(name="Mentee Onboarding", is_active=True),
        ]
        await self.insert_entities(courses)
        self.course_id = courses[0].course_id
        self.other_course_id = courses[1].course_id

    def _user(self, first_name):
        return UsersEntity(
            first_name=first_name,
            last_name="Tester",
            timezone="Asia/Shanghai",
            timezone_updated_at=self.now,
            communication_channel=CommunicationMethod.EMAIL,
            is_active=True,
            updated_timestamp=self.now,
        )

    def _new_user(self):
        self._next_user_index += 1
        return self._user(f"Learner{self._next_user_index}")

    async def _assign(self, user, course_id, status):
        await self.insert_entities([user])
        training = TrainingEntity(
            user_id=user.user_id,
            course_id=course_id,
            status=status,
            deadline=self.now,
        )
        await self.insert_entities([training])
        return training

    async def test_unfinished_counts_everyone_who_has_not_finished(self):
        """TO_DO and IN_PROGRESS both count; a new package restarts both."""
        for status in (
            TrainingStatus.TO_DO,
            TrainingStatus.IN_PROGRESS,
            TrainingStatus.DONE,
        ):
            await self._assign(self._new_user(), self.course_id, status)

        self.assertEqual(
            await self.repo.count_unfinished_assignments(self.session, self.course_id),
            2,
        )

    async def test_unfinished_does_not_reach_another_course(self):
        await self._assign(self._new_user(), self.other_course_id, TrainingStatus.TO_DO)

        self.assertEqual(
            await self.repo.count_unfinished_assignments(self.session, self.course_id),
            0,
        )


if __name__ == "__main__":
    unittest.main()
