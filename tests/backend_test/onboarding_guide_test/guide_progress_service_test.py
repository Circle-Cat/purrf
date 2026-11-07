import unittest
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

from backend.common.onboarding_guide_enums import GuideProgressStatus
from backend.onboarding_guide.guide_progress_service import (
    MAX_GUIDE_SNOOZES,
    GuideProgressService,
)

# Two users and two keys, so a read that mixes them up cannot pass.
USER_ID = 7
OTHER_USER_ID = 8
KEY = "first-login"
OTHER_KEY = "recruiting-board"

CREATED = datetime(2026, 11, 1, 9, 0, tzinfo=timezone.utc)
UPDATED = datetime(2026, 11, 2, 10, 30, tzinfo=timezone.utc)


def _row(user_id=USER_ID, guide_key=KEY, status=GuideProgressStatus.SNOOZED, count=0):
    return SimpleNamespace(
        user_id=user_id,
        guide_key=guide_key,
        status=status,
        snooze_count=count,
        created_at=CREATED,
        updated_at=UPDATED,
    )


class TestGuideProgressService(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.calls = MagicMock()
        self.session = MagicMock()
        self.session.commit = AsyncMock()
        self.calls.attach_mock(self.session.commit, "commit")

        self.repository = MagicMock()
        self.repository.list_by_user = AsyncMock(return_value=[])
        self.repository.get_for_update = AsyncMock(return_value=None)
        self.repository.upsert = AsyncMock(
            side_effect=lambda session, user_id, guide_key, status, snooze_count: _row(
                user_id=user_id, guide_key=guide_key, status=status, count=snooze_count
            )
        )
        self.calls.attach_mock(self.repository.upsert, "upsert")

        self.service = GuideProgressService(self.repository)

    def _written(self):
        return self.repository.upsert.await_args.kwargs

    async def test_list_for_user_reads_the_callers_rows(self):
        self.repository.list_by_user.return_value = [
            _row(guide_key=KEY, status=GuideProgressStatus.COMPLETED),
            _row(guide_key=OTHER_KEY, status=GuideProgressStatus.SNOOZED, count=2),
        ]

        result = await self.service.list_for_user(self.session, USER_ID)

        self.repository.list_by_user.assert_awaited_once_with(self.session, USER_ID)
        self.assertEqual([dto.guide_key for dto in result], [KEY, OTHER_KEY])
        self.assertEqual(result[1].status, GuideProgressStatus.SNOOZED)
        self.assertEqual(result[1].snooze_count, 2)
        self.assertEqual(result[1].updated_at, UPDATED)

    async def test_list_for_user_does_not_commit(self):
        await self.service.list_for_user(self.session, USER_ID)

        self.session.commit.assert_not_awaited()

    async def test_record_reads_the_row_for_this_user_and_key(self):
        await self.service.record(
            self.session, OTHER_USER_ID, OTHER_KEY, GuideProgressStatus.COMPLETED
        )

        self.repository.get_for_update.assert_awaited_once_with(
            self.session, OTHER_USER_ID, OTHER_KEY
        )
        self.assertEqual(self._written()["user_id"], OTHER_USER_ID)
        self.assertEqual(self._written()["guide_key"], OTHER_KEY)

    async def test_completing_a_new_guide_writes_completed_with_no_snoozes(self):
        result = await self.service.record(
            self.session, USER_ID, KEY, GuideProgressStatus.COMPLETED
        )

        self.assertEqual(
            self._written(),
            {
                "user_id": USER_ID,
                "guide_key": KEY,
                "status": GuideProgressStatus.COMPLETED,
                "snooze_count": 0,
            },
        )
        self.assertEqual(result.status, GuideProgressStatus.COMPLETED)

    async def test_completing_keeps_the_snooze_count_so_far(self):
        self.repository.get_for_update.return_value = _row(count=2)

        await self.service.record(
            self.session, USER_ID, KEY, GuideProgressStatus.COMPLETED
        )

        self.assertEqual(self._written()["status"], GuideProgressStatus.COMPLETED)
        self.assertEqual(self._written()["snooze_count"], 2)

    async def test_dismissing_overwrites_a_completed_guide(self):
        self.repository.get_for_update.return_value = _row(
            status=GuideProgressStatus.COMPLETED, count=1
        )

        await self.service.record(
            self.session, USER_ID, KEY, GuideProgressStatus.DISMISSED
        )

        self.assertEqual(self._written()["status"], GuideProgressStatus.DISMISSED)
        self.assertEqual(self._written()["snooze_count"], 1)

    async def test_first_snooze_is_snoozed_with_count_one(self):
        result = await self.service.record(
            self.session, USER_ID, KEY, GuideProgressStatus.SNOOZED
        )

        self.assertEqual(self._written()["status"], GuideProgressStatus.SNOOZED)
        self.assertEqual(self._written()["snooze_count"], 1)
        self.assertEqual(result.snooze_count, 1)

    async def test_second_snooze_is_snoozed_with_count_two(self):
        self.repository.get_for_update.return_value = _row(count=1)

        await self.service.record(
            self.session, USER_ID, KEY, GuideProgressStatus.SNOOZED
        )

        self.assertEqual(self._written()["status"], GuideProgressStatus.SNOOZED)
        self.assertEqual(self._written()["snooze_count"], 2)

    async def test_third_snooze_dismisses_the_guide(self):
        self.assertEqual(MAX_GUIDE_SNOOZES, 3)
        self.repository.get_for_update.return_value = _row(count=2)

        result = await self.service.record(
            self.session, USER_ID, KEY, GuideProgressStatus.SNOOZED
        )

        self.assertEqual(self._written()["status"], GuideProgressStatus.DISMISSED)
        self.assertEqual(self._written()["snooze_count"], 3)
        self.assertEqual(result.status, GuideProgressStatus.DISMISSED)

    async def test_snoozing_a_completed_guide_changes_nothing(self):
        stored = _row(status=GuideProgressStatus.COMPLETED, count=1)
        self.repository.get_for_update.return_value = stored

        result = await self.service.record(
            self.session, USER_ID, KEY, GuideProgressStatus.SNOOZED
        )

        self.repository.upsert.assert_not_awaited()
        self.session.commit.assert_not_awaited()
        self.assertEqual(result.status, GuideProgressStatus.COMPLETED)
        self.assertEqual(result.snooze_count, 1)
        self.assertEqual(result.updated_at, UPDATED)

    async def test_snoozing_a_dismissed_guide_changes_nothing(self):
        self.repository.get_for_update.return_value = _row(
            status=GuideProgressStatus.DISMISSED, count=3
        )

        result = await self.service.record(
            self.session, USER_ID, KEY, GuideProgressStatus.SNOOZED
        )

        self.repository.upsert.assert_not_awaited()
        self.session.commit.assert_not_awaited()
        self.assertEqual(result.status, GuideProgressStatus.DISMISSED)
        self.assertEqual(result.snooze_count, 3)

    async def test_commit_comes_after_the_write(self):
        await self.service.record(
            self.session, USER_ID, KEY, GuideProgressStatus.SNOOZED
        )

        names = [call[0] for call in self.calls.mock_calls]
        self.assertEqual(names, ["upsert", "commit"])

    async def test_bad_keys_are_rejected_before_any_read_or_commit(self):
        for bad in ["", "Upper", "has space", "under_score", "a" * 65, "ok\n", "../x"]:
            with self.subTest(key=bad):
                with self.assertRaises(ValueError):
                    await self.service.record(
                        self.session, USER_ID, bad, GuideProgressStatus.COMPLETED
                    )

        self.repository.get_for_update.assert_not_awaited()
        self.repository.upsert.assert_not_awaited()
        self.session.commit.assert_not_awaited()

    async def test_keys_at_the_limits_are_accepted(self):
        for good in ["a", "0", "-", "a" * 64, "first-login-2"]:
            with self.subTest(key=good):
                await self.service.record(
                    self.session, USER_ID, good, GuideProgressStatus.COMPLETED
                )
                self.assertEqual(self._written()["guide_key"], good)


if __name__ == "__main__":
    unittest.main()
