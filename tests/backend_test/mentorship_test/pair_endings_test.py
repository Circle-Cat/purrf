"""Who goes from matched to un_matched once a pair has ended: only someone
left with no active pair in the round, and only from matched."""

import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

from backend.common.mentorship_enums import ApprovalStatus, PairStatus
from backend.mentorship.pair_endings import unmatch_if_unpaired

ROUND = 7
MENTOR = 11
MENTEE = 21
OTHER_MENTEE = 22
LEFT = 23


def _pair(pair_id, mentee_id, status):
    return SimpleNamespace(
        pair_id=pair_id, mentor_id=MENTOR, mentee_id=mentee_id, status=status
    )


class UnmatchIfUnpairedTest(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.ended = _pair(501, MENTEE, PairStatus.INACTIVE)
        self.live = _pair(502, OTHER_MENTEE, PairStatus.ACTIVE)
        self.left_pair = _pair(503, LEFT, PairStatus.INACTIVE)
        by_user = {
            MENTOR: [self.ended, self.live, self.left_pair],
            MENTEE: [self.ended],
            OTHER_MENTEE: [self.live],
            LEFT: [self.left_pair],
        }
        self.pairs = MagicMock()
        self.pairs.get_pairs_by_user_and_round = AsyncMock(
            side_effect=lambda session, user_id, round_id: by_user[user_id]
        )
        self.registrations = {
            MENTOR: SimpleNamespace(approval_status=ApprovalStatus.MATCHED),
            MENTEE: SimpleNamespace(approval_status=ApprovalStatus.MATCHED),
            OTHER_MENTEE: SimpleNamespace(approval_status=ApprovalStatus.MATCHED),
            LEFT: SimpleNamespace(approval_status=ApprovalStatus.WITHDRAWN),
        }
        self.participants = MagicMock()
        self.participants.get_by_user_id_and_round_id = AsyncMock(
            side_effect=lambda session, user_id, round_id: self.registrations.get(
                user_id
            )
        )
        self.session = AsyncMock()

    async def _run(self, user_ids):
        return await unmatch_if_unpaired(
            self.session,
            participants_repository=self.participants,
            pairs_repository=self.pairs,
            round_id=ROUND,
            user_ids=user_ids,
        )

    async def test_someone_left_with_no_active_pair_becomes_un_matched(self):
        moved = await self._run([MENTEE])

        self.assertEqual(moved, {MENTEE})
        self.assertIs(
            self.registrations[MENTEE].approval_status, ApprovalStatus.UN_MATCHED
        )

    async def test_someone_with_another_active_pair_stays_matched(self):
        moved = await self._run([MENTOR, OTHER_MENTEE])

        self.assertEqual(moved, set())
        self.assertIs(
            self.registrations[MENTOR].approval_status, ApprovalStatus.MATCHED
        )

    async def test_only_matched_moves(self):
        moved = await self._run([LEFT])

        self.assertEqual(moved, set())
        self.assertIs(
            self.registrations[LEFT].approval_status, ApprovalStatus.WITHDRAWN
        )

    async def test_someone_not_registered_is_skipped(self):
        del self.registrations[MENTEE]

        self.assertEqual(await self._run([MENTEE]), set())

    async def test_the_pairs_are_read_in_this_round(self):
        await self._run([MENTEE])

        self.pairs.get_pairs_by_user_and_round.assert_awaited_once_with(
            session=self.session, user_id=MENTEE, round_id=ROUND
        )


if __name__ == "__main__":
    unittest.main()
