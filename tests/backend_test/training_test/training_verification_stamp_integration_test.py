"""Proves the stamp write lands where the course row's fields read it back.

TrainingProgressService writes the verification stamp on the LIVE package row,
and TrainingCourseService reads that same row's fields into the course DTO.
Each is unit-tested against mocks on its own; this closes the gap between
them: a completed run must make a fresh read of the package actually carry
the stamp, not merely set a field a mock never checked.
"""

import logging
import unittest
from datetime import datetime, timedelta, timezone

from backend.common.mentorship_enums import (
    CommunicationMethod,
    ScormVersion,
    TrainingPackageState,
    TrainingStatus,
)
from backend.dto.training_course_dto import TrainingCourseLiveState
from backend.entity.training_course_entity import TrainingCourseEntity
from backend.entity.training_course_package_entity import (
    TrainingCoursePackageEntity,
)
from backend.entity.training_entity import TrainingEntity
from backend.entity.users_entity import UsersEntity
from backend.repository.training_course_package_repository import (
    TrainingCoursePackageRepository,
)
from backend.repository.training_progress_repository import (
    TrainingProgressRepository,
)
from backend.repository.training_repository import TrainingRepository
from backend.training.training_content_token import issue_content_token
from backend.training.training_course_service import derive_live_state
from backend.training.training_progress_service import TrainingProgressService
from tests.backend_test.repository_test.base_repository_test_lib import (
    BaseRepositoryTestLib,
)

_SIGNING_KEY = "integration-test-signing-key"


class TestACompletedRunsStampSurvivesAFreshReadEndToEnd(BaseRepositoryTestLib):
    async def asyncSetUp(self):
        await super().asyncSetUp()
        self.package_repository = TrainingCoursePackageRepository()
        self.training_repository = TrainingRepository()
        self.progress_repository = TrainingProgressRepository()
        self.service = TrainingProgressService(
            logger=logging.getLogger(__name__),
            signing_key=_SIGNING_KEY,
            training_repository=self.training_repository,
            training_progress_repository=self.progress_repository,
            training_course_package_repository=self.package_repository,
        )

        user = UsersEntity(
            first_name="Ada",
            last_name="Lovelace",
            timezone="Asia/Shanghai",
            timezone_updated_at=datetime.now(timezone.utc),
            communication_channel=CommunicationMethod.EMAIL,
            is_active=True,
            updated_timestamp=datetime.now(timezone.utc),
        )
        await self.insert_entities([user])
        self.user_id = user.user_id

        self.course = TrainingCourseEntity(name="Real Package Course", is_active=True)
        await self.insert_entities([self.course])

        self.uploaded_at = datetime.now(timezone.utc) - timedelta(hours=1)
        self.package = TrainingCoursePackageEntity(
            course_id=self.course.course_id,
            state=TrainingPackageState.LIVE,
            storage_prefix="training/1/aaa/",
            entry_path="scormcontent/index.html",
            scorm_version=ScormVersion.SCORM_12,
            uploaded_at=self.uploaded_at,
        )
        await self.insert_entities([self.package])

        self.assignment = TrainingEntity(
            user_id=self.user_id,
            course_id=self.course.course_id,
            status=TrainingStatus.IN_PROGRESS,
        )
        await self.insert_entities([self.assignment])

    def _token_for_the_live_package(self) -> str:
        token, _ = issue_content_token(
            _SIGNING_KEY,
            self.assignment.training_id,
            self.user_id,
            package_id=self.package.package_id,
        )
        return token

    async def test_a_completed_run_leaves_its_stamp_on_a_fresh_read(self):
        # Before the run, the course already reads LIVE -- that only asks
        # whether the slot is filled -- but the package itself carries no
        # verification stamp yet.
        before = await self.package_repository.get_by_state(
            self.session, self.course.course_id, TrainingPackageState.LIVE
        )
        self.assertIsNone(before.verified_completable_at)
        self.assertEqual(
            derive_live_state(self.course, before), TrainingCourseLiveState.LIVE
        )

        await self.service.save(
            self.session,
            self.assignment.training_id,
            self.user_id,
            {"cmi.core.lesson_status": "completed"},
            may_verify_course=True,
            session_token=self._token_for_the_live_package(),
        )

        # expire_on_commit=False means the session would otherwise hand back
        # the same identity-mapped object the service just wrote through --
        # expire it first so this really re-selects the row from Postgres,
        # the way the admin course list's own fresh session would. Only the
        # package: expiring the whole session would also expire self.course
        # and force a lazy load outside the async context when it is read
        # below.
        self.session.expire(before)
        after = await self.package_repository.get_by_state(
            self.session, self.course.course_id, TrainingPackageState.LIVE
        )
        self.assertIsNotNone(after.verified_completable_at)
        self.assertEqual(after.verified_by_user_id, self.user_id)
        # The stamp changed the package row, not whether a learner can open
        # it -- the course read LIVE before the run and still does after.
        self.assertEqual(
            derive_live_state(self.course, after), TrainingCourseLiveState.LIVE
        )


if __name__ == "__main__":
    unittest.main()
