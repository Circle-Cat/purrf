import unittest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

from backend.admin.block_service import BlockService
from backend.common.permissions import Permission
from backend.common.user_enums import (
    USER_SUBJECT_TYPE,
    BlockRequestStatus,
    UserEvent,
)
from backend.entity.block_request_entity import BlockRequestEntity
from backend.entity.users_entity import UsersEntity

TARGET = 5
RAISER = 2
OTHER_RAISER = 6
REVIEWER = 3
OTHER_ADMIN = 4
ADMIN = 7


def _user(user_id, first=None, last=None, preferred=None):
    # Distinctive per person: a one-letter name makes the "does the refusal
    # leak who raised it" assertion match the article in any English sentence.
    first = first if first is not None else f"Firstname{user_id}"
    last = last if last is not None else f"Lastname{user_id}"
    row = UsersEntity(first_name=first, last_name=last, preferred_name=preferred)
    row.user_id = user_id
    row.is_active = True
    row.is_blocked = False
    row.blocked_by = None
    row.blocked_at = None
    row.blocked_reason = None
    return row


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
        self.requests_repo = MagicMock()
        self.perms_repo = MagicMock()
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

        self.rows = {}
        self.next_id = 100

        async def create(_s, **kwargs):
            row = BlockRequestEntity(status=BlockRequestStatus.PENDING, **kwargs)
            row.request_id = self.next_id
            row.created_at = datetime.now(timezone.utc)
            row.decided_by = None
            row.decided_at = None
            row.decision_note = None
            self.rows[self.next_id] = row
            self.next_id += 1
            return row

        async def get(_s, request_id):
            return self.rows.get(request_id)

        async def list_pending_for_target(_s, target_user_id):
            return [
                r
                for r in self.rows.values()
                if r.target_user_id == target_user_id
                and r.status is BlockRequestStatus.PENDING
            ]

        async def set_reviewer(_s, request_id, reviewer_id):
            row = self.rows[request_id]
            if row.status is not BlockRequestStatus.PENDING:
                return False
            row.reviewer_id = reviewer_id
            return True

        async def close(_s, request_id, *, status, decided_by, decision_note):
            row = self.rows[request_id]
            if row.status is not BlockRequestStatus.PENDING:
                return False
            row.status = status
            row.decided_by = decided_by
            row.decided_at = datetime.now(timezone.utc)
            row.decision_note = decision_note
            return True

        self.requests_repo.create = AsyncMock(side_effect=create)
        self.requests_repo.get = AsyncMock(side_effect=get)
        self.requests_repo.list_pending_for_target = AsyncMock(
            side_effect=list_pending_for_target
        )
        self.requests_repo.set_reviewer = AsyncMock(side_effect=set_reviewer)
        self.requests_repo.close = AsyncMock(side_effect=close)
        self.requests_repo.list_pending_for_reviewer = AsyncMock(return_value=[])

        recorder = patch(
            "backend.admin.block_service.record_event", new_callable=AsyncMock
        )
        self.record_event = recorder.start()
        self.addCleanup(recorder.stop)

        self.service = BlockService(
            users_repository=self.users_repo,
            application_repository=self.app_repo,
            application_submission_repository=self.sub_repo,
            application_interview_repository=self.interview_repo,
            interview_scheduling_service=self.interview_svc,
            block_request_repository=self.requests_repo,
            user_permissions_repository=self.perms_repo,
            logger=MagicMock(),
        )

    async def _raise(
        self,
        actor_id=RAISER,
        user_id=TARGET,
        reason="second no-show",
        reviewer_id=REVIEWER,
        raised_from="recruiting_board",
    ):
        return await self.service.raise_request(
            self.session,
            actor_id=actor_id,
            user_id=user_id,
            reason=reason,
            reviewer_id=reviewer_id,
            raised_from=raised_from,
        )

    async def _seed_request(self, **kwargs):
        """A row put straight into the repository, bypassing the service.

        For shapes ``raise_request`` refuses to produce: a second pending row
        against one target, or a request whose reviewer is its own target
        (rows raised before ``_validate_reviewer`` grew that rule).
        """
        return await self.requests_repo.create(
            self.session,
            **{
                "target_user_id": TARGET,
                "raised_by": RAISER,
                "raised_from": "recruiting_board",
                "reason": "second no-show",
                "reviewer_id": REVIEWER,
                **kwargs,
            },
        )

    # -- raising ------------------------------------------------------------

    async def test_raise_returns_a_pending_request_with_names_resolved(self):
        out = await self._raise()

        self.assertEqual(out.status, BlockRequestStatus.PENDING.value)
        self.assertEqual(out.target_user_id, TARGET)
        self.assertEqual(out.reviewer_id, REVIEWER)
        self.assertEqual(out.raised_from, "recruiting_board")
        self.assertTrue(out.target_name)
        self.assertTrue(out.raised_by_name)
        self.assertTrue(out.reviewer_name)
        self.assertIsNone(out.decided_by_name)
        self.session.commit.assert_awaited_once()

    async def test_names_are_resolved_in_one_lookup(self):
        await self._raise()

        self.users_repo.get_all_by_ids.assert_awaited_once()

    async def test_reviewer_must_hold_user_admin(self):
        self.perms_repo.get_active_users_with_permission = AsyncMock(return_value=[])

        with self.assertRaises(ValueError):
            await self._raise()

        self.requests_repo.create.assert_not_awaited()
        self.session.commit.assert_not_awaited()

    async def test_reviewer_is_looked_up_against_user_admin(self):
        await self._raise()

        self.perms_repo.get_active_users_with_permission.assert_awaited_once_with(
            self.session, Permission.USER_ADMIN.value
        )

    async def test_raiser_cannot_name_themselves_as_reviewer(self):
        """Two people is the whole point of the flow."""
        self.perms_repo.get_active_users_with_permission = AsyncMock(
            return_value=[self.people[RAISER]]
        )

        with self.assertRaises(ValueError):
            await self._raise(reviewer_id=RAISER)

        self.requests_repo.create.assert_not_awaited()

    async def test_raiser_cannot_name_the_target_as_reviewer(self):
        """Asking someone to rule on their own blocking is the same failure as
        letting them block themselves, one step earlier."""
        # In the pool, so the refusal can only come from the target rule.
        self.perms_repo.get_active_users_with_permission = AsyncMock(
            return_value=[self.people[REVIEWER], self.people[TARGET]]
        )

        with self.assertRaises(ValueError):
            await self._raise(reviewer_id=TARGET)

        self.requests_repo.create.assert_not_awaited()
        self.session.commit.assert_not_awaited()

    async def test_raised_from_must_fit_the_column(self):
        """raised_from is a String(64): a longer value reaches the database as
        a truncation error and surfaces as a 500 instead of a 400."""
        for raised_from in ("", "x" * 65):
            with self.subTest(length=len(raised_from)):
                with self.assertRaises(ValueError):
                    await self._raise(raised_from=raised_from)

        self.requests_repo.create.assert_not_awaited()

    async def test_raised_from_at_the_limit_is_accepted(self):
        out = await self._raise(raised_from="x" * 64)

        self.assertEqual(out.raised_from, "x" * 64)

    async def test_raise_records_the_event_the_reviewer_is_notified_from(self):
        """``user_recipient_resolvers._request_of`` finds the row through
        ``details["requestId"]``. Renaming the key here would leave the event
        with no recipients and nothing on this side would fail."""
        out = await self._raise()

        kwargs = self.record_event.call_args.kwargs
        self.assertEqual(kwargs["subject_type"], USER_SUBJECT_TYPE)
        self.assertEqual(kwargs["subject_id"], TARGET)
        self.assertEqual(kwargs["actor_id"], RAISER)
        self.assertEqual(kwargs["event_type"], UserEvent.BLOCK_REQUESTED)
        self.assertEqual(kwargs["details"], {"requestId": out.id})

    async def test_unknown_target_is_rejected(self):
        with self.assertRaises(ValueError):
            await self._raise(user_id=999999)

    async def test_second_pending_request_is_rejected_without_leaking(self):
        """The second raiser may not see the first request, so the refusal must
        not carry its reason or who filed it."""
        await self._raise(reason="secret reason")

        with self.assertRaises(ValueError) as err:
            await self._raise(
                actor_id=OTHER_RAISER,
                reason="r2",
                raised_from="recruiting_interviews",
            )

        message = str(err.exception)
        self.assertNotIn("secret reason", message)
        self.assertNotIn(self.people[RAISER].first_name, message)
        self.assertNotIn(str(RAISER), message)

    async def test_a_second_request_is_fine_once_the_first_is_closed(self):
        first = await self._raise()
        await self.service.decide(
            self.session,
            actor_id=REVIEWER,
            request_id=first.id,
            approved=False,
            note="not enough",
        )

        second = await self._raise(actor_id=OTHER_RAISER)

        self.assertEqual(second.status, BlockRequestStatus.PENDING.value)

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

    async def test_reassign_moves_the_decision_right(self):
        request = await self._raise()
        await self.service.reassign(
            self.session,
            actor_id=RAISER,
            request_id=request.id,
            reviewer_id=OTHER_ADMIN,
        )

        with self.assertRaises(PermissionError):
            await self.service.decide(
                self.session,
                actor_id=REVIEWER,
                request_id=request.id,
                approved=True,
                note=None,
            )

        out = await self.service.decide(
            self.session,
            actor_id=OTHER_ADMIN,
            request_id=request.id,
            approved=True,
            note=None,
        )
        self.assertEqual(out.status, BlockRequestStatus.APPROVED.value)

    async def test_reassign_target_must_hold_user_admin(self):
        request = await self._raise()

        with self.assertRaises(ValueError):
            await self.service.reassign(
                self.session,
                actor_id=RAISER,
                request_id=request.id,
                reviewer_id=OTHER_RAISER,
            )

    async def test_reassign_a_closed_request_is_rejected(self):
        request = await self._raise()
        await self.service.decide(
            self.session,
            actor_id=REVIEWER,
            request_id=request.id,
            approved=False,
            note=None,
        )

        with self.assertRaises(ValueError):
            await self.service.reassign(
                self.session,
                actor_id=RAISER,
                request_id=request.id,
                reviewer_id=OTHER_ADMIN,
            )

    async def test_reassign_to_the_current_reviewer_is_rejected(self):
        """A no-op that would still email both "reviewers" -- the same person
        twice -- and log a reassignment that never happened."""
        request = await self._raise()

        with self.assertRaises(ValueError):
            await self.service.reassign(
                self.session,
                actor_id=RAISER,
                request_id=request.id,
                reviewer_id=REVIEWER,
            )

        self.requests_repo.set_reviewer.assert_not_awaited()

    async def test_reassign_cannot_hand_the_request_to_its_target(self):
        request = await self._raise()
        self.perms_repo.get_active_users_with_permission = AsyncMock(
            return_value=[self.people[REVIEWER], self.people[TARGET]]
        )

        with self.assertRaises(ValueError):
            await self.service.reassign(
                self.session,
                actor_id=RAISER,
                request_id=request.id,
                reviewer_id=TARGET,
            )

        self.assertEqual(self.rows[request.id].reviewer_id, REVIEWER)

    async def test_reassign_checks_standing_before_status(self):
        """A closed request must answer a stranger exactly as an open one
        does, or the error message becomes a way to probe who has an open
        block request against them."""
        request = await self._raise()
        await self.service.decide(
            self.session,
            actor_id=REVIEWER,
            request_id=request.id,
            approved=False,
            note=None,
        )

        with self.assertRaises(PermissionError):
            await self.service.reassign(
                self.session,
                actor_id=OTHER_RAISER,
                request_id=request.id,
                reviewer_id=OTHER_ADMIN,
            )

    async def test_reassign_raises_when_the_row_was_closed_under_it(self):
        """set_reviewer only touches a PENDING row and reports whether it did.
        The row read at the top of reassign can be stale, so False is the only
        signal that someone decided it in between."""
        request = await self._raise()
        self.requests_repo.set_reviewer = AsyncMock(return_value=False)
        self.record_event.reset_mock()
        self.session.commit.reset_mock()

        with self.assertRaises(ValueError):
            await self.service.reassign(
                self.session,
                actor_id=RAISER,
                request_id=request.id,
                reviewer_id=OTHER_ADMIN,
            )

        self.record_event.assert_not_awaited()
        self.session.commit.assert_not_awaited()

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

        kwargs = self.record_event.call_args.kwargs
        self.assertEqual(kwargs["subject_type"], USER_SUBJECT_TYPE)
        self.assertEqual(kwargs["subject_id"], TARGET)
        self.assertEqual(kwargs["actor_id"], RAISER)
        self.assertEqual(kwargs["event_type"], UserEvent.BLOCK_REQUEST_REASSIGNED)
        self.assertEqual(
            kwargs["details"],
            {"requestId": request.id, "previousReviewerId": REVIEWER},
        )

    async def test_reassign_unknown_request_raises(self):
        with self.assertRaises(ValueError):
            await self.service.reassign(
                self.session,
                actor_id=RAISER,
                request_id=999999,
                reviewer_id=OTHER_ADMIN,
            )

    # -- deciding -----------------------------------------------------------

    async def test_only_named_reviewer_may_decide(self):
        request = await self._raise()

        with self.assertRaises(PermissionError):
            await self.service.decide(
                self.session,
                actor_id=OTHER_ADMIN,
                request_id=request.id,
                approved=True,
                note=None,
            )

    async def test_approve_blocks_the_target(self):
        request = await self._raise()

        out = await self.service.decide(
            self.session,
            actor_id=REVIEWER,
            request_id=request.id,
            approved=True,
            note=None,
        )

        self.assertTrue(self.people[TARGET].is_blocked)
        self.assertEqual(self.people[TARGET].blocked_by, REVIEWER)
        self.assertEqual(out.status, BlockRequestStatus.APPROVED.value)
        self.assertEqual(out.decided_by, REVIEWER)
        self.assertTrue(out.decided_by_name)

    async def test_approve_blocks_with_the_reason_from_the_request(self):
        request = await self._raise(reason="second no-show")

        await self.service.decide(
            self.session,
            actor_id=REVIEWER,
            request_id=request.id,
            approved=True,
            note="agreed",
        )

        self.assertEqual(self.people[TARGET].blocked_reason, "second no-show")

    async def test_reject_leaves_the_target_alone(self):
        request = await self._raise()

        out = await self.service.decide(
            self.session,
            actor_id=REVIEWER,
            request_id=request.id,
            approved=False,
            note="not enough",
        )

        self.assertFalse(self.people[TARGET].is_blocked)
        self.assertEqual(out.status, BlockRequestStatus.REJECTED.value)
        self.assertEqual(out.decision_note, "not enough")

    async def test_approve_commits_once_after_the_block_lands(self):
        """apply_block does not commit; decide owns the one transaction, so a
        failure while closing the request rolls the block back with it."""
        request = await self._raise()
        self.session.commit.reset_mock()

        await self.service.decide(
            self.session,
            actor_id=REVIEWER,
            request_id=request.id,
            approved=True,
            note=None,
        )

        self.session.commit.assert_awaited_once()

    async def test_deciding_twice_is_rejected(self):
        request = await self._raise()
        await self.service.decide(
            self.session,
            actor_id=REVIEWER,
            request_id=request.id,
            approved=False,
            note=None,
        )

        with self.assertRaises(ValueError):
            await self.service.decide(
                self.session,
                actor_id=REVIEWER,
                request_id=request.id,
                approved=True,
                note=None,
            )

    def _decided_events(self):
        return [
            call
            for call in self.record_event.await_args_list
            if call.kwargs["event_type"] == UserEvent.BLOCK_REQUEST_DECIDED
        ]

    async def test_the_reviewer_cannot_approve_a_request_against_themselves(self):
        """Approving it would be blocking yourself through a second door.

        The row is seeded rather than raised: _validate_reviewer refuses to
        create this shape now, but rows raised before it did still exist.
        """
        row = await self._seed_request(target_user_id=REVIEWER, reviewer_id=REVIEWER)

        with self.assertRaises(PermissionError):
            await self.service.decide(
                self.session,
                actor_id=REVIEWER,
                request_id=row.request_id,
                approved=True,
                note=None,
            )

        self.assertFalse(self.people[REVIEWER].is_blocked)
        self.assertIs(self.rows[row.request_id].status, BlockRequestStatus.PENDING)
        self.session.commit.assert_not_awaited()

    async def test_a_superseded_request_cannot_be_decided(self):
        """Superseded is closed, not pending: its outcome already happened and
        deciding it again would block the target a second time."""
        request = await self._raise()
        await self.service.block_directly(
            self.session, actor_id=ADMIN, user_id=TARGET, reason="direct"
        )
        self.record_event.reset_mock()

        with self.assertRaises(ValueError):
            await self.service.decide(
                self.session,
                actor_id=REVIEWER,
                request_id=request.id,
                approved=True,
                note=None,
            )

        self.assertIs(self.rows[request.id].status, BlockRequestStatus.SUPERSEDED)
        self.assertEqual(self.rows[request.id].decided_by, ADMIN)
        self.assertEqual(self._decided_events(), [])

    async def test_a_second_decision_changes_nothing_and_emails_nobody(self):
        """A double submit must apply once and notify once."""
        request = await self._raise()
        await self.service.decide(
            self.session,
            actor_id=REVIEWER,
            request_id=request.id,
            approved=False,
            note="not enough",
        )
        self.requests_repo.close.reset_mock()
        self.record_event.reset_mock()
        self.session.commit.reset_mock()

        with self.assertRaises(ValueError):
            await self.service.decide(
                self.session,
                actor_id=REVIEWER,
                request_id=request.id,
                approved=True,
                note="changed my mind",
            )

        self.assertFalse(self.people[TARGET].is_blocked)
        self.assertIs(self.rows[request.id].status, BlockRequestStatus.REJECTED)
        self.assertEqual(self.rows[request.id].decision_note, "not enough")
        self.requests_repo.close.assert_not_awaited()
        self.record_event.assert_not_awaited()
        self.session.commit.assert_not_awaited()

    async def test_decide_raises_when_the_row_was_closed_under_it(self):
        """The row read at the top of decide can be stale. close only touches
        a PENDING row and reports whether it did; raising on False rolls the
        block back with the rest of the transaction, so the concurrent pair
        blocks once and emails once."""
        request = await self._raise()
        self.requests_repo.close = AsyncMock(return_value=False)
        self.record_event.reset_mock()
        self.session.commit.reset_mock()

        with self.assertRaises(ValueError):
            await self.service.decide(
                self.session,
                actor_id=REVIEWER,
                request_id=request.id,
                approved=True,
                note=None,
            )

        # apply_block ran before close refused, so the flags are set in memory.
        # Nothing commits, which is what keeps them from reaching the database.
        self.assertEqual(self._decided_events(), [])
        self.session.commit.assert_not_awaited()

    async def test_decide_checks_standing_before_status(self):
        """Same reason as reassign: a stranger must not be able to tell a
        closed request from an open one by which error they get."""
        request = await self._raise()
        await self.service.decide(
            self.session,
            actor_id=REVIEWER,
            request_id=request.id,
            approved=False,
            note=None,
        )

        with self.assertRaises(PermissionError):
            await self.service.decide(
                self.session,
                actor_id=OTHER_ADMIN,
                request_id=request.id,
                approved=True,
                note=None,
            )

    async def test_decide_records_the_outcome_the_email_is_worded_from(self):
        """The renderer picks "approved" or "rejected" off ``approved``, and
        finds the request through ``requestId``."""
        approved_request = await self._raise()
        await self.service.decide(
            self.session,
            actor_id=REVIEWER,
            request_id=approved_request.id,
            approved=True,
            note=None,
        )

        kwargs = self.record_event.call_args.kwargs
        self.assertEqual(kwargs["subject_type"], USER_SUBJECT_TYPE)
        self.assertEqual(kwargs["subject_id"], TARGET)
        self.assertEqual(kwargs["actor_id"], REVIEWER)
        self.assertEqual(kwargs["event_type"], UserEvent.BLOCK_REQUEST_DECIDED)
        self.assertEqual(
            kwargs["details"], {"requestId": approved_request.id, "approved": True}
        )

        rejected_request = await self._raise(actor_id=OTHER_RAISER)
        await self.service.decide(
            self.session,
            actor_id=REVIEWER,
            request_id=rejected_request.id,
            approved=False,
            note=None,
        )

        self.assertEqual(
            self.record_event.call_args.kwargs["details"],
            {"requestId": rejected_request.id, "approved": False},
        )

    async def test_decide_unknown_request_raises(self):
        with self.assertRaises(ValueError):
            await self.service.decide(
                self.session,
                actor_id=REVIEWER,
                request_id=999999,
                approved=True,
                note=None,
            )

    # -- blocking directly --------------------------------------------------

    async def test_direct_block_supersedes_a_pending_request(self):
        """The pending request's outcome already happened, and nobody judged
        it -- superseded is not a decision."""
        request = await self._raise()

        await self.service.block_directly(
            self.session, actor_id=ADMIN, user_id=TARGET, reason="direct"
        )

        self.assertIs(self.rows[request.id].status, BlockRequestStatus.SUPERSEDED)
        self.assertEqual(self.rows[request.id].decided_by, ADMIN)
        self.assertTrue(self.people[TARGET].is_blocked)

    async def test_direct_block_supersedes_every_pending_request(self):
        """raise_request's duplicate check is a read-then-write, so a
        concurrent pair can both land. A row left PENDING here would sit on
        its reviewer's banner forever with nothing left to decide."""
        first = await self._seed_request()
        second = await self._seed_request(
            raised_by=OTHER_RAISER, reviewer_id=OTHER_ADMIN
        )

        await self.service.block_directly(
            self.session, actor_id=ADMIN, user_id=TARGET, reason="direct"
        )

        for row in (first, second):
            with self.subTest(request_id=row.request_id):
                self.assertIs(
                    self.rows[row.request_id].status, BlockRequestStatus.SUPERSEDED
                )
                self.assertEqual(self.rows[row.request_id].decided_by, ADMIN)

    async def test_direct_block_with_no_pending_request_closes_nothing(self):
        await self.service.block_directly(
            self.session, actor_id=ADMIN, user_id=TARGET, reason="direct"
        )

        self.requests_repo.close.assert_not_awaited()
        self.assertTrue(self.people[TARGET].is_blocked)

    async def test_block_self_is_rejected(self):
        with self.assertRaises(PermissionError):
            await self.service.block_directly(
                self.session, actor_id=ADMIN, user_id=ADMIN, reason="r"
            )

        self.assertFalse(self.people[ADMIN].is_blocked)
        self.session.commit.assert_not_awaited()

    async def test_direct_block_commits(self):
        await self.service.block_directly(
            self.session, actor_id=ADMIN, user_id=TARGET, reason="direct"
        )

        self.session.commit.assert_awaited_once()

    # -- the reviewer's queue -----------------------------------------------

    async def test_list_pending_for_reviewer_resolves_names_in_one_lookup(self):
        await self._raise()
        self.requests_repo.list_pending_for_reviewer = AsyncMock(
            return_value=list(self.rows.values())
        )
        self.users_repo.get_all_by_ids.reset_mock()

        out = await self.service.list_pending_for_reviewer(self.session, REVIEWER)

        self.assertEqual(len(out), 1)
        self.assertTrue(out[0].target_name)
        self.assertTrue(out[0].reviewer_name)
        self.users_repo.get_all_by_ids.assert_awaited_once()

    async def test_empty_queue_needs_no_lookup(self):
        self.users_repo.get_all_by_ids.reset_mock()

        out = await self.service.list_pending_for_reviewer(self.session, REVIEWER)

        self.assertEqual(out, [])
        self.users_repo.get_all_by_ids.assert_not_awaited()


if __name__ == "__main__":
    unittest.main()
