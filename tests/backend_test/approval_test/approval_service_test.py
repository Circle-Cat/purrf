import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from sqlalchemy.exc import IntegrityError

from backend.approval.approval_handler import ApprovalHandler
from backend.approval.approval_service import (
    APPROVAL_CHECKS_FAILED,
    ApprovalService,
)
from backend.common.approval_enums import ApprovalRequestStatus
from backend.common.exceptions import ConflictError
from backend.common.permissions import Permission
from backend.entity.approval_request_entity import ApprovalRequestEntity
from backend.entity.users_entity import UsersEntity

RAISER = 11
REVIEWER = 22
OTHER_REVIEWER = 33
OUTSIDER = 44
MANAGER = 55
REQUEST_ID = 701
SUBJECT_ID = 9


class ChosenHandler(ApprovalHandler):
    """A handler whose reviewer the raiser picks from permission holders."""

    action = "publish_matching"
    target_type = "matching_run"
    subject_type = "mentorship_round"
    raised_event = "test.raised"
    reassigned_event = "test.reassigned"
    decided_event = "test.decided"
    review_permission = Permission.MENTORSHIP_APPROVE

    def __init__(self):
        self.check_raise_mock = AsyncMock()
        self.on_raised_mock = AsyncMock()
        self.problems = []
        self.execute_mock = AsyncMock()
        self.revert_mock = AsyncMock()
        self.after_commit_mock = AsyncMock()

    def subject_id(self, request):
        return request.payload["round_id"]

    async def event_details(self, session, request):
        # "action" collides with the service's own field, which must win.
        return {"roundName": "Spring 2026", "action": "spoofed"}

    async def check_raise(self, session, *, raised_by, target_id, payload):
        await self.check_raise_mock(
            session, raised_by=raised_by, target_id=target_id, payload=payload
        )

    async def on_raised(self, session, request):
        await self.on_raised_mock(session, request)

    async def problems_at_approval(self, session, request):
        return list(self.problems)

    async def execute(self, session, request, *, actor_id):
        await self.execute_mock(session, request, actor_id=actor_id)

    async def revert(self, session, request, outcome):
        await self.revert_mock(session, request, outcome)

    async def after_commit(self, request):
        await self.after_commit_mock(request)


class AssignedHandler(ChosenHandler):
    """A handler that picks the reviewer itself, like leave."""

    action = "leave_request"
    target_type = "leave_request"
    review_permission = None
    raiser_may_reassign = False

    def __init__(self):
        super().__init__()
        self.assigned = MANAGER

    def subject_id(self, request):
        return int(request.target_id)

    async def assign_reviewer(self, session, *, raised_by, target_id, payload):
        return self.assigned


def _user(user_id, *, active=True, blocked=False):
    row = UsersEntity(first_name=f"First{user_id}", last_name=f"Last{user_id}")
    row.user_id = user_id
    row.is_active = active
    row.is_blocked = blocked
    return row


def _request(
    *,
    action="publish_matching",
    status=ApprovalRequestStatus.PENDING,
    raised_by=RAISER,
    reviewer_id=REVIEWER,
    target_id="run-7",
):
    row = ApprovalRequestEntity(
        action=action,
        target_type="matching_run",
        target_id=target_id,
        payload={"round_id": SUBJECT_ID},
        reason="looked over the result",
        raised_by=raised_by,
        reviewer_id=reviewer_id,
        status=status,
    )
    row.request_id = REQUEST_ID
    return row


class ApprovalServiceTestBase(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.order = []
        self.session = AsyncMock()
        self.session.commit = AsyncMock(side_effect=lambda: self.order.append("commit"))
        self.requests = MagicMock()
        self.requests.get_pending_for_target = AsyncMock(return_value=None)
        self.requests.create = AsyncMock(side_effect=self._create)
        self.requests.set_reviewer = AsyncMock(return_value=True)
        self.requests.close = AsyncMock(
            side_effect=lambda *a, **k: self.order.append("close") or True
        )
        self.stored = _request()
        self.requests.get = AsyncMock(side_effect=self._get)
        self.permissions = MagicMock()
        self.permissions.get_active_users_with_permission = AsyncMock(
            return_value=[_user(REVIEWER), _user(OTHER_REVIEWER), _user(RAISER)]
        )
        self.users = MagicMock()
        self.users.get_user_by_user_id = AsyncMock(
            side_effect=lambda _s, uid: _user(uid)
        )
        self.logger = MagicMock()
        self.chosen = ChosenHandler()
        self.assigned = AssignedHandler()
        self.chosen.execute_mock.side_effect = lambda *a, **k: self.order.append(
            "execute"
        )
        self.chosen.after_commit_mock.side_effect = lambda *a: self.order.append(
            "after_commit"
        )
        self.service = ApprovalService(
            self.requests,
            self.permissions,
            self.users,
            self.logger,
            handlers=[self.chosen, self.assigned],
        )
        patcher = patch(
            "backend.approval.approval_service.record_event",
            new=AsyncMock(side_effect=lambda *a, **k: self.order.append("event")),
        )
        self.record_event = patcher.start()
        self.addCleanup(patcher.stop)

    async def _create(self, session, **kwargs):
        row = ApprovalRequestEntity(**kwargs, status=ApprovalRequestStatus.PENDING)
        row.request_id = REQUEST_ID
        self.stored = row
        return row

    async def _get(self, session, request_id, for_update=False):
        return self.stored if request_id == REQUEST_ID else None


class TestRegistry(ApprovalServiceTestBase):
    def test_two_handlers_for_one_action_are_refused(self):
        with self.assertRaises(ValueError):
            ApprovalService(
                self.requests,
                self.permissions,
                self.users,
                self.logger,
                handlers=[ChosenHandler(), ChosenHandler()],
            )

    def test_unknown_action_is_refused(self):
        with self.assertRaises(ValueError):
            self.service.handler_for("delete_everything")

    def test_a_handler_registered_later_is_found(self):
        service = ApprovalService(
            self.requests, self.permissions, self.users, self.logger
        )
        handler = ChosenHandler()

        service.register(handler)

        self.assertIs(service.handler_for(handler.action), handler)

    def test_registering_a_second_handler_for_an_action_is_refused(self):
        with self.assertRaises(ValueError):
            self.service.register(ChosenHandler())


class TestListReviewers(ApprovalServiceTestBase):
    async def test_lists_holders_of_the_review_permission_except_the_raiser(self):
        reviewers = await self.service.list_reviewers(
            self.session, "publish_matching", exclude_user_id=RAISER
        )

        self.assertEqual([u.user_id for u in reviewers], [REVIEWER, OTHER_REVIEWER])
        self.permissions.get_active_users_with_permission.assert_awaited_once_with(
            self.session, "mentorship.approve"
        )

    async def test_an_assigned_reviewer_cannot_be_listed(self):
        with self.assertRaises(ValueError):
            await self.service.list_reviewers(
                self.session, "leave_request", exclude_user_id=RAISER
            )


class TestRaise(ApprovalServiceTestBase):
    async def _raise(self, **overrides):
        kwargs = dict(
            action="publish_matching",
            raised_by=RAISER,
            target_id="run-7",
            payload={"round_id": SUBJECT_ID},
            reason="  looked over the result  ",
            reviewer_id=REVIEWER,
        )
        kwargs.update(overrides)
        return await self.service.raise_request(self.session, **kwargs)

    async def test_raises_a_pending_request_and_tells_the_reviewer(self):
        row = await self._raise()

        self.assertIs(row.status, ApprovalRequestStatus.PENDING)
        self.requests.create.assert_awaited_once_with(
            self.session,
            action="publish_matching",
            target_type="matching_run",
            target_id="run-7",
            payload={"round_id": SUBJECT_ID},
            reason="looked over the result",
            raised_by=RAISER,
            reviewer_id=REVIEWER,
        )
        self.record_event.assert_awaited_once_with(
            self.session,
            subject_type="mentorship_round",
            subject_id=SUBJECT_ID,
            actor_id=RAISER,
            event_type="test.raised",
            details={
                "roundName": "Spring 2026",
                "requestId": REQUEST_ID,
                "action": "publish_matching",
            },
        )
        self.assertEqual(self.order, ["event", "commit"])

    async def test_the_target_is_marked_waiting_before_the_event(self):
        self.chosen.on_raised_mock.side_effect = lambda *a: self.order.append(
            "on_raised"
        )

        await self._raise()

        self.assertEqual(self.order, ["on_raised", "event", "commit"])
        self.assertEqual(
            self.chosen.on_raised_mock.await_args.args[1].request_id, REQUEST_ID
        )

    async def test_nothing_is_marked_waiting_when_the_raise_is_refused(self):
        self.requests.get_pending_for_target.return_value = _request()

        with self.assertRaises(ConflictError):
            await self._raise()
        self.chosen.on_raised_mock.assert_not_awaited()

    async def test_a_blank_reason_is_stored_as_none(self):
        # The reason is optional for every action.
        await self._raise(reason="   ")

        self.assertIsNone(self.requests.create.await_args.kwargs["reason"])
        self.session.commit.assert_awaited_once()

    async def test_reviewer_must_be_named(self):
        with self.assertRaises(ValueError):
            await self._raise(reviewer_id=None)

    async def test_raiser_cannot_name_themselves(self):
        with self.assertRaises(ValueError):
            await self._raise(reviewer_id=RAISER)
        self.requests.create.assert_not_awaited()

    async def test_reviewer_must_hold_the_review_permission(self):
        with self.assertRaises(ValueError):
            await self._raise(reviewer_id=OUTSIDER)
        self.requests.create.assert_not_awaited()

    async def test_a_bad_reviewer_is_refused_before_the_target_is_looked_at(self):
        self.chosen.check_raise_mock.side_effect = ConflictError("target is gone")

        with self.assertRaises(ValueError):
            await self._raise(reviewer_id=OUTSIDER)
        self.chosen.check_raise_mock.assert_not_awaited()

    async def test_the_handler_can_refuse_the_target(self):
        self.chosen.check_raise_mock.side_effect = ConflictError("run not current")

        with self.assertRaises(ConflictError):
            await self._raise()
        self.chosen.check_raise_mock.assert_awaited_once_with(
            self.session,
            raised_by=RAISER,
            target_id="run-7",
            payload={"round_id": SUBJECT_ID},
        )
        self.requests.create.assert_not_awaited()

    async def test_a_target_already_waiting_is_refused(self):
        self.requests.get_pending_for_target.return_value = _request()

        with self.assertRaises(ConflictError):
            await self._raise()
        self.requests.create.assert_not_awaited()
        self.session.commit.assert_not_awaited()

    async def test_a_concurrent_raise_caught_by_the_index_is_a_conflict(self):
        self.requests.create.side_effect = IntegrityError("insert", {}, Exception())

        with self.assertRaises(ConflictError):
            await self._raise()
        self.record_event.assert_not_awaited()
        self.session.commit.assert_not_awaited()

    async def test_an_assigned_reviewer_is_picked_by_the_handler(self):
        await self._raise(
            action="leave_request", target_id="88", reviewer_id=None, reason=None
        )

        kwargs = self.requests.create.await_args.kwargs
        self.assertEqual(kwargs["reviewer_id"], MANAGER)
        self.assertIsNone(kwargs["reason"])
        self.assertEqual(kwargs["target_type"], "leave_request")

    async def test_an_assigned_reviewer_cannot_be_chosen_by_the_raiser(self):
        with self.assertRaises(ValueError):
            await self._raise(action="leave_request", target_id="88")

    async def test_an_assigned_reviewer_must_not_be_the_raiser(self):
        self.assigned.assigned = RAISER

        with self.assertRaises(ValueError):
            await self._raise(action="leave_request", target_id="88", reviewer_id=None)

    async def test_an_assigned_reviewer_must_be_an_active_account(self):
        self.users.get_user_by_user_id.side_effect = lambda _s, uid: _user(
            uid, blocked=True
        )

        with self.assertRaises(ValueError):
            await self._raise(action="leave_request", target_id="88", reviewer_id=None)
        self.requests.create.assert_not_awaited()


class TestReassign(ApprovalServiceTestBase):
    async def test_the_raiser_hands_it_to_another_reviewer(self):
        await self.service.reassign(
            self.session,
            request_id=REQUEST_ID,
            actor_id=RAISER,
            reviewer_id=OTHER_REVIEWER,
        )

        self.requests.set_reviewer.assert_awaited_once_with(
            self.session, REQUEST_ID, OTHER_REVIEWER
        )
        self.record_event.assert_awaited_once_with(
            self.session,
            subject_type="mentorship_round",
            subject_id=SUBJECT_ID,
            actor_id=RAISER,
            event_type="test.reassigned",
            details={
                "roundName": "Spring 2026",
                "requestId": REQUEST_ID,
                "action": "publish_matching",
                "previousReviewerId": REVIEWER,
            },
        )
        self.assertEqual(self.order, ["event", "commit"])

    async def test_only_the_raiser_may_reassign(self):
        with self.assertRaises(PermissionError):
            await self.service.reassign(
                self.session,
                request_id=REQUEST_ID,
                actor_id=REVIEWER,
                reviewer_id=OTHER_REVIEWER,
            )
        self.requests.set_reviewer.assert_not_awaited()

    async def test_an_assigned_reviewer_cannot_be_changed(self):
        self.stored = _request(action="leave_request", target_id="88")

        with self.assertRaises(PermissionError):
            await self.service.reassign(
                self.session,
                request_id=REQUEST_ID,
                actor_id=RAISER,
                reviewer_id=OTHER_REVIEWER,
            )

    async def test_a_closed_request_cannot_be_reassigned(self):
        self.stored = _request(status=ApprovalRequestStatus.APPROVED)

        with self.assertRaises(ConflictError):
            await self.service.reassign(
                self.session,
                request_id=REQUEST_ID,
                actor_id=RAISER,
                reviewer_id=OTHER_REVIEWER,
            )

    async def test_reassigning_to_the_current_reviewer_is_refused(self):
        with self.assertRaises(ValueError):
            await self.service.reassign(
                self.session,
                request_id=REQUEST_ID,
                actor_id=RAISER,
                reviewer_id=REVIEWER,
            )

    async def test_the_new_reviewer_must_hold_the_permission(self):
        with self.assertRaises(ValueError):
            await self.service.reassign(
                self.session,
                request_id=REQUEST_ID,
                actor_id=RAISER,
                reviewer_id=OUTSIDER,
            )
        self.requests.set_reviewer.assert_not_awaited()

    async def test_an_unknown_request_is_refused(self):
        with self.assertRaises(ValueError):
            await self.service.reassign(
                self.session, request_id=1, actor_id=RAISER, reviewer_id=REVIEWER
            )


class TestDecide(ApprovalServiceTestBase):
    async def _decide(self, **overrides):
        kwargs = dict(
            request_id=REQUEST_ID, actor_id=REVIEWER, approve=True, comment=None
        )
        kwargs.update(overrides)
        return await self.service.decide(self.session, **kwargs)

    async def test_approving_executes_closes_and_tells_the_raiser(self):
        await self._decide()

        self.chosen.execute_mock.assert_awaited_once()
        self.assertEqual(
            self.chosen.execute_mock.await_args.kwargs, {"actor_id": REVIEWER}
        )
        self.requests.close.assert_awaited_once_with(
            self.session,
            REQUEST_ID,
            status=ApprovalRequestStatus.APPROVED,
            decided_by=REVIEWER,
            decision_comment=None,
        )
        self.record_event.assert_awaited_once_with(
            self.session,
            subject_type="mentorship_round",
            subject_id=SUBJECT_ID,
            actor_id=REVIEWER,
            event_type="test.decided",
            details={
                "roundName": "Spring 2026",
                "requestId": REQUEST_ID,
                "action": "publish_matching",
                "decision": "approved",
                "comment": None,
            },
        )
        self.assertEqual(
            self.order, ["execute", "close", "event", "commit", "after_commit"]
        )
        self.chosen.revert_mock.assert_not_awaited()

    async def test_only_the_named_reviewer_may_decide(self):
        # Holding the review permission, or every permission, is not enough:
        # the check is on who was named.
        with self.assertRaises(PermissionError):
            await self._decide(actor_id=OTHER_REVIEWER)
        self.chosen.execute_mock.assert_not_awaited()
        self.session.commit.assert_not_awaited()

    async def test_a_closed_request_cannot_be_decided(self):
        self.stored = _request(status=ApprovalRequestStatus.WITHDRAWN)

        with self.assertRaises(ConflictError):
            await self._decide()
        self.chosen.execute_mock.assert_not_awaited()

    async def test_failed_checks_refuse_the_approval_and_leave_it_pending(self):
        self.chosen.problems = ["The run is no longer current.", "Ann is blocked."]

        with self.assertRaises(ConflictError) as raised:
            await self._decide()

        self.assertEqual(raised.exception.code, APPROVAL_CHECKS_FAILED)
        self.assertIn("The run is no longer current.", str(raised.exception))
        self.assertIn("Ann is blocked.", str(raised.exception))
        self.chosen.execute_mock.assert_not_awaited()
        self.requests.close.assert_not_awaited()
        self.session.commit.assert_not_awaited()

    async def test_rejecting_needs_a_reason(self):
        with self.assertRaises(ValueError):
            await self._decide(approve=False, comment="  ")
        self.chosen.revert_mock.assert_not_awaited()
        self.requests.close.assert_not_awaited()
        self.session.commit.assert_not_awaited()

    async def test_rejecting_reverts_and_records_the_reason(self):
        await self._decide(approve=False, comment=" two mentors over slots ")

        self.assertIs(
            self.chosen.revert_mock.await_args.args[2], ApprovalRequestStatus.REJECTED
        )
        self.chosen.execute_mock.assert_not_awaited()
        self.requests.close.assert_awaited_once_with(
            self.session,
            REQUEST_ID,
            status=ApprovalRequestStatus.REJECTED,
            decided_by=REVIEWER,
            decision_comment="two mentors over slots",
        )
        details = self.record_event.await_args.kwargs["details"]
        self.assertEqual(details["decision"], "rejected")
        # The timeline of what was decided shows why.
        self.assertEqual(details["comment"], "two mentors over slots")
        self.chosen.after_commit_mock.assert_not_awaited()

    async def test_a_failing_after_commit_step_is_logged_not_raised(self):
        self.chosen.after_commit_mock.side_effect = RuntimeError("redis down")

        row = await self._decide()

        self.assertEqual(row.request_id, REQUEST_ID)
        self.logger.exception.assert_called_once()

    async def test_a_close_that_does_not_land_is_a_conflict(self):
        self.requests.close.side_effect = None
        self.requests.close.return_value = False

        with self.assertRaises(ConflictError):
            await self._decide()
        self.session.commit.assert_not_awaited()


class TestWithdraw(ApprovalServiceTestBase):
    async def test_the_raiser_withdraws_a_pending_request(self):
        await self.service.withdraw(
            self.session, request_id=REQUEST_ID, actor_id=RAISER
        )

        self.assertIs(
            self.chosen.revert_mock.await_args.args[2], ApprovalRequestStatus.WITHDRAWN
        )
        self.requests.close.assert_awaited_once_with(
            self.session,
            REQUEST_ID,
            status=ApprovalRequestStatus.WITHDRAWN,
            decided_by=RAISER,
            decision_comment=None,
        )
        self.record_event.assert_awaited_once_with(
            self.session,
            subject_type="mentorship_round",
            subject_id=SUBJECT_ID,
            actor_id=RAISER,
            event_type="test.decided",
            details={
                "roundName": "Spring 2026",
                "requestId": REQUEST_ID,
                "action": "publish_matching",
                "decision": "withdrawn",
                "comment": None,
            },
        )
        self.assertEqual(self.order, ["close", "event", "commit"])

    async def test_only_the_raiser_may_withdraw(self):
        with self.assertRaises(PermissionError):
            await self.service.withdraw(
                self.session, request_id=REQUEST_ID, actor_id=REVIEWER
            )
        self.requests.close.assert_not_awaited()

    async def test_a_decided_request_cannot_be_withdrawn(self):
        self.stored = _request(status=ApprovalRequestStatus.REJECTED)

        with self.assertRaises(ConflictError):
            await self.service.withdraw(
                self.session, request_id=REQUEST_ID, actor_id=RAISER
            )
        self.chosen.revert_mock.assert_not_awaited()


class TestSupersede(ApprovalServiceTestBase):
    async def test_nothing_pending_closes_nothing(self):
        count = await self.service.supersede_pending(
            self.session,
            action="publish_matching",
            target_id="run-7",
            actor_id=OUTSIDER,
        )

        self.assertEqual(count, 0)
        self.requests.close.assert_not_awaited()

    async def test_the_pending_request_is_superseded_without_a_commit(self):
        self.requests.get_pending_for_target.return_value = _request()

        count = await self.service.supersede_pending(
            self.session,
            action="publish_matching",
            target_id="run-7",
            actor_id=OUTSIDER,
        )

        self.assertEqual(count, 1)
        self.requests.close.assert_awaited_once_with(
            self.session,
            REQUEST_ID,
            status=ApprovalRequestStatus.SUPERSEDED,
            decided_by=OUTSIDER,
            decision_comment=None,
        )
        self.session.commit.assert_not_awaited()
        self.record_event.assert_not_awaited()


class TestReads(ApprovalServiceTestBase):
    async def test_pending_for_target_uses_the_handler_target_type(self):
        self.requests.get_pending_for_target.return_value = _request()

        await self.service.get_pending_for_target(
            self.session, "publish_matching", "run-7"
        )

        self.requests.get_pending_for_target.assert_awaited_once_with(
            self.session, "publish_matching", "matching_run", "run-7"
        )

    async def test_pending_for_targets_comes_back_by_target(self):
        first, second = _request(target_id="run-1"), _request(target_id="run-2")
        self.requests.list_pending_for_targets = AsyncMock(return_value=[first, second])

        result = await self.service.list_pending_for_targets(
            self.session, "publish_matching", ["run-1", "run-2", "run-3"]
        )

        self.assertEqual(result, {"run-1": first, "run-2": second})
        self.requests.list_pending_for_targets.assert_awaited_once_with(
            self.session,
            "publish_matching",
            "matching_run",
            ["run-1", "run-2", "run-3"],
        )

    async def test_latest_for_targets_comes_back_by_target(self):
        newest = _request(target_id="run-1")
        self.requests.list_latest_for_targets = AsyncMock(return_value=[newest])

        result = await self.service.latest_for_targets(
            self.session, "publish_matching", ["run-1", "run-2"]
        )

        self.assertEqual(result, {"run-1": newest})
        self.requests.list_latest_for_targets.assert_awaited_once_with(
            self.session, "publish_matching", "matching_run", ["run-1", "run-2"]
        )

    async def test_latest_closed_for_target_uses_the_handler_target_type(self):
        self.requests.get_latest_closed_for_target = AsyncMock(return_value=None)

        await self.service.get_latest_closed_for_target(
            self.session, "leave_request", "88"
        )

        self.requests.get_latest_closed_for_target.assert_awaited_once_with(
            self.session, "leave_request", "leave_request", "88"
        )


if __name__ == "__main__":
    unittest.main()
