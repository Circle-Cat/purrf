"""Proves the stamp write and the state read agree, against a real database.

TrainingProgressService writes the verification stamp on the LIVE package row,
and TrainingCourseService derives a course's state from that same row. Each is
unit-tested against mocks on its own; this closes the gap between them: a
completed run must make the course actually read VERIFIED, not merely set a
field a mock never checked.
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
from backend.dto.training_course_dto import TrainingCourseState
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
from backend.training.training_course_service import derive_course_state
from backend.training.training_progress_service import TrainingProgressService
from tests.backend_test.repository_test.base_repository_test_lib import (
    BaseRepositoryTestLib,
)

_SIGNING_KEY = "integration-test-signing-key"


class TestACompletedRunDerivesVerifiedEndToEnd(BaseRepositoryTestLib):
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

    def _token_opened_after_upload(self) -> str:
        opened_at = int((self.uploaded_at + timedelta(minutes=5)).timestamp())
        token, _ = issue_content_token(
            _SIGNING_KEY, self.assignment.training_id, self.user_id, now=opened_at
        )
        return token

    async def test_a_completed_run_makes_the_course_read_verified(self):
        # Before the run, the course has no proof and reads NEEDS_TRIAL_RUN.
        before = await self.package_repository.get_by_state(
            self.session, self.course.course_id, TrainingPackageState.LIVE
        )
        self.assertEqual(
            derive_course_state(self.course, before),
            TrainingCourseState.NEEDS_TRIAL_RUN,
        )

        await self.service.save(
            self.session,
            self.assignment.training_id,
            self.user_id,
            {"cmi.core.lesson_status": "completed"},
            may_verify_course=True,
            session_token=self._token_opened_after_upload(),
        )

        # A fresh read, the way the admin course list actually reads it --
        # not the same Python object the service just wrote through.
        after = await self.package_repository.get_by_state(
            self.session, self.course.course_id, TrainingPackageState.LIVE
        )
        self.assertIsNotNone(after.verified_completable_at)
        self.assertEqual(after.verified_by_user_id, self.user_id)
        self.assertEqual(
            derive_course_state(self.course, after), TrainingCourseState.VERIFIED
        )


if __name__ == "__main__":
    unittest.main()
