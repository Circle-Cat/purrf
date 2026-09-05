import unittest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

from backend.admin.block_service import BlockService
from backend.common.permissions import Permission
from backend.common.user_enums import BlockRequestStatus
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

        async def get_pending_for_target(_s, target_user_id):
            return next(
                (
                    r
                    for r in self.rows.values()
                    if r.target_user_id == target_user_id
                    and r.status is BlockRequestStatus.PENDING
                ),
                None,
            )

        async def set_reviewer(_s, request_id, reviewer_id):
            self.rows[request_id].reviewer_id = reviewer_id

        async def close(_s, request_id, *, status, decided_by, decision_note):
            row = self.rows[request_id]
            row.status = status
            row.decided_by = decided_by
            row.decided_at = datetime.now(timezone.utc)
            row.decision_note = decision_note

        self.requests_repo.create = AsyncMock(side_effect=create)
        self.requests_repo.get = AsyncMock(side_effect=get)
        self.requests_repo.get_pending_for_target = AsyncMock(
            side_effect=get_pending_for_target
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

    async def _raise(self, actor_id=RAISER, user_id=TARGET, reason="second no-show",
                     reviewer_id=REVIEWER, raised_from="recruiting_board"):
        return await self.service.raise_request(
            self.session,
            actor_id=actor_id,
            user_id=user_id,
            reason=reason,
            reviewer_id=reviewer_id,
            raised_from=raised_from,
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
            self.session, actor_id=REVIEWER, request_id=first.id,
            approved=False, note="not enough",
        )

        second = await self._raise(actor_id=OTHER_RAISER)

        self.assertEqual(second.status, BlockRequestStatus.PENDING.value)

    # -- reassigning --------------------------------------------------------

    async def test_only_raiser_may_reassign(self):
        request = await self._raise()

        with self.assertRaises(PermissionError):
            await self.service.reassign(
                self.session, actor_id=REVIEWER, request_id=request.id,
                reviewer_id=OTHER_ADMIN,
            )

        out = await self.service.reassign(
            self.session, actor_id=RAISER, request_id=request.id,
            reviewer_id=OTHER_ADMIN,
        )
        self.assertEqual(out.reviewer_id, OTHER_ADMIN)

    async def test_reassign_moves_the_decision_right(self):
        request = await self._raise()
        await self.service.reassign(
            self.session, actor_id=RAISER, request_id=request.id,
            reviewer_id=OTHER_ADMIN,
        )

        with self.assertRaises(PermissionError):
            await self.service.decide(
                self.session, actor_id=REVIEWER, request_id=request.id,
                approved=True, note=None,
            )

        out = await self.service.decide(
            self.session, actor_id=OTHER_ADMIN, request_id=request.id,
            approved=True, note=None,
        )
        self.assertEqual(out.status, BlockRequestStatus.APPROVED.value)

    async def test_reassign_target_must_hold_user_admin(self):
        request = await self._raise()

        with self.assertRaises(ValueError):
            await self.service.reassign(
                self.session, actor_id=RAISER, request_id=request.id,
                reviewer_id=OTHER_RAISER,
            )

    async def test_reassign_a_closed_request_is_rejected(self):
        request = await self._raise()
        await self.service.decide(
            self.session, actor_id=REVIEWER, request_id=request.id,
            approved=False, note=None,
        )

        with self.assertRaises(ValueError):
            await self.service.reassign(
                self.session, actor_id=RAISER, request_id=request.id,
                reviewer_id=OTHER_ADMIN,
            )

    async def test_reassign_unknown_request_raises(self):
        with self.assertRaises(ValueError):
            await self.service.reassign(
                self.session, actor_id=RAISER, request_id=999999,
                reviewer_id=OTHER_ADMIN,
            )

    # -- deciding -----------------------------------------------------------

    async def test_only_named_reviewer_may_decide(self):
        request = await self._raise()

        with self.assertRaises(PermissionError):
            await self.service.decide(
                self.session, actor_id=OTHER_ADMIN, request_id=request.id,
                approved=True, note=None,
            )

    async def test_approve_blocks_the_target(self):
        request = await self._raise()

        out = await self.service.decide(
            self.session, actor_id=REVIEWER, request_id=request.id,
            approved=True, note=None,
        )

        self.assertTrue(self.people[TARGET].is_blocked)
        self.assertEqual(self.people[TARGET].blocked_by, REVIEWER)
        self.assertEqual(out.status, BlockRequestStatus.APPROVED.value)
        self.assertEqual(out.decided_by, REVIEWER)
        self.assertTrue(out.decided_by_name)

    async def test_approve_blocks_with_the_reason_from_the_request(self):
        request = await self._raise(reason="second no-show")

        await self.service.decide(
            self.session, actor_id=REVIEWER, request_id=request.id,
            approved=True, note="agreed",
        )

        self.assertEqual(self.people[TARGET].blocked_reason, "second no-show")

    async def test_reject_leaves_the_target_alone(self):
        request = await self._raise()

        out = await self.service.decide(
            self.session, actor_id=REVIEWER, request_id=request.id,
            approved=False, note="not enough",
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
            self.session, actor_id=REVIEWER, request_id=request.id,
            approved=True, note=None,
        )

        self.session.commit.assert_awaited_once()

    async def test_deciding_twice_is_rejected(self):
        request = await self._raise()
        await self.service.decide(
            self.session, actor_id=REVIEWER, request_id=request.id,
            approved=False, note=None,
        )

        with self.assertRaises(ValueError):
            await self.service.decide(
                self.session, actor_id=REVIEWER, request_id=request.id,
                approved=True, note=None,
            )

    async def test_decide_unknown_request_raises(self):
        with self.assertRaises(ValueError):
            await self.service.decide(
                self.session, actor_id=REVIEWER, request_id=999999,
                approved=True, note=None,
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
