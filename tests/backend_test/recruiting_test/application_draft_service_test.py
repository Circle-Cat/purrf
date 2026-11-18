import unittest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, create_autospec

from backend.common.recruiting_enums import ApplicationStage, JobKind, JobStatus
from backend.dto.application_dto import ApplicationDraftSaveDto
from backend.dto.user_context_dto import UserContextDto
from backend.entity.application_draft_entity import ApplicationDraftEntity
from backend.entity.application_entity import ApplicationEntity
from backend.entity.job_entity import JobEntity
from backend.recruiting.application_draft_service import ApplicationDraftService
from backend.recruiting.recruiting_mapper import RecruitingMapper
from backend.repository.application_draft_repository import (
    ApplicationDraftRepository,
)
from backend.repository.application_repository import ApplicationRepository
from backend.repository.job_repository import JobRepository

USER_ID = 23
JOB_ID = 71
SHA = "0123456789abcdef" * 4
KEY = f"resumes/{SHA}.pdf"
SAVED_AT = datetime(2026, 11, 5, 9, 30, tzinfo=timezone.utc)


class TestApplicationDraftService(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.call_order = []
        self.session = AsyncMock()
        self.session.commit = AsyncMock(
            side_effect=lambda: self.call_order.append("commit")
        )
        self.draft_repo = create_autospec(ApplicationDraftRepository, instance=True)
        self.draft_repo.get = AsyncMock(return_value=None)
        self.draft_repo.upsert = AsyncMock(side_effect=self._upsert)
        self.app_repo = create_autospec(ApplicationRepository, instance=True)
        self.app_repo.get_latest_by_job_and_user = AsyncMock(return_value=None)
        self.job_repo = create_autospec(JobRepository, instance=True)
        self.job_repo.get_by_job_id = AsyncMock(
            return_value=self._job(JobStatus.PUBLISHED)
        )
        self.service = ApplicationDraftService(
            self.draft_repo, self.app_repo, self.job_repo, RecruitingMapper()
        )
        self.ctx = UserContextDto(sub="s", primary_email="c@d.com", user_id=USER_ID)

    def _upsert(self, session, user_id, job_id, content):
        self.call_order.append("upsert")
        draft = ApplicationDraftEntity(user_id=user_id, job_id=job_id, content=content)
        draft.updated_timestamp = SAVED_AT
        return draft

    @staticmethod
    def _job(status):
        job = JobEntity(kind=JobKind.EMPLOYMENT, title="Backend", status=status)
        job.job_id = JOB_ID
        return job

    @staticmethod
    def _application(stage):
        application = ApplicationEntity(job_id=JOB_ID, user_id=USER_ID, stage=stage)
        application.application_id = 905
        return application

    @staticmethod
    def _save_dto(**overrides):
        payload = {
            "jobId": JOB_ID,
            "personal": {"firstName": "Ada"},
            "education": [{"institution": "MIT"}],
            "experience": [{"company": "Circle Cat"}],
            "answers": {"q1": "half done"},
            "resumeSha256": SHA,
            "resumeObjectKey": KEY,
        }
        payload.update(overrides)
        return ApplicationDraftSaveDto.model_validate(payload)

    async def test_save_stores_the_form_in_the_submission_keys_then_commits(self):
        result = await self.service.save(self.session, self.ctx, self._save_dto())

        self.draft_repo.upsert.assert_awaited_once_with(
            self.session,
            USER_ID,
            JOB_ID,
            {
                "personal": {"firstName": "Ada"},
                "education": [{"institution": "MIT"}],
                "experience": [{"company": "Circle Cat"}],
                "answers": {"q1": "half done"},
                "resumeSha256": SHA,
                "resumeObjectKey": KEY,
            },
        )
        self.assertEqual(["upsert", "commit"], self.call_order)
        self.assertEqual(JOB_ID, result.job_id)
        self.assertEqual({"q1": "half done"}, result.answers)
        self.assertEqual(KEY, result.resume_object_key)
        self.assertEqual(SAVED_AT, result.updated_at)

    async def test_save_looks_up_the_callers_latest_application_for_that_job(self):
        await self.service.save(self.session, self.ctx, self._save_dto())

        self.job_repo.get_by_job_id.assert_awaited_once_with(self.session, JOB_ID)
        self.app_repo.get_latest_by_job_and_user.assert_awaited_once_with(
            self.session, JOB_ID, USER_ID
        )

    async def test_save_refuses_a_missing_posting(self):
        self.job_repo.get_by_job_id = AsyncMock(return_value=None)

        with self.assertRaises(ValueError):
            await self.service.save(self.session, self.ctx, self._save_dto())

        self.draft_repo.upsert.assert_not_awaited()
        self.session.commit.assert_not_awaited()

    async def test_save_refuses_a_posting_that_is_not_live(self):
        for status in (JobStatus.CLOSED, JobStatus.DRAFT, JobStatus.PENDING_REVIEW):
            with self.subTest(status=status):
                self.job_repo.get_by_job_id = AsyncMock(return_value=self._job(status))

                with self.assertRaises(ValueError):
                    await self.service.save(self.session, self.ctx, self._save_dto())

                self.draft_repo.upsert.assert_not_awaited()
                self.session.commit.assert_not_awaited()

    async def test_save_accepts_a_posting_with_a_close_under_review(self):
        self.job_repo.get_by_job_id = AsyncMock(
            return_value=self._job(JobStatus.PENDING_CLOSE)
        )

        await self.service.save(self.session, self.ctx, self._save_dto())

        self.draft_repo.upsert.assert_awaited_once()

    async def test_save_refuses_beside_an_active_application(self):
        for stage in (ApplicationStage.APPLIED, ApplicationStage.HIRED):
            with self.subTest(stage=stage):
                self.app_repo.get_latest_by_job_and_user = AsyncMock(
                    return_value=self._application(stage)
                )

                with self.assertRaises(ValueError):
                    await self.service.save(self.session, self.ctx, self._save_dto())

                self.draft_repo.upsert.assert_not_awaited()
                self.session.commit.assert_not_awaited()

    async def test_save_allows_a_reapplication_draft_after_a_rejection(self):
        self.app_repo.get_latest_by_job_and_user = AsyncMock(
            return_value=self._application(ApplicationStage.REJECTED)
        )

        await self.service.save(self.session, self.ctx, self._save_dto())

        self.assertEqual(["upsert", "commit"], self.call_order)

    async def test_save_needs_no_required_fields(self):
        dto = ApplicationDraftSaveDto.model_validate({"jobId": JOB_ID})

        result = await self.service.save(self.session, self.ctx, dto)

        self.assertEqual({}, result.personal)
        self.assertIsNone(result.resume_sha256)

    async def test_get_mine_returns_none_without_a_draft(self):
        result = await self.service.get_mine(self.session, self.ctx, JOB_ID)

        self.assertIsNone(result)
        self.draft_repo.get.assert_awaited_once_with(self.session, USER_ID, JOB_ID)

    async def test_get_mine_returns_the_saved_form(self):
        draft = ApplicationDraftEntity(
            user_id=USER_ID,
            job_id=JOB_ID,
            content={
                "personal": {"lastName": "Lovelace"},
                "education": [],
                "experience": [{"title": "Engineer"}],
                "answers": {"q2": ["a", "b"]},
                "resumeSha256": SHA,
                "resumeObjectKey": KEY,
            },
        )
        draft.updated_timestamp = SAVED_AT
        self.draft_repo.get = AsyncMock(return_value=draft)

        result = await self.service.get_mine(self.session, self.ctx, JOB_ID)

        self.assertEqual(JOB_ID, result.job_id)
        self.assertEqual({"lastName": "Lovelace"}, result.personal)
        self.assertEqual([{"title": "Engineer"}], result.experience)
        self.assertEqual({"q2": ["a", "b"]}, result.answers)
        self.assertEqual(SHA, result.resume_sha256)
        self.assertEqual(KEY, result.resume_object_key)
        self.assertEqual(SAVED_AT, result.updated_at)

    async def test_get_mine_does_not_commit(self):
        await self.service.get_mine(self.session, self.ctx, JOB_ID)

        self.session.commit.assert_not_awaited()


if __name__ == "__main__":
    unittest.main()
