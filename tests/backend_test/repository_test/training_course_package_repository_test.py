"""One row per package, and the constraint that keeps the slots single."""

import unittest
from datetime import datetime, timezone

from sqlalchemy.exc import IntegrityError

from backend.common.mentorship_enums import (
    ScormVersion,
    TrainingPackageState,
)
from backend.entity.training_course_entity import TrainingCourseEntity
from backend.entity.training_course_package_entity import (
    TrainingCoursePackageEntity,
)

# Imported for its side effect only: a package's uploaded_by_user_id and
# verified_by_user_id point at users, and SQLAlchemy cannot configure the
# package mapper until that table is in the registry. Production imports
# every entity at startup, so this only bites a test that names one of them.
from backend.entity.users_entity import UsersEntity  # noqa: F401
from backend.repository.training_course_package_repository import (
    TrainingCoursePackageRepository,
)
from tests.backend_test.repository_test.base_repository_test_lib import (
    BaseRepositoryTestLib,
)


class TestTrainingCoursePackageRepository(BaseRepositoryTestLib):
    async def asyncSetUp(self):
        await super().asyncSetUp()
        self.repo = TrainingCoursePackageRepository()
        self.now = datetime.now(timezone.utc)

        courses = [
            TrainingCourseEntity(name="Mentor Onboarding", is_active=True),
            TrainingCourseEntity(name="Mentee Onboarding", is_active=True),
        ]
        await self.insert_entities(courses)
        self.course_id = courses[0].course_id
        self.other_course_id = courses[1].course_id

    def _package(self, course_id, state, prefix="training/1/aaa/"):
        return TrainingCoursePackageEntity(
            course_id=course_id,
            state=state,
            storage_prefix=prefix,
            entry_path="scormcontent/index.html",
            scorm_version=ScormVersion.SCORM_12,
            uploaded_at=self.now,
        )

    async def test_reads_back_the_package_it_stored(self):
        stored = await self.repo.add(
            self.session, self._package(self.course_id, TrainingPackageState.LIVE)
        )

        found = await self.repo.get_by_state(
            self.session, self.course_id, TrainingPackageState.LIVE
        )

        self.assertIsNotNone(found)
        self.assertEqual(found.package_id, stored.package_id)
        self.assertEqual(found.storage_prefix, "training/1/aaa/")
        self.assertEqual(found.entry_path, "scormcontent/index.html")

    async def test_a_slot_a_course_does_not_hold_is_none(self):
        await self.repo.add(
            self.session, self._package(self.course_id, TrainingPackageState.LIVE)
        )

        self.assertIsNone(
            await self.repo.get_by_state(
                self.session, self.course_id, TrainingPackageState.PENDING
            )
        )

    async def test_one_course_cannot_hold_two_live_packages(self):
        # The single-slot rule is the database's, not the service's: a second
        # live row would make "which package is this course" unanswerable.
        await self.repo.add(
            self.session,
            self._package(self.course_id, TrainingPackageState.LIVE, "training/1/a/"),
        )

        with self.assertRaises(IntegrityError):
            await self.repo.add(
                self.session,
                self._package(
                    self.course_id, TrainingPackageState.LIVE, "training/1/b/"
                ),
            )

    async def test_two_courses_may_each_hold_a_live_package(self):
        await self.repo.add(
            self.session,
            self._package(self.course_id, TrainingPackageState.LIVE, "training/1/a/"),
        )
        await self.repo.add(
            self.session,
            self._package(
                self.other_course_id, TrainingPackageState.LIVE, "training/2/a/"
            ),
        )

        self.assertIsNotNone(
            await self.repo.get_by_state(
                self.session, self.other_course_id, TrainingPackageState.LIVE
            )
        )

    async def test_one_course_may_hold_a_live_and_a_pending_at_once(self):
        await self.repo.add(
            self.session,
            self._package(self.course_id, TrainingPackageState.LIVE, "training/1/a/"),
        )
        await self.repo.add(
            self.session,
            self._package(
                self.course_id, TrainingPackageState.PENDING, "training/1/b/"
            ),
        )

        live = await self.repo.get_by_state(
            self.session, self.course_id, TrainingPackageState.LIVE
        )
        pending = await self.repo.get_by_state(
            self.session, self.course_id, TrainingPackageState.PENDING
        )
        self.assertEqual(live.storage_prefix, "training/1/a/")
        self.assertEqual(pending.storage_prefix, "training/1/b/")

    async def test_deleting_frees_the_slot(self):
        first = await self.repo.add(
            self.session,
            self._package(self.course_id, TrainingPackageState.LIVE, "training/1/a/"),
        )

        await self.repo.delete(self.session, first)
        await self.repo.add(
            self.session,
            self._package(self.course_id, TrainingPackageState.LIVE, "training/1/b/"),
        )

        found = await self.repo.get_by_state(
            self.session, self.course_id, TrainingPackageState.LIVE
        )
        self.assertEqual(found.storage_prefix, "training/1/b/")


if __name__ == "__main__":
    unittest.main()
