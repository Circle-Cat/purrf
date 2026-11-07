import unittest
from datetime import datetime, timezone

from sqlalchemy import text

from backend.common.mentorship_enums import CommunicationMethod
from backend.common.onboarding_guide_enums import GuideProgressStatus
from backend.entity.user_guide_progress_entity import UserGuideProgressEntity
from backend.entity.users_entity import UsersEntity
from backend.repository.user_guide_progress_repository import (
    UserGuideProgressRepository,
)
from tests.backend_test.repository_test.base_repository_test_lib import (
    BaseRepositoryTestLib,
)

FIRST_KEY = "first-login"
SECOND_KEY = "recruiting-board"


def _make_user(first_name: str) -> UsersEntity:
    return UsersEntity(
        first_name=first_name,
        last_name="Ser",
        timezone="America/Los_Angeles",
        timezone_updated_at=datetime.now(timezone.utc),
        communication_channel=CommunicationMethod.EMAIL,
        is_active=True,
        updated_timestamp=datetime.now(timezone.utc),
    )


class TestUserGuideProgressRepository(BaseRepositoryTestLib):
    async def asyncSetUp(self):
        await super().asyncSetUp()
        self.repo = UserGuideProgressRepository()
        self.alice = _make_user("Alice")
        self.bob = _make_user("Bob")
        await self.insert_entities([self.alice, self.bob])

    async def _stored(self, user_id, guide_key):
        """Read the row back with plain SQL, past the session's identity map."""
        result = await self.session.execute(
            text(
                "SELECT status, snooze_count, created_at FROM user_guide_progress "
                "WHERE user_id = :user_id AND guide_key = :guide_key"
            ),
            {"user_id": user_id, "guide_key": guide_key},
        )
        return result.one_or_none()

    async def test_upsert_inserts_a_new_row(self):
        row = await self.repo.upsert(
            self.session,
            user_id=self.alice.user_id,
            guide_key=FIRST_KEY,
            status=GuideProgressStatus.SNOOZED,
            snooze_count=1,
        )

        self.assertEqual(row.user_id, self.alice.user_id)
        self.assertEqual(row.guide_key, FIRST_KEY)
        self.assertEqual(row.status, GuideProgressStatus.SNOOZED)
        self.assertEqual(row.snooze_count, 1)
        self.assertIsNotNone(row.created_at)
        self.assertIsNotNone(row.updated_at)
        stored = await self._stored(self.alice.user_id, FIRST_KEY)
        self.assertEqual(stored.status, "snoozed")
        self.assertEqual(stored.snooze_count, 1)

    async def test_upsert_updates_an_existing_row_and_keeps_created_at(self):
        self.session.add(
            UserGuideProgressEntity(
                user_id=self.alice.user_id,
                guide_key=FIRST_KEY,
                status=GuideProgressStatus.SNOOZED,
                snooze_count=1,
                created_at=datetime(2026, 1, 5, 8, 0, tzinfo=timezone.utc),
                updated_at=datetime(2026, 1, 5, 8, 0, tzinfo=timezone.utc),
            )
        )
        await self.session.flush()

        row = await self.repo.upsert(
            self.session,
            user_id=self.alice.user_id,
            guide_key=FIRST_KEY,
            status=GuideProgressStatus.DISMISSED,
            snooze_count=3,
        )

        self.assertEqual(row.status, GuideProgressStatus.DISMISSED)
        self.assertEqual(row.snooze_count, 3)
        self.assertEqual(
            row.created_at, datetime(2026, 1, 5, 8, 0, tzinfo=timezone.utc)
        )
        self.assertGreater(
            row.updated_at, datetime(2026, 1, 5, 8, 0, tzinfo=timezone.utc)
        )
        stored = await self._stored(self.alice.user_id, FIRST_KEY)
        self.assertEqual(stored.status, "dismissed")
        self.assertEqual(stored.snooze_count, 3)
        self.assertEqual(
            stored.created_at, datetime(2026, 1, 5, 8, 0, tzinfo=timezone.utc)
        )

    async def test_upsert_touches_only_its_own_user_and_key(self):
        for user, key in [
            (self.alice, FIRST_KEY),
            (self.alice, SECOND_KEY),
            (self.bob, FIRST_KEY),
        ]:
            await self.repo.upsert(
                self.session,
                user_id=user.user_id,
                guide_key=key,
                status=GuideProgressStatus.SNOOZED,
                snooze_count=1,
            )

        await self.repo.upsert(
            self.session,
            user_id=self.alice.user_id,
            guide_key=FIRST_KEY,
            status=GuideProgressStatus.COMPLETED,
            snooze_count=1,
        )

        self.assertEqual(
            (await self._stored(self.alice.user_id, FIRST_KEY)).status, "completed"
        )
        self.assertEqual(
            (await self._stored(self.alice.user_id, SECOND_KEY)).status, "snoozed"
        )
        self.assertEqual(
            (await self._stored(self.bob.user_id, FIRST_KEY)).status, "snoozed"
        )

    async def test_list_by_user_returns_only_the_callers_rows(self):
        await self.repo.upsert(
            self.session,
            user_id=self.alice.user_id,
            guide_key=SECOND_KEY,
            status=GuideProgressStatus.SNOOZED,
            snooze_count=2,
        )
        await self.repo.upsert(
            self.session,
            user_id=self.alice.user_id,
            guide_key=FIRST_KEY,
            status=GuideProgressStatus.COMPLETED,
            snooze_count=0,
        )
        await self.repo.upsert(
            self.session,
            user_id=self.bob.user_id,
            guide_key=FIRST_KEY,
            status=GuideProgressStatus.DISMISSED,
            snooze_count=3,
        )

        alice_rows = await self.repo.list_by_user(self.session, self.alice.user_id)
        bob_rows = await self.repo.list_by_user(self.session, self.bob.user_id)

        self.assertEqual(
            [(r.guide_key, r.status, r.snooze_count) for r in alice_rows],
            [
                (FIRST_KEY, GuideProgressStatus.COMPLETED, 0),
                (SECOND_KEY, GuideProgressStatus.SNOOZED, 2),
            ],
        )
        self.assertEqual(
            [(r.guide_key, r.status, r.snooze_count) for r in bob_rows],
            [(FIRST_KEY, GuideProgressStatus.DISMISSED, 3)],
        )

    async def test_list_by_user_is_empty_for_a_user_with_no_rows(self):
        await self.repo.upsert(
            self.session,
            user_id=self.alice.user_id,
            guide_key=FIRST_KEY,
            status=GuideProgressStatus.COMPLETED,
            snooze_count=0,
        )

        self.assertEqual(
            await self.repo.list_by_user(self.session, self.bob.user_id), []
        )

    async def test_get_for_update_finds_the_row_for_this_user_and_key(self):
        await self.repo.upsert(
            self.session,
            user_id=self.alice.user_id,
            guide_key=FIRST_KEY,
            status=GuideProgressStatus.SNOOZED,
            snooze_count=1,
        )
        await self.repo.upsert(
            self.session,
            user_id=self.bob.user_id,
            guide_key=SECOND_KEY,
            status=GuideProgressStatus.COMPLETED,
            snooze_count=2,
        )

        row = await self.repo.get_for_update(self.session, self.bob.user_id, SECOND_KEY)

        self.assertEqual(row.user_id, self.bob.user_id)
        self.assertEqual(row.guide_key, SECOND_KEY)
        self.assertEqual(row.status, GuideProgressStatus.COMPLETED)
        self.assertEqual(row.snooze_count, 2)

    async def test_get_for_update_is_none_when_the_user_has_not_seen_the_guide(self):
        await self.repo.upsert(
            self.session,
            user_id=self.alice.user_id,
            guide_key=FIRST_KEY,
            status=GuideProgressStatus.SNOOZED,
            snooze_count=1,
        )

        self.assertIsNone(
            await self.repo.get_for_update(self.session, self.bob.user_id, FIRST_KEY)
        )
        self.assertIsNone(
            await self.repo.get_for_update(self.session, self.alice.user_id, SECOND_KEY)
        )


if __name__ == "__main__":
    unittest.main()
