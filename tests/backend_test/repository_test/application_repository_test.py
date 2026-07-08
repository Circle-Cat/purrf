from backend.entity.application_entity import ApplicationEntity
from backend.entity.application_submission_entity import ApplicationSubmissionEntity
from backend.entity.job_entity import JobEntity
from backend.entity.users_entity import UsersEntity
from backend.common.recruiting_enums import ApplicationStage, JobKind, JobStatus
from backend.repository.application_repository import ApplicationRepository
from backend.repository.application_submission_repository import (
    ApplicationSubmissionRepository,
)
from tests.backend_test.repository_test.base_repository_test_lib import (
    BaseRepositoryTestLib,
)


class TestApplicationRepository(BaseRepositoryTestLib):
    async def _seed_job_and_user(self):
        job = JobEntity(kind=JobKind.ACTIVITY, title="T", status=JobStatus.PUBLISHED)
        user = UsersEntity(first_name="A", last_name="B", primary_email="a@b.com")
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
        user_a = UsersEntity(first_name="A", last_name="One", primary_email="a1@b.com")
        user_b = UsersEntity(first_name="B", last_name="Two", primary_email="b2@b.com")
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
        job_a = JobEntity(kind=JobKind.ACTIVITY, title="Job A", status=JobStatus.PUBLISHED)
        job_b = JobEntity(kind=JobKind.ACTIVITY, title="Job B", status=JobStatus.PUBLISHED)
        user_a = UsersEntity(first_name="A", last_name="One", primary_email="a1@b.com")
        user_b = UsersEntity(first_name="B", last_name="Two", primary_email="b2@b.com")
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
            {(app_a1.application_id, job_a.job_id), (app_a2.application_id, job_b.job_id)},
        )
