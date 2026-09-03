"""The gate between uploading a course and anybody being given it."""

import datetime
import unittest
from unittest.mock import AsyncMock, MagicMock

from backend.common.exceptions import ConflictError
from backend.common.mentorship_enums import TrainingCategory, TrainingStatus
from backend.dto.training_course_dto import TrainingAssignmentRequestDto
from backend.entity.training_course_entity import TrainingCourseEntity
from backend.entity.training_entity import TrainingEntity
from backend.training.training_assignment_service import TrainingAssignmentService

_VERIFIED_AT = datetime.datetime(2026, 9, 1, 12, 7, tzinfo=datetime.timezone.utc)


def _course(**overrides):
    defaults = {
        "course_id": 3,
        "name": "Mentee Onboarding",
        "category": TrainingCategory.MENTORSHIP_MENTEE_ONBOARDING,
        "is_active": True,
        "storage_prefix": "training/3/abc/",
        "verified_completable_at": _VERIFIED_AT,
    }
    return TrainingCourseEntity(**{**defaults, **overrides})


class TestTrainingAssignmentService(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.session = AsyncMock()
        self.courses = MagicMock()
        self.courses.get_course_by_id = AsyncMock(return_value=_course())
        self.trainings = MagicMock()
        self.trainings.get_training_by_user_id_and_course_id = AsyncMock(
            return_value=None
        )
        self.service = TrainingAssignmentService(
            logger=MagicMock(),
            training_course_repository=self.courses,
            training_repository=self.trainings,
        )
        self.payload = TrainingAssignmentRequestDto(user_id=11, course_id=3)

        # Records the order the write, the flush and the commit happen in.
        # add() is synchronous in SQLAlchemy, unlike the session itself.
        self.calls = []
        self.session.add = MagicMock(
            side_effect=lambda entity: self.calls.append(("add", entity))
        )
        self.session.flush = AsyncMock(side_effect=self._stamp_training_id)
        self.session.commit = AsyncMock(
            side_effect=lambda: self.calls.append(("commit",))
        )

    async def _stamp_training_id(self):
        # flush() is what gives the new row its training_id.
        self.calls.append(("flush",))
        for call in self.session.add.call_args_list:
            call.args[0].training_id = 42

    async def test_assigns_a_verified_course(self):
        result = await self.service.assign(self.session, self.payload)

        self.assertTrue(result.created)
        self.assertEqual(result.user_id, 11)
        self.assertEqual(result.course_id, 3)
        added = self.session.add.call_args.args[0]
        self.assertEqual(added.status, TrainingStatus.TO_DO)
        self.assertEqual(added.course_id, 3)
        self.assertEqual([step[0] for step in self.calls], ["add", "flush", "commit"])

    async def test_unverified_course_is_refused(self):
        """The refusal is the whole point of the gate."""
        self.courses.get_course_by_id.return_value = _course(
            verified_completable_at=None
        )

        with self.assertRaises(ConflictError):
            await self.service.assign(self.session, self.payload)

        self.session.add.assert_not_called()
        self.session.commit.assert_not_awaited()

    async def test_deactivated_course_is_refused(self):
        self.courses.get_course_by_id.return_value = _course(is_active=False)

        with self.assertRaises(ConflictError):
            await self.service.assign(self.session, self.payload)

        self.session.add.assert_not_called()
        self.session.commit.assert_not_awaited()

    async def test_missing_course_is_a_value_error(self):
        self.courses.get_course_by_id.return_value = None

        with self.assertRaises(ValueError):
            await self.service.assign(self.session, self.payload)

        self.session.commit.assert_not_awaited()

    async def test_assigning_twice_is_a_no_op(self):
        """Not an error: (user_id, course_id) is uniquely indexed."""
        self.trainings.get_training_by_user_id_and_course_id.return_value = (
            TrainingEntity(training_id=99, user_id=11, course_id=3)
        )

        result = await self.service.assign(self.session, self.payload)

        self.assertFalse(result.created)
        self.assertEqual(result.training_id, 99)
        self.session.add.assert_not_called()
        self.session.commit.assert_not_awaited()

    async def test_repeat_assignment_never_overwrites_an_existing_deadline(self):
        """Registration stamps a deadline once; this must not be a second way
        to move it."""
        existing = TrainingEntity(
            training_id=99,
            user_id=11,
            course_id=3,
            deadline=datetime.datetime(2026, 10, 1, tzinfo=datetime.timezone.utc),
        )
        self.trainings.get_training_by_user_id_and_course_id.return_value = existing

        await self.service.assign(
            self.session,
            TrainingAssignmentRequestDto(
                user_id=11,
                course_id=3,
                deadline=datetime.datetime(2027, 1, 1, tzinfo=datetime.timezone.utc),
            ),
        )

        self.assertEqual(
            existing.deadline,
            datetime.datetime(2026, 10, 1, tzinfo=datetime.timezone.utc),
        )

    async def test_an_empty_deadline_is_allowed(self):
        """ensure_for_admitted already creates rows without one."""
        await self.service.assign(self.session, self.payload)

        self.assertIsNone(self.session.add.call_args.args[0].deadline)

    async def test_category_is_copied_from_the_course(self):
        """So registration and the matching gate read as they always did."""
        await self.service.assign(self.session, self.payload)

        self.assertEqual(
            self.session.add.call_args.args[0].category,
            TrainingCategory.MENTORSHIP_MENTEE_ONBOARDING,
        )

    async def test_a_course_without_a_category_assigns_with_none(self):
        self.courses.get_course_by_id.return_value = _course(category=None)

        await self.service.assign(self.session, self.payload)

        self.assertIsNone(self.session.add.call_args.args[0].category)


if __name__ == "__main__":
    unittest.main()
