import unittest
from http import HTTPStatus
from unittest.mock import AsyncMock, MagicMock, patch

from backend.dto.job_review_dto import JobReviewDecisionDto, JobSubmitDto
from backend.dto.user_context_dto import UserContextDto
from backend.recruiting.recruiting_controller import RecruitingController


class TestRecruitingController(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.service = MagicMock()
        self.service.list_all_jobs = AsyncMock(return_value=[])
        self.service.submit_for_review = AsyncMock(return_value="submitted")
        self.service.approve = AsyncMock(return_value="approved")
        self.service.reject = AsyncMock(return_value="rejected")
        self.service.list_active_approvers = AsyncMock(return_value=[])
        self.service.list_reviews_for_reviewer = AsyncMock(return_value=[])
        self.service.reopen_job = AsyncMock(return_value="reopened")

        self.session = AsyncMock()
        self.database = MagicMock()
        self.database.session.return_value.__aenter__.return_value = self.session
        self.database.session.return_value.__aexit__.return_value = None

        self.controller = RecruitingController(
            job_service=self.service, database=self.database
        )

        self.patcher = patch("backend.recruiting.recruiting_controller.api_response")
        self.mock_api_response = self.patcher.start()
        self.mock_api_response.side_effect = (
            lambda message, data=None, status_code=HTTPStatus.OK, success=True: {
                "message": message,
                "data": data,
            }
        )
        self.addCleanup(self.patcher.stop)

        self.user = UserContextDto(sub="s", primary_email="me@x.com", user_id=42)

    async def test_list_jobs_uses_list_all(self):
        await self.controller.list_jobs(current_user=self.user)
        self.service.list_all_jobs.assert_awaited_once_with(self.session)

    async def test_submit_passes_current_user_as_submitter(self):
        body = JobSubmitDto(reviewer_id=7, message="please")
        await self.controller.submit_job(
            current_user=self.user, job_id=3, submit_data=body
        )
        self.service.submit_for_review.assert_awaited_once_with(
            self.session, 3, 7, 42, "please"
        )

    async def test_list_approvers(self):
        await self.controller.list_approvers(current_user=self.user)
        self.service.list_active_approvers.assert_awaited_once_with(self.session)

    async def test_review_decision_approve_dispatches(self):
        body = JobReviewDecisionDto(decision="approve")
        await self.controller.review_decision(
            current_user=self.user, review_id=5, decision_data=body
        )
        self.service.approve.assert_awaited_once_with(self.session, 5)
        self.service.reject.assert_not_awaited()

    async def test_review_decision_reject_dispatches_with_comment(self):
        body = JobReviewDecisionDto(decision="reject", comment="fix it")
        await self.controller.review_decision(
            current_user=self.user, review_id=5, decision_data=body
        )
        self.service.reject.assert_awaited_once_with(self.session, 5, "fix it")
        self.service.approve.assert_not_awaited()

    async def test_my_reviews_uses_current_user(self):
        await self.controller.list_my_reviews(current_user=self.user)
        self.service.list_reviews_for_reviewer.assert_awaited_once_with(
            self.session, 42
        )

    async def test_reopen(self):
        await self.controller.reopen_job(current_user=self.user, job_id=8)
        self.service.reopen_job.assert_awaited_once_with(self.session, 8)


if __name__ == "__main__":
    unittest.main()
