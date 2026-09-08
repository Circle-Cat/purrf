import unittest
import uuid
from datetime import datetime, timezone

from backend.common.mentorship_enums import CommunicationMethod
from backend.common.user_enums import BlockRequestStatus
from backend.entity.users_entity import UsersEntity
from backend.repository.block_request_repository import BlockRequestRepository
from tests.backend_test.repository_test.base_repository_test_lib import (
    BaseRepositoryTestLib,
)


class TestBlockRequestRepository(BaseRepositoryTestLib):
    async def asyncSetUp(self):
        await super().asyncSetUp()

        self.repo = BlockRequestRepository()

        # Every column on block_request that names a person carries a real
        # foreign key, so these rows have to exist before a request can.
        self.target = self._make_user()
        self.other_target = self._make_user()
        self.raiser = self._make_user()
        self.reviewer = self._make_user()
        self.other_reviewer = self._make_user()
        await self.insert_entities([
            self.target,
            self.other_target,
            self.raiser,
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

    async def _create(self, *, target=None, reviewer=None, reason="second no-show"):
        return await self.repo.create(
            self.session,
            target_user_id=(target or self.target).user_id,
            raised_by=self.raiser.user_id,
            raised_from="recruiting_board",
            reason=reason,
            reviewer_id=(reviewer or self.reviewer).user_id,
        )

    async def test_create_starts_pending(self):
        row = await self._create()

        self.assertIs(row.status, BlockRequestStatus.PENDING)
        self.assertIsNone(row.decided_by)
        self.assertIsNone(row.decided_at)
        self.assertIsNotNone(row.request_id)

    async def test_get_returns_the_row(self):
        row = await self._create()

        fetched = await self.repo.get(self.session, row.request_id)

        self.assertEqual(fetched.request_id, row.request_id)
        self.assertEqual(fetched.reason, "second no-show")

    async def test_get_missing_request_is_none(self):
        self.assertIsNone(await self.repo.get(self.session, 9_999_999))

    async def test_list_pending_for_reviewer_is_scoped(self):
        """The queue is per-reviewer: a request names one person, and only
        that person sees it."""
        mine = await self._create()
        await self._create(target=self.other_target, reviewer=self.other_reviewer)

        rows = await self.repo.list_pending_for_reviewer(
            self.session, self.reviewer.user_id
        )

        self.assertEqual([r.request_id for r in rows], [mine.request_id])

    async def test_list_pending_for_reviewer_is_oldest_first(self):
        first = await self._create()
        second = await self._create(target=self.other_target)

        rows = await self.repo.list_pending_for_reviewer(
            self.session, self.reviewer.user_id
        )

        self.assertEqual(
            [r.request_id for r in rows], [first.request_id, second.request_id]
        )

    async def test_list_pending_for_reviewer_excludes_closed(self):
        row = await self._create()
        await self.repo.close(
            self.session,
            row.request_id,
            status=BlockRequestStatus.APPROVED,
            decided_by=self.reviewer.user_id,
            decision_note=None,
        )

        rows = await self.repo.list_pending_for_reviewer(
            self.session, self.reviewer.user_id
        )

        self.assertEqual(rows, [])

    async def test_set_reviewer_moves_the_request(self):
        row = await self._create()

        await self.repo.set_reviewer(
            self.session, row.request_id, self.other_reviewer.user_id
        )

        refetched = await self.repo.get(self.session, row.request_id)
        self.assertEqual(refetched.reviewer_id, self.other_reviewer.user_id)
        self.assertIs(refetched.status, BlockRequestStatus.PENDING)

    async def test_close_records_decision(self):
        row = await self._create()

        await self.repo.close(
            self.session,
            row.request_id,
            status=BlockRequestStatus.REJECTED,
            decided_by=self.reviewer.user_id,
            decision_note="not enough evidence",
        )

        refetched = await self.repo.get(self.session, row.request_id)
        self.assertIs(refetched.status, BlockRequestStatus.REJECTED)
        self.assertEqual(refetched.decided_by, self.reviewer.user_id)
        self.assertIsNotNone(refetched.decided_at)
        self.assertEqual(refetched.decision_note, "not enough evidence")

    async def test_list_pending_for_target_finds_the_open_ones(self):
        row = await self._create()

        found = await self.repo.list_pending_for_target(
            self.session, self.target.user_id
        )

        self.assertEqual([r.request_id for r in found], [row.request_id])

    async def test_list_pending_for_target_returns_every_open_row(self):
        # The service's "one pending per target" rule is a read-then-write, so
        # a concurrent pair can both land. Superseding must see both.
        first = await self._create()
        second = await self._create()

        found = await self.repo.list_pending_for_target(
            self.session, self.target.user_id
        )

        self.assertEqual(
            {r.request_id for r in found}, {first.request_id, second.request_id}
        )

    async def test_closed_request_is_not_pending_for_target(self):
        row = await self._create()

        closed = await self.repo.close(
            self.session,
            row.request_id,
            status=BlockRequestStatus.SUPERSEDED,
            decided_by=self.reviewer.user_id,
            decision_note=None,
        )

        self.assertTrue(closed)
        self.assertEqual(
            await self.repo.list_pending_for_target(self.session, self.target.user_id),
            [],
        )

    async def test_closing_an_already_closed_request_reports_no_row(self):
        row = await self._create()
        await self.repo.close(
            self.session,
            row.request_id,
            status=BlockRequestStatus.APPROVED,
            decided_by=self.reviewer.user_id,
            decision_note=None,
        )

        again = await self.repo.close(
            self.session,
            row.request_id,
            status=BlockRequestStatus.REJECTED,
            decided_by=self.reviewer.user_id,
            decision_note="second click",
        )

        self.assertFalse(again)
        refetched = await self.repo.get(self.session, row.request_id)
        self.assertIs(refetched.status, BlockRequestStatus.APPROVED)
        self.assertIsNone(refetched.decision_note)

    async def test_set_reviewer_on_a_closed_request_reports_no_row(self):
        row = await self._create()
        await self.repo.close(
            self.session,
            row.request_id,
            status=BlockRequestStatus.APPROVED,
            decided_by=self.reviewer.user_id,
            decision_note=None,
        )

        moved = await self.repo.set_reviewer(
            self.session, row.request_id, self.other_reviewer.user_id
        )

        self.assertFalse(moved)

    async def test_list_pending_for_target_is_empty_when_never_requested(self):
        self.assertEqual(
            await self.repo.list_pending_for_target(
                self.session, self.other_target.user_id
            ),
            [],
        )


if __name__ == "__main__":
    unittest.main()
