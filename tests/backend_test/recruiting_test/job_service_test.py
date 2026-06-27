import unittest
from unittest.mock import AsyncMock, MagicMock

from backend.recruiting.job_service import JobService
from backend.recruiting.recruiting_mapper import RecruitingMapper
from backend.dto.job_dto import JobCreateDto
from backend.entity.job_entity import JobEntity
from backend.entity.users_entity import UsersEntity
from backend.common.recruiting_enums import JobKind, JobStatus


class TestJobService(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        def _create(session, entity):
            entity.job_id = 1
            return entity

        self.repo = MagicMock()
        self.repo.get_by_job_id = AsyncMock()
        self.repo.create_job = AsyncMock(side_effect=_create)
        self.repo.update_job = AsyncMock(side_effect=lambda session, entity: entity)
        self.perms = MagicMock()
        self.perms.get_active_users_with_permission = AsyncMock(return_value=[])
        self.session = AsyncMock()
        self.service = JobService(self.repo, RecruitingMapper(), self.perms)

    def _job(self, **kw):
        defaults = {"kind": JobKind.ACTIVITY, "title": "T", "status": JobStatus.DRAFT}
        defaults.update(kw)
        job = JobEntity(**defaults)
        job.job_id = 1
        return job

    async def test_create_stores_pipeline_config(self):
        """create_job persists pipeline_config and starts in DRAFT."""
        dto = JobCreateDto(
            title="SWE", kind=JobKind.EMPLOYMENT, pipeline_config=[{"stage": "tech"}]
        )
        result = await self.service.create_job(self.session, dto)

        self.assertEqual(result.pipeline_config, [{"stage": "tech"}])
        self.assertEqual(result.status, JobStatus.DRAFT)

    async def test_update_published_writes_pending_and_flips_status(self):
        """Editing a PUBLISHED posting parks the change as a pending revision."""
        job = self._job(status=JobStatus.PUBLISHED, form_schema={"a": 1})
        self.repo.get_by_job_id.return_value = job
        dto = JobCreateDto(title=job.title, kind=job.kind, form_schema={"a": 2})

        result = await self.service.update_job(self.session, job.job_id, dto)

        self.assertEqual(result.status, JobStatus.PUBLISHED_PENDING_REVISION)
        self.assertEqual(result.pending_form_schema, {"a": 2})
        self.assertEqual(result.form_schema, {"a": 1})

    async def test_update_draft_changes_live_directly(self):
        """Editing a DRAFT posting mutates the live fields with no review gate."""
        job = self._job(status=JobStatus.DRAFT, title="old")
        self.repo.get_by_job_id.return_value = job
        dto = JobCreateDto(title="new", kind=job.kind)

        result = await self.service.update_job(self.session, job.job_id, dto)

        self.assertEqual(result.title, "new")
        self.assertEqual(result.status, JobStatus.DRAFT)

    async def test_reopen_closed_to_published(self):
        """reopen_job moves a CLOSED posting back to PUBLISHED."""
        job = self._job(status=JobStatus.CLOSED)
        self.repo.get_by_job_id.return_value = job

        result = await self.service.reopen_job(self.session, job.job_id)

        self.assertEqual(result.status, JobStatus.PUBLISHED)

    async def test_list_active_approvers_maps_users(self):
        """list_active_approvers maps active job.approve holders to ApproverDto."""
        u1 = UsersEntity(
            first_name="Ann", last_name="Lee", primary_email="ann@x.com"
        )
        u1.user_id = 7
        u2 = UsersEntity(
            first_name="Bo", last_name="Ng", primary_email="bo@x.com"
        )
        u2.user_id = 8
        self.perms.get_active_users_with_permission.return_value = [u1, u2]

        result = await self.service.list_active_approvers(self.session)

        self.assertEqual([a.user_id for a in result], [7, 8])
        self.assertEqual(result[0].name, "Ann Lee")
        self.assertEqual(result[0].email, "ann@x.com")

    async def test_reopen_non_closed_raises(self):
        """reopen_job rejects a posting that is not CLOSED."""
        job = self._job(status=JobStatus.PUBLISHED)
        self.repo.get_by_job_id.return_value = job

        with self.assertRaises(ValueError):
            await self.service.reopen_job(self.session, job.job_id)


if __name__ == "__main__":
    unittest.main()
