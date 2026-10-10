"""Ending one pair through an approval: when it may be asked for, what has to
still hold when approved, and what approving does to the pair, its meetings
and the two people.

Every id and name is distinct -- raiser, reviewer, mentor, mentee, pairs."""

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
from backend.mentorship.end_pair_handler import (
    END_PAIR,
    PAIR_TARGET,
    EndPairHandler,
    pair_target,
)

ROUND = 7
OTHER_ROUND = 6
MENTOR = 11
MENTEE = 21
OTHER_MENTEE = 22
PAIR = 501
OTHER_PAIR = 502
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


def _payload(**overrides):
    return {
        "round_id": ROUND,
        "pair_id": PAIR,
        "mentor_id": MENTOR,
        "mentee_id": MENTEE,
        **overrides,
    }


def _request(reason="They never met"):
    row = ApprovalRequestEntity(
        action=END_PAIR,
        target_type=PAIR_TARGET,
        target_id=pair_target(PAIR),
        payload=_payload(),
        reason=reason,
        raised_by=RAISER,
        reviewer_id=REVIEWER,
    )
    row.request_id = 801
    return row


class EndPairHandlerTest(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.rounds = MagicMock()
        self.rounds.get_by_round_id = AsyncMock(return_value=_round())
        self.pair = SimpleNamespace(
            pair_id=PAIR,
            round_id=ROUND,
            mentor_id=MENTOR,
            mentee_id=MENTEE,
            status=PairStatus.ACTIVE,
        )
        self.other_pair = SimpleNamespace(
            pair_id=OTHER_PAIR,
            round_id=ROUND,
            mentor_id=MENTOR,
            mentee_id=OTHER_MENTEE,
            status=PairStatus.ACTIVE,
        )
        by_user = {
            MENTOR: [self.pair, self.other_pair],
            MENTEE: [self.pair],
        }
        self.pairs = MagicMock()
        self.pairs.get_pair_by_id = AsyncMock(return_value=self.pair)
        self.pairs.get_pairs_by_user_and_round = AsyncMock(
            side_effect=lambda session, user_id, round_id: by_user[user_id]
        )
        self.registrations = {
            MENTOR: SimpleNamespace(approval_status=ApprovalStatus.MATCHED),
            MENTEE: SimpleNamespace(approval_status=ApprovalStatus.MATCHED),
        }
        self.participants = MagicMock()
        self.participants.get_by_user_id_and_round_id = AsyncMock(
            side_effect=lambda session, user_id, round_id: self.registrations[user_id]
        )
        self.meetings = MagicMock()
        self.meetings.cancel_upcoming_for_pairs = AsyncMock(return_value=2)
        self.notes = MagicMock()
        self.notes.create = AsyncMock()
        names = {
            MENTOR: ("Mia", "Ko"),
            MENTEE: ("Ann", "Lee"),
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
        self.handler = EndPairHandler(
            participants_repository=self.participants,
            pairs_repository=self.pairs,
            meeting_service=self.meetings,
            rounds_repository=self.rounds,
            note_repository=self.notes,
            users_repository=self.users,
            logger=MagicMock(),
        )

    async def _check(self, payload=None, target=None):
        await self.handler.check_raise(
            self.session,
            raised_by=RAISER,
            target_id=target or pair_target(PAIR),
            payload=payload or _payload(),
        )

    def _notes(self):
        return {
            call.kwargs["user_id"]: call.kwargs
            for call in self.notes.create.await_args_list
        }

    def test_it_is_about_the_pair_in_its_round(self):
        self.assertEqual(self.handler.action, "end_pair")
        self.assertEqual(self.handler.target_type, "mentorship_pair")
        self.assertEqual(pair_target(PAIR), "501")
        self.assertEqual(self.handler.subject_id(_request()), ROUND)

    async def test_an_active_pair_in_a_round_in_progress_may_be_ended(self):
        await self._check()

    async def test_a_malformed_payload_or_target_is_refused(self):
        for payload, target in (
            (_payload(pair_id="501"), None),
            (_payload(mentor_id=None), None),
            (_payload(), "502"),
        ):
            with self.subTest(payload=payload, target=target):
                with self.assertRaises(ValueError):
                    await self._check(payload=payload, target=target)

    async def test_a_round_not_in_progress_is_refused(self):
        self.rounds.get_by_round_id.return_value = _round(in_progress=False)

        with self.assertRaises(ConflictError) as caught:
            await self._check()
        self.assertEqual(str(caught.exception), "The round is not in progress.")

    async def test_a_pair_already_ended_is_refused(self):
        self.pair.status = PairStatus.INACTIVE

        with self.assertRaises(ConflictError) as caught:
            await self._check()
        self.assertEqual(str(caught.exception), "This pair has already ended.")

    async def test_a_pair_from_another_round_or_with_other_people_is_refused(self):
        for change in (
            {"round_id": OTHER_ROUND},
            {"mentee_id": OTHER_MENTEE},
        ):
            with self.subTest(change=change):
                for key, value in change.items():
                    setattr(self.pair, key, value)
                with self.assertRaises(ConflictError):
                    await self._check()
                self.pair.round_id, self.pair.mentee_id = ROUND, MENTEE

    async def test_a_missing_pair_is_refused(self):
        self.pairs.get_pair_by_id.return_value = None

        with self.assertRaises(ConflictError):
            await self._check()

    async def test_approval_re_checks_the_pair(self):
        self.assertEqual(
            await self.handler.problems_at_approval(self.session, _request()), []
        )
        self.pair.status = PairStatus.INACTIVE
        self.assertEqual(
            await self.handler.problems_at_approval(self.session, _request()),
            ["This pair has already ended."],
        )

    async def test_approving_ends_the_pair_and_cancels_its_meetings(self):
        await self.handler.execute(self.session, _request(), actor_id=REVIEWER)

        self.pairs.get_pair_by_id.assert_awaited_with(
            self.session, PAIR, with_lock=True
        )
        self.assertIs(self.pair.status, PairStatus.INACTIVE)
        self.assertIs(self.other_pair.status, PairStatus.ACTIVE)
        self.meetings.cancel_upcoming_for_pairs.assert_awaited_once_with(
            self.session, [PAIR]
        )

    async def test_only_who_is_left_with_no_pair_becomes_un_matched(self):
        await self.handler.execute(self.session, _request(), actor_id=REVIEWER)

        self.assertIs(
            self.registrations[MENTEE].approval_status, ApprovalStatus.UN_MATCHED
        )
        self.assertIs(
            self.registrations[MENTOR].approval_status, ApprovalStatus.MATCHED
        )

    async def test_each_person_gets_a_note_by_the_approver(self):
        await self.handler.execute(self.session, _request(), actor_id=REVIEWER)

        notes = self._notes()
        self.assertEqual(sorted(notes), [MENTOR, MENTEE])
        for user_id, note in notes.items():
            self.assertIs(note["tag"], ParticipantNoteTag.STATUS_CHANGE, user_id)
            self.assertEqual(note["pair_id"], PAIR)
            self.assertEqual(note["request_id"], 801)
            self.assertEqual(note["author_user_id"], REVIEWER)
            self.assertEqual(note["round_id"], ROUND)
        tail = (
            "Raised by Ada Raiser, reason: They never met; approved by "
            "Rae Reviewer. 2 upcoming meetings cancelled."
        )
        self.assertEqual(notes[MENTOR]["body"], f"Pair ended. {tail}")
        self.assertEqual(
            notes[MENTEE]["body"], f"Pair ended; matched -> un_matched. {tail}"
        )

    async def test_events_name_both_people_and_the_round(self):
        details = await self.handler.event_details(self.session, _request())

        self.assertEqual(
            details,
            {
                "roundName": "Spring 2026",
                "mentorName": "Mia Ko",
                "menteeName": "Ann Lee",
                "personName": "mentor Mia Ko and mentee Ann Lee",
            },
        )


if __name__ == "__main__":
    unittest.main()
