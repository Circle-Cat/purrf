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
        # session.flush() is what gives the new row its training_id.
        self.session.flush.side_effect = self._stamp_training_id
        self.service = TrainingAssignmentService(
            logger=MagicMock(),
            training_course_repository=self.courses,
            training_repository=self.trainings,
        )
        self.payload = TrainingAssignmentRequestDto(user_id=11, course_id=3)

    async def _stamp_training_id(self):
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

    async def test_unverified_course_is_refused(self):
        """A course nobody has finished closes the matching gate for everybody
        assigned to it, silently. The refusal is the whole point of the gate."""
        self.courses.get_course_by_id.return_value = _course(
            verified_completable_at=None
        )

        with self.assertRaises(ConflictError):
            await self.service.assign(self.session, self.payload)

        self.session.add.assert_not_called()

    async def test_deactivated_course_is_refused(self):
        self.courses.get_course_by_id.return_value = _course(is_active=False)

        with self.assertRaises(ConflictError):
            await self.service.assign(self.session, self.payload)

        self.session.add.assert_not_called()

    async def test_missing_course_is_a_value_error(self):
        self.courses.get_course_by_id.return_value = None

        with self.assertRaises(ValueError):
            await self.service.assign(self.session, self.payload)

    async def test_assigning_twice_is_a_no_op(self):
        """Not an error: (user_id, course_id) is uniquely indexed, and the
        second call must not look like a duplicate somebody created."""
        self.trainings.get_training_by_user_id_and_course_id.return_value = (
            TrainingEntity(training_id=99, user_id=11, course_id=3)
        )

        result = await self.service.assign(self.session, self.payload)

        self.assertFalse(result.created)
        self.assertEqual(result.training_id, 99)
        self.session.add.assert_not_called()

    async def test_repeat_assignment_never_overwrites_an_existing_deadline(self):
        """Registration stamps a deadline once and never refreshes it. Assigning
        again with a different date must not be a second way to move it."""
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
        """Nullable since July; ensure_for_admitted already creates rows without
        one and stamps it on first registration."""
        await self.service.assign(self.session, self.payload)

        self.assertIsNone(self.session.add.call_args.args[0].deadline)

    async def test_category_is_copied_from_the_course(self):
        """Seed courses keep their category on the assignment so registration and
        the matching gate, which filter on that column, read as they always did."""
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
