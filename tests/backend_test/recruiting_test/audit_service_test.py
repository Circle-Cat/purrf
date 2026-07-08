import unittest
from datetime import date
from unittest.mock import AsyncMock, MagicMock

from backend.common.recruiting_enums import ApplicationStage, JobKind, JobStatus
from backend.entity.job_entity import JobEntity
from backend.recruiting.audit_service import AuditService


class TestAuditService(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.job_repo = MagicMock()
        self.app_repo = MagicMock()
        self.session = AsyncMock()
        self.service = AuditService(self.job_repo, self.app_repo)

    def _job(self, job_id, title, status):
        job = JobEntity(kind=JobKind.ACTIVITY, title=title, status=status)
        job.job_id = job_id
        return job

    async def test_open_positions_count_is_unfiltered_and_live_only(self):
        self.job_repo.list_all = AsyncMock(
            return_value=[
                self._job(1, "Job A", JobStatus.PUBLISHED),
                self._job(2, "Job B", JobStatus.DRAFT),
                self._job(3, "Job C", JobStatus.PUBLISHED),
            ]
        )
        self.app_repo.count_by_job_and_stage = AsyncMock(return_value=[])
        self.app_repo.count_by_job_and_day = AsyncMock(return_value=[])

        result = await self.service.get_overview(
            self.session, date(2026, 6, 1), date(2026, 6, 30), None
        )

        self.assertEqual(result.open_positions_count, 2)

    async def test_jobs_list_includes_every_status_unfiltered(self):
        self.job_repo.list_all = AsyncMock(
            return_value=[
                self._job(1, "Job A", JobStatus.PUBLISHED),
                self._job(2, "Job B", JobStatus.CLOSED),
            ]
        )
        self.app_repo.count_by_job_and_stage = AsyncMock(return_value=[])
        self.app_repo.count_by_job_and_day = AsyncMock(return_value=[])

        result = await self.service.get_overview(
            self.session, date(2026, 6, 1), date(2026, 6, 30), [1]
        )

        self.assertEqual(
            {(j.id, j.title, j.status) for j in result.jobs},
            {(1, "Job A", JobStatus.PUBLISHED), (2, "Job B", JobStatus.CLOSED)},
        )

    async def test_stage_breakdown_resolves_job_titles_and_passes_filters(self):
        self.job_repo.list_all = AsyncMock(
            return_value=[self._job(1, "Job A", JobStatus.PUBLISHED)]
        )
        self.app_repo.count_by_job_and_stage = AsyncMock(
            return_value=[(1, ApplicationStage.RECRUITER_SCREENING, 3)]
        )
        self.app_repo.count_by_job_and_day = AsyncMock(return_value=[])

        result = await self.service.get_overview(
            self.session, date(2026, 6, 1), date(2026, 6, 30), [1]
        )

        self.app_repo.count_by_job_and_stage.assert_awaited_once_with(
            self.session, date(2026, 6, 1), date(2026, 6, 30), [1]
        )
        self.assertEqual(len(result.stage_breakdown), 1)
        row = result.stage_breakdown[0]
        self.assertEqual(row.job_id, 1)
        self.assertEqual(row.job_title, "Job A")
        self.assertEqual(row.stage, ApplicationStage.RECRUITER_SCREENING)
        self.assertEqual(row.count, 3)

    async def test_daily_trend_resolves_job_titles_and_passes_filters(self):
        self.job_repo.list_all = AsyncMock(
            return_value=[self._job(1, "Job A", JobStatus.PUBLISHED)]
        )
        self.app_repo.count_by_job_and_stage = AsyncMock(return_value=[])
        self.app_repo.count_by_job_and_day = AsyncMock(
            return_value=[(1, date(2026, 6, 5), 4)]
        )

        result = await self.service.get_overview(
            self.session, date(2026, 6, 1), date(2026, 6, 30), None
        )

        self.app_repo.count_by_job_and_day.assert_awaited_once_with(
            self.session, date(2026, 6, 1), date(2026, 6, 30), None
        )
        self.assertEqual(len(result.daily_trend), 1)
        row = result.daily_trend[0]
        self.assertEqual(row.job_id, 1)
        self.assertEqual(row.job_title, "Job A")
        self.assertEqual(row.date, date(2026, 6, 5))
        self.assertEqual(row.count, 4)

    async def test_empty_job_ids_list_means_all_jobs(self):
        self.job_repo.list_all = AsyncMock(
            return_value=[self._job(1, "Job A", JobStatus.PUBLISHED)]
        )
        self.app_repo.count_by_job_and_stage = AsyncMock(return_value=[])
        self.app_repo.count_by_job_and_day = AsyncMock(return_value=[])

        await self.service.get_overview(
            self.session, date(2026, 6, 1), date(2026, 6, 30), []
        )

        self.app_repo.count_by_job_and_stage.assert_awaited_once_with(
            self.session, date(2026, 6, 1), date(2026, 6, 30), None
        )
        self.app_repo.count_by_job_and_day.assert_awaited_once_with(
            self.session, date(2026, 6, 1), date(2026, 6, 30), None
        )


if __name__ == "__main__":
    unittest.main()
