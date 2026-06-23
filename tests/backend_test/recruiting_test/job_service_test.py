import unittest
from unittest.mock import AsyncMock, MagicMock
from backend.entity.job_entity import JobEntity
from backend.dto.job_dto import JobCreateDto
from backend.common.recruiting_enums import JobKind, JobStatus
from backend.common.mentorship_enums import ParticipantRole
from backend.recruiting.recruiting_mapper import RecruitingMapper
from backend.recruiting.job_service import JobService


class TestJobService(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.repo = MagicMock()
        self.session = AsyncMock()
        self.service = JobService(self.repo, RecruitingMapper())

    async def test_create_job_persists_and_commits(self):
        async def fake_create(session, entity):
            entity.job_id = 1
            return entity

        self.repo.create_job = AsyncMock(side_effect=fake_create)

        dto = JobCreateDto(
            title="Mentor",
            description="jd",
            kind=JobKind.ACTIVITY,
            mentorship_role=ParticipantRole.MENTOR,
            form_schema={"type": "object"},
        )
        result = await self.service.create_job(self.session, dto)

        self.assertEqual(result.id, 1)
        self.assertEqual(result.status, JobStatus.DRAFT)
        self.session.commit.assert_awaited_once()

    async def test_publish_sets_status_published(self):
        job = JobEntity(
            job_id=2, kind=JobKind.ACTIVITY, status=JobStatus.DRAFT, title="x"
        )
        self.repo.get_by_job_id = AsyncMock(return_value=job)
        self.repo.update_job = AsyncMock(side_effect=lambda s, e: e)

        result = await self.service.publish_job(self.session, 2)
        self.assertEqual(result.status, JobStatus.PUBLISHED)

    async def test_publish_missing_raises(self):
        self.repo.get_by_job_id = AsyncMock(return_value=None)
        with self.assertRaises(ValueError):
            await self.service.publish_job(self.session, 999)


if __name__ == "__main__":
    unittest.main()
