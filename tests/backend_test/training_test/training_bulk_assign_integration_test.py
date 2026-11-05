"""A bulk assignment against a real database.

The unit tests prove the service asks the session for one commit. Only a real
transaction proves what that buys: a batch that fails partway leaves no rows
behind, which is the whole reason the per-person write does not commit.
"""

import unittest
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from backend.common.exceptions import ConflictError

from backend.common.mentorship_enums import (
    CommunicationMethod,
    ScormVersion,
    TrainingCategory,
    TrainingPackageState,
    TrainingStatus,
)
from backend.dto.training_course_dto import TrainingBulkAssignmentRequestDto
from backend.entity.training_course_entity import TrainingCourseEntity
from backend.entity.training_course_package_entity import TrainingCoursePackageEntity
from backend.entity.training_entity import TrainingEntity
from backend.entity.users_entity import UsersEntity
from backend.repository.training_course_package_repository import (
    TrainingCoursePackageRepository,
)
from backend.repository.training_course_repository import TrainingCourseRepository
from backend.repository.training_repository import TrainingRepository
from backend.training.training_assignment_service import TrainingAssignmentService
from tests.backend_test.repository_test.base_repository_test_lib import (
    BaseRepositoryTestLib,
)
from unittest.mock import MagicMock


class TestBulkAssignAgainstTheDatabase(BaseRepositoryTestLib):
    async def asyncSetUp(self):
        await super().asyncSetUp()
        self.now = datetime.now(timezone.utc)
        self.deadline = self.now + timedelta(days=14)

        self.service = TrainingAssignmentService(
            logger=MagicMock(),
            training_course_repository=TrainingCourseRepository(),
            training_repository=TrainingRepository(),
            training_course_package_repository=TrainingCoursePackageRepository(),
        )

        self.course = TrainingCourseEntity(
            name="Corporate Culture",
            category=TrainingCategory.CORPORATE_CULTURE_COURSE,
            is_active=True,
        )
        await self.insert_entities([self.course])
        await self.insert_entities([
            TrainingCoursePackageEntity(
                course_id=self.course.course_id,
                state=TrainingPackageState.LIVE,
                storage_prefix="packages/culture/1",
                entry_path="scormcontent/index.html",
                scorm_version=ScormVersion.SCORM_12,
                package_version="AAAAaaaa",
                uploaded_at=self.now,
            )
        ])

        self.users = [self._user("Ada"), self._user("Bo")]
        await self.insert_entities(self.users)

    def _user(self, first_name):
        return UsersEntity(
            first_name=first_name,
            last_name="Learner",
            timezone="Asia/Shanghai",
            timezone_updated_at=self.now,
            communication_channel=CommunicationMethod.EMAIL,
            is_active=True,
            updated_timestamp=self.now,
        )

    async def _training_rows(self):
        result = await self.session.execute(
            select(TrainingEntity).where(
                TrainingEntity.course_id == self.course.course_id
            )
        )
        return list(result.scalars().all())

    async def test_a_batch_writes_the_row_the_dispatch_writes(self):
        await self.service.assign_bulk(
            self.session,
            TrainingBulkAssignmentRequestDto(
                course_id=self.course.course_id,
                user_ids=[user.user_id for user in self.users],
                deadline=self.deadline,
            ),
        )

        rows = await self._training_rows()
        self.assertEqual(
            sorted(row.user_id for row in rows),
            sorted(user.user_id for user in self.users),
        )
        for row in rows:
            self.assertEqual(row.category, TrainingCategory.CORPORATE_CULTURE_COURSE)
            self.assertEqual(row.status, TrainingStatus.TO_DO)
            self.assertEqual(row.deadline, self.deadline)
            self.assertIsNone(row.link)

    async def test_a_batch_that_fails_partway_leaves_no_rows(self):
        missing_user_id = 10_000_000

        # Narrow on purpose: a bare Exception would also pass on a typo in
        # this test, and prove nothing about the transaction. The service
        # turns the referential failure into a conflict, so that is what a
        # caller sees -- and nothing is committed either way.
        with self.assertRaises(ConflictError):
            await self.service.assign_bulk(
                self.session,
                TrainingBulkAssignmentRequestDto(
                    course_id=self.course.course_id,
                    user_ids=[self.users[0].user_id, missing_user_id],
                    deadline=self.deadline,
                ),
            )

        await self.session.rollback()
        self.assertEqual(await self._training_rows(), [])

    async def test_a_standing_deadline_survives_a_second_batch(self):
        stamped = self.now + timedelta(days=3)
        await self.insert_entities([
            TrainingEntity(
                user_id=self.users[0].user_id,
                course_id=self.course.course_id,
                category=TrainingCategory.CORPORATE_CULTURE_COURSE,
                status=TrainingStatus.IN_PROGRESS,
                deadline=stamped,
            )
        ])

        result = await self.service.assign_bulk(
            self.session,
            TrainingBulkAssignmentRequestDto(
                course_id=self.course.course_id,
                user_ids=[user.user_id for user in self.users],
                deadline=self.deadline,
            ),
        )

        self.assertEqual(result.created_count, 1)
        self.assertEqual(result.already_assigned_count, 1)
        rows = {row.user_id: row for row in await self._training_rows()}
        self.assertEqual(rows[self.users[0].user_id].deadline, stamped)
        self.assertEqual(rows[self.users[0].user_id].status, TrainingStatus.IN_PROGRESS)
        self.assertEqual(rows[self.users[1].user_id].deadline, self.deadline)


if __name__ == "__main__":
    unittest.main()
