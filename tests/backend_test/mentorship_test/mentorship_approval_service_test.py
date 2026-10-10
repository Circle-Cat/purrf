"""The mentorship console's side of approvals: scoped to its own actions,
and described the way the console shows them."""

import unittest
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

from backend.common.approval_enums import ApprovalRequestStatus
from backend.common.exceptions import ConflictError
from backend.entity.approval_request_entity import ApprovalRequestEntity
from backend.mentorship.mentorship_approval_service import MentorshipApprovalService

RAISER = 9
REVIEWER = 8
PERSON = 21


def _request(action="publish_matching", request_id=31):
    row = ApprovalRequestEntity(
        action=action,
        target_type="matching_run",
        target_id="r7-x-y",
        payload={"round_id": 7},
        reason="Reviewed every pair",
        raised_by=RAISER,
        reviewer_id=REVIEWER,
        status=ApprovalRequestStatus.PENDING,
        created_at=datetime(2026, 10, 7, 9, 30, tzinfo=timezone.utc),
    )
    row.request_id = request_id
    return row


def _withdrawal(request_id=41):
    row = _request(action="withdraw_participant", request_id=request_id)
    row.target_type = "round_participant"
    row.target_id = "7:21"
    row.payload = {"round_id": 7, "user_id": PERSON}
    return row


def _mark(action="mark_no_show", request_id=51, pair_id=501):
    row = _request(action=action, request_id=request_id)
    row.target_type = "round_participant"
    row.target_id = "7:21"
    row.payload = {"round_id": 7, "user_id": PERSON, "pair_id": pair_id}
    return row


MENTOR = 11
MENTEE = PERSON
PAIR = 501


def _end_pair(request_id=61):
    row = _request(action="end_pair", request_id=request_id)
    row.target_type = "mentorship_pair"
    row.target_id = str(PAIR)
    row.payload = {
        "round_id": 7,
        "pair_id": PAIR,
        "mentor_id": MENTOR,
        "mentee_id": MENTEE,
    }
    return row


def _user(user_id, first, last):
    return SimpleNamespace(
        user_id=user_id, first_name=first, last_name=last, preferred_name=None
    )


class MentorshipApprovalServiceTest(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.approvals = MagicMock()
        for name in ("raise_request", "reassign", "decide", "withdraw"):
            setattr(self.approvals, name, AsyncMock(return_value=_request()))
        self.approvals.get_request = AsyncMock(return_value=_request())
        self.approvals.list_pending_for_reviewer = AsyncMock(return_value=[_request()])
        self.approvals.list_pending_for_targets = AsyncMock(return_value={})
        self.approvals.get_pending_for_target = AsyncMock(return_value=None)
        self.approvals.list_reviewers = AsyncMock(
            return_value=[_user(12, "zoe", "Adams"), _user(8, "Rae", "Kim")]
        )
        self.storage = MagicMock()
        self.storage.current_run_id.return_value = "r7-x-y"
        self.users = MagicMock()
        self.users.get_all_by_ids = AsyncMock(
            return_value=[_user(RAISER, "Ada", "Ng"), _user(REVIEWER, "Rae", "Kim")]
        )
        self.rounds = MagicMock()
        self.rounds.get_by_round_id = AsyncMock(
            return_value=SimpleNamespace(name="Spring 2026")
        )
        self.session = AsyncMock()
        self.pair = SimpleNamespace(
            pair_id=PAIR, round_id=7, mentor_id=MENTOR, mentee_id=MENTEE
        )
        self.pairs = MagicMock()
        self.pairs.get_pair_by_id = AsyncMock(return_value=self.pair)
        self.service = MentorshipApprovalService(
            approval_service=self.approvals,
            matching_storage=self.storage,
            users_repository=self.users,
            rounds_repository=self.rounds,
            pairs_repository=self.pairs,
            logger=MagicMock(),
        )

    async def test_publishing_asks_about_the_round_s_current_run(self):
        result = await self.service.request_publish(
            self.session,
            round_id=7,
            actor_id=RAISER,
            reviewer_id=REVIEWER,
            reason="Reviewed every pair",
        )

        self.approvals.raise_request.assert_awaited_once_with(
            self.session,
            action="publish_matching",
            raised_by=RAISER,
            target_id="r7-x-y",
            payload={"round_id": 7},
            reason="Reviewed every pair",
            reviewer_id=REVIEWER,
        )
        self.assertEqual(result["request_id"], 31)

    async def test_a_round_without_a_run_has_nothing_to_publish(self):
        self.storage.current_run_id.return_value = None

        with self.assertRaises(ValueError):
            await self.service.request_publish(
                self.session,
                round_id=7,
                actor_id=RAISER,
                reviewer_id=REVIEWER,
                reason="x",
            )
        self.approvals.raise_request.assert_not_awaited()

    async def test_a_request_is_described_with_names_and_its_round(self):
        result = await self.service.list_mine(self.session, REVIEWER)

        self.approvals.list_pending_for_reviewer.assert_awaited_once_with(
            self.session,
            REVIEWER,
            (
                "publish_matching",
                "exempt_matching",
                "withdraw_participant",
                "mark_no_show",
                "mark_red_flag",
                "end_pair",
            ),
        )
        self.assertEqual(
            result,
            [
                {
                    "request_id": 31,
                    "action": "publish_matching",
                    "status": ApprovalRequestStatus.PENDING,
                    "round": {"round_id": 7, "name": "Spring 2026"},
                    "target_id": "r7-x-y",
                    "person": None,
                    "pair_id": None,
                    "pair": None,
                    "raised_by": {"user_id": RAISER, "name": "Ada Ng"},
                    "reviewer": {"user_id": REVIEWER, "name": "Rae Kim"},
                    "reason": "Reviewed every pair",
                    "decision_comment": None,
                    "created_at": datetime(2026, 10, 7, 9, 30, tzinfo=timezone.utc),
                    "decided_at": None,
                }
            ],
        )

    async def test_reviewers_are_sorted_by_name(self):
        result = await self.service.list_reviewers(self.session, RAISER)

        self.approvals.list_reviewers.assert_awaited_once_with(
            self.session, "publish_matching", exclude_user_id=RAISER
        )
        self.assertEqual([r["user_id"] for r in result], [8, 12])

    async def test_actions_pass_through_for_a_mentorship_request(self):
        await self.service.reassign(
            self.session, request_id=31, actor_id=RAISER, reviewer_id=12
        )
        await self.service.decide(
            self.session, request_id=31, actor_id=REVIEWER, approve=False, comment="No"
        )
        await self.service.withdraw(self.session, request_id=31, actor_id=RAISER)

        self.approvals.reassign.assert_awaited_once_with(
            self.session, request_id=31, actor_id=RAISER, reviewer_id=12
        )
        self.approvals.decide.assert_awaited_once_with(
            self.session, request_id=31, actor_id=REVIEWER, approve=False, comment="No"
        )
        self.approvals.withdraw.assert_awaited_once_with(
            self.session, request_id=31, actor_id=RAISER
        )

    async def test_an_exemption_asks_about_the_person_in_the_round(self):
        exemption = _request(action="exempt_matching")
        exemption.target_id = "7:21"
        exemption.payload = {"round_id": 7, "user_id": 21}
        self.approvals.raise_request.return_value = exemption
        self.users.get_all_by_ids.return_value = [
            _user(RAISER, "Ada", "Ng"),
            _user(REVIEWER, "Rae", "Kim"),
            _user(21, "Ann", "Lee"),
        ]

        result = await self.service.request_exemption(
            self.session,
            round_id=7,
            user_id=21,
            actor_id=RAISER,
            reviewer_id=REVIEWER,
            reason="Her mentor left midway",
        )

        self.approvals.raise_request.assert_awaited_once_with(
            self.session,
            action="exempt_matching",
            raised_by=RAISER,
            target_id="7:21",
            payload={"round_id": 7, "user_id": 21},
            reason="Her mentor left midway",
            reviewer_id=REVIEWER,
        )
        self.assertEqual(result["person"], {"user_id": 21, "name": "Ann Lee"})

    async def test_pending_exemptions_are_keyed_by_person(self):
        exemption = _request(action="exempt_matching")
        exemption.target_id = "7:21"
        exemption.payload = {"round_id": 7, "user_id": 21}
        self.approvals.list_pending_for_targets.return_value = {"7:21": exemption}

        result = await self.service.pending_exemptions(self.session, 7, [21, 22])

        self.approvals.list_pending_for_targets.assert_awaited_once_with(
            self.session, "exempt_matching", ["7:21", "7:22"]
        )
        self.assertEqual(list(result), [21])
        self.assertEqual(result[21]["reviewer"]["user_id"], REVIEWER)

    async def test_another_part_of_purrf_s_request_cannot_be_touched_here(self):
        self.approvals.get_request.return_value = _request(action="job_review")

        for call in (
            self.service.reassign(
                self.session, request_id=31, actor_id=RAISER, reviewer_id=12
            ),
            self.service.decide(
                self.session,
                request_id=31,
                actor_id=REVIEWER,
                approve=True,
                comment=None,
            ),
            self.service.withdraw(self.session, request_id=31, actor_id=RAISER),
        ):
            with self.assertRaises(ValueError) as caught:
                await call
            self.assertEqual(str(caught.exception), "No approval request 31")

        self.approvals.reassign.assert_not_awaited()
        self.approvals.decide.assert_not_awaited()
        self.approvals.withdraw.assert_not_awaited()

    async def test_a_withdrawal_asks_about_the_person_in_the_round(self):
        self.approvals.raise_request.return_value = _withdrawal()
        self.users.get_all_by_ids.return_value = [
            _user(RAISER, "Ada", "Ng"),
            _user(REVIEWER, "Rae", "Kim"),
            _user(PERSON, "Mia", "Ko"),
        ]

        result = await self.service.request_withdrawal(
            self.session,
            round_id=7,
            user_id=PERSON,
            actor_id=RAISER,
            reviewer_id=REVIEWER,
            reason="",
        )

        self.approvals.raise_request.assert_awaited_once_with(
            self.session,
            action="withdraw_participant",
            raised_by=RAISER,
            target_id="7:21",
            payload={"round_id": 7, "user_id": PERSON},
            reason="",
            reviewer_id=REVIEWER,
        )
        self.assertEqual(result["person"], {"user_id": PERSON, "name": "Mia Ko"})

    async def test_the_person_withdrawn_cannot_be_named_reviewer(self):
        with self.assertRaises(ValueError) as caught:
            await self.service.request_withdrawal(
                self.session,
                round_id=7,
                user_id=PERSON,
                actor_id=RAISER,
                reviewer_id=PERSON,
                reason="",
            )
        self.assertEqual(
            str(caught.exception),
            "The person being withdrawn cannot review their own withdrawal.",
        )
        self.approvals.raise_request.assert_not_awaited()

    async def test_a_withdrawal_cannot_be_handed_to_the_person_withdrawn(self):
        self.approvals.get_request.return_value = _withdrawal()

        with self.assertRaises(ValueError):
            await self.service.reassign(
                self.session, request_id=41, actor_id=RAISER, reviewer_id=PERSON
            )
        self.approvals.reassign.assert_not_awaited()

        await self.service.reassign(
            self.session, request_id=41, actor_id=RAISER, reviewer_id=12
        )
        self.approvals.reassign.assert_awaited_once_with(
            self.session, request_id=41, actor_id=RAISER, reviewer_id=12
        )

    async def test_an_exemption_may_still_be_handed_to_its_subject(self):
        exemption = _request(action="exempt_matching")
        exemption.payload = {"round_id": 7, "user_id": 12}
        self.approvals.get_request.return_value = exemption

        await self.service.reassign(
            self.session, request_id=31, actor_id=RAISER, reviewer_id=12
        )

        self.approvals.reassign.assert_awaited_once()

    async def test_pending_requests_on_a_participant_are_described(self):
        waiting = {
            "withdraw_participant": _withdrawal(),
            "mark_no_show": _mark("mark_no_show", request_id=51, pair_id=501),
            "mark_red_flag": _mark("mark_red_flag", request_id=52, pair_id=None),
        }
        self.approvals.get_pending_for_target.side_effect = (
            lambda session, action, target: waiting.get(action)
        )

        result = await self.service.pending_for_participant(self.session, 7, PERSON)

        self.assertEqual(
            [c.args[1:] for c in self.approvals.get_pending_for_target.await_args_list],
            [
                ("withdraw_participant", "7:21"),
                ("mark_no_show", "7:21"),
                ("mark_red_flag", "7:21"),
            ],
        )
        self.assertEqual([r["request_id"] for r in result], [41, 51, 52])
        self.assertEqual([r["pair_id"] for r in result], [None, 501, None])
        self.assertEqual(result[0]["raised_by"]["user_id"], RAISER)
        self.assertEqual(result[0]["reviewer"]["user_id"], REVIEWER)

    async def test_a_no_show_asks_about_the_person_and_the_pair(self):
        self.approvals.raise_request.return_value = _mark()

        await self.service.request_mark(
            self.session,
            round_id=7,
            user_id=PERSON,
            tag="no_show",
            pair_id=501,
            actor_id=RAISER,
            reviewer_id=REVIEWER,
            reason="",
        )

        self.approvals.raise_request.assert_awaited_once_with(
            self.session,
            action="mark_no_show",
            raised_by=RAISER,
            target_id="7:21",
            payload={"round_id": 7, "user_id": PERSON, "pair_id": 501},
            reason="",
            reviewer_id=REVIEWER,
        )

    async def test_a_red_flag_without_a_pair_leaves_it_out_of_the_payload(self):
        self.approvals.raise_request.return_value = _mark("mark_red_flag", 52, None)

        await self.service.request_mark(
            self.session,
            round_id=7,
            user_id=PERSON,
            tag="red_flag",
            pair_id=None,
            actor_id=RAISER,
            reviewer_id=REVIEWER,
            reason="Rude to the mentee",
        )

        kwargs = self.approvals.raise_request.await_args.kwargs
        self.assertEqual(kwargs["action"], "mark_red_flag")
        self.assertEqual(kwargs["payload"], {"round_id": 7, "user_id": PERSON})

    async def test_the_person_marked_cannot_be_named_reviewer(self):
        for tag in ("no_show", "red_flag"):
            with self.subTest(tag=tag):
                with self.assertRaises(ValueError) as caught:
                    await self.service.request_mark(
                        self.session,
                        round_id=7,
                        user_id=PERSON,
                        tag=tag,
                        pair_id=501,
                        actor_id=RAISER,
                        reviewer_id=PERSON,
                        reason="",
                    )
                self.assertEqual(
                    str(caught.exception),
                    "The person being marked cannot review a mark on themselves.",
                )
        self.approvals.raise_request.assert_not_awaited()

    async def test_an_unknown_mark_is_refused(self):
        with self.assertRaises(ValueError):
            await self.service.request_mark(
                self.session,
                round_id=7,
                user_id=PERSON,
                tag="status_change",
                pair_id=None,
                actor_id=RAISER,
                reviewer_id=REVIEWER,
                reason="",
            )
        self.approvals.raise_request.assert_not_awaited()

    async def test_a_mark_cannot_be_handed_to_the_person_marked(self):
        for action in ("mark_no_show", "mark_red_flag"):
            with self.subTest(action=action):
                self.approvals.get_request.return_value = _mark(action)
                with self.assertRaises(ValueError):
                    await self.service.reassign(
                        self.session, request_id=51, actor_id=RAISER, reviewer_id=PERSON
                    )
        self.approvals.reassign.assert_not_awaited()

    async def test_no_pending_request_on_a_participant_is_an_empty_list(self):
        self.assertEqual(
            await self.service.pending_for_participant(self.session, 7, PERSON), []
        )

    async def test_ending_a_pair_asks_about_the_pair_with_both_people(self):
        self.approvals.raise_request.return_value = _end_pair()

        result = await self.service.request_end_pair(
            self.session,
            round_id=7,
            user_id=MENTOR,
            pair_id=PAIR,
            actor_id=RAISER,
            reviewer_id=REVIEWER,
            reason="They never met",
        )

        self.approvals.raise_request.assert_awaited_once_with(
            self.session,
            action="end_pair",
            raised_by=RAISER,
            target_id="501",
            payload={
                "round_id": 7,
                "pair_id": PAIR,
                "mentor_id": MENTOR,
                "mentee_id": MENTEE,
            },
            reason="They never met",
            reviewer_id=REVIEWER,
        )
        self.assertEqual(result["pair"]["pair_id"], PAIR)
        self.assertEqual(result["pair"]["mentor"]["user_id"], MENTOR)
        self.assertEqual(result["pair"]["mentee"]["user_id"], MENTEE)
        self.assertIsNone(result["person"])

    async def test_a_pair_that_is_not_theirs_in_the_round_is_refused(self):
        for pair in (
            None,
            SimpleNamespace(
                pair_id=PAIR, round_id=6, mentor_id=MENTOR, mentee_id=MENTEE
            ),
            SimpleNamespace(pair_id=PAIR, round_id=7, mentor_id=12, mentee_id=22),
        ):
            with self.subTest(pair=pair):
                self.pairs.get_pair_by_id.return_value = pair
                with self.assertRaises(ConflictError):
                    await self.service.request_end_pair(
                        self.session,
                        round_id=7,
                        user_id=MENTOR,
                        pair_id=PAIR,
                        actor_id=RAISER,
                        reviewer_id=REVIEWER,
                        reason="",
                    )
        self.approvals.raise_request.assert_not_awaited()

    async def test_neither_person_in_the_pair_may_review_ending_it(self):
        for reviewer in (MENTOR, MENTEE):
            with self.subTest(reviewer=reviewer):
                with self.assertRaises(ValueError) as caught:
                    await self.service.request_end_pair(
                        self.session,
                        round_id=7,
                        user_id=MENTEE,
                        pair_id=PAIR,
                        actor_id=RAISER,
                        reviewer_id=reviewer,
                        reason="",
                    )
                self.assertEqual(
                    str(caught.exception),
                    "Neither person in the pair can review a request to end it.",
                )
        self.approvals.raise_request.assert_not_awaited()

    async def test_ending_a_pair_cannot_be_handed_to_either_person(self):
        self.approvals.get_request.return_value = _end_pair()
        for reviewer in (MENTOR, MENTEE):
            with self.subTest(reviewer=reviewer):
                with self.assertRaises(ValueError):
                    await self.service.reassign(
                        self.session,
                        request_id=61,
                        actor_id=RAISER,
                        reviewer_id=reviewer,
                    )
        self.approvals.reassign.assert_not_awaited()

    async def test_a_pending_end_pair_is_listed_for_either_person(self):
        self.approvals.list_pending_for_targets.return_value = {"501": _end_pair()}

        result = await self.service.pending_for_participant(
            self.session, 7, MENTOR, pair_ids=[PAIR, 502]
        )

        self.approvals.list_pending_for_targets.assert_awaited_once_with(
            self.session, "end_pair", ["501", "502"]
        )
        self.assertEqual([r["action"] for r in result], ["end_pair"])
        self.assertEqual(result[0]["pair_id"], PAIR)

    async def test_no_pairs_means_no_end_pair_lookup(self):
        await self.service.pending_for_participant(self.session, 7, MENTOR)

        self.approvals.list_pending_for_targets.assert_not_awaited()


if __name__ == "__main__":
    unittest.main()
