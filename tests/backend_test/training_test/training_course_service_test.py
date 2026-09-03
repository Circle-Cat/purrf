"""The course catalogue, and the state its list column shows."""

import datetime
import unittest
from unittest.mock import AsyncMock, MagicMock

from backend.common.mentorship_enums import TrainingCategory
from backend.dto.training_course_dto import (
    TrainingCourseCreateDto,
    TrainingCourseState,
    TrainingCourseUpdateDto,
)
from backend.entity.training_course_entity import TrainingCourseEntity
from backend.training.training_course_service import (
    TrainingCourseService,
    derive_course_state,
)

_VERIFIED_AT = datetime.datetime(2026, 9, 1, 12, 7, tzinfo=datetime.timezone.utc)


class TestDeriveCourseState(unittest.TestCase):
    def test_package_and_proof_is_verified(self):
        course = TrainingCourseEntity(
            storage_prefix="training/3/abc/", verified_completable_at=_VERIFIED_AT
        )
        self.assertEqual(derive_course_state(course), TrainingCourseState.VERIFIED)

    def test_package_without_proof_needs_a_trial_run(self):
        course = TrainingCourseEntity(storage_prefix="training/3/abc/")
        self.assertEqual(
            derive_course_state(course), TrainingCourseState.NEEDS_TRIAL_RUN
        )

    def test_re_upload_drops_a_verified_course_back_to_needs_trial_run(self):
        """The prefix stays populated, so reading it first would say VERIFIED."""
        course = TrainingCourseEntity(
            storage_prefix="training/3/def/", verified_completable_at=None
        )
        self.assertEqual(
            derive_course_state(course), TrainingCourseState.NEEDS_TRIAL_RUN
        )

    def test_seed_course_without_a_package_keeps_its_external_link(self):
        """Not broken, just not hosted here."""
        course = TrainingCourseEntity(
            category=TrainingCategory.CORPORATE_CULTURE_COURSE, storage_prefix=None
        )
        self.assertEqual(derive_course_state(course), TrainingCourseState.EXTERNAL_LINK)

    def test_new_course_without_a_package_has_nowhere_to_send_anybody(self):
        course = TrainingCourseEntity(category=None, storage_prefix=None)
        self.assertEqual(derive_course_state(course), TrainingCourseState.NO_PACKAGE)


class TestTrainingCourseService(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.session = AsyncMock()
        self.repository = MagicMock()
        self.repository.list_courses = AsyncMock(return_value=[])
        self.repository.count_assignments = AsyncMock(return_value=0)

        # Records the order the write and the commit happen in.
        self.calls = []

        async def _add_course(_session, course):
            course.course_id = 7
            self.calls.append("add_course")
            return course

        self.repository.add_course = AsyncMock(side_effect=_add_course)
        self.repository.get_course_by_id = AsyncMock(return_value=None)
        self.session.commit = AsyncMock(side_effect=lambda: self.calls.append("commit"))
        self.service = TrainingCourseService(
            logger=MagicMock(), training_course_repository=self.repository
        )

    async def test_list_carries_the_assignment_count_through(self):
        course = TrainingCourseEntity(
            course_id=5,
            name="Corporate Culture",
            category=TrainingCategory.CORPORATE_CULTURE_COURSE,
            is_active=True,
        )
        self.repository.list_courses.return_value = [(course, 61)]

        courses = await self.service.list_courses(self.session)

        self.assertEqual(len(courses), 1)
        self.assertEqual(courses[0].assigned_count, 61)
        self.assertEqual(courses[0].state, TrainingCourseState.EXTERNAL_LINK)

    async def test_a_new_course_starts_unassignable(self):
        course = await self.service.create_course(
            self.session, TrainingCourseCreateDto(name="  Safety Briefing  ")
        )

        self.assertEqual(course.name, "Safety Briefing")
        self.assertIsNone(course.verified_completable_at)
        self.assertEqual(course.state, TrainingCourseState.NO_PACKAGE)
        self.assertEqual(self.calls, ["add_course", "commit"])

    async def test_deactivating_only_flips_the_flag(self):
        """Nothing is deleted and nobody loses access."""
        existing = TrainingCourseEntity(
            course_id=5, name="Legacy Safety Briefing", is_active=True
        )
        self.repository.get_course_by_id.return_value = existing
        self.repository.count_assignments.return_value = 61

        course = await self.service.update_course(
            self.session, 5, TrainingCourseUpdateDto(is_active=False)
        )

        self.assertFalse(course.is_active)
        self.assertEqual(course.assigned_count, 61)
        self.assertEqual(existing.name, "Legacy Safety Briefing")
        self.session.commit.assert_awaited_once()

    async def test_the_rename_lands_before_the_commit(self):
        existing = TrainingCourseEntity(course_id=5, name="Old Name", is_active=True)
        self.repository.get_course_by_id.return_value = existing

        async def _commit():
            # If this runs before the rename, the assertion below catches it.
            self.calls.append(("commit", existing.name))

        self.session.commit = AsyncMock(side_effect=_commit)

        await self.service.update_course(
            self.session, 5, TrainingCourseUpdateDto(name="New Name")
        )

        self.assertEqual(self.calls, [("commit", "New Name")])

    async def test_updating_a_missing_course_is_a_value_error(self):
        with self.assertRaises(ValueError):
            await self.service.update_course(
                self.session, 404, TrainingCourseUpdateDto(name="Nope")
            )

        self.session.commit.assert_not_awaited()


if __name__ == "__main__":
    unittest.main()
