import unittest
from datetime import datetime, timezone

from backend.repository.job_review_repository import JobReviewRepository
from backend.entity.job_review_entity import JobReviewEntity
from backend.entity.job_entity import JobEntity
from backend.entity.users_entity import UsersEntity
from backend.common.mentorship_enums import CommunicationMethod
from backend.common.recruiting_enums import (
    JobKind,
    JobReviewKind,
    JobReviewStatus,
    JobStatus,
)
from tests.backend_test.repository_test.base_repository_test_lib import (
    BaseRepositoryTestLib,
)


class TestJobReviewRepository(BaseRepositoryTestLib):
    async def asyncSetUp(self):
        await super().asyncSetUp()
        self.repo = JobReviewRepository()

        now = datetime.now(timezone.utc)
        self.users = [
            UsersEntity(
                first_name="Sub",
                last_name="Mitter",
                timezone="Asia/Shanghai",
                timezone_updated_at=now,
                communication_channel=CommunicationMethod.EMAIL,
                primary_email="submitter@example.com",
                is_active=True,
                updated_timestamp=now,
            ),
            UsersEntity(
                first_name="Re",
                last_name="Viewer",
                timezone="America/New_York",
                timezone_updated_at=now,
                communication_channel=CommunicationMethod.EMAIL,
                primary_email="reviewer@example.com",
                is_active=True,
                updated_timestamp=now,
            ),
        ]
        await self.insert_entities(self.users)
        self.submitter_id = self.users[0].user_id
        self.reviewer_id = self.users[1].user_id

        self.job = JobEntity(
            kind=JobKind.ACTIVITY, title="Mentor", status=JobStatus.DRAFT
        )
        await self.insert_entities([self.job])

    async def test_create_and_get_open_review(self):
        """create persists a review; get_open_for_job returns the pending one."""
        rev = JobReviewEntity(
            job_id=self.job.job_id,
            submitted_by=self.submitter_id,
            reviewer_id=self.reviewer_id,
            status=JobReviewStatus.PENDING,
            kind=JobReviewKind.INITIAL,
            submit_message="pls review",
        )
        saved = await self.repo.create(self.session, rev)

        self.assertIsNotNone(saved.review_id)
        open_rev = await self.repo.get_open_for_job(self.session, self.job.job_id)
        self.assertIsNotNone(open_rev)
        self.assertEqual(open_rev.review_id, saved.review_id)

    async def test_get_open_for_job_ignores_decided(self):
        """A decided (approved) review is not returned as open."""
        await self.repo.create(
            self.session,
            JobReviewEntity(
                job_id=self.job.job_id,
                submitted_by=self.submitter_id,
                reviewer_id=self.reviewer_id,
                status=JobReviewStatus.APPROVED,
                kind=JobReviewKind.INITIAL,
            ),
        )
        self.assertIsNone(
            await self.repo.get_open_for_job(self.session, self.job.job_id)
        )

    async def test_list_by_reviewer_filters_pending(self):
        """list_by_reviewer returns only the reviewer's reviews in the given statuses."""
        await self.repo.create(
            self.session,
            JobReviewEntity(
                job_id=self.job.job_id,
                submitted_by=self.submitter_id,
                reviewer_id=self.reviewer_id,
                status=JobReviewStatus.PENDING,
                kind=JobReviewKind.INITIAL,
            ),
        )
        await self.repo.create(
            self.session,
            JobReviewEntity(
                job_id=self.job.job_id,
                submitted_by=self.submitter_id,
                reviewer_id=self.reviewer_id,
                status=JobReviewStatus.APPROVED,
                kind=JobReviewKind.INITIAL,
            ),
        )

        rows = await self.repo.list_by_reviewer(
            self.session, self.reviewer_id, [JobReviewStatus.PENDING]
        )

        self.assertEqual(len(rows), 1)
        self.assertTrue(
            all(
                r.reviewer_id == self.reviewer_id
                and r.status == JobReviewStatus.PENDING
                for r in rows
            )
        )


if __name__ == "__main__":
    unittest.main()
