import unittest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, call

from backend.recruiting.board_service import BoardService
from backend.recruiting.recruiting_mapper import RecruitingMapper
from backend.dto.board_dto import (
    REJECT_REASONS,
    BlacklistDto,
    ReassignDto,
    RoundChangeDto,
    StageChangeDto,
    SubStatusChangeDto,
)
from backend.dto.user_context_dto import UserContextDto
from backend.entity.application_assignment_entity import ApplicationAssignmentEntity
from backend.entity.application_entity import ApplicationEntity
from backend.entity.application_submission_entity import ApplicationSubmissionEntity
from backend.entity.job_entity import JobEntity
from backend.entity.users_entity import UsersEntity
from backend.common.recruiting_enums import ApplicationStage, JobKind, JobStatus


class TestBoardService(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.job_repo = MagicMock()
        self.app_repo = MagicMock()
        self.sub_repo = MagicMock()
        self.users_repo = MagicMock()
        self.users_repo.get_all_by_ids = AsyncMock(return_value=[])
        self.resume_storage = MagicMock()
        self.assignment_repo = MagicMock()
        self.assignment_repo.upsert = AsyncMock()
        self.assignment_repo.list_by_application_ids = AsyncMock(return_value=[])
        self.user_permissions_repo = MagicMock()
        self.session = AsyncMock()
        self.service = BoardService(
            self.job_repo,
            self.app_repo,
            self.sub_repo,
            self.users_repo,
            RecruitingMapper(),
            self.resume_storage,
            self.assignment_repo,
            self.user_permissions_repo,
        )
        # Default persistence mocks: echo the entity back, like SQLAlchemy's
        # merge-and-flush does when nothing else stubs them out.
        self.app_repo.update = AsyncMock(side_effect=lambda session, entity: entity)
        self.sub_repo.update = AsyncMock(side_effect=lambda session, entity: entity)

    def _job(
        self,
        job_id=1,
        owner_ids=(2,),
        stages=("recruiter_screening", "tech"),
        rounds=None,
        default_assignees=None,
    ):
        job = JobEntity(
            kind=JobKind.ACTIVITY,
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
        job = self._job(job_id=1, owner_ids=(2,), stages=("offer",))
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
        self.assignment_repo.get = AsyncMock(return_value=None)
        self.users_repo.get_user_by_user_id = AsyncMock(return_value=applicant)
        self.sub_repo.get_current = AsyncMock(return_value=current_sub)

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
        self.assignment_repo.get = AsyncMock(return_value=None)
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
        self.assignment_repo.get = AsyncMock(return_value=None)

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
        self.assignment_repo.get = AsyncMock(return_value=assignment)
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
            [call(self.session, 10, ApplicationStage.RECRUITER_SCREENING)] * 2
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
        self.assignment_repo.get = AsyncMock(return_value=assignment)

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
        self.assignment_repo.get = AsyncMock(return_value=assignment)
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
        self.assignment_repo.get = AsyncMock(return_value=assignment)
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
        self.assignment_repo.get = AsyncMock(return_value=assignment)
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
        self.assignment_repo.get = AsyncMock(return_value=None)
        self.users_repo.get_user_by_user_id = AsyncMock(return_value=applicant)
        self.sub_repo.get_current = AsyncMock(return_value=None)

        result = await self.service.get_application_detail(
            self.session, self._ctx(user_id=2), 10
        )

        self.assertTrue(result.is_owner)
        self.assertIsNone(result.assignee_id)

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

    async def test_get_resume_raises_for_non_owner_with_collapsed_message(self):
        job = self._job(job_id=1, owner_ids=(9,))
        application = self._application(application_id=10, job_id=1, user_id=3)
        self.app_repo.get_by_id = AsyncMock(return_value=application)
        self.job_repo.get_by_job_id = AsyncMock(return_value=job)

        with self.assertRaises(ValueError) as ctx:
            await self.service.get_resume(self.session, self._ctx(user_id=2), 10)
        self.assertEqual(str(ctx.exception), "application 10 not found")

    async def test_get_resume_raises_when_no_resume_on_file(self):
        job = self._job(job_id=1, owner_ids=(2,))
        application = self._application(application_id=10, job_id=1, user_id=3)
        self.app_repo.get_by_id = AsyncMock(return_value=application)
        self.job_repo.get_by_job_id = AsyncMock(return_value=job)
        self.sub_repo.get_current = AsyncMock(return_value=None)

        with self.assertRaises(ValueError) as ctx:
            await self.service.get_resume(self.session, self._ctx(user_id=2), 10)
        self.assertEqual(str(ctx.exception), "no resume on file for application 10")
        self.resume_storage.get.assert_not_called()

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

    async def test_change_stage_last_stage_to_hired_clears_sub_status(self):
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
        self.assignment_repo.get = AsyncMock(return_value=assignment)

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
        job = self._job(job_id=1, owner_ids=(2,), stages=("tech",))
        application = self._application(
            application_id=10, job_id=1, stage=ApplicationStage.TECH
        )
        self.job_repo.get_by_job_id = AsyncMock(return_value=job)
        self.app_repo.get_by_id = AsyncMock(return_value=application)
        self.sub_repo.get_current = AsyncMock(return_value=None)

        dto = StageChangeDto(to_stage=ApplicationStage.HIRED)
        await self.service.change_stage(self.session, self._ctx(user_id=2), 10, dto)

        self.app_repo.get_by_id.assert_awaited_once_with(
            self.session, 10, for_update=True
        )

    async def test_change_stage_to_interview_stage_requires_assignee_id(self):
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
        with self.assertRaisesRegex(ValueError, "assignee"):
            await self.service.change_stage(self.session, self._ctx(user_id=2), 10, dto)

        self.assignment_repo.upsert.assert_not_awaited()
        self.app_repo.update.assert_not_awaited()
        self.session.commit.assert_not_awaited()

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

    async def test_change_stage_to_hired_ignores_assignee_id(self):
        job = self._job(job_id=1, owner_ids=(2,), stages=("tech",))
        application = self._application(
            application_id=10, job_id=1, stage=ApplicationStage.TECH
        )
        self.job_repo.get_by_job_id = AsyncMock(return_value=job)
        self.app_repo.get_by_id = AsyncMock(return_value=application)
        self.sub_repo.get_current = AsyncMock(return_value=None)

        dto = StageChangeDto(to_stage=ApplicationStage.HIRED)  # no assignee_id
        await self.service.change_stage(self.session, self._ctx(user_id=2), 10, dto)

        self.assignment_repo.upsert.assert_not_awaited()
        self.user_permissions_repo.get_active_users_with_permission.assert_not_called()

    # -- reassign --

    async def test_reassign_updates_assignment_and_resets_sub_status(self):
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

        self.assertEqual(result.sub_status, "pending")
        self.assignment_repo.upsert.assert_awaited_once_with(
            self.session, 10, ApplicationStage.TECH, 1, 42, 2
        )
        self.app_repo.update.assert_awaited_once()
        self.session.commit.assert_awaited_once()

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

    async def test_set_round_to_interview_stage_requires_assignee_id(self):
        job = self._job(job_id=1, owner_ids=(2,), stages=("tech",), rounds={"tech": 2})
        application = self._application(
            application_id=10, job_id=1, stage=ApplicationStage.TECH
        )
        self.job_repo.get_by_job_id = AsyncMock(return_value=job)
        self.app_repo.get_by_id = AsyncMock(return_value=application)
        self.sub_repo.get_current = AsyncMock(return_value=None)

        dto = RoundChangeDto(round=2)  # no assignee_id
        with self.assertRaisesRegex(ValueError, "assignee"):
            await self.service.set_round(self.session, self._ctx(user_id=2), 10, dto)

        self.assignment_repo.upsert.assert_not_awaited()
        self.app_repo.update.assert_not_awaited()
        self.session.commit.assert_not_awaited()

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

    async def test_set_round_on_non_interview_stage_ignores_missing_assignee(self):
        job = self._job(
            job_id=1, owner_ids=(2,), stages=("offer",), rounds={"offer": 2}
        )
        application = self._application(
            application_id=10, job_id=1, stage=ApplicationStage.OFFER
        )
        self.job_repo.get_by_job_id = AsyncMock(return_value=job)
        self.app_repo.get_by_id = AsyncMock(return_value=application)
        self.sub_repo.get_current = AsyncMock(return_value=None)

        dto = RoundChangeDto(round=2)  # no assignee_id — offer isn't assignable
        result = await self.service.set_round(
            self.session, self._ctx(user_id=2), 10, dto
        )

        self.assertEqual(result.current_round, 2)
        self.assignment_repo.upsert.assert_not_awaited()
        self.user_permissions_repo.get_active_users_with_permission.assert_not_called()


if __name__ == "__main__":
    unittest.main()
