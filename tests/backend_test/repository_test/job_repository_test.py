import unittest
from backend.entity.job_entity import JobEntity
from backend.repository.job_repository import JobRepository
from backend.common.recruiting_enums import JobKind, JobStatus
from backend.common.mentorship_enums import ParticipantRole
from tests.backend_test.repository_test.base_repository_test_lib import (
    BaseRepositoryTestLib,
)


class TestJobRepository(BaseRepositoryTestLib):
    async def asyncSetUp(self):
        await super().asyncSetUp()
        self.repo = JobRepository()

    async def test_create_and_get(self):
        job = JobEntity(
            kind=JobKind.ACTIVITY,
            mentorship_role=ParticipantRole.MENTOR,
            status=JobStatus.DRAFT,
            title="Mentor 2026",
            description="Be a mentor",
            form_schema={"type": "object", "properties": {}},
        )
        created = await self.repo.create_job(self.session, job)
        self.assertIsNotNone(created.job_id)

        fetched = await self.repo.get_by_job_id(self.session, created.job_id)
        self.assertEqual(fetched.title, "Mentor 2026")
        self.assertEqual(fetched.mentorship_role, ParticipantRole.MENTOR)
        self.assertEqual(fetched.status, JobStatus.DRAFT)

    async def test_list_published_only(self):
        draft = JobEntity(kind=JobKind.ACTIVITY, status=JobStatus.DRAFT, title="d")
        pub = JobEntity(kind=JobKind.ACTIVITY, status=JobStatus.PUBLISHED, title="p")
        await self.insert_entities([draft, pub])
        published = await self.repo.list_published(self.session)
        titles = {j.title for j in published}
        self.assertIn("p", titles)
        self.assertNotIn("d", titles)


if __name__ == "__main__":
    unittest.main()
