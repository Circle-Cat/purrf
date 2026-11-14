"""Which mentorship rounds still hold someone, so their account cannot be
deactivated until the mentorship admins have dealt with them. Every round,
person and pair in the fixture has a distinct id."""

import unittest
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

from backend.common.mentorship_enums import (
    ApprovalStatus,
    PairStatus,
    ParticipantRole,
)
from backend.mentorship.open_participation_service import OpenParticipationService
from backend.mentorship.withdraw_participant_handler import WITHDRAW_PARTICIPANT

PERSON = 41
PAST, SPRING, SUMMER, AUTUMN, WINTER = 6, 7, 8, 9, 10


def _round(round_id, name, under_way=True):
    now = datetime.now(timezone.utc)
    if under_way:
        start, end = now - timedelta(days=10), now + timedelta(days=10)
    else:
        start, end = now - timedelta(days=200), now - timedelta(days=100)
    return SimpleNamespace(
        round_id=round_id,
        name=name,
        promotion_start_at=start,
        feedback_deadline_at=end,
    )


def _pair(pair_id, status=PairStatus.ACTIVE):
    return SimpleNamespace(pair_id=pair_id, status=status)


def _reg(status, role=ParticipantRole.MENTOR):
    return SimpleNamespace(approval_status=status, participant_role=role)


class OpenParticipationServiceTest(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.rounds = [
            _round(SPRING, "Spring 2026"),
            _round(SUMMER, "Summer 2026"),
            _round(AUTUMN, "Autumn 2026"),
            _round(WINTER, "Winter 2026"),
            _round(PAST, "Fall 2025", under_way=False),
        ]
        self.regs = {
            SPRING: _reg(ApprovalStatus.MATCHED),
            SUMMER: _reg(ApprovalStatus.SIGNED_UP, ParticipantRole.MENTEE),
            AUTUMN: _reg(ApprovalStatus.WITHDRAWN),
            WINTER: _reg(ApprovalStatus.REJECTED),
            PAST: _reg(ApprovalStatus.MATCHED),
        }
        self.pairs_of = {
            SPRING: [_pair(601), _pair(602), _pair(603, PairStatus.INACTIVE)],
            SUMMER: [],
            AUTUMN: [],
            WINTER: [],
            PAST: [_pair(600)],
        }
        participants = MagicMock()
        participants.list_registered_rounds_by_user_ids = AsyncMock(
            side_effect=lambda session, ids: {PERSON: self.rounds}
        )
        participants.get_by_user_id_and_round_id = AsyncMock(
            side_effect=lambda session, user_id, round_id: self.regs.get(round_id)
        )
        pairs = MagicMock()
        pairs.get_pairs_by_user_and_round = AsyncMock(
            side_effect=lambda session, user_id, round_id: self.pairs_of[round_id]
        )
        self.approvals = MagicMock()
        self.approvals.list_pending_for_targets = AsyncMock(return_value={})
        self.session = MagicMock()
        self.service = OpenParticipationService(
            participants_repository=participants,
            pairs_repository=pairs,
            approval_service=self.approvals,
            logger=MagicMock(),
        )

    async def test_lists_only_rounds_under_way_the_person_is_still_in(self):
        rounds = await self.service.list_open(self.session, PERSON)

        self.assertEqual(
            [(r.round_id, r.round_name) for r in rounds],
            [(SPRING, "Spring 2026"), (SUMMER, "Summer 2026")],
        )

    async def test_names_the_role_and_counts_only_active_pairs(self):
        spring, summer = await self.service.list_open(self.session, PERSON)

        self.assertEqual((spring.role, spring.pair_count), ("mentor", 2))
        self.assertEqual((summer.role, summer.pair_count), ("mentee", 0))

    async def test_flags_a_withdrawal_awaiting_approval(self):
        self.approvals.list_pending_for_targets = AsyncMock(
            return_value={f"{SPRING}:{PERSON}": SimpleNamespace(request_id=5)}
        )

        spring, summer = await self.service.list_open(self.session, PERSON)

        self.approvals.list_pending_for_targets.assert_awaited_once_with(
            self.session,
            WITHDRAW_PARTICIPANT,
            [f"{SPRING}:{PERSON}", f"{SUMMER}:{PERSON}"],
        )
        self.assertTrue(spring.withdraw_pending)
        self.assertFalse(summer.withdraw_pending)

    async def test_a_registration_with_no_role_is_still_open(self):
        self.regs[SUMMER] = _reg(ApprovalStatus.UN_MATCHED, role=None)

        rounds = await self.service.list_open(self.session, PERSON)

        self.assertIsNone(rounds[1].role)

    async def test_nothing_open_reads_no_approvals(self):
        self.rounds = [_round(PAST, "Fall 2025", under_way=False)]

        self.assertEqual(await self.service.list_open(self.session, PERSON), [])
        self.approvals.list_pending_for_targets.assert_not_awaited()


if __name__ == "__main__":
    unittest.main()
