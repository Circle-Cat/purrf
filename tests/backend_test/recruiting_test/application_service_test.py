import unittest
from datetime import date, datetime, timezone
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
            kind=kw.get("kind", JobKind.ACTIVITY),
            title="T",
            status=kw.get("status", JobStatus.PUBLISHED),
        )
        job.job_id = 1
        job.cooldown_days = kw.get("cooldown_days")
        job.pipeline_config = kw.get(
            "pipeline_config", {"stages": [{"stage": "recruiter_screening"}]}
        )
        return job

    def _user(self, is_blocked=False):
        u = UsersEntity(first_name="A", last_name="B", primary_email="a@b.com")
        u.user_id = 2
        u.is_blocked = is_blocked
        return u

    def _ctx(self):
        return UserContextDto(sub="s", primary_email="a@b.com", user_id=2)

    async def test_submit_lands_first_stage_with_version_one(self):
        dto = ApplicationSubmitDto.model_validate({
            "jobId": 1,
            "personal": {"firstName": "A"},
        })
        result = await self.service.submit(self.session, self._ctx(), dto)
        self.assertEqual(result.stage, ApplicationStage.RECRUITER_SCREENING)
        self.assertEqual(result.sub_status, "pending")
        self.assertTrue(result.editable)
        self.app_repo.create.assert_awaited_once()
        created_sub = self.sub_repo.create.call_args.args[1]
        self.assertEqual(created_sub.version, 1)
        self.assertEqual(created_sub.submission["personal"]["firstName"], "A")
        self.session.commit.assert_awaited()

    async def test_blocked_user_lands_rejected(self):
        self.users_repo.get_user_by_user_id = AsyncMock(
            return_value=self._user(is_blocked=True)
        )
        dto = ApplicationSubmitDto.model_validate({"jobId": 1})
        result = await self.service.submit(self.session, self._ctx(), dto)
        self.assertEqual(result.stage, ApplicationStage.REJECTED)
        self.assertFalse(result.editable)

    async def test_edit_overwrites_current_version_when_editable(self):
        app = ApplicationEntity(
            job_id=1,
            user_id=2,
            stage=ApplicationStage.RECRUITER_SCREENING,
            sub_status="pending",
        )
        app.application_id = 100
        self.app_repo.get_by_id = AsyncMock(return_value=app)
        current = ApplicationSubmissionEntity(
            application_id=100, version=1, submission={"personal": {}}
        )
        current.submission_id = 5
        current.is_frozen = False
        self.sub_repo.get_current = AsyncMock(return_value=current)
        dto = ApplicationEditDto.model_validate({"answers": {"q1": "z"}})
        result = await self.service.edit(self.session, self._ctx(), 100, dto)
        self.sub_repo.update.assert_awaited_once()
        self.sub_repo.create.assert_not_awaited()
        self.session.commit.assert_awaited()
        self.assertTrue(result.editable)

    async def test_get_mine_does_not_commit(self):
        result = await self.service.get_mine(self.session, self._ctx(), 1)
        self.assertIsNone(result)
        self.session.commit.assert_not_awaited()

    async def test_edit_blocked_when_stage_advanced(self):
        app = ApplicationEntity(
            job_id=1,
            user_id=2,
            stage=ApplicationStage.BEHAVIORAL,
            sub_status="pending",
        )
        app.application_id = 100
        self.app_repo.get_by_id = AsyncMock(return_value=app)
        with self.assertRaises(ValueError):
            await self.service.edit(
                self.session, self._ctx(), 100, ApplicationEditDto()
            )

    async def test_edit_blocked_when_sub_status_not_pending(self):
        app = ApplicationEntity(
            job_id=1,
            user_id=2,
            stage=ApplicationStage.RECRUITER_SCREENING,
            sub_status="in_progress",
        )
        app.application_id = 100
        self.app_repo.get_by_id = AsyncMock(return_value=app)
        with self.assertRaises(ValueError):
            await self.service.edit(
                self.session, self._ctx(), 100, ApplicationEditDto()
            )

    async def test_edit_blocked_when_current_submission_frozen(self):
        app = ApplicationEntity(
            job_id=1,
            user_id=2,
            stage=ApplicationStage.RECRUITER_SCREENING,
            sub_status="pending",
        )
        app.application_id = 100
        self.app_repo.get_by_id = AsyncMock(return_value=app)
        current = ApplicationSubmissionEntity(
            application_id=100, version=1, submission={"personal": {}}
        )
        current.submission_id = 5
        current.is_frozen = True
        self.sub_repo.get_current = AsyncMock(return_value=current)
        with self.assertRaises(ValueError):
            await self.service.edit(
                self.session, self._ctx(), 100, ApplicationEditDto()
            )

    async def test_get_mine_editable_true_when_first_stage_pending_unfrozen(self):
        app = ApplicationEntity(
            job_id=1,
            user_id=2,
            stage=ApplicationStage.RECRUITER_SCREENING,
            sub_status="pending",
        )
        app.application_id = 100
        self.app_repo.get_by_job_and_user = AsyncMock(return_value=app)
        current = ApplicationSubmissionEntity(
            application_id=100, version=1, submission={"personal": {}}
        )
        current.is_frozen = False
        self.sub_repo.get_current = AsyncMock(return_value=current)
        result = await self.service.get_mine(self.session, self._ctx(), 1)
        self.assertTrue(result.editable)

    async def test_get_mine_editable_false_when_stage_advanced(self):
        app = ApplicationEntity(
            job_id=1,
            user_id=2,
            stage=ApplicationStage.TECH,
            sub_status="pending",
        )
        app.application_id = 100
        self.app_repo.get_by_job_and_user = AsyncMock(return_value=app)
        current = ApplicationSubmissionEntity(
            application_id=100, version=1, submission={"personal": {}}
        )
        current.is_frozen = False
        self.sub_repo.get_current = AsyncMock(return_value=current)
        result = await self.service.get_mine(self.session, self._ctx(), 1)
        self.assertFalse(result.editable)

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

    async def test_reapply_after_reject_mints_new_version_and_freezes_prior(self):
        app = ApplicationEntity(job_id=1, user_id=2, stage=ApplicationStage.REJECTED)
        app.application_id = 100
        app.created_datetime = datetime(2026, 1, 10, tzinfo=timezone.utc)
        self.app_repo.get_by_job_and_user = AsyncMock(return_value=app)
        prior = ApplicationSubmissionEntity(
            application_id=100, version=1, submission={"v": 1}
        )
        prior.submitted_at = datetime(2026, 1, 20, tzinfo=timezone.utc)
        self.sub_repo.get_current = AsyncMock(return_value=prior)
        self.service._today = lambda: date(2026, 2, 1)  # inside cooldown (< 2026-04-01)
        dto = ApplicationSubmitDto.model_validate({
            "jobId": 1,
            "personal": {"firstName": "New"},
        })
        result = await self.service.submit(self.session, self._ctx(), dto)
        self.assertEqual(result.stage, ApplicationStage.RECRUITER_SCREENING)
        self.assertEqual(result.sub_status, "pending")
        self.assertTrue(result.editable)
        self.assertTrue(prior.is_frozen)  # prior version preserved as frozen
        created_sub = self.sub_repo.create.call_args.args[1]
        self.assertEqual(created_sub.version, 2)
        self.assertIn("cold_freeze", result.tags or {})
        self.assertEqual(result.tags["cold_freeze"]["thaw_date"], "2026-04-01")

    async def test_reapply_non_activity_uses_updated_timestamp_for_rejected_at(self):
        """For a fixed-cooldown (non-ACTIVITY) job, the thaw must anchor to the
        application container's last-update time (the actual rejection
        moment), not the frozen submission's submitted_at."""
        job = self._job(kind=JobKind.EMPLOYMENT, status=JobStatus.PUBLISHED)
        job.cooldown_days = 90
        self.job_repo.get_by_job_id = AsyncMock(return_value=job)

        app = ApplicationEntity(job_id=1, user_id=2, stage=ApplicationStage.REJECTED)
        app.application_id = 100
        app.created_datetime = datetime(2026, 1, 10, tzinfo=timezone.utc)
        # Rejection actually happened later than the prior submission.
        app.updated_timestamp = datetime(2026, 3, 1, tzinfo=timezone.utc)
        self.app_repo.get_by_job_and_user = AsyncMock(return_value=app)

        prior = ApplicationSubmissionEntity(
            application_id=100, version=1, submission={"v": 1}
        )
        prior.submitted_at = datetime(2026, 1, 20, tzinfo=timezone.utc)
        self.sub_repo.get_current = AsyncMock(return_value=prior)

        self.service._today = lambda: date(2026, 4, 1)  # inside 90-day window
        dto = ApplicationSubmitDto.model_validate({
            "jobId": 1,
            "personal": {"firstName": "New"},
        })
        result = await self.service.submit(self.session, self._ctx(), dto)

        self.assertEqual(result.stage, ApplicationStage.RECRUITER_SCREENING)
        self.assertEqual(result.sub_status, "pending")
        created_sub = self.sub_repo.create.call_args.args[1]
        self.assertEqual(created_sub.version, 2)
        self.assertEqual(result.tags["cold_freeze"]["thaw_date"], "2026-05-30")

    async def test_reapply_after_thaw_has_no_cold_freeze_tag(self):
        app = ApplicationEntity(job_id=1, user_id=2, stage=ApplicationStage.REJECTED)
        app.application_id = 100
        app.created_datetime = datetime(2026, 1, 10, tzinfo=timezone.utc)
        self.app_repo.get_by_job_and_user = AsyncMock(return_value=app)
        prior = ApplicationSubmissionEntity(
            application_id=100, version=1, submission={}
        )
        prior.submitted_at = datetime(2026, 1, 20, tzinfo=timezone.utc)
        self.sub_repo.get_current = AsyncMock(return_value=prior)
        self.service._today = lambda: date(2026, 5, 1)  # past thaw (>= 2026-04-01)
        result = await self.service.submit(
            self.session, self._ctx(), ApplicationSubmitDto.model_validate({"jobId": 1})
        )
        self.assertNotIn("cold_freeze", result.tags or {})


if __name__ == "__main__":
    unittest.main()
