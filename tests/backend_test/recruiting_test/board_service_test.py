import unittest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

from backend.recruiting.board_service import BoardService
from backend.recruiting.recruiting_mapper import RecruitingMapper
from backend.dto.board_dto import (
    REJECT_REASONS,
    BlacklistDto,
    ReassignDto,
    StageChangeDto,
    SubStatusChangeDto,
)
from backend.dto.user_context_dto import UserContextDto
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
        self.resume_storage = MagicMock()
        self.assignment_repo = MagicMock()
        self.assignment_repo.upsert = AsyncMock()
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

    def _job(self, job_id=1, owner_ids=(2,), stages=("recruiter_screening", "tech")):
        job = JobEntity(
            kind=JobKind.ACTIVITY,
            title=f"Job {job_id}",
            status=JobStatus.PUBLISHED,
        )
        job.job_id = job_id
        job.form_schema = {"questions": [{"id": "q1"}]}
        job.pipeline_config = {
            "ownerIds": list(owner_ids),
            "stages": [{"stage": s} for s in stages],
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
        )
        app.application_id = application_id
        return app

    def _ctx(self, user_id=2):
        return UserContextDto(sub="s", primary_email="owner@b.com", user_id=user_id)

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
        self.assertEqual(result[0].stages, ["recruiter_screening", "tech"])

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

    async def test_get_application_detail_resume_unavailable_without_submission(self):
        job = self._job(job_id=1, owner_ids=(2,))
        application = self._application(application_id=10, job_id=1, user_id=3)
        applicant = self._user(user_id=3)
        self.app_repo.get_by_id = AsyncMock(return_value=application)
        self.job_repo.get_by_job_id = AsyncMock(return_value=job)
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

        with self.assertRaises(ValueError) as ctx:
            await self.service.get_application_detail(
                self.session, self._ctx(user_id=2), 10
            )
        # Same message as the missing-application case: not-owned must be
        # indistinguishable from nonexistent, or authenticated callers could
        # enumerate which application ids exist.
        self.assertEqual(str(ctx.exception), "application 10 not found")

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
            self.session, 10, ApplicationStage.TECH, 42, 2
        )

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

    async def test_change_stage_non_owner_gets_collapsed_not_found_message(self):
        job = self._job(job_id=1, owner_ids=(9,))
        application = self._application(application_id=10, job_id=1)
        self.job_repo.get_by_job_id = AsyncMock(return_value=job)
        self.app_repo.get_by_id = AsyncMock(return_value=application)

        dto = StageChangeDto(to_stage=ApplicationStage.TECH)
        with self.assertRaises(ValueError) as ctx:
            await self.service.change_stage(self.session, self._ctx(user_id=2), 10, dto)
        self.assertEqual(str(ctx.exception), "application 10 not found")

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
            self.session, 10, ApplicationStage.TECH, 42, 2
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
            self.session, 10, ApplicationStage.TECH, 42, 2
        )
        self.app_repo.update.assert_awaited_once()
        self.session.commit.assert_awaited_once()

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


if __name__ == "__main__":
    unittest.main()
