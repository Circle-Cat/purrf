import unittest
from datetime import datetime, timezone

from sqlalchemy import event
from sqlalchemy.dialects import postgresql

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
                is_active=True,
                updated_timestamp=now,
            ),
            UsersEntity(
                first_name="Re",
                last_name="Viewer",
                timezone="America/New_York",
                timezone_updated_at=now,
                communication_channel=CommunicationMethod.EMAIL,
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

    async def _sql_of_get_open_for_job(self, **kwargs):
        """The SQL ``get_open_for_job`` actually issues, for lock assertions.

        Mirrors ``training_repository_test``'s capture: the flag is only worth
        anything if it reaches the statement, and a silently ignored one reads
        the same as a working one from the return value alone.
        """
        captured = []

        def capture(conn, clauseelement, multiparams, params, execution_options):
            captured.append(clauseelement)

        event.listen(self.connection.sync_connection, "before_execute", capture)
        try:
            await self.repo.get_open_for_job(self.session, self.job.job_id, **kwargs)
        finally:
            event.remove(self.connection.sync_connection, "before_execute", capture)

        return [
            str(statement.compile(dialect=postgresql.dialect()))
            for statement in captured
            if hasattr(statement, "compile")
        ]

    async def test_the_read_a_reassignment_makes_locks_the_row(self):
        """Reassigning reads the open review, then overwrites its reviewer.

        Without the lock an approve can commit in between, leaving a decided
        review whose reviewer_id names somebody who never saw it.
        """
        sqls = await self._sql_of_get_open_for_job(for_update=True)

        self.assertTrue(
            any("FOR UPDATE" in sql for sql in sqls),
            f"Expected FOR UPDATE when for_update=True. Got: {sqls}",
        )

    async def test_a_plain_open_review_read_takes_no_lock(self):
        """get_job reads the open review on every page view; locking there
        would make every viewer wait behind whoever is deciding it."""
        sqls = await self._sql_of_get_open_for_job()

        self.assertFalse(
            any("FOR UPDATE" in sql for sql in sqls),
            f"Expected no lock by default. Got: {sqls}",
        )

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

    async def test_get_latest_reviews_returns_newest_per_job(self):
        """get_latest_reviews returns the most-recent review per job_id (REJECTED wins over older APPROVED)."""
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
        newer = await self.repo.create(
            self.session,
            JobReviewEntity(
                job_id=self.job.job_id,
                submitted_by=self.submitter_id,
                reviewer_id=self.reviewer_id,
                status=JobReviewStatus.REJECTED,
                kind=JobReviewKind.REVISION,
                reject_comment="needs work",
            ),
        )

        result = await self.repo.get_latest_reviews(self.session, [self.job.job_id])

        self.assertIn(self.job.job_id, result)
        self.assertEqual(result[self.job.job_id].review_id, newer.review_id)
        self.assertEqual(result[self.job.job_id].status, JobReviewStatus.REJECTED)

    async def test_get_latest_reviews_empty_job_ids_returns_empty(self):
        """get_latest_reviews with no job_ids returns {} without querying."""
        result = await self.repo.get_latest_reviews(self.session, [])

        self.assertEqual(result, {})


if __name__ == "__main__":
    unittest.main()
