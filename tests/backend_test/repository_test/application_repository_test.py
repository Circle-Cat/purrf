import unittest
from datetime import date, datetime, timezone

from backend.entity.application_entity import ApplicationEntity
from backend.entity.application_submission_entity import ApplicationSubmissionEntity
from backend.entity.job_entity import JobEntity
from backend.entity.users_entity import UsersEntity
from backend.common.recruiting_enums import ApplicationStage, JobKind, JobStatus
from backend.common.mentorship_enums import CommunicationMethod
from backend.repository.application_repository import ApplicationRepository
from backend.repository.application_submission_repository import (
    ApplicationSubmissionRepository,
)
from tests.backend_test.repository_test.base_repository_test_lib import (
    BaseRepositoryTestLib,
)


def _make_user(first_name: str, last_name: str, primary_email: str) -> UsersEntity:
    """Build a UsersEntity satisfying every NOT NULL column."""
    return UsersEntity(
        first_name=first_name,
        last_name=last_name,
        timezone="UTC",
        timezone_updated_at=datetime.now(timezone.utc),
        communication_channel=CommunicationMethod.EMAIL,
        primary_email=primary_email,
        is_active=True,
        updated_timestamp=datetime.now(timezone.utc),
    )


class TestApplicationRepository(BaseRepositoryTestLib):
    async def _seed_job_and_user(self):
        job = JobEntity(kind=JobKind.ACTIVITY, title="T", status=JobStatus.PUBLISHED)
        user = _make_user("A", "B", "a@b.com")
        await self.insert_entities([job, user])
        await self.session.flush()
        return job, user

    async def test_create_and_get_by_job_and_user(self):
        job, user = await self._seed_job_and_user()
        repo = ApplicationRepository()
        created = await repo.create(
            self.session,
            ApplicationEntity(
                job_id=job.job_id, user_id=user.user_id, stage=ApplicationStage.APPLIED
            ),
        )
        self.assertIsNotNone(created.application_id)
        found = await repo.get_by_job_and_user(self.session, job.job_id, user.user_id)
        self.assertEqual(found.application_id, created.application_id)
        self.assertIsNone(
            await repo.get_by_job_and_user(self.session, job.job_id, 999999)
        )

    async def test_submission_get_current_returns_highest_version(self):
        job, user = await self._seed_job_and_user()
        app = await ApplicationRepository().create(
            self.session,
            ApplicationEntity(job_id=job.job_id, user_id=user.user_id),
        )
        sub_repo = ApplicationSubmissionRepository()
        await sub_repo.create(
            self.session,
            ApplicationSubmissionEntity(
                application_id=app.application_id, version=1, submission={"a": 1}
            ),
        )
        await sub_repo.create(
            self.session,
            ApplicationSubmissionEntity(
                application_id=app.application_id, version=2, submission={"a": 2}
            ),
        )
        current = await sub_repo.get_current(self.session, app.application_id)
        self.assertEqual(current.version, 2)
        versions = await sub_repo.list_by_application(self.session, app.application_id)
        self.assertEqual([v.version for v in versions], [1, 2])

    async def test_list_by_job_returns_joined_rows_ordered_excluding_other_jobs(self):
        job = JobEntity(kind=JobKind.ACTIVITY, title="T", status=JobStatus.PUBLISHED)
        other_job = JobEntity(
            kind=JobKind.ACTIVITY, title="Other", status=JobStatus.PUBLISHED
        )
        user_a = _make_user("A", "One", "a1@b.com")
        user_b = _make_user("B", "Two", "b2@b.com")
        await self.insert_entities([job, other_job, user_a, user_b])
        await self.session.flush()

        repo = ApplicationRepository()
        app_a = await repo.create(
            self.session,
            ApplicationEntity(
                job_id=job.job_id,
                user_id=user_a.user_id,
                stage=ApplicationStage.APPLIED,
            ),
        )
        app_b = await repo.create(
            self.session,
            ApplicationEntity(
                job_id=job.job_id,
                user_id=user_b.user_id,
                stage=ApplicationStage.RECRUITER_SCREENING,
            ),
        )
        await repo.create(
            self.session,
            ApplicationEntity(job_id=other_job.job_id, user_id=user_a.user_id),
        )

        rows = await repo.list_by_job(self.session, job.job_id)

        self.assertEqual(len(rows), 2)
        self.assertEqual(
            [app.application_id for app, _ in rows],
            [app_a.application_id, app_b.application_id],
        )
        self.assertEqual(
            [user.user_id for _, user in rows], [user_a.user_id, user_b.user_id]
        )
        self.assertTrue(all(app.job_id == job.job_id for app, _ in rows))

    async def test_list_by_user_returns_joined_rows_across_jobs(self):
        job_a = JobEntity(
            kind=JobKind.ACTIVITY, title="Job A", status=JobStatus.PUBLISHED
        )
        job_b = JobEntity(
            kind=JobKind.ACTIVITY, title="Job B", status=JobStatus.PUBLISHED
        )
        user_a = _make_user("A", "One", "a1@b.com")
        user_b = _make_user("B", "Two", "b2@b.com")
        await self.insert_entities([job_a, job_b, user_a, user_b])
        await self.session.flush()

        repo = ApplicationRepository()
        app_a1 = await repo.create(
            self.session,
            ApplicationEntity(
                job_id=job_a.job_id,
                user_id=user_a.user_id,
                stage=ApplicationStage.APPLIED,
            ),
        )
        await repo.create(
            self.session,
            ApplicationEntity(
                job_id=job_a.job_id,
                user_id=user_b.user_id,
                stage=ApplicationStage.APPLIED,
            ),
        )
        app_a2 = await repo.create(
            self.session,
            ApplicationEntity(
                job_id=job_b.job_id,
                user_id=user_a.user_id,
                stage=ApplicationStage.APPLIED,
            ),
        )

        result = await repo.list_by_user(self.session, user_a.user_id)

        self.assertEqual(
            {(app.application_id, job.job_id) for app, job in result},
            {
                (app_a1.application_id, job_a.job_id),
                (app_a2.application_id, job_b.job_id),
            },
        )

    async def test_count_by_job_and_stage_groups_across_jobs(self):
        job_a = JobEntity(
            kind=JobKind.ACTIVITY, title="Job A", status=JobStatus.PUBLISHED
        )
        job_b = JobEntity(
            kind=JobKind.ACTIVITY, title="Job B", status=JobStatus.PUBLISHED
        )
        user_1 = _make_user("A", "One", "a1@b.com")
        user_2 = _make_user("B", "Two", "b2@b.com")
        user_3 = _make_user("C", "Three", "c3@b.com")
        await self.insert_entities([job_a, job_b, user_1, user_2, user_3])
        await self.session.flush()

        repo = ApplicationRepository()
        await repo.create(
            self.session,
            ApplicationEntity(
                job_id=job_a.job_id,
                user_id=user_1.user_id,
                stage=ApplicationStage.RECRUITER_SCREENING,
                created_datetime=datetime(2026, 6, 1, tzinfo=timezone.utc),
            ),
        )
        await repo.create(
            self.session,
            ApplicationEntity(
                job_id=job_a.job_id,
                user_id=user_2.user_id,
                stage=ApplicationStage.TECH,
                created_datetime=datetime(2026, 6, 2, tzinfo=timezone.utc),
            ),
        )
        await repo.create(
            self.session,
            ApplicationEntity(
                job_id=job_b.job_id,
                user_id=user_1.user_id,
                stage=ApplicationStage.RECRUITER_SCREENING,
                created_datetime=datetime(2026, 6, 3, tzinfo=timezone.utc),
            ),
        )
        # Outside the date range — must not be counted.
        await repo.create(
            self.session,
            ApplicationEntity(
                job_id=job_a.job_id,
                user_id=user_3.user_id,
                stage=ApplicationStage.HIRED,
                created_datetime=datetime(2026, 5, 1, tzinfo=timezone.utc),
            ),
        )

        result = await repo.count_by_job_and_stage(
            self.session, date(2026, 6, 1), date(2026, 6, 30), None
        )

        self.assertEqual(
            {(job_id, stage, count) for job_id, stage, count in result},
            {
                (job_a.job_id, ApplicationStage.RECRUITER_SCREENING, 1),
                (job_a.job_id, ApplicationStage.TECH, 1),
                (job_b.job_id, ApplicationStage.RECRUITER_SCREENING, 1),
            },
        )

    async def test_count_by_job_and_stage_filters_by_job_ids(self):
        job_a = JobEntity(
            kind=JobKind.ACTIVITY, title="Job A", status=JobStatus.PUBLISHED
        )
        job_b = JobEntity(
            kind=JobKind.ACTIVITY, title="Job B", status=JobStatus.PUBLISHED
        )
        user = _make_user("A", "One", "a1@b.com")
        await self.insert_entities([job_a, job_b, user])
        await self.session.flush()

        repo = ApplicationRepository()
        await repo.create(
            self.session,
            ApplicationEntity(
                job_id=job_a.job_id,
                user_id=user.user_id,
                stage=ApplicationStage.RECRUITER_SCREENING,
                created_datetime=datetime(2026, 6, 1, tzinfo=timezone.utc),
            ),
        )
        await repo.create(
            self.session,
            ApplicationEntity(
                job_id=job_b.job_id,
                user_id=user.user_id,
                stage=ApplicationStage.RECRUITER_SCREENING,
                created_datetime=datetime(2026, 6, 1, tzinfo=timezone.utc),
            ),
        )

        result = await repo.count_by_job_and_stage(
            self.session, date(2026, 6, 1), date(2026, 6, 30), [job_a.job_id]
        )

        self.assertEqual(
            [(job_id, stage, count) for job_id, stage, count in result],
            [(job_a.job_id, ApplicationStage.RECRUITER_SCREENING, 1)],
        )

    async def test_count_by_job_and_day_groups_by_calendar_day(self):
        job = JobEntity(
            kind=JobKind.ACTIVITY, title="Job A", status=JobStatus.PUBLISHED
        )
        user_1 = _make_user("A", "One", "a1@b.com")
        user_2 = _make_user("B", "Two", "b2@b.com")
        user_3 = _make_user("C", "Three", "c3@b.com")
        await self.insert_entities([job, user_1, user_2, user_3])
        await self.session.flush()

        repo = ApplicationRepository()
        await repo.create(
            self.session,
            ApplicationEntity(
                job_id=job.job_id,
                user_id=user_1.user_id,
                created_datetime=datetime(2026, 6, 1, 9, 0, tzinfo=timezone.utc),
            ),
        )
        await repo.create(
            self.session,
            ApplicationEntity(
                job_id=job.job_id,
                user_id=user_2.user_id,
                created_datetime=datetime(2026, 6, 1, 15, 0, tzinfo=timezone.utc),
            ),
        )
        await repo.create(
            self.session,
            ApplicationEntity(
                job_id=job.job_id,
                user_id=user_3.user_id,
                created_datetime=datetime(2026, 6, 2, 9, 0, tzinfo=timezone.utc),
            ),
        )

        result = await repo.count_by_job_and_day(
            self.session, date(2026, 6, 1), date(2026, 6, 30), None
        )

        self.assertEqual(
            {(job_id, day, count) for job_id, day, count in result},
            {
                (job.job_id, date(2026, 6, 1), 2),
                (job.job_id, date(2026, 6, 2), 1),
            },
        )

    async def test_count_methods_return_empty_for_no_matches(self):
        repo = ApplicationRepository()
        stage_result = await repo.count_by_job_and_stage(
            self.session, date(2026, 1, 1), date(2026, 1, 31), None
        )
        day_result = await repo.count_by_job_and_day(
            self.session, date(2026, 1, 1), date(2026, 1, 31), None
        )
        self.assertEqual(stage_result, [])
        self.assertEqual(day_result, [])


if __name__ == "__main__":
    unittest.main()
