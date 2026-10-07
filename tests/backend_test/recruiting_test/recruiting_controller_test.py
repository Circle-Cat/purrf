import unittest
from http import HTTPStatus
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from backend.common.fast_api_response_wrapper import api_response
from backend.common.permissions import Permission
from backend.common.recruiting_enums import JobKind
from backend.dto.job_dto import JobCreateDto
from backend.dto.job_review_dto import (
    JobReviewDecisionDto,
    JobReviewReassignDto,
    JobSubmitDto,
)
from backend.dto.user_context_dto import UserContextDto
from backend.recruiting.recruiting_controller import RecruitingController


class TestRecruitingController(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.service = MagicMock()
        self.service.list_all_jobs = AsyncMock(return_value=[])
        self.service.submit_for_review = AsyncMock(return_value="submitted")
        self.service.approve = AsyncMock(return_value="approved")
        self.service.reject = AsyncMock(return_value="rejected")
        self.service.reassign_review = AsyncMock(return_value="reassigned")
        self.service.list_active_approvers = AsyncMock(return_value=[])
        self.service.list_reviews_for_reviewer = AsyncMock(return_value=[])
        self.service.request_close = AsyncMock(return_value="close-requested")
        self.service.request_reopen = AsyncMock(return_value="reopen-requested")
        self.service.delete_job = AsyncMock(return_value=None)
        self.service.create_job = AsyncMock(return_value="created")
        self.service.get_job_activity = AsyncMock(return_value=[])

        self.session = AsyncMock()
        self.database = MagicMock()
        self.database.session.return_value.__aenter__.return_value = self.session
        self.database.session.return_value.__aexit__.return_value = None

        self.controller = RecruitingController(
            job_service=self.service,
            database=self.database,
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

    async def test_create_job_passes_current_user_as_creator(self):
        body = JobCreateDto(title="T", kind=JobKind.ACTIVITY)
        await self.controller.create_job(current_user=self.user, job_data=body)
        self.service.create_job.assert_awaited_once_with(self.session, body, 42)

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
        self.service.approve.assert_awaited_once_with(self.session, 5, 42)
        self.service.reject.assert_not_awaited()

    async def test_review_decision_reject_dispatches_with_comment(self):
        body = JobReviewDecisionDto(decision="reject", comment="fix it")
        await self.controller.review_decision(
            current_user=self.user, review_id=5, decision_data=body
        )
        self.service.reject.assert_awaited_once_with(self.session, 5, "fix it", 42)
        self.service.approve.assert_not_awaited()

    async def test_reassign_review_passes_current_user_as_the_actor(self):
        """The caller is the claimed submitter; the service decides if they are.

        Passing it from the token rather than the body is what makes the
        submitter-only rule enforceable at all.
        """
        body = JobReviewReassignDto(reviewer_id=7)
        await self.controller.reassign_review(
            current_user=self.user, job_id=3, reassign_data=body
        )
        self.service.reassign_review.assert_awaited_once_with(
            self.session, 3, acting_user_id=42, reviewer_id=7
        )

    async def test_withdraw_review_passes_current_user_as_the_actor(self):
        """Like reassigning: the token names the claimed submitter, and the
        service decides whether they are."""
        self.service.withdraw_review = AsyncMock(return_value="withdrawn")

        result = await self.controller.withdraw_review(current_user=self.user, job_id=3)

        self.service.withdraw_review.assert_awaited_once_with(
            self.session, 3, acting_user_id=42
        )
        self.assertEqual(result["data"], "withdrawn")

    def test_withdraw_review_route_is_a_post_for_job_writers(self):
        routes_by_path = {route.path: route for route in self.controller.router.routes}
        route = routes_by_path["/recruiting/jobs/{job_id}/review/withdraw"]

        self.assertEqual(route.methods, {"POST"})
        self.assertEqual(
            self._endpoint_permissions(route.endpoint),
            [Permission.RECRUITING_JOB_WRITE],
        )

    async def test_my_reviews_uses_current_user(self):
        await self.controller.list_my_reviews(current_user=self.user)
        self.service.list_reviews_for_reviewer.assert_awaited_once_with(
            self.session, 42
        )

    async def test_request_close_passes_current_user_as_submitter(self):
        body = JobSubmitDto(reviewer_id=7, message="please close")
        await self.controller.request_close(
            current_user=self.user, job_id=3, submit_data=body
        )
        self.service.request_close.assert_awaited_once_with(
            self.session, 3, 7, 42, "please close"
        )

    async def test_request_reopen_passes_current_user_as_submitter(self):
        body = JobSubmitDto(reviewer_id=7, message="please reopen")
        await self.controller.request_reopen(
            current_user=self.user, job_id=4, submit_data=body
        )
        self.service.request_reopen.assert_awaited_once_with(
            self.session, 4, 7, 42, "please reopen"
        )

    async def test_delete_job(self):
        await self.controller.delete_job(current_user=self.user, job_id=9)
        self.service.delete_job.assert_awaited_once_with(self.session, 9)

    async def test_discard_pending_edit_passes_current_user(self):
        self.service.discard_pending_edit = AsyncMock(return_value="discarded")
        await self.controller.discard_pending_edit(current_user=self.user, job_id=3)
        self.service.discard_pending_edit.assert_awaited_once_with(self.session, 3, 42)

    async def test_list_interview_pool_route(self):
        self.service.list_interview_pool = AsyncMock(return_value=["x"])
        result = await self.controller.list_interview_pool(self.user)
        self.assertEqual(result["data"], ["x"])

    async def test_list_job_owners_route(self):
        self.service.list_job_owners = AsyncMock(return_value=["y"])
        result = await self.controller.list_job_owners(self.user)
        self.assertEqual(result["data"], ["y"])

    async def test_get_job_activity(self):
        await self.controller.get_job_activity(current_user=self.user, job_id=9)
        self.service.get_job_activity.assert_awaited_once_with(self.session, 9)

    def _endpoint_permissions(self, endpoint):
        """Pull the `permissions` list out of an authenticate()-wrapped endpoint."""
        idx = endpoint.__code__.co_freevars.index("permissions")
        return endpoint.__closure__[idx].cell_contents

    def test_get_job_route_accepts_read_all(self):
        routes_by_path = {route.path: route for route in self.controller.router.routes}
        get_job_route = routes_by_path["/recruiting/jobs/{job_id}"]

        self.assertIn("GET", get_job_route.methods)
        self.assertEqual(
            self._endpoint_permissions(get_job_route.endpoint),
            [
                Permission.RECRUITING_JOB_READ,
                Permission.RECRUITING_JOB_WRITE,
                Permission.RECRUITING_JOB_APPROVE,
                Permission.RECRUITING_APPLICATION_READ_ALL,
            ],
        )

    def test_list_jobs_route_accepts_write_approve_and_read_all(self):
        """Anyone who can create/approve a job, or has the org-wide read-all
        override, also needs to browse the postings list (e.g. the Job
        Postings management page) — not just RECRUITING_JOB_READ holders."""
        routes_by_path = {route.path: route for route in self.controller.router.routes}
        list_jobs_route = routes_by_path["/recruiting/jobs"]

        self.assertIn("GET", list_jobs_route.methods)
        self.assertEqual(
            self._endpoint_permissions(list_jobs_route.endpoint),
            [
                Permission.RECRUITING_JOB_READ,
                Permission.RECRUITING_JOB_WRITE,
                Permission.RECRUITING_JOB_APPROVE,
                Permission.RECRUITING_APPLICATION_READ_ALL,
            ],
        )

    def test_job_authoring_helper_routes_accept_read_write_and_approve(self):
        """approvers/job-owners are read-only lookups, so any holder of
        RECRUITING_JOB_READ/WRITE/APPROVE should be able to load them — not
        just RECRUITING_JOB_WRITE (job authors)."""
        routes_by_path = {route.path: route for route in self.controller.router.routes}
        expected = [
            Permission.RECRUITING_JOB_READ,
            Permission.RECRUITING_JOB_WRITE,
            Permission.RECRUITING_JOB_APPROVE,
        ]
        for path in (
            "/recruiting/approvers",
            "/recruiting/job-owners",
        ):
            with self.subTest(path=path):
                route = routes_by_path[path]
                self.assertIn("GET", route.methods)
                self.assertEqual(self._endpoint_permissions(route.endpoint), expected)

    def _interview_pool_route(self):
        routes_by_path = {route.path: route for route in self.controller.router.routes}
        return routes_by_path["/recruiting/interview-pool"]

    def _request_as(self, permissions):
        user = UserContextDto(
            sub="s",
            primary_email="me@x.com",
            user_id=42,
            permissions=frozenset(permissions),
        )
        return SimpleNamespace(state=SimpleNamespace(user=user))

    def test_interview_pool_route_accepts_job_permissions_and_read_all(self):
        route = self._interview_pool_route()

        self.assertIn("GET", route.methods)
        self.assertEqual(
            self._endpoint_permissions(route.endpoint),
            [
                Permission.RECRUITING_JOB_READ,
                Permission.RECRUITING_JOB_WRITE,
                Permission.RECRUITING_JOB_APPROVE,
                Permission.RECRUITING_APPLICATION_READ_ALL,
            ],
        )

    async def test_read_all_only_viewer_can_load_the_interview_pool(self):
        """The application detail page loads the pool alongside the job for
        every canView caller, so a read.all viewer with no job.* permission
        must get the pool too, or the whole page fails to load."""
        self.service.list_interview_pool = AsyncMock(return_value=["pool"])
        route = self._interview_pool_route()

        with patch(
            "backend.recruiting.recruiting_controller.api_response", api_response
        ):
            response = await route.endpoint(
                request=self._request_as({Permission.RECRUITING_APPLICATION_READ_ALL})
            )

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.service.list_interview_pool.assert_awaited_once_with(self.session)

    async def test_interview_pool_still_refuses_a_caller_without_permissions(self):
        self.service.list_interview_pool = AsyncMock(return_value=["pool"])
        route = self._interview_pool_route()

        response = await route.endpoint(
            request=self._request_as({Permission.RECRUITING_APPLICATION_ADVANCE})
        )

        self.assertEqual(response.status_code, HTTPStatus.FORBIDDEN)
        self.service.list_interview_pool.assert_not_awaited()


if __name__ == "__main__":
    unittest.main()
