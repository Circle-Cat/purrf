import unittest
from datetime import date, datetime, timezone
from unittest.mock import AsyncMock, MagicMock, create_autospec
from backend.recruiting.application_service import ApplicationService
from backend.recruiting.recruiting_mapper import RecruitingMapper
from backend.dto.application_dto import ApplicationSubmitDto, ApplicationEditDto
from backend.dto.user_context_dto import UserContextDto
from backend.entity.application_entity import ApplicationEntity
from backend.entity.application_submission_entity import ApplicationSubmissionEntity
from backend.entity.job_entity import JobEntity
from backend.entity.users_entity import UsersEntity
from backend.common.recruiting_enums import ApplicationStage, JobKind, JobStatus
from backend.repository.application_assignment_repository import (
    ApplicationAssignmentRepository,
)
from backend.repository.application_activity_repository import (
    ApplicationActivityRepository,
)


class TestApplicationService(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.app_repo = MagicMock()
        self.app_repo.get_by_job_and_user = AsyncMock(return_value=None)
        self.app_repo.get_by_id = AsyncMock(return_value=None)
        self.app_repo.create = AsyncMock(side_effect=self._create_side_effect)
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
        # autospec (not a bare MagicMock) so a caller/repo signature drift
        # fails the test instead of silently accepting any arity.
        self.assignment_repo = create_autospec(
            ApplicationAssignmentRepository, instance=True
        )
        self.activity_repo = create_autospec(
            ApplicationActivityRepository, instance=True
        )
        self.session = AsyncMock()
        self.service = ApplicationService(
            self.app_repo,
            self.sub_repo,
            self.job_repo,
            self.users_repo,
            RecruitingMapper(),
            self.assignment_repo,
            self.activity_repo,
        )

    def _create_side_effect(self, session, entity):
        """Stand in for app_repo.create's real flush: sets the id and, like
        an INSERT-time column default would, current_round when unset."""
        entity.application_id = 100
        if entity.current_round is None:
            entity.current_round = 1
        return entity

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
        job.screen_rules = kw.get("screen_rules")
        return job

    def _user(self, is_blocked=False, email="a@b.com"):
        u = UsersEntity(first_name="A", last_name="B", primary_email=email)
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

    async def test_submit_creates_default_assignment_when_stage_has_default(self):
        """A stage's configured defaultAssigneeId is only a board display
        fallback until a real application_assignment row exists (My
        Evaluations and evaluation submit only see real rows) — so landing
        on such a stage must materialize it immediately."""
        job = self._job(
            pipeline_config={
                "stages": [{"stage": "recruiter_screening", "defaultAssigneeId": 5}],
                "ownerIds": [9],
            }
        )
        self.job_repo.get_by_job_id = AsyncMock(return_value=job)
        dto = ApplicationSubmitDto.model_validate({"jobId": 1})
        await self.service.submit(self.session, self._ctx(), dto)
        self.assignment_repo.upsert.assert_awaited_once_with(
            self.session, 100, ApplicationStage.RECRUITER_SCREENING, 1, 5, 9
        )

    async def test_submit_logs_auto_assigned_activity_when_default_configured(self):
        """The default-assignee materialization is a real, auditable event —
        not a silent side effect of the assignment row being created."""
        job = self._job(
            pipeline_config={
                "stages": [{"stage": "recruiter_screening", "defaultAssigneeId": 5}],
                "ownerIds": [9],
            }
        )
        self.job_repo.get_by_job_id = AsyncMock(return_value=job)
        dto = ApplicationSubmitDto.model_validate({"jobId": 1})
        await self.service.submit(self.session, self._ctx(), dto)
        self.activity_repo.create.assert_any_await(
            self.session,
            100,
            2,
            "auto_assigned",
            details={"stage": "recruiter_screening", "assigneeId": 5},
        )

    async def test_submit_skips_assignment_when_no_default_configured(self):
        dto = ApplicationSubmitDto.model_validate({"jobId": 1})
        await self.service.submit(self.session, self._ctx(), dto)
        self.assignment_repo.upsert.assert_not_awaited()

    async def test_submit_skips_assignment_when_blocked(self):
        self.users_repo.get_user_by_user_id = AsyncMock(
            return_value=self._user(is_blocked=True)
        )
        job = self._job(
            pipeline_config={
                "stages": [{"stage": "recruiter_screening", "defaultAssigneeId": 5}],
                "ownerIds": [9],
            }
        )
        self.job_repo.get_by_job_id = AsyncMock(return_value=job)
        dto = ApplicationSubmitDto.model_validate({"jobId": 1})
        await self.service.submit(self.session, self._ctx(), dto)
        self.assignment_repo.upsert.assert_not_awaited()

    async def test_submit_skips_assignment_when_no_owner_configured(self):
        """No owner to attribute assigned_by to (the earlier ownerIds=[]
        board-visibility gap) — skip rather than violate the assigned_by FK."""
        job = self._job(
            pipeline_config={
                "stages": [{"stage": "recruiter_screening", "defaultAssigneeId": 5}],
                "ownerIds": [],
            }
        )
        self.job_repo.get_by_job_id = AsyncMock(return_value=job)
        dto = ApplicationSubmitDto.model_validate({"jobId": 1})
        await self.service.submit(self.session, self._ctx(), dto)
        self.assignment_repo.upsert.assert_not_awaited()

    async def test_submit_logs_application_submitted_activity(self):
        dto = ApplicationSubmitDto.model_validate({"jobId": 1})
        await self.service.submit(self.session, self._ctx(), dto)
        self.activity_repo.create.assert_awaited_once_with(
            self.session,
            100,
            2,
            "application_submitted",
            details={"stage": "recruiter_screening"},
        )

    async def test_submit_reapply_logs_application_submitted_activity(self):
        app = ApplicationEntity(
            job_id=1,
            user_id=2,
            stage=ApplicationStage.REJECTED,
            sub_status=None,
            current_round=1,
        )
        app.application_id = 100
        app.created_datetime = datetime.now(timezone.utc)
        app.updated_timestamp = datetime.now(timezone.utc)
        self.app_repo.get_by_job_and_user = AsyncMock(return_value=app)
        current = ApplicationSubmissionEntity(
            application_id=100, version=1, submission={"personal": {}}
        )
        current.submission_id = 5
        current.is_frozen = False
        self.sub_repo.get_current = AsyncMock(return_value=current)
        dto = ApplicationSubmitDto.model_validate({"jobId": 1})

        await self.service.submit(self.session, self._ctx(), dto)

        self.activity_repo.create.assert_awaited_once_with(
            self.session,
            100,
            2,
            "application_submitted",
            details={"stage": "recruiter_screening"},
        )

    async def test_blocked_user_lands_rejected(self):
        self.users_repo.get_user_by_user_id = AsyncMock(
            return_value=self._user(is_blocked=True)
        )
        dto = ApplicationSubmitDto.model_validate({"jobId": 1})
        result = await self.service.submit(self.session, self._ctx(), dto)
        self.assertEqual(result.stage, ApplicationStage.REJECTED)
        self.assertFalse(result.editable)

    async def test_blocked_user_submit_logs_auto_rejected_activity(self):
        self.users_repo.get_user_by_user_id = AsyncMock(
            return_value=self._user(is_blocked=True)
        )
        dto = ApplicationSubmitDto.model_validate({"jobId": 1})

        await self.service.submit(self.session, self._ctx(), dto)

        self.activity_repo.create.assert_awaited_once_with(
            self.session,
            100,
            2,
            "auto_rejected",
            details={"reason": "blocked"},
        )

    async def test_blocked_user_reapply_with_existing_application(self):
        """Blocked user attempting to reapply: existing application is updated to REJECTED with sub_status cleared."""
        self.users_repo.get_user_by_user_id = AsyncMock(
            return_value=self._user(is_blocked=True)
        )
        # Simulate an existing application in screening stage.
        app = ApplicationEntity(
            job_id=1,
            user_id=2,
            stage=ApplicationStage.RECRUITER_SCREENING,
            sub_status="pending",
            current_round=1,
        )
        app.application_id = 100
        self.app_repo.get_by_job_and_user = AsyncMock(return_value=app)
        dto = ApplicationSubmitDto.model_validate({"jobId": 1})
        result = await self.service.submit(self.session, self._ctx(), dto)
        self.assertEqual(result.stage, ApplicationStage.REJECTED)
        self.assertIsNone(result.sub_status)
        self.assertEqual(result.tags, {"auto_reject": "blocked"})
        self.assertFalse(result.editable)

    async def test_edit_overwrites_current_version_when_editable(self):
        app = ApplicationEntity(
            job_id=1,
            user_id=2,
            stage=ApplicationStage.RECRUITER_SCREENING,
            sub_status="pending",
            current_round=1,
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

    async def test_edit_row_locks_the_application(self):
        """A TOCTOU fix (Task 8 review rider): the edit path must lock the
        application row so a concurrent owner decision (freeze/advance)
        can't interleave with — and be silently clobbered by — a candidate
        edit based on stale state."""
        app = ApplicationEntity(
            job_id=1,
            user_id=2,
            stage=ApplicationStage.RECRUITER_SCREENING,
            sub_status="pending",
            current_round=1,
        )
        app.application_id = 100
        self.app_repo.get_by_id = AsyncMock(return_value=app)
        await self.service.edit(self.session, self._ctx(), 100, ApplicationEditDto())
        self.app_repo.get_by_id.assert_awaited_once_with(
            self.session, 100, for_update=True
        )

    async def test_get_mine_does_not_row_lock(self):
        """get_mine is a read; it must stay lock-free (no for_update)."""
        app = ApplicationEntity(
            job_id=1,
            user_id=2,
            stage=ApplicationStage.RECRUITER_SCREENING,
            sub_status="pending",
            current_round=1,
        )
        app.application_id = 100
        self.app_repo.get_by_job_and_user = AsyncMock(return_value=app)
        await self.service.get_mine(self.session, self._ctx(), 1)
        self.app_repo.get_by_job_and_user.assert_awaited_once_with(self.session, 1, 2)

    async def test_edit_blocked_when_stage_advanced(self):
        app = ApplicationEntity(
            job_id=1,
            user_id=2,
            stage=ApplicationStage.BEHAVIORAL,
            sub_status="pending",
            current_round=1,
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
            current_round=1,
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
            current_round=1,
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
            current_round=1,
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
            current_round=1,
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
        job = self._job(cooldown_days=90, status=JobStatus.PUBLISHED)
        self.job_repo.get_by_job_id = AsyncMock(return_value=job)
        app = ApplicationEntity(
            job_id=1, user_id=2, stage=ApplicationStage.REJECTED, current_round=1
        )
        app.application_id = 100
        app.created_datetime = datetime(2026, 1, 10, tzinfo=timezone.utc)
        self.app_repo.get_by_job_and_user = AsyncMock(return_value=app)
        prior = ApplicationSubmissionEntity(
            application_id=100, version=1, submission={"v": 1}
        )
        prior.submitted_at = datetime(2026, 1, 20, tzinfo=timezone.utc)
        self.sub_repo.get_current = AsyncMock(return_value=prior)
        self.service._today = lambda: date(2026, 2, 1)  # inside the 90-day window
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
        self.assertEqual(result.tags["cold_freeze"]["thaw_date"], "2026-04-10")

    async def test_reapply_creates_default_assignment_when_stage_has_default(self):
        """Reapplying also re-lands on the first stage, so a configured
        default assignee must be materialized again, same as a fresh
        application."""
        job = self._job(
            pipeline_config={
                "stages": [{"stage": "recruiter_screening", "defaultAssigneeId": 5}],
                "ownerIds": [9],
            }
        )
        self.job_repo.get_by_job_id = AsyncMock(return_value=job)
        app = ApplicationEntity(
            job_id=1, user_id=2, stage=ApplicationStage.REJECTED, current_round=1
        )
        app.application_id = 100
        app.created_datetime = datetime(2026, 1, 10, tzinfo=timezone.utc)
        self.app_repo.get_by_job_and_user = AsyncMock(return_value=app)
        prior = ApplicationSubmissionEntity(
            application_id=100, version=1, submission={"v": 1}
        )
        prior.submitted_at = datetime(2026, 1, 20, tzinfo=timezone.utc)
        self.sub_repo.get_current = AsyncMock(return_value=prior)
        self.service._today = lambda: date(2026, 5, 1)  # outside cooldown
        dto = ApplicationSubmitDto.model_validate({"jobId": 1})
        await self.service.submit(self.session, self._ctx(), dto)
        self.assignment_repo.upsert.assert_awaited_once_with(
            self.session, 100, ApplicationStage.RECRUITER_SCREENING, 1, 5, 9
        )

    async def test_reapply_non_activity_uses_updated_timestamp_for_rejected_at(self):
        """The thaw must anchor to the application container's last-update
        time (the actual rejection moment), not the frozen submission's
        submitted_at, which can predate it."""
        job = self._job(kind=JobKind.EMPLOYMENT, status=JobStatus.PUBLISHED)
        job.cooldown_days = 90
        self.job_repo.get_by_job_id = AsyncMock(return_value=job)

        app = ApplicationEntity(
            job_id=1, user_id=2, stage=ApplicationStage.REJECTED, current_round=1
        )
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

    async def test_submit_screen_rule_reject_lands_rejected_with_rule_tag(self):
        job = self._job(
            screen_rules={
                "rules": [
                    {
                        "id": "r1",
                        "condition": {
                            "source": "email_domain",
                            "operator": "equals",
                            "value": "spam.com",
                        },
                        "action": "reject",
                    }
                ]
            }
        )
        self.job_repo.get_by_job_id = AsyncMock(return_value=job)
        self.users_repo.get_user_by_user_id = AsyncMock(
            return_value=self._user(email="a@spam.com")
        )
        dto = ApplicationSubmitDto.model_validate({"jobId": 1})

        result = await self.service.submit(self.session, self._ctx(), dto)

        self.assertEqual(result.stage, ApplicationStage.REJECTED)
        self.assertEqual(
            result.tags, {"auto_reject": "screen_rule", "rule_id": "r1"}
        )
        self.activity_repo.create.assert_awaited_once_with(
            self.session,
            100,
            2,
            "auto_rejected",
            details={"reason": "screen_rule", "ruleId": "r1"},
        )

    async def test_submit_screen_rule_qualify_lands_first_stage_with_activity_detail(
        self,
    ):
        job = self._job(
            screen_rules={
                "rules": [
                    {
                        "id": "r1",
                        "condition": {
                            "source": "email_domain",
                            "operator": "equals",
                            "value": "google.com",
                        },
                        "action": "qualify",
                    }
                ]
            }
        )
        self.job_repo.get_by_job_id = AsyncMock(return_value=job)
        self.users_repo.get_user_by_user_id = AsyncMock(
            return_value=self._user(email="a@google.com")
        )
        dto = ApplicationSubmitDto.model_validate({"jobId": 1})

        result = await self.service.submit(self.session, self._ctx(), dto)

        self.assertEqual(result.stage, ApplicationStage.RECRUITER_SCREENING)
        self.assertEqual(result.sub_status, "pending")
        self.assertIsNone(result.tags)
        self.activity_repo.create.assert_awaited_once_with(
            self.session,
            100,
            2,
            "application_submitted",
            details={
                "stage": "recruiter_screening",
                "screenQualifyRuleId": "r1",
            },
        )

    async def test_submit_screen_rule_auto_hire_lands_hired_with_no_sub_status(self):
        job = self._job(
            screen_rules={
                "rules": [
                    {
                        "id": "r1",
                        "condition": {
                            "source": "email_domain",
                            "operator": "equals",
                            "value": "circlecat.org",
                        },
                        "action": "auto_hire",
                    }
                ]
            }
        )
        self.job_repo.get_by_job_id = AsyncMock(return_value=job)
        self.users_repo.get_user_by_user_id = AsyncMock(
            return_value=self._user(email="a@circlecat.org")
        )
        dto = ApplicationSubmitDto.model_validate({"jobId": 1})

        result = await self.service.submit(self.session, self._ctx(), dto)

        self.assertEqual(result.stage, ApplicationStage.HIRED)
        self.assertIsNone(result.sub_status)
        self.assertIsNone(result.tags)
        self.activity_repo.create.assert_awaited_once_with(
            self.session,
            100,
            2,
            "application_submitted",
            details={"stage": "hired", "screenAutoHireRuleId": "r1"},
        )

    async def test_submit_auto_hire_skips_default_assignment(self):
        """HIRED is never an interview stage, so no assignment row should
        be materialized even if the job configures a default assignee
        elsewhere in its pipeline."""
        job = self._job(
            pipeline_config={
                "stages": [{"stage": "recruiter_screening", "defaultAssigneeId": 5}],
                "ownerIds": [9],
            },
            screen_rules={
                "rules": [
                    {
                        "id": "r1",
                        "condition": {
                            "source": "email_domain",
                            "operator": "equals",
                            "value": "circlecat.org",
                        },
                        "action": "auto_hire",
                    }
                ]
            },
        )
        self.job_repo.get_by_job_id = AsyncMock(return_value=job)
        self.users_repo.get_user_by_user_id = AsyncMock(
            return_value=self._user(email="a@circlecat.org")
        )
        dto = ApplicationSubmitDto.model_validate({"jobId": 1})

        await self.service.submit(self.session, self._ctx(), dto)

        self.assignment_repo.upsert.assert_not_awaited()

    async def test_submit_blocked_wins_over_screen_rule_auto_hire(self):
        """A real blacklist entry is more severe than any configured rule —
        screen_rules must never even be evaluated for a blocked user."""
        job = self._job(
            screen_rules={
                "rules": [
                    {
                        "id": "r1",
                        "condition": {
                            "source": "email_domain",
                            "operator": "equals",
                            "value": "circlecat.org",
                        },
                        "action": "auto_hire",
                    }
                ]
            }
        )
        self.job_repo.get_by_job_id = AsyncMock(return_value=job)
        self.users_repo.get_user_by_user_id = AsyncMock(
            return_value=self._user(is_blocked=True, email="a@circlecat.org")
        )
        dto = ApplicationSubmitDto.model_validate({"jobId": 1})

        result = await self.service.submit(self.session, self._ctx(), dto)

        self.assertEqual(result.stage, ApplicationStage.REJECTED)
        self.assertEqual(result.tags, {"auto_reject": "blocked"})

    async def test_reapply_screen_rule_reject_lands_rejected(self):
        job = self._job(
            cooldown_days=90,
            screen_rules={
                "rules": [
                    {
                        "id": "r1",
                        "condition": {
                            "source": "email_domain",
                            "operator": "equals",
                            "value": "spam.com",
                        },
                        "action": "reject",
                    }
                ]
            },
        )
        self.job_repo.get_by_job_id = AsyncMock(return_value=job)
        self.users_repo.get_user_by_user_id = AsyncMock(
            return_value=self._user(email="a@spam.com")
        )
        app = ApplicationEntity(
            job_id=1, user_id=2, stage=ApplicationStage.REJECTED, current_round=1
        )
        app.application_id = 100
        app.created_datetime = datetime(2026, 1, 10, tzinfo=timezone.utc)
        self.app_repo.get_by_job_and_user = AsyncMock(return_value=app)
        prior = ApplicationSubmissionEntity(
            application_id=100, version=1, submission={"v": 1}
        )
        prior.submitted_at = datetime(2026, 1, 20, tzinfo=timezone.utc)
        self.sub_repo.get_current = AsyncMock(return_value=prior)
        self.service._today = lambda: date(2026, 2, 1)  # inside the 90-day window
        dto = ApplicationSubmitDto.model_validate({"jobId": 1})

        result = await self.service.submit(self.session, self._ctx(), dto)

        self.assertEqual(result.stage, ApplicationStage.REJECTED)
        # The new reject's tag wins over the prior rejection's cooldown tag.
        self.assertEqual(
            result.tags, {"auto_reject": "screen_rule", "rule_id": "r1"}
        )

    async def test_reapply_screen_rule_auto_hire_lands_hired(self):
        job = self._job(
            cooldown_days=90,
            screen_rules={
                "rules": [
                    {
                        "id": "r1",
                        "condition": {
                            "source": "email_domain",
                            "operator": "equals",
                            "value": "circlecat.org",
                        },
                        "action": "auto_hire",
                    }
                ]
            },
        )
        self.job_repo.get_by_job_id = AsyncMock(return_value=job)
        self.users_repo.get_user_by_user_id = AsyncMock(
            return_value=self._user(email="a@circlecat.org")
        )
        app = ApplicationEntity(
            job_id=1, user_id=2, stage=ApplicationStage.REJECTED, current_round=1
        )
        app.application_id = 100
        app.created_datetime = datetime(2026, 1, 10, tzinfo=timezone.utc)
        self.app_repo.get_by_job_and_user = AsyncMock(return_value=app)
        prior = ApplicationSubmissionEntity(
            application_id=100, version=1, submission={"v": 1}
        )
        prior.submitted_at = datetime(2026, 1, 20, tzinfo=timezone.utc)
        self.sub_repo.get_current = AsyncMock(return_value=prior)
        self.service._today = lambda: date(2026, 2, 1)  # inside the 90-day window
        dto = ApplicationSubmitDto.model_validate({"jobId": 1})

        result = await self.service.submit(self.session, self._ctx(), dto)

        self.assertEqual(result.stage, ApplicationStage.HIRED)
        self.assertIsNone(result.sub_status)
        self.assertIsNone(result.tags)

    async def test_reapply_after_thaw_has_no_cold_freeze_tag(self):
        app = ApplicationEntity(
            job_id=1, user_id=2, stage=ApplicationStage.REJECTED, current_round=1
        )
        app.application_id = 100
        app.created_datetime = datetime(2026, 1, 10, tzinfo=timezone.utc)
        self.app_repo.get_by_job_and_user = AsyncMock(return_value=app)
        prior = ApplicationSubmissionEntity(
            application_id=100, version=1, submission={}
        )
        prior.submitted_at = datetime(2026, 1, 20, tzinfo=timezone.utc)
        self.sub_repo.get_current = AsyncMock(return_value=prior)
        self.service._today = lambda: date(2026, 5, 1)  # past thaw (>= 2026-01-10)
        result = await self.service.submit(
            self.session, self._ctx(), ApplicationSubmitDto.model_validate({"jobId": 1})
        )
        self.assertNotIn("cold_freeze", result.tags or {})


if __name__ == "__main__":
    unittest.main()
