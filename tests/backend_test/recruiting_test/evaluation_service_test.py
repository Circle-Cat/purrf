import unittest
from unittest.mock import AsyncMock, MagicMock, create_autospec

from backend.recruiting.evaluation_service import EvaluationService
from backend.dto.evaluation_dto import EvaluationSubmitDto
from backend.dto.user_context_dto import UserContextDto
from backend.entity.application_assignment_entity import ApplicationAssignmentEntity
from backend.entity.application_entity import ApplicationEntity
from backend.entity.evaluation_entity import EvaluationEntity
from backend.entity.job_entity import JobEntity
from backend.entity.users_entity import UsersEntity
from backend.common.recruiting_enums import ApplicationStage, JobKind, JobStatus
from backend.common.permissions import Permission
from backend.repository.application_activity_repository import (
    ApplicationActivityRepository,
)
from backend.repository.application_assignment_repository import (
    ApplicationAssignmentRepository,
)
from backend.repository.evaluation_repository import EvaluationRepository

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
        # autospec (not a bare MagicMock) so a caller/repo signature drift
        # (e.g. a new required param) fails the test instead of silently
        # accepting any arity.
        self.assignment_repo = create_autospec(
            ApplicationAssignmentRepository, instance=True
        )
        self.evaluation_repo = create_autospec(EvaluationRepository, instance=True)
        self.job_repo = MagicMock()
        self.users_repo = MagicMock()
        self.activity_repo = create_autospec(
            ApplicationActivityRepository, instance=True
        )
        self.session = AsyncMock()
        self.service = EvaluationService(
            self.app_repo,
            self.assignment_repo,
            self.evaluation_repo,
            self.job_repo,
            self.users_repo,
            self.activity_repo,
        )

    def _job(self, job_id=1, title="Job 1", owner_ids=None):
        job = JobEntity(kind=JobKind.ACTIVITY, title=title, status=JobStatus.PUBLISHED)
        job.job_id = job_id
        if owner_ids is not None:
            job.pipeline_config = {"ownerIds": list(owner_ids)}
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
        current_round=1,
    ):
        app = ApplicationEntity(
            job_id=job_id,
            user_id=user_id,
            stage=stage,
            sub_status=sub_status,
            current_round=current_round,
        )
        app.application_id = application_id
        return app

    def _ctx(self, user_id=2):
        return UserContextDto(sub="s", primary_email="eval@b.com", user_id=user_id)

    def _assignment(
        self,
        application_id=10,
        stage=ApplicationStage.RECRUITER_SCREENING,
        round=1,
        assignee_id=2,
        assigned_by=1,
    ):
        a = ApplicationAssignmentEntity(
            application_id=application_id,
            stage=stage,
            round=round,
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
        round=1,
        evaluator_id=2,
        responses=None,
        is_confirmed=False,
        confirmed_at=None,
    ):
        e = EvaluationEntity(
            application_id=application_id,
            stage=stage,
            round=round,
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
        self.assignment_repo.get.return_value = assignment
        self.evaluation_repo.upsert_draft.return_value = draft_row
        self.app_repo.update = AsyncMock()

        dto = EvaluationSubmitDto(
            responses=INCOMPLETE_RECRUITER_SCREENING_RESPONSES, confirm=False
        )
        result = await self.service.submit(self.session, self._ctx(user_id=2), 10, dto)

        self.assertFalse(result.is_confirmed)
        self.evaluation_repo.upsert_draft.assert_awaited_once_with(
            self.session,
            10,
            ApplicationStage.RECRUITER_SCREENING,
            1,
            2,
            INCOMPLETE_RECRUITER_SCREENING_RESPONSES,
        )
        self.evaluation_repo.confirm.assert_not_awaited()
        self.app_repo.update.assert_not_awaited()
        self.assertEqual(application.sub_status, "pending")
        self.session.commit.assert_awaited_once()
        self.activity_repo.create.assert_not_awaited()

    async def test_submit_on_round_two_scopes_the_key_to_that_round(self):
        """Confirming round 1 must not affect round 2: the evaluation key
        includes the application's current_round, not just stage."""
        application = self._application(
            stage=ApplicationStage.TECH, current_round=2, sub_status="pending"
        )
        assignment = self._assignment(
            stage=ApplicationStage.TECH, round=2, assignee_id=2
        )
        draft_row = self._evaluation(
            stage=ApplicationStage.TECH, round=2, responses={"rating": 5}
        )
        self.app_repo.get_by_id = AsyncMock(return_value=application)
        self.assignment_repo.get.return_value = assignment
        self.evaluation_repo.upsert_draft.return_value = draft_row

        dto = EvaluationSubmitDto(responses={"rating": 5}, confirm=False)
        result = await self.service.submit(self.session, self._ctx(user_id=2), 10, dto)

        self.assertEqual(result.round, 2)
        self.evaluation_repo.upsert_draft.assert_awaited_once_with(
            self.session,
            10,
            ApplicationStage.TECH,
            2,
            2,
            {"rating": 5},
        )

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
        self.assignment_repo.get.return_value = assignment
        self.evaluation_repo.upsert_draft.return_value = draft_row
        self.evaluation_repo.confirm.return_value = confirmed_row
        self.app_repo.update = AsyncMock(side_effect=lambda session, entity: entity)

        dto = EvaluationSubmitDto(
            responses=COMPLETE_RECRUITER_SCREENING_RESPONSES, confirm=True
        )
        result = await self.service.submit(self.session, self._ctx(user_id=2), 10, dto)

        self.assertTrue(result.is_confirmed)
        self.evaluation_repo.confirm.assert_awaited_once()
        confirm_call_args = self.evaluation_repo.confirm.await_args.args
        self.assertIs(confirm_call_args[0], self.session)
        self.assertIs(confirm_call_args[1], draft_row)
        self.assertEqual(application.sub_status, "evaluated")
        self.app_repo.update.assert_awaited_once_with(self.session, application)
        self.session.commit.assert_awaited_once()
        self.activity_repo.create.assert_awaited_once_with(
            self.session,
            10,
            2,
            "evaluation_confirmed",
            details={"stage": ApplicationStage.RECRUITER_SCREENING.value, "round": 1},
        )

    async def test_submit_confirm_with_incomplete_rubric_raises_without_persisting(
        self,
    ):
        application = self._application(sub_status="pending")
        assignment = self._assignment(assignee_id=2)
        self.app_repo.get_by_id = AsyncMock(return_value=application)
        self.assignment_repo.get.return_value = assignment
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
        self.assignment_repo.get.return_value = assignment

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
        self.assignment_repo.get.return_value = None

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
        self.assignment_repo.get.return_value = assignment
        self.evaluation_repo.upsert_draft.side_effect = ValueError(
            "this evaluation is already confirmed and cannot be edited"
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
            application_id=10,
            job_id=1,
            user_id=3,
            stage=ApplicationStage.RECRUITER_SCREENING,
        )
        app11 = self._application(
            application_id=11, job_id=1, user_id=3, stage=ApplicationStage.TECH
        )

        async def get_by_id(session, application_id, **kwargs):
            return {10: app10, 11: app11}[application_id]

        self.app_repo.get_by_id = AsyncMock(side_effect=get_by_id)
        self.job_repo.get_by_job_id = AsyncMock(
            return_value=self._job(job_id=1, title="Engineer")
        )
        self.users_repo.get_user_by_user_id = AsyncMock(
            return_value=self._user(user_id=3, first="C", last="D")
        )

        confirmed_row = self._evaluation(
            application_id=11,
            stage=ApplicationStage.TECH,
            evaluator_id=2,
            is_confirmed=True,
        )

        async def get_evaluation(session, application_id, stage, round, evaluator_id):
            if application_id == 11:
                return confirmed_row
            return None

        self.evaluation_repo.get.side_effect = get_evaluation

        result = await self.service.get_mine(self.session, self._ctx(user_id=2))

        self.assertEqual(len(result), 2)
        by_app = {r.application_id: r for r in result}
        self.assertFalse(by_app[10].is_confirmed)
        self.assertTrue(by_app[11].is_confirmed)
        self.assertEqual(by_app[10].job_title, "Engineer")
        self.assertEqual(by_app[10].applicant_name, "C D")
        self.assertEqual(by_app[10].stage, ApplicationStage.RECRUITER_SCREENING)
        self.assertEqual(by_app[11].stage, ApplicationStage.TECH)
        self.assertTrue(by_app[10].is_current)
        self.assertTrue(by_app[11].is_current)

    async def test_get_mine_returns_distinct_rows_for_two_rounds_of_same_application(
        self,
    ):
        """The same evaluator assigned to two rounds of one multi-round stage
        must appear as two distinct rows (round-scoped), not collapse into
        one duplicate-keyed entry."""
        round1 = self._assignment(
            application_id=10, stage=ApplicationStage.TECH, round=1, assignee_id=2
        )
        round2 = self._assignment(
            application_id=10, stage=ApplicationStage.TECH, round=2, assignee_id=2
        )
        self.assignment_repo.list_by_assignee = AsyncMock(return_value=[round1, round2])
        app = self._application(
            application_id=10, stage=ApplicationStage.TECH, current_round=2
        )
        self.app_repo.get_by_id = AsyncMock(return_value=app)
        self.job_repo.get_by_job_id = AsyncMock(return_value=self._job(job_id=1))
        self.users_repo.get_user_by_user_id = AsyncMock(return_value=self._user())

        confirmed_round1 = self._evaluation(
            application_id=10, stage=ApplicationStage.TECH, round=1, is_confirmed=True
        )

        async def get_evaluation(session, application_id, stage, round, evaluator_id):
            return confirmed_round1 if round == 1 else None

        self.evaluation_repo.get.side_effect = get_evaluation

        result = await self.service.get_mine(self.session, self._ctx(user_id=2))

        self.assertEqual(len(result), 2)
        by_round = {r.round: r for r in result}
        self.assertTrue(by_round[1].is_confirmed)
        self.assertFalse(by_round[2].is_confirmed)
        self.assertFalse(by_round[1].is_current)
        self.assertTrue(by_round[2].is_current)

    async def test_get_mine_excludes_stale_unconfirmed_assignment(self):
        """An assignment whose round the application has since advanced
        past, with no confirmed evaluation, is dropped entirely -- it's
        neither actionable nor a completed record worth keeping."""
        stale = self._assignment(
            application_id=10, stage=ApplicationStage.TECH, round=1, assignee_id=2
        )
        self.assignment_repo.list_by_assignee = AsyncMock(return_value=[stale])
        app = self._application(
            application_id=10, stage=ApplicationStage.TECH, current_round=2
        )
        self.app_repo.get_by_id = AsyncMock(return_value=app)
        self.evaluation_repo.get = AsyncMock(return_value=None)
        self.evaluation_repo.list_by_assignee = AsyncMock(return_value=[])

        result = await self.service.get_mine(self.session, self._ctx(user_id=2))

        self.assertEqual(result, [])

    async def test_get_mine_recovers_confirmed_evaluation_after_reassignment(self):
        """Once reassigned, the outgoing assignee's application_assignment
        row is overwritten and list_by_assignee no longer returns it -- but
        their already-confirmed evaluation row survives independently and
        must still show up, read-only."""
        self.assignment_repo.list_by_assignee = AsyncMock(return_value=[])
        app = self._application(
            application_id=10, stage=ApplicationStage.TECH, current_round=1
        )
        self.app_repo.get_by_id = AsyncMock(return_value=app)
        self.job_repo.get_by_job_id = AsyncMock(
            return_value=self._job(job_id=1, title="Engineer")
        )
        self.users_repo.get_user_by_user_id = AsyncMock(
            return_value=self._user(user_id=3, first="C", last="D")
        )
        confirmed_row = self._evaluation(
            application_id=10,
            stage=ApplicationStage.TECH,
            round=1,
            evaluator_id=2,
            is_confirmed=True,
        )
        self.evaluation_repo.list_by_assignee = AsyncMock(return_value=[confirmed_row])

        result = await self.service.get_mine(self.session, self._ctx(user_id=2))

        self.assertEqual(len(result), 1)
        self.assertFalse(result[0].is_current)
        self.assertTrue(result[0].is_confirmed)
        self.assertEqual(result[0].job_title, "Engineer")
        self.assertEqual(result[0].applicant_name, "C D")

    async def test_get_mine_excludes_unconfirmed_draft_after_reassignment(self):
        self.assignment_repo.list_by_assignee = AsyncMock(return_value=[])
        draft_row = self._evaluation(
            application_id=10,
            stage=ApplicationStage.TECH,
            round=1,
            evaluator_id=2,
            is_confirmed=False,
        )
        self.evaluation_repo.list_by_assignee = AsyncMock(return_value=[draft_row])

        result = await self.service.get_mine(self.session, self._ctx(user_id=2))

        self.assertEqual(result, [])

    async def test_get_mine_does_not_duplicate_a_row_covered_by_both_passes(self):
        """A still-current, already-confirmed assignment must appear once,
        not twice, even though it also matches via
        evaluation_repository.list_by_assignee."""
        current = self._assignment(
            application_id=10, stage=ApplicationStage.TECH, round=1, assignee_id=2
        )
        self.assignment_repo.list_by_assignee = AsyncMock(return_value=[current])
        app = self._application(
            application_id=10, stage=ApplicationStage.TECH, current_round=1
        )
        self.app_repo.get_by_id = AsyncMock(return_value=app)
        self.job_repo.get_by_job_id = AsyncMock(return_value=self._job(job_id=1))
        self.users_repo.get_user_by_user_id = AsyncMock(return_value=self._user())
        confirmed_row = self._evaluation(
            application_id=10,
            stage=ApplicationStage.TECH,
            round=1,
            evaluator_id=2,
            is_confirmed=True,
        )
        self.evaluation_repo.get = AsyncMock(return_value=confirmed_row)
        self.evaluation_repo.list_by_assignee = AsyncMock(return_value=[confirmed_row])

        result = await self.service.get_mine(self.session, self._ctx(user_id=2))

        self.assertEqual(len(result), 1)
        self.assertTrue(result[0].is_current)

    # -- get_for_application --

    async def test_get_for_application_owner_sees_all_rows(self):
        application = self._application(job_id=1, stage=ApplicationStage.TECH)
        job = self._job(job_id=1, owner_ids=(2,))
        rows = [
            self._evaluation(
                evaluation_id=201,
                stage=ApplicationStage.RECRUITER_SCREENING,
                evaluator_id=5,
                is_confirmed=True,
            ),
            self._evaluation(
                evaluation_id=202,
                stage=ApplicationStage.TECH,
                evaluator_id=7,
                is_confirmed=False,
            ),
        ]
        self.app_repo.get_by_id = AsyncMock(return_value=application)
        self.job_repo.get_by_job_id = AsyncMock(return_value=job)
        self.assignment_repo.get.return_value = None
        self.evaluation_repo.list_by_application.return_value = rows

        result = await self.service.get_for_application(
            self.session, self._ctx(user_id=2), 10
        )

        self.assertEqual(len(result), 2)
        self.assertEqual({r.id for r in result}, {201, 202})
        self.evaluation_repo.list_by_application.assert_awaited_once_with(
            self.session, 10
        )

    async def test_get_for_application_current_assignee_sees_rows_including_own_draft(
        self,
    ):
        application = self._application(job_id=1, stage=ApplicationStage.TECH)
        job = self._job(job_id=1, owner_ids=(9,))  # caller is not an owner
        assignment = self._assignment(
            application_id=10, stage=ApplicationStage.TECH, assignee_id=2
        )
        own_draft = self._evaluation(
            evaluation_id=300,
            stage=ApplicationStage.TECH,
            evaluator_id=2,
            is_confirmed=False,
        )
        self.app_repo.get_by_id = AsyncMock(return_value=application)
        self.job_repo.get_by_job_id = AsyncMock(return_value=job)
        self.assignment_repo.get.return_value = assignment
        self.evaluation_repo.list_by_application.return_value = [own_draft]

        result = await self.service.get_for_application(
            self.session, self._ctx(user_id=2), 10
        )

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].id, 300)
        self.assertFalse(result[0].is_confirmed)

    async def test_get_for_application_third_party_raises(self):
        application = self._application(job_id=1, stage=ApplicationStage.TECH)
        job = self._job(job_id=1, owner_ids=(9,))
        self.app_repo.get_by_id = AsyncMock(return_value=application)
        self.job_repo.get_by_job_id = AsyncMock(return_value=job)
        self.assignment_repo.get.return_value = None

        with self.assertRaises(ValueError):
            await self.service.get_for_application(
                self.session, self._ctx(user_id=2), 10
            )

        self.evaluation_repo.list_by_application.assert_not_awaited()

    async def test_get_for_application_missing_application_raises(self):
        self.app_repo.get_by_id = AsyncMock(return_value=None)

        with self.assertRaises(ValueError):
            await self.service.get_for_application(
                self.session, self._ctx(user_id=2), 999
            )

    async def test_get_for_application_succeeds_for_read_all_non_owner(self):
        application = self._application(job_id=1, stage=ApplicationStage.TECH)
        job = self._job(job_id=1, owner_ids=(9,))
        self.app_repo.get_by_id = AsyncMock(return_value=application)
        self.job_repo.get_by_job_id = AsyncMock(return_value=job)
        self.assignment_repo.get.return_value = None
        self.evaluation_repo.list_by_application.return_value = []
        ctx = UserContextDto(
            sub="s",
            primary_email="hr@b.com",
            user_id=2,
            permissions=frozenset({Permission.RECRUITING_APPLICATION_READ_ALL}),
        )

        result = await self.service.get_for_application(self.session, ctx, 10)

        self.assertEqual(result, [])


if __name__ == "__main__":
    unittest.main()
