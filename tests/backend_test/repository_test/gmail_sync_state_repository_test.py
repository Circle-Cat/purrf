import asyncio
import unittest
import uuid

from sqlalchemy import delete

from backend.common.database import Database
from backend.entity.gmail_sync_state_entity import GmailSyncStateEntity
from backend.repository.gmail_sync_state_repository import GmailSyncStateRepository
from tests.backend_test.repository_test.base_repository_test_lib import (
    BaseRepositoryTestLib,
)


class TestGmailSyncStateRepository(BaseRepositoryTestLib):
    async def asyncSetUp(self):
        await super().asyncSetUp()
        self.repo = GmailSyncStateRepository()

    async def test_get_returns_none_before_create(self):
        self.assertIsNone(await self.repo.get(self.session, "box@example.com"))

    async def test_create_then_get_round_trips_a_uint64_cursor(self):
        big = 2**40 + 5
        created = await self.repo.create(self.session, "box@example.com", big)
        fetched = await self.repo.get(self.session, "box@example.com")
        self.assertEqual(fetched.id, created.id)
        self.assertEqual(fetched.last_history_id, big)

    async def test_get_for_update_returns_the_row(self):
        await self.repo.create(self.session, "box@example.com", 10)
        row = await self.repo.get_for_update(self.session, "box@example.com")
        self.assertEqual(row.last_history_id, 10)

    async def test_rows_are_per_address(self):
        await self.repo.create(self.session, "a@example.com", 1)
        await self.repo.create(self.session, "b@example.com", 2)
        self.assertEqual(
            (await self.repo.get(self.session, "b@example.com")).last_history_id, 2
        )

    async def test_get_single_returns_none_without_rows(self):
        self.assertIsNone(await self.repo.get_single(self.session))

    async def test_get_single_returns_the_only_row(self):
        created = await self.repo.create(self.session, "box@example.com", 7)
        self.assertEqual((await self.repo.get_single(self.session)).id, created.id)

    async def test_get_single_returns_none_when_the_row_is_ambiguous(self):
        await self.repo.create(self.session, "a@example.com", 1)
        await self.repo.create(self.session, "b@example.com", 2)
        self.assertIsNone(await self.repo.get_single(self.session))


class TestGmailSyncStateRowLock(unittest.IsolatedAsyncioTestCase):
    """Two real sessions on two connections, so the row must be committed."""

    async def asyncSetUp(self):
        self.db = Database(echo=False)
        self.repo = GmailSyncStateRepository()
        self.address = f"lock-{uuid.uuid4().hex}@example.com"
        async with self.db.session() as session:
            await self.repo.create(session, self.address, 1)
            await session.commit()

    async def asyncTearDown(self):
        async with self.db.session() as session:
            await session.execute(
                delete(GmailSyncStateEntity).where(
                    GmailSyncStateEntity.email_address == self.address
                )
            )
            await session.commit()
        await self.db.close()

    async def test_second_locker_waits_until_the_first_commits(self):
        async with self.db.session() as first, self.db.session() as second:
            held = await self.repo.get_for_update(first, self.address)
            held.last_history_id = 2
            await first.flush()

            waiting = asyncio.create_task(
                self.repo.get_for_update(second, self.address)
            )
            try:
                done, _ = await asyncio.wait({waiting}, timeout=0.5)
                self.assertEqual(done, set(), "second session did not wait")

                await first.commit()
                row = await asyncio.wait_for(waiting, timeout=5)
            finally:
                waiting.cancel()
            self.assertEqual(row.last_history_id, 2)
            await second.commit()


if __name__ == "__main__":
    unittest.main()
