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
from backend.common.recruiting_enums import (
    ApplicationStage,
    JobKind,
    JobStatus,
    NotificationType,
)
from backend.repository.application_assignment_repository import (
    ApplicationAssignmentRepository,
)
from backend.repository.application_activity_repository import (
    ApplicationActivityRepository,
)
from backend.repository.notification_repository import NotificationRepository


class TestApplicationService(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.app_repo = MagicMock()
        self.app_repo.get_latest_by_job_and_user = AsyncMock(return_value=None)
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
        self.notification_repo = create_autospec(NotificationRepository, instance=True)
        self.session = AsyncMock()
        self.service = ApplicationService(
            self.app_repo,
            self.sub_repo,
            self.job_repo,
            self.users_repo,
            RecruitingMapper(),
            self.assignment_repo,
            self.activity_repo,
            self.notification_repo,
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

    def _ctx(self, user_id=2):
        return UserContextDto(sub="s", primary_email="a@b.com", user_id=user_id)

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
        self.app_repo.get_latest_by_job_and_user = AsyncMock(return_value=app)
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

    async def test_blocked_user_resubmit_on_active_application_still_errors(self):
        """A blocked user whose latest attempt is still active (not
        REJECTED) hits the same "edit it instead" guard as anyone else —
        the blacklist check never even runs. Post-PR4 this combination
        shouldn't occur in practice (blacklisting now closes in-flight
        applications), but the guard order must hold regardless."""
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
        self.app_repo.get_latest_by_job_and_user = AsyncMock(return_value=app)
        dto = ApplicationSubmitDto.model_validate({"jobId": 1})
        with self.assertRaises(ValueError):
            await self.service.submit(self.session, self._ctx(), dto)
        self.app_repo.create.assert_not_awaited()
        self.app_repo.update.assert_not_awaited()

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
        self.app_repo.get_latest_by_job_and_user = AsyncMock(return_value=app)
        await self.service.get_mine(self.session, self._ctx(), 1)
        self.app_repo.get_latest_by_job_and_user.assert_awaited_once_with(self.session, 1, 2)

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
        self.app_repo.get_latest_by_job_and_user = AsyncMock(return_value=app)
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
        self.app_repo.get_latest_by_job_and_user = AsyncMock(return_value=app)
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

    async def test_submit_drops_resume_when_posting_collects_none(self):
        job = self._job(status=JobStatus.PUBLISHED)
        job.profile_config = {"resume": "off"}
        self.job_repo.get_by_job_id = AsyncMock(return_value=job)
        dto = ApplicationSubmitDto.model_validate({
            "jobId": 1,
            "resumeObjectKey": "resumes/abc.pdf",
            "resumeSha256": "abc",
        })
        await self.service.submit(self.session, self._ctx(), dto)
        created_sub = self.sub_repo.create.call_args.args[1]
        self.assertIsNone(created_sub.resume_object_key)
        self.assertIsNone(created_sub.resume_sha256)

    async def test_edit_drops_resume_when_posting_collects_none(self):
        job = self._job(status=JobStatus.PUBLISHED)
        job.profile_config = {"resume": "off"}
        self.job_repo.get_by_job_id = AsyncMock(return_value=job)
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
        dto = ApplicationEditDto.model_validate({
            "resumeObjectKey": "resumes/abc.pdf",
            "resumeSha256": "abc",
        })
        await self.service.edit(self.session, self._ctx(), 100, dto)
        written_sub = self.sub_repo.update.call_args.args[1]
        self.assertIsNone(written_sub.resume_object_key)
        self.assertIsNone(written_sub.resume_sha256)

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

    async def test_reapply_creates_new_application_row(self):
        """A rejected latest attempt is no longer reused: re-applying
        creates a brand-new ApplicationEntity, distinct from the rejected
        row, rather than updating it in place."""
        job = self._job(cooldown_days=90, status=JobStatus.PUBLISHED)
        self.job_repo.get_by_job_id = AsyncMock(return_value=job)
        rejected_application = ApplicationEntity(
            job_id=1, user_id=2, stage=ApplicationStage.REJECTED, current_round=1
        )
        rejected_application.application_id = 55
        rejected_application.created_datetime = datetime(2026, 1, 10, tzinfo=timezone.utc)
        self.app_repo.get_latest_by_job_and_user = AsyncMock(
            return_value=rejected_application
        )
        self.service._today = lambda: date(2026, 2, 1)  # inside the 90-day window
        dto = ApplicationSubmitDto.model_validate({
            "jobId": 1,
            "personal": {"firstName": "New"},
        })

        result = await self.service.submit(self.session, self._ctx(), dto)

        self.assertNotEqual(result.id, rejected_application.application_id)
        self.app_repo.create.assert_awaited_once()
        self.app_repo.update.assert_not_awaited()
        self.assertEqual(result.stage, ApplicationStage.RECRUITER_SCREENING)
        self.assertEqual(result.sub_status, "pending")
        self.assertTrue(result.editable)

    async def test_reapply_new_row_starts_at_version_1(self):
        """The new row's submission is a fresh version 1, not a bumped
        version of the prior (now-history) row."""
        job = self._job(cooldown_days=90, status=JobStatus.PUBLISHED)
        self.job_repo.get_by_job_id = AsyncMock(return_value=job)
        rejected_application = ApplicationEntity(
            job_id=1, user_id=2, stage=ApplicationStage.REJECTED, current_round=1
        )
        rejected_application.application_id = 55
        rejected_application.created_datetime = datetime(2026, 1, 10, tzinfo=timezone.utc)
        self.app_repo.get_latest_by_job_and_user = AsyncMock(
            return_value=rejected_application
        )
        self.service._today = lambda: date(2026, 2, 1)  # inside the 90-day window
        dto = ApplicationSubmitDto.model_validate({
            "jobId": 1,
            "personal": {"firstName": "New"},
        })

        result = await self.service.submit(self.session, self._ctx(), dto)

        self.sub_repo.create.assert_awaited_once()
        created_sub = self.sub_repo.create.call_args.args[1]
        self.assertEqual(created_sub.version, 1)
        self.assertEqual(created_sub.application_id, result.id)
        self.sub_repo.update.assert_not_awaited()

    async def test_reapply_inside_cooldown_tags_new_row_cold_freeze(self):
        job = self._job(cooldown_days=90, status=JobStatus.PUBLISHED)
        self.job_repo.get_by_job_id = AsyncMock(return_value=job)
        rejected_application = ApplicationEntity(
            job_id=1, user_id=2, stage=ApplicationStage.REJECTED, current_round=1
        )
        rejected_application.application_id = 55
        rejected_application.created_datetime = datetime(2026, 1, 10, tzinfo=timezone.utc)
        self.app_repo.get_latest_by_job_and_user = AsyncMock(
            return_value=rejected_application
        )
        self.service._today = lambda: date(2026, 2, 1)  # inside the 90-day window
        dto = ApplicationSubmitDto.model_validate({
            "jobId": 1,
            "personal": {"firstName": "New"},
        })

        result = await self.service.submit(self.session, self._ctx(), dto)

        self.assertIn("cold_freeze", result.tags or {})
        self.assertEqual(result.tags["cold_freeze"]["thaw_date"], "2026-04-10")

    async def test_reapply_keeps_prior_row_untouched(self):
        """The prior rejected row stays exactly as it was rejected: its
        stage/tags are unchanged and its submissions are never frozen or
        rewritten — it's now immutable history, not a live row."""
        job = self._job(cooldown_days=90, status=JobStatus.PUBLISHED)
        self.job_repo.get_by_job_id = AsyncMock(return_value=job)
        rejected_application = ApplicationEntity(
            job_id=1, user_id=2, stage=ApplicationStage.REJECTED, current_round=1
        )
        rejected_application.application_id = 55
        rejected_application.created_datetime = datetime(2026, 1, 10, tzinfo=timezone.utc)
        rejected_application.tags = {"auto_reject": "screen_rule", "rule_id": "r1"}
        self.app_repo.get_latest_by_job_and_user = AsyncMock(
            return_value=rejected_application
        )
        self.service._today = lambda: date(2026, 2, 1)
        dto = ApplicationSubmitDto.model_validate({"jobId": 1})

        await self.service.submit(self.session, self._ctx(), dto)

        self.assertEqual(rejected_application.stage, ApplicationStage.REJECTED)
        self.assertEqual(
            rejected_application.tags, {"auto_reject": "screen_rule", "rule_id": "r1"}
        )
        self.app_repo.update.assert_not_awaited()
        self.sub_repo.update.assert_not_awaited()

    async def test_submit_active_application_still_errors(self):
        """A latest attempt that hasn't been rejected must still block a
        fresh submit — the candidate should edit it instead."""
        app = ApplicationEntity(
            job_id=1,
            user_id=2,
            stage=ApplicationStage.APPLIED,
            current_round=1,
        )
        app.application_id = 100
        self.app_repo.get_latest_by_job_and_user = AsyncMock(return_value=app)
        dto = ApplicationSubmitDto.model_validate({"jobId": 1})

        with self.assertRaises(ValueError):
            await self.service.submit(self.session, self._ctx(), dto)
        self.app_repo.create.assert_not_awaited()
        self.app_repo.update.assert_not_awaited()

    async def test_blocked_reapply_creates_new_auto_rejected_row(self):
        """A blocked user re-applying after a prior rejection gets a new
        row too, immediately auto-rejected, not an overwrite of the old
        one."""
        self.users_repo.get_user_by_user_id = AsyncMock(
            return_value=self._user(is_blocked=True)
        )
        rejected_application = ApplicationEntity(
            job_id=1, user_id=2, stage=ApplicationStage.REJECTED, current_round=1
        )
        rejected_application.application_id = 55
        rejected_application.created_datetime = datetime(2026, 1, 10, tzinfo=timezone.utc)
        self.app_repo.get_latest_by_job_and_user = AsyncMock(
            return_value=rejected_application
        )
        dto = ApplicationSubmitDto.model_validate({"jobId": 1})

        result = await self.service.submit(self.session, self._ctx(), dto)

        self.assertNotEqual(result.id, rejected_application.application_id)
        self.assertEqual(result.stage, ApplicationStage.REJECTED)
        self.assertEqual(result.tags, {"auto_reject": "blocked"})
        self.app_repo.update.assert_not_awaited()
        self.activity_repo.create.assert_awaited_once_with(
            self.session,
            result.id,
            2,
            "auto_rejected",
            details={"reason": "blocked"},
        )

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
        rejected_application = ApplicationEntity(
            job_id=1, user_id=2, stage=ApplicationStage.REJECTED, current_round=1
        )
        rejected_application.application_id = 55
        rejected_application.created_datetime = datetime(2026, 1, 10, tzinfo=timezone.utc)
        self.app_repo.get_latest_by_job_and_user = AsyncMock(
            return_value=rejected_application
        )
        self.service._today = lambda: date(2026, 5, 1)  # outside cooldown
        dto = ApplicationSubmitDto.model_validate({"jobId": 1})
        result = await self.service.submit(self.session, self._ctx(), dto)
        self.assignment_repo.upsert.assert_awaited_once_with(
            self.session, result.id, ApplicationStage.RECRUITER_SCREENING, 1, 5, 9
        )

    async def test_reapply_non_activity_uses_updated_timestamp_for_rejected_at(self):
        """The thaw must anchor to the application container's last-update
        time (the actual rejection moment), not the frozen submission's
        submitted_at, which can predate it."""
        job = self._job(kind=JobKind.EMPLOYMENT, status=JobStatus.PUBLISHED)
        job.cooldown_days = 90
        self.job_repo.get_by_job_id = AsyncMock(return_value=job)

        rejected_application = ApplicationEntity(
            job_id=1, user_id=2, stage=ApplicationStage.REJECTED, current_round=1
        )
        rejected_application.application_id = 55
        rejected_application.created_datetime = datetime(2026, 1, 10, tzinfo=timezone.utc)
        # Rejection actually happened later than the prior submission.
        rejected_application.updated_timestamp = datetime(2026, 3, 1, tzinfo=timezone.utc)
        self.app_repo.get_latest_by_job_and_user = AsyncMock(
            return_value=rejected_application
        )

        self.service._today = lambda: date(2026, 4, 1)  # inside 90-day window
        dto = ApplicationSubmitDto.model_validate({
            "jobId": 1,
            "personal": {"firstName": "New"},
        })
        result = await self.service.submit(self.session, self._ctx(), dto)

        self.assertEqual(result.stage, ApplicationStage.RECRUITER_SCREENING)
        self.assertEqual(result.sub_status, "pending")
        created_sub = self.sub_repo.create.call_args.args[1]
        self.assertEqual(created_sub.version, 1)
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
        self.assertEqual(result.tags, {"auto_reject": "screen_rule", "rule_id": "r1"})
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

    async def test_submit_email_domain_include_and_exclude_rules_together(self):
        """A posting configured with both an include+auto_hire rule and an
        exclude+reject rule for the same domain set: matching domains get
        auto-hired, everyone else gets auto-rejected — proving a posting can
        express 'approve this domain, reject the rest' with two rules."""
        job = self._job(
            screen_rules={
                "rules": [
                    {
                        "id": "r1",
                        "condition": {
                            "source": "email_domain",
                            "operator": "in",
                            "value": ["circlecat.org"],
                        },
                        "action": "auto_hire",
                    },
                    {
                        "id": "r2",
                        "condition": {
                            "source": "email_domain",
                            "operator": "not_in",
                            "value": ["circlecat.org"],
                        },
                        "action": "reject",
                    },
                ]
            }
        )
        self.job_repo.get_by_job_id = AsyncMock(return_value=job)

        self.users_repo.get_user_by_user_id = AsyncMock(
            return_value=self._user(email="a@circlecat.org")
        )
        dto = ApplicationSubmitDto.model_validate({"jobId": 1})
        hired_result = await self.service.submit(self.session, self._ctx(), dto)
        self.assertEqual(hired_result.stage, ApplicationStage.HIRED)

        self.users_repo.get_user_by_user_id = AsyncMock(
            return_value=self._user(email="a@yahoo.com")
        )
        rejected_result = await self.service.submit(self.session, self._ctx(), dto)
        self.assertEqual(rejected_result.stage, ApplicationStage.REJECTED)

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
        self.app_repo.get_latest_by_job_and_user = AsyncMock(return_value=app)
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
        self.assertEqual(result.tags, {"auto_reject": "screen_rule", "rule_id": "r1"})

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
        self.app_repo.get_latest_by_job_and_user = AsyncMock(return_value=app)
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
        self.app_repo.get_latest_by_job_and_user = AsyncMock(return_value=app)
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

    async def test_list_mine_returns_summaries_across_jobs(self):
        job_a = self._job(kind=JobKind.ACTIVITY)
        job_a.job_id = 1
        job_a.title = "CircleCat Mentor"
        job_a.mentorship_role = None  # overwritten below via kwargs helper gap
        from backend.common.mentorship_enums import ParticipantRole

        job_a.mentorship_role = ParticipantRole.MENTOR
        app_a = ApplicationEntity(job_id=1, user_id=2, stage=ApplicationStage.HIRED)
        app_a.application_id = 10

        job_b = self._job(kind=JobKind.EMPLOYMENT)
        job_b.job_id = 2
        job_b.title = "Backend Engineer"
        app_b = ApplicationEntity(
            job_id=2, user_id=2, stage=ApplicationStage.RECRUITER_SCREENING
        )
        app_b.application_id = 11

        self.app_repo.list_by_user = AsyncMock(
            return_value=[(app_a, job_a), (app_b, job_b)]
        )

        result = await self.service.list_mine(self.session, self._user())

        self.app_repo.list_by_user.assert_awaited_once_with(self.session, 2)
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0].application_id, 10)
        self.assertEqual(result[0].job_title, "CircleCat Mentor")
        self.assertEqual(result[0].mentorship_role, ParticipantRole.MENTOR)
        self.assertEqual(result[1].application_id, 11)
        self.assertEqual(result[1].mentorship_role, None)

    async def test_list_mine_returns_empty_for_no_applications(self):
        self.app_repo.list_by_user = AsyncMock(return_value=[])

        result = await self.service.list_mine(self.session, self._user())

        self.assertEqual(result, [])

    async def test_assign_default_if_configured_notifies_default_assignee(self):
        job = self._job(status=JobStatus.PUBLISHED)
        job.pipeline_config = {
            "ownerIds": [9],
            "stages": [
                {"stage": "recruiter_screening", "defaultAssigneeId": 5},
            ],
        }
        application = ApplicationEntity(
            job_id=job.job_id,
            user_id=3,
            stage=ApplicationStage.RECRUITER_SCREENING,
            current_round=1,
        )
        application.application_id = 10

        await self.service._assign_default_if_configured(
            self.session, application, job, self._ctx(user_id=3)
        )

        self.notification_repo.create.assert_awaited_once()
        (_session_arg, entity_arg), _ = self.notification_repo.create.call_args
        self.assertEqual(entity_arg.user_id, 5)
        self.assertEqual(entity_arg.type, NotificationType.ASSIGNED_TO_EVALUATE)
        self.assertEqual(entity_arg.application_id, 10)
        self.assertIsNone(entity_arg.actor_user_id)


if __name__ == "__main__":
    unittest.main()
