"""Marking someone as a no show, or raising a red flag on them, through an
approval: when it may be asked for, what has to still hold when it is
approved, and what approving writes.

Every id and name below is distinct on purpose -- raiser, reviewer, the
person marked, each partner and each pair, and a pair that is somebody
else's -- so reading one as another cannot pass."""

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
from backend.mentorship.mark_participant_handler import (
    MARK_NO_SHOW,
    MARK_RED_FLAG,
    MarkNoShowHandler,
    MarkRedFlagHandler,
)

ROUND = 7
PERSON = 21
PARTNER_A = 31
OLD_PARTNER = 33
RAISER = 90
REVIEWER = 80
ACTIVE_PAIR = 501
ENDED_PAIR = 503
SOMEONE_ELSES_PAIR = 599


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


def _request(action, pair_id=None, reason="Missed both kickoff calls"):
    payload = {"round_id": ROUND, "user_id": PERSON}
    if pair_id is not None:
        payload["pair_id"] = pair_id
    row = ApprovalRequestEntity(
        action=action,
        target_type="round_participant",
        target_id=exemption_target(ROUND, PERSON),
        payload=payload,
        reason=reason,
        raised_by=RAISER,
        reviewer_id=REVIEWER,
    )
    row.request_id = 702
    return row


class MarkParticipantHandlerTest(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.rounds = MagicMock()
        self.rounds.get_by_round_id = AsyncMock(return_value=_round())
        self.registration = SimpleNamespace(approval_status=ApprovalStatus.MATCHED)
        self.participants = MagicMock()
        self.participants.get_by_user_id_and_round_id = AsyncMock(
            return_value=self.registration
        )
        # A mentor with two pairs this round, one of them already ended.
        self.pairs = MagicMock()
        self.pairs.get_pairs_by_user_and_round = AsyncMock(
            return_value=[
                _pair(ACTIVE_PAIR, PARTNER_A),
                _pair(ENDED_PAIR, OLD_PARTNER, status=PairStatus.INACTIVE),
            ]
        )
        self.notes = MagicMock()
        self.notes.create = AsyncMock()
        names = {
            PERSON: ("Mia", "Ko"),
            PARTNER_A: ("Ann", "Lee"),
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
        deps = dict(
            participants_repository=self.participants,
            pairs_repository=self.pairs,
            rounds_repository=self.rounds,
            note_repository=self.notes,
            users_repository=self.users,
            logger=MagicMock(),
        )
        self.no_show = MarkNoShowHandler(**deps)
        self.red_flag = MarkRedFlagHandler(**deps)

    async def _check(self, handler, pair_id=None, target=None, payload=None):
        if payload is None:
            payload = {"round_id": ROUND, "user_id": PERSON}
            if pair_id is not None:
                payload["pair_id"] = pair_id
        await handler.check_raise(
            self.session,
            raised_by=RAISER,
            target_id=target or exemption_target(ROUND, PERSON),
            payload=payload,
        )

    async def _refusal(self, handler, pair_id=None):
        with self.assertRaises(ConflictError) as caught:
            await self._check(handler, pair_id)
        return str(caught.exception)

    def test_each_is_about_the_person_in_the_round(self):
        self.assertEqual(self.no_show.action, "mark_no_show")
        self.assertEqual(self.red_flag.action, "mark_red_flag")
        for handler in (self.no_show, self.red_flag):
            self.assertEqual(handler.target_type, "round_participant")
            self.assertEqual(handler.subject_id(_request(handler.action)), ROUND)

    async def test_a_no_show_must_name_one_of_her_own_pairs(self):
        self.assertEqual(
            await self._refusal(self.no_show),
            "Say which of Mia Ko's pairs the no show is about.",
        )
        self.assertEqual(
            await self._refusal(self.no_show, SOMEONE_ELSES_PAIR),
            f"Pair {SOMEONE_ELSES_PAIR} is not one of Mia Ko's pairs in this round.",
        )
        await self._check(self.no_show, ACTIVE_PAIR)
        await self._check(self.no_show, ENDED_PAIR)
        self.pairs.get_pairs_by_user_and_round.assert_awaited_with(
            session=self.session, user_id=PERSON, round_id=ROUND
        )

    async def test_a_no_show_needs_a_pair_this_round(self):
        self.pairs.get_pairs_by_user_and_round.return_value = []

        self.assertEqual(
            await self._refusal(self.no_show, ACTIVE_PAIR),
            "Mia Ko had no pair in this round.",
        )

    async def test_a_red_flag_needs_no_pair_but_a_named_one_must_be_hers(self):
        self.pairs.get_pairs_by_user_and_round.return_value = []
        await self._check(self.red_flag)

        self.pairs.get_pairs_by_user_and_round.return_value = [
            _pair(ACTIVE_PAIR, PARTNER_A)
        ]
        await self._check(self.red_flag, ACTIVE_PAIR)
        self.assertEqual(
            await self._refusal(self.red_flag, SOMEONE_ELSES_PAIR),
            f"Pair {SOMEONE_ELSES_PAIR} is not one of Mia Ko's pairs in this round.",
        )

    async def test_any_status_will_do_once_registered(self):
        for status in (ApprovalStatus.WITHDRAWN, ApprovalStatus.REJECTED):
            with self.subTest(status=status):
                self.registration.approval_status = status
                await self._check(self.red_flag)
                await self._check(self.no_show, ENDED_PAIR)

    async def test_someone_not_registered_is_refused_by_name(self):
        self.participants.get_by_user_id_and_round_id.return_value = None

        for handler in (self.no_show, self.red_flag):
            with self.subTest(action=handler.action):
                self.assertEqual(
                    await self._refusal(handler, ACTIVE_PAIR),
                    "Mia Ko is not registered for this round.",
                )

    async def test_a_round_not_in_progress_is_refused(self):
        self.rounds.get_by_round_id.return_value = _round(in_progress=False)

        self.assertEqual(
            await self._refusal(self.red_flag), "The round is not in progress."
        )

    async def test_a_malformed_payload_is_refused(self):
        for target, payload in (
            ("7:21", {"round_id": ROUND}),
            ("7:22", {"round_id": ROUND, "user_id": PERSON}),
            ("7:21", {"round_id": ROUND, "user_id": PERSON, "pair_id": "501"}),
        ):
            with self.subTest(target=target, payload=payload):
                with self.assertRaises(ValueError):
                    await self._check(self.red_flag, target=target, payload=payload)

    async def test_at_approval_the_pair_must_still_be_hers(self):
        request = _request(MARK_NO_SHOW, pair_id=ACTIVE_PAIR)
        self.assertEqual(
            await self.no_show.problems_at_approval(self.session, request), []
        )

        self.pairs.get_pairs_by_user_and_round.return_value = [
            _pair(ENDED_PAIR, OLD_PARTNER, status=PairStatus.INACTIVE)
        ]
        self.assertEqual(
            await self.no_show.problems_at_approval(self.session, request),
            [f"Pair {ACTIVE_PAIR} is not one of Mia Ko's pairs in this round."],
        )

        self.rounds.get_by_round_id.return_value = _round(in_progress=False)
        self.assertEqual(
            await self.no_show.problems_at_approval(self.session, request),
            ["The round is not in progress."],
        )

    async def test_approving_a_no_show_writes_one_note_and_nothing_else(self):
        await self.no_show.execute(
            self.session, _request(MARK_NO_SHOW, pair_id=ENDED_PAIR), actor_id=REVIEWER
        )

        self.notes.create.assert_awaited_once()
        kwargs = self.notes.create.await_args.kwargs
        self.assertEqual(kwargs["user_id"], PERSON)
        self.assertEqual(kwargs["round_id"], ROUND)
        self.assertEqual(kwargs["author_user_id"], REVIEWER)
        self.assertIs(kwargs["tag"], ParticipantNoteTag.NO_SHOW)
        self.assertEqual(kwargs["pair_id"], ENDED_PAIR)
        self.assertEqual(kwargs["request_id"], 702)
        self.assertEqual(
            kwargs["body"],
            "Marked as a no show. Raised by Ada Raiser, reason: Missed both "
            "kickoff calls; approved by Rae Reviewer.",
        )
        self.assertIs(self.registration.approval_status, ApprovalStatus.MATCHED)
        self.participants.get_by_user_id_and_round_id.assert_not_awaited()
        self.pairs.get_pairs_by_user_and_round.assert_not_awaited()
        self.session.commit.assert_not_awaited()

    async def test_approving_a_red_flag_without_a_pair_leaves_the_pair_empty(self):
        await self.red_flag.execute(
            self.session, _request(MARK_RED_FLAG, reason=None), actor_id=REVIEWER
        )

        kwargs = self.notes.create.await_args.kwargs
        self.assertIs(kwargs["tag"], ParticipantNoteTag.RED_FLAG)
        self.assertIsNone(kwargs["pair_id"])
        self.assertEqual(
            kwargs["body"],
            "Red flag raised. Raised by Ada Raiser, reason: none given; "
            "approved by Rae Reviewer.",
        )

    async def test_events_snapshot_the_round_and_the_person(self):
        details = await self.red_flag.event_details(
            self.session, _request(MARK_RED_FLAG)
        )

        self.assertEqual(details, {"roundName": "Spring 2026", "personName": "Mia Ko"})


if __name__ == "__main__":
    unittest.main()
