import unittest
from datetime import datetime, timezone
from backend.common.mentorship_enums import CommunicationMethod
from backend.common.recruiting_enums import ApplicationStage, JobKind, JobStatus
from backend.entity.application_entity import ApplicationEntity
from backend.entity.job_entity import JobEntity
from backend.entity.users_entity import UsersEntity
from backend.repository.application_comment_repository import (
    ApplicationCommentRepository,
)
from tests.backend_test.repository_test.base_repository_test_lib import (
    BaseRepositoryTestLib,
)


def _make_user() -> UsersEntity:
    """Build a UsersEntity satisfying every NOT NULL column, unique email."""
    return UsersEntity(
        first_name="U",
        last_name="Ser",
        timezone="America/Los_Angeles",
        timezone_updated_at=datetime.now(timezone.utc),
        communication_channel=CommunicationMethod.EMAIL,
        is_active=True,
        updated_timestamp=datetime.now(timezone.utc),
    )


class TestApplicationCommentRepository(BaseRepositoryTestLib):
    async def _seed_application(self):
        """Create a job, an author user, and one application for it.

        Returns:
            tuple[ApplicationEntity, UsersEntity]: The seeded application and
                an author usable for posted comments.
        """
        job = JobEntity(kind=JobKind.ACTIVITY, title="T", status=JobStatus.PUBLISHED)
        author = _make_user()
        await self.insert_entities([job, author])
        app = ApplicationEntity(
            job_id=job.job_id,
            user_id=author.user_id,
            stage=ApplicationStage.RECRUITER_SCREENING,
        )
        await self.insert_entities([app])
        return app, author

    async def test_list_by_application_returns_empty_before_any_comment(self):
        app, _author = await self._seed_application()
        repo = ApplicationCommentRepository()

        result = await repo.list_by_application(self.session, app.application_id)

        self.assertEqual(result, [])

    async def test_create_persists_application_author_and_body(self):
        app, author = await self._seed_application()
        repo = ApplicationCommentRepository()

        created = await repo.create(
            self.session, app.application_id, author.user_id, "Looks strong."
        )

        self.assertEqual(created.application_id, app.application_id)
        self.assertEqual(created.author_id, author.user_id)
        self.assertEqual(created.body, "Looks strong.")

    async def test_list_by_application_returns_newest_first(self):
        app, author = await self._seed_application()
        repo = ApplicationCommentRepository()

        first = await repo.create(
            self.session, app.application_id, author.user_id, "First comment"
        )
        second = await repo.create(
            self.session, app.application_id, author.user_id, "Second comment"
        )

        result = await repo.list_by_application(self.session, app.application_id)

        self.assertEqual(
            [row.comment_id for row in result],
            [second.comment_id, first.comment_id],
        )

    async def test_list_by_application_only_returns_rows_for_that_application(self):
        app1, author = await self._seed_application()
        job2 = JobEntity(kind=JobKind.ACTIVITY, title="T2", status=JobStatus.PUBLISHED)
        await self.insert_entities([job2])
        app2 = ApplicationEntity(
            job_id=job2.job_id,
            user_id=author.user_id,
            stage=ApplicationStage.RECRUITER_SCREENING,
        )
        await self.insert_entities([app2])
        repo = ApplicationCommentRepository()

        await repo.create(self.session, app1.application_id, author.user_id, "On app1")
        await repo.create(self.session, app2.application_id, author.user_id, "On app2")

        result = await repo.list_by_application(self.session, app1.application_id)

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].application_id, app1.application_id)


if __name__ == "__main__":
    unittest.main()
