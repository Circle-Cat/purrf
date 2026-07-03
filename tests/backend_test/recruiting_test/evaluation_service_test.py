import unittest
from unittest.mock import AsyncMock, MagicMock

from backend.recruiting.evaluation_service import EvaluationService
from backend.recruiting.recruiting_mapper import RecruitingMapper
from backend.dto.evaluation_dto import EvaluationSubmitDto
from backend.dto.user_context_dto import UserContextDto
from backend.entity.application_assignment_entity import ApplicationAssignmentEntity
from backend.entity.application_entity import ApplicationEntity
from backend.entity.evaluation_entity import EvaluationEntity
from backend.entity.job_entity import JobEntity
from backend.entity.users_entity import UsersEntity
from backend.common.recruiting_enums import ApplicationStage, JobKind, JobStatus

# A fully-answered RECRUITER_SCREENING rubric (see evaluation_rubric.RUBRICS):
# every field required on confirm, in the shape validate_responses expects.
COMPLETE_RECRUITER_SCREENING_RESPONSES = {
    "bg_match": {"value": True},
    "bg_consistency": {"value": True},
    "bg_strength": {"value": 4, "notes": "Strong background"},
    "format_compliance": {"value": True},
    "mission_alignment": {"value": True},
    "writing_quality": {"value": 5, "notes": "Excellent writing"},
    "overall": {"value": 5, "notes": "Advance"},
}

# Intentionally missing every field but one — valid as a draft
# (require_complete=False only shape-checks present fields).
INCOMPLETE_RECRUITER_SCREENING_RESPONSES = {
    "bg_match": {"value": True},
}


class TestEvaluationService(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.app_repo = MagicMock()
        self.assignment_repo = MagicMock()
        self.evaluation_repo = MagicMock()
        self.job_repo = MagicMock()
        self.users_repo = MagicMock()
        self.session = AsyncMock()
        self.service = EvaluationService(
            self.app_repo,
            self.assignment_repo,
            self.evaluation_repo,
            self.job_repo,
            self.users_repo,
            RecruitingMapper(),
        )

    def _job(self, job_id=1, title="Job 1"):
        job = JobEntity(kind=JobKind.ACTIVITY, title=title, status=JobStatus.PUBLISHED)
        job.job_id = job_id
        return job

    def _user(self, user_id=3, first="A", last="B", email="a@b.com"):
        u = UsersEntity(first_name=first, last_name=last, primary_email=email)
        u.user_id = user_id
        return u

    def _application(
        self,
        application_id=10,
        job_id=1,
        user_id=3,
        stage=ApplicationStage.RECRUITER_SCREENING,
        sub_status="pending",
    ):
        app = ApplicationEntity(
            job_id=job_id,
            user_id=user_id,
            stage=stage,
            sub_status=sub_status,
        )
        app.application_id = application_id
        return app

    def _ctx(self, user_id=2):
        return UserContextDto(sub="s", primary_email="eval@b.com", user_id=user_id)

    def _assignment(
        self,
        application_id=10,
        stage=ApplicationStage.RECRUITER_SCREENING,
        assignee_id=2,
        assigned_by=1,
    ):
        a = ApplicationAssignmentEntity(
            application_id=application_id,
            stage=stage,
            assignee_id=assignee_id,
            assigned_by=assigned_by,
        )
        a.assignment_id = 100
        return a

    def _evaluation(
        self,
        evaluation_id=200,
        application_id=10,
        stage=ApplicationStage.RECRUITER_SCREENING,
        evaluator_id=2,
        responses=None,
        is_confirmed=False,
        confirmed_at=None,
    ):
        e = EvaluationEntity(
            application_id=application_id,
            stage=stage,
            evaluator_id=evaluator_id,
            responses=responses or {},
        )
        e.evaluation_id = evaluation_id
        e.is_confirmed = is_confirmed
        e.confirmed_at = confirmed_at
        return e

    # -- submit --

    async def test_submit_draft_with_incomplete_rubric_succeeds_without_touching_sub_status(
        self,
    ):
        application = self._application(sub_status="pending")
        assignment = self._assignment(assignee_id=2)
        draft_row = self._evaluation(
            responses=INCOMPLETE_RECRUITER_SCREENING_RESPONSES, is_confirmed=False
        )
        self.app_repo.get_by_id = AsyncMock(return_value=application)
        self.assignment_repo.get = AsyncMock(return_value=assignment)
        self.evaluation_repo.upsert_draft = AsyncMock(return_value=draft_row)
        self.evaluation_repo.confirm = AsyncMock()
        self.app_repo.update = AsyncMock()

        dto = EvaluationSubmitDto(
            responses=INCOMPLETE_RECRUITER_SCREENING_RESPONSES, confirm=False
        )
        result = await self.service.submit(
            self.session, self._ctx(user_id=2), 10, dto
        )

        self.assertFalse(result.is_confirmed)
        self.evaluation_repo.upsert_draft.assert_awaited_once_with(
            self.session,
            10,
            ApplicationStage.RECRUITER_SCREENING,
            2,
            INCOMPLETE_RECRUITER_SCREENING_RESPONSES,
        )
        self.evaluation_repo.confirm.assert_not_awaited()
        self.app_repo.update.assert_not_awaited()
        self.assertEqual(application.sub_status, "pending")
        self.session.commit.assert_awaited_once()

    async def test_submit_confirm_with_complete_rubric_locks_row_and_sets_sub_status(
        self,
    ):
        application = self._application(sub_status="pending")
        assignment = self._assignment(assignee_id=2)
        draft_row = self._evaluation(
            responses=COMPLETE_RECRUITER_SCREENING_RESPONSES, is_confirmed=False
        )
        confirmed_row = self._evaluation(
            responses=COMPLETE_RECRUITER_SCREENING_RESPONSES, is_confirmed=True
        )
        self.app_repo.get_by_id = AsyncMock(return_value=application)
        self.assignment_repo.get = AsyncMock(return_value=assignment)
        self.evaluation_repo.upsert_draft = AsyncMock(return_value=draft_row)
        self.evaluation_repo.confirm = AsyncMock(return_value=confirmed_row)
        self.app_repo.update = AsyncMock(side_effect=lambda session, entity: entity)

        dto = EvaluationSubmitDto(
            responses=COMPLETE_RECRUITER_SCREENING_RESPONSES, confirm=True
        )
        result = await self.service.submit(
            self.session, self._ctx(user_id=2), 10, dto
        )

        self.assertTrue(result.is_confirmed)
        self.evaluation_repo.confirm.assert_awaited_once()
        confirm_call_args = self.evaluation_repo.confirm.await_args.args
        self.assertIs(confirm_call_args[0], self.session)
        self.assertIs(confirm_call_args[1], draft_row)
        self.assertEqual(application.sub_status, "evaluated")
        self.app_repo.update.assert_awaited_once_with(self.session, application)
        self.session.commit.assert_awaited_once()

    async def test_submit_confirm_with_incomplete_rubric_raises_without_persisting(self):
        application = self._application(sub_status="pending")
        assignment = self._assignment(assignee_id=2)
        self.app_repo.get_by_id = AsyncMock(return_value=application)
        self.assignment_repo.get = AsyncMock(return_value=assignment)
        self.evaluation_repo.upsert_draft = AsyncMock()
        self.app_repo.update = AsyncMock()

        dto = EvaluationSubmitDto(
            responses=INCOMPLETE_RECRUITER_SCREENING_RESPONSES, confirm=True
        )
        with self.assertRaises(ValueError):
            await self.service.submit(self.session, self._ctx(user_id=2), 10, dto)

        self.evaluation_repo.upsert_draft.assert_not_awaited()
        self.app_repo.update.assert_not_awaited()
        self.session.commit.assert_not_awaited()

    async def test_submit_by_non_assignee_raises(self):
        application = self._application(sub_status="pending")
        assignment = self._assignment(assignee_id=42)  # not the caller
        self.app_repo.get_by_id = AsyncMock(return_value=application)
        self.assignment_repo.get = AsyncMock(return_value=assignment)
        self.evaluation_repo.upsert_draft = AsyncMock()

        dto = EvaluationSubmitDto(
            responses=INCOMPLETE_RECRUITER_SCREENING_RESPONSES, confirm=False
        )
        with self.assertRaisesRegex(ValueError, "not the assignee"):
            await self.service.submit(self.session, self._ctx(user_id=2), 10, dto)

        self.evaluation_repo.upsert_draft.assert_not_awaited()
        self.session.commit.assert_not_awaited()

    async def test_submit_with_no_assignment_at_all_raises(self):
        application = self._application(sub_status="pending")
        self.app_repo.get_by_id = AsyncMock(return_value=application)
        self.assignment_repo.get = AsyncMock(return_value=None)
        self.evaluation_repo.upsert_draft = AsyncMock()

        dto = EvaluationSubmitDto(
            responses=INCOMPLETE_RECRUITER_SCREENING_RESPONSES, confirm=False
        )
        with self.assertRaisesRegex(ValueError, "not the assignee"):
            await self.service.submit(self.session, self._ctx(user_id=2), 10, dto)

        self.evaluation_repo.upsert_draft.assert_not_awaited()

    async def test_submit_on_already_confirmed_row_raises(self):
        application = self._application(sub_status="evaluated")
        assignment = self._assignment(assignee_id=2)
        self.app_repo.get_by_id = AsyncMock(return_value=application)
        self.assignment_repo.get = AsyncMock(return_value=assignment)
        self.evaluation_repo.upsert_draft = AsyncMock(
            side_effect=ValueError(
                "this evaluation is already confirmed and cannot be edited"
            )
        )
        self.app_repo.update = AsyncMock()

        dto = EvaluationSubmitDto(
            responses=INCOMPLETE_RECRUITER_SCREENING_RESPONSES, confirm=False
        )
        with self.assertRaisesRegex(ValueError, "already confirmed"):
            await self.service.submit(self.session, self._ctx(user_id=2), 10, dto)

        self.app_repo.update.assert_not_awaited()
        self.session.commit.assert_not_awaited()

    async def test_submit_missing_application_raises(self):
        self.app_repo.get_by_id = AsyncMock(return_value=None)

        dto = EvaluationSubmitDto(
            responses=INCOMPLETE_RECRUITER_SCREENING_RESPONSES, confirm=False
        )
        with self.assertRaises(ValueError):
            await self.service.submit(self.session, self._ctx(user_id=2), 999, dto)

    # -- get_mine --

    async def test_get_mine_reflects_is_confirmed_per_assignment(self):
        assignment_no_eval = self._assignment(
            application_id=10, stage=ApplicationStage.RECRUITER_SCREENING, assignee_id=2
        )
        assignment_confirmed = self._assignment(
            application_id=11, stage=ApplicationStage.TECH, assignee_id=2
        )
        self.assignment_repo.list_by_assignee = AsyncMock(
            return_value=[assignment_no_eval, assignment_confirmed]
        )

        app10 = self._application(
            application_id=10, job_id=1, user_id=3, stage=ApplicationStage.RECRUITER_SCREENING
        )
        app11 = self._application(
            application_id=11, job_id=1, user_id=3, stage=ApplicationStage.TECH
        )

        async def get_by_id(session, application_id, **kwargs):
            return {10: app10, 11: app11}[application_id]

        self.app_repo.get_by_id = AsyncMock(side_effect=get_by_id)
        self.job_repo.get_by_job_id = AsyncMock(return_value=self._job(job_id=1, title="Engineer"))
        self.users_repo.get_user_by_user_id = AsyncMock(
            return_value=self._user(user_id=3, first="C", last="D")
        )

        confirmed_row = self._evaluation(
            application_id=11, stage=ApplicationStage.TECH, evaluator_id=2, is_confirmed=True
        )

        async def get_evaluation(session, application_id, stage, evaluator_id):
            if application_id == 11:
                return confirmed_row
            return None

        self.evaluation_repo.get = AsyncMock(side_effect=get_evaluation)

        result = await self.service.get_mine(self.session, self._ctx(user_id=2))

        self.assertEqual(len(result), 2)
        by_app = {r.application_id: r for r in result}
        self.assertFalse(by_app[10].is_confirmed)
        self.assertTrue(by_app[11].is_confirmed)
        self.assertEqual(by_app[10].job_title, "Engineer")
        self.assertEqual(by_app[10].applicant_name, "C D")
        self.assertEqual(by_app[10].stage, ApplicationStage.RECRUITER_SCREENING)
        self.assertEqual(by_app[11].stage, ApplicationStage.TECH)


if __name__ == "__main__":
    unittest.main()
