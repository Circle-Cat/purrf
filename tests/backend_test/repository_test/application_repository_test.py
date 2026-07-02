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
