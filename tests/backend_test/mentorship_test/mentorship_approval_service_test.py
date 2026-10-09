"""The mentorship console's side of approvals: scoped to its own actions,
and described the way the console shows them."""

import unittest
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

from backend.common.approval_enums import ApprovalRequestStatus
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
        self.service = MentorshipApprovalService(
            approval_service=self.approvals,
            matching_storage=self.storage,
            users_repository=self.users,
            rounds_repository=self.rounds,
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
            ("publish_matching", "exempt_matching", "withdraw_participant"),
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
        self.approvals.get_pending_for_target.return_value = _withdrawal()

        result = await self.service.pending_for_participant(self.session, 7, PERSON)

        self.approvals.get_pending_for_target.assert_awaited_once_with(
            self.session, "withdraw_participant", "7:21"
        )
        self.assertEqual([r["request_id"] for r in result], [41])
        self.assertEqual(result[0]["raised_by"]["user_id"], RAISER)
        self.assertEqual(result[0]["reviewer"]["user_id"], REVIEWER)

    async def test_no_pending_request_on_a_participant_is_an_empty_list(self):
        self.assertEqual(
            await self.service.pending_for_participant(self.session, 7, PERSON), []
        )


if __name__ == "__main__":
    unittest.main()
