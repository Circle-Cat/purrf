"""Reading a round and its history into the eligibility check."""

import unittest
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

from backend.common.mentorship_enums import (
    ApprovalStatus,
    PairStatus,
    ParticipantNoteTag,
    ParticipantRole,
    TrainingCategory,
    TrainingStatus,
)
from backend.mentorship.matching_eligibility import HistoryFinding, IneligibleReason
from backend.mentorship.matching_eligibility_service import MatchingEligibilityService
from backend.repository.mentorship_participant_note_repository import TaggedNote

MENTOR_COURSE = TrainingCategory.MENTORSHIP_MENTOR_ONBOARDING
MENTEE_COURSE = TrainingCategory.MENTORSHIP_MENTEE_ONBOARDING


def _round(round_id, month, required=5):
    return SimpleNamespace(
        round_id=round_id,
        meetings_completion_deadline_at=(
            datetime(2026, month, 1, tzinfo=timezone.utc) if month else None
        ),
        required_meetings=required,
    )


def _registration(
    user_id,
    role,
    *,
    status=ApprovalStatus.SIGNED_UP,
    max_partners=None,
    blocked=False,
    active=True,
):
    user = SimpleNamespace(user_id=user_id, is_blocked=blocked, is_active=active)
    participant = SimpleNamespace(
        participant_role=role, approval_status=status, max_partners=max_partners
    )
    return user, participant


def _training(user_id, category, status=TrainingStatus.DONE):
    return SimpleNamespace(user_id=user_id, category=category, status=status)


def _pair(pair_id, round_id, mentor_id, mentee_id, *, active=True):
    return SimpleNamespace(
        pair_id=pair_id,
        round_id=round_id,
        mentor_id=mentor_id,
        mentee_id=mentee_id,
        status=PairStatus.ACTIVE if active else PairStatus.INACTIVE,
    )


# Fixed instants, compared only with each other: an exemption at hour 0 and
# marks hours either side of it.
T0 = datetime(2026, 1, 1, tzinfo=timezone.utc)
EXEMPTION = ParticipantNoteTag.MATCHING_EXEMPTION
NO_SHOW_TAG = ParticipantNoteTag.NO_SHOW
RED_FLAG_TAG = ParticipantNoteTag.RED_FLAG


def _note(user_id, round_id, tag, hours=0):
    return TaggedNote(user_id, round_id, tag, T0 + timedelta(hours=hours))


class MatchingEligibilityServiceTest(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        # Round ids out of time order on purpose: 30 is the current round.
        self.rounds = [_round(10, 12), _round(30, 9), _round(20, 5), _round(40, None)]
        self.rounds_repo = MagicMock()
        self.rounds_repo.get_all_rounds = AsyncMock(return_value=self.rounds)
        self.participants_repo = MagicMock()
        self.participants_repo.list_round_registrations = AsyncMock(return_value=[])
        self.participants_repo.list_quitters_by_round = AsyncMock(return_value={})
        self.pairs_repo = MagicMock()
        self.pairs_repo.get_active_pairs_by_round = AsyncMock(return_value=[])
        self.pairs_repo.list_pairs_with_meeting_counts = AsyncMock(return_value=[])
        self.training_repo = MagicMock()
        self.training_repo.get_training_by_user_ids_and_categories = AsyncMock(
            return_value=[]
        )
        self.notes_repo = MagicMock()
        self.notes_repo.list_tagged = AsyncMock(return_value=[])
        self.service = MatchingEligibilityService(
            participants_repository=self.participants_repo,
            pairs_repository=self.pairs_repo,
            rounds_repository=self.rounds_repo,
            training_repository=self.training_repo,
            note_repository=self.notes_repo,
            logger=MagicMock(),
        )
        self.session = MagicMock()

    async def test_an_unknown_round_is_refused(self):
        with self.assertRaises(ValueError):
            await self.service.ineligible_by_user(self.session, 99)

    async def test_a_round_nobody_registered_for_has_nobody(self):
        self.assertEqual(await self.service.ineligible_by_user(self.session, 30), {})

    async def test_training_is_read_for_the_role_registered_as(self):
        self.participants_repo.list_round_registrations.return_value = [
            _registration(1, ParticipantRole.MENTOR),
            _registration(2, ParticipantRole.MENTEE),
        ]
        # 1 finished the mentee course, not the mentor one; 2 finished hers.
        self.training_repo.get_training_by_user_ids_and_categories.return_value = [
            _training(1, MENTEE_COURSE),
            _training(1, MENTOR_COURSE, TrainingStatus.IN_PROGRESS),
            _training(2, MENTEE_COURSE),
        ]

        result = await self.service.ineligible_by_user(self.session, 30)

        self.assertEqual(result, {1: [IneligibleReason.TRAINING_NOT_DONE], 2: []})

    async def test_open_slots_count_the_round_s_active_pairs(self):
        self.participants_repo.list_round_registrations.return_value = [
            _registration(1, ParticipantRole.MENTOR, max_partners=2),
            _registration(2, ParticipantRole.MENTOR),
            _registration(3, ParticipantRole.MENTEE, status=ApprovalStatus.MATCHED),
            _registration(4, ParticipantRole.MENTEE),
        ]
        self.training_repo.get_training_by_user_ids_and_categories.return_value = [
            _training(1, MENTOR_COURSE),
            _training(2, MENTOR_COURSE),
            _training(3, MENTEE_COURSE),
            _training(4, MENTEE_COURSE),
        ]
        self.pairs_repo.get_active_pairs_by_round.return_value = [
            _pair(1, 30, 1, 3),
            _pair(2, 30, 2, 9),
        ]

        result = await self.service.ineligible_by_user(self.session, 30)

        self.assertEqual(result[1], [])
        self.assertEqual(result[2], [IneligibleReason.NO_OPEN_SLOTS])
        self.assertEqual(result[3], [IneligibleReason.NO_OPEN_SLOTS])
        self.assertEqual(result[4], [])

    async def test_account_and_status_are_read_from_the_registration(self):
        self.participants_repo.list_round_registrations.return_value = [
            _registration(
                1,
                ParticipantRole.MENTEE,
                blocked=True,
                active=False,
                status=ApprovalStatus.REJECTED,
            ),
        ]
        self.training_repo.get_training_by_user_ids_and_categories.return_value = [
            _training(1, MENTEE_COURSE),
        ]

        result = await self.service.ineligible_by_user(self.session, 30)

        self.assertEqual(
            result[1],
            [
                IneligibleReason.BLOCKED,
                IneligibleReason.DEACTIVATED,
                IneligibleReason.NOT_TAKING_PART,
            ],
        )

    async def test_history_comes_from_earlier_rounds_latest_first(self):
        self.participants_repo.list_round_registrations.return_value = [
            _registration(1, ParticipantRole.MENTEE),
        ]
        self.training_repo.get_training_by_user_ids_and_categories.return_value = [
            _training(1, MENTEE_COURSE),
        ]
        # Round 20 (May) is the only earlier one; 10 is later, 40 has no date.
        self.pairs_repo.list_pairs_with_meeting_counts.side_effect = [
            [(_pair(5, 20, 7, 1), 2)],
            [],
        ]

        result = await self.service.ineligible_by_user(self.session, 30)

        self.assertEqual(result[1], [IneligibleReason.MEETINGS_SHORT])
        first_call = self.pairs_repo.list_pairs_with_meeting_counts.await_args_list[0]
        self.assertEqual(first_call.args[1:], ([20], [1]))

    async def test_a_mentor_s_mentee_is_judged_by_her_pairs_with_others_too(self):
        self.participants_repo.list_round_registrations.return_value = [
            _registration(1, ParticipantRole.MENTOR),
        ]
        self.training_repo.get_training_by_user_ids_and_categories.return_value = [
            _training(1, MENTOR_COURSE),
        ]
        # 1 took mentee 21 over from 9, who quit after one meeting.
        self.pairs_repo.list_pairs_with_meeting_counts.side_effect = [
            [(_pair(6, 20, 1, 21), 4)],
            [(_pair(5, 20, 9, 21, active=False), 1), (_pair(6, 20, 1, 21), 4)],
        ]
        self.participants_repo.list_quitters_by_round.return_value = {20: set()}

        result = await self.service.ineligible_by_user(self.session, 30)

        self.assertEqual(result[1], [])
        second_call = self.pairs_repo.list_pairs_with_meeting_counts.await_args_list[1]
        self.assertEqual(second_call.args[1:], ([20], [21]))

    async def test_quitting_is_read_from_the_quitters_registrations(self):
        self.participants_repo.list_round_registrations.return_value = [
            _registration(1, ParticipantRole.MENTEE),
        ]
        self.training_repo.get_training_by_user_ids_and_categories.return_value = [
            _training(1, MENTEE_COURSE),
        ]
        self.pairs_repo.list_pairs_with_meeting_counts.side_effect = [
            [(_pair(5, 20, 7, 1, active=False), 1)],
            [],
        ]
        self.participants_repo.list_quitters_by_round.return_value = {20: {1}}

        result = await self.service.ineligible_by_user(self.session, 30)

        self.assertEqual(result[1], [IneligibleReason.QUIT_AFTER_MATCH])

    def _registered_and_trained(self, *user_ids):
        self.participants_repo.list_round_registrations.return_value = [
            _registration(u, ParticipantRole.MENTEE) for u in user_ids
        ]
        self.training_repo.get_training_by_user_ids_and_categories.return_value = [
            _training(u, MENTEE_COURSE) for u in user_ids
        ]

    async def test_a_red_flag_this_round_needs_an_exemption(self):
        self._registered_and_trained(1, 2)
        self.notes_repo.list_tagged.return_value = [_note(1, 30, RED_FLAG_TAG, 2)]

        result = await self.service.needs_exemption(self.session, 30)

        self.assertEqual(result, {1: [HistoryFinding(IneligibleReason.RED_FLAG, 30)]})

    async def test_a_mark_after_this_round_s_exemption_needs_another(self):
        # Exempted this round at hour 0 for last round's shortfall, then
        # flagged this round at hour 2.
        self._registered_and_trained(1)
        self._short_last_round(1)
        self.notes_repo.list_tagged.return_value = [
            _note(1, 30, EXEMPTION, 0),
            _note(1, 30, RED_FLAG_TAG, 2),
        ]

        result = await self.service.needs_exemption(self.session, 30)

        self.assertEqual(result, {1: [HistoryFinding(IneligibleReason.RED_FLAG, 30)]})

    async def test_a_mark_before_this_round_s_exemption_is_lifted(self):
        self._registered_and_trained(1)
        self.notes_repo.list_tagged.return_value = [
            _note(1, 30, RED_FLAG_TAG, -2),
            _note(1, 30, EXEMPTION, 0),
        ]

        self.assertEqual(await self.service.eligible_user_ids(self.session, 30), {1})

    async def test_an_exemption_in_a_later_round_does_not_lift_a_mark(self):
        # Round 10 (December) comes after 30 (September).
        self._registered_and_trained(1)
        self.notes_repo.list_tagged.return_value = [
            _note(1, 30, RED_FLAG_TAG, 0),
            _note(1, 10, EXEMPTION, 2),
        ]

        result = await self.service.ineligible_by_user(self.session, 30)

        self.assertEqual(result[1], [IneligibleReason.RED_FLAG])

    async def test_a_no_show_counts_only_from_the_latest_paired_round_or_this_one(
        self,
    ):
        # Round 5 (February) is before 20 (May); 1 had a full pair in both.
        self.rounds.append(_round(5, 2))
        self._registered_and_trained(1)
        self.pairs_repo.list_pairs_with_meeting_counts.side_effect = [
            [(_pair(51, 20, 7, 1), 5), (_pair(52, 5, 8, 1), 5)],
            [],
        ]
        self.notes_repo.list_tagged.return_value = [
            _note(1, 5, NO_SHOW_TAG, 1),
            _note(1, 5, RED_FLAG_TAG, 2),
        ]

        result = await self.service.needs_exemption(self.session, 30)

        self.assertEqual(result, {1: [HistoryFinding(IneligibleReason.RED_FLAG, 5)]})

    def _short_last_round(self, *user_ids):
        """Each of these mentees was two meetings into round 20's five. Asked
        for these people, the pairs come back; asked for their mentees'
        other pairs, there are none."""
        pairs = [(_pair(50 + u, 20, 7, u), 2) for u in user_ids]
        self.pairs_repo.list_pairs_with_meeting_counts.side_effect = (
            lambda session, round_ids, people: [
                p for p in pairs if p[0].mentee_id in people
            ]
        )

    async def test_needs_exemption_is_those_only_history_keeps_out(self):
        self.participants_repo.list_round_registrations.return_value = [
            _registration(1, ParticipantRole.MENTEE),
            _registration(2, ParticipantRole.MENTEE),
            _registration(3, ParticipantRole.MENTEE),
        ]
        # 2 has not done the course; 3 has no history.
        self.training_repo.get_training_by_user_ids_and_categories.return_value = [
            _training(1, MENTEE_COURSE),
            _training(3, MENTEE_COURSE),
        ]
        self._short_last_round(1, 2)

        result = await self.service.needs_exemption(self.session, 30)

        self.assertEqual(
            result,
            {1: [HistoryFinding(IneligibleReason.MEETINGS_SHORT, 20, 2, 5)]},
        )

    async def test_an_exemption_in_this_round_makes_them_eligible(self):
        self.participants_repo.list_round_registrations.return_value = [
            _registration(1, ParticipantRole.MENTEE),
        ]
        self.training_repo.get_training_by_user_ids_and_categories.return_value = [
            _training(1, MENTEE_COURSE),
        ]
        self._short_last_round(1)
        self.notes_repo.list_tagged.return_value = [_note(1, 30, EXEMPTION)]

        self.assertEqual(await self.service.eligible_user_ids(self.session, 30), {1})
        self.assertEqual(await self.service.needs_exemption(self.session, 30), {})
        self.notes_repo.list_tagged.assert_awaited_with(
            self.session, [1], [EXEMPTION, NO_SHOW_TAG, RED_FLAG_TAG]
        )

    async def test_an_exemption_in_another_round_is_passed_to_the_history_check(self):
        # Exempted in 20 and short in 20 itself: the round of the exemption
        # still counts, so she still needs one.
        self.participants_repo.list_round_registrations.return_value = [
            _registration(1, ParticipantRole.MENTEE),
        ]
        self.training_repo.get_training_by_user_ids_and_categories.return_value = [
            _training(1, MENTEE_COURSE),
        ]
        self._short_last_round(1)
        self.notes_repo.list_tagged.return_value = [_note(1, 20, EXEMPTION)]

        result = await self.service.ineligible_by_user(self.session, 30)

        self.assertEqual(result[1], [IneligibleReason.MEETINGS_SHORT])

    async def test_eligible_user_ids_keeps_only_those_with_no_reason(self):
        self.participants_repo.list_round_registrations.return_value = [
            _registration(1, ParticipantRole.MENTEE),
            _registration(2, ParticipantRole.MENTEE),
        ]
        self.training_repo.get_training_by_user_ids_and_categories.return_value = [
            _training(1, MENTEE_COURSE),
        ]

        self.assertEqual(await self.service.eligible_user_ids(self.session, 30), {1})


if __name__ == "__main__":
    unittest.main()
