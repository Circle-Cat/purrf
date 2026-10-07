"""What a block request checks and does, as an approval."""

import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from backend.admin.block_user_handler import BlockUserHandler
from backend.common.user_enums import UserEvent
from backend.entity.approval_request_entity import ApprovalRequestEntity

TARGET = 31
RAISER = 7
REVIEWER = 8


def _request(*, reviewer_id=REVIEWER, reason="Abusive messages"):
    return ApprovalRequestEntity(
        action="block_user",
        target_type="user",
        target_id=str(TARGET),
        payload={"raised_from": "recruiting_board"},
        reason=reason,
        raised_by=RAISER,
        reviewer_id=reviewer_id,
    )


class BlockUserHandlerTest(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.session = MagicMock()
        self.users = MagicMock()
        self.users.get_user_by_user_id = AsyncMock(
            return_value=SimpleNamespace(user_id=TARGET, is_blocked=False)
        )
        self.applications = MagicMock()
        self.submissions = MagicMock()
        self.interviews = MagicMock()
        self.scheduling = MagicMock()
        self.handler = BlockUserHandler(
            self.users,
            self.applications,
            self.submissions,
            self.interviews,
            self.scheduling,
        )

    def test_declares_the_user_events_and_the_user_admin_reviewer(self):
        self.assertEqual(self.handler.action, "block_user")
        self.assertEqual(self.handler.target_type, "user")
        self.assertEqual(self.handler.raised_event, UserEvent.BLOCK_REQUESTED)
        self.assertEqual(
            self.handler.reassigned_event, UserEvent.BLOCK_REQUEST_REASSIGNED
        )
        self.assertEqual(self.handler.decided_event, UserEvent.BLOCK_REQUEST_DECIDED)
        self.assertEqual(self.handler.review_permission.value, "user.admin")
        self.assertTrue(self.handler.raiser_may_reassign)

    def test_events_are_recorded_against_the_target(self):
        self.assertEqual(self.handler.subject_id(_request()), TARGET)

    async def test_raising_against_an_unknown_person_is_refused(self):
        self.users.get_user_by_user_id.return_value = None

        with self.assertRaises(ValueError):
            await self.handler.check_raise(
                self.session, raised_by=RAISER, target_id=str(TARGET), payload={}
            )

    async def test_raising_against_someone_already_blocked_is_refused(self):
        self.users.get_user_by_user_id.return_value = SimpleNamespace(
            user_id=TARGET, is_blocked=True
        )

        with self.assertRaisesRegex(ValueError, "already blocked"):
            await self.handler.check_raise(
                self.session, raised_by=RAISER, target_id=str(TARGET), payload={}
            )

    async def test_raising_against_someone_unblocked_goes_ahead(self):
        await self.handler.check_raise(
            self.session, raised_by=RAISER, target_id=str(TARGET), payload={}
        )
        self.users.get_user_by_user_id.assert_awaited_once_with(self.session, TARGET)

    async def test_nothing_stands_in_the_way_of_approving_an_unblocked_person(self):
        self.assertEqual(
            await self.handler.problems_at_approval(self.session, _request()), []
        )

    async def test_approving_someone_blocked_since_is_a_problem(self):
        self.users.get_user_by_user_id.return_value = SimpleNamespace(
            user_id=TARGET, is_blocked=True
        )

        problems = await self.handler.problems_at_approval(self.session, _request())

        self.assertEqual(problems, ["This person is already blocked."])

    async def test_a_reviewer_cannot_approve_blocking_themselves(self):
        with self.assertRaises(PermissionError):
            await self.handler.problems_at_approval(
                self.session, _request(reviewer_id=TARGET)
            )

    async def test_approving_applies_the_block_with_the_request_reason(self):
        with patch(
            "backend.admin.block_user_handler.apply_block_kernel", new=AsyncMock()
        ) as kernel:
            await self.handler.execute(self.session, _request(), actor_id=REVIEWER)

        kernel.assert_awaited_once_with(
            self.session,
            actor_id=REVIEWER,
            user_id=TARGET,
            reason="Abusive messages",
            users_repository=self.users,
            application_repository=self.applications,
            application_submission_repository=self.submissions,
            application_interview_repository=self.interviews,
            interview_scheduling_service=self.scheduling,
        )

    async def test_a_request_with_no_reason_blocks_with_none(self):
        with patch(
            "backend.admin.block_user_handler.apply_block_kernel", new=AsyncMock()
        ) as kernel:
            await self.handler.execute(
                self.session, _request(reason=None), actor_id=REVIEWER
            )

        self.assertIsNone(kernel.await_args.kwargs["reason"])


if __name__ == "__main__":
    unittest.main()
