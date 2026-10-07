import unittest
import uuid
from datetime import datetime, timezone

from sqlalchemy.exc import IntegrityError

from backend.common.approval_enums import ApprovalRequestStatus
from backend.common.mentorship_enums import CommunicationMethod
from backend.entity.users_entity import UsersEntity
from backend.repository.approval_request_repository import (
    ApprovalRequestRepository,
)
from tests.backend_test.repository_test.base_repository_test_lib import (
    BaseRepositoryTestLib,
)

PUBLISH = "publish_matching"
EXEMPT = "exempt_matching"


class TestApprovalRequestRepository(BaseRepositoryTestLib):
    async def asyncSetUp(self):
        await super().asyncSetUp()
        self.repo = ApprovalRequestRepository()
        self.raiser = self._make_user()
        self.other_raiser = self._make_user()
        self.reviewer = self._make_user()
        self.other_reviewer = self._make_user()
        await self.insert_entities([
            self.raiser,
            self.other_raiser,
            self.reviewer,
            self.other_reviewer,
        ])

    def _make_user(self):
        return UsersEntity(
            first_name="T",
            last_name=uuid.uuid4().hex[:10],
            timezone="UTC",
            timezone_updated_at=datetime.now(timezone.utc),
            communication_channel=CommunicationMethod.EMAIL,
            is_active=True,
            updated_timestamp=datetime.now(timezone.utc),
        )

    async def _create(
        self,
        *,
        action=PUBLISH,
        target_type="matching_run",
        target_id="run-a",
        raiser=None,
        reviewer=None,
        payload=None,
    ):
        return await self.repo.create(
            self.session,
            action=action,
            target_type=target_type,
            target_id=target_id,
            payload=payload if payload is not None else {"round_id": 7},
            reason="matcher result reviewed",
            raised_by=(raiser or self.raiser).user_id,
            reviewer_id=(reviewer or self.reviewer).user_id,
        )

    async def test_create_starts_pending_and_keeps_the_payload(self):
        row = await self._create(payload={"round_id": 41})

        fetched = await self.repo.get(self.session, row.request_id)

        self.assertIs(fetched.status, ApprovalRequestStatus.PENDING)
        self.assertEqual(fetched.payload, {"round_id": 41})
        self.assertEqual(fetched.target_id, "run-a")
        self.assertIsNone(fetched.decided_by)
        self.assertIsNone(fetched.decided_at)

    async def test_get_for_update_returns_the_row(self):
        row = await self._create()

        fetched = await self.repo.get(self.session, row.request_id, for_update=True)

        self.assertEqual(fetched.request_id, row.request_id)

    async def test_get_missing_request_is_none(self):
        self.assertIsNone(await self.repo.get(self.session, 9_999_999))

    async def test_a_second_pending_request_on_one_target_is_refused(self):
        await self._create()

        with self.assertRaises(IntegrityError):
            await self._create(raiser=self.other_raiser)

    async def test_the_same_target_id_under_another_action_is_separate(self):
        await self._create(action=PUBLISH, target_id="12")

        other = await self._create(
            action=EXEMPT, target_type="round_participant", target_id="12"
        )

        self.assertIs(other.status, ApprovalRequestStatus.PENDING)

    async def test_a_closed_request_frees_the_target_for_a_new_one(self):
        first = await self._create()
        await self.repo.close(
            self.session,
            first.request_id,
            status=ApprovalRequestStatus.REJECTED,
            decided_by=self.reviewer.user_id,
            decision_comment="two mentors over their slots",
        )

        second = await self._create()

        self.assertNotEqual(second.request_id, first.request_id)

    async def test_get_pending_for_target_ignores_closed_and_other_targets(self):
        closed = await self._create(target_id="run-a")
        await self.repo.close(
            self.session,
            closed.request_id,
            status=ApprovalRequestStatus.WITHDRAWN,
            decided_by=self.raiser.user_id,
            decision_comment=None,
        )
        await self._create(target_id="run-b")

        self.assertIsNone(
            await self.repo.get_pending_for_target(
                self.session, PUBLISH, "matching_run", "run-a"
            )
        )
        pending = await self.repo.get_pending_for_target(
            self.session, PUBLISH, "matching_run", "run-b"
        )
        self.assertEqual(pending.target_id, "run-b")

    async def test_latest_closed_for_target_is_the_newest_decision(self):
        older = await self._create()
        await self.repo.close(
            self.session,
            older.request_id,
            status=ApprovalRequestStatus.REJECTED,
            decided_by=self.reviewer.user_id,
            decision_comment="first rejection",
        )
        newer = await self._create()
        await self.repo.close(
            self.session,
            newer.request_id,
            status=ApprovalRequestStatus.REJECTED,
            decided_by=self.reviewer.user_id,
            decision_comment="second rejection",
        )
        await self._create()

        latest = await self.repo.get_latest_closed_for_target(
            self.session, PUBLISH, "matching_run", "run-a"
        )

        self.assertEqual(latest.request_id, newer.request_id)
        self.assertEqual(latest.decision_comment, "second rejection")

    async def test_latest_closed_for_target_is_none_when_only_pending(self):
        await self._create()

        self.assertIsNone(
            await self.repo.get_latest_closed_for_target(
                self.session, PUBLISH, "matching_run", "run-a"
            )
        )

    async def test_list_pending_for_reviewer_is_scoped_by_reviewer_and_action(self):
        mine = await self._create(target_id="run-a")
        await self._create(target_id="run-b", reviewer=self.other_reviewer)
        await self._create(
            action=EXEMPT,
            target_type="round_participant",
            target_id="7:31",
        )

        rows = await self.repo.list_pending_for_reviewer(
            self.session, self.reviewer.user_id, [PUBLISH]
        )

        self.assertEqual([r.request_id for r in rows], [mine.request_id])

    async def test_list_pending_for_reviewer_with_no_actions_is_empty(self):
        await self._create()

        self.assertEqual(
            await self.repo.list_pending_for_reviewer(
                self.session, self.reviewer.user_id, []
            ),
            [],
        )

    async def test_list_pending_raised_by_is_scoped_and_pending_only(self):
        mine = await self._create(target_id="run-a")
        closed = await self._create(target_id="run-b")
        await self.repo.close(
            self.session,
            closed.request_id,
            status=ApprovalRequestStatus.APPROVED,
            decided_by=self.reviewer.user_id,
            decision_comment=None,
        )
        await self._create(target_id="run-c", raiser=self.other_raiser)

        rows = await self.repo.list_pending_raised_by(
            self.session, self.raiser.user_id, [PUBLISH, EXEMPT]
        )

        self.assertEqual([r.request_id for r in rows], [mine.request_id])

    async def test_set_reviewer_moves_a_pending_request(self):
        row = await self._create()

        moved = await self.repo.set_reviewer(
            self.session, row.request_id, self.other_reviewer.user_id
        )

        self.assertTrue(moved)
        # Re-read from the database, not the identity map.
        await self.session.refresh(row)
        fetched = row
        self.assertEqual(fetched.reviewer_id, self.other_reviewer.user_id)

    async def test_set_reviewer_on_a_closed_request_does_nothing(self):
        row = await self._create()
        await self.repo.close(
            self.session,
            row.request_id,
            status=ApprovalRequestStatus.APPROVED,
            decided_by=self.reviewer.user_id,
            decision_comment=None,
        )

        moved = await self.repo.set_reviewer(
            self.session, row.request_id, self.other_reviewer.user_id
        )

        self.assertFalse(moved)

    async def test_close_records_who_and_when(self):
        row = await self._create()

        closed = await self.repo.close(
            self.session,
            row.request_id,
            status=ApprovalRequestStatus.REJECTED,
            decided_by=self.reviewer.user_id,
            decision_comment="mentee already paired",
        )

        self.assertTrue(closed)
        # Re-read from the database, not the identity map.
        await self.session.refresh(row)
        fetched = row
        self.assertIs(fetched.status, ApprovalRequestStatus.REJECTED)
        self.assertEqual(fetched.decided_by, self.reviewer.user_id)
        self.assertIsNotNone(fetched.decided_at)
        self.assertEqual(fetched.decision_comment, "mentee already paired")

    async def test_close_twice_only_lands_once(self):
        row = await self._create()
        await self.repo.close(
            self.session,
            row.request_id,
            status=ApprovalRequestStatus.APPROVED,
            decided_by=self.reviewer.user_id,
            decision_comment=None,
        )

        again = await self.repo.close(
            self.session,
            row.request_id,
            status=ApprovalRequestStatus.REJECTED,
            decided_by=self.reviewer.user_id,
            decision_comment="too late",
        )

        self.assertFalse(again)
        # Re-read from the database, not the identity map.
        await self.session.refresh(row)
        fetched = row
        self.assertIs(fetched.status, ApprovalRequestStatus.APPROVED)


if __name__ == "__main__":
    unittest.main()
