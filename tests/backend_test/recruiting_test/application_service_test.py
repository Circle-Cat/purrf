import unittest
from unittest.mock import AsyncMock, MagicMock
from backend.recruiting.application_service import ApplicationService
from backend.recruiting.recruiting_mapper import RecruitingMapper
from backend.dto.application_dto import ApplicationSubmitDto, ApplicationEditDto
from backend.dto.user_context_dto import UserContextDto
from backend.entity.application_entity import ApplicationEntity
from backend.entity.application_submission_entity import ApplicationSubmissionEntity
from backend.entity.job_entity import JobEntity
from backend.entity.users_entity import UsersEntity
from backend.common.recruiting_enums import ApplicationStage, JobKind, JobStatus


class TestApplicationService(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.app_repo = MagicMock()
        self.app_repo.get_by_job_and_user = AsyncMock(return_value=None)
        self.app_repo.get_by_id = AsyncMock(return_value=None)
        self.app_repo.create = AsyncMock(
            side_effect=lambda s, e: setattr(e, "application_id", 100) or e
        )
        self.app_repo.update = AsyncMock(side_effect=lambda s, e: e)
        self.sub_repo = MagicMock()
        self.sub_repo.get_current = AsyncMock(return_value=None)
        self.sub_repo.create = AsyncMock(
            side_effect=lambda s, e: setattr(e, "submission_id", 1) or e
        )
        self.sub_repo.update = AsyncMock(side_effect=lambda s, e: e)
        self.job_repo = MagicMock()
        self.job_repo.get_by_job_id = AsyncMock(
            return_value=self._job(status=JobStatus.PUBLISHED)
        )
        self.users_repo = MagicMock()
        self.users_repo.get_user_by_user_id = AsyncMock(
            return_value=self._user(is_blocked=False)
        )
        self.session = AsyncMock()
        self.service = ApplicationService(
            self.app_repo,
            self.sub_repo,
            self.job_repo,
            self.users_repo,
            RecruitingMapper(),
        )

    def _job(self, **kw):
        job = JobEntity(
            kind=JobKind.ACTIVITY,
            title="T",
            status=kw.get("status", JobStatus.PUBLISHED),
        )
        job.job_id = 1
        job.cooldown_days = kw.get("cooldown_days")
        return job

    def _user(self, is_blocked=False):
        u = UsersEntity(first_name="A", last_name="B", primary_email="a@b.com")
        u.user_id = 2
        u.is_blocked = is_blocked
        return u

    def _ctx(self):
        return UserContextDto(sub="s", primary_email="a@b.com", user_id=2)

    async def test_submit_lands_applied_with_version_one(self):
        dto = ApplicationSubmitDto.model_validate({
            "jobId": 1,
            "personal": {"firstName": "A"},
        })
        result = await self.service.submit(self.session, self._ctx(), dto)
        self.assertEqual(result.stage, ApplicationStage.APPLIED)
        self.app_repo.create.assert_awaited_once()
        created_sub = self.sub_repo.create.call_args.args[1]
        self.assertEqual(created_sub.version, 1)
        self.assertEqual(created_sub.submission["personal"]["firstName"], "A")

    async def test_blocked_user_lands_rejected(self):
        self.users_repo.get_user_by_user_id = AsyncMock(
            return_value=self._user(is_blocked=True)
        )
        dto = ApplicationSubmitDto.model_validate({"jobId": 1})
        result = await self.service.submit(self.session, self._ctx(), dto)
        self.assertEqual(result.stage, ApplicationStage.REJECTED)

    async def test_edit_overwrites_current_version_when_applied(self):
        app = ApplicationEntity(job_id=1, user_id=2, stage=ApplicationStage.APPLIED)
        app.application_id = 100
        self.app_repo.get_by_id = AsyncMock(return_value=app)
        current = ApplicationSubmissionEntity(
            application_id=100, version=1, submission={"personal": {}}
        )
        current.submission_id = 5
        self.sub_repo.get_current = AsyncMock(return_value=current)
        dto = ApplicationEditDto.model_validate({"answers": {"q1": "z"}})
        await self.service.edit(self.session, self._ctx(), 100, dto)
        self.sub_repo.update.assert_awaited_once()
        self.sub_repo.create.assert_not_awaited()

    async def test_edit_rejected_when_not_applied(self):
        app = ApplicationEntity(
            job_id=1, user_id=2, stage=ApplicationStage.RECRUITER_SCREENING
        )
        app.application_id = 100
        self.app_repo.get_by_id = AsyncMock(return_value=app)
        with self.assertRaises(ValueError):
            await self.service.edit(
                self.session, self._ctx(), 100, ApplicationEditDto()
            )

    async def test_submit_requires_resume_when_config_requires(self):
        job = self._job(status=JobStatus.PUBLISHED)
        job.profile_config = {"resume": "required"}
        self.job_repo.get_by_job_id = AsyncMock(return_value=job)
        with self.assertRaises(ValueError):
            await self.service.submit(
                self.session,
                self._ctx(),
                ApplicationSubmitDto.model_validate({"jobId": 1}),
            )

    async def test_submit_requires_answers_to_required_questions(self):
        job = self._job(status=JobStatus.PUBLISHED)
        job.form_schema = {
            "questions": [
                {"id": "q1", "type": "short_text", "label": "Name", "required": True}
            ]
        }
        self.job_repo.get_by_job_id = AsyncMock(return_value=job)
        with self.assertRaises(ValueError):
            await self.service.submit(
                self.session,
                self._ctx(),
                ApplicationSubmitDto.model_validate({"jobId": 1}),
            )


if __name__ == "__main__":
    unittest.main()
