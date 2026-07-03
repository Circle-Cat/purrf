import unittest
import uuid
from datetime import datetime, timezone
from backend.common.mentorship_enums import CommunicationMethod
from backend.common.recruiting_enums import ApplicationStage, JobKind, JobStatus
from backend.entity.application_entity import ApplicationEntity
from backend.entity.job_entity import JobEntity
from backend.entity.users_entity import UsersEntity
from backend.repository.evaluation_repository import EvaluationRepository
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
        primary_email=f"{uuid.uuid4().hex}@test.com",
        is_active=True,
        updated_timestamp=datetime.now(timezone.utc),
    )


class TestEvaluationRepository(BaseRepositoryTestLib):
    async def _seed_application(self):
        """Create a job, an applicant, and one application for it.

        Returns:
            ApplicationEntity: The seeded application.
        """
        job = JobEntity(kind=JobKind.ACTIVITY, title="T", status=JobStatus.PUBLISHED)
        applicant = _make_user()
        await self.insert_entities([job, applicant])
        app = ApplicationEntity(
            job_id=job.job_id,
            user_id=applicant.user_id,
            stage=ApplicationStage.RECRUITER_SCREENING,
        )
        await self.insert_entities([app])
        return app

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

    async def test_get_returns_none_before_any_draft(self):
        app = await self._seed_application()
        (evaluator,) = await self._seed_users(1)
        repo = EvaluationRepository()

        result = await repo.get(
            self.session,
            app.application_id,
            ApplicationStage.RECRUITER_SCREENING,
            evaluator.user_id,
        )

        self.assertIsNone(result)

    async def test_upsert_draft_creates_then_updates_same_row(self):
        app = await self._seed_application()
        (evaluator,) = await self._seed_users(1)
        repo = EvaluationRepository()

        first = await repo.upsert_draft(
            self.session,
            app.application_id,
            ApplicationStage.RECRUITER_SCREENING,
            evaluator.user_id,
            {"rating": 1},
        )
        self.assertEqual(first.responses, {"rating": 1})

        second = await repo.upsert_draft(
            self.session,
            app.application_id,
            ApplicationStage.RECRUITER_SCREENING,
            evaluator.user_id,
            {"rating": 5},
        )

        self.assertEqual(second.evaluation_id, first.evaluation_id)
        self.assertEqual(second.responses, {"rating": 5})

        fetched = await repo.get(
            self.session,
            app.application_id,
            ApplicationStage.RECRUITER_SCREENING,
            evaluator.user_id,
        )
        self.assertEqual(fetched.evaluation_id, first.evaluation_id)
        self.assertEqual(fetched.responses, {"rating": 5})

    async def test_upsert_draft_on_confirmed_row_raises(self):
        app = await self._seed_application()
        (evaluator,) = await self._seed_users(1)
        repo = EvaluationRepository()

        draft = await repo.upsert_draft(
            self.session,
            app.application_id,
            ApplicationStage.RECRUITER_SCREENING,
            evaluator.user_id,
            {"rating": 1},
        )
        await repo.confirm(self.session, draft, datetime.now(timezone.utc))

        with self.assertRaises(ValueError):
            await repo.upsert_draft(
                self.session,
                app.application_id,
                ApplicationStage.RECRUITER_SCREENING,
                evaluator.user_id,
                {"rating": 2},
            )

    async def test_confirm_sets_fields_and_is_retrievable(self):
        app = await self._seed_application()
        (evaluator,) = await self._seed_users(1)
        repo = EvaluationRepository()
        draft = await repo.upsert_draft(
            self.session,
            app.application_id,
            ApplicationStage.RECRUITER_SCREENING,
            evaluator.user_id,
            {"rating": 3},
        )
        confirmed_at = datetime.now(timezone.utc)

        confirmed = await repo.confirm(self.session, draft, confirmed_at)

        self.assertTrue(confirmed.is_confirmed)
        self.assertEqual(confirmed.confirmed_at, confirmed_at)

        fetched = await repo.get(
            self.session,
            app.application_id,
            ApplicationStage.RECRUITER_SCREENING,
            evaluator.user_id,
        )
        self.assertTrue(fetched.is_confirmed)
        self.assertEqual(fetched.confirmed_at, confirmed_at)

    async def test_list_by_assignee_returns_only_that_evaluators_rows(self):
        app1 = await self._seed_application()
        job2 = JobEntity(kind=JobKind.ACTIVITY, title="T2", status=JobStatus.PUBLISHED)
        applicant2 = _make_user()
        await self.insert_entities([job2, applicant2])
        app2 = ApplicationEntity(
            job_id=job2.job_id,
            user_id=applicant2.user_id,
            stage=ApplicationStage.RECRUITER_SCREENING,
        )
        await self.insert_entities([app2])
        evaluator, other_evaluator = await self._seed_users(2)
        repo = EvaluationRepository()

        await repo.upsert_draft(
            self.session,
            app1.application_id,
            ApplicationStage.RECRUITER_SCREENING,
            evaluator.user_id,
            {"rating": 1},
        )
        await repo.upsert_draft(
            self.session,
            app2.application_id,
            ApplicationStage.RECRUITER_SCREENING,
            evaluator.user_id,
            {"rating": 2},
        )
        await repo.upsert_draft(
            self.session,
            app1.application_id,
            ApplicationStage.BEHAVIORAL,
            other_evaluator.user_id,
            {"rating": 9},
        )

        results = await repo.list_by_assignee(self.session, evaluator.user_id)

        self.assertEqual(len(results), 2)
        self.assertEqual(
            {r.application_id for r in results},
            {app1.application_id, app2.application_id},
        )
        self.assertTrue(all(r.evaluator_id == evaluator.user_id for r in results))


if __name__ == "__main__":
    unittest.main()
