"""What blocking someone does to their mentorship: the pairs in rounds under
way end, they leave those rounds, and partners left with nothing go back to
un_matched. Everyone in the fixture has a distinct id and name."""

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
from backend.mentorship.mentorship_block_service import (
    CALENDAR_REFUSED,
    MentorshipBlockService,
)

BLOCKED = 41
ANN = 51  # Zed's mentee in round 7, no other pair
BO = 52  # Zed's mentee in round 7, no other pair
MO = 61  # Zed's mentor in round 8, also mentors Cy
CY = 62
OLD = 50  # Zed's mentee in a past round
ACTOR = 90
PAST, SEVEN, EIGHT, NINE = 6, 7, 8, 9


def _round(round_id, under_way=True):
    now = datetime.now(timezone.utc)
    if under_way:
        start, end = now - timedelta(days=10), now + timedelta(days=10)
    else:
        start, end = now - timedelta(days=200), now - timedelta(days=100)
    return SimpleNamespace(
        round_id=round_id, promotion_start_at=start, feedback_deadline_at=end
    )


def _pair(pair_id, round_id, mentor_id, mentee_id):
    return SimpleNamespace(
        pair_id=pair_id,
        round_id=round_id,
        mentor_id=mentor_id,
        mentee_id=mentee_id,
        status=PairStatus.ACTIVE,
    )


class MentorshipBlockServiceTest(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.p600 = _pair(600, PAST, BLOCKED, OLD)
        self.p601 = _pair(601, SEVEN, BLOCKED, ANN)
        self.p602 = _pair(602, SEVEN, BLOCKED, BO)
        self.p603 = _pair(603, EIGHT, MO, BLOCKED)
        self.p604 = _pair(604, EIGHT, MO, CY)
        self.pairs_of = {
            (BLOCKED, PAST): [self.p600],
            (BLOCKED, SEVEN): [self.p601, self.p602],
            (BLOCKED, EIGHT): [self.p603],
            (BLOCKED, NINE): [],
            (ANN, SEVEN): [self.p601],
            (BO, SEVEN): [self.p602],
            (MO, EIGHT): [self.p603, self.p604],
        }
        self.pairs = MagicMock()
        self.pairs.get_pairs_by_user_and_round = AsyncMock(
            side_effect=lambda session, user_id, round_id: self.pairs_of[
                (user_id, round_id)
            ]
        )
        self.regs = {
            (BLOCKED, SEVEN): SimpleNamespace(approval_status=ApprovalStatus.MATCHED),
            (BLOCKED, EIGHT): SimpleNamespace(approval_status=ApprovalStatus.MATCHED),
            (BLOCKED, NINE): SimpleNamespace(approval_status=ApprovalStatus.SIGNED_UP),
            (ANN, SEVEN): SimpleNamespace(approval_status=ApprovalStatus.MATCHED),
            (BO, SEVEN): SimpleNamespace(approval_status=ApprovalStatus.MATCHED),
            (MO, EIGHT): SimpleNamespace(approval_status=ApprovalStatus.MATCHED),
        }
        self.participants = MagicMock()
        self.participants.list_registered_rounds_by_user_ids = AsyncMock(
            return_value={
                BLOCKED: [
                    _round(NINE),
                    _round(EIGHT),
                    _round(SEVEN),
                    _round(PAST, under_way=False),
                ]
            }
        )
        self.participants.get_by_user_id_and_round_id = AsyncMock(
            side_effect=lambda session, user_id, round_id: self.regs.get((
                user_id,
                round_id,
            ))
        )
        self.order = []
        self.cancelled = {601: 2, 602: 0, 603: 1}

        async def cancel(session, pair_ids):
            self.order.append(("cancel", list(pair_ids)))
            return self.cancelled[pair_ids[0]]

        self.meetings = MagicMock()
        self.meetings.cancel_upcoming_for_pairs = AsyncMock(side_effect=cancel)
        self.meetings.count_upcoming_for_pairs = AsyncMock(return_value=3)
        self.notes = MagicMock()
        self.notes.create = AsyncMock()
        names = {
            BLOCKED: ("Zed", "Block"),
            ANN: ("Ann", "Lee"),
            BO: ("Bo", "Ng"),
            MO: ("Mo", "Fox"),
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
        self.session = MagicMock()
        self.session.flush = AsyncMock(
            side_effect=lambda: self.order.append(("flush",))
        )
        self.service = MentorshipBlockService(
            participants_repository=self.participants,
            pairs_repository=self.pairs,
            meeting_service=self.meetings,
            note_repository=self.notes,
            users_repository=self.users,
            logger=MagicMock(),
        )

    async def _block(self, request_id=None):
        await self.service.end_for_blocked_user(
            self.session, user_id=BLOCKED, actor_id=ACTOR, request_id=request_id
        )

    def _notes(self):
        return [call.kwargs for call in self.notes.create.await_args_list]

    async def test_only_pairs_in_rounds_under_way_end(self):
        await self._block()

        for pair in (self.p601, self.p602, self.p603):
            self.assertIs(pair.status, PairStatus.INACTIVE, pair.pair_id)
        self.assertIs(self.p600.status, PairStatus.ACTIVE)
        self.assertIs(self.p604.status, PairStatus.ACTIVE)

    async def test_ended_pairs_are_flushed_before_meetings_are_cancelled_pair_by_pair(
        self,
    ):
        await self._block()

        self.assertEqual(
            self.order,
            [("flush",), ("cancel", [603]), ("cancel", [601]), ("cancel", [602])],
        )

    async def test_the_blocked_person_leaves_each_round_whose_pairs_ended(self):
        await self._block()

        self.assertIs(
            self.regs[(BLOCKED, SEVEN)].approval_status, ApprovalStatus.WITHDRAWN
        )
        self.assertIs(
            self.regs[(BLOCKED, EIGHT)].approval_status, ApprovalStatus.WITHDRAWN
        )
        self.assertIs(
            self.regs[(BLOCKED, NINE)].approval_status, ApprovalStatus.SIGNED_UP
        )

    async def test_only_partners_left_with_no_pair_become_un_matched(self):
        await self._block()

        self.assertIs(
            self.regs[(ANN, SEVEN)].approval_status, ApprovalStatus.UN_MATCHED
        )
        self.assertIs(self.regs[(BO, SEVEN)].approval_status, ApprovalStatus.UN_MATCHED)
        self.assertIs(self.regs[(MO, EIGHT)].approval_status, ApprovalStatus.MATCHED)

    async def test_notes_say_what_happened_without_the_block_reason(self):
        await self._block()

        bodies = {(n["user_id"], n["round_id"]): n["body"] for n in self._notes()}
        self.assertEqual(
            bodies,
            {
                (BLOCKED, EIGHT): "matched -> withdrawn: blocked. Pairs ended: "
                "Mo Fox (pair 603). Upcoming meetings cancelled: 1.",
                (MO, EIGHT): "Pair ended: Zed Block was blocked. "
                "1 upcoming meetings cancelled.",
                (BLOCKED, SEVEN): "matched -> withdrawn: blocked. Pairs ended: "
                "Ann Lee (pair 601), Bo Ng (pair 602). "
                "Upcoming meetings cancelled: 2.",
                (ANN, SEVEN): "Pair ended: Zed Block was blocked; matched -> "
                "un_matched. 2 upcoming meetings cancelled.",
                (BO, SEVEN): "Pair ended: Zed Block was blocked; matched -> "
                "un_matched. 0 upcoming meetings cancelled.",
            },
        )

    async def test_notes_carry_the_pair_the_request_and_the_actor(self):
        await self._block(request_id=901)

        for note in self._notes():
            self.assertIs(note["tag"], ParticipantNoteTag.STATUS_CHANGE)
            self.assertEqual(note["author_user_id"], ACTOR)
            self.assertEqual(note["request_id"], 901)
        pair_of = {(n["user_id"], n["round_id"]): n["pair_id"] for n in self._notes()}
        self.assertEqual(pair_of[(ANN, SEVEN)], 601)
        self.assertEqual(pair_of[(MO, EIGHT)], 603)
        self.assertIsNone(pair_of[(BLOCKED, SEVEN)])

    async def test_a_registration_that_already_left_is_noted_but_not_moved(self):
        self.regs[(BLOCKED, SEVEN)].approval_status = ApprovalStatus.REJECTED

        await self._block()

        self.assertIs(
            self.regs[(BLOCKED, SEVEN)].approval_status, ApprovalStatus.REJECTED
        )
        bodies = {(n["user_id"], n["round_id"]): n["body"] for n in self._notes()}
        self.assertEqual(
            bodies[(BLOCKED, SEVEN)],
            "Blocked. Pairs ended: Ann Lee (pair 601), Bo Ng (pair 602). "
            "Upcoming meetings cancelled: 2.",
        )

    async def test_a_calendar_refusal_says_nobody_was_blocked(self):
        self.meetings.cancel_upcoming_for_pairs = AsyncMock(
            side_effect=ConflictError("refused", code="calendar_cancel_failed")
        )

        with self.assertRaises(ConflictError) as caught:
            await self._block()

        self.assertEqual(caught.exception.code, "calendar_cancel_failed")
        self.assertEqual(str(caught.exception), CALENDAR_REFUSED)
        self.notes.create.assert_not_awaited()
        self.assertIs(
            self.regs[(BLOCKED, SEVEN)].approval_status, ApprovalStatus.MATCHED
        )

    async def test_someone_with_no_pair_under_way_is_left_alone(self):
        self.participants.list_registered_rounds_by_user_ids.return_value = {
            BLOCKED: [_round(NINE), _round(PAST, under_way=False)]
        }

        await self._block()

        self.session.flush.assert_not_awaited()
        self.meetings.cancel_upcoming_for_pairs.assert_not_awaited()
        self.notes.create.assert_not_awaited()

    async def test_preflight_counts_pairs_under_way_and_their_meetings(self):
        self.assertEqual(
            await self.service.preflight_counts(self.session, BLOCKED), (3, 3)
        )
        self.meetings.count_upcoming_for_pairs.assert_awaited_once_with(
            self.session, [603, 601, 602]
        )
        self.assertIs(self.p601.status, PairStatus.ACTIVE)


if __name__ == "__main__":
    unittest.main()
