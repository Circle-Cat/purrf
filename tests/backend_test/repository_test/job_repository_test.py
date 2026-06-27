import unittest

from backend.repository.job_repository import JobRepository
from backend.entity.job_entity import JobEntity
from backend.common.recruiting_enums import JobKind, JobStatus
from tests.backend_test.repository_test.base_repository_test_lib import (
    BaseRepositoryTestLib,
)


class TestJobRepository(BaseRepositoryTestLib):
    async def asyncSetUp(self):
        await super().asyncSetUp()
        self.repo = JobRepository()

    async def test_persists_pipeline_config_and_pending(self):
        """create_job round-trips pipeline_config; pending fields default to None."""
        job = JobEntity(
            kind=JobKind.EMPLOYMENT,
            title="SWE Intern",
            status=JobStatus.DRAFT,
            pipeline_config=[
                {"stage": "recruiter_screening", "referral_skippable": False}
            ],
        )
        saved = await self.repo.create_job(self.session, job)

        self.assertEqual(saved.pipeline_config[0]["stage"], "recruiter_screening")
        self.assertIsNone(saved.pending_form_schema)
        self.assertIsNone(saved.pending_pipeline_config)

    async def test_list_all_returns_every_status(self):
        """list_all returns jobs regardless of status."""
        await self.repo.create_job(
            self.session,
            JobEntity(kind=JobKind.ACTIVITY, title="A", status=JobStatus.DRAFT),
        )
        await self.repo.create_job(
            self.session,
            JobEntity(kind=JobKind.ACTIVITY, title="B", status=JobStatus.CLOSED),
        )
        rows = await self.repo.list_all(self.session)

        titles = {r.title for r in rows}
        self.assertIn("A", titles)
        self.assertIn("B", titles)


if __name__ == "__main__":
    unittest.main()
