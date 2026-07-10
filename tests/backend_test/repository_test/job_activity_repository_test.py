import unittest
import uuid
from datetime import datetime, timezone

from backend.common.mentorship_enums import CommunicationMethod
from backend.common.recruiting_enums import JobKind, JobStatus
from backend.entity.job_entity import JobEntity
from backend.entity.users_entity import UsersEntity
from backend.repository.job_activity_repository import JobActivityRepository
from tests.backend_test.repository_test.base_repository_test_lib import (
    BaseRepositoryTestLib,
)


def _make_user() -> UsersEntity:
    """Build a UsersEntity satisfying every NOT NULL column, unique email."""
    return UsersEntity(
        first_name="A",
        last_name="B",
        timezone="America/Los_Angeles",
        timezone_updated_at=datetime.now(timezone.utc),
        communication_channel=CommunicationMethod.EMAIL,
        primary_email=f"{uuid.uuid4().hex}@test.com",
        is_active=True,
        updated_timestamp=datetime.now(timezone.utc),
    )


class TestJobActivityRepository(BaseRepositoryTestLib):
    async def asyncSetUp(self):
        await super().asyncSetUp()
        self.repo = JobActivityRepository()
        self.user = _make_user()
        self.job = JobEntity(kind=JobKind.ACTIVITY, title="T", status=JobStatus.DRAFT)
        await self.insert_entities([self.user, self.job])
        self.user_id = self.user.user_id
        self.job_id = self.job.job_id

    async def test_create_and_list_by_job(self):
        await self.repo.create(
            self.session, self.job_id, self.user_id, "job_created", {}
        )

        rows = await self.repo.list_by_job(self.session, self.job_id)

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].job_id, self.job_id)
        self.assertEqual(rows[0].actor_id, self.user_id)
        self.assertEqual(rows[0].event_type, "job_created")

    async def test_list_by_job_orders_newest_first(self):
        await self.repo.create(self.session, self.job_id, self.user_id, "job_created")
        await self.repo.create(self.session, self.job_id, self.user_id, "review_opened")

        rows = await self.repo.list_by_job(self.session, self.job_id)

        self.assertEqual([r.event_type for r in rows], ["review_opened", "job_created"])


if __name__ == "__main__":
    unittest.main()
