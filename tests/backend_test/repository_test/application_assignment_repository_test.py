import unittest
from datetime import datetime, timezone
from backend.common.mentorship_enums import CommunicationMethod
from backend.common.recruiting_enums import ApplicationStage, JobKind, JobStatus
from backend.entity.application_entity import ApplicationEntity
from backend.entity.job_entity import JobEntity
from backend.entity.users_entity import UsersEntity
from backend.repository.application_assignment_repository import (
    ApplicationAssignmentRepository,
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


class TestApplicationAssignmentRepository(BaseRepositoryTestLib):
    async def _seed_application(self):
        """Create a job, an owner/applicant, and one application for it.

        Returns:
            tuple[ApplicationEntity, UsersEntity]: The seeded application and
                the owner user (usable as an ``assigned_by`` actor).
        """
        job = JobEntity(kind=JobKind.ACTIVITY, title="T", status=JobStatus.PUBLISHED)
        owner = _make_user()
        await self.insert_entities([job, owner])
        app = ApplicationEntity(
            job_id=job.job_id,
            user_id=owner.user_id,
            stage=ApplicationStage.RECRUITER_SCREENING,
        )
        await self.insert_entities([app])
        return app, owner

    async def _seed_users(self, n):
        """Create and insert ``n`` distinct users.

        Args:
            n (int): How many users to create.

        Returns:
            list[UsersEntity]: The inserted users, each with a populated id.
        """
        users = [_make_user() for _ in range(n)]
        await self.insert_entities(users)
        return users

    async def test_get_returns_none_before_assignment(self):
        app, _owner = await self._seed_application()
        repo = ApplicationAssignmentRepository()

        result = await repo.get(
            self.session, app.application_id, ApplicationStage.RECRUITER_SCREENING, 1
        )

        self.assertIsNone(result)

    async def test_upsert_creates_then_overwrites(self):
        app, owner = await self._seed_application()
        assignee_a, assignee_b = await self._seed_users(2)
        repo = ApplicationAssignmentRepository()

        first = await repo.upsert(
            self.session,
            app.application_id,
            ApplicationStage.RECRUITER_SCREENING,
            1,
            assignee_a.user_id,
            owner.user_id,
        )
        self.assertEqual(first.assignee_id, assignee_a.user_id)

        second = await repo.upsert(
            self.session,
            app.application_id,
            ApplicationStage.RECRUITER_SCREENING,
            1,
            assignee_b.user_id,
            owner.user_id,
        )

        self.assertEqual(second.assignee_id, assignee_b.user_id)
        self.assertEqual(first.assignment_id, second.assignment_id)

        fetched = await repo.get(
            self.session, app.application_id, ApplicationStage.RECRUITER_SCREENING, 1
        )
        self.assertEqual(fetched.assignee_id, assignee_b.user_id)
        self.assertEqual(fetched.assigned_by, owner.user_id)

    async def test_upsert_same_stage_different_round_creates_separate_rows(self):
        app, owner = await self._seed_application()
        assignee_a, assignee_b = await self._seed_users(2)
        repo = ApplicationAssignmentRepository()

        round_one = await repo.upsert(
            self.session,
            app.application_id,
            ApplicationStage.RECRUITER_SCREENING,
            1,
            assignee_a.user_id,
            owner.user_id,
        )
        round_two = await repo.upsert(
            self.session,
            app.application_id,
            ApplicationStage.RECRUITER_SCREENING,
            2,
            assignee_b.user_id,
            owner.user_id,
        )

        self.assertNotEqual(round_one.assignment_id, round_two.assignment_id)
        fetched_round_one = await repo.get(
            self.session, app.application_id, ApplicationStage.RECRUITER_SCREENING, 1
        )
        self.assertEqual(fetched_round_one.assignee_id, assignee_a.user_id)

    async def test_list_by_assignee_returns_only_that_assignees_rows(self):
        job2 = JobEntity(kind=JobKind.ACTIVITY, title="T2", status=JobStatus.PUBLISHED)
        owner = _make_user()
        await self.insert_entities([job2, owner])
        app1, _ = await self._seed_application()
        app2 = ApplicationEntity(
            job_id=job2.job_id,
            user_id=owner.user_id,
            stage=ApplicationStage.RECRUITER_SCREENING,
        )
        await self.insert_entities([app2])
        assignee, other_assignee = await self._seed_users(2)
        repo = ApplicationAssignmentRepository()

        await repo.upsert(
            self.session,
            app1.application_id,
            ApplicationStage.RECRUITER_SCREENING,
            1,
            assignee.user_id,
            owner.user_id,
        )
        await repo.upsert(
            self.session,
            app2.application_id,
            ApplicationStage.RECRUITER_SCREENING,
            1,
            assignee.user_id,
            owner.user_id,
        )
        await repo.upsert(
            self.session,
            app1.application_id,
            ApplicationStage.BEHAVIORAL,
            1,
            other_assignee.user_id,
            owner.user_id,
        )

        results = await repo.list_by_assignee(self.session, assignee.user_id)

        self.assertEqual(len(results), 2)
        self.assertEqual(
            {r.application_id for r in results},
            {app1.application_id, app2.application_id},
        )
        self.assertTrue(all(r.assignee_id == assignee.user_id for r in results))

    async def test_list_by_application_ids_returns_rows_for_given_apps(self):
        app1, owner = await self._seed_application()
        other_applicants = await self._seed_users(2)
        app2 = ApplicationEntity(
            job_id=app1.job_id,
            user_id=other_applicants[0].user_id,
            stage=ApplicationStage.TECH,
        )
        app3 = ApplicationEntity(
            job_id=app1.job_id,
            user_id=other_applicants[1].user_id,
            stage=ApplicationStage.TECH,
        )
        await self.insert_entities([app2, app3])
        assignee = await self._seed_users(1)
        repo = ApplicationAssignmentRepository()

        await repo.upsert(
            self.session,
            app1.application_id,
            ApplicationStage.RECRUITER_SCREENING,
            1,
            assignee[0].user_id,
            owner.user_id,
        )
        await repo.upsert(
            self.session,
            app2.application_id,
            ApplicationStage.TECH,
            1,
            assignee[0].user_id,
            owner.user_id,
        )
        await repo.upsert(
            self.session,
            app3.application_id,
            ApplicationStage.TECH,
            1,
            assignee[0].user_id,
            owner.user_id,
        )

        results = await repo.list_by_application_ids(
            self.session, [app1.application_id, app2.application_id]
        )

        self.assertEqual(
            {r.application_id for r in results},
            {app1.application_id, app2.application_id},
        )

    async def test_list_by_application_ids_empty_input_returns_empty_list(self):
        repo = ApplicationAssignmentRepository()

        results = await repo.list_by_application_ids(self.session, [])

        self.assertEqual(results, [])


if __name__ == "__main__":
    unittest.main()
