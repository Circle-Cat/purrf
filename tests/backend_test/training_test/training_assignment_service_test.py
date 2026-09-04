"""The gate between uploading a course and anybody being given it."""

import datetime
import unittest
from unittest.mock import AsyncMock, MagicMock

from backend.common.exceptions import ConflictError
from backend.common.mentorship_enums import (
    TrainingCategory,
    TrainingPackageState,
    TrainingStatus,
)
from backend.dto.training_course_dto import TrainingAssignmentRequestDto
from backend.entity.training_course_entity import TrainingCourseEntity
from backend.entity.training_entity import TrainingEntity
from backend.training.training_assignment_service import TrainingAssignmentService

_VERIFIED_AT = datetime.datetime(2026, 9, 1, 12, 7, tzinfo=datetime.timezone.utc)
_COURSE_ID = 3
_USER_ID = 11


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
        self.trainings.get_training_by_user_id_and_category = AsyncMock(
            return_value=None
        )
        self.package_repository = MagicMock()
        self.package_repository.get_by_state = AsyncMock(
            return_value=MagicMock(verified_completable_at=_VERIFIED_AT)
        )
        self.service = TrainingAssignmentService(
            logger=MagicMock(),
            training_course_repository=self.courses,
            training_repository=self.trainings,
            training_course_package_repository=self.package_repository,
        )
        self.payload = TrainingAssignmentRequestDto(user_id=11, course_id=3)
        # Aliases matching the repositories' role in start_trial's tests.
        self.course_repository = self.courses
        self.training_repository = self.trainings

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

    async def test_refuses_to_assign_a_course_whose_live_package_is_unverified(self):
        """The refusal is the whole point of the gate. The course row still
        carries its own (verified) stamp from _course()'s defaults, so this
        only passes if the gate reads the package's stamp, not the course's."""
        self.package_repository.get_by_state.return_value = MagicMock(
            verified_completable_at=None
        )

        with self.assertRaises(ConflictError):
            await self.service.assign(self.session, self.payload)

        self.session.add.assert_not_called()
        self.session.commit.assert_not_awaited()

    async def test_refuses_to_assign_a_course_with_no_live_package(self):
        """Same course row as above, still carrying a verified stamp; only
        the absence of a LIVE package row should block this."""
        self.package_repository.get_by_state.return_value = None

        with self.assertRaises(ConflictError):
            await self.service.assign(self.session, self.payload)

        self.session.add.assert_not_called()
        self.session.commit.assert_not_awaited()

    async def test_assigns_when_the_live_package_carries_a_stamp(self):
        """The course row itself is unverified; assignment must still
        succeed because the gate reads the package, not the course."""
        self.courses.get_course_by_id.return_value = _course(
            verified_completable_at=None
        )

        result = await self.service.assign(self.session, self.payload)

        self.assertTrue(result.created)
        self.package_repository.get_by_state.assert_awaited_once_with(
            self.session, 3, TrainingPackageState.LIVE
        )

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

    async def test_a_trial_opens_an_assignment_on_an_unverified_course(self):
        """The gate that refuses assignment is exactly what the trial answers."""
        self.course_repository.get_course_by_id.return_value = TrainingCourseEntity(
            course_id=_COURSE_ID,
            name="Mentor Onboarding",
            is_active=True,
            storage_prefix="training/3/abc/",
            verified_completable_at=None,
        )

        result = await self.service.start_trial(self.session, _COURSE_ID, _USER_ID)

        self.assertEqual(result.user_id, _USER_ID)
        self.assertEqual(result.course_id, _COURSE_ID)
        self.assertTrue(result.created)
        self.package_repository.get_by_state.assert_awaited_once_with(
            self.session, _COURSE_ID, TrainingPackageState.LIVE
        )

    async def test_a_second_trial_reuses_the_first_assignment(self):
        """So a verifier who stops and comes back resumes where they were."""
        self.training_repository.get_training_by_user_id_and_course_id.return_value = (
            TrainingEntity(training_id=42, user_id=_USER_ID, course_id=_COURSE_ID)
        )

        result = await self.service.start_trial(self.session, _COURSE_ID, _USER_ID)

        self.assertEqual(result.training_id, 42)
        self.assertFalse(result.created)

    async def test_a_trial_on_a_course_with_no_package_is_refused(self):
        """The course row still claims a storage_prefix; only the absence of
        a LIVE package row should block the trial."""
        self.course_repository.get_course_by_id.return_value = TrainingCourseEntity(
            course_id=_COURSE_ID,
            name="Empty",
            is_active=True,
            storage_prefix="training/3/abc/",
        )
        self.package_repository.get_by_state.return_value = None

        with self.assertRaises(ConflictError):
            await self.service.start_trial(self.session, _COURSE_ID, _USER_ID)

    async def test_a_trial_carries_the_courses_category_like_an_assignment_does(self):
        """A seed course's category is what opens the mentorship gate."""
        self.course_repository.get_course_by_id.return_value = TrainingCourseEntity(
            course_id=_COURSE_ID,
            name="Mentor Onboarding",
            category=TrainingCategory.MENTORSHIP_MENTOR_ONBOARDING,
            is_active=True,
            storage_prefix="training/3/abc/",
        )

        await self.service.start_trial(self.session, _COURSE_ID, _USER_ID)

        added = self.session.add.call_args.args[0]
        self.assertEqual(added.category, TrainingCategory.MENTORSHIP_MENTOR_ONBOARDING)

    async def test_a_deactivated_course_can_still_be_trialled(self):
        """assign checks is_active on its own, so a trial does not have to:
        stamping a deactivated course does not make it assignable."""
        self.course_repository.get_course_by_id.return_value = TrainingCourseEntity(
            course_id=_COURSE_ID,
            name="Mentor Onboarding",
            is_active=False,
            storage_prefix="training/3/abc/",
        )

        result = await self.service.start_trial(self.session, _COURSE_ID, _USER_ID)

        self.assertTrue(result.created)

    async def test_a_row_held_by_category_is_adopted_rather_than_doubled(self):
        """The onboarding dispatch owns the same pairing under a category. A
        second row for one category makes every later read of it raise, and
        the partial unique index does not stop the insert."""
        by_category = TrainingEntity(
            training_id=77,
            user_id=11,
            category=TrainingCategory.MENTORSHIP_MENTEE_ONBOARDING,
            course_id=None,
        )
        self.trainings.get_training_by_user_id_and_category.return_value = by_category

        result = await self.service.assign(self.session, self.payload)

        self.assertFalse(result.created)
        self.assertEqual(result.training_id, 77)
        self.assertEqual(by_category.course_id, 3)
        self.session.add.assert_not_called()
        self.session.commit.assert_awaited_once()

    async def test_adopting_a_category_row_leaves_the_rest_of_it_alone(self):
        stamped = datetime.datetime(2026, 10, 1, tzinfo=datetime.timezone.utc)
        by_category = TrainingEntity(
            training_id=77,
            user_id=11,
            category=TrainingCategory.MENTORSHIP_MENTEE_ONBOARDING,
            course_id=None,
            status=TrainingStatus.IN_PROGRESS,
            deadline=stamped,
            link="https://mentee",
        )
        self.trainings.get_training_by_user_id_and_category.return_value = by_category

        await self.service.assign(
            self.session,
            TrainingAssignmentRequestDto(
                user_id=11,
                course_id=3,
                deadline=datetime.datetime(2027, 1, 1, tzinfo=datetime.timezone.utc),
            ),
        )

        self.assertEqual(by_category.deadline, stamped)
        self.assertEqual(by_category.status, TrainingStatus.IN_PROGRESS)
        self.assertEqual(by_category.link, "https://mentee")

    async def test_a_course_without_a_category_is_not_looked_up_by_one(self):
        self.courses.get_course_by_id.return_value = _course(category=None)

        await self.service.assign(self.session, self.payload)

        self.trainings.get_training_by_user_id_and_category.assert_not_awaited()
        self.session.add.assert_called_once()

    async def test_a_trial_adopts_a_category_row_too(self):
        """A verifier who already holds the seed course by category must not
        end up with two rows for it either."""
        by_category = TrainingEntity(
            training_id=77,
            user_id=_USER_ID,
            category=TrainingCategory.MENTORSHIP_MENTEE_ONBOARDING,
            course_id=None,
        )
        self.trainings.get_training_by_user_id_and_category.return_value = by_category

        result = await self.service.start_trial(self.session, _COURSE_ID, _USER_ID)

        self.assertFalse(result.created)
        self.assertEqual(result.training_id, 77)
        self.assertEqual(by_category.course_id, _COURSE_ID)
        self.session.add.assert_not_called()


if __name__ == "__main__":
    unittest.main()
