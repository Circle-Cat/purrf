import unittest
from unittest.mock import AsyncMock, MagicMock

from backend.recruiting.board_service import BoardService
from backend.recruiting.recruiting_mapper import RecruitingMapper
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
        self.session = AsyncMock()
        self.service = BoardService(
            self.job_repo,
            self.app_repo,
            self.sub_repo,
            self.users_repo,
            RecruitingMapper(),
        )

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

        with self.assertRaises(ValueError):
            await self.service.get_application_detail(
                self.session, self._ctx(user_id=2), 999
            )

    async def test_get_application_detail_raises_for_non_owner(self):
        job = self._job(job_id=1, owner_ids=(9,))
        application = self._application(application_id=10, job_id=1, user_id=3)
        self.app_repo.get_by_id = AsyncMock(return_value=application)
        self.job_repo.get_by_job_id = AsyncMock(return_value=job)

        with self.assertRaises(ValueError):
            await self.service.get_application_detail(
                self.session, self._ctx(user_id=2), 10
            )


if __name__ == "__main__":
    unittest.main()
