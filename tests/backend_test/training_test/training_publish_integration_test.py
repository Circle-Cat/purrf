"""Publishing over a live package, against the index that forbids two.

Every other publish test drives the service with mocks, and the one write a
mock cannot vouch for is this one: the outgoing row has to leave the live slot
before the incoming row takes it, and what forbids the overlap is a partial
unique index in Postgres rather than anything the service can be observed
doing. Asserting the flush order against a mock and asserting the index
against a bare repository are two halves of an argument; this is the whole of
it, in one transaction, through the service the route calls.
"""

import logging
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

from backend.common.mentorship_enums import ScormVersion, TrainingPackageState
from backend.entity.training_course_entity import TrainingCourseEntity
from backend.entity.training_course_package_entity import (
    TrainingCoursePackageEntity,
)

# Imported for its side effect only: a package's uploaded_by_user_id and
# verified_by_user_id point at users, and SQLAlchemy cannot configure the
# package mapper until that table is in the registry.
from backend.entity.users_entity import UsersEntity  # noqa: F401
from backend.repository.training_course_package_repository import (
    TrainingCoursePackageRepository,
)
from backend.repository.training_course_repository import TrainingCourseRepository
from backend.repository.training_progress_repository import (
    TrainingProgressRepository,
)
from backend.training.training_package_service import TrainingPackageService
from tests.backend_test.repository_test.base_repository_test_lib import (
    BaseRepositoryTestLib,
)

_OUTGOING_PREFIX = "training/1/outgoing/"
_INCOMING_PREFIX = "training/1/incoming/"


class TestPublishingOverALivePackageEndToEnd(BaseRepositoryTestLib):
    async def asyncSetUp(self):
        await super().asyncSetUp()
        self.package_repository = TrainingCoursePackageRepository()
        self.storage = MagicMock()
        self.service = TrainingPackageService(
            logger=logging.getLogger(__name__),
            training_course_repository=TrainingCourseRepository(),
            training_progress_repository=TrainingProgressRepository(),
            training_course_package_repository=self.package_repository,
            training_storage=self.storage,
        )

        self.course = TrainingCourseEntity(name="Cat Care Fundamentals", is_active=True)
        await self.insert_entities([self.course])

        now = datetime.now(timezone.utc)
        self.outgoing = self._package(
            TrainingPackageState.LIVE, _OUTGOING_PREFIX, now - timedelta(days=7)
        )
        self.incoming = self._package(
            TrainingPackageState.PENDING, _INCOMING_PREFIX, now
        )
        # Publish refuses an unverified staged package, so the trial run this
        # test is not about has already happened.
        self.incoming.verified_completable_at = now
        await self.insert_entities([self.outgoing, self.incoming])

    def _package(self, state, prefix, uploaded_at):
        return TrainingCoursePackageEntity(
            course_id=self.course.course_id,
            state=state,
            storage_prefix=prefix,
            entry_path="scormcontent/index.html",
            scorm_version=ScormVersion.SCORM_12,
            uploaded_at=uploaded_at,
        )

    async def _slot(self, state):
        return await self.package_repository.get_by_state(
            self.session, self.course.course_id, state
        )

    async def test_the_staged_package_takes_the_slot_the_outgoing_one_vacates(self):
        result = await self.service.publish_package(self.session, self.course.course_id)

        self.assertEqual(result.package_id, self.incoming.package_id)
        live = await self._slot(TrainingPackageState.LIVE)
        self.assertEqual(live.package_id, self.incoming.package_id)
        self.assertEqual(live.storage_prefix, _INCOMING_PREFIX)
        # Nothing is left staged, and the row that was live is gone rather
        # than parked in the other slot.
        self.assertIsNone(await self._slot(TrainingPackageState.PENDING))
        self.assertIsNone(
            await self.package_repository.get_by_id(
                self.session, self.outgoing.package_id
            )
        )
        self.storage.delete_prefix.assert_called_once_with(_OUTGOING_PREFIX)


if __name__ == "__main__":
    unittest.main()
