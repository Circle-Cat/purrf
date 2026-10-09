"""A matching exemption through an approval: when it may be asked for, what
has to still hold when it is approved, and what approving writes."""

import unittest
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

from backend.common.exceptions import ConflictError
from backend.common.mentorship_enums import ApprovalStatus, ParticipantNoteTag
from backend.entity.approval_request_entity import ApprovalRequestEntity
from backend.mentorship.exempt_matching_handler import (
    ExemptMatchingHandler,
    exemption_target,
)
from backend.mentorship.matching_eligibility import HistoryFinding, IneligibleReason

ROUND = 7
PERSON = 21
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


def _request():
    row = ApprovalRequestEntity(
        action="exempt_matching",
        target_type="round_participant",
        target_id=exemption_target(ROUND, PERSON),
        payload={"round_id": ROUND, "user_id": PERSON},
        reason="Her mentor left midway",
        raised_by=RAISER,
        reviewer_id=REVIEWER,
    )
    row.request_id = 601
    return row


class ExemptMatchingHandlerTest(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.eligibility = MagicMock()
        self.eligibility.needs_exemption = AsyncMock(
            return_value={
                PERSON: [HistoryFinding(IneligibleReason.MEETINGS_SHORT, 5, 2, 5)]
            }
        )
        self.rounds = MagicMock()
        self.rounds.get_by_round_id = AsyncMock(return_value=_round())
        self.notes = MagicMock()
        self.notes.create = AsyncMock()
        names = {
            PERSON: ("Ann", "Lee"),
            RAISER: ("Ada", "Ng"),
            REVIEWER: ("Rae", "Kim"),
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
        self.participants = MagicMock()
        self.participants.get_by_user_id_and_round_id = AsyncMock(
            return_value=SimpleNamespace(approval_status=ApprovalStatus.SIGNED_UP)
        )
        self.handler = ExemptMatchingHandler(
            matching_eligibility_service=self.eligibility,
            rounds_repository=self.rounds,
            note_repository=self.notes,
            users_repository=self.users,
            logger=MagicMock(),
            participants_repository=self.participants,
        )

    async def test_someone_withdrawn_from_the_round_is_refused_by_name(self):
        self.participants.get_by_user_id_and_round_id.return_value = SimpleNamespace(
            approval_status=ApprovalStatus.WITHDRAWN
        )

        with self.assertRaises(ConflictError) as caught:
            await self._check()
        self.assertEqual(str(caught.exception), "Ann Lee has left this round.")
        self.eligibility.needs_exemption.assert_not_awaited()
        self.assertEqual(
            await self.handler.problems_at_approval(self.session, _request()),
            ["Ann Lee has left this round."],
        )

    async def _check(self, target=None, payload=None):
        await self.handler.check_raise(
            self.session,
            raised_by=RAISER,
            target_id=target or exemption_target(ROUND, PERSON),
            payload=payload or {"round_id": ROUND, "user_id": PERSON},
        )

    def test_the_target_is_the_person_in_the_round(self):
        self.assertEqual(exemption_target(7, 21), "7:21")
        self.assertEqual(self.handler.subject_id(_request()), 7)

    async def test_someone_kept_out_only_by_history_may_be_put_up(self):
        await self._check()

        self.eligibility.needs_exemption.assert_awaited_once_with(self.session, ROUND)

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
        self.eligibility.needs_exemption.assert_not_awaited()

    async def test_someone_who_does_not_need_one_is_refused_by_name(self):
        self.eligibility.needs_exemption.return_value = {}

        with self.assertRaises(ConflictError) as caught:
            await self._check()
        self.assertIn("Ann Lee does not need an exemption", str(caught.exception))

    async def test_at_approval_the_same_two_conditions_are_rechecked(self):
        self.assertEqual(
            await self.handler.problems_at_approval(self.session, _request()), []
        )

        self.eligibility.needs_exemption.return_value = {}
        problems = await self.handler.problems_at_approval(self.session, _request())
        self.assertEqual(len(problems), 1)
        self.assertIn("does not need an exemption", problems[0])

        self.rounds.get_by_round_id.return_value = _round(in_progress=False)
        self.assertEqual(
            await self.handler.problems_at_approval(self.session, _request()),
            ["The round is not in progress."],
        )

    async def test_approving_writes_the_exemption_by_the_approver(self):
        await self.handler.execute(self.session, _request(), actor_id=REVIEWER)

        kwargs = self.notes.create.await_args.kwargs
        self.assertEqual(kwargs["user_id"], PERSON)
        self.assertEqual(kwargs["round_id"], ROUND)
        self.assertEqual(kwargs["author_user_id"], REVIEWER)
        self.assertIs(kwargs["tag"], ParticipantNoteTag.MATCHING_EXEMPTION)
        self.assertEqual(kwargs["request_id"], 601)
        self.assertIn("Raised by Ada Ng", kwargs["body"])
        self.assertIn("Her mentor left midway", kwargs["body"])
        self.assertIn("approved by Rae Kim", kwargs["body"])

    async def test_events_snapshot_the_round_and_the_person(self):
        details = await self.handler.event_details(self.session, _request())

        self.assertEqual(details, {"roundName": "Spring 2026", "personName": "Ann Lee"})


if __name__ == "__main__":
    unittest.main()
