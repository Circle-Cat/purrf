import asyncio
from unittest import TestCase, main
from unittest.mock import patch, MagicMock, AsyncMock
from backend.common.database import Database

TEST_DATABASE_URL = "postgresql+asyncpg://test"


# Shared patch stack: every test that instantiates Database needs these three patches
# because DATABASE_URL is evaluated at module level in environment_constants.py.
def _common_patches():
    return (
        patch("backend.common.database.DATABASE_URL", TEST_DATABASE_URL),
        patch("backend.common.database.create_async_engine"),
        patch("backend.common.database.async_sessionmaker"),
    )


class _BaseDatabaseTest(TestCase):
    """Base class that applies the common patches for every test method."""

    def setUp(self):
        patches = _common_patches()
        self.url_patch, self.engine_patch, self.sessionmaker_patch = patches
        self.url_patch.start()
        self.mock_create_engine = self.engine_patch.start()
        self.mock_sessionmaker = self.sessionmaker_patch.start()

    def tearDown(self):
        self.sessionmaker_patch.stop()
        self.engine_patch.stop()
        self.url_patch.stop()


class TestDatabaseInit(_BaseDatabaseTest):
    """Tests for Database.__init__ configuration."""

    def test_creates_engine_with_pool_settings(self):
        Database(echo=False)

        self.mock_create_engine.assert_called_once_with(
            TEST_DATABASE_URL,
            echo=False,
            pool_recycle=25,
            pool_pre_ping=True,
        )
        self.mock_sessionmaker.assert_called_once_with(
            bind=self.mock_create_engine.return_value,
            autoflush=False,
            expire_on_commit=False,
        )

    def test_with_echo_true(self):
        Database(echo=True)

        self.mock_create_engine.assert_called_once_with(
            TEST_DATABASE_URL,
            echo=True,
            pool_recycle=25,
            pool_pre_ping=True,
        )

    @patch("backend.common.database.DATABASE_URL", None)
    def test_raises_when_database_url_not_set(self):
        with self.assertRaises(ValueError) as ctx:
            Database()

        self.assertIn("DATABASE_URL must be set", str(ctx.exception))

    @patch("backend.common.database.DATABASE_URL", "")
    def test_raises_when_database_url_empty(self):
        with self.assertRaises(ValueError):
            Database()


class TestDatabaseEngine(_BaseDatabaseTest):
    """Tests for Database.get_engine and close."""

    def test_get_engine_returns_engine(self):
        db = Database()

        self.assertEqual(db.get_engine(), self.mock_create_engine.return_value)

    def test_close_disposes_engine(self):
        mock_engine = self.mock_create_engine.return_value
        mock_engine.dispose = AsyncMock()

        db = Database()
        asyncio.get_event_loop().run_until_complete(db.close())

        mock_engine.dispose.assert_called_once()


class TestDatabaseSession(_BaseDatabaseTest):
    """Tests for Database.session context manager."""

    def test_session_yields_and_closes(self):
        mock_session = AsyncMock()
        self.mock_sessionmaker.return_value = MagicMock(return_value=mock_session)

        db = Database()

        async def run():
            async with db.session() as session:
                self.assertEqual(session, mock_session)
            mock_session.close.assert_called_once()
            mock_session.rollback.assert_not_called()

        asyncio.get_event_loop().run_until_complete(run())

    def test_session_rollbacks_on_exception(self):
        mock_session = AsyncMock()
        self.mock_sessionmaker.return_value = MagicMock(return_value=mock_session)

        db = Database()

        async def run():
            with self.assertRaises(RuntimeError):
                async with db.session():
                    raise RuntimeError("test error")
            mock_session.rollback.assert_called_once()
            mock_session.close.assert_called_once()

        asyncio.get_event_loop().run_until_complete(run())


if __name__ == "__main__":
    main()
