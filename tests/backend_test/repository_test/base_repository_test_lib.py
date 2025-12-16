import unittest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from backend.common.database import Database


class BaseRepositoryTestLib(unittest.IsolatedAsyncioTestCase):
    """
    A reusable base test class for repository tests.

    Features:
      - Each test gets an isolated database transaction.
      - Uses savepoint mode so inner commit() won't persist to database.
      - Auto-initializes Database, engine, session, transaction.
      - Provides helper to insert entities safely.
    """

    async def asyncSetUp(self):
        # 1. Initialize database wrapper
        self.db = Database(echo=True)

        # 2. Open manual connection
        self.connection = await self.db.get_engine().connect()

        # 3. Begin outer transaction (rolled back after each test)
        self.trans = await self.connection.begin()

        # 4. Bind sessionmaker to this specific connection
        self.session_maker = async_sessionmaker(
            bind=self.connection,
            expire_on_commit=False,
            join_transaction_mode="create_savepoint",  # Key: prevents commit from persisting
            class_=AsyncSession,
        )
        self.session = self.session_maker()

    async def asyncTearDown(self):
        # Cleanup session + rollback whole transaction
        await self.session.close()
        await self.trans.rollback()
        await self.connection.close()
        await self.db.close()

    async def insert_entities(self, entities):
        """
        Insert ORM entities into the active test session.

        With `join_transaction_mode="create_savepoint"`, `flush()` writes the entities
        into the test savepoint without committing to the real database.
        """
        self.session.add_all(entities)
        await self.session.flush()
