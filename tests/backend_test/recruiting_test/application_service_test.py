import unittest
from datetime import date, datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, create_autospec, patch
from backend.common.mentorship_enums import ParticipantRole
from backend.mentorship.onboarding_training_service import OnboardingTrainingService
from backend.recruiting.application_service import ApplicationService
from backend.repository.notification_repository import NotificationRepository
from backend.recruiting.recruiting_mapper import RecruitingMapper
from backend.dto.application_dto import ApplicationSubmitDto, ApplicationEditDto
from backend.dto.job_config_dto import (
    LONG_TEXT_MAX_LENGTH,
    SHORT_TEXT_MAX_LENGTH,
)
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


# The three fields every submission must carry, and one complete row of each
# list, in the shape the candidate form puts on the wire.
REQUIRED_PERSONAL = {
    "firstName": "Cand",
    "lastName": "Idate",
    "timezone": "Asia/Taipei",
}
COMPLETE_EDUCATION = {
    "id": "rpf-1",
    "institution": "Tsinghua University",
    "degree": "BSc",
    "field": "Computer Science",
    "startMonth": "September",
    "startYear": "2018",
    "endMonth": "June",
    "endYear": "2022",
}
COMPLETE_EXPERIENCE = {
    "id": "rpf-2",
    "title": "Backend Engineer",
    "company": "Circle Cat",
    "startMonth": "July",
    "startYear": "2022",
    "endMonth": "March",
    "endYear": "2024",
}


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
        self.session = AsyncMock()
        recorder = patch(
            "backend.recruiting.application_service.record_event",
            new_callable=AsyncMock,
        )
        self.record_event = recorder.start()
        self.addCleanup(recorder.stop)
        self.notification_repo = self._notification_repository_double()
        # The applicant's screen-rule emails come from user_emails; submit
        # matches against every confirmed claim, not one contact address.
        self.user_emails_repo = MagicMock()
        self.user_emails_repo.list_by_user_id = AsyncMock(return_value=[])
        # autospec so a signature drift on ensure_for_admitted fails the test
        # instead of silently accepting any arity.
        self.onboarding_training_svc = create_autospec(
            OnboardingTrainingService, instance=True
        )
        self.service = ApplicationService(
            self.app_repo,
            self.sub_repo,
            self.job_repo,
            self.users_repo,
            RecruitingMapper(),
            self.assignment_repo,
            self.notification_repo,
            self.user_emails_repo,
            self.onboarding_training_svc,
        )

    def _notification_repository_double(self):
        """A notification repository whose writes are observable and ordered.

        `self.call_order` records the write and the commit so a test can
        assert the row lands *inside* the transaction. Asserting only "it was
        awaited" would pass even if the row were written after the commit,
        which would let a rollback drop the notification while the event it
        announces survived.
        """
        self.call_order = []
        repository = create_autospec(NotificationRepository, instance=True)

        async def _create(session, entity):
            self.call_order.append("record")
            return entity

        repository.create = AsyncMock(side_effect=_create)
        self.session.commit = AsyncMock(
            side_effect=lambda: self.call_order.append("commit")
        )
        return repository

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
        u = UsersEntity(first_name="A", last_name="B")
        u.user_id = 2
        u.is_blocked = is_blocked
        return u

    def _ctx(self, user_id=2):
        return UserContextDto(sub="s", primary_email="a@b.com", user_id=user_id)

    @staticmethod
    def _email_row(email, otp_confirmed=True):
        """A user_emails row stub with just the fields submit reads."""
        return SimpleNamespace(email=email, otp_confirmed=otp_confirmed)

    async def test_submit_lands_first_stage_with_version_one(self):
        dto = ApplicationSubmitDto.model_validate({
            "jobId": 1,
            "personal": {**REQUIRED_PERSONAL, "firstName": "A"},
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

    async def test_submit_snapshots_the_job_form_schema(self):
        """A version-1 snapshot carries the questions the candidate saw."""
        schema = {"questions": [{"id": "q1", "type": "short_text", "label": "Why us?"}]}
        job = self._job(status=JobStatus.PUBLISHED)
        job.form_schema = schema
        self.job_repo.get_by_job_id = AsyncMock(return_value=job)
        dto = ApplicationSubmitDto.model_validate({
            "personal": REQUIRED_PERSONAL,
            "jobId": 1,
            "answers": {"q1": "Because"},
        })

        await self.service.submit(self.session, self._ctx(), dto)

        created_sub = self.sub_repo.create.call_args.args[1]
        self.assertEqual(created_sub.submission["formSchema"], schema)

    async def test_submit_snapshots_empty_schema_when_job_has_none(self):
        """A job with no form still produces a well-formed snapshot key."""
        job = self._job(status=JobStatus.PUBLISHED)
        job.form_schema = None
        self.job_repo.get_by_job_id = AsyncMock(return_value=job)
        dto = ApplicationSubmitDto.model_validate({
            "jobId": 1,
            "personal": REQUIRED_PERSONAL,
        })

        await self.service.submit(self.session, self._ctx(), dto)

        created_sub = self.sub_repo.create.call_args.args[1]
        self.assertEqual(created_sub.submission["formSchema"], {"questions": []})

    def _gated_form_job(self):
        """A posting whose q2 is required but only shown when q1 is "Yes"."""
        job = self._job(status=JobStatus.PUBLISHED)
        job.form_schema = {
            "questions": [
                {
                    "id": "q1",
                    "type": "single_choice",
                    "label": "Need sponsorship?",
                    "options": ["Yes", "No"],
                },
                {
                    "id": "q2",
                    "type": "short_text",
                    "label": "Visa type?",
                    "required": True,
                    "showWhen": {"questionId": "q1", "equals": "Yes"},
                },
            ]
        }
        self.job_repo.get_by_job_id = AsyncMock(return_value=job)
        return job

    async def test_submit_does_not_require_a_hidden_question(self):
        """A required question the form never showed cannot block submission."""
        self._gated_form_job()
        dto = ApplicationSubmitDto.model_validate({
            "personal": REQUIRED_PERSONAL,
            "jobId": 1,
            "answers": {"q1": "No"},
        })

        await self.service.submit(self.session, self._ctx(), dto)

        created_sub = self.sub_repo.create.call_args.args[1]
        self.assertEqual(created_sub.submission["answers"], {"q1": "No"})

    async def test_submit_does_not_require_a_transitively_hidden_question(self):
        """The required check has to follow the chain, not just the last rule.

        q3's own rule reads q2's answer and is satisfied by it. Only resolving
        q2 as well shows that the candidate was never asked either question,
        so demanding q3 would block a submission over a field the form did not
        put on screen.
        """
        job = self._job(status=JobStatus.PUBLISHED)
        job.form_schema = {
            "questions": [
                {
                    "id": "q1",
                    "type": "single_choice",
                    "label": "Need sponsorship?",
                    "options": ["Yes", "No"],
                },
                {
                    "id": "q2",
                    "type": "single_choice",
                    "label": "Currently on a visa?",
                    "options": ["Yes", "No"],
                    "showWhen": {"questionId": "q1", "equals": "Yes"},
                },
                {
                    "id": "q3",
                    "type": "short_text",
                    "label": "Which visa?",
                    "required": True,
                    "showWhen": {"questionId": "q2", "equals": "Yes"},
                },
            ]
        }
        self.job_repo.get_by_job_id = AsyncMock(return_value=job)
        dto = ApplicationSubmitDto.model_validate({
            "personal": REQUIRED_PERSONAL,
            "jobId": 1,
            "answers": {"q1": "No", "q2": "Yes"},
        })

        await self.service.submit(self.session, self._ctx(), dto)

        created_sub = self.sub_repo.create.call_args.args[1]
        self.assertEqual(created_sub.submission["answers"], {"q1": "No"})

    async def test_submit_still_requires_a_visible_question(self):
        self._gated_form_job()
        dto = ApplicationSubmitDto.model_validate({
            "personal": REQUIRED_PERSONAL,
            "jobId": 1,
            "answers": {"q1": "Yes"},
        })

        with self.assertRaises(ValueError):
            await self.service.submit(self.session, self._ctx(), dto)
        self.sub_repo.create.assert_not_awaited()

    async def test_submit_drops_an_answer_the_form_did_not_show(self):
        """Only the state the candidate last stood behind is recorded."""
        self._gated_form_job()
        dto = ApplicationSubmitDto.model_validate({
            "personal": REQUIRED_PERSONAL,
            "jobId": 1,
            "answers": {"q1": "No", "q2": "F-1 OPT", "q9": "retired question"},
        })

        await self.service.submit(self.session, self._ctx(), dto)

        created_sub = self.sub_repo.create.call_args.args[1]
        self.assertEqual(created_sub.submission["answers"], {"q1": "No"})

    async def test_submit_keeps_other_free_text_through_the_write(self):
        """The `__other` sibling is not a question, so nothing in the schema
        loop keeps it -- only the explicit Other branch does."""
        job = self._job(status=JobStatus.PUBLISHED)
        job.form_schema = {
            "questions": [
                {
                    "id": "q3",
                    "type": "multi_choice",
                    "label": "Teams?",
                    "options": ["Backend", "Other"],
                    "otherOption": "Other",
                }
            ]
        }
        self.job_repo.get_by_job_id = AsyncMock(return_value=job)
        dto = ApplicationSubmitDto.model_validate({
            "personal": REQUIRED_PERSONAL,
            "jobId": 1,
            "answers": {"q3": ["Backend", "Other"], "q3__other": "Infrastructure"},
        })

        await self.service.submit(self.session, self._ctx(), dto)

        created_sub = self.sub_repo.create.call_args.args[1]
        self.assertEqual(
            created_sub.submission["answers"],
            {"q3": ["Backend", "Other"], "q3__other": "Infrastructure"},
        )

    async def test_screening_sees_the_pruned_answers(self):
        """A rule must not fire on an answer the form had stopped showing."""
        job = self._gated_form_job()
        job.screen_rules = {
            "rules": [
                {
                    "id": "r1",
                    "condition": {
                        "source": "answer",
                        "operator": "equals",
                        "value": "F-1 OPT",
                        "questionId": "q2",
                    },
                    "action": "reject",
                }
            ]
        }
        dto = ApplicationSubmitDto.model_validate({
            "personal": REQUIRED_PERSONAL,
            "jobId": 1,
            "answers": {"q1": "No", "q2": "F-1 OPT"},
        })

        result = await self.service.submit(self.session, self._ctx(), dto)

        self.assertEqual(result.stage, ApplicationStage.RECRUITER_SCREENING)

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
        dto = ApplicationSubmitDto.model_validate({
            "jobId": 1,
            "personal": REQUIRED_PERSONAL,
        })
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
        dto = ApplicationSubmitDto.model_validate({
            "jobId": 1,
            "personal": REQUIRED_PERSONAL,
        })
        await self.service.submit(self.session, self._ctx(), dto)
        self.record_event.assert_any_await(
            self.session,
            subject_type="application",
            subject_id=100,
            actor_id=None,
            event_type="recruiting.auto_assigned",
            details={
                "stage": "recruiter_screening",
                "assigneeId": 5,
                "round": 1,
            },
        )

    async def test_submit_skips_assignment_when_no_default_configured(self):
        dto = ApplicationSubmitDto.model_validate({
            "jobId": 1,
            "personal": REQUIRED_PERSONAL,
        })
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
        dto = ApplicationSubmitDto.model_validate({
            "jobId": 1,
            "personal": REQUIRED_PERSONAL,
        })
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
        dto = ApplicationSubmitDto.model_validate({
            "jobId": 1,
            "personal": REQUIRED_PERSONAL,
        })
        await self.service.submit(self.session, self._ctx(), dto)
        self.assignment_repo.upsert.assert_not_awaited()

    async def test_submit_logs_application_submitted_activity(self):
        dto = ApplicationSubmitDto.model_validate({
            "jobId": 1,
            "personal": REQUIRED_PERSONAL,
        })
        await self.service.submit(self.session, self._ctx(), dto)
        self.record_event.assert_awaited_once_with(
            self.session,
            subject_type="application",
            subject_id=100,
            actor_id=2,
            event_type="recruiting.application_submitted",
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
        dto = ApplicationSubmitDto.model_validate({
            "jobId": 1,
            "personal": REQUIRED_PERSONAL,
        })

        await self.service.submit(self.session, self._ctx(), dto)

        self.record_event.assert_awaited_once_with(
            self.session,
            subject_type="application",
            subject_id=100,
            actor_id=2,
            event_type="recruiting.application_submitted",
            details={"stage": "recruiter_screening"},
        )

    async def test_blocked_user_lands_rejected(self):
        self.users_repo.get_user_by_user_id = AsyncMock(
            return_value=self._user(is_blocked=True)
        )
        dto = ApplicationSubmitDto.model_validate({
            "jobId": 1,
            "personal": REQUIRED_PERSONAL,
        })
        result = await self.service.submit(self.session, self._ctx(), dto)
        self.assertEqual(result.stage, ApplicationStage.REJECTED)
        self.assertFalse(result.editable)

    async def test_blocked_user_submit_logs_auto_rejected_activity(self):
        self.users_repo.get_user_by_user_id = AsyncMock(
            return_value=self._user(is_blocked=True)
        )
        dto = ApplicationSubmitDto.model_validate({
            "jobId": 1,
            "personal": REQUIRED_PERSONAL,
        })

        await self.service.submit(self.session, self._ctx(), dto)

        self.record_event.assert_awaited_once_with(
            self.session,
            subject_type="application",
            subject_id=100,
            actor_id=None,
            event_type="recruiting.auto_rejected",
            details={"reason": "blocked"},
        )

    async def test_blocked_user_resubmit_on_active_application_still_errors(self):
        """A blocked user whose latest attempt is still active (not
        REJECTED) hits the same "edit it instead" guard as anyone else —
        the blacklist check never even runs. This combination
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
        dto = ApplicationSubmitDto.model_validate({
            "jobId": 1,
            "personal": REQUIRED_PERSONAL,
        })
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
        dto = ApplicationEditDto.model_validate({
            "answers": {"q1": "z"},
            "personal": REQUIRED_PERSONAL,
        })
        result = await self.service.edit(self.session, self._ctx(), 100, dto)
        self.sub_repo.update.assert_awaited_once()
        self.sub_repo.create.assert_not_awaited()
        self.session.commit.assert_awaited()
        self.assertTrue(result.editable)

    async def test_edit_resnapshots_the_current_form_schema(self):
        """Editing re-snapshots against the schema live at edit time."""
        schema = {
            "questions": [{"id": "q1", "type": "short_text", "label": "Revised?"}]
        }
        job = self._job(status=JobStatus.PUBLISHED)
        job.form_schema = schema
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
            "answers": {"q1": "Yes"},
            "personal": REQUIRED_PERSONAL,
        })

        await self.service.edit(self.session, self._ctx(), 100, dto)

        written_sub = self.sub_repo.update.call_args.args[1]
        self.assertEqual(written_sub.submission["formSchema"], schema)

    async def test_edit_drops_answers_the_revised_form_no_longer_shows(self):
        """The candidate's client re-sends the whole prior answer bag, so an
        answer stranded by their own change — or by an owner deleting the
        question — arrives with the edit. Only the current state is kept."""
        job = self._job(status=JobStatus.PUBLISHED)
        job.form_schema = {
            "questions": [
                {
                    "id": "q1",
                    "type": "single_choice",
                    "label": "Need sponsorship?",
                    "options": ["Yes", "No"],
                },
                {
                    "id": "q2",
                    "type": "short_text",
                    "label": "Visa type?",
                    "showWhen": {"questionId": "q1", "equals": "Yes"},
                },
            ]
        }
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
            "personal": REQUIRED_PERSONAL,
            "answers": {"q1": "No", "q2": "F-1 OPT", "q5": "WeChat"},
        })

        await self.service.edit(self.session, self._ctx(), 100, dto)

        written_sub = self.sub_repo.update.call_args.args[1]
        self.assertEqual(written_sub.submission["answers"], {"q1": "No"})

    async def test_edit_does_not_require_a_hidden_question(self):
        """`required` is relaxed on the edit path too, not only on submit."""
        job = self._job(status=JobStatus.PUBLISHED)
        job.form_schema = {
            "questions": [
                {
                    "id": "q1",
                    "type": "single_choice",
                    "label": "Need sponsorship?",
                    "options": ["Yes", "No"],
                },
                {
                    "id": "q2",
                    "type": "short_text",
                    "label": "Visa type?",
                    "required": True,
                    "showWhen": {"questionId": "q1", "equals": "Yes"},
                },
            ]
        }
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
            "answers": {"q1": "No"},
            "personal": REQUIRED_PERSONAL,
        })

        await self.service.edit(self.session, self._ctx(), 100, dto)

        written_sub = self.sub_repo.update.call_args.args[1]
        self.assertEqual(written_sub.submission["answers"], {"q1": "No"})

    async def test_pruning_leaves_the_other_snapshot_sections_alone(self):
        """Only `answers` is narrowed -- profile sections are separate keys."""
        job = self._job(status=JobStatus.PUBLISHED)
        job.form_schema = {"questions": []}
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
        personal = {**REQUIRED_PERSONAL, "firstName": "A"}
        # Rows in the form's shape, which is what actually goes on the wire and
        # gets stored verbatim -- the placeholders here used to be in the
        # profile PATCH shape, which the candidate form never sends.
        dto = ApplicationEditDto.model_validate({
            "personal": personal,
            "education": [COMPLETE_EDUCATION],
            "experience": [COMPLETE_EXPERIENCE],
            "answers": {"q1": "dropped"},
        })

        await self.service.edit(self.session, self._ctx(), 100, dto)

        written = self.sub_repo.update.call_args.args[1].submission
        self.assertEqual(written["answers"], {})
        self.assertEqual(written["personal"], personal)
        self.assertEqual(written["education"], [COMPLETE_EDUCATION])
        self.assertEqual(written["experience"], [COMPLETE_EXPERIENCE])

    def _editable_app(self):
        """An application in the window where the candidate may still edit."""
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
        return app

    def _answer_rule(self, action):
        """A posting that screens on q1 == "Yes"."""
        job = self._job(
            status=JobStatus.PUBLISHED,
            screen_rules={
                "rules": [
                    {
                        "id": "r1",
                        "condition": {
                            "source": "answer",
                            "operator": "equals",
                            "questionId": "q1",
                            "value": "Yes",
                        },
                        "action": action,
                    }
                ]
            },
        )
        job.form_schema = {
            "questions": [
                {
                    "id": "q1",
                    "type": "single_choice",
                    "label": "Blocked?",
                    "options": ["Yes", "No"],
                }
            ]
        }
        self.job_repo.get_by_job_id = AsyncMock(return_value=job)
        return job

    async def test_edit_into_a_reject_rule_rejects(self):
        """An edit is a submission -- there is no save that is not one.

        Submitting "No" past a reject rule and then editing to "Yes" used to
        leave the application in the pipeline reading "Yes", with the rule
        that exists to catch exactly that never having run.
        """
        self._answer_rule("reject")
        app = self._editable_app()
        dto = ApplicationEditDto.model_validate({
            "answers": {"q1": "Yes"},
            "personal": REQUIRED_PERSONAL,
        })

        result = await self.service.edit(self.session, self._ctx(), 100, dto)

        self.assertEqual(app.stage, ApplicationStage.REJECTED)
        self.assertEqual(app.tags, {"auto_reject": "screen_rule", "rule_id": "r1"})
        self.assertFalse(result.editable)
        self.record_event.assert_awaited_once_with(
            self.session,
            subject_type="application",
            subject_id=100,
            actor_id=None,
            event_type="recruiting.auto_rejected",
            details={"reason": "screen_rule", "ruleId": "r1", "onEdit": True},
        )

    async def test_edit_that_matches_nothing_leaves_the_stage_alone(self):
        self._answer_rule("reject")
        app = self._editable_app()
        dto = ApplicationEditDto.model_validate({
            "answers": {"q1": "No"},
            "personal": REQUIRED_PERSONAL,
        })

        result = await self.service.edit(self.session, self._ctx(), 100, dto)

        self.assertEqual(app.stage, ApplicationStage.RECRUITER_SCREENING)
        self.assertIsNone(app.tags)
        self.assertTrue(result.editable)
        self.record_event.assert_not_awaited()

    async def test_edit_into_a_qualify_rule_stays_put(self):
        """qualify lands on the first stage, which is where an editable
        application already is."""
        self._answer_rule("qualify")
        app = self._editable_app()
        dto = ApplicationEditDto.model_validate({
            "answers": {"q1": "Yes"},
            "personal": REQUIRED_PERSONAL,
        })

        await self.service.edit(self.session, self._ctx(), 100, dto)

        self.assertEqual(app.stage, ApplicationStage.RECRUITER_SCREENING)
        self.assertIsNone(app.tags)

    async def test_edit_into_an_auto_hire_rule_hires(self):
        self._answer_rule("auto_hire")
        app = self._editable_app()
        dto = ApplicationEditDto.model_validate({
            "answers": {"q1": "Yes"},
            "personal": REQUIRED_PERSONAL,
        })

        await self.service.edit(self.session, self._ctx(), 100, dto)

        self.assertEqual(app.stage, ApplicationStage.HIRED)
        self.onboarding_training_svc.ensure_for_admitted.assert_awaited_once()

    async def test_edit_screens_the_answers_it_just_stored(self):
        """The rule reads the edit's answers, not the ones already on file."""
        self._answer_rule("reject")
        app = self._editable_app()
        app_sub = self.sub_repo.get_current.return_value
        app_sub.submission = {"answers": {"q1": "No"}}
        dto = ApplicationEditDto.model_validate({
            "answers": {"q1": "Yes"},
            "personal": REQUIRED_PERSONAL,
        })

        await self.service.edit(self.session, self._ctx(), 100, dto)

        self.assertEqual(app.stage, ApplicationStage.REJECTED)

    def _typed_job(self, question):
        """A published posting whose only question is the one given."""
        job = self._job(status=JobStatus.PUBLISHED)
        job.form_schema = {"questions": [question]}
        self.job_repo.get_by_job_id = AsyncMock(return_value=job)
        return job

    async def _submit_answers(self, answers, **overrides):
        """Submit `answers` with a personal block that satisfies the required
        fields, so a test about answers is not also a test about the name."""
        body = {
            "jobId": 1,
            "answers": answers,
            "personal": REQUIRED_PERSONAL,
            **overrides,
        }
        dto = ApplicationSubmitDto.model_validate(body)
        return await self.service.submit(self.session, self._ctx(), dto)

    async def test_required_message_names_the_question_not_its_id(self):
        """The message reaches the candidate verbatim, and `q1` is nowhere on
        the page they are looking at."""
        self._typed_job({
            "id": "q1",
            "type": "short_text",
            "label": "Where are you based?",
            "required": True,
        })

        with self.assertRaises(ValueError) as ctx:
            await self._submit_answers({})

        self.assertEqual(str(ctx.exception), "Where are you based? is required")

    async def test_a_choice_answer_must_be_one_of_the_options(self):
        """Also closes a required-bypass: an off-list value counts as answered
        for the gate, so the question it gates is never shown and its own
        `required` is never checked."""
        self._typed_job({
            "id": "q1",
            "type": "single_choice",
            "label": "Need sponsorship?",
            "options": ["Yes", "No"],
        })

        with self.assertRaises(ValueError) as ctx:
            await self._submit_answers({"q1": "maybe"})

        self.assertIn("pick one of the listed options", str(ctx.exception))
        self.sub_repo.create.assert_not_awaited()

    async def test_multi_choice_rejects_more_than_the_cap(self):
        self._typed_job({
            "id": "q1",
            "type": "multi_choice",
            "label": "Teams?",
            "options": ["A", "B", "C"],
            "maxSelections": 2,
        })

        with self.assertRaises(ValueError) as ctx:
            await self._submit_answers({"q1": ["A", "B", "C"]})

        self.assertIn("pick at most 2", str(ctx.exception))

    async def test_multi_choice_accepts_the_cap_exactly(self):
        self._typed_job({
            "id": "q1",
            "type": "multi_choice",
            "label": "Teams?",
            "options": ["A", "B", "C"],
            "maxSelections": 2,
        })

        await self._submit_answers({"q1": ["A", "B"]})

        self.sub_repo.create.assert_awaited_once()

    async def test_long_text_rejects_more_than_the_character_budget(self):
        self._typed_job({
            "id": "q1",
            "type": "long_text",
            "label": "Why?",
            "maxLength": 10,
        })

        with self.assertRaises(ValueError) as ctx:
            await self._submit_answers({"q1": "x" * 11})

        self.assertIn("under 10 characters", str(ctx.exception))

    async def test_short_text_rejects_more_than_the_hard_ceiling(self):
        self._typed_job({
            "id": "q1",
            "type": "short_text",
            "label": "City",
        })

        with self.assertRaises(ValueError) as ctx:
            await self._submit_answers({"q1": "x" * (SHORT_TEXT_MAX_LENGTH + 1)})

        self.assertIn(f"under {SHORT_TEXT_MAX_LENGTH} characters", str(ctx.exception))

    async def test_short_text_accepts_exactly_the_hard_ceiling(self):
        self._typed_job({
            "id": "q1",
            "type": "short_text",
            "label": "City",
        })

        await self._submit_answers({"q1": "x" * SHORT_TEXT_MAX_LENGTH})
        self.sub_repo.create.assert_awaited_once()

    async def test_long_text_without_a_budget_falls_back_to_the_ceiling(self):
        self._typed_job({
            "id": "q1",
            "type": "long_text",
            "label": "Why",
        })

        with self.assertRaises(ValueError) as ctx:
            await self._submit_answers({"q1": "x" * (LONG_TEXT_MAX_LENGTH + 1)})

        self.assertIn(f"under {LONG_TEXT_MAX_LENGTH} characters", str(ctx.exception))

    async def test_exact_text_must_match_after_trimming(self):
        self._typed_job({
            "id": "q1",
            "type": "exact_text",
            "label": "Confirm",
            "expectedValue": "I AGREE",
        })

        await self._submit_answers({"q1": "  I AGREE  "})
        self.sub_repo.create.assert_awaited_once()

        with self.assertRaises(ValueError):
            await self._submit_answers({"q1": "i agree"})

    async def test_other_free_text_is_required_once_other_is_picked(self):
        """The renderer marks it required; nothing used to hold it to that."""
        self._typed_job({
            "id": "q1",
            "type": "single_choice",
            "label": "How did you hear?",
            "options": ["Friend", "Other"],
            "otherOption": "Other",
        })

        with self.assertRaises(ValueError) as ctx:
            await self._submit_answers({"q1": "Other", "q1__other": "  "})

        self.assertIn("describe your answer", str(ctx.exception))

    async def test_other_free_text_is_not_required_when_other_is_not_picked(self):
        self._typed_job({
            "id": "q1",
            "type": "single_choice",
            "label": "How did you hear?",
            "options": ["Friend", "Other"],
            "otherOption": "Other",
        })

        await self._submit_answers({"q1": "Friend"})

        self.sub_repo.create.assert_awaited_once()

    async def test_a_hidden_question_is_not_value_checked(self):
        """A stale answer under a question the form stopped showing is pruned,
        not rejected -- otherwise changing your mind would wedge the form."""
        job = self._job(status=JobStatus.PUBLISHED)
        job.form_schema = {
            "questions": [
                {
                    "id": "q1",
                    "type": "single_choice",
                    "label": "Need sponsorship?",
                    "options": ["Yes", "No"],
                },
                {
                    "id": "q2",
                    "type": "exact_text",
                    "label": "Confirm",
                    "expectedValue": "I AGREE",
                    "showWhen": {"questionId": "q1", "equals": "Yes"},
                },
            ]
        }
        self.job_repo.get_by_job_id = AsyncMock(return_value=job)

        await self._submit_answers({"q1": "No", "q2": "nonsense"})

        created_sub = self.sub_repo.create.call_args.args[1]
        self.assertEqual(created_sub.submission["answers"], {"q1": "No"})

    async def test_a_required_profile_section_must_have_an_entry(self):
        job = self._job(status=JobStatus.PUBLISHED)
        job.profile_config = {"education": "required", "workExperience": "off"}
        self.job_repo.get_by_job_id = AsyncMock(return_value=job)

        with self.assertRaises(ValueError) as ctx:
            await self._submit_answers({})

        self.assertIn("education entry", str(ctx.exception))

    async def test_a_submission_needs_a_first_name(self):
        """The form marks it required; nothing used to hold the API to that."""
        job = self._job(status=JobStatus.PUBLISHED)
        self.job_repo.get_by_job_id = AsyncMock(return_value=job)

        with self.assertRaises(ValueError) as ctx:
            await self._submit_answers(
                {}, personal={**REQUIRED_PERSONAL, "firstName": "  "}
            )

        self.assertIn("first name", str(ctx.exception).lower())

    async def test_a_submission_needs_a_last_name_and_a_timezone(self):
        job = self._job(status=JobStatus.PUBLISHED)
        self.job_repo.get_by_job_id = AsyncMock(return_value=job)

        for field, needle in (("lastName", "last name"), ("timezone", "timezone")):
            with self.subTest(field=field):
                self.job_repo.get_by_job_id = AsyncMock(return_value=job)
                with self.assertRaises(ValueError) as ctx:
                    await self._submit_answers(
                        {}, personal={**REQUIRED_PERSONAL, field: ""}
                    )
                self.assertIn(needle, str(ctx.exception).lower())

    async def test_a_personal_block_is_required_whatever_the_profile_config(self):
        job = self._job(status=JobStatus.PUBLISHED)
        job.profile_config = {"education": "off", "workExperience": "off"}
        self.job_repo.get_by_job_id = AsyncMock(return_value=job)

        with self.assertRaises(ValueError) as ctx:
            await self._submit_answers({}, personal={})

        self.assertIn("first name", str(ctx.exception).lower())

    async def test_an_education_row_must_be_filled_in(self):
        """A row the candidate started counts; an empty one is not an entry."""
        job = self._job(status=JobStatus.PUBLISHED)
        job.profile_config = {"education": "optional", "workExperience": "off"}
        self.job_repo.get_by_job_id = AsyncMock(return_value=job)

        with self.assertRaises(ValueError) as ctx:
            await self._submit_answers({}, education=[{"id": "rpf-9"}])

        message = str(ctx.exception).lower()
        self.assertIn("education", message)
        self.assertIn("school", message)

    async def test_a_complete_education_row_is_accepted(self):
        job = self._job(status=JobStatus.PUBLISHED)
        job.profile_config = {"education": "required", "workExperience": "off"}
        self.job_repo.get_by_job_id = AsyncMock(return_value=job)

        await self._submit_answers({}, education=[COMPLETE_EDUCATION])

        self.sub_repo.create.assert_awaited()

    async def test_an_experience_row_must_be_filled_in(self):
        job = self._job(status=JobStatus.PUBLISHED)
        job.profile_config = {"education": "off", "workExperience": "optional"}
        self.job_repo.get_by_job_id = AsyncMock(return_value=job)

        with self.assertRaises(ValueError) as ctx:
            await self._submit_answers(
                {}, experience=[{**COMPLETE_EXPERIENCE, "company": " "}]
            )

        self.assertIn("company", str(ctx.exception).lower())

    async def test_an_ongoing_role_needs_no_end_date(self):
        job = self._job(status=JobStatus.PUBLISHED)
        job.profile_config = {"education": "off", "workExperience": "optional"}
        self.job_repo.get_by_job_id = AsyncMock(return_value=job)

        await self._submit_answers(
            {},
            experience=[
                {
                    **COMPLETE_EXPERIENCE,
                    "isCurrentlyWorking": True,
                    "endMonth": "",
                    "endYear": "",
                }
            ],
        )

        self.sub_repo.create.assert_awaited()

    async def test_a_finished_role_needs_an_end_date(self):
        job = self._job(status=JobStatus.PUBLISHED)
        job.profile_config = {"education": "off", "workExperience": "optional"}
        self.job_repo.get_by_job_id = AsyncMock(return_value=job)

        with self.assertRaises(ValueError) as ctx:
            await self._submit_answers(
                {},
                experience=[{**COMPLETE_EXPERIENCE, "endMonth": "", "endYear": ""}],
            )

        self.assertIn("end date", str(ctx.exception).lower())

    async def test_a_switched_off_section_has_its_rows_ignored(self):
        """The section is not on screen, so an error there is unfixable."""
        job = self._job(status=JobStatus.PUBLISHED)
        job.profile_config = {"education": "off", "workExperience": "off"}
        self.job_repo.get_by_job_id = AsyncMock(return_value=job)

        await self._submit_answers({}, education=[{"id": "rpf-9"}])

        self.sub_repo.create.assert_awaited()

    async def test_a_row_problem_names_which_entry_it_is(self):
        """`rpf-9` appears nowhere on the candidate's screen; "entry 2" does."""
        job = self._job(status=JobStatus.PUBLISHED)
        job.profile_config = {"education": "optional", "workExperience": "off"}
        self.job_repo.get_by_job_id = AsyncMock(return_value=job)

        with self.assertRaises(ValueError) as ctx:
            await self._submit_answers(
                {}, education=[COMPLETE_EDUCATION, {"id": "rpf-9"}]
            )

        message = str(ctx.exception)
        self.assertIn("2", message)
        self.assertNotIn("rpf-9", message)

    async def test_an_off_education_section_is_not_stored(self):
        """A posting that collects no education must not keep any.

        The candidate never saw the section -- it is not rendered -- so rows
        reaching here came from a résumé parse or an older submission, and
        storing them would put data on the application that nobody reviewed
        and that a later write-back could push into the profile.
        """
        job = self._job(status=JobStatus.PUBLISHED)
        job.profile_config = {"education": "off", "workExperience": "optional"}
        self.job_repo.get_by_job_id = AsyncMock(return_value=job)

        await self._submit_answers({}, education=[COMPLETE_EDUCATION])

        created_sub = self.sub_repo.create.call_args.args[1]
        self.assertEqual(created_sub.submission["education"], [])

    async def test_an_off_experience_section_is_not_stored(self):
        job = self._job(status=JobStatus.PUBLISHED)
        job.profile_config = {"education": "optional", "workExperience": "off"}
        self.job_repo.get_by_job_id = AsyncMock(return_value=job)

        await self._submit_answers({}, experience=[COMPLETE_EXPERIENCE])

        created_sub = self.sub_repo.create.call_args.args[1]
        self.assertEqual(created_sub.submission["experience"], [])

    async def test_a_collected_section_is_still_stored(self):
        """The strip is scoped to `off`; anything else passes through."""
        job = self._job(status=JobStatus.PUBLISHED)
        job.profile_config = {"education": "optional", "workExperience": "required"}
        self.job_repo.get_by_job_id = AsyncMock(return_value=job)

        await self._submit_answers(
            {}, education=[COMPLETE_EDUCATION], experience=[COMPLETE_EXPERIENCE]
        )

        created_sub = self.sub_repo.create.call_args.args[1]
        self.assertEqual(created_sub.submission["education"], [COMPLETE_EDUCATION])
        self.assertEqual(created_sub.submission["experience"], [COMPLETE_EXPERIENCE])

    async def test_a_section_with_no_config_at_all_is_stored(self):
        """`off` is opt-in; a posting saying nothing collects both."""
        job = self._job(status=JobStatus.PUBLISHED)
        job.profile_config = {}
        self.job_repo.get_by_job_id = AsyncMock(return_value=job)

        await self._submit_answers({}, education=[COMPLETE_EDUCATION])

        created_sub = self.sub_repo.create.call_args.args[1]
        self.assertEqual(created_sub.submission["education"], [COMPLETE_EDUCATION])

    async def test_latest_profile_returns_the_blocks_of_the_newest_submission(self):
        """The application form falls back to this when the profile is empty.

        Only the profile blocks: answers belong to the job they were asked
        for, and prefilling another posting's answers would be wrong.
        """
        sub = ApplicationSubmissionEntity(
            application_id=100,
            version=1,
            submission={
                "personal": REQUIRED_PERSONAL,
                "education": [COMPLETE_EDUCATION],
                "experience": [COMPLETE_EXPERIENCE],
                "answers": {"q1": "for another job"},
            },
        )
        self.sub_repo.get_latest_by_user = AsyncMock(return_value=sub)

        result = await self.service.get_my_latest_profile(self.session, self._ctx())

        self.sub_repo.get_latest_by_user.assert_awaited_once_with(self.session, 2)
        self.assertEqual(result["personal"], REQUIRED_PERSONAL)
        self.assertEqual(result["education"], [COMPLETE_EDUCATION])
        self.assertEqual(result["experience"], [COMPLETE_EXPERIENCE])
        self.assertNotIn("answers", result)

    async def test_latest_profile_is_empty_for_a_first_time_applicant(self):
        self.sub_repo.get_latest_by_user = AsyncMock(return_value=None)

        result = await self.service.get_my_latest_profile(self.session, self._ctx())

        self.assertEqual(result, {"personal": {}, "education": [], "experience": []})

    async def test_latest_profile_survives_a_submission_with_no_body(self):
        """`submission` is a nullable JSONB column."""
        sub = ApplicationSubmissionEntity(
            application_id=100, version=1, submission=None
        )
        self.sub_repo.get_latest_by_user = AsyncMock(return_value=sub)

        result = await self.service.get_my_latest_profile(self.session, self._ctx())

        self.assertEqual(result, {"personal": {}, "education": [], "experience": []})

    async def test_latest_profile_is_a_read(self):
        self.sub_repo.get_latest_by_user = AsyncMock(return_value=None)

        await self.service.get_my_latest_profile(self.session, self._ctx())

        self.session.commit.assert_not_awaited()

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
        await self.service.edit(
            self.session,
            self._ctx(),
            100,
            ApplicationEditDto(personal=REQUIRED_PERSONAL),
        )
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
        self.app_repo.get_latest_by_job_and_user.assert_awaited_once_with(
            self.session, 1, 2
        )

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
                self.session,
                self._ctx(),
                100,
                ApplicationEditDto(personal=REQUIRED_PERSONAL),
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
                self.session,
                self._ctx(),
                100,
                ApplicationEditDto(personal=REQUIRED_PERSONAL),
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
                self.session,
                self._ctx(),
                100,
                ApplicationEditDto(personal=REQUIRED_PERSONAL),
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

    async def test_submit_accepted_while_revision_under_review(self):
        """A staged revision must not stop applications to the live posting."""
        self.job_repo.get_by_job_id = AsyncMock(
            return_value=self._job(status=JobStatus.PUBLISHED_PENDING_REVISION)
        )
        dto = ApplicationSubmitDto.model_validate({
            "jobId": 1,
            "personal": REQUIRED_PERSONAL,
        })

        result = await self.service.submit(self.session, self._ctx(), dto)

        self.assertEqual(result.stage, ApplicationStage.RECRUITER_SCREENING)

    async def test_submit_accepted_while_close_under_review(self):
        """The posting keeps accepting applications until the close is approved."""
        self.job_repo.get_by_job_id = AsyncMock(
            return_value=self._job(status=JobStatus.PENDING_CLOSE)
        )
        dto = ApplicationSubmitDto.model_validate({
            "jobId": 1,
            "personal": REQUIRED_PERSONAL,
        })

        result = await self.service.submit(self.session, self._ctx(), dto)

        self.assertEqual(result.stage, ApplicationStage.RECRUITER_SCREENING)

    async def test_submit_rejected_when_posting_not_live(self):
        """A closed posting takes no applications, reopen pending or not."""
        for status in (
            JobStatus.DRAFT,
            JobStatus.PENDING_REVIEW,
            JobStatus.CLOSED,
            JobStatus.PENDING_REOPEN,
        ):
            with self.subTest(status=status):
                self.job_repo.get_by_job_id = AsyncMock(
                    return_value=self._job(status=status)
                )
                with self.assertRaises(ValueError):
                    await self.service.submit(
                        self.session,
                        self._ctx(),
                        ApplicationSubmitDto.model_validate({
                            "jobId": 1,
                            "personal": REQUIRED_PERSONAL,
                        }),
                    )

    async def test_submit_requires_resume_when_config_requires(self):
        job = self._job(status=JobStatus.PUBLISHED)
        job.profile_config = {"resume": "required"}
        self.job_repo.get_by_job_id = AsyncMock(return_value=job)
        with self.assertRaises(ValueError):
            await self.service.submit(
                self.session,
                self._ctx(),
                ApplicationSubmitDto.model_validate({
                    "jobId": 1,
                    "personal": REQUIRED_PERSONAL,
                }),
            )

    async def test_submit_drops_resume_when_posting_collects_none(self):
        job = self._job(status=JobStatus.PUBLISHED)
        job.profile_config = {"resume": "off"}
        self.job_repo.get_by_job_id = AsyncMock(return_value=job)
        dto = ApplicationSubmitDto.model_validate({
            "personal": REQUIRED_PERSONAL,
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
            "personal": REQUIRED_PERSONAL,
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
                ApplicationSubmitDto.model_validate({
                    "jobId": 1,
                    "personal": REQUIRED_PERSONAL,
                }),
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
        rejected_application.created_datetime = datetime(
            2026, 1, 10, tzinfo=timezone.utc
        )
        self.app_repo.get_latest_by_job_and_user = AsyncMock(
            return_value=rejected_application
        )
        self.service._today = lambda: date(2026, 2, 1)  # inside the 90-day window
        dto = ApplicationSubmitDto.model_validate({
            "jobId": 1,
            "personal": {**REQUIRED_PERSONAL, "firstName": "New"},
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
        rejected_application.created_datetime = datetime(
            2026, 1, 10, tzinfo=timezone.utc
        )
        self.app_repo.get_latest_by_job_and_user = AsyncMock(
            return_value=rejected_application
        )
        self.service._today = lambda: date(2026, 2, 1)  # inside the 90-day window
        dto = ApplicationSubmitDto.model_validate({
            "jobId": 1,
            "personal": {**REQUIRED_PERSONAL, "firstName": "New"},
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
        rejected_application.created_datetime = datetime(
            2026, 1, 10, tzinfo=timezone.utc
        )
        self.app_repo.get_latest_by_job_and_user = AsyncMock(
            return_value=rejected_application
        )
        self.service._today = lambda: date(2026, 2, 1)  # inside the 90-day window
        dto = ApplicationSubmitDto.model_validate({
            "jobId": 1,
            "personal": {**REQUIRED_PERSONAL, "firstName": "New"},
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
        rejected_application.created_datetime = datetime(
            2026, 1, 10, tzinfo=timezone.utc
        )
        rejected_application.tags = {"auto_reject": "screen_rule", "rule_id": "r1"}
        self.app_repo.get_latest_by_job_and_user = AsyncMock(
            return_value=rejected_application
        )
        self.service._today = lambda: date(2026, 2, 1)
        dto = ApplicationSubmitDto.model_validate({
            "jobId": 1,
            "personal": REQUIRED_PERSONAL,
        })

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
        dto = ApplicationSubmitDto.model_validate({
            "jobId": 1,
            "personal": REQUIRED_PERSONAL,
        })

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
        rejected_application.created_datetime = datetime(
            2026, 1, 10, tzinfo=timezone.utc
        )
        self.app_repo.get_latest_by_job_and_user = AsyncMock(
            return_value=rejected_application
        )
        dto = ApplicationSubmitDto.model_validate({
            "jobId": 1,
            "personal": REQUIRED_PERSONAL,
        })

        result = await self.service.submit(self.session, self._ctx(), dto)

        self.assertNotEqual(result.id, rejected_application.application_id)
        self.assertEqual(result.stage, ApplicationStage.REJECTED)
        self.assertEqual(result.tags, {"auto_reject": "blocked"})
        self.app_repo.update.assert_not_awaited()
        self.record_event.assert_awaited_once_with(
            self.session,
            subject_type="application",
            subject_id=result.id,
            actor_id=None,
            event_type="recruiting.auto_rejected",
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
        rejected_application.created_datetime = datetime(
            2026, 1, 10, tzinfo=timezone.utc
        )
        self.app_repo.get_latest_by_job_and_user = AsyncMock(
            return_value=rejected_application
        )
        self.service._today = lambda: date(2026, 5, 1)  # outside cooldown
        dto = ApplicationSubmitDto.model_validate({
            "jobId": 1,
            "personal": REQUIRED_PERSONAL,
        })
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
        rejected_application.created_datetime = datetime(
            2026, 1, 10, tzinfo=timezone.utc
        )
        # Rejection actually happened later than the prior submission.
        rejected_application.updated_timestamp = datetime(
            2026, 3, 1, tzinfo=timezone.utc
        )
        self.app_repo.get_latest_by_job_and_user = AsyncMock(
            return_value=rejected_application
        )

        self.service._today = lambda: date(2026, 4, 1)  # inside 90-day window
        dto = ApplicationSubmitDto.model_validate({
            "jobId": 1,
            "personal": {**REQUIRED_PERSONAL, "firstName": "New"},
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
        # The screen-rule email comes from user_emails, not the legacy column.
        self.user_emails_repo.list_by_user_id.return_value = [
            self._email_row("a@spam.com")
        ]
        dto = ApplicationSubmitDto.model_validate({
            "jobId": 1,
            "personal": REQUIRED_PERSONAL,
        })

        result = await self.service.submit(self.session, self._ctx(), dto)

        self.assertEqual(result.stage, ApplicationStage.REJECTED)
        self.assertEqual(result.tags, {"auto_reject": "screen_rule", "rule_id": "r1"})
        self.record_event.assert_awaited_once_with(
            self.session,
            subject_type="application",
            subject_id=100,
            actor_id=None,
            event_type="recruiting.auto_rejected",
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
        self.user_emails_repo.list_by_user_id.return_value = [
            self._email_row("a@google.com")
        ]
        dto = ApplicationSubmitDto.model_validate({
            "jobId": 1,
            "personal": REQUIRED_PERSONAL,
        })

        result = await self.service.submit(self.session, self._ctx(), dto)

        self.assertEqual(result.stage, ApplicationStage.RECRUITER_SCREENING)
        self.assertEqual(result.sub_status, "pending")
        self.assertIsNone(result.tags)
        self.record_event.assert_awaited_once_with(
            self.session,
            subject_type="application",
            subject_id=100,
            actor_id=2,
            event_type="recruiting.application_submitted",
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
        self.user_emails_repo.list_by_user_id.return_value = [
            self._email_row("a@circlecat.org")
        ]
        dto = ApplicationSubmitDto.model_validate({
            "jobId": 1,
            "personal": REQUIRED_PERSONAL,
        })

        result = await self.service.submit(self.session, self._ctx(), dto)

        self.assertEqual(result.stage, ApplicationStage.HIRED)
        self.assertIsNone(result.sub_status)
        self.assertIsNone(result.tags)
        self.record_event.assert_awaited_once_with(
            self.session,
            subject_type="application",
            subject_id=100,
            actor_id=2,
            event_type="recruiting.application_submitted",
            details={"stage": "hired", "screenAutoHireRuleId": "r1"},
        )

    async def test_submit_auto_hire_assigns_onboarding_training(self):
        """An `auto_hire` screen rule admits the candidate without any board
        action, so this is a second, independent path into HIRED --
        OnboardingTrainingService itself decides whether the job's kind/role
        actually owes one (Task 2); submit just always calls it once HIRED."""
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
        job.mentorship_role = ParticipantRole.MENTEE
        self.job_repo.get_by_job_id = AsyncMock(return_value=job)
        self.user_emails_repo.list_by_user_id.return_value = [
            self._email_row("a@circlecat.org")
        ]
        dto = ApplicationSubmitDto.model_validate({
            "jobId": 1,
            "personal": REQUIRED_PERSONAL,
        })

        await self.service.submit(self.session, self._ctx(), dto)

        self.onboarding_training_svc.ensure_for_admitted.assert_awaited_once_with(
            session=self.session,
            user_id=2,
            job=job,
        )

    async def test_submit_without_auto_hire_does_not_assign_onboarding_training(self):
        dto = ApplicationSubmitDto.model_validate({
            "jobId": 1,
            "personal": REQUIRED_PERSONAL,
        })

        result = await self.service.submit(self.session, self._ctx(), dto)

        self.assertEqual(result.stage, ApplicationStage.RECRUITER_SCREENING)
        self.onboarding_training_svc.ensure_for_admitted.assert_not_awaited()

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

        self.user_emails_repo.list_by_user_id.return_value = [
            self._email_row("a@circlecat.org")
        ]
        dto = ApplicationSubmitDto.model_validate({
            "jobId": 1,
            "personal": REQUIRED_PERSONAL,
        })
        hired_result = await self.service.submit(self.session, self._ctx(), dto)
        self.assertEqual(hired_result.stage, ApplicationStage.HIRED)

        self.user_emails_repo.list_by_user_id.return_value = [
            self._email_row("a@yahoo.com")
        ]
        rejected_result = await self.service.submit(self.session, self._ctx(), dto)
        self.assertEqual(rejected_result.stage, ApplicationStage.REJECTED)

    async def test_submit_screens_against_all_confirmed_claims(self):
        """A required-domain address held as a non-contact claim still
        satisfies the include rule and escapes the exclude rule — screening
        looks at every confirmed claim, not just the contact address."""
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
        self.user_emails_repo.list_by_user_id.return_value = [
            self._email_row("a@gmail.com"),
            self._email_row("a@circlecat.org"),
        ]
        dto = ApplicationSubmitDto.model_validate({
            "jobId": 1,
            "personal": REQUIRED_PERSONAL,
        })

        result = await self.service.submit(self.session, self._ctx(), dto)

        self.assertEqual(result.stage, ApplicationStage.HIRED)

    async def test_submit_ignores_unconfirmed_claims_in_screening(self):
        """An unverified claim can't game the screening: only
        otp_confirmed rows participate in email_domain matching."""
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
                    }
                ]
            }
        )
        self.job_repo.get_by_job_id = AsyncMock(return_value=job)
        self.user_emails_repo.list_by_user_id.return_value = [
            self._email_row("a@gmail.com"),
            self._email_row("a@circlecat.org", otp_confirmed=False),
        ]
        dto = ApplicationSubmitDto.model_validate({
            "jobId": 1,
            "personal": REQUIRED_PERSONAL,
        })

        result = await self.service.submit(self.session, self._ctx(), dto)

        self.assertEqual(result.stage, ApplicationStage.RECRUITER_SCREENING)

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
        self.user_emails_repo.list_by_user_id.return_value = [
            self._email_row("a@circlecat.org")
        ]
        dto = ApplicationSubmitDto.model_validate({
            "jobId": 1,
            "personal": REQUIRED_PERSONAL,
        })

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
        dto = ApplicationSubmitDto.model_validate({
            "jobId": 1,
            "personal": REQUIRED_PERSONAL,
        })

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
        self.user_emails_repo.list_by_user_id.return_value = [
            self._email_row("a@spam.com")
        ]
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
        dto = ApplicationSubmitDto.model_validate({
            "jobId": 1,
            "personal": REQUIRED_PERSONAL,
        })

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
        self.user_emails_repo.list_by_user_id.return_value = [
            self._email_row("a@circlecat.org")
        ]
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
        dto = ApplicationSubmitDto.model_validate({
            "jobId": 1,
            "personal": REQUIRED_PERSONAL,
        })

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
            self.session,
            self._ctx(),
            ApplicationSubmitDto.model_validate({
                "jobId": 1,
                "personal": REQUIRED_PERSONAL,
            }),
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

    def _owner_types(self):
        """The (user_id, type) pairs of every notification submit wrote."""
        return [
            (call.args[1].user_id, call.args[1].type)
            for call in self.notification_repo.create.await_args_list
        ]

    async def test_submit_writes_no_owner_notification_without_an_owner(self):
        dto = ApplicationSubmitDto.model_validate({
            "jobId": 1,
            "personal": REQUIRED_PERSONAL,
        })

        await self.service.submit(self.session, self._ctx(), dto)

        self.notification_repo.create.assert_not_awaited()
