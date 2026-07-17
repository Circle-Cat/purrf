import unittest
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, call, create_autospec

from backend.recruiting.board_service import BoardService
from backend.recruiting.recruiting_mapper import RecruitingMapper
from backend.dto.board_dto import (
    REJECT_REASONS,
    BlacklistDto,
    CommentCreateDto,
    ReassignDto,
    RoundChangeDto,
    StageChangeDto,
    SubStatusChangeDto,
)
from backend.dto.user_context_dto import UserContextDto
from backend.entity.application_assignment_entity import ApplicationAssignmentEntity
from backend.entity.application_entity import ApplicationEntity
from backend.entity.application_submission_entity import ApplicationSubmissionEntity
from backend.entity.evaluation_entity import EvaluationEntity
from backend.entity.job_entity import JobEntity
from backend.entity.users_entity import UsersEntity
from backend.common.permissions import Permission
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
from backend.repository.application_comment_repository import (
    ApplicationCommentRepository,
)
from backend.repository.application_comment_mention_repository import (
    ApplicationCommentMentionRepository,
)
from backend.repository.evaluation_repository import EvaluationRepository
from backend.repository.notification_repository import NotificationRepository


class TestBoardService(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.job_repo = MagicMock()
        self.app_repo = MagicMock()
        self.sub_repo = MagicMock()
        self.users_repo = MagicMock()
        self.users_repo.get_all_by_ids = AsyncMock(return_value=[])
        self.resume_storage = MagicMock()
        # autospec (not a bare MagicMock) so a caller/repo signature drift
        # (e.g. a new required param) fails the test instead of silently
        # accepting any arity.
        self.assignment_repo = create_autospec(
            ApplicationAssignmentRepository, instance=True
        )
        self.assignment_repo.list_by_application_ids.return_value = []
        # Default: no prior assignment on the current stage+round, so
        # reassign's "fromAssigneeId" activity-log detail defaults to None
        # unless a test seeds an existing assignment via .get.return_value.
        self.assignment_repo.get.return_value = None
        self.user_permissions_repo = MagicMock()
        self.activity_repo = create_autospec(
            ApplicationActivityRepository, instance=True
        )
        self.comment_repo = create_autospec(ApplicationCommentRepository, instance=True)
        self.comment_mention_repo = create_autospec(
            ApplicationCommentMentionRepository, instance=True
        )
        self.comment_mention_repo.get_by_comment_ids.return_value = []
        self.evaluation_repo = create_autospec(EvaluationRepository, instance=True)
        self.evaluation_repo.list_by_application.return_value = []
        self.notification_repo = create_autospec(NotificationRepository, instance=True)
        self.session = AsyncMock()
        # Applicant emails come from user_emails, not the legacy column.
        self.user_emails_repo = MagicMock()
        self.user_emails_repo.get_contact_emails_by_user_ids = AsyncMock(
            return_value={}
        )
        self.user_emails_repo.get_contact_email = AsyncMock(return_value=None)
        self.service = BoardService(
            self.job_repo,
            self.app_repo,
            self.sub_repo,
            self.users_repo,
            RecruitingMapper(),
            self.resume_storage,
            self.assignment_repo,
            self.user_permissions_repo,
            self.activity_repo,
            self.comment_repo,
            self.comment_mention_repo,
            self.evaluation_repo,
            self.notification_repo,
            self.user_emails_repo,
        )
        # Default persistence mocks: echo the entity back, like SQLAlchemy's
        # merge-and-flush does when nothing else stubs them out.
        self.app_repo.update = AsyncMock(side_effect=lambda session, entity: entity)
        self.sub_repo.update = AsyncMock(side_effect=lambda session, entity: entity)
        # Default: candidate has no other applications, so blacklist's
        # close-out-the-rest loop is a no-op unless a test seeds siblings.
        self.app_repo.list_by_user = AsyncMock(return_value=[])

    def _job(
        self,
        job_id=1,
        owner_ids=(2,),
        stages=("recruiter_screening", "tech"),
        rounds=None,
        default_assignees=None,
        kind=JobKind.ACTIVITY,
    ):
        job = JobEntity(
            kind=kind,
            title=f"Job {job_id}",
            status=JobStatus.PUBLISHED,
        )
        job.job_id = job_id
        job.form_schema = {"questions": [{"id": "q1"}]}
        rounds = rounds or {}
        default_assignees = default_assignees or {}
        job.pipeline_config = {
            "ownerIds": list(owner_ids),
            "stages": [
                {
                    "stage": s,
                    "rounds": rounds.get(s, 1),
                    **(
                        {"defaultAssigneeId": default_assignees[s]}
                        if s in default_assignees
                        else {}
                    ),
                }
                for s in stages
            ],
        }
        return job

    def _user(self, user_id=2, first="A", last="B", email="a@b.com"):
        u = UsersEntity(first_name=first, last_name=last, primary_email=email)
        u.user_id = user_id
        return u

    def _application(
        self,
        application_id=10,
        job_id=1,
        user_id=3,
        stage=ApplicationStage.RECRUITER_SCREENING,
    ):
        app = ApplicationEntity(
            job_id=job_id,
            user_id=user_id,
            stage=stage,
            sub_status="pending",
            current_round=1,
        )
        app.application_id = application_id
        return app

    def _ctx(self, user_id=2):
        return UserContextDto(sub="s", primary_email="owner@b.com", user_id=user_id)

    def _assignment(self, application_id, stage, round, assignee_id, assigned_by=2):
        return ApplicationAssignmentEntity(
            application_id=application_id,
            stage=stage,
            round=round,
            assignee_id=assignee_id,
            assigned_by=assigned_by,
        )

    def _submission(self, application_id=10, is_frozen=False):
        return ApplicationSubmissionEntity(
            application_id=application_id,
            version=1,
            submission={"answers": {}},
            is_frozen=is_frozen,
        )

    # -- list_my_jobs --

    async def test_list_my_jobs_returns_only_owned_jobs(self):
        job_a = self._job(job_id=1, owner_ids=(2,))
        job_b = self._job(job_id=2, owner_ids=(9,))
        self.job_repo.list_all = AsyncMock(return_value=[job_a, job_b])

        result = await self.service.list_my_jobs(self.session, self._ctx(user_id=2))

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].id, 1)
        self.assertEqual(
            [(s.stage, s.rounds) for s in result[0].stages],
            [("recruiter_screening", 1), ("tech", 1)],
        )

    async def test_list_my_jobs_reports_configured_rounds_per_stage(self):
        job = self._job(
            job_id=1,
            owner_ids=(2,),
            stages=("recruiter_screening", "tech"),
            rounds={"tech": 3},
        )
        self.job_repo.list_all = AsyncMock(return_value=[job])

        result = await self.service.list_my_jobs(self.session, self._ctx(user_id=2))

        self.assertEqual(
            [(s.stage, s.rounds) for s in result[0].stages],
            [("recruiter_screening", 1), ("tech", 3)],
        )

    async def test_list_my_jobs_empty_when_not_owner_of_any(self):
        job_a = self._job(job_id=1, owner_ids=(9,))
        self.job_repo.list_all = AsyncMock(return_value=[job_a])

        result = await self.service.list_my_jobs(self.session, self._ctx(user_id=2))

        self.assertEqual(result, [])

    async def test_list_my_jobs_returns_all_jobs_for_read_all_holder(self):
        job_a = self._job(job_id=1, owner_ids=(9,))
        job_b = self._job(job_id=2, owner_ids=(8,))
        self.job_repo.list_all = AsyncMock(return_value=[job_a, job_b])
        ctx = UserContextDto(
            sub="s",
            primary_email="hr@b.com",
            user_id=2,
            permissions=frozenset({Permission.RECRUITING_APPLICATION_READ_ALL}),
        )

        result = await self.service.list_my_jobs(self.session, ctx)

        self.assertEqual({j.id for j in result}, {1, 2})

    # -- _require_owner / get_board --

    async def test_get_board_groups_by_stage(self):
        job = self._job(job_id=1, owner_ids=(2,))
        self.job_repo.get_by_job_id = AsyncMock(return_value=job)
        app1 = self._application(
            application_id=10, stage=ApplicationStage.RECRUITER_SCREENING
        )
        app2 = self._application(application_id=11, stage=ApplicationStage.TECH)
        app3 = self._application(
            application_id=12, stage=ApplicationStage.RECRUITER_SCREENING
        )
        user = self._user(user_id=3)
        self.app_repo.list_by_job = AsyncMock(
            return_value=[(app1, user), (app2, user), (app3, user)]
        )

        result = await self.service.get_board(self.session, self._ctx(user_id=2), 1)

        self.assertEqual({c.id for c in result["recruiter_screening"]}, {10, 12})
        self.assertEqual({c.id for c in result["tech"]}, {11})

    async def test_get_board_raises_for_non_owner(self):
        job = self._job(job_id=1, owner_ids=(9,))
        self.job_repo.get_by_job_id = AsyncMock(return_value=job)

        with self.assertRaises(ValueError):
            await self.service.get_board(self.session, self._ctx(user_id=2), 1)

    async def test_get_board_reviewer_uses_explicit_assignment_over_default(self):
        job = self._job(
            job_id=1,
            owner_ids=(2,),
            stages=("recruiter_screening",),
            default_assignees={"recruiter_screening": 99},
        )
        self.job_repo.get_by_job_id = AsyncMock(return_value=job)
        app = self._application(
            application_id=10, stage=ApplicationStage.RECRUITER_SCREENING
        )
        user = self._user(user_id=3)
        self.app_repo.list_by_job = AsyncMock(return_value=[(app, user)])
        self.assignment_repo.list_by_application_ids = AsyncMock(
            return_value=[
                self._assignment(10, ApplicationStage.RECRUITER_SCREENING, 1, 42)
            ]
        )
        self.users_repo.get_all_by_ids = AsyncMock(
            return_value=[
                self._user(user_id=42, first="Explicit", last="Assignee"),
                self._user(user_id=99, first="Default", last="Person"),
            ]
        )

        result = await self.service.get_board(self.session, self._ctx(user_id=2), 1)

        self.assertEqual(
            result["recruiter_screening"][0].reviewer_name, "Explicit Assignee"
        )

    async def test_get_board_reviewer_falls_back_to_default_when_no_assignment(self):
        job = self._job(
            job_id=1,
            owner_ids=(2,),
            stages=("recruiter_screening",),
            default_assignees={"recruiter_screening": 99},
        )
        self.job_repo.get_by_job_id = AsyncMock(return_value=job)
        app = self._application(
            application_id=10, stage=ApplicationStage.RECRUITER_SCREENING
        )
        user = self._user(user_id=3)
        self.app_repo.list_by_job = AsyncMock(return_value=[(app, user)])
        self.users_repo.get_all_by_ids = AsyncMock(
            return_value=[self._user(user_id=99, first="Default", last="Person")]
        )

        result = await self.service.get_board(self.session, self._ctx(user_id=2), 1)

        self.assertEqual(
            result["recruiter_screening"][0].reviewer_name, "Default Person"
        )

    async def test_get_board_reviewer_none_when_no_assignment_and_no_default(self):
        job = self._job(job_id=1, owner_ids=(2,), stages=("recruiter_screening",))
        self.job_repo.get_by_job_id = AsyncMock(return_value=job)
        app = self._application(
            application_id=10, stage=ApplicationStage.RECRUITER_SCREENING
        )
        user = self._user(user_id=3)
        self.app_repo.list_by_job = AsyncMock(return_value=[(app, user)])

        result = await self.service.get_board(self.session, self._ctx(user_id=2), 1)

        self.assertIsNone(result["recruiter_screening"][0].reviewer_name)

    async def test_get_board_reviewer_none_at_round_two_even_with_round_one_default(
        self,
    ):
        job = self._job(
            job_id=1,
            owner_ids=(2,),
            stages=("recruiter_screening",),
            rounds={"recruiter_screening": 2},
            default_assignees={"recruiter_screening": 99},
        )
        self.job_repo.get_by_job_id = AsyncMock(return_value=job)
        app = self._application(
            application_id=10, stage=ApplicationStage.RECRUITER_SCREENING
        )
        app.current_round = 2
        user = self._user(user_id=3)
        self.app_repo.list_by_job = AsyncMock(return_value=[(app, user)])
        self.users_repo.get_all_by_ids = AsyncMock(
            return_value=[self._user(user_id=99, first="Default", last="Person")]
        )

        result = await self.service.get_board(self.session, self._ctx(user_id=2), 1)

        self.assertIsNone(result["recruiter_screening"][0].reviewer_name)

    async def test_get_board_reviewer_none_for_non_interview_stage(self):
        job = self._job(job_id=1, owner_ids=(2,))
        self.job_repo.get_by_job_id = AsyncMock(return_value=job)
        app = self._application(application_id=10, stage=ApplicationStage.OFFER)
        user = self._user(user_id=3)
        self.app_repo.list_by_job = AsyncMock(return_value=[(app, user)])
        # Contrived: even if an assignment row happened to exist for this
        # (application, stage, round), OFFER isn't in INTERVIEW_STAGES, so
        # it must never surface as a reviewer.
        self.assignment_repo.list_by_application_ids = AsyncMock(
            return_value=[self._assignment(10, ApplicationStage.OFFER, 1, 42)]
        )

        result = await self.service.get_board(self.session, self._ctx(user_id=2), 1)

        self.assertIsNone(result["offer"][0].reviewer_name)

    async def test_require_owner_raises_when_job_missing(self):
        self.job_repo.get_by_job_id = AsyncMock(return_value=None)

        with self.assertRaises(ValueError):
            await self.service.get_board(self.session, self._ctx(user_id=2), 999)

    async def test_get_board_succeeds_for_read_all_non_owner(self):
        job = self._job(job_id=1, owner_ids=(9,))
        self.job_repo.get_by_job_id = AsyncMock(return_value=job)
        self.app_repo.list_by_job = AsyncMock(return_value=[])
        ctx = UserContextDto(
            sub="s",
            primary_email="hr@b.com",
            user_id=2,
            permissions=frozenset({Permission.RECRUITING_APPLICATION_READ_ALL}),
        )

        result = await self.service.get_board(self.session, ctx, 1)

        self.assertEqual(result, {})

    # -- get_application_detail --

    async def test_get_application_detail_includes_resume_and_form_schema(self):
        job = self._job(job_id=1, owner_ids=(2,))
        application = self._application(application_id=10, job_id=1, user_id=3)
        applicant = self._user(user_id=3, first="C", last="D", email="c@d.com")
        current_sub = ApplicationSubmissionEntity(
            application_id=10,
            version=1,
            submission={"answers": {"q1": "yes"}},
            resume_object_key="resumes/abc.pdf",
        )
        self.app_repo.get_by_id = AsyncMock(return_value=application)
        self.job_repo.get_by_job_id = AsyncMock(return_value=job)
        self.assignment_repo.get.return_value = None
        self.users_repo.get_user_by_user_id = AsyncMock(return_value=applicant)
        self.sub_repo.get_current = AsyncMock(return_value=current_sub)
        # The applicant's email is resolved from user_emails.
        self.user_emails_repo.get_contact_email.return_value = "c@d.com"

        result = await self.service.get_application_detail(
            self.session, self._ctx(user_id=2), 10
        )

        self.assertEqual(result.application.id, 10)
        self.assertEqual(result.applicant_name, "C D")
        self.assertEqual(result.applicant_email, "c@d.com")
        self.assertTrue(result.resume_available)
        self.assertEqual(result.form_schema, {"questions": [{"id": "q1"}]})
        self.assertTrue(result.is_owner)
        self.assertIsNone(result.assignee_id)

    async def test_get_application_detail_resume_unavailable_without_submission(self):
        job = self._job(job_id=1, owner_ids=(2,))
        application = self._application(application_id=10, job_id=1, user_id=3)
        applicant = self._user(user_id=3)
        self.app_repo.get_by_id = AsyncMock(return_value=application)
        self.job_repo.get_by_job_id = AsyncMock(return_value=job)
        self.assignment_repo.get.return_value = None
        self.users_repo.get_user_by_user_id = AsyncMock(return_value=applicant)
        self.sub_repo.get_current = AsyncMock(return_value=None)

        result = await self.service.get_application_detail(
            self.session, self._ctx(user_id=2), 10
        )

        self.assertFalse(result.resume_available)

    async def test_get_application_detail_raises_when_missing(self):
        self.app_repo.get_by_id = AsyncMock(return_value=None)

        with self.assertRaises(ValueError) as ctx:
            await self.service.get_application_detail(
                self.session, self._ctx(user_id=2), 999
            )
        self.assertEqual(str(ctx.exception), "application 999 not found")

    async def test_get_application_detail_raises_for_non_owner(self):
        job = self._job(job_id=1, owner_ids=(9,))
        application = self._application(application_id=10, job_id=1, user_id=3)
        self.app_repo.get_by_id = AsyncMock(return_value=application)
        self.job_repo.get_by_job_id = AsyncMock(return_value=job)
        self.assignment_repo.get.return_value = None

        with self.assertRaises(ValueError) as ctx:
            await self.service.get_application_detail(
                self.session, self._ctx(user_id=2), 10
            )
        # Same message as the missing-application case: not-owned must be
        # indistinguishable from nonexistent, or authenticated callers could
        # enumerate which application ids exist.
        self.assertEqual(str(ctx.exception), "application 10 not found")

    async def test_get_application_detail_succeeds_for_current_stage_assignee(self):
        """A caller who is the current-stage assignee (but not an owner) can
        still read the detail view — needed once PR 3 merges the owner's
        board dialog and the assignee's evaluation view into one shared
        page served by this same read endpoint."""
        job = self._job(job_id=1, owner_ids=(9,))
        application = self._application(
            application_id=10,
            job_id=1,
            user_id=3,
            stage=ApplicationStage.RECRUITER_SCREENING,
        )
        applicant = self._user(user_id=3, first="C", last="D", email="c@d.com")
        assignment = MagicMock(assignee_id=2)
        self.app_repo.get_by_id = AsyncMock(return_value=application)
        self.job_repo.get_by_job_id = AsyncMock(return_value=job)
        self.assignment_repo.get.return_value = assignment
        self.users_repo.get_user_by_user_id = AsyncMock(return_value=applicant)
        self.sub_repo.get_current = AsyncMock(return_value=None)

        result = await self.service.get_application_detail(
            self.session, self._ctx(user_id=2), 10
        )

        self.assertEqual(result.application.id, 10)
        # Called twice: once inside `_load_owned_application` (to check
        # assignee-eligibility for the auth gate) and once more directly in
        # `get_application_detail` (to compute `assigneeId` for the DTO).
        # Assert both the args AND the exact count so a future accidental
        # extra call (or a dropped call) doesn't go unnoticed.
        self.assignment_repo.get.assert_has_awaits(
            [call(self.session, 10, ApplicationStage.RECRUITER_SCREENING, 1)] * 2
        )
        self.assertEqual(self.assignment_repo.get.await_count, 2)

    async def test_get_application_detail_raises_when_neither_owner_nor_assignee(
        self,
    ):
        job = self._job(job_id=1, owner_ids=(9,))
        application = self._application(application_id=10, job_id=1, user_id=3)
        assignment = MagicMock(assignee_id=99)
        self.app_repo.get_by_id = AsyncMock(return_value=application)
        self.job_repo.get_by_job_id = AsyncMock(return_value=job)
        self.assignment_repo.get.return_value = assignment

        with self.assertRaises(ValueError) as ctx:
            await self.service.get_application_detail(
                self.session, self._ctx(user_id=2), 10
            )
        self.assertEqual(str(ctx.exception), "application 10 not found")

    async def test_get_application_detail_owner_not_assignee_role_signals(self):
        """An owner who is not the current-stage assignee sees isOwner=True
        and the OTHER user's id as assigneeId, so the frontend can render
        the owner-decision area (and not claim they're also evaluating)."""
        job = self._job(job_id=1, owner_ids=(2,))
        application = self._application(
            application_id=10,
            job_id=1,
            user_id=3,
            stage=ApplicationStage.RECRUITER_SCREENING,
        )
        applicant = self._user(user_id=3, first="C", last="D", email="c@d.com")
        assignment = MagicMock(assignee_id=7)
        self.app_repo.get_by_id = AsyncMock(return_value=application)
        self.job_repo.get_by_job_id = AsyncMock(return_value=job)
        self.assignment_repo.get.return_value = assignment
        self.users_repo.get_user_by_user_id = AsyncMock(return_value=applicant)
        self.sub_repo.get_current = AsyncMock(return_value=None)

        result = await self.service.get_application_detail(
            self.session, self._ctx(user_id=2), 10
        )

        self.assertTrue(result.is_owner)
        self.assertEqual(result.assignee_id, 7)

    async def test_get_application_detail_assignee_not_owner_role_signals(self):
        """The current-stage assignee who is not an owner sees isOwner=False
        and their OWN id as assigneeId, so the frontend renders the
        evaluator rubric area."""
        job = self._job(job_id=1, owner_ids=(9,))
        application = self._application(
            application_id=10,
            job_id=1,
            user_id=3,
            stage=ApplicationStage.RECRUITER_SCREENING,
        )
        applicant = self._user(user_id=3, first="C", last="D", email="c@d.com")
        assignment = MagicMock(assignee_id=2)
        self.app_repo.get_by_id = AsyncMock(return_value=application)
        self.job_repo.get_by_job_id = AsyncMock(return_value=job)
        self.assignment_repo.get.return_value = assignment
        self.users_repo.get_user_by_user_id = AsyncMock(return_value=applicant)
        self.sub_repo.get_current = AsyncMock(return_value=None)

        result = await self.service.get_application_detail(
            self.session, self._ctx(user_id=2), 10
        )

        self.assertFalse(result.is_owner)
        self.assertEqual(result.assignee_id, 2)

    async def test_get_application_detail_both_owner_and_assignee_role_signals(self):
        """A caller who is both an owner and the current-stage assignee sees
        isOwner=True and their own id as assigneeId, so the frontend can
        render both the owner-decision area and the evaluator rubric."""
        job = self._job(job_id=1, owner_ids=(2,))
        application = self._application(
            application_id=10,
            job_id=1,
            user_id=3,
            stage=ApplicationStage.RECRUITER_SCREENING,
        )
        applicant = self._user(user_id=3, first="C", last="D", email="c@d.com")
        assignment = MagicMock(assignee_id=2)
        self.app_repo.get_by_id = AsyncMock(return_value=application)
        self.job_repo.get_by_job_id = AsyncMock(return_value=job)
        self.assignment_repo.get.return_value = assignment
        self.users_repo.get_user_by_user_id = AsyncMock(return_value=applicant)
        self.sub_repo.get_current = AsyncMock(return_value=None)

        result = await self.service.get_application_detail(
            self.session, self._ctx(user_id=2), 10
        )

        self.assertTrue(result.is_owner)
        self.assertEqual(result.assignee_id, 2)

    async def test_get_application_detail_no_assignment_yet_gives_none_assignee_id(
        self,
    ):
        """An application still in a non-interview stage (no assignment row
        yet) gets assigneeId=None rather than an error."""
        job = self._job(job_id=1, owner_ids=(2,))
        application = self._application(application_id=10, job_id=1, user_id=3)
        applicant = self._user(user_id=3, first="C", last="D", email="c@d.com")
        self.app_repo.get_by_id = AsyncMock(return_value=application)
        self.job_repo.get_by_job_id = AsyncMock(return_value=job)
        self.assignment_repo.get.return_value = None
        self.users_repo.get_user_by_user_id = AsyncMock(return_value=applicant)
        self.sub_repo.get_current = AsyncMock(return_value=None)

        result = await self.service.get_application_detail(
            self.session, self._ctx(user_id=2), 10
        )

        self.assertTrue(result.is_owner)
        self.assertIsNone(result.assignee_id)

    async def test_get_application_detail_succeeds_for_read_all_non_owner(self):
        job = self._job(job_id=1, owner_ids=(9,))
        application = self._application(application_id=10, job_id=1, user_id=3)
        applicant = self._user(user_id=3)
        self.app_repo.get_by_id = AsyncMock(return_value=application)
        self.job_repo.get_by_job_id = AsyncMock(return_value=job)
        self.assignment_repo.get.return_value = None
        self.users_repo.get_user_by_user_id = AsyncMock(return_value=applicant)
        self.sub_repo.get_current = AsyncMock(return_value=None)
        ctx = UserContextDto(
            sub="s",
            primary_email="hr@b.com",
            user_id=2,
            permissions=frozenset({Permission.RECRUITING_APPLICATION_READ_ALL}),
        )

        result = await self.service.get_application_detail(self.session, ctx, 10)

        self.assertEqual(result.application.id, 10)
        self.assertFalse(result.is_owner)

    async def test_get_application_detail_can_view_true_for_owner(self):
        job = self._job(job_id=1, owner_ids=(2,))
        application = self._application(application_id=10, job_id=1, user_id=3)
        applicant = self._user(user_id=3)
        self.app_repo.get_by_id = AsyncMock(return_value=application)
        self.job_repo.get_by_job_id = AsyncMock(return_value=job)
        self.assignment_repo.get.return_value = None
        self.users_repo.get_user_by_user_id = AsyncMock(return_value=applicant)
        self.sub_repo.get_current = AsyncMock(return_value=None)

        result = await self.service.get_application_detail(
            self.session, self._ctx(user_id=2), 10
        )

        self.assertTrue(result.can_view)

    async def test_get_application_detail_can_view_true_for_read_all_non_owner(self):
        job = self._job(job_id=1, owner_ids=(9,))
        application = self._application(application_id=10, job_id=1, user_id=3)
        applicant = self._user(user_id=3)
        self.app_repo.get_by_id = AsyncMock(return_value=application)
        self.job_repo.get_by_job_id = AsyncMock(return_value=job)
        self.assignment_repo.get.return_value = None
        self.users_repo.get_user_by_user_id = AsyncMock(return_value=applicant)
        self.sub_repo.get_current = AsyncMock(return_value=None)
        ctx = UserContextDto(
            sub="s",
            primary_email="hr@b.com",
            user_id=2,
            permissions=frozenset({Permission.RECRUITING_APPLICATION_READ_ALL}),
        )

        result = await self.service.get_application_detail(self.session, ctx, 10)

        self.assertTrue(result.can_view)
        self.assertFalse(result.is_owner)

    async def test_get_application_detail_can_view_false_for_plain_assignee(self):
        job = self._job(job_id=1, owner_ids=(9,))
        application = self._application(application_id=10, job_id=1, user_id=3)
        applicant = self._user(user_id=3)
        assignment = self._assignment(
            application_id=10,
            stage=ApplicationStage.RECRUITER_SCREENING,
            round=1,
            assignee_id=2,
        )
        self.app_repo.get_by_id = AsyncMock(return_value=application)
        self.job_repo.get_by_job_id = AsyncMock(return_value=job)
        self.assignment_repo.get.return_value = assignment
        self.users_repo.get_user_by_user_id = AsyncMock(return_value=applicant)
        self.sub_repo.get_current = AsyncMock(return_value=None)

        result = await self.service.get_application_detail(
            self.session, self._ctx(user_id=2), 10
        )

        self.assertFalse(result.can_view)

    # -- get_resume --

    async def test_get_resume_returns_bytes_from_storage(self):
        job = self._job(job_id=1, owner_ids=(2,))
        application = self._application(application_id=10, job_id=1, user_id=3)
        current_sub = ApplicationSubmissionEntity(
            application_id=10,
            version=1,
            submission={"answers": {}},
            resume_object_key="resumes/abc.pdf",
        )
        self.app_repo.get_by_id = AsyncMock(return_value=application)
        self.app_repo.list_by_user = AsyncMock(return_value=[(application, job)])
        self.job_repo.get_by_job_id = AsyncMock(return_value=job)
        self.sub_repo.get_current = AsyncMock(return_value=current_sub)
        self.resume_storage.get = MagicMock(return_value=b"%PDF-1.4 data")

        result = await self.service.get_resume(self.session, self._ctx(user_id=2), 10)

        self.assertEqual(result, b"%PDF-1.4 data")
        self.resume_storage.get.assert_called_once_with("resumes/abc.pdf")

    async def test_get_resume_raises_when_missing(self):
        self.app_repo.get_by_id = AsyncMock(return_value=None)

        with self.assertRaises(ValueError) as ctx:
            await self.service.get_resume(self.session, self._ctx(user_id=2), 999)
        self.assertEqual(str(ctx.exception), "application 999 not found")

    async def test_get_resume_raises_for_third_party_with_collapsed_message(self):
        """Neither an owner nor the current-stage assignee: same collapsed
        "not found" message as get_application_detail, not a distinct 403."""
        job = self._job(job_id=1, owner_ids=(9,))
        application = self._application(application_id=10, job_id=1, user_id=3)
        self.app_repo.get_by_id = AsyncMock(return_value=application)
        self.app_repo.list_by_user = AsyncMock(return_value=[(application, job)])
        self.job_repo.get_by_job_id = AsyncMock(return_value=job)
        self.assignment_repo.get.return_value = None

        with self.assertRaises(ValueError) as ctx:
            await self.service.get_resume(self.session, self._ctx(user_id=2), 10)
        self.assertEqual(str(ctx.exception), "application 10 not found")

    async def test_get_resume_succeeds_for_applications_own_submitter(self):
        """The candidate herself can read her own application's résumé, even
        though she is neither the job's owner nor its current-stage
        assignee — needed so she can preview a résumé reference her
        application form inherited without a fresh upload."""
        job = self._job(job_id=1, owner_ids=(9,))  # caller is not an owner
        application = self._application(application_id=10, job_id=1, user_id=2)
        current_sub = ApplicationSubmissionEntity(
            application_id=10,
            version=1,
            submission={"answers": {}},
            resume_object_key="resumes/abc.pdf",
        )
        self.app_repo.get_by_id = AsyncMock(return_value=application)
        self.app_repo.list_by_user = AsyncMock(return_value=[(application, job)])
        self.job_repo.get_by_job_id = AsyncMock(return_value=job)
        self.assignment_repo.get.return_value = None  # not the assignee either
        self.sub_repo.get_current = AsyncMock(return_value=current_sub)
        self.resume_storage.get = MagicMock(return_value=b"%PDF-1.4 data")

        result = await self.service.get_resume(self.session, self._ctx(user_id=2), 10)

        self.assertEqual(result, b"%PDF-1.4 data")

    async def test_get_resume_succeeds_for_current_stage_assignee(self):
        """The shared detail page (#138) lets a non-owner assignee view
        everything else about an application; the résumé must not be the one
        piece of it gated owner-only."""
        job = self._job(job_id=1, owner_ids=(9,))  # caller is not an owner
        application = self._application(application_id=10, job_id=1, user_id=3)
        assignment = self._assignment(
            application_id=10, stage=application.stage, round=1, assignee_id=2
        )
        current_sub = ApplicationSubmissionEntity(
            application_id=10,
            version=1,
            submission={"answers": {}},
            resume_object_key="resumes/abc.pdf",
        )
        self.app_repo.get_by_id = AsyncMock(return_value=application)
        self.app_repo.list_by_user = AsyncMock(return_value=[(application, job)])
        self.job_repo.get_by_job_id = AsyncMock(return_value=job)
        self.assignment_repo.get.return_value = assignment
        self.sub_repo.get_current = AsyncMock(return_value=current_sub)
        self.resume_storage.get = MagicMock(return_value=b"%PDF-1.4 data")

        result = await self.service.get_resume(self.session, self._ctx(user_id=2), 10)

        self.assertEqual(result, b"%PDF-1.4 data")

    async def test_get_resume_raises_when_no_resume_on_file(self):
        job = self._job(job_id=1, owner_ids=(2,))
        application = self._application(application_id=10, job_id=1, user_id=3)
        self.app_repo.get_by_id = AsyncMock(return_value=application)
        self.job_repo.get_by_job_id = AsyncMock(return_value=job)
        self.app_repo.list_by_user = AsyncMock(return_value=[(application, job)])
        self.sub_repo.get_current = AsyncMock(return_value=None)

        with self.assertRaises(ValueError) as ctx:
            await self.service.get_resume(self.session, self._ctx(user_id=2), 10)
        self.assertEqual(str(ctx.exception), "no resume on file for application 10")
        self.resume_storage.get.assert_not_called()

    async def test_get_resume_succeeds_via_sibling_application_standing(self):
        """A caller who owns/is-assigned-to a DIFFERENT application by the
        same candidate (reached this résumé request via the aggregation
        view) can still fetch it, even with no direct relationship to the
        requested application's own job."""
        requested_job = self._job(job_id=1, owner_ids=(9,))
        sibling_job = self._job(job_id=2, owner_ids=(2,))
        requested_app = self._application(application_id=10, job_id=1, user_id=3)
        sibling_app = self._application(application_id=11, job_id=2, user_id=3)
        current_sub = ApplicationSubmissionEntity(
            application_id=10,
            version=1,
            submission={},
            resume_object_key="resumes/abc.pdf",
        )
        # Keyed by application_id (like job_repo below): _load_owned_application
        # re-fetches per candidate row, so a single return_value would wrongly
        # reuse requested_app's job for the sibling row too.
        self.app_repo.get_by_id = AsyncMock(
            side_effect=lambda _session, application_id, for_update=False: {
                10: requested_app,
                11: sibling_app,
            }[application_id]
        )
        self.app_repo.list_by_user = AsyncMock(
            return_value=[(requested_app, requested_job), (sibling_app, sibling_job)]
        )
        self.job_repo.get_by_job_id = AsyncMock(
            side_effect=lambda _session, job_id: {
                1: requested_job,
                2: sibling_job,
            }[job_id]
        )
        self.assignment_repo.get.return_value = None
        self.sub_repo.get_current = AsyncMock(return_value=current_sub)
        self.resume_storage.get.return_value = b"%PDF-1.4"

        result = await self.service.get_resume(self.session, self._ctx(user_id=2), 10)

        self.assertEqual(result, b"%PDF-1.4")

    async def test_get_resume_raises_with_no_standing_on_any_sibling(self):
        requested_job = self._job(job_id=1, owner_ids=(9,))
        other_job = self._job(job_id=2, owner_ids=(8,))
        requested_app = self._application(application_id=10, job_id=1, user_id=3)
        other_app = self._application(application_id=11, job_id=2, user_id=3)
        self.app_repo.get_by_id = AsyncMock(return_value=requested_app)
        self.app_repo.list_by_user = AsyncMock(
            return_value=[(requested_app, requested_job), (other_app, other_job)]
        )
        self.job_repo.get_by_job_id = AsyncMock(
            side_effect=lambda _session, job_id: {
                1: requested_job,
                2: other_job,
            }[job_id]
        )
        self.assignment_repo.get.return_value = None

        with self.assertRaises(ValueError):
            await self.service.get_resume(self.session, self._ctx(user_id=2), 10)

    # -- change_stage --

    async def test_change_stage_advances_resets_sub_status_and_freezes(self):
        job = self._job(
            job_id=1, owner_ids=(2,), stages=("recruiter_screening", "tech")
        )
        application = self._application(
            application_id=10,
            job_id=1,
            stage=ApplicationStage.RECRUITER_SCREENING,
        )
        application.current_round = 2
        application.sub_status = "in_progress"
        current_sub = self._submission(application_id=10, is_frozen=False)
        self.job_repo.get_by_job_id = AsyncMock(return_value=job)
        self.app_repo.get_by_id = AsyncMock(return_value=application)
        self.sub_repo.get_current = AsyncMock(return_value=current_sub)
        self.user_permissions_repo.get_active_users_with_permission = AsyncMock(
            return_value=[self._user(user_id=42)]
        )

        dto = StageChangeDto(to_stage=ApplicationStage.TECH, assignee_id=42)
        result = await self.service.change_stage(
            self.session, self._ctx(user_id=2), 10, dto
        )

        self.assertEqual(result.stage, ApplicationStage.TECH)
        self.assertEqual(result.sub_status, "pending")
        self.assertIsNone(result.tags)
        self.assertTrue(current_sub.is_frozen)
        self.sub_repo.update.assert_awaited_once()
        self.app_repo.update.assert_awaited_once()
        self.session.commit.assert_awaited_once()
        self.assignment_repo.upsert.assert_awaited_once_with(
            self.session, 10, ApplicationStage.TECH, 1, 42, 2
        )
        self.assertEqual(result.current_round, 1)

    async def test_change_stage_last_stage_to_offer_clears_sub_status(self):
        job = self._job(
            job_id=1, owner_ids=(2,), stages=("tech",), kind=JobKind.EMPLOYMENT
        )
        application = self._application(
            application_id=10, job_id=1, stage=ApplicationStage.TECH
        )
        self.job_repo.get_by_job_id = AsyncMock(return_value=job)
        self.app_repo.get_by_id = AsyncMock(return_value=application)
        self.sub_repo.get_current = AsyncMock(return_value=None)

        dto = StageChangeDto(to_stage=ApplicationStage.OFFER)
        result = await self.service.change_stage(
            self.session, self._ctx(user_id=2), 10, dto
        )

        self.assertEqual(result.stage, ApplicationStage.OFFER)
        self.assertIsNone(result.sub_status)

    async def test_change_stage_offer_to_hired_is_always_allowed(self):
        """Offer is a fixed step before Hired (not a configurable pipeline
        stage) — advancing out of it uses the same generic Advance action
        as any other stage, with no special-casing needed."""
        job = self._job(
            job_id=1, owner_ids=(2,), stages=("board_review",), kind=JobKind.EMPLOYMENT
        )
        application = self._application(
            application_id=10, job_id=1, stage=ApplicationStage.OFFER
        )
        self.job_repo.get_by_job_id = AsyncMock(return_value=job)
        self.app_repo.get_by_id = AsyncMock(return_value=application)
        self.sub_repo.get_current = AsyncMock(return_value=None)

        dto = StageChangeDto(to_stage=ApplicationStage.HIRED)
        result = await self.service.change_stage(
            self.session, self._ctx(user_id=2), 10, dto
        )

        self.assertEqual(result.stage, ApplicationStage.HIRED)
        self.assertIsNone(result.sub_status)

    async def test_change_stage_offer_to_rejected_with_declined_reason(self):
        """The owner rejects from Offer the same generic way as any other
        stage, using the "candidate declined" reason."""
        job = self._job(
            job_id=1, owner_ids=(2,), stages=("board_review",), kind=JobKind.EMPLOYMENT
        )
        application = self._application(
            application_id=10, job_id=1, stage=ApplicationStage.OFFER
        )
        self.job_repo.get_by_job_id = AsyncMock(return_value=job)
        self.app_repo.get_by_id = AsyncMock(return_value=application)
        self.sub_repo.get_current = AsyncMock(return_value=None)

        dto = StageChangeDto(
            to_stage=ApplicationStage.REJECTED,
            reason="Candidate declined the offer",
        )
        result = await self.service.change_stage(
            self.session, self._ctx(user_id=2), 10, dto
        )

        self.assertEqual(result.stage, ApplicationStage.REJECTED)
        self.assertEqual(
            result.tags["reject"]["reason"], "Candidate declined the offer"
        )
        self.assertEqual(result.tags["reject"]["fromStage"], "offer")

    async def test_change_stage_activity_last_stage_advances_straight_to_hired(self):
        """ACTIVITY jobs have no Offer step: the last configured stage
        advances directly to HIRED (shown as "Admitted" in the UI)."""
        job = self._job(job_id=1, owner_ids=(2,), stages=("tech",))
        application = self._application(
            application_id=10, job_id=1, stage=ApplicationStage.TECH
        )
        self.job_repo.get_by_job_id = AsyncMock(return_value=job)
        self.app_repo.get_by_id = AsyncMock(return_value=application)
        self.sub_repo.get_current = AsyncMock(return_value=None)

        dto = StageChangeDto(to_stage=ApplicationStage.HIRED)
        result = await self.service.change_stage(
            self.session, self._ctx(user_id=2), 10, dto
        )

        self.assertEqual(result.stage, ApplicationStage.HIRED)
        self.assertIsNone(result.sub_status)

    async def test_change_stage_activity_move_to_offer_raises(self):
        job = self._job(job_id=1, owner_ids=(2,), stages=("tech",))
        application = self._application(
            application_id=10, job_id=1, stage=ApplicationStage.TECH
        )
        self.job_repo.get_by_job_id = AsyncMock(return_value=job)
        self.app_repo.get_by_id = AsyncMock(return_value=application)
        self.sub_repo.get_current = AsyncMock(return_value=None)

        dto = StageChangeDto(to_stage=ApplicationStage.OFFER)
        with self.assertRaises(ValueError):
            await self.service.change_stage(self.session, self._ctx(user_id=2), 10, dto)

    async def test_change_stage_illegal_transition_raises_without_mutating(self):
        job = self._job(job_id=1, owner_ids=(2,), stages=("tech",))
        application = self._application(
            application_id=10, job_id=1, stage=ApplicationStage.TECH
        )
        self.job_repo.get_by_job_id = AsyncMock(return_value=job)
        self.app_repo.get_by_id = AsyncMock(return_value=application)
        self.sub_repo.get_current = AsyncMock(return_value=None)

        dto = StageChangeDto(to_stage=ApplicationStage.BEHAVIORAL)
        with self.assertRaises(ValueError):
            await self.service.change_stage(self.session, self._ctx(user_id=2), 10, dto)

        self.assertEqual(application.stage, ApplicationStage.TECH)
        self.app_repo.update.assert_not_awaited()
        self.sub_repo.update.assert_not_awaited()
        self.session.commit.assert_not_awaited()

    async def test_change_stage_reject_stores_tags_reject_with_from_stage(self):
        job = self._job(job_id=1, owner_ids=(2,), stages=("tech",))
        application = self._application(
            application_id=10, job_id=1, stage=ApplicationStage.TECH
        )
        application.current_round = 2
        self.job_repo.get_by_job_id = AsyncMock(return_value=job)
        self.app_repo.get_by_id = AsyncMock(return_value=application)
        self.sub_repo.get_current = AsyncMock(return_value=None)

        dto = StageChangeDto(
            to_stage=ApplicationStage.REJECTED,
            reason=REJECT_REASONS[0],
            note="not a fit",
        )
        result = await self.service.change_stage(
            self.session, self._ctx(user_id=2), 10, dto
        )

        self.assertEqual(result.stage, ApplicationStage.REJECTED)
        self.assertIsNone(result.sub_status)
        reject_tag = result.tags["reject"]
        self.assertEqual(reject_tag["reason"], REJECT_REASONS[0])
        self.assertEqual(reject_tag["note"], "not a fit")
        self.assertEqual(reject_tag["fromStage"], "tech")
        # "at" is an ISO-8601 timestamp; just assert it parses.
        datetime.fromisoformat(reject_tag["at"])
        self.assertEqual(result.current_round, 1)

    async def test_change_stage_non_owner_gets_collapsed_not_found_message(self):
        job = self._job(job_id=1, owner_ids=(9,))
        application = self._application(application_id=10, job_id=1)
        self.job_repo.get_by_job_id = AsyncMock(return_value=job)
        self.app_repo.get_by_id = AsyncMock(return_value=application)

        dto = StageChangeDto(to_stage=ApplicationStage.TECH)
        with self.assertRaises(ValueError) as ctx:
            await self.service.change_stage(self.session, self._ctx(user_id=2), 10, dto)
        self.assertEqual(str(ctx.exception), "application 10 not found")

    async def test_change_stage_assignee_but_not_owner_still_raises(self):
        """change_stage is a mutation path — it must stay owner-only. Even
        though the caller is the application's current-stage assignee, that
        must not satisfy `_load_owned_application` here, proving the
        `allow_assignee` default (False) didn't leak into this call site."""
        job = self._job(job_id=1, owner_ids=(9,))
        application = self._application(
            application_id=10, job_id=1, stage=ApplicationStage.RECRUITER_SCREENING
        )
        assignment = MagicMock(assignee_id=2)
        self.job_repo.get_by_job_id = AsyncMock(return_value=job)
        self.app_repo.get_by_id = AsyncMock(return_value=application)
        self.assignment_repo.get.return_value = assignment

        dto = StageChangeDto(to_stage=ApplicationStage.TECH)
        with self.assertRaises(ValueError) as ctx:
            await self.service.change_stage(self.session, self._ctx(user_id=2), 10, dto)
        self.assertEqual(str(ctx.exception), "application 10 not found")
        self.assignment_repo.get.assert_not_awaited()

    async def test_change_stage_missing_application_gets_same_message(self):
        self.app_repo.get_by_id = AsyncMock(return_value=None)

        dto = StageChangeDto(to_stage=ApplicationStage.TECH)
        with self.assertRaises(ValueError) as ctx:
            await self.service.change_stage(
                self.session, self._ctx(user_id=2), 999, dto
            )
        self.assertEqual(str(ctx.exception), "application 999 not found")

    async def test_change_stage_row_locks_the_application(self):
        job = self._job(
            job_id=1, owner_ids=(2,), stages=("tech",), kind=JobKind.EMPLOYMENT
        )
        application = self._application(
            application_id=10, job_id=1, stage=ApplicationStage.TECH
        )
        self.job_repo.get_by_job_id = AsyncMock(return_value=job)
        self.app_repo.get_by_id = AsyncMock(return_value=application)
        self.sub_repo.get_current = AsyncMock(return_value=None)

        dto = StageChangeDto(to_stage=ApplicationStage.OFFER)
        await self.service.change_stage(self.session, self._ctx(user_id=2), 10, dto)

        self.app_repo.get_by_id.assert_awaited_once_with(
            self.session, 10, for_update=True
        )

    async def test_change_stage_to_interview_stage_allows_missing_assignee_id(self):
        """Picking an assignee at advance time is optional: the owner may
        leave the target stage unassigned and use `reassign` once it's
        entered, instead of being forced to pick someone up front."""
        job = self._job(
            job_id=1, owner_ids=(2,), stages=("recruiter_screening", "tech")
        )
        application = self._application(
            application_id=10, job_id=1, stage=ApplicationStage.RECRUITER_SCREENING
        )
        self.job_repo.get_by_job_id = AsyncMock(return_value=job)
        self.app_repo.get_by_id = AsyncMock(return_value=application)
        self.sub_repo.get_current = AsyncMock(return_value=None)

        dto = StageChangeDto(to_stage=ApplicationStage.TECH)  # no assignee_id
        result = await self.service.change_stage(
            self.session, self._ctx(user_id=2), 10, dto
        )

        self.assertEqual(result.stage, ApplicationStage.TECH)
        self.assignment_repo.upsert.assert_not_awaited()
        self.app_repo.update.assert_awaited_once()
        self.session.commit.assert_awaited_once()

    async def test_change_stage_to_interview_stage_rejects_unqualified_assignee(self):
        job = self._job(
            job_id=1, owner_ids=(2,), stages=("recruiter_screening", "tech")
        )
        application = self._application(
            application_id=10, job_id=1, stage=ApplicationStage.RECRUITER_SCREENING
        )
        self.job_repo.get_by_job_id = AsyncMock(return_value=job)
        self.app_repo.get_by_id = AsyncMock(return_value=application)
        self.sub_repo.get_current = AsyncMock(return_value=None)
        self.user_permissions_repo.get_active_users_with_permission = AsyncMock(
            return_value=[]
        )

        dto = StageChangeDto(to_stage=ApplicationStage.TECH, assignee_id=99)
        with self.assertRaisesRegex(ValueError, "99"):
            await self.service.change_stage(self.session, self._ctx(user_id=2), 10, dto)

        self.assignment_repo.upsert.assert_not_awaited()
        self.app_repo.update.assert_not_awaited()
        self.session.commit.assert_not_awaited()

    async def test_change_stage_to_interview_stage_persists_assignment(self):
        job = self._job(
            job_id=1, owner_ids=(2,), stages=("recruiter_screening", "tech")
        )
        application = self._application(
            application_id=10, job_id=1, stage=ApplicationStage.RECRUITER_SCREENING
        )
        self.job_repo.get_by_job_id = AsyncMock(return_value=job)
        self.app_repo.get_by_id = AsyncMock(return_value=application)
        self.sub_repo.get_current = AsyncMock(return_value=None)
        self.user_permissions_repo.get_active_users_with_permission = AsyncMock(
            return_value=[self._user(user_id=42)]
        )

        dto = StageChangeDto(to_stage=ApplicationStage.TECH, assignee_id=42)
        await self.service.change_stage(self.session, self._ctx(user_id=2), 10, dto)

        self.assignment_repo.upsert.assert_awaited_once_with(
            self.session, 10, ApplicationStage.TECH, 1, 42, 2
        )

    async def test_change_stage_notifies_new_interview_assignee(self):
        job = self._job(job_id=1, owner_ids=(9,))
        application = self._application(
            application_id=10, job_id=1, stage=ApplicationStage.RECRUITER_SCREENING
        )
        self.job_repo.get_by_job_id = AsyncMock(return_value=job)
        self.app_repo.get_by_id = AsyncMock(return_value=application)
        self.sub_repo.get_current = AsyncMock(return_value=None)
        self.assignment_repo.get = AsyncMock(return_value=None)
        self.user_permissions_repo.get_active_users_with_permission = AsyncMock(
            return_value=[self._user(user_id=5)]
        )

        dto = StageChangeDto(to_stage=ApplicationStage.TECH, assignee_id=5)
        await self.service.change_stage(self.session, self._ctx(user_id=9), 10, dto)

        self.notification_repo.create.assert_awaited_once()
        (session_arg, entity_arg), _ = self.notification_repo.create.call_args
        self.assertEqual(session_arg, self.session)
        self.assertEqual(entity_arg.user_id, 5)
        self.assertEqual(entity_arg.type, NotificationType.ASSIGNED_TO_EVALUATE)
        self.assertEqual(entity_arg.application_id, 10)
        self.assertEqual(entity_arg.round, 1)
        self.assertEqual(entity_arg.actor_user_id, 9)

    async def test_change_stage_does_not_notify_when_reassigning_same_person(self):
        job = self._job(job_id=1, owner_ids=(9,))
        application = self._application(
            application_id=10, job_id=1, stage=ApplicationStage.RECRUITER_SCREENING
        )
        self.job_repo.get_by_job_id = AsyncMock(return_value=job)
        self.app_repo.get_by_id = AsyncMock(return_value=application)
        self.sub_repo.get_current = AsyncMock(return_value=None)
        existing = MagicMock()
        existing.assignee_id = 5
        self.assignment_repo.get = AsyncMock(return_value=existing)
        self.user_permissions_repo.get_active_users_with_permission = AsyncMock(
            return_value=[self._user(user_id=5)]
        )

        dto = StageChangeDto(to_stage=ApplicationStage.TECH, assignee_id=5)
        await self.service.change_stage(self.session, self._ctx(user_id=9), 10, dto)

        self.notification_repo.create.assert_not_awaited()

    async def test_change_stage_to_hired_ignores_assignee_id(self):
        job = self._job(
            job_id=1, owner_ids=(2,), stages=("tech",), kind=JobKind.EMPLOYMENT
        )
        application = self._application(
            application_id=10, job_id=1, stage=ApplicationStage.OFFER
        )
        self.job_repo.get_by_job_id = AsyncMock(return_value=job)
        self.app_repo.get_by_id = AsyncMock(return_value=application)
        self.sub_repo.get_current = AsyncMock(return_value=None)

        dto = StageChangeDto(to_stage=ApplicationStage.HIRED)  # no assignee_id
        await self.service.change_stage(self.session, self._ctx(user_id=2), 10, dto)

        self.assignment_repo.upsert.assert_not_awaited()
        self.user_permissions_repo.get_active_users_with_permission.assert_not_called()

    # -- reassign --

    async def test_reassign_promotes_evaluated_to_scheduled_on_scheduling_stage(self):
        """TECH uses scheduling/scheduled instead of in_progress -- an
        "evaluated" application being reassigned means the interview itself
        already happened, so it drops back to "scheduled" (not
        "scheduling": no new slot needs booking), leaving the new assignee
        to submit their own evaluation."""
        job = self._job(
            job_id=1, owner_ids=(2,), stages=("recruiter_screening", "tech")
        )
        application = self._application(
            application_id=10, job_id=1, stage=ApplicationStage.TECH
        )
        application.sub_status = "evaluated"
        current_sub = self._submission(application_id=10, is_frozen=True)
        self.job_repo.get_by_job_id = AsyncMock(return_value=job)
        self.app_repo.get_by_id = AsyncMock(return_value=application)
        self.sub_repo.get_current = AsyncMock(return_value=current_sub)
        self.user_permissions_repo.get_active_users_with_permission = AsyncMock(
            return_value=[self._user(user_id=42)]
        )

        dto = ReassignDto(assignee_id=42)
        result = await self.service.reassign(
            self.session, self._ctx(user_id=2), 10, dto
        )

        self.assertEqual(result.sub_status, "scheduled")
        self.assignment_repo.upsert.assert_awaited_once_with(
            self.session, 10, ApplicationStage.TECH, 1, 42, 2
        )
        self.app_repo.update.assert_awaited_once()
        self.session.commit.assert_awaited_once()

    async def test_reassign_promotes_pending_to_scheduling_on_scheduling_stage(self):
        job = self._job(
            job_id=1, owner_ids=(2,), stages=("recruiter_screening", "tech")
        )
        application = self._application(
            application_id=10, job_id=1, stage=ApplicationStage.TECH
        )
        application.sub_status = "pending"
        self.job_repo.get_by_job_id = AsyncMock(return_value=job)
        self.app_repo.get_by_id = AsyncMock(return_value=application)
        self.sub_repo.get_current = AsyncMock(return_value=None)
        self.user_permissions_repo.get_active_users_with_permission = AsyncMock(
            return_value=[self._user(user_id=42)]
        )

        dto = ReassignDto(assignee_id=42)
        result = await self.service.reassign(
            self.session, self._ctx(user_id=2), 10, dto
        )

        self.assertEqual(result.sub_status, "scheduling")

    async def test_reassign_leaves_scheduling_unchanged_on_scheduling_stage(self):
        job = self._job(
            job_id=1, owner_ids=(2,), stages=("recruiter_screening", "tech")
        )
        application = self._application(
            application_id=10, job_id=1, stage=ApplicationStage.TECH
        )
        application.sub_status = "scheduling"
        self.job_repo.get_by_job_id = AsyncMock(return_value=job)
        self.app_repo.get_by_id = AsyncMock(return_value=application)
        self.sub_repo.get_current = AsyncMock(return_value=None)
        self.user_permissions_repo.get_active_users_with_permission = AsyncMock(
            return_value=[self._user(user_id=42)]
        )

        dto = ReassignDto(assignee_id=42)
        result = await self.service.reassign(
            self.session, self._ctx(user_id=2), 10, dto
        )

        self.assertEqual(result.sub_status, "scheduling")

    async def test_reassign_promotes_pending_to_in_progress_when_available(self):
        job = self._job(
            job_id=1, owner_ids=(2,), stages=("recruiter_screening", "tech")
        )
        application = self._application(
            application_id=10, job_id=1, stage=ApplicationStage.RECRUITER_SCREENING
        )
        application.sub_status = "pending"
        self.job_repo.get_by_job_id = AsyncMock(return_value=job)
        self.app_repo.get_by_id = AsyncMock(return_value=application)
        self.sub_repo.get_current = AsyncMock(return_value=None)
        self.user_permissions_repo.get_active_users_with_permission = AsyncMock(
            return_value=[self._user(user_id=42)]
        )

        dto = ReassignDto(assignee_id=42)
        result = await self.service.reassign(
            self.session, self._ctx(user_id=2), 10, dto
        )

        self.assertEqual(result.sub_status, "in_progress")

    async def test_reassign_promotes_evaluated_to_in_progress_when_available(self):
        """A single "evaluated" isn't enough -- reassigning while evaluated
        means the new assignee still owes their own evaluation, so it's
        promoted back to "in_progress" rather than left as if the stage
        were done."""
        job = self._job(
            job_id=1, owner_ids=(2,), stages=("recruiter_screening", "tech")
        )
        application = self._application(
            application_id=10, job_id=1, stage=ApplicationStage.RECRUITER_SCREENING
        )
        application.sub_status = "evaluated"
        self.job_repo.get_by_job_id = AsyncMock(return_value=job)
        self.app_repo.get_by_id = AsyncMock(return_value=application)
        self.sub_repo.get_current = AsyncMock(return_value=None)
        self.user_permissions_repo.get_active_users_with_permission = AsyncMock(
            return_value=[self._user(user_id=42)]
        )

        dto = ReassignDto(assignee_id=42)
        result = await self.service.reassign(
            self.session, self._ctx(user_id=2), 10, dto
        )

        self.assertEqual(result.sub_status, "in_progress")

    async def test_reassign_leaves_in_progress_unchanged(self):
        job = self._job(
            job_id=1, owner_ids=(2,), stages=("recruiter_screening", "tech")
        )
        application = self._application(
            application_id=10, job_id=1, stage=ApplicationStage.RECRUITER_SCREENING
        )
        application.sub_status = "in_progress"
        self.job_repo.get_by_job_id = AsyncMock(return_value=job)
        self.app_repo.get_by_id = AsyncMock(return_value=application)
        self.sub_repo.get_current = AsyncMock(return_value=None)
        self.user_permissions_repo.get_active_users_with_permission = AsyncMock(
            return_value=[self._user(user_id=42)]
        )

        dto = ReassignDto(assignee_id=42)
        result = await self.service.reassign(
            self.session, self._ctx(user_id=2), 10, dto
        )

        self.assertEqual(result.sub_status, "in_progress")

    async def test_reassign_targets_the_applications_current_round(self):
        job = self._job(
            job_id=1, owner_ids=(2,), stages=("recruiter_screening", "tech")
        )
        application = self._application(
            application_id=10, job_id=1, stage=ApplicationStage.TECH
        )
        application.current_round = 2
        self.job_repo.get_by_job_id = AsyncMock(return_value=job)
        self.app_repo.get_by_id = AsyncMock(return_value=application)
        self.sub_repo.get_current = AsyncMock(return_value=None)
        self.user_permissions_repo.get_active_users_with_permission = AsyncMock(
            return_value=[self._user(user_id=42)]
        )

        dto = ReassignDto(assignee_id=42)
        await self.service.reassign(self.session, self._ctx(user_id=2), 10, dto)

        self.assignment_repo.upsert.assert_awaited_once_with(
            self.session, 10, ApplicationStage.TECH, 2, 42, 2
        )

    async def test_reassign_on_terminal_stage_raises(self):
        job = self._job(job_id=1, owner_ids=(2,), stages=("tech",))
        application = self._application(
            application_id=10, job_id=1, stage=ApplicationStage.HIRED
        )
        self.job_repo.get_by_job_id = AsyncMock(return_value=job)
        self.app_repo.get_by_id = AsyncMock(return_value=application)

        dto = ReassignDto(assignee_id=42)
        with self.assertRaises(ValueError):
            await self.service.reassign(self.session, self._ctx(user_id=2), 10, dto)

        self.assignment_repo.upsert.assert_not_awaited()
        self.app_repo.update.assert_not_awaited()
        self.session.commit.assert_not_awaited()

    async def test_reassign_rejects_unqualified_assignee(self):
        job = self._job(
            job_id=1, owner_ids=(2,), stages=("recruiter_screening", "tech")
        )
        application = self._application(
            application_id=10, job_id=1, stage=ApplicationStage.TECH
        )
        self.job_repo.get_by_job_id = AsyncMock(return_value=job)
        self.app_repo.get_by_id = AsyncMock(return_value=application)
        self.user_permissions_repo.get_active_users_with_permission = AsyncMock(
            return_value=[]
        )

        dto = ReassignDto(assignee_id=99)
        with self.assertRaisesRegex(ValueError, "99"):
            await self.service.reassign(self.session, self._ctx(user_id=2), 10, dto)

        self.assignment_repo.upsert.assert_not_awaited()
        self.app_repo.update.assert_not_awaited()
        self.session.commit.assert_not_awaited()

    async def test_reassign_non_owner_gets_collapsed_not_found_message(self):
        job = self._job(job_id=1, owner_ids=(9,), stages=("tech",))
        application = self._application(
            application_id=10, job_id=1, stage=ApplicationStage.TECH
        )
        self.job_repo.get_by_job_id = AsyncMock(return_value=job)
        self.app_repo.get_by_id = AsyncMock(return_value=application)

        dto = ReassignDto(assignee_id=42)
        with self.assertRaises(ValueError) as ctx:
            await self.service.reassign(self.session, self._ctx(user_id=2), 10, dto)
        self.assertEqual(str(ctx.exception), "application 10 not found")

    async def test_reassign_row_locks_the_application(self):
        job = self._job(job_id=1, owner_ids=(2,), stages=("tech",))
        application = self._application(
            application_id=10, job_id=1, stage=ApplicationStage.TECH
        )
        self.job_repo.get_by_job_id = AsyncMock(return_value=job)
        self.app_repo.get_by_id = AsyncMock(return_value=application)
        self.sub_repo.get_current = AsyncMock(return_value=None)
        self.user_permissions_repo.get_active_users_with_permission = AsyncMock(
            return_value=[self._user(user_id=42)]
        )

        dto = ReassignDto(assignee_id=42)
        await self.service.reassign(self.session, self._ctx(user_id=2), 10, dto)

        self.app_repo.get_by_id.assert_awaited_once_with(
            self.session, 10, for_update=True
        )

    async def test_reassign_notifies_new_assignee(self):
        application = self._application(
            application_id=10, job_id=1, stage=ApplicationStage.TECH
        )
        self.job_repo.get_by_job_id = AsyncMock(
            return_value=self._job(job_id=1, owner_ids=(9,))
        )
        self.app_repo.get_by_id = AsyncMock(return_value=application)
        self.sub_repo.get_current = AsyncMock(return_value=None)
        previous = MagicMock()
        previous.assignee_id = 5
        self.assignment_repo.get = AsyncMock(return_value=previous)
        self.user_permissions_repo.get_active_users_with_permission = AsyncMock(
            return_value=[self._user(user_id=6)]
        )

        dto = ReassignDto(assignee_id=6)
        await self.service.reassign(self.session, self._ctx(user_id=9), 10, dto)

        self.notification_repo.create.assert_awaited_once()
        (_session_arg, entity_arg), _ = self.notification_repo.create.call_args
        self.assertEqual(entity_arg.user_id, 6)
        self.assertEqual(entity_arg.type, NotificationType.ASSIGNED_TO_EVALUATE)
        self.assertEqual(entity_arg.application_id, 10)
        self.assertEqual(entity_arg.actor_user_id, 9)

    async def test_reassign_to_same_person_does_not_notify(self):
        application = self._application(
            application_id=10, job_id=1, stage=ApplicationStage.TECH
        )
        self.job_repo.get_by_job_id = AsyncMock(
            return_value=self._job(job_id=1, owner_ids=(9,))
        )
        self.app_repo.get_by_id = AsyncMock(return_value=application)
        self.sub_repo.get_current = AsyncMock(return_value=None)
        previous = MagicMock()
        previous.assignee_id = 6
        self.assignment_repo.get = AsyncMock(return_value=previous)
        self.user_permissions_repo.get_active_users_with_permission = AsyncMock(
            return_value=[self._user(user_id=6)]
        )

        dto = ReassignDto(assignee_id=6)
        await self.service.reassign(self.session, self._ctx(user_id=9), 10, dto)

        self.notification_repo.create.assert_not_awaited()

    # -- set_sub_status --

    async def test_set_sub_status_valid_switch_freezes_on_first_leave(self):
        job = self._job(job_id=1, owner_ids=(2,))
        application = self._application(
            application_id=10, job_id=1, stage=ApplicationStage.RECRUITER_SCREENING
        )
        application.sub_status = "pending"
        current_sub = self._submission(application_id=10, is_frozen=False)
        self.job_repo.get_by_job_id = AsyncMock(return_value=job)
        self.app_repo.get_by_id = AsyncMock(return_value=application)
        self.sub_repo.get_current = AsyncMock(return_value=current_sub)

        dto = SubStatusChangeDto(sub_status="in_progress")
        result = await self.service.set_sub_status(
            self.session, self._ctx(user_id=2), 10, dto
        )

        self.assertEqual(result.sub_status, "in_progress")
        self.assertTrue(current_sub.is_frozen)
        self.sub_repo.update.assert_awaited_once()
        self.app_repo.update.assert_awaited_once()
        self.session.commit.assert_awaited_once()

    async def test_set_sub_status_logs_activity(self):
        job = self._job(job_id=1, owner_ids=(2,))
        application = self._application(
            application_id=10, job_id=1, stage=ApplicationStage.RECRUITER_SCREENING
        )
        application.sub_status = "pending"
        self.job_repo.get_by_job_id = AsyncMock(return_value=job)
        self.app_repo.get_by_id = AsyncMock(return_value=application)
        self.sub_repo.get_current = AsyncMock(return_value=None)

        dto = SubStatusChangeDto(sub_status="in_progress")
        await self.service.set_sub_status(self.session, self._ctx(user_id=2), 10, dto)

        self.activity_repo.create.assert_awaited_once_with(
            self.session,
            10,
            2,
            "sub_status_changed",
            details={
                "stage": ApplicationStage.RECRUITER_SCREENING.value,
                "fromSubStatus": "pending",
                "toSubStatus": "in_progress",
            },
        )

    async def test_set_sub_status_invalid_value_raises_without_mutating(self):
        job = self._job(job_id=1, owner_ids=(2,))
        application = self._application(
            application_id=10, job_id=1, stage=ApplicationStage.RECRUITER_SCREENING
        )
        application.sub_status = "pending"
        self.job_repo.get_by_job_id = AsyncMock(return_value=job)
        self.app_repo.get_by_id = AsyncMock(return_value=application)
        self.sub_repo.get_current = AsyncMock(return_value=None)

        dto = SubStatusChangeDto(sub_status="not_a_real_value")
        with self.assertRaises(ValueError):
            await self.service.set_sub_status(
                self.session, self._ctx(user_id=2), 10, dto
            )

        self.assertEqual(application.sub_status, "pending")
        self.app_repo.update.assert_not_awaited()
        self.sub_repo.update.assert_not_awaited()
        self.session.commit.assert_not_awaited()

    async def test_set_sub_status_between_non_pending_values_does_not_refreeze(self):
        job = self._job(job_id=1, owner_ids=(2,))
        application = self._application(
            application_id=10, job_id=1, stage=ApplicationStage.RECRUITER_SCREENING
        )
        application.sub_status = "in_progress"
        current_sub = self._submission(application_id=10, is_frozen=True)
        self.job_repo.get_by_job_id = AsyncMock(return_value=job)
        self.app_repo.get_by_id = AsyncMock(return_value=application)
        self.sub_repo.get_current = AsyncMock(return_value=current_sub)

        dto = SubStatusChangeDto(sub_status="evaluated")
        result = await self.service.set_sub_status(
            self.session, self._ctx(user_id=2), 10, dto
        )

        self.assertEqual(result.sub_status, "evaluated")
        self.sub_repo.update.assert_not_awaited()

    async def test_set_sub_status_back_to_pending_does_not_unfreeze(self):
        job = self._job(job_id=1, owner_ids=(2,))
        application = self._application(
            application_id=10, job_id=1, stage=ApplicationStage.RECRUITER_SCREENING
        )
        application.sub_status = "evaluated"
        current_sub = self._submission(application_id=10, is_frozen=True)
        self.job_repo.get_by_job_id = AsyncMock(return_value=job)
        self.app_repo.get_by_id = AsyncMock(return_value=application)
        self.sub_repo.get_current = AsyncMock(return_value=current_sub)

        dto = SubStatusChangeDto(sub_status="pending")
        result = await self.service.set_sub_status(
            self.session, self._ctx(user_id=2), 10, dto
        )

        self.assertEqual(result.sub_status, "pending")
        self.sub_repo.update.assert_not_awaited()
        self.assertTrue(current_sub.is_frozen)

    async def test_set_sub_status_non_owner_gets_collapsed_not_found_message(self):
        job = self._job(job_id=1, owner_ids=(9,))
        application = self._application(application_id=10, job_id=1)
        self.job_repo.get_by_job_id = AsyncMock(return_value=job)
        self.app_repo.get_by_id = AsyncMock(return_value=application)

        dto = SubStatusChangeDto(sub_status="in_progress")
        with self.assertRaises(ValueError) as ctx:
            await self.service.set_sub_status(
                self.session, self._ctx(user_id=2), 10, dto
            )
        self.assertEqual(str(ctx.exception), "application 10 not found")

    async def test_set_sub_status_row_locks_the_application(self):
        job = self._job(job_id=1, owner_ids=(2,))
        application = self._application(
            application_id=10, job_id=1, stage=ApplicationStage.RECRUITER_SCREENING
        )
        application.sub_status = "pending"
        self.job_repo.get_by_job_id = AsyncMock(return_value=job)
        self.app_repo.get_by_id = AsyncMock(return_value=application)
        self.sub_repo.get_current = AsyncMock(return_value=None)

        dto = SubStatusChangeDto(sub_status="in_progress")
        await self.service.set_sub_status(self.session, self._ctx(user_id=2), 10, dto)

        self.app_repo.get_by_id.assert_awaited_once_with(
            self.session, 10, for_update=True
        )

    # -- blacklist --

    async def test_blacklist_writes_block_fields_on_the_user(self):
        user = self._user(user_id=3)
        application = self._application(
            application_id=10, job_id=1, user_id=3, stage=ApplicationStage.TECH
        )
        self.users_repo.get_user_by_user_id = AsyncMock(return_value=user)
        self.app_repo.get_by_id = AsyncMock(return_value=application)
        self.sub_repo.get_current = AsyncMock(return_value=None)

        dto = BlacklistDto(
            user_id=3, application_id=10, reason="Fabricated credentials"
        )
        await self.service.blacklist(self.session, self._ctx(user_id=99), dto)

        self.assertTrue(user.is_blocked)
        self.assertEqual(user.blocked_by, 99)
        self.assertEqual(user.blocked_reason, "Fabricated credentials")
        self.assertIsNotNone(user.blocked_at)

    async def test_blacklist_closes_tags_and_freezes_the_application(self):
        user = self._user(user_id=3)
        application = self._application(
            application_id=10, job_id=1, user_id=3, stage=ApplicationStage.TECH
        )
        application.current_round = 2
        application.sub_status = "in_progress"
        application.tags = {"existing": "keep-me"}
        current_sub = self._submission(application_id=10, is_frozen=False)
        self.users_repo.get_user_by_user_id = AsyncMock(return_value=user)
        self.app_repo.get_by_id = AsyncMock(return_value=application)
        self.sub_repo.get_current = AsyncMock(return_value=current_sub)

        dto = BlacklistDto(
            user_id=3, application_id=10, reason="Fabricated credentials"
        )
        result = await self.service.blacklist(self.session, self._ctx(user_id=99), dto)

        self.assertEqual(result.stage, ApplicationStage.REJECTED)
        self.assertIsNone(result.sub_status)
        self.assertEqual(result.tags["existing"], "keep-me")
        self.assertTrue(result.tags["blacklisted"])
        self.assertTrue(current_sub.is_frozen)
        self.app_repo.update.assert_awaited_once()
        self.session.commit.assert_awaited_once()
        self.assertEqual(result.current_round, 1)

    async def test_blacklist_logs_activity(self):
        user = self._user(user_id=3)
        application = self._application(
            application_id=10, job_id=1, user_id=3, stage=ApplicationStage.TECH
        )
        current_sub = self._submission(application_id=10, is_frozen=False)
        self.users_repo.get_user_by_user_id = AsyncMock(return_value=user)
        self.app_repo.get_by_id = AsyncMock(return_value=application)
        self.sub_repo.get_current = AsyncMock(return_value=current_sub)

        dto = BlacklistDto(
            user_id=3, application_id=10, reason="Fabricated credentials"
        )
        await self.service.blacklist(self.session, self._ctx(user_id=99), dto)

        self.activity_repo.create.assert_awaited_once_with(
            self.session,
            10,
            99,
            "blacklisted",
            details={
                "fromStage": ApplicationStage.TECH.value,
                "reason": "Fabricated credentials",
            },
        )

    async def test_blacklist_row_locks_the_application(self):
        user = self._user(user_id=3)
        application = self._application(application_id=10, job_id=1, user_id=3)
        self.users_repo.get_user_by_user_id = AsyncMock(return_value=user)
        self.app_repo.get_by_id = AsyncMock(return_value=application)
        self.sub_repo.get_current = AsyncMock(return_value=None)

        dto = BlacklistDto(user_id=3, application_id=10, reason="Spam")
        await self.service.blacklist(self.session, self._ctx(user_id=99), dto)

        self.app_repo.get_by_id.assert_awaited_once_with(
            self.session, 10, for_update=True
        )

    async def test_blacklist_missing_user_raises(self):
        self.users_repo.get_user_by_user_id = AsyncMock(return_value=None)
        self.app_repo.get_by_id = AsyncMock(return_value=None)

        dto = BlacklistDto(user_id=3, application_id=10, reason="Spam")
        with self.assertRaises(ValueError):
            await self.service.blacklist(self.session, self._ctx(user_id=99), dto)
        self.app_repo.get_by_id.assert_not_awaited()

    async def test_blacklist_missing_application_raises(self):
        user = self._user(user_id=3)
        self.users_repo.get_user_by_user_id = AsyncMock(return_value=user)
        self.app_repo.get_by_id = AsyncMock(return_value=None)

        dto = BlacklistDto(user_id=3, application_id=999, reason="Spam")
        with self.assertRaises(ValueError) as ctx:
            await self.service.blacklist(self.session, self._ctx(user_id=99), dto)
        self.assertEqual(str(ctx.exception), "application 999 not found")

    async def test_blacklist_application_belonging_to_other_user_raises(self):
        user = self._user(user_id=3)
        application = self._application(application_id=10, job_id=1, user_id=4)
        self.users_repo.get_user_by_user_id = AsyncMock(return_value=user)
        self.app_repo.get_by_id = AsyncMock(return_value=application)

        dto = BlacklistDto(user_id=3, application_id=10, reason="Spam")
        with self.assertRaises(ValueError) as ctx:
            await self.service.blacklist(self.session, self._ctx(user_id=99), dto)
        self.assertEqual(str(ctx.exception), "application 10 not found")
        self.app_repo.update.assert_not_awaited()
        self.session.commit.assert_not_awaited()

    async def test_blacklist_is_not_owner_gated(self):
        """The caller need not own the application's job — only the
        RECRUITING_BLACKLIST_WRITE permission (checked at the route) gates
        this action."""
        user = self._user(user_id=3)
        application = self._application(application_id=10, job_id=1, user_id=3)
        self.users_repo.get_user_by_user_id = AsyncMock(return_value=user)
        self.app_repo.get_by_id = AsyncMock(return_value=application)
        self.sub_repo.get_current = AsyncMock(return_value=None)
        # job_repo is deliberately never consulted; blacklist doesn't load
        # the job or check ownership at all.
        self.job_repo.get_by_job_id = AsyncMock(
            side_effect=AssertionError("blacklist must not check job ownership")
        )

        dto = BlacklistDto(user_id=3, application_id=10, reason="Spam")
        await self.service.blacklist(self.session, self._ctx(user_id=42), dto)

        self.job_repo.get_by_job_id.assert_not_awaited()

    async def test_blacklist_rejects_other_in_flight_applications(self):
        """Blacklisting closes out every other in-flight application of the
        same user (2026-07-15 decision), not just the triggering one.
        HIRED and already-REJECTED rows are left untouched."""
        user = self._user(user_id=3)
        job_a = self._job(job_id=1, owner_ids=(2,))
        job_b = self._job(job_id=2, owner_ids=(2,))
        job_c = self._job(job_id=3, owner_ids=(2,))
        job_d = self._job(job_id=4, owner_ids=(2,))
        trigger = self._application(
            application_id=10, job_id=1, user_id=3, stage=ApplicationStage.TECH
        )
        second = self._application(
            application_id=11, job_id=2, user_id=3, stage=ApplicationStage.APPLIED
        )
        second.current_round = 2
        third = self._application(
            application_id=12, job_id=3, user_id=3, stage=ApplicationStage.HIRED
        )
        fourth = self._application(
            application_id=13, job_id=4, user_id=3, stage=ApplicationStage.REJECTED
        )
        apps_by_id = {10: trigger, 11: second, 12: third, 13: fourth}
        self.users_repo.get_user_by_user_id = AsyncMock(return_value=user)
        self.app_repo.get_by_id = AsyncMock(
            side_effect=lambda _session, application_id, for_update=False: apps_by_id[
                application_id
            ]
        )
        self.app_repo.list_by_user = AsyncMock(
            return_value=[
                (trigger, job_a),
                (second, job_b),
                (third, job_c),
                (fourth, job_d),
            ]
        )
        self.sub_repo.get_current = AsyncMock(return_value=None)

        dto = BlacklistDto(
            user_id=3, application_id=10, reason="Fabricated credentials"
        )
        await self.service.blacklist(self.session, self._ctx(user_id=99), dto)

        self.assertEqual(second.stage, ApplicationStage.REJECTED)
        self.assertTrue(second.tags["blacklisted"])
        self.assertIsNone(second.sub_status)
        self.assertEqual(second.current_round, 1)
        self.assertEqual(third.stage, ApplicationStage.HIRED)
        self.assertIsNone(fourth.tags)
        self.app_repo.list_by_user.assert_awaited_once_with(self.session, 3)
        self.assertEqual(self.activity_repo.create.call_count, 2)
        second_call = self.activity_repo.create.call_args_list[1]
        self.assertEqual(
            second_call.args,
            (self.session, 11, 99, "blacklisted"),
        )
        self.assertEqual(
            second_call.kwargs,
            {
                "details": {
                    "fromStage": ApplicationStage.APPLIED.value,
                    "reason": "Fabricated credentials",
                }
            },
        )

    # -- set_round --

    async def test_set_round_advances_to_a_valid_round(self):
        job = self._job(job_id=1, owner_ids=(2,), stages=("tech",), rounds={"tech": 3})
        application = self._application(
            application_id=10, job_id=1, stage=ApplicationStage.TECH
        )
        self.job_repo.get_by_job_id = AsyncMock(return_value=job)
        self.app_repo.get_by_id = AsyncMock(return_value=application)
        self.sub_repo.get_current = AsyncMock(return_value=None)
        self.user_permissions_repo.get_active_users_with_permission = AsyncMock(
            return_value=[self._user(user_id=42)]
        )

        dto = RoundChangeDto(round=2, assignee_id=42)
        result = await self.service.set_round(
            self.session, self._ctx(user_id=2), 10, dto
        )

        self.assertEqual(result.current_round, 2)
        self.assignment_repo.upsert.assert_awaited_once_with(
            self.session, 10, ApplicationStage.TECH, 2, 42, 2
        )
        self.app_repo.update.assert_awaited_once()
        self.session.commit.assert_awaited_once()

    async def test_set_round_resets_sub_status_to_pending(self):
        """Mirrors reassign/change_stage: advancing to a new round must not
        leave the prior round's "evaluated" sub_status on a round nobody has
        evaluated yet."""
        job = self._job(job_id=1, owner_ids=(2,), stages=("tech",), rounds={"tech": 3})
        application = self._application(
            application_id=10, job_id=1, stage=ApplicationStage.TECH
        )
        application.sub_status = "evaluated"
        self.job_repo.get_by_job_id = AsyncMock(return_value=job)
        self.app_repo.get_by_id = AsyncMock(return_value=application)
        self.sub_repo.get_current = AsyncMock(return_value=None)
        self.user_permissions_repo.get_active_users_with_permission = AsyncMock(
            return_value=[self._user(user_id=42)]
        )

        dto = RoundChangeDto(round=2, assignee_id=42)
        result = await self.service.set_round(
            self.session, self._ctx(user_id=2), 10, dto
        )

        self.assertEqual(result.sub_status, "pending")

    async def test_set_round_rejects_round_above_the_stage_configured_max(self):
        job = self._job(job_id=1, owner_ids=(2,), stages=("tech",), rounds={"tech": 2})
        application = self._application(
            application_id=10, job_id=1, stage=ApplicationStage.TECH
        )
        self.job_repo.get_by_job_id = AsyncMock(return_value=job)
        self.app_repo.get_by_id = AsyncMock(return_value=application)

        dto = RoundChangeDto(round=3)
        with self.assertRaises(ValueError):
            await self.service.set_round(self.session, self._ctx(user_id=2), 10, dto)

        self.assertEqual(application.current_round, 1)
        self.app_repo.update.assert_not_awaited()
        self.session.commit.assert_not_awaited()

    async def test_set_round_non_owner_gets_collapsed_not_found_message(self):
        job = self._job(job_id=1, owner_ids=(9,))
        application = self._application(application_id=10, job_id=1)
        self.job_repo.get_by_job_id = AsyncMock(return_value=job)
        self.app_repo.get_by_id = AsyncMock(return_value=application)

        dto = RoundChangeDto(round=1)
        with self.assertRaises(ValueError) as ctx:
            await self.service.set_round(self.session, self._ctx(user_id=2), 10, dto)
        self.assertEqual(str(ctx.exception), "application 10 not found")

    async def test_set_round_row_locks_the_application(self):
        job = self._job(job_id=1, owner_ids=(2,), stages=("tech",), rounds={"tech": 2})
        application = self._application(
            application_id=10, job_id=1, stage=ApplicationStage.TECH
        )
        self.job_repo.get_by_job_id = AsyncMock(return_value=job)
        self.app_repo.get_by_id = AsyncMock(return_value=application)
        self.sub_repo.get_current = AsyncMock(return_value=None)
        self.user_permissions_repo.get_active_users_with_permission = AsyncMock(
            return_value=[self._user(user_id=42)]
        )

        dto = RoundChangeDto(round=2, assignee_id=42)
        await self.service.set_round(self.session, self._ctx(user_id=2), 10, dto)

        self.app_repo.get_by_id.assert_awaited_once_with(
            self.session, 10, for_update=True
        )

    async def test_set_round_to_interview_stage_without_assignee_leaves_it_unassigned(
        self,
    ):
        """A round can be left unassigned, mirroring change_stage's
        optional-assignee advance -- picked up later via reassign."""
        job = self._job(job_id=1, owner_ids=(2,), stages=("tech",), rounds={"tech": 2})
        application = self._application(
            application_id=10, job_id=1, stage=ApplicationStage.TECH
        )
        self.job_repo.get_by_job_id = AsyncMock(return_value=job)
        self.app_repo.get_by_id = AsyncMock(return_value=application)
        self.sub_repo.get_current = AsyncMock(return_value=None)

        dto = RoundChangeDto(round=2)  # no assignee_id
        result = await self.service.set_round(
            self.session, self._ctx(user_id=2), 10, dto
        )

        self.assertEqual(result.current_round, 2)
        self.assignment_repo.upsert.assert_not_awaited()
        self.user_permissions_repo.get_active_users_with_permission.assert_not_called()
        self.app_repo.update.assert_awaited_once()
        self.session.commit.assert_awaited_once()

    async def test_set_round_rejects_unqualified_assignee(self):
        job = self._job(job_id=1, owner_ids=(2,), stages=("tech",), rounds={"tech": 2})
        application = self._application(
            application_id=10, job_id=1, stage=ApplicationStage.TECH
        )
        self.job_repo.get_by_job_id = AsyncMock(return_value=job)
        self.app_repo.get_by_id = AsyncMock(return_value=application)
        self.sub_repo.get_current = AsyncMock(return_value=None)
        self.user_permissions_repo.get_active_users_with_permission = AsyncMock(
            return_value=[]
        )

        dto = RoundChangeDto(round=2, assignee_id=99)
        with self.assertRaisesRegex(ValueError, "99"):
            await self.service.set_round(self.session, self._ctx(user_id=2), 10, dto)

        self.assignment_repo.upsert.assert_not_awaited()
        self.app_repo.update.assert_not_awaited()
        self.session.commit.assert_not_awaited()

    # -- activity timeline logging --

    async def test_change_stage_logs_stage_changed_activity(self):
        job = self._job(
            job_id=1, owner_ids=(2,), stages=("recruiter_screening", "tech")
        )
        application = self._application(
            application_id=10, job_id=1, stage=ApplicationStage.RECRUITER_SCREENING
        )
        self.job_repo.get_by_job_id = AsyncMock(return_value=job)
        self.app_repo.get_by_id = AsyncMock(return_value=application)
        self.sub_repo.get_current = AsyncMock(return_value=None)
        self.user_permissions_repo.get_active_users_with_permission = AsyncMock(
            return_value=[self._user(user_id=42)]
        )

        dto = StageChangeDto(to_stage=ApplicationStage.TECH, assignee_id=42)
        await self.service.change_stage(self.session, self._ctx(user_id=2), 10, dto)

        self.activity_repo.create.assert_awaited_once_with(
            self.session,
            10,
            2,
            "stage_changed",
            details={
                "fromStage": "recruiter_screening",
                "toStage": "tech",
                "assigneeId": 42,
            },
        )

    async def test_change_stage_reject_logs_reason_and_note_in_activity(self):
        job = self._job(job_id=1, owner_ids=(2,), stages=("tech",))
        application = self._application(
            application_id=10, job_id=1, stage=ApplicationStage.TECH
        )
        self.job_repo.get_by_job_id = AsyncMock(return_value=job)
        self.app_repo.get_by_id = AsyncMock(return_value=application)
        self.sub_repo.get_current = AsyncMock(return_value=None)

        dto = StageChangeDto(
            to_stage=ApplicationStage.REJECTED,
            reason=REJECT_REASONS[0],
            note="not a fit",
        )
        await self.service.change_stage(self.session, self._ctx(user_id=2), 10, dto)

        self.activity_repo.create.assert_awaited_once_with(
            self.session,
            10,
            2,
            "stage_changed",
            details={
                "fromStage": "tech",
                "toStage": "rejected",
                "reason": REJECT_REASONS[0],
                "note": "not a fit",
            },
        )

    async def test_reassign_logs_activity_with_from_and_to_assignee(self):
        job = self._job(
            job_id=1, owner_ids=(2,), stages=("recruiter_screening", "tech")
        )
        application = self._application(
            application_id=10, job_id=1, stage=ApplicationStage.TECH
        )
        self.job_repo.get_by_job_id = AsyncMock(return_value=job)
        self.app_repo.get_by_id = AsyncMock(return_value=application)
        self.sub_repo.get_current = AsyncMock(return_value=None)
        self.user_permissions_repo.get_active_users_with_permission = AsyncMock(
            return_value=[self._user(user_id=42)]
        )
        self.assignment_repo.get.return_value = ApplicationAssignmentEntity(
            application_id=10,
            stage=ApplicationStage.TECH,
            round=1,
            assignee_id=7,
            assigned_by=2,
        )

        dto = ReassignDto(assignee_id=42)
        await self.service.reassign(self.session, self._ctx(user_id=2), 10, dto)

        self.activity_repo.create.assert_awaited_once_with(
            self.session,
            10,
            2,
            "reassigned",
            details={
                "stage": "tech",
                "round": 1,
                "fromAssigneeId": 7,
                "toAssigneeId": 42,
            },
        )

    async def test_reassign_logs_none_from_assignee_when_stage_was_unassigned(self):
        job = self._job(
            job_id=1, owner_ids=(2,), stages=("recruiter_screening", "tech")
        )
        application = self._application(
            application_id=10, job_id=1, stage=ApplicationStage.TECH
        )
        self.job_repo.get_by_job_id = AsyncMock(return_value=job)
        self.app_repo.get_by_id = AsyncMock(return_value=application)
        self.sub_repo.get_current = AsyncMock(return_value=None)
        self.user_permissions_repo.get_active_users_with_permission = AsyncMock(
            return_value=[self._user(user_id=42)]
        )

        dto = ReassignDto(assignee_id=42)
        await self.service.reassign(self.session, self._ctx(user_id=2), 10, dto)

        self.activity_repo.create.assert_awaited_once_with(
            self.session,
            10,
            2,
            "reassigned",
            details={
                "stage": "tech",
                "round": 1,
                "fromAssigneeId": None,
                "toAssigneeId": 42,
            },
        )

    async def test_set_round_logs_round_advanced_activity(self):
        job = self._job(job_id=1, owner_ids=(2,), stages=("tech",), rounds={"tech": 3})
        application = self._application(
            application_id=10, job_id=1, stage=ApplicationStage.TECH
        )
        self.job_repo.get_by_job_id = AsyncMock(return_value=job)
        self.app_repo.get_by_id = AsyncMock(return_value=application)
        self.sub_repo.get_current = AsyncMock(return_value=None)
        self.user_permissions_repo.get_active_users_with_permission = AsyncMock(
            return_value=[self._user(user_id=42)]
        )

        dto = RoundChangeDto(round=2, assignee_id=42)
        await self.service.set_round(self.session, self._ctx(user_id=2), 10, dto)

        self.activity_repo.create.assert_awaited_once_with(
            self.session,
            10,
            2,
            "round_advanced",
            details={
                "stage": "tech",
                "fromRound": 1,
                "toRound": 2,
                "assigneeId": 42,
            },
        )

    # -- get_application_activity --

    async def test_get_application_activity_returns_dtos_with_resolved_actor_names(
        self,
    ):
        job = self._job(job_id=1, owner_ids=(2,))
        application = self._application(application_id=10, job_id=1)
        self.job_repo.get_by_job_id = AsyncMock(return_value=job)
        self.app_repo.get_by_id = AsyncMock(return_value=application)
        row = SimpleNamespace(
            activity_id=1,
            application_id=10,
            actor_id=42,
            event_type="stage_changed",
            details={"toStage": "tech"},
            created_at=datetime(2026, 7, 4, 12, 0, 0),
        )
        self.activity_repo.list_by_application = AsyncMock(return_value=[row])
        self.users_repo.get_all_by_ids = AsyncMock(
            return_value=[self._user(user_id=42, first="Ivan", last="Interviewer")]
        )

        result = await self.service.get_application_activity(
            self.session, self._ctx(user_id=2), 10
        )

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].id, 1)
        self.assertEqual(result[0].event_type, "stage_changed")
        self.assertEqual(result[0].details, {"toStage": "tech"})
        self.assertEqual(result[0].actor_id, 42)
        self.assertEqual(result[0].actor_name, "Ivan Interviewer")

    async def test_get_application_activity_unresolved_actor_falls_back_to_user_id(
        self,
    ):
        job = self._job(job_id=1, owner_ids=(2,))
        application = self._application(application_id=10, job_id=1)
        self.job_repo.get_by_job_id = AsyncMock(return_value=job)
        self.app_repo.get_by_id = AsyncMock(return_value=application)
        row = SimpleNamespace(
            activity_id=1,
            application_id=10,
            actor_id=99,
            event_type="stage_changed",
            details={},
            created_at=datetime(2026, 7, 4, 12, 0, 0),
        )
        self.activity_repo.list_by_application = AsyncMock(return_value=[row])
        self.users_repo.get_all_by_ids = AsyncMock(return_value=[])

        result = await self.service.get_application_activity(
            self.session, self._ctx(user_id=2), 10
        )

        self.assertEqual(result[0].actor_name, "User 99")

    async def test_get_application_activity_resolves_assignee_name_for_stage_changed(
        self,
    ):
        job = self._job(job_id=1, owner_ids=(2,))
        application = self._application(application_id=10, job_id=1)
        self.job_repo.get_by_job_id = AsyncMock(return_value=job)
        self.app_repo.get_by_id = AsyncMock(return_value=application)
        row = SimpleNamespace(
            activity_id=1,
            application_id=10,
            actor_id=2,
            event_type="stage_changed",
            details={
                "fromStage": "recruiter_screening",
                "toStage": "tech",
                "assigneeId": 42,
            },
            created_at=datetime(2026, 7, 4, 12, 0, 0),
        )
        self.activity_repo.list_by_application = AsyncMock(return_value=[row])
        self.users_repo.get_all_by_ids = AsyncMock(
            return_value=[
                self._user(user_id=2, first="Owen", last="Owner"),
                self._user(user_id=42, first="Ivan", last="Interviewer"),
            ]
        )

        result = await self.service.get_application_activity(
            self.session, self._ctx(user_id=2), 10
        )

        self.assertEqual(result[0].details["assigneeName"], "Ivan Interviewer")

    async def test_get_application_activity_resolves_assignee_name_for_round_advanced(
        self,
    ):
        job = self._job(job_id=1, owner_ids=(2,))
        application = self._application(application_id=10, job_id=1)
        self.job_repo.get_by_job_id = AsyncMock(return_value=job)
        self.app_repo.get_by_id = AsyncMock(return_value=application)
        row = SimpleNamespace(
            activity_id=1,
            application_id=10,
            actor_id=2,
            event_type="round_advanced",
            details={"stage": "tech", "fromRound": 1, "toRound": 2, "assigneeId": 42},
            created_at=datetime(2026, 7, 4, 12, 0, 0),
        )
        self.activity_repo.list_by_application = AsyncMock(return_value=[row])
        self.users_repo.get_all_by_ids = AsyncMock(
            return_value=[
                self._user(user_id=2, first="Owen", last="Owner"),
                self._user(user_id=42, first="Ivan", last="Interviewer"),
            ]
        )

        result = await self.service.get_application_activity(
            self.session, self._ctx(user_id=2), 10
        )

        self.assertEqual(result[0].details["assigneeName"], "Ivan Interviewer")

    async def test_get_application_activity_resolves_assignee_name_for_auto_assigned(
        self,
    ):
        job = self._job(job_id=1, owner_ids=(2,))
        application = self._application(application_id=10, job_id=1)
        self.job_repo.get_by_job_id = AsyncMock(return_value=job)
        self.app_repo.get_by_id = AsyncMock(return_value=application)
        row = SimpleNamespace(
            activity_id=1,
            application_id=10,
            actor_id=3,
            event_type="auto_assigned",
            details={"stage": "recruiter_screening", "assigneeId": 42},
            created_at=datetime(2026, 7, 4, 12, 0, 0),
        )
        self.activity_repo.list_by_application = AsyncMock(return_value=[row])
        self.users_repo.get_all_by_ids = AsyncMock(
            return_value=[
                self._user(user_id=3, first="Alice", last="Smith"),
                self._user(user_id=42, first="Ivan", last="Interviewer"),
            ]
        )

        result = await self.service.get_application_activity(
            self.session, self._ctx(user_id=2), 10
        )

        self.assertEqual(result[0].actor_name, "Alice Smith")
        self.assertEqual(result[0].details["assigneeName"], "Ivan Interviewer")

    async def test_get_application_activity_resolves_both_names_for_reassigned(self):
        job = self._job(job_id=1, owner_ids=(2,))
        application = self._application(application_id=10, job_id=1)
        self.job_repo.get_by_job_id = AsyncMock(return_value=job)
        self.app_repo.get_by_id = AsyncMock(return_value=application)
        row = SimpleNamespace(
            activity_id=1,
            application_id=10,
            actor_id=2,
            event_type="reassigned",
            details={
                "stage": "tech",
                "round": 1,
                "fromAssigneeId": 7,
                "toAssigneeId": 42,
            },
            created_at=datetime(2026, 7, 4, 12, 0, 0),
        )
        self.activity_repo.list_by_application = AsyncMock(return_value=[row])
        self.users_repo.get_all_by_ids = AsyncMock(
            return_value=[
                self._user(user_id=2, first="Owen", last="Owner"),
                self._user(user_id=7, first="Eve", last="Evaluator"),
                self._user(user_id=42, first="Ivan", last="Interviewer"),
            ]
        )

        result = await self.service.get_application_activity(
            self.session, self._ctx(user_id=2), 10
        )

        self.assertEqual(result[0].details["fromAssigneeName"], "Eve Evaluator")
        self.assertEqual(result[0].details["toAssigneeName"], "Ivan Interviewer")

    async def test_get_application_activity_reassigned_null_from_assignee_omits_from_name(
        self,
    ):
        job = self._job(job_id=1, owner_ids=(2,))
        application = self._application(application_id=10, job_id=1)
        self.job_repo.get_by_job_id = AsyncMock(return_value=job)
        self.app_repo.get_by_id = AsyncMock(return_value=application)
        row = SimpleNamespace(
            activity_id=1,
            application_id=10,
            actor_id=2,
            event_type="reassigned",
            details={
                "stage": "tech",
                "round": 1,
                "fromAssigneeId": None,
                "toAssigneeId": 42,
            },
            created_at=datetime(2026, 7, 4, 12, 0, 0),
        )
        self.activity_repo.list_by_application = AsyncMock(return_value=[row])
        self.users_repo.get_all_by_ids = AsyncMock(
            return_value=[
                self._user(user_id=2, first="Owen", last="Owner"),
                self._user(user_id=42, first="Ivan", last="Interviewer"),
            ]
        )

        result = await self.service.get_application_activity(
            self.session, self._ctx(user_id=2), 10
        )

        self.assertNotIn("fromAssigneeName", result[0].details)
        self.assertEqual(result[0].details["toAssigneeName"], "Ivan Interviewer")

    async def test_get_application_activity_unresolved_assignee_falls_back_to_user_id(
        self,
    ):
        job = self._job(job_id=1, owner_ids=(2,))
        application = self._application(application_id=10, job_id=1)
        self.job_repo.get_by_job_id = AsyncMock(return_value=job)
        self.app_repo.get_by_id = AsyncMock(return_value=application)
        row = SimpleNamespace(
            activity_id=1,
            application_id=10,
            actor_id=2,
            event_type="stage_changed",
            details={"fromStage": "tech", "toStage": "offer", "assigneeId": 999},
            created_at=datetime(2026, 7, 4, 12, 0, 0),
        )
        self.activity_repo.list_by_application = AsyncMock(return_value=[row])
        self.users_repo.get_all_by_ids = AsyncMock(
            return_value=[self._user(user_id=2, first="Owen", last="Owner")]
        )

        result = await self.service.get_application_activity(
            self.session, self._ctx(user_id=2), 10
        )

        self.assertEqual(result[0].details["assigneeName"], "User 999")

    async def test_get_application_activity_does_not_mutate_stored_row_details(self):
        job = self._job(job_id=1, owner_ids=(2,))
        application = self._application(application_id=10, job_id=1)
        self.job_repo.get_by_job_id = AsyncMock(return_value=job)
        self.app_repo.get_by_id = AsyncMock(return_value=application)
        original_details = {
            "fromStage": "recruiter_screening",
            "toStage": "tech",
            "assigneeId": 42,
        }
        row = SimpleNamespace(
            activity_id=1,
            application_id=10,
            actor_id=2,
            event_type="stage_changed",
            details=original_details,
            created_at=datetime(2026, 7, 4, 12, 0, 0),
        )
        self.activity_repo.list_by_application = AsyncMock(return_value=[row])
        self.users_repo.get_all_by_ids = AsyncMock(
            return_value=[
                self._user(user_id=2, first="Owen", last="Owner"),
                self._user(user_id=42, first="Ivan", last="Interviewer"),
            ]
        )

        await self.service.get_application_activity(
            self.session, self._ctx(user_id=2), 10
        )

        self.assertNotIn("assigneeName", original_details)
        self.assertEqual(
            original_details,
            {
                "fromStage": "recruiter_screening",
                "toStage": "tech",
                "assigneeId": 42,
            },
        )

    async def test_activity_resolves_screen_rule_label(self):
        job = self._job(job_id=1, owner_ids=(2,))
        job.screen_rules = {
            "rules": [
                {
                    "id": "r1",
                    "condition": {
                        "source": "email_domain",
                        "operator": "not_in",
                        "value": ["google.com"],
                    },
                    "action": "reject",
                }
            ]
        }
        application = self._application(application_id=10, job_id=1)
        self.job_repo.get_by_job_id = AsyncMock(return_value=job)
        self.app_repo.get_by_id = AsyncMock(return_value=application)
        row = SimpleNamespace(
            activity_id=1,
            application_id=10,
            actor_id=2,
            event_type="auto_rejected",
            details={"reason": "screen_rule", "ruleId": "r1"},
            created_at=datetime(2026, 7, 4, 12, 0, 0),
        )
        self.activity_repo.list_by_application = AsyncMock(return_value=[row])
        self.users_repo.get_all_by_ids = AsyncMock(
            return_value=[self._user(user_id=2, first="Owen", last="Owner")]
        )

        result = await self.service.get_application_activity(
            self.session, self._ctx(user_id=2), 10
        )

        self.assertEqual(
            result[0].details["ruleLabel"], "email domain not in google.com"
        )

    async def test_activity_screen_rule_label_falls_back_when_rule_removed(self):
        job = self._job(job_id=1, owner_ids=(2,))
        job.screen_rules = {"rules": []}
        application = self._application(application_id=10, job_id=1)
        self.job_repo.get_by_job_id = AsyncMock(return_value=job)
        self.app_repo.get_by_id = AsyncMock(return_value=application)
        row = SimpleNamespace(
            activity_id=1,
            application_id=10,
            actor_id=2,
            event_type="auto_rejected",
            details={"reason": "screen_rule", "ruleId": "r9"},
            created_at=datetime(2026, 7, 4, 12, 0, 0),
        )
        self.activity_repo.list_by_application = AsyncMock(return_value=[row])
        self.users_repo.get_all_by_ids = AsyncMock(
            return_value=[self._user(user_id=2, first="Owen", last="Owner")]
        )

        result = await self.service.get_application_activity(
            self.session, self._ctx(user_id=2), 10
        )

        self.assertEqual(
            result[0].details["ruleLabel"], "rule r9 (no longer configured)"
        )

    async def test_activity_resolves_qualify_and_auto_hire_labels(self):
        job = self._job(job_id=1, owner_ids=(2,))
        job.screen_rules = {
            "rules": [
                {
                    "id": "r1",
                    "condition": {
                        "source": "answer",
                        "questionId": "q_role",
                        "operator": "equals",
                        "value": "mentor",
                    },
                    "action": "qualify",
                }
            ]
        }
        application = self._application(application_id=10, job_id=1)
        self.job_repo.get_by_job_id = AsyncMock(return_value=job)
        self.app_repo.get_by_id = AsyncMock(return_value=application)
        row = SimpleNamespace(
            activity_id=1,
            application_id=10,
            actor_id=2,
            event_type="application_submitted",
            details={
                "stage": "recruiter_screening",
                "screenQualifyRuleId": "r1",
            },
            created_at=datetime(2026, 7, 4, 12, 0, 0),
        )
        self.activity_repo.list_by_application = AsyncMock(return_value=[row])
        self.users_repo.get_all_by_ids = AsyncMock(
            return_value=[self._user(user_id=2, first="Owen", last="Owner")]
        )

        result = await self.service.get_application_activity(
            self.session, self._ctx(user_id=2), 10
        )

        self.assertEqual(
            result[0].details["screenQualifyRuleLabel"],
            "answer to q_role equals mentor",
        )

    async def test_activity_resolves_auto_hire_label(self):
        job = self._job(job_id=1, owner_ids=(2,))
        job.screen_rules = {
            "rules": [
                {
                    "id": "r2",
                    "condition": {
                        "source": "answer",
                        "questionId": "q_experience",
                        "operator": "equals",
                        "value": "senior",
                    },
                    "action": "auto_hire",
                }
            ]
        }
        application = self._application(application_id=10, job_id=1)
        self.job_repo.get_by_job_id = AsyncMock(return_value=job)
        self.app_repo.get_by_id = AsyncMock(return_value=application)
        row = SimpleNamespace(
            activity_id=1,
            application_id=10,
            actor_id=2,
            event_type="application_submitted",
            details={
                "stage": "hired",
                "screenAutoHireRuleId": "r2",
            },
            created_at=datetime(2026, 7, 4, 12, 0, 0),
        )
        self.activity_repo.list_by_application = AsyncMock(return_value=[row])
        self.users_repo.get_all_by_ids = AsyncMock(
            return_value=[self._user(user_id=2, first="Owen", last="Owner")]
        )

        result = await self.service.get_application_activity(
            self.session, self._ctx(user_id=2), 10
        )

        self.assertEqual(
            result[0].details["screenAutoHireRuleLabel"],
            "answer to q_experience equals senior",
        )

    async def test_get_application_activity_non_owner_gets_collapsed_not_found_message(
        self,
    ):
        job = self._job(job_id=1, owner_ids=(2,))
        application = self._application(application_id=10, job_id=1)
        self.job_repo.get_by_job_id = AsyncMock(return_value=job)
        self.app_repo.get_by_id = AsyncMock(return_value=application)

        with self.assertRaises(ValueError):
            await self.service.get_application_activity(
                self.session, self._ctx(user_id=99), 10
            )

        self.activity_repo.list_by_application.assert_not_awaited()

    async def test_get_application_activity_assignee_who_is_not_owner_still_raises(
        self,
    ):
        """Timeline is owner-only, unlike get_application_detail/get_resume —
        the current-stage assignee alone must not be able to read it."""
        job = self._job(job_id=1, owner_ids=(2,))
        application = self._application(application_id=10, job_id=1)
        self.job_repo.get_by_job_id = AsyncMock(return_value=job)
        self.app_repo.get_by_id = AsyncMock(return_value=application)
        self.assignment_repo.get.return_value = ApplicationAssignmentEntity(
            application_id=10,
            stage=application.stage,
            round=1,
            assignee_id=99,
            assigned_by=2,
        )

        with self.assertRaises(ValueError):
            await self.service.get_application_activity(
                self.session, self._ctx(user_id=99), 10
            )

    # -- list_comments / add_comment --

    async def test_list_comments_returns_dtos_with_resolved_author_names(self):
        job = self._job(job_id=1, owner_ids=(2,))
        application = self._application(application_id=10, job_id=1)
        self.job_repo.get_by_job_id = AsyncMock(return_value=job)
        self.app_repo.get_by_id = AsyncMock(return_value=application)
        row = SimpleNamespace(
            comment_id=1,
            application_id=10,
            author_id=42,
            body="Looks strong.",
            created_at=datetime(2026, 7, 7, 12, 0, 0),
        )
        self.comment_repo.list_by_application = AsyncMock(return_value=[row])
        self.users_repo.get_all_by_ids = AsyncMock(
            return_value=[self._user(user_id=42, first="Ivan", last="Interviewer")]
        )

        result = await self.service.list_comments(
            self.session, self._ctx(user_id=2), 10
        )

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].id, 1)
        self.assertEqual(result[0].body, "Looks strong.")
        self.assertEqual(result[0].author_id, 42)
        self.assertEqual(result[0].author_name, "Ivan Interviewer")

    async def test_list_comments_unresolved_author_falls_back_to_user_id(self):
        job = self._job(job_id=1, owner_ids=(2,))
        application = self._application(application_id=10, job_id=1)
        self.job_repo.get_by_job_id = AsyncMock(return_value=job)
        self.app_repo.get_by_id = AsyncMock(return_value=application)
        row = SimpleNamespace(
            comment_id=1,
            application_id=10,
            author_id=99,
            body="Hi.",
            created_at=datetime(2026, 7, 7, 12, 0, 0),
        )
        self.comment_repo.list_by_application = AsyncMock(return_value=[row])
        self.users_repo.get_all_by_ids = AsyncMock(return_value=[])

        result = await self.service.list_comments(
            self.session, self._ctx(user_id=2), 10
        )

        self.assertEqual(result[0].author_name, "User 99")

    async def test_list_comments_succeeds_for_current_stage_assignee(self):
        """Unlike get_application_activity, the current-stage assignee (not
        just the owner) can read comments -- same access as
        get_application_detail."""
        job = self._job(job_id=1, owner_ids=(9,))
        application = self._application(
            application_id=10,
            job_id=1,
            stage=ApplicationStage.RECRUITER_SCREENING,
        )
        self.job_repo.get_by_job_id = AsyncMock(return_value=job)
        self.app_repo.get_by_id = AsyncMock(return_value=application)
        self.assignment_repo.get.return_value = MagicMock(assignee_id=2)
        self.comment_repo.list_by_application = AsyncMock(return_value=[])

        result = await self.service.list_comments(
            self.session, self._ctx(user_id=2), 10
        )

        self.assertEqual(result, [])

    async def test_list_comments_non_owner_non_assignee_gets_collapsed_not_found_message(
        self,
    ):
        job = self._job(job_id=1, owner_ids=(2,))
        application = self._application(application_id=10, job_id=1)
        self.job_repo.get_by_job_id = AsyncMock(return_value=job)
        self.app_repo.get_by_id = AsyncMock(return_value=application)
        self.assignment_repo.get.return_value = None

        with self.assertRaises(ValueError) as ctx:
            await self.service.list_comments(self.session, self._ctx(user_id=99), 10)
        self.assertEqual(str(ctx.exception), "application 10 not found")
        self.comment_repo.list_by_application.assert_not_awaited()

    async def test_add_comment_persists_and_returns_dto_with_authors_own_name(self):
        job = self._job(job_id=1, owner_ids=(2,))
        application = self._application(application_id=10, job_id=1)
        self.job_repo.get_by_job_id = AsyncMock(return_value=job)
        self.app_repo.get_by_id = AsyncMock(return_value=application)
        created_row = SimpleNamespace(
            comment_id=5,
            application_id=10,
            author_id=2,
            body="Great candidate.",
            created_at=datetime(2026, 7, 7, 12, 0, 0),
        )
        self.comment_repo.create = AsyncMock(return_value=created_row)
        self.users_repo.get_user_by_user_id = AsyncMock(
            return_value=self._user(user_id=2, first="Owen", last="Owner")
        )

        dto = CommentCreateDto(body="Great candidate.")
        result = await self.service.add_comment(
            self.session, self._ctx(user_id=2), 10, dto
        )

        self.comment_repo.create.assert_awaited_once_with(
            self.session, 10, 2, "Great candidate."
        )
        self.assertEqual(result.id, 5)
        self.assertEqual(result.body, "Great candidate.")
        self.assertEqual(result.author_id, 2)
        self.assertEqual(result.author_name, "Owen Owner")
        self.session.commit.assert_awaited_once()

    async def test_add_comment_succeeds_for_current_stage_assignee(self):
        job = self._job(job_id=1, owner_ids=(9,))
        application = self._application(
            application_id=10,
            job_id=1,
            stage=ApplicationStage.RECRUITER_SCREENING,
        )
        self.job_repo.get_by_job_id = AsyncMock(return_value=job)
        self.app_repo.get_by_id = AsyncMock(return_value=application)
        self.assignment_repo.get.return_value = MagicMock(assignee_id=2)
        created_row = SimpleNamespace(
            comment_id=5,
            application_id=10,
            author_id=2,
            body="On it.",
            created_at=datetime(2026, 7, 7, 12, 0, 0),
        )
        self.comment_repo.create = AsyncMock(return_value=created_row)
        self.users_repo.get_user_by_user_id = AsyncMock(
            return_value=self._user(user_id=2, first="Eve", last="Evaluator")
        )

        dto = CommentCreateDto(body="On it.")
        result = await self.service.add_comment(
            self.session, self._ctx(user_id=2), 10, dto
        )

        self.assertEqual(result.author_name, "Eve Evaluator")

    async def test_add_comment_non_owner_non_assignee_gets_collapsed_not_found_message(
        self,
    ):
        job = self._job(job_id=1, owner_ids=(2,))
        application = self._application(application_id=10, job_id=1)
        self.job_repo.get_by_job_id = AsyncMock(return_value=job)
        self.app_repo.get_by_id = AsyncMock(return_value=application)
        self.assignment_repo.get.return_value = None

        dto = CommentCreateDto(body="Sneaking in.")
        with self.assertRaises(ValueError) as ctx:
            await self.service.add_comment(self.session, self._ctx(user_id=99), 10, dto)
        self.assertEqual(str(ctx.exception), "application 10 not found")
        self.comment_repo.create.assert_not_awaited()

    async def test_add_comment_valid_mention_creates_row_and_keeps_token(self):
        job = self._job(job_id=1, owner_ids=(2,))
        application = self._application(application_id=10, job_id=1)
        self.job_repo.get_by_job_id = AsyncMock(return_value=job)
        self.app_repo.get_by_id = AsyncMock(return_value=application)
        self.assignment_repo.get.return_value = MagicMock(assignee_id=7)
        created_row = SimpleNamespace(
            comment_id=5,
            application_id=10,
            author_id=2,
            body="ping @[7]",
            created_at=datetime(2026, 7, 7, 12, 0, 0),
        )
        self.comment_repo.create = AsyncMock(return_value=created_row)
        self.users_repo.get_user_by_user_id = AsyncMock(
            return_value=self._user(user_id=2, first="Owen", last="Owner")
        )
        self.users_repo.get_all_by_ids = AsyncMock(
            return_value=[self._user(user_id=7, first="Eve", last="Evaluator")]
        )

        dto = CommentCreateDto(body="ping @[7]")
        result = await self.service.add_comment(
            self.session, self._ctx(user_id=2), 10, dto
        )

        self.comment_repo.create.assert_awaited_once_with(
            self.session, 10, 2, "ping @[7]"
        )
        self.comment_mention_repo.create_mentions.assert_awaited_once_with(
            self.session, 5, [7]
        )
        self.assertEqual(len(result.mentions), 1)
        self.assertEqual(result.mentions[0].user_id, 7)
        self.assertEqual(result.mentions[0].name, "Eve Evaluator")

    async def test_add_comment_mention_of_unauthorized_id_is_stripped(self):
        job = self._job(job_id=1, owner_ids=(2,))
        application = self._application(application_id=10, job_id=1)
        self.job_repo.get_by_job_id = AsyncMock(return_value=job)
        self.app_repo.get_by_id = AsyncMock(return_value=application)
        self.assignment_repo.get.return_value = None
        created_row = SimpleNamespace(
            comment_id=5,
            application_id=10,
            author_id=2,
            body="ping ",
            created_at=datetime(2026, 7, 7, 12, 0, 0),
        )
        self.comment_repo.create = AsyncMock(return_value=created_row)
        self.users_repo.get_user_by_user_id = AsyncMock(
            return_value=self._user(user_id=2, first="Owen", last="Owner")
        )

        dto = CommentCreateDto(body="ping @[999]")
        result = await self.service.add_comment(
            self.session, self._ctx(user_id=2), 10, dto
        )

        self.comment_repo.create.assert_awaited_once_with(self.session, 10, 2, "ping ")
        self.comment_mention_repo.create_mentions.assert_not_awaited()
        self.assertEqual(result.mentions, [])

    async def test_add_comment_body_that_is_only_an_invalid_mention_is_rejected(self):
        job = self._job(job_id=1, owner_ids=(2,))
        application = self._application(application_id=10, job_id=1)
        self.job_repo.get_by_job_id = AsyncMock(return_value=job)
        self.app_repo.get_by_id = AsyncMock(return_value=application)
        self.assignment_repo.get.return_value = None

        dto = CommentCreateDto(body="@[999]")
        with self.assertRaises(ValueError) as ctx:
            await self.service.add_comment(self.session, self._ctx(user_id=2), 10, dto)

        self.assertEqual(str(ctx.exception), "comment text is required")
        self.comment_repo.create.assert_not_awaited()
        self.comment_mention_repo.create_mentions.assert_not_awaited()

    async def test_add_comment_duplicate_mention_of_same_user_creates_one_row(self):
        job = self._job(job_id=1, owner_ids=(2,))
        application = self._application(application_id=10, job_id=1)
        self.job_repo.get_by_job_id = AsyncMock(return_value=job)
        self.app_repo.get_by_id = AsyncMock(return_value=application)
        self.assignment_repo.get.return_value = None
        created_row = SimpleNamespace(
            comment_id=5,
            application_id=10,
            author_id=2,
            body="@[2] and @[2] again",
            created_at=datetime(2026, 7, 7, 12, 0, 0),
        )
        self.comment_repo.create = AsyncMock(return_value=created_row)
        self.users_repo.get_user_by_user_id = AsyncMock(
            return_value=self._user(user_id=2, first="Owen", last="Owner")
        )
        self.users_repo.get_all_by_ids = AsyncMock(
            return_value=[self._user(user_id=2, first="Owen", last="Owner")]
        )

        dto = CommentCreateDto(body="@[2] and @[2] again")
        result = await self.service.add_comment(
            self.session, self._ctx(user_id=2), 10, dto
        )

        self.comment_mention_repo.create_mentions.assert_awaited_once_with(
            self.session, 5, [2]
        )
        self.assertEqual(len(result.mentions), 1)

    async def test_add_comment_no_mention_syntax_behaves_as_before(self):
        """Regression: a plain comment is untouched by the mention parser."""
        job = self._job(job_id=1, owner_ids=(2,))
        application = self._application(application_id=10, job_id=1)
        self.job_repo.get_by_job_id = AsyncMock(return_value=job)
        self.app_repo.get_by_id = AsyncMock(return_value=application)
        self.assignment_repo.get.return_value = None
        created_row = SimpleNamespace(
            comment_id=5,
            application_id=10,
            author_id=2,
            body="Great candidate.",
            created_at=datetime(2026, 7, 7, 12, 0, 0),
        )
        self.comment_repo.create = AsyncMock(return_value=created_row)
        self.users_repo.get_user_by_user_id = AsyncMock(
            return_value=self._user(user_id=2, first="Owen", last="Owner")
        )

        dto = CommentCreateDto(body="Great candidate.")
        result = await self.service.add_comment(
            self.session, self._ctx(user_id=2), 10, dto
        )

        self.comment_mention_repo.create_mentions.assert_not_awaited()
        self.assertEqual(result.mentions, [])

    async def test_add_comment_notifies_each_mentioned_user(self):
        job = self._job(job_id=1, owner_ids=(9, 7))
        application = self._application(
            application_id=10, job_id=1, stage=ApplicationStage.RECRUITER_SCREENING
        )
        self.job_repo.get_by_job_id = AsyncMock(return_value=job)
        self.app_repo.get_by_id = AsyncMock(return_value=application)
        self.assignment_repo.get = AsyncMock(return_value=None)
        comment_row = MagicMock(
            comment_id=100,
            application_id=10,
            author_id=9,
            body="hi @[7]",
            created_at=datetime(2026, 7, 7, 12, 0, 0),
        )
        self.comment_repo.create = AsyncMock(return_value=comment_row)
        self.users_repo.get_user_by_user_id = AsyncMock(
            return_value=self._user(user_id=9)
        )

        dto = CommentCreateDto(body="hi @[7]")
        await self.service.add_comment(self.session, self._ctx(user_id=9), 10, dto)

        self.notification_repo.create.assert_awaited_once()
        (_session_arg, entity_arg), _ = self.notification_repo.create.call_args
        self.assertEqual(entity_arg.user_id, 7)
        self.assertEqual(entity_arg.type, NotificationType.MENTIONED)
        self.assertEqual(entity_arg.application_id, 10)
        self.assertEqual(entity_arg.comment_id, 100)
        self.assertEqual(entity_arg.actor_user_id, 9)

    async def test_add_comment_skips_self_mention(self):
        job = self._job(job_id=1, owner_ids=(9,))
        application = self._application(
            application_id=10, job_id=1, stage=ApplicationStage.RECRUITER_SCREENING
        )
        self.job_repo.get_by_job_id = AsyncMock(return_value=job)
        self.app_repo.get_by_id = AsyncMock(return_value=application)
        self.assignment_repo.get = AsyncMock(return_value=None)
        comment_row = MagicMock(
            comment_id=100,
            application_id=10,
            author_id=9,
            body="hi @[9]",
            created_at=datetime(2026, 7, 7, 12, 0, 0),
        )
        self.comment_repo.create = AsyncMock(return_value=comment_row)
        self.users_repo.get_user_by_user_id = AsyncMock(
            return_value=self._user(user_id=9)
        )

        dto = CommentCreateDto(body="hi @[9]")
        await self.service.add_comment(self.session, self._ctx(user_id=9), 10, dto)

        self.notification_repo.create.assert_not_awaited()

    async def test_list_comments_includes_resolved_mentions(self):
        job = self._job(job_id=1, owner_ids=(2,))
        application = self._application(application_id=10, job_id=1)
        self.job_repo.get_by_job_id = AsyncMock(return_value=job)
        self.app_repo.get_by_id = AsyncMock(return_value=application)
        row = SimpleNamespace(
            comment_id=1,
            application_id=10,
            author_id=42,
            body="cc @[7]",
            created_at=datetime(2026, 7, 7, 12, 0, 0),
        )
        self.comment_repo.list_by_application = AsyncMock(return_value=[row])
        self.comment_mention_repo.get_by_comment_ids = AsyncMock(
            return_value=[SimpleNamespace(comment_id=1, mentioned_user_id=7)]
        )
        self.users_repo.get_all_by_ids = AsyncMock(
            return_value=[
                self._user(user_id=42, first="Ivan", last="Interviewer"),
                self._user(user_id=7, first="Eve", last="Evaluator"),
            ]
        )

        result = await self.service.list_comments(
            self.session, self._ctx(user_id=2), 10
        )

        self.assertEqual(len(result[0].mentions), 1)
        self.assertEqual(result[0].mentions[0].user_id, 7)
        self.assertEqual(result[0].mentions[0].name, "Eve Evaluator")

    # -- list_mentionable_users --

    async def test_list_mentionable_users_returns_owners_and_current_assignee(self):
        job = self._job(job_id=1, owner_ids=(2, 3))
        application = self._application(application_id=10, job_id=1)
        self.job_repo.get_by_job_id = AsyncMock(return_value=job)
        self.app_repo.get_by_id = AsyncMock(return_value=application)
        self.assignment_repo.get.return_value = MagicMock(assignee_id=7)
        self.users_repo.get_all_by_ids = AsyncMock(
            return_value=[
                self._user(user_id=2, first="Owen", last="Owner"),
                self._user(user_id=3, first="Ozzy", last="Owner"),
                self._user(user_id=7, first="Eve", last="Evaluator"),
            ]
        )

        result = await self.service.list_mentionable_users(
            self.session, self._ctx(user_id=2), 10
        )

        self.assertEqual({u.user_id for u in result}, {2, 3, 7})

    async def test_list_mentionable_users_no_assignee_returns_owners_only(self):
        job = self._job(job_id=1, owner_ids=(2,))
        application = self._application(application_id=10, job_id=1)
        self.job_repo.get_by_job_id = AsyncMock(return_value=job)
        self.app_repo.get_by_id = AsyncMock(return_value=application)
        self.assignment_repo.get.return_value = None
        self.users_repo.get_all_by_ids = AsyncMock(
            return_value=[self._user(user_id=2, first="Owen", last="Owner")]
        )

        result = await self.service.list_mentionable_users(
            self.session, self._ctx(user_id=2), 10
        )

        self.assertEqual({u.user_id for u in result}, {2})

    async def test_list_mentionable_users_non_owner_non_assignee_gets_collapsed_not_found_message(
        self,
    ):
        job = self._job(job_id=1, owner_ids=(2,))
        application = self._application(application_id=10, job_id=1)
        self.job_repo.get_by_job_id = AsyncMock(return_value=job)
        self.app_repo.get_by_id = AsyncMock(return_value=application)
        self.assignment_repo.get.return_value = None

        with self.assertRaises(ValueError) as ctx:
            await self.service.list_mentionable_users(
                self.session, self._ctx(user_id=99), 10
            )
        self.assertEqual(str(ctx.exception), "application 10 not found")

    async def test_list_comments_succeeds_for_read_all_non_owner_non_assignee(self):
        job = self._job(job_id=1, owner_ids=(9,))
        application = self._application(
            application_id=10, job_id=1, stage=ApplicationStage.RECRUITER_SCREENING
        )
        self.job_repo.get_by_job_id = AsyncMock(return_value=job)
        self.app_repo.get_by_id = AsyncMock(return_value=application)
        self.assignment_repo.get.return_value = None
        self.comment_repo.list_by_application = AsyncMock(return_value=[])
        ctx = UserContextDto(
            sub="s",
            primary_email="hr@b.com",
            user_id=2,
            permissions=frozenset({Permission.RECRUITING_APPLICATION_READ_ALL}),
        )

        result = await self.service.list_comments(self.session, ctx, 10)

        self.assertEqual(result, [])

    async def test_add_comment_succeeds_for_read_all_non_owner_non_assignee(self):
        job = self._job(job_id=1, owner_ids=(9,))
        application = self._application(
            application_id=10, job_id=1, stage=ApplicationStage.RECRUITER_SCREENING
        )
        self.job_repo.get_by_job_id = AsyncMock(return_value=job)
        self.app_repo.get_by_id = AsyncMock(return_value=application)
        self.assignment_repo.get.return_value = None
        created_row = SimpleNamespace(
            comment_id=5,
            application_id=10,
            author_id=2,
            body="On it.",
            created_at=datetime(2026, 7, 7, 12, 0, 0),
        )
        self.comment_repo.create = AsyncMock(return_value=created_row)
        self.users_repo.get_user_by_user_id = AsyncMock(
            return_value=self._user(user_id=2, first="Hank", last="HR")
        )
        ctx = UserContextDto(
            sub="s",
            primary_email="hr@b.com",
            user_id=2,
            permissions=frozenset({Permission.RECRUITING_APPLICATION_READ_ALL}),
        )

        dto = CommentCreateDto(body="On it.")
        result = await self.service.add_comment(self.session, ctx, 10, dto)

        self.assertEqual(result.author_name, "Hank HR")

    async def test_list_mentionable_users_succeeds_for_read_all_non_owner_non_assignee(
        self,
    ):
        job = self._job(job_id=1, owner_ids=(9,))
        application = self._application(application_id=10, job_id=1)
        self.job_repo.get_by_job_id = AsyncMock(return_value=job)
        self.app_repo.get_by_id = AsyncMock(return_value=application)
        self.assignment_repo.get.return_value = None
        self.users_repo.get_all_by_ids = AsyncMock(
            return_value=[self._user(user_id=9, first="Owen", last="Owner")]
        )
        ctx = UserContextDto(
            sub="s",
            primary_email="hr@b.com",
            user_id=2,
            permissions=frozenset({Permission.RECRUITING_APPLICATION_READ_ALL}),
        )

        result = await self.service.list_mentionable_users(self.session, ctx, 10)

        self.assertEqual({u.user_id for u in result}, {9})

    async def test_get_application_activity_succeeds_for_read_all_non_owner(self):
        job = self._job(job_id=1, owner_ids=(9,))
        application = self._application(application_id=10, job_id=1, user_id=3)
        self.app_repo.get_by_id = AsyncMock(return_value=application)
        self.job_repo.get_by_job_id = AsyncMock(return_value=job)
        self.users_repo.get_all_by_ids = AsyncMock(return_value=[])
        self.activity_repo.list_by_application.return_value = []
        ctx = UserContextDto(
            sub="s",
            primary_email="hr@b.com",
            user_id=2,
            permissions=frozenset({Permission.RECRUITING_APPLICATION_READ_ALL}),
        )

        result = await self.service.get_application_activity(self.session, ctx, 10)

        self.assertEqual(result, [])
        self.activity_repo.list_by_application.assert_awaited_once_with(
            self.session, 10
        )

    # -- get_other_applications --

    async def test_get_other_applications_returns_every_sibling_application(self):
        entry_job = self._job(job_id=1, owner_ids=(2,))
        other_job = self._job(job_id=2, owner_ids=(9,))
        entry_app = self._application(
            application_id=10,
            job_id=1,
            user_id=3,
        )
        other_app = self._application(
            application_id=11,
            job_id=2,
            user_id=3,
            stage=ApplicationStage.TECH,
        )
        self.app_repo.get_by_id = AsyncMock(return_value=entry_app)
        self.job_repo.get_by_job_id = AsyncMock(return_value=entry_job)
        self.assignment_repo.get.return_value = None
        self.app_repo.list_by_user = AsyncMock(
            return_value=[(entry_app, entry_job), (other_app, other_job)]
        )
        self.sub_repo.get_current = AsyncMock(return_value=None)
        self.evaluation_repo.list_by_application.return_value = []

        result = await self.service.get_other_applications(
            self.session, self._ctx(user_id=2), 10
        )

        self.assertEqual(len(result.other_jobs), 1)
        self.assertEqual(result.other_jobs[0].application.id, 11)
        self.assertEqual(result.other_jobs[0].job_title, "Job 2")
        self.app_repo.list_by_user.assert_awaited_once_with(self.session, 3)

    async def test_get_other_applications_routes_same_job_prior_attempt_to_history(
        self,
    ):
        """A prior rejected attempt on the SAME job is history for the
        detail page, not the cross-posting panel — it must never appear in
        ``other_jobs`` even though list_by_user returns every attempt ever
        made. It surfaces instead in ``previous_same_job``."""
        entry_job = self._job(job_id=1, owner_ids=(2,))
        other_job = self._job(job_id=2, owner_ids=(9,))
        rejected_same_job = self._application(
            application_id=9,
            job_id=1,
            user_id=3,
            stage=ApplicationStage.REJECTED,
        )
        entry_app = self._application(
            application_id=10,
            job_id=1,
            user_id=3,
        )
        other_app = self._application(
            application_id=11,
            job_id=2,
            user_id=3,
            stage=ApplicationStage.TECH,
        )
        self.app_repo.get_by_id = AsyncMock(return_value=entry_app)
        self.job_repo.get_by_job_id = AsyncMock(return_value=entry_job)
        self.assignment_repo.get.return_value = None
        self.app_repo.list_by_user = AsyncMock(
            return_value=[
                (rejected_same_job, entry_job),
                (entry_app, entry_job),
                (other_app, other_job),
            ]
        )
        self.sub_repo.get_current = AsyncMock(return_value=None)
        self.evaluation_repo.list_by_application.return_value = []

        result = await self.service.get_other_applications(
            self.session, self._ctx(user_id=2), 10
        )

        self.assertEqual([r.application.id for r in result.other_jobs], [11])
        self.assertEqual([r.application.id for r in result.previous_same_job], [9])

    async def test_aggregate_splits_same_job_history_from_other_jobs(self):
        """Candidate rows: current app (job A), one prior rejected attempt
        (job A), one application to job B — the current application must
        appear in neither list."""
        entry_job = self._job(job_id=1, owner_ids=(2,))
        other_job = self._job(job_id=2, owner_ids=(9,))
        prior_a = self._application(
            application_id=9,
            job_id=1,
            user_id=3,
            stage=ApplicationStage.REJECTED,
        )
        entry_app = self._application(application_id=10, job_id=1, user_id=3)
        app_b = self._application(
            application_id=11,
            job_id=2,
            user_id=3,
            stage=ApplicationStage.TECH,
        )
        self.app_repo.get_by_id = AsyncMock(return_value=entry_app)
        self.job_repo.get_by_job_id = AsyncMock(return_value=entry_job)
        self.assignment_repo.get.return_value = None
        self.app_repo.list_by_user = AsyncMock(
            return_value=[
                (prior_a, entry_job),
                (entry_app, entry_job),
                (app_b, other_job),
            ]
        )
        self.sub_repo.get_current = AsyncMock(return_value=None)
        self.evaluation_repo.list_by_application.return_value = []

        result = await self.service.get_other_applications(
            self.session, self._ctx(user_id=2), 10
        )

        self.assertEqual(
            [o.application.id for o in result.previous_same_job],
            [prior_a.application_id],
        )
        self.assertEqual(
            [o.application.id for o in result.other_jobs],
            [app_b.application_id],
        )

    async def test_same_job_history_is_newest_first(self):
        """Two prior rejected attempts on job A come back newest
        (higher application_id) first."""
        entry_job = self._job(job_id=1, owner_ids=(2,))
        entry_app = self._application(application_id=10, job_id=1, user_id=3)
        prior_older = self._application(
            application_id=7,
            job_id=1,
            user_id=3,
            stage=ApplicationStage.REJECTED,
        )
        prior_newer = self._application(
            application_id=9,
            job_id=1,
            user_id=3,
            stage=ApplicationStage.REJECTED,
        )
        self.app_repo.get_by_id = AsyncMock(return_value=entry_app)
        self.job_repo.get_by_job_id = AsyncMock(return_value=entry_job)
        self.assignment_repo.get.return_value = None
        self.app_repo.list_by_user = AsyncMock(
            return_value=[
                (prior_older, entry_job),
                (entry_app, entry_job),
                (prior_newer, entry_job),
            ]
        )
        self.sub_repo.get_current = AsyncMock(return_value=None)
        self.evaluation_repo.list_by_application.return_value = []

        result = await self.service.get_other_applications(
            self.session, self._ctx(user_id=2), 10
        )

        self.assertEqual(
            [o.application.id for o in result.previous_same_job],
            [9, 7],
        )

    async def test_get_other_applications_includes_evaluations_and_resume_flag(self):
        entry_job = self._job(job_id=1, owner_ids=(2,))
        other_job = self._job(job_id=2, owner_ids=(9,))
        entry_app = self._application(application_id=10, job_id=1, user_id=3)
        other_app = self._application(
            application_id=11,
            job_id=2,
            user_id=3,
            stage=ApplicationStage.TECH,
        )
        other_sub = ApplicationSubmissionEntity(
            application_id=11,
            version=1,
            submission={"answers": {"q1": "yes"}},
            resume_object_key="resumes/xyz.pdf",
        )
        other_eval = EvaluationEntity(
            application_id=11,
            stage=ApplicationStage.TECH,
            round=1,
            evaluator_id=7,
            responses={"overall": {"value": 5}},
            is_confirmed=True,
        )
        other_eval.evaluation_id = 900
        self.app_repo.get_by_id = AsyncMock(return_value=entry_app)
        self.job_repo.get_by_job_id = AsyncMock(return_value=entry_job)
        self.assignment_repo.get.return_value = None
        self.app_repo.list_by_user = AsyncMock(
            return_value=[(entry_app, entry_job), (other_app, other_job)]
        )
        self.sub_repo.get_current = AsyncMock(return_value=other_sub)
        self.evaluation_repo.list_by_application.return_value = [other_eval]

        result = await self.service.get_other_applications(
            self.session, self._ctx(user_id=2), 10
        )

        self.assertTrue(result.other_jobs[0].resume_available)
        self.assertEqual(len(result.other_jobs[0].evaluations), 1)
        self.assertEqual(result.other_jobs[0].evaluations[0].id, 900)

    async def test_get_other_applications_raises_when_caller_lacks_entry_gate(self):
        entry_job = self._job(job_id=1, owner_ids=(9,))
        entry_app = self._application(application_id=10, job_id=1, user_id=3)
        self.app_repo.get_by_id = AsyncMock(return_value=entry_app)
        self.job_repo.get_by_job_id = AsyncMock(return_value=entry_job)
        self.assignment_repo.get.return_value = None

        with self.assertRaises(ValueError):
            await self.service.get_other_applications(
                self.session, self._ctx(user_id=2), 10
            )

        self.app_repo.list_by_user.assert_not_called()


if __name__ == "__main__":
    unittest.main()
