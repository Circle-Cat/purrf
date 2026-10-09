"""Withdrawing someone from a round through an approval: when it may be
asked for, what has to still hold when it is approved, and what approving
does.

Every id and name below is distinct on purpose -- raiser, reviewer, the
person withdrawn, each partner and each pair -- so reading one as another
cannot pass."""

import unittest
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

from backend.common.exceptions import ConflictError
from backend.common.mentorship_enums import (
    ApprovalStatus,
    PairStatus,
    ParticipantNoteTag,
)
from backend.entity.approval_request_entity import ApprovalRequestEntity
from backend.mentorship.exempt_matching_handler import exemption_target
from backend.mentorship.withdraw_participant_handler import (
    WITHDRAW_PARTICIPANT,
    WithdrawParticipantHandler,
)

ROUND = 7
PERSON = 21
PARTNER_A = 31
PARTNER_B = 32
OLD_PARTNER = 33
RAISER = 90
REVIEWER = 80


def _round(in_progress=True):
    now = datetime.now(timezone.utc)
    if in_progress:
        start, end = now - timedelta(days=10), now + timedelta(days=10)
    else:
        start, end = now - timedelta(days=60), now - timedelta(days=1)
    return SimpleNamespace(
        round_id=ROUND,
        name="Spring 2026",
        promotion_start_at=start,
        feedback_deadline_at=end,
    )


def _pair(pair_id, mentee_id, status=PairStatus.ACTIVE):
    return SimpleNamespace(
        pair_id=pair_id, mentor_id=PERSON, mentee_id=mentee_id, status=status
    )


def _request(reason="Stopped replying to both mentees"):
    row = ApprovalRequestEntity(
        action=WITHDRAW_PARTICIPANT,
        target_type="round_participant",
        target_id=exemption_target(ROUND, PERSON),
        payload={"round_id": ROUND, "user_id": PERSON},
        reason=reason,
        raised_by=RAISER,
        reviewer_id=REVIEWER,
    )
    row.request_id = 701
    return row


class WithdrawParticipantHandlerTest(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.rounds = MagicMock()
        self.rounds.get_by_round_id = AsyncMock(return_value=_round())
        self.registration = SimpleNamespace(approval_status=ApprovalStatus.MATCHED)
        self.participants = MagicMock()
        self.participants.get_by_user_id_and_round_id = AsyncMock(
            return_value=self.registration
        )
        self.pair_a = _pair(501, PARTNER_A)
        self.pair_b = _pair(502, PARTNER_B)
        self.old_pair = _pair(503, OLD_PARTNER, status=PairStatus.INACTIVE)
        self.pairs = MagicMock()
        self.pairs.get_pairs_by_user_and_round = AsyncMock(
            return_value=[self.pair_a, self.old_pair, self.pair_b]
        )
        self.meetings = MagicMock()
        self.meetings.cancel_upcoming_for_pairs = AsyncMock(return_value=3)
        self.notes = MagicMock()
        self.notes.create = AsyncMock()
        names = {
            PERSON: ("Mia", "Ko"),
            PARTNER_A: ("Ann", "Lee"),
            PARTNER_B: ("Bo", "Ng"),
            OLD_PARTNER: ("Cy", "Park"),
            RAISER: ("Ada", "Raiser"),
            REVIEWER: ("Rae", "Reviewer"),
        }
        self.users = MagicMock()
        self.users.get_all_by_ids = AsyncMock(
            side_effect=lambda session, ids: [
                SimpleNamespace(
                    user_id=uid, first_name=first, last_name=last, preferred_name=None
                )
                for uid, (first, last) in names.items()
                if uid in ids
            ]
        )
        self.session = AsyncMock()
        self.handler = WithdrawParticipantHandler(
            participants_repository=self.participants,
            pairs_repository=self.pairs,
            meeting_service=self.meetings,
            rounds_repository=self.rounds,
            note_repository=self.notes,
            users_repository=self.users,
            logger=MagicMock(),
        )

    async def _check(self, target=None, payload=None):
        await self.handler.check_raise(
            self.session,
            raised_by=RAISER,
            target_id=target or exemption_target(ROUND, PERSON),
            payload=payload or {"round_id": ROUND, "user_id": PERSON},
        )

    def test_it_is_about_the_person_in_the_round(self):
        self.assertEqual(self.handler.action, "withdraw_participant")
        self.assertEqual(self.handler.target_type, "round_participant")
        self.assertEqual(self.handler.subject_id(_request()), ROUND)

    async def test_each_status_still_in_the_round_may_be_withdrawn(self):
        for status in (
            ApprovalStatus.SIGNED_UP,
            ApprovalStatus.MATCHED,
            ApprovalStatus.UN_MATCHED,
        ):
            with self.subTest(status=status):
                self.registration.approval_status = status
                await self._check()

    async def test_the_payload_must_name_the_round_and_person_of_the_target(self):
        for target, payload in (
            ("7:21", {"round_id": ROUND}),
            ("7:22", {"round_id": ROUND, "user_id": PERSON}),
        ):
            with self.subTest(target=target, payload=payload):
                with self.assertRaises(ValueError):
                    await self._check(target=target, payload=payload)

    async def test_a_round_not_in_progress_is_refused(self):
        self.rounds.get_by_round_id.return_value = _round(in_progress=False)

        with self.assertRaises(ConflictError) as caught:
            await self._check()
        self.assertEqual(str(caught.exception), "The round is not in progress.")

    async def test_someone_not_registered_is_refused_by_name(self):
        self.participants.get_by_user_id_and_round_id.return_value = None

        with self.assertRaises(ConflictError) as caught:
            await self._check()
        self.assertEqual(
            str(caught.exception), "Mia Ko is not registered for this round."
        )

    async def test_someone_already_gone_is_refused(self):
        self.registration.approval_status = ApprovalStatus.WITHDRAWN
        with self.assertRaises(ConflictError) as caught:
            await self._check()
        self.assertEqual(str(caught.exception), "Mia Ko has already left this round.")

        self.registration.approval_status = ApprovalStatus.REJECTED
        with self.assertRaises(ConflictError) as caught:
            await self._check()
        self.assertIn("status is rejected", str(caught.exception))

    async def test_at_approval_the_same_conditions_are_rechecked(self):
        self.assertEqual(
            await self.handler.problems_at_approval(self.session, _request()), []
        )

        self.registration.approval_status = ApprovalStatus.REJECTED
        problems = await self.handler.problems_at_approval(self.session, _request())
        self.assertEqual(len(problems), 1)
        self.assertIn("cannot be withdrawn", problems[0])

        self.rounds.get_by_round_id.return_value = _round(in_progress=False)
        self.assertEqual(
            await self.handler.problems_at_approval(self.session, _request()),
            ["The round is not in progress."],
        )

    async def test_approving_ends_only_the_active_pairs_and_their_meetings(self):
        await self.handler.execute(self.session, _request(), actor_id=REVIEWER)

        self.assertIs(self.registration.approval_status, ApprovalStatus.WITHDRAWN)
        self.assertIs(self.pair_a.status, PairStatus.INACTIVE)
        self.assertIs(self.pair_b.status, PairStatus.INACTIVE)
        self.meetings.cancel_upcoming_for_pairs.assert_awaited_once_with(
            self.session, [501, 502]
        )
        # Only the withdrawn person's registration is read; partners keep
        # whatever status they had.
        self.participants.get_by_user_id_and_round_id.assert_awaited_once_with(
            self.session, PERSON, ROUND
        )
        self.session.commit.assert_not_awaited()

    async def test_approving_writes_one_status_change_note_by_the_approver(self):
        await self.handler.execute(self.session, _request(), actor_id=REVIEWER)

        self.notes.create.assert_awaited_once()
        kwargs = self.notes.create.await_args.kwargs
        self.assertEqual(kwargs["user_id"], PERSON)
        self.assertEqual(kwargs["round_id"], ROUND)
        self.assertEqual(kwargs["author_user_id"], REVIEWER)
        self.assertIs(kwargs["tag"], ParticipantNoteTag.STATUS_CHANGE)
        self.assertEqual(kwargs["request_id"], 701)
        body = kwargs["body"]
        self.assertTrue(body.startswith("matched -> withdrawn"), body)
        self.assertIn("Pairs ended: Ann Lee (pair 501), Bo Ng (pair 502).", body)
        self.assertIn("Upcoming meetings cancelled: 3.", body)
        self.assertIn("Raised by Ada Raiser", body)
        self.assertIn("Stopped replying to both mentees", body)
        self.assertIn("approved by Rae Reviewer", body)
        self.assertNotIn("Cy Park", body)
        self.assertNotIn("503", body)

    async def test_withdrawing_before_any_pair_says_so_and_cancels_nothing(self):
        self.registration.approval_status = ApprovalStatus.SIGNED_UP
        self.pairs.get_pairs_by_user_and_round.return_value = []
        self.meetings.cancel_upcoming_for_pairs.return_value = 0

        await self.handler.execute(
            self.session, _request(reason=None), actor_id=REVIEWER
        )

        self.meetings.cancel_upcoming_for_pairs.assert_awaited_once_with(
            self.session, []
        )
        body = self.notes.create.await_args.kwargs["body"]
        self.assertTrue(body.startswith("signed_up -> withdrawn"), body)
        self.assertIn("Pairs ended: none. Upcoming meetings cancelled: 0.", body)
        self.assertIn("reason: none given", body)

    async def test_a_calendar_refusal_stops_before_the_note(self):
        self.meetings.cancel_upcoming_for_pairs.side_effect = ConflictError(
            "1 upcoming meeting(s) could not be cancelled",
            code="calendar_cancel_failed",
        )

        with self.assertRaises(ConflictError):
            await self.handler.execute(self.session, _request(), actor_id=REVIEWER)
        self.notes.create.assert_not_awaited()

    async def test_events_snapshot_the_round_and_the_person(self):
        details = await self.handler.event_details(self.session, _request())

        self.assertEqual(details, {"roundName": "Spring 2026", "personName": "Mia Ko"})


if __name__ == "__main__":
    unittest.main()
