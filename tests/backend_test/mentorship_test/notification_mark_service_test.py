"""Marking people notified when a notification went out some other way:
who is marked, who is skipped and why, and when nothing is written.

Every id differs: the admin, each registered person, each person not
registered, the round."""

import unittest
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

from backend.common.exceptions import ConflictError, NotFoundError
from backend.common.mentorship_email_enums import MentorshipEmailStage as Stage
from backend.common.mentorship_enums import ParticipantNoteTag
from backend.mentorship.notification_mark_service import NotificationMarkService

ROUND = 7
ADMIN = 9
MIA, ANN, BO = 21, 22, 23  # registered
CY = 31  # not registered
BODY = "Sent on Teams, 10-10."


def _round(in_progress=True):
    now = datetime.now(timezone.utc)
    if in_progress:
        start, end = now - timedelta(days=10), now + timedelta(days=10)
    else:
        start, end = now - timedelta(days=60), now - timedelta(days=1)
    return SimpleNamespace(
        round_id=ROUND, promotion_start_at=start, feedback_deadline_at=end
    )


class NotificationMarkServiceTest(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.session = AsyncMock()
        self.rounds = MagicMock()
        self.rounds.get_by_round_id = AsyncMock(return_value=_round())
        self.users = MagicMock()
        self.users.get_all_by_ids = AsyncMock(
            side_effect=lambda session, ids: [SimpleNamespace(user_id=i) for i in ids]
        )
        self.participants = MagicMock()
        self.participants.list_round_registrations = AsyncMock(
            return_value=[
                (SimpleNamespace(user_id=i), SimpleNamespace(user_id=i, round_id=ROUND))
                for i in (MIA, ANN, BO)
            ]
        )
        self.email_repo = MagicMock()
        self.email_repo.list_sent_stages = AsyncMock(return_value=[])
        self.email_repo.list_manual_stages = AsyncMock(return_value=[])
        self.notes = MagicMock()
        self.notes.create = AsyncMock()
        self.service = NotificationMarkService(
            note_repository=self.notes,
            participants_repository=self.participants,
            rounds_repository=self.rounds,
            users_repository=self.users,
            mentorship_email_repository=self.email_repo,
            logger=MagicMock(),
        )

    async def _mark(self, user_ids, stage=Stage.MATCH_RESULT):
        return await self.service.mark(
            self.session,
            round_id=ROUND,
            user_ids=user_ids,
            stage=stage,
            body=BODY,
            actor_id=ADMIN,
        )

    def _noted(self):
        return [call.kwargs for call in self.notes.create.await_args_list]

    @staticmethod
    def _skips(result):
        return [(s.user_id, s.reason) for s in result.skipped]

    async def test_marks_each_person_with_a_note_by_the_actor(self):
        result = await self._mark([MIA, ANN])

        self.assertEqual(result.marked, [MIA, ANN])
        self.assertEqual(result.skipped, [])
        notes = self._noted()
        self.assertEqual([n["user_id"] for n in notes], [MIA, ANN])
        for note in notes:
            self.assertEqual(note["round_id"], ROUND)
            self.assertEqual(note["author_user_id"], ADMIN)
            self.assertEqual(note["body"], BODY)
            self.assertIs(note["tag"], ParticipantNoteTag.NOTIFIED)
            self.assertEqual(note["notification_stage"], "match_result")
        self.session.commit.assert_awaited_once()

    async def test_skips_people_already_notified_by_kit_or_by_hand(self):
        self.email_repo.list_sent_stages = AsyncMock(
            return_value=[(MIA, "match_result"), (ANN, "admission")]
        )
        self.email_repo.list_manual_stages = AsyncMock(
            return_value=[(BO, "match_result"), (ANN, "midterm_reminder")]
        )

        result = await self._mark([MIA, ANN, BO])

        self.assertEqual(result.marked, [ANN])
        self.assertEqual(
            self._skips(result),
            [(MIA, "already_notified"), (BO, "already_notified")],
        )
        self.assertEqual([n["user_id"] for n in self._noted()], [ANN])

    async def test_offers_each_person_only_their_stages(self):
        invited = await self._mark([MIA, CY], stage=Stage.ROUND_RECRUITMENT)
        self.assertEqual(invited.marked, [CY])
        self.assertEqual(self._skips(invited), [(MIA, "not_offered")])

        matched = await self._mark([MIA, CY], stage=Stage.MATCH_RESULT)
        self.assertEqual(matched.marked, [MIA])
        self.assertEqual(self._skips(matched), [(CY, "not_offered")])

        reminded = await self._mark([CY], stage=Stage.ONBOARDING_REMINDER)
        self.assertEqual(reminded.marked, [CY])

    async def test_a_scheduled_kit_send_does_not_count_as_notified(self):
        self.email_repo.list_scheduled_stages = AsyncMock(
            return_value=[(MIA, "match_result", datetime.now(timezone.utc))]
        )

        result = await self._mark([MIA])

        self.assertEqual(result.marked, [MIA])
        self.assertEqual(result.skipped, [])
        self.email_repo.list_scheduled_stages.assert_not_awaited()

    async def test_a_person_listed_twice_is_marked_once(self):
        result = await self._mark([ANN, ANN])

        self.assertEqual(result.marked, [ANN])
        self.assertEqual(len(self._noted()), 1)

    async def test_a_round_not_in_progress_writes_nothing(self):
        self.rounds.get_by_round_id = AsyncMock(return_value=_round(in_progress=False))

        with self.assertRaises(ConflictError) as caught:
            await self._mark([MIA])

        self.assertEqual(caught.exception.code, "round_not_in_progress")
        self.assertEqual(
            str(caught.exception),
            "Notifications can only be marked while the round is in progress.",
        )
        self.notes.create.assert_not_awaited()
        self.session.commit.assert_not_awaited()

    async def test_a_missing_round_or_person_is_not_found(self):
        self.rounds.get_by_round_id = AsyncMock(return_value=None)
        with self.assertRaises(NotFoundError):
            await self._mark([MIA])

        self.rounds.get_by_round_id = AsyncMock(return_value=_round())
        self.users.get_all_by_ids = AsyncMock(
            return_value=[SimpleNamespace(user_id=MIA)]
        )
        with self.assertRaises(NotFoundError) as caught:
            await self._mark([MIA, 999])
        self.assertEqual(str(caught.exception), "User 999 does not exist.")
        self.notes.create.assert_not_awaited()
        self.session.commit.assert_not_awaited()


if __name__ == "__main__":
    unittest.main()
