"""The course catalogue, and the state its list column shows."""

import datetime
import os
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from backend.common.mentorship_enums import (
    ScormVersion,
    TrainingCategory,
    TrainingPackageState,
)
from backend.dto.training_course_dto import (
    TrainingCourseCreateDto,
    TrainingCourseState,
    TrainingCourseUpdateDto,
)
from backend.entity.training_course_entity import TrainingCourseEntity
from backend.entity.training_course_package_entity import (
    TrainingCoursePackageEntity,
)
from backend.training.training_course_service import (
    TrainingCourseService,
    derive_course_state,
    to_course_dto,
)

_VERIFIED_AT = datetime.datetime(2026, 9, 1, 12, 7, tzinfo=datetime.timezone.utc)
_UPLOADED_AT = datetime.datetime(2026, 8, 1, 9, 0, tzinfo=datetime.timezone.utc)


def _package(**overrides) -> TrainingCoursePackageEntity:
    """A live package row, defaulted so each test sets only what it cares about."""
    fields = dict(
        course_id=1,
        state=TrainingPackageState.LIVE,
        storage_prefix="training/1/abc/",
        entry_path="scormcontent/index.html",
        scorm_version=ScormVersion.SCORM_12,
        uploaded_at=_UPLOADED_AT,
    )
    fields.update(overrides)
    return TrainingCoursePackageEntity(**fields)


class TestDeriveCourseState(unittest.TestCase):
    def test_package_and_proof_is_verified(self):
        course = TrainingCourseEntity()
        package = _package(verified_completable_at=_VERIFIED_AT)
        self.assertEqual(
            derive_course_state(course, package), TrainingCourseState.VERIFIED
        )

    def test_package_without_proof_needs_a_trial_run(self):
        course = TrainingCourseEntity()
        package = _package()
        self.assertEqual(
            derive_course_state(course, package), TrainingCourseState.NEEDS_TRIAL_RUN
        )

    @patch.dict(
        os.environ,
        {"MENTORSHIP_MENTOR_ONBOARDING_LINK": "https://example.com/mentor"},
    )
    def test_seed_course_without_a_package_keeps_its_external_link(self):
        """Not broken, just not hosted here."""
        course = TrainingCourseEntity(
            category=TrainingCategory.MENTORSHIP_MENTOR_ONBOARDING
        )
        self.assertEqual(
            derive_course_state(course, None), TrainingCourseState.EXTERNAL_LINK
        )

    def test_a_seed_category_with_no_link_configured_has_nowhere_either(self):
        """Only the two mentorship courses were ever hosted elsewhere.

        Reporting EXTERNAL_LINK for the other two showed a state with nothing
        behind it, indistinguishable from one that can actually send people
        somewhere.
        """
        course = TrainingCourseEntity(
            category=TrainingCategory.CORPORATE_CULTURE_COURSE
        )
        self.assertEqual(
            derive_course_state(course, None), TrainingCourseState.NO_PACKAGE
        )

    @patch.dict(os.environ, {}, clear=True)
    def test_a_mentorship_course_is_no_package_when_its_variable_is_unset(self):
        course = TrainingCourseEntity(
            category=TrainingCategory.MENTORSHIP_MENTOR_ONBOARDING
        )
        self.assertEqual(
            derive_course_state(course, None), TrainingCourseState.NO_PACKAGE
        )

    def test_new_course_without_a_package_has_nowhere_to_send_anybody(self):
        course = TrainingCourseEntity(category=None)
        self.assertEqual(
            derive_course_state(course, None), TrainingCourseState.NO_PACKAGE
        )


class TestExternalLinkOnTheCourseRow(unittest.TestCase):
    """A state named EXTERNAL_LINK has to be able to show the link."""

    @patch.dict(
        os.environ,
        {"MENTORSHIP_MENTOR_ONBOARDING_LINK": "https://example.com/mentor"},
    )
    def test_a_course_still_on_its_external_link_carries_that_link(self):
        course = TrainingCourseEntity(
            course_id=1,
            name="Mentor Onboarding",
            is_active=True,
            category=TrainingCategory.MENTORSHIP_MENTOR_ONBOARDING,
        )

        dto = to_course_dto(course, None, 0, 0)

        self.assertEqual(dto.state, TrainingCourseState.EXTERNAL_LINK)
        self.assertEqual(dto.link, "https://example.com/mentor")

    @patch.dict(
        os.environ,
        {"MENTORSHIP_MENTOR_ONBOARDING_LINK": "https://example.com/mentor"},
    )
    def test_a_course_we_now_host_stops_pointing_at_the_old_one(self):
        """The env var still resolves; the course is no longer served from it."""
        course = TrainingCourseEntity(
            course_id=1,
            name="Mentor Onboarding",
            is_active=True,
            category=TrainingCategory.MENTORSHIP_MENTOR_ONBOARDING,
        )
        package = _package()

        dto = to_course_dto(course, package, 0, 0)

        self.assertIsNone(dto.link)

    def test_a_course_created_from_the_admin_page_has_no_link(self):
        course = TrainingCourseEntity(
            course_id=2, name="Something New", is_active=True, category=None
        )

        dto = to_course_dto(course, None, 0, 0)

        self.assertEqual(dto.state, TrainingCourseState.NO_PACKAGE)
        self.assertIsNone(dto.link)

    def test_the_dto_reads_package_fields_from_the_package(self):
        course = TrainingCourseEntity(
            course_id=1,
            name="Cat Care",
            is_active=True,
        )
        package = _package(
            scorm_version=ScormVersion.SCORM_12,
            package_version="from-package-row",
            reporting_mode="passed-incomplete",
            uploaded_at=_UPLOADED_AT,
            verified_completable_at=_VERIFIED_AT,
            verified_by_user_id=7,
        )

        dto = to_course_dto(course, package, 0, 0)

        self.assertEqual(dto.scorm_version, ScormVersion.SCORM_12)
        self.assertEqual(dto.package_version, "from-package-row")
        self.assertEqual(dto.reporting_mode, "passed-incomplete")
        self.assertEqual(dto.package_uploaded_at, _UPLOADED_AT)
        self.assertEqual(dto.verified_completable_at, _VERIFIED_AT)
        self.assertEqual(dto.verified_by_user_id, 7)


class TestTrainingCourseService(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.session = AsyncMock()
        self.repository = MagicMock()
        self.repository.list_courses = AsyncMock(return_value=[])
        self.repository.count_assignments = AsyncMock(return_value=0)
        self.repository.count_unfinished_assignments = AsyncMock(return_value=0)

        self.package_repository = MagicMock()
        self.package_repository.live_packages_for = AsyncMock(return_value={})
        self.package_repository.get_by_state = AsyncMock(return_value=None)

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
            logger=MagicMock(),
            training_course_repository=self.repository,
            training_course_package_repository=self.package_repository,
        )

    async def test_list_carries_the_assignment_count_through(self):
        course = TrainingCourseEntity(
            course_id=5,
            name="Corporate Culture",
            category=TrainingCategory.CORPORATE_CULTURE_COURSE,
            is_active=True,
        )
        self.repository.list_courses.return_value = [(course, 61, 0)]

        courses = await self.service.list_courses(self.session)

        self.assertEqual(len(courses), 1)
        self.assertEqual(courses[0].assigned_count, 61)
        # This category never had an external link, so there is nowhere to go.
        self.assertEqual(courses[0].state, TrainingCourseState.NO_PACKAGE)

    async def test_the_list_carries_how_many_have_not_finished(self):
        """The deactivate and replace dialogs both count heads with this."""
        course = TrainingCourseEntity(
            course_id=5, name="Mentor Onboarding", is_active=True
        )
        self.repository.list_courses.return_value = [(course, 61, 23)]

        courses = await self.service.list_courses(self.session)

        self.assertEqual(courses[0].assigned_count, 61)
        self.assertEqual(courses[0].unfinished_count, 23)

    async def test_list_asks_for_every_courses_package_in_one_call(self):
        """A query per row would not show up in the DTOs, only in the call
        count: this pins it at exactly one batched call for the whole page."""
        course_a = TrainingCourseEntity(course_id=5, name="A", is_active=True)
        course_b = TrainingCourseEntity(course_id=6, name="B", is_active=True)
        self.repository.list_courses.return_value = [(course_a, 0, 0), (course_b, 0, 0)]

        await self.service.list_courses(self.session)

        self.package_repository.live_packages_for.assert_awaited_once_with(
            self.session, [5, 6]
        )
        self.package_repository.get_by_state.assert_not_awaited()

    async def test_list_reads_a_live_package_when_one_exists(self):
        course = TrainingCourseEntity(course_id=5, name="Cat Care", is_active=True)
        package = _package(
            course_id=5,
            scorm_version=ScormVersion.SCORM_12,
            package_version="from-package-row",
        )
        self.repository.list_courses.return_value = [(course, 0, 0)]
        self.package_repository.live_packages_for.return_value = {5: package}

        courses = await self.service.list_courses(self.session)

        self.assertEqual(courses[0].state, TrainingCourseState.NEEDS_TRIAL_RUN)
        self.assertEqual(courses[0].scorm_version, ScormVersion.SCORM_12)
        self.assertEqual(courses[0].package_version, "from-package-row")

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

    async def test_update_reads_the_live_package_for_its_state(self):
        existing = TrainingCourseEntity(
            course_id=5, name="Legacy Safety Briefing", is_active=True
        )
        self.repository.get_course_by_id.return_value = existing
        self.package_repository.get_by_state.return_value = _package(
            course_id=5, verified_completable_at=_VERIFIED_AT
        )

        course = await self.service.update_course(
            self.session, 5, TrainingCourseUpdateDto(is_active=False)
        )

        self.package_repository.get_by_state.assert_awaited_once_with(
            self.session, 5, TrainingPackageState.LIVE
        )
        self.assertEqual(course.state, TrainingCourseState.VERIFIED)

    async def test_update_reports_the_real_unfinished_count(self):
        """The deactivate dialog weighs the decision by counting heads.

        A stubbed-away or mixed-up count here would tell an administrator
        nobody is mid-course when 23 people are.
        """
        existing = TrainingCourseEntity(
            course_id=5, name="Legacy Safety Briefing", is_active=True
        )
        self.repository.get_course_by_id.return_value = existing
        self.repository.count_assignments.return_value = 61
        self.repository.count_unfinished_assignments.return_value = 23

        course = await self.service.update_course(
            self.session, 5, TrainingCourseUpdateDto(is_active=False)
        )

        self.assertEqual(course.unfinished_count, 23)

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
