import unittest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

from sqlalchemy.exc import IntegrityError

from backend.admin.block_service import BLOCK_TARGET, BLOCK_USER, BlockService
from backend.admin.block_user_handler import BlockUserHandler
from backend.approval.approval_service import APPROVAL_CHECKS_FAILED, ApprovalService
from backend.common.approval_enums import ApprovalRequestStatus
from backend.common.exceptions import ConflictError
from backend.common.permissions import Permission
from backend.common.user_enums import USER_SUBJECT_TYPE, UserEvent
from backend.entity.approval_request_entity import ApprovalRequestEntity
from backend.entity.users_entity import UsersEntity

# Distinct ids for every role, and request ids from 301 up, so a read of the
# wrong one shows.
TARGET = 5
RAISER = 2
OTHER_RAISER = 6
REVIEWER = 3
OTHER_ADMIN = 4
ADMIN = 7


def _user(user_id):
    # Distinctive per person: a one-letter name makes the "does the refusal
    # leak who raised it" assertion match the article in any English sentence.
    row = UsersEntity(first_name=f"Firstname{user_id}", last_name=f"Lastname{user_id}")
    row.user_id = user_id
    row.is_active = True
    row.is_blocked = False
    row.blocked_by = None
    row.blocked_at = None
    row.blocked_reason = None
    return row


class _FakeApprovalRequestRepository:
    """In-memory ApprovalRequestRepository with the real one's semantics.

    Closing and reassigning only touch a pending row and say whether they
    did; a second pending request on a target is refused the way the partial
    unique index refuses it.
    """

    def __init__(self):
        self.rows: list[ApprovalRequestEntity] = []
        self._next_id = 301

    def add(self, **fields) -> ApprovalRequestEntity:
        row = ApprovalRequestEntity(**fields)
        row.request_id = self._next_id
        row.created_at = datetime.now(timezone.utc)
        self._next_id += 1
        self.rows.append(row)
        return row

    async def create(
        self,
        session,
        *,
        action,
        target_type,
        target_id,
        payload,
        reason,
        raised_by,
        reviewer_id,
    ):
        if await self.get_pending_for_target(session, action, target_type, target_id):
            raise IntegrityError("INSERT", {}, Exception("pending target"))
        return self.add(
            action=action,
            target_type=target_type,
            target_id=target_id,
            payload=payload,
            reason=reason,
            raised_by=raised_by,
            reviewer_id=reviewer_id,
            status=ApprovalRequestStatus.PENDING,
        )

    async def get(self, session, request_id, *, for_update=False):
        return next((r for r in self.rows if r.request_id == request_id), None)

    async def get_pending_for_target(self, session, action, target_type, target_id):
        return next(
            (
                r
                for r in self.rows
                if r.action == action
                and r.target_type == target_type
                and r.target_id == target_id
                and r.status == ApprovalRequestStatus.PENDING
            ),
            None,
        )

    async def list_pending_for_reviewer(self, session, reviewer_id, actions):
        return [
            r
            for r in self.rows
            if r.reviewer_id == reviewer_id
            and r.status == ApprovalRequestStatus.PENDING
            and r.action in actions
        ]

    async def list_pending_raised_by(self, session, raised_by, actions):
        return [
            r
            for r in self.rows
            if r.raised_by == raised_by
            and r.status == ApprovalRequestStatus.PENDING
            and r.action in actions
        ]

    async def set_reviewer(self, session, request_id, reviewer_id):
        row = await self.get(session, request_id)
        if row is None or row.status != ApprovalRequestStatus.PENDING:
            return False
        row.reviewer_id = reviewer_id
        return True

    async def close(self, session, request_id, *, status, decided_by, decision_comment):
        row = await self.get(session, request_id)
        if row is None or row.status != ApprovalRequestStatus.PENDING:
            return False
        row.status = status
        row.decided_by = decided_by
        row.decided_at = datetime.now(timezone.utc)
        row.decision_comment = decision_comment
        return True


class TestBlockServiceRequests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.users_repo = MagicMock()
        self.app_repo = MagicMock()
        self.app_repo.list_by_user = AsyncMock(return_value=[])
        self.sub_repo = MagicMock()
        self.interview_repo = MagicMock()
        self.interview_repo.list_by_application_ids = AsyncMock(return_value=[])
        self.interview_svc = MagicMock()
        self.interview_svc.cancel_for_round = AsyncMock(return_value=True)
        self.perms_repo = MagicMock()
        self.requests = _FakeApprovalRequestRepository()
        self.session = AsyncMock()

        self.people = {
            uid: _user(uid)
            for uid in (TARGET, RAISER, OTHER_RAISER, REVIEWER, OTHER_ADMIN, ADMIN)
        }
        self.users_repo.get_user_by_user_id = AsyncMock(
            side_effect=lambda _s, user_id: self.people.get(user_id)
        )
        self.users_repo.get_all_by_ids = AsyncMock(
            side_effect=lambda _s, ids: [
                self.people[i] for i in ids if i in self.people
            ]
        )
        # Everyone who can be named as reviewer holds USER_ADMIN.
        self.perms_repo.get_active_users_with_permission = AsyncMock(
            return_value=[self.people[REVIEWER], self.people[OTHER_ADMIN]]
        )

        # One recorder for both modules: request events are written by the
        # approval service, the block's own events by the kernel.
        self.record_event = AsyncMock()
        for target in (
            "backend.admin.block_service.record_event",
            "backend.approval.approval_service.record_event",
        ):
            recorder = patch(target, new=self.record_event)
            recorder.start()
            self.addCleanup(recorder.stop)

        self.mentorship = MagicMock()
        self.mentorship.end_for_blocked_user = AsyncMock()
        self.mentorship.preflight_counts = AsyncMock(return_value=(0, 0))
        self.approvals = ApprovalService(
            approval_request_repository=self.requests,
            user_permissions_repository=self.perms_repo,
            users_repository=self.users_repo,
            logger=MagicMock(),
            handlers=[
                BlockUserHandler(
                    self.users_repo,
                    self.app_repo,
                    self.sub_repo,
                    self.interview_repo,
                    self.interview_svc,
                    self.mentorship,
                )
            ],
        )
        self.service = BlockService(
            users_repository=self.users_repo,
            application_repository=self.app_repo,
            application_submission_repository=self.sub_repo,
            application_interview_repository=self.interview_repo,
            interview_scheduling_service=self.interview_svc,
            approval_service=self.approvals,
            user_permissions_repository=self.perms_repo,
            mentorship_block_service=self.mentorship,
            logger=MagicMock(),
        )

    async def _raise(
        self,
        actor_id=RAISER,
        user_id=TARGET,
        reason="second no-show",
        reviewer_id=REVIEWER,
        raised_from="recruiting_application",
    ):
        return await self.service.raise_request(
            self.session,
            actor_id=actor_id,
            user_id=user_id,
            reason=reason,
            reviewer_id=reviewer_id,
            raised_from=raised_from,
        )

    async def _decide(self, request_id, *, actor_id=REVIEWER, approved, note=None):
        return await self.service.decide(
            self.session,
            actor_id=actor_id,
            request_id=request_id,
            approved=approved,
            note=note,
        )

    def _seed_request(self, **fields):
        """A row put straight into the repository, bypassing the service, for
        shapes raise_request refuses to produce."""
        return self.requests.add(**{
            "action": BLOCK_USER,
            "target_type": BLOCK_TARGET,
            "target_id": str(TARGET),
            "payload": {"raised_from": "recruiting_application"},
            "reason": "second no-show",
            "raised_by": RAISER,
            "reviewer_id": REVIEWER,
            "status": ApprovalRequestStatus.PENDING,
            **fields,
        })

    def _events(self, event_type):
        return [
            call
            for call in self.record_event.await_args_list
            if call.kwargs["event_type"] == event_type
        ]

    # -- raising ------------------------------------------------------------

    async def test_raise_returns_a_pending_request_with_names_resolved(self):
        out = await self._raise()

        self.assertEqual(out.status, ApprovalRequestStatus.PENDING.value)
        self.assertEqual(out.target_user_id, TARGET)
        self.assertEqual(out.raised_by, RAISER)
        self.assertEqual(out.reviewer_id, REVIEWER)
        self.assertEqual(out.raised_from, "recruiting_application")
        self.assertEqual(out.reason, "second no-show")
        self.assertEqual(out.target_name, "Firstname5 Lastname5")
        self.assertEqual(out.raised_by_name, "Firstname2 Lastname2")
        self.assertEqual(out.reviewer_name, "Firstname3 Lastname3")
        self.assertIsNone(out.decided_by_name)
        self.session.commit.assert_awaited_once()

    async def test_raise_stores_a_block_user_approval_request(self):
        out = await self._raise()

        (row,) = self.requests.rows
        self.assertEqual(row.request_id, out.id)
        self.assertEqual(row.action, BLOCK_USER)
        self.assertEqual(row.target_type, "user")
        self.assertEqual(row.target_id, str(TARGET))
        self.assertEqual(row.payload, {"raised_from": "recruiting_application"})

    async def test_names_are_resolved_in_one_lookup(self):
        await self._raise()

        self.users_repo.get_all_by_ids.assert_awaited_once()

    async def test_reason_is_optional_and_stored_as_none(self):
        for reason in (None, "   "):
            with self.subTest(reason=reason):
                self.requests.rows.clear()

                out = await self._raise(reason=reason)

                self.assertIsNone(out.reason)
                self.assertIsNone(self.requests.rows[0].reason)

    async def test_reviewer_must_hold_user_admin(self):
        self.perms_repo.get_active_users_with_permission = AsyncMock(return_value=[])

        with self.assertRaises(ValueError):
            await self._raise()

        self.assertEqual(self.requests.rows, [])
        self.session.commit.assert_not_awaited()

    async def test_reviewer_is_looked_up_against_user_admin(self):
        await self._raise()

        self.perms_repo.get_active_users_with_permission.assert_awaited_once_with(
            self.session, Permission.USER_ADMIN.value
        )

    async def test_cannot_raise_a_request_about_yourself(self):
        """Not a guardrail against self-harm. Without it the refusals below are
        a probe: someone who suspects a request names them could learn it
        exists by raising one about themselves."""
        with self.assertRaises(PermissionError):
            await self._raise(actor_id=TARGET)

        self.assertEqual(self.requests.rows, [])

    async def test_cannot_raise_against_someone_already_blocked(self):
        """Approving it later would overwrite blocked_by/at/reason and erase
        who imposed the original sanction."""
        self.people[TARGET].is_blocked = True

        with self.assertRaises(ValueError):
            await self._raise()

        self.assertEqual(self.requests.rows, [])

    async def test_a_bogus_reviewer_hides_whether_the_target_is_blocked(self):
        """The reviewer is checked first: otherwise naming nobody in
        particular would read out anyone's block state."""
        self.people[TARGET].is_blocked = True
        self.perms_repo.get_active_users_with_permission = AsyncMock(return_value=[])

        with self.assertRaises(ValueError) as err:
            await self._raise()

        self.assertNotIn("blocked", str(err.exception))

    async def test_raiser_cannot_name_themselves_as_reviewer(self):
        """Two people is the whole point of the flow."""
        self.perms_repo.get_active_users_with_permission = AsyncMock(
            return_value=[self.people[RAISER]]
        )

        with self.assertRaises(ValueError):
            await self._raise(reviewer_id=RAISER)

        self.assertEqual(self.requests.rows, [])

    async def test_raiser_cannot_name_the_target_as_reviewer(self):
        """Asking someone to rule on their own blocking is the same failure as
        letting them block themselves, one step earlier."""
        # In the pool, so the refusal can only come from the target rule.
        self.perms_repo.get_active_users_with_permission = AsyncMock(
            return_value=[self.people[REVIEWER], self.people[TARGET]]
        )

        with self.assertRaises(ValueError):
            await self._raise(reviewer_id=TARGET)

        self.assertEqual(self.requests.rows, [])
        self.session.commit.assert_not_awaited()

    async def test_raised_from_must_be_a_known_source(self):
        for raised_from in ("", "recruiting_board", "x" * 65):
            with self.subTest(raised_from=raised_from):
                with self.assertRaises(ValueError):
                    await self._raise(raised_from=raised_from)

        self.assertEqual(self.requests.rows, [])

    async def test_both_sources_are_accepted(self):
        for raised_from in ("recruiting_application", "mentorship_participant"):
            with self.subTest(raised_from=raised_from):
                self.requests.rows.clear()

                out = await self._raise(raised_from=raised_from)

                self.assertEqual(out.raised_from, raised_from)

    async def test_raise_records_the_event_the_reviewer_is_notified_from(self):
        """``user_recipient_resolvers._request_of`` finds the row through
        ``details["requestId"]``."""
        out = await self._raise()

        (call,) = self._events(UserEvent.BLOCK_REQUESTED)
        self.assertEqual(call.kwargs["subject_type"], USER_SUBJECT_TYPE)
        self.assertEqual(call.kwargs["subject_id"], TARGET)
        self.assertEqual(call.kwargs["actor_id"], RAISER)
        self.assertEqual(
            call.kwargs["details"], {"requestId": out.id, "action": BLOCK_USER}
        )

    async def test_unknown_target_is_rejected(self):
        with self.assertRaises(ValueError):
            await self._raise(user_id=999999)

    async def test_second_pending_request_is_a_conflict_without_leaking(self):
        """The second raiser may not see the first request, so the refusal must
        not carry its reason or who filed it."""
        await self._raise(reason="secret reason")

        with self.assertRaises(ConflictError) as err:
            await self._raise(
                actor_id=OTHER_RAISER,
                reason="r2",
                raised_from="recruiting_application",
            )

        message = str(err.exception)
        self.assertNotIn("secret reason", message)
        self.assertNotIn(self.people[RAISER].first_name, message)
        self.assertNotIn(str(RAISER), message)
        self.assertEqual(len(self.requests.rows), 1)

    async def test_a_second_request_is_fine_once_the_first_is_closed(self):
        first = await self._raise()
        await self._decide(first.id, approved=False, note="not enough")

        second = await self._raise(actor_id=OTHER_RAISER)

        self.assertEqual(second.status, ApprovalRequestStatus.PENDING.value)

    # -- ids that are not block requests ------------------------------------

    async def test_other_approval_requests_are_not_block_requests(self):
        """Every approval shares one id space; the block routes must not
        reach a job review or a matching exemption through it."""
        other = self._seed_request(action="job_review", target_type="job")

        for name, call in (
            (
                "reassign",
                lambda: self.service.reassign(
                    self.session,
                    actor_id=RAISER,
                    request_id=other.request_id,
                    reviewer_id=OTHER_ADMIN,
                ),
            ),
            ("decide", lambda: self._decide(other.request_id, approved=True)),
            (
                "withdraw",
                lambda: self.service.withdraw(
                    self.session, actor_id=RAISER, request_id=other.request_id
                ),
            ),
        ):
            with self.subTest(name):
                with self.assertRaises(ValueError) as err:
                    await call()
                self.assertEqual(
                    str(err.exception), f"block request {other.request_id} not found"
                )

        self.assertIs(other.status, ApprovalRequestStatus.PENDING)
        self.assertEqual(other.reviewer_id, REVIEWER)
        self.session.commit.assert_not_awaited()

    async def test_unknown_request_ids_are_refused(self):
        for name, call in (
            (
                "reassign",
                lambda: self.service.reassign(
                    self.session,
                    actor_id=RAISER,
                    request_id=999999,
                    reviewer_id=OTHER_ADMIN,
                ),
            ),
            ("decide", lambda: self._decide(999999, approved=True)),
            (
                "withdraw",
                lambda: self.service.withdraw(
                    self.session, actor_id=RAISER, request_id=999999
                ),
            ),
        ):
            with self.subTest(name):
                with self.assertRaises(ValueError):
                    await call()

    # -- reassigning --------------------------------------------------------

    async def test_only_raiser_may_reassign(self):
        request = await self._raise()

        with self.assertRaises(PermissionError):
            await self.service.reassign(
                self.session,
                actor_id=REVIEWER,
                request_id=request.id,
                reviewer_id=OTHER_ADMIN,
            )

        out = await self.service.reassign(
            self.session,
            actor_id=RAISER,
            request_id=request.id,
            reviewer_id=OTHER_ADMIN,
        )
        self.assertEqual(out.reviewer_id, OTHER_ADMIN)
        self.assertEqual(out.reviewer_name, "Firstname4 Lastname4")

    async def test_reassign_moves_the_decision_right(self):
        request = await self._raise()
        await self.service.reassign(
            self.session,
            actor_id=RAISER,
            request_id=request.id,
            reviewer_id=OTHER_ADMIN,
        )

        with self.assertRaises(PermissionError):
            await self._decide(request.id, actor_id=REVIEWER, approved=True)
        self.assertFalse(self.people[TARGET].is_blocked)

        out = await self._decide(request.id, actor_id=OTHER_ADMIN, approved=True)
        self.assertEqual(out.status, ApprovalRequestStatus.APPROVED.value)

    async def test_reassign_target_must_hold_user_admin(self):
        request = await self._raise()

        with self.assertRaises(ValueError):
            await self.service.reassign(
                self.session,
                actor_id=RAISER,
                request_id=request.id,
                reviewer_id=OTHER_RAISER,
            )

    async def test_reassign_a_closed_request_is_a_conflict(self):
        request = await self._raise()
        await self._decide(request.id, approved=False, note="not enough")

        with self.assertRaises(ConflictError):
            await self.service.reassign(
                self.session,
                actor_id=RAISER,
                request_id=request.id,
                reviewer_id=OTHER_ADMIN,
            )

    async def test_reassign_to_the_current_reviewer_is_rejected(self):
        request = await self._raise()
        self.record_event.reset_mock()

        with self.assertRaises(ValueError):
            await self.service.reassign(
                self.session,
                actor_id=RAISER,
                request_id=request.id,
                reviewer_id=REVIEWER,
            )

        self.record_event.assert_not_awaited()

    async def test_reassign_cannot_hand_the_request_to_its_target(self):
        request = await self._raise()
        self.perms_repo.get_active_users_with_permission = AsyncMock(
            return_value=[self.people[REVIEWER], self.people[TARGET]]
        )
        self.session.commit.reset_mock()

        with self.assertRaises(ValueError):
            await self.service.reassign(
                self.session,
                actor_id=RAISER,
                request_id=request.id,
                reviewer_id=TARGET,
            )

        self.assertEqual(self.requests.rows[0].reviewer_id, REVIEWER)
        self.session.commit.assert_not_awaited()

    async def test_reassign_by_a_stranger_naming_the_target_is_a_403(self):
        """The target-as-reviewer refusal is only given to the raiser; anyone
        else gets the same 403 they would get naming anybody."""
        request = await self._raise()

        with self.assertRaises(PermissionError):
            await self.service.reassign(
                self.session,
                actor_id=OTHER_RAISER,
                request_id=request.id,
                reviewer_id=TARGET,
            )

    async def test_reassign_checks_standing_before_status(self):
        """A closed request must answer a stranger exactly as an open one
        does."""
        request = await self._raise()
        await self._decide(request.id, approved=False, note="not enough")

        with self.assertRaises(PermissionError):
            await self.service.reassign(
                self.session,
                actor_id=OTHER_RAISER,
                request_id=request.id,
                reviewer_id=OTHER_ADMIN,
            )

    async def test_reassign_records_where_the_request_came_from_and_went(self):
        """The old reviewer is a recipient of this event, and the resolver
        finds them through ``previousReviewerId``."""
        request = await self._raise()
        await self.service.reassign(
            self.session,
            actor_id=RAISER,
            request_id=request.id,
            reviewer_id=OTHER_ADMIN,
        )

        (call,) = self._events(UserEvent.BLOCK_REQUEST_REASSIGNED)
        self.assertEqual(call.kwargs["subject_type"], USER_SUBJECT_TYPE)
        self.assertEqual(call.kwargs["subject_id"], TARGET)
        self.assertEqual(call.kwargs["actor_id"], RAISER)
        self.assertEqual(
            call.kwargs["details"],
            {
                "requestId": request.id,
                "action": BLOCK_USER,
                "previousReviewerId": REVIEWER,
            },
        )

    # -- deciding -----------------------------------------------------------

    async def test_only_named_reviewer_may_decide(self):
        request = await self._raise()

        with self.assertRaises(PermissionError):
            await self._decide(request.id, actor_id=OTHER_ADMIN, approved=True)

        self.assertFalse(self.people[TARGET].is_blocked)

    async def test_approve_blocks_the_target(self):
        request = await self._raise()
        self.session.commit.reset_mock()

        out = await self._decide(request.id, approved=True)

        self.assertTrue(self.people[TARGET].is_blocked)
        self.assertEqual(self.people[TARGET].blocked_by, REVIEWER)
        self.assertEqual(out.status, ApprovalRequestStatus.APPROVED.value)
        self.assertEqual(out.decided_by, REVIEWER)
        self.assertEqual(out.decided_by_name, "Firstname3 Lastname3")
        self.session.commit.assert_awaited_once()

    async def test_approve_blocks_with_the_reason_from_the_request(self):
        request = await self._raise(reason="second no-show")

        out = await self._decide(request.id, approved=True, note="agreed")

        self.assertEqual(self.people[TARGET].blocked_reason, "second no-show")
        self.assertEqual(out.decision_note, "agreed")

    async def test_approve_a_request_with_no_reason_blocks_with_none(self):
        request = await self._raise(reason=None)

        await self._decide(request.id, approved=True)

        self.assertTrue(self.people[TARGET].is_blocked)
        self.assertIsNone(self.people[TARGET].blocked_reason)
        (blocked,) = self._events(UserEvent.BLOCKED)
        self.assertEqual(blocked.kwargs["details"], {"reason": None})

    async def test_reject_leaves_the_target_alone(self):
        request = await self._raise()

        out = await self._decide(request.id, approved=False, note="not enough")

        self.assertFalse(self.people[TARGET].is_blocked)
        self.assertEqual(out.status, ApprovalRequestStatus.REJECTED.value)
        self.assertEqual(out.decision_note, "not enough")

    async def test_reject_needs_a_note(self):
        request = await self._raise()
        self.session.commit.reset_mock()

        for note in (None, "  "):
            with self.subTest(note=note):
                with self.assertRaises(ValueError):
                    await self._decide(request.id, approved=False, note=note)

        self.assertIs(self.requests.rows[0].status, ApprovalRequestStatus.PENDING)
        self.session.commit.assert_not_awaited()

    async def test_approving_refuses_a_target_blocked_since_the_request(self):
        """Raising's check cannot cover this: an operator may block the person
        directly while the request waits."""
        request = await self._raise()
        self.people[TARGET].is_blocked = True
        self.people[TARGET].blocked_by = ADMIN

        with self.assertRaises(ConflictError) as err:
            await self._decide(request.id, approved=True)

        self.assertEqual(err.exception.code, APPROVAL_CHECKS_FAILED)
        self.assertEqual(self.people[TARGET].blocked_by, ADMIN)
        self.assertIs(self.requests.rows[0].status, ApprovalRequestStatus.PENDING)

    async def test_the_reviewer_cannot_approve_a_request_against_themselves(self):
        """Approving it would be blocking yourself through a second door. The
        row is seeded: raising refuses to create this shape."""
        row = self._seed_request(target_id=str(REVIEWER), reviewer_id=REVIEWER)

        with self.assertRaises(PermissionError):
            await self._decide(row.request_id, approved=True)

        self.assertFalse(self.people[REVIEWER].is_blocked)
        self.assertIs(row.status, ApprovalRequestStatus.PENDING)
        self.session.commit.assert_not_awaited()

    async def test_deciding_twice_is_a_conflict_and_changes_nothing(self):
        """A double submit must apply once and notify once."""
        request = await self._raise()
        await self._decide(request.id, approved=False, note="not enough")
        self.record_event.reset_mock()
        self.session.commit.reset_mock()

        with self.assertRaises(ConflictError):
            await self._decide(request.id, approved=True, note="changed my mind")

        self.assertFalse(self.people[TARGET].is_blocked)
        self.assertIs(self.requests.rows[0].status, ApprovalRequestStatus.REJECTED)
        self.assertEqual(self.requests.rows[0].decision_comment, "not enough")
        self.record_event.assert_not_awaited()
        self.session.commit.assert_not_awaited()

    async def test_decide_checks_standing_before_status(self):
        request = await self._raise()
        await self._decide(request.id, approved=False, note="not enough")

        with self.assertRaises(PermissionError):
            await self._decide(request.id, actor_id=OTHER_ADMIN, approved=True)

    async def test_decide_records_the_outcome_the_email_is_worded_from(self):
        """The renderer and resolver read ``decision`` and ``comment``, and
        find the request through ``requestId``."""
        approved_request = await self._raise()
        await self._decide(approved_request.id, approved=True, note="agreed")

        (call,) = self._events(UserEvent.BLOCK_REQUEST_DECIDED)
        self.assertEqual(call.kwargs["subject_type"], USER_SUBJECT_TYPE)
        self.assertEqual(call.kwargs["subject_id"], TARGET)
        self.assertEqual(call.kwargs["actor_id"], REVIEWER)
        self.assertEqual(
            call.kwargs["details"],
            {
                "requestId": approved_request.id,
                "action": BLOCK_USER,
                "decision": "approved",
                "comment": "agreed",
            },
        )

        # Lift the block, the way an unblock would, so a second request can
        # be raised at all.
        self.people[TARGET].is_blocked = False
        self.record_event.reset_mock()
        rejected_request = await self._raise(actor_id=OTHER_RAISER)
        await self._decide(rejected_request.id, approved=False, note="not enough")

        (call,) = self._events(UserEvent.BLOCK_REQUEST_DECIDED)
        self.assertEqual(
            call.kwargs["details"],
            {
                "requestId": rejected_request.id,
                "action": BLOCK_USER,
                "decision": "rejected",
                "comment": "not enough",
            },
        )

    # -- withdrawing --------------------------------------------------------

    async def test_raiser_may_withdraw_a_pending_request(self):
        request = await self._raise()
        self.session.commit.reset_mock()

        out = await self.service.withdraw(
            self.session, actor_id=RAISER, request_id=request.id
        )

        self.assertEqual(out.status, ApprovalRequestStatus.WITHDRAWN.value)
        self.assertEqual(out.decided_by, RAISER)
        self.assertFalse(self.people[TARGET].is_blocked)
        self.session.commit.assert_awaited_once()
        (call,) = self._events(UserEvent.BLOCK_REQUEST_DECIDED)
        self.assertEqual(call.kwargs["actor_id"], RAISER)
        self.assertEqual(call.kwargs["details"]["decision"], "withdrawn")
        self.assertIsNone(call.kwargs["details"]["comment"])

    async def test_a_withdrawn_request_frees_the_target_for_a_new_one(self):
        request = await self._raise()
        await self.service.withdraw(
            self.session, actor_id=RAISER, request_id=request.id
        )

        again = await self._raise(actor_id=OTHER_RAISER)

        self.assertEqual(again.status, ApprovalRequestStatus.PENDING.value)

    async def test_only_the_raiser_may_withdraw(self):
        request = await self._raise()

        for actor_id in (REVIEWER, OTHER_RAISER):
            with self.subTest(actor_id=actor_id):
                with self.assertRaises(PermissionError):
                    await self.service.withdraw(
                        self.session, actor_id=actor_id, request_id=request.id
                    )

        self.assertIs(self.requests.rows[0].status, ApprovalRequestStatus.PENDING)

    async def test_withdrawing_a_closed_request_is_a_conflict(self):
        request = await self._raise()
        await self._decide(request.id, approved=False, note="not enough")

        with self.assertRaises(ConflictError):
            await self.service.withdraw(
                self.session, actor_id=RAISER, request_id=request.id
            )

        self.assertIs(self.requests.rows[0].status, ApprovalRequestStatus.REJECTED)

    async def test_a_withdrawn_request_cannot_be_decided(self):
        request = await self._raise()
        await self.service.withdraw(
            self.session, actor_id=RAISER, request_id=request.id
        )

        with self.assertRaises(ConflictError):
            await self._decide(request.id, approved=True)

        self.assertFalse(self.people[TARGET].is_blocked)

    # -- blocking directly --------------------------------------------------

    async def test_direct_block_supersedes_a_pending_request(self):
        """The pending request's outcome already happened, and nobody judged
        it -- superseded is not a decision."""
        request = await self._raise()
        self.record_event.reset_mock()
        self.session.commit.reset_mock()

        await self.service.block_directly(
            self.session, actor_id=ADMIN, user_id=TARGET, reason="direct"
        )

        row = self.requests.rows[0]
        self.assertEqual(row.request_id, request.id)
        self.assertIs(row.status, ApprovalRequestStatus.SUPERSEDED)
        self.assertEqual(row.decided_by, ADMIN)
        self.assertIsNone(row.decision_comment)
        self.assertTrue(self.people[TARGET].is_blocked)
        self.assertEqual(self.people[TARGET].blocked_reason, "direct")
        self.assertEqual(self._events(UserEvent.BLOCK_REQUEST_DECIDED), [])
        self.session.commit.assert_awaited_once()

    async def test_direct_block_leaves_other_targets_requests_alone(self):
        other = self._seed_request(target_id=str(OTHER_RAISER))

        await self.service.block_directly(
            self.session, actor_id=ADMIN, user_id=TARGET, reason="direct"
        )

        self.assertIs(other.status, ApprovalRequestStatus.PENDING)

    async def test_a_superseded_request_cannot_be_decided(self):
        request = await self._raise()
        await self.service.block_directly(
            self.session, actor_id=ADMIN, user_id=TARGET, reason="direct"
        )
        self.record_event.reset_mock()

        with self.assertRaises(ConflictError):
            await self._decide(request.id, approved=True)

        self.assertIs(self.requests.rows[0].status, ApprovalRequestStatus.SUPERSEDED)
        self.assertEqual(self.people[TARGET].blocked_by, ADMIN)
        self.record_event.assert_not_awaited()

    async def test_direct_block_refuses_someone_already_blocked(self):
        self.people[TARGET].is_blocked = True

        with self.assertRaises(ValueError):
            await self.service.block_directly(
                self.session, actor_id=ADMIN, user_id=TARGET, reason="again"
            )

        self.session.commit.assert_not_awaited()

    async def test_direct_block_with_no_pending_request_closes_nothing(self):
        await self.service.block_directly(
            self.session, actor_id=ADMIN, user_id=TARGET, reason="direct"
        )

        self.assertEqual(self.requests.rows, [])
        self.assertTrue(self.people[TARGET].is_blocked)
        self.session.commit.assert_awaited_once()

    async def test_block_self_is_rejected(self):
        with self.assertRaises(PermissionError):
            await self.service.block_directly(
                self.session, actor_id=ADMIN, user_id=ADMIN, reason="r"
            )

        self.assertFalse(self.people[ADMIN].is_blocked)
        self.session.commit.assert_not_awaited()

    # -- the reviewer's queue -----------------------------------------------

    async def test_list_pending_for_reviewer_asks_for_block_requests_only(self):
        spy = AsyncMock(wraps=self.approvals.list_pending_for_reviewer)
        self.approvals.list_pending_for_reviewer = spy

        await self.service.list_pending_for_reviewer(self.session, REVIEWER)

        spy.assert_awaited_once_with(self.session, REVIEWER, [BLOCK_USER])

    async def test_list_pending_for_reviewer_skips_other_approvals(self):
        await self._raise()
        self._seed_request(
            action="job_review", target_type="job", target_id="41", raised_by=ADMIN
        )
        self.users_repo.get_all_by_ids.reset_mock()

        out = await self.service.list_pending_for_reviewer(self.session, REVIEWER)

        self.assertEqual([row.target_user_id for row in out], [TARGET])
        self.assertEqual(out[0].target_name, "Firstname5 Lastname5")
        self.assertEqual(out[0].reviewer_name, "Firstname3 Lastname3")
        self.users_repo.get_all_by_ids.assert_awaited_once()

    async def test_empty_queue_needs_no_lookup(self):
        self.users_repo.get_all_by_ids.reset_mock()

        out = await self.service.list_pending_for_reviewer(self.session, REVIEWER)

        self.assertEqual(out, [])
        self.users_repo.get_all_by_ids.assert_not_awaited()

    # -- what the raiser can read back --------------------------------------

    async def test_list_pending_raised_by_actor_asks_for_block_requests_only(self):
        spy = AsyncMock(wraps=self.approvals.list_pending_raised_by)
        self.approvals.list_pending_raised_by = spy

        await self.service.list_pending_raised_by_actor(self.session, RAISER)

        spy.assert_awaited_once_with(self.session, RAISER, [BLOCK_USER])

    async def test_raiser_reads_back_the_request_they_raised(self):
        await self._raise()
        self._seed_request(action="job_review", target_type="job", target_id="41")

        out = await self.service.list_pending_raised_by_actor(self.session, RAISER)

        self.assertEqual(len(out), 1)
        self.assertEqual(out[0].target_user_id, TARGET)
        self.assertEqual(out[0].reviewer_id, REVIEWER)
        self.assertEqual(out[0].raised_from, "recruiting_application")

    async def test_raiser_does_not_read_back_someone_elses_request(self):
        await self._raise()

        out = await self.service.list_pending_raised_by_actor(
            self.session, OTHER_RAISER
        )

        self.assertEqual(out, [])


if __name__ == "__main__":
    unittest.main()
