import sys
import types
import unittest
from unittest.mock import patch, MagicMock, AsyncMock

_entity_mock = types.ModuleType("backend.entity")
_entity_mock.__path__ = []

_backend_mock = MagicMock()
_backend_mock.entity = _entity_mock

sys.modules["backend"] = _backend_mock
sys.modules["backend.common"] = MagicMock()
sys.modules["backend.common.database"] = MagicMock()
sys.modules["backend.common.base"] = MagicMock()
sys.modules["backend.common.logger"] = MagicMock()
sys.modules["backend.entity"] = _entity_mock

import tools.init_db as init_db_module  # noqa: E402


class TestLoadAllEntities(unittest.TestCase):
    """Tests for load_all_entities() entity module discovery and import."""

    @patch.object(init_db_module, "importlib")
    @patch.object(init_db_module, "pkgutil")
    def test_imports_all_discovered_modules(self, mock_pkgutil, mock_importlib):
        """Each module returned by pkgutil.iter_modules is imported exactly once."""
        mock_pkgutil.iter_modules.return_value = [
            (None, "backend.entity.user", False),
            (None, "backend.entity.session", False),
        ]

        init_db_module.load_all_entities()

        mock_importlib.import_module.assert_any_call("backend.entity.user")
        mock_importlib.import_module.assert_any_call("backend.entity.session")
        self.assertEqual(mock_importlib.import_module.call_count, 2)

    @patch.object(init_db_module, "importlib")
    @patch.object(init_db_module, "pkgutil")
    def test_no_modules_discovered(self, mock_pkgutil, mock_importlib):
        """No import_module calls are made when iter_modules returns nothing."""
        mock_pkgutil.iter_modules.return_value = []

        init_db_module.load_all_entities()

        mock_importlib.import_module.assert_not_called()


class TestResetDatabase(unittest.IsolatedAsyncioTestCase):
    """Tests for reset_database() schema teardown and recreation."""

    @patch.object(init_db_module, "load_all_entities")
    @patch.object(init_db_module, "Base")
    @patch.object(init_db_module, "Database")
    async def test_drops_and_recreates_schema(
        self, mock_db_class, mock_base, mock_load_entities
    ):
        """DROP SCHEMA and CREATE SCHEMA are executed in order, followed by create_all."""
        mock_engine = MagicMock()
        mock_db_class.return_value.get_engine.return_value = mock_engine

        mock_conn = AsyncMock()
        mock_ctx = AsyncMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_ctx.__aexit__ = AsyncMock(return_value=False)
        mock_engine.begin.return_value = mock_ctx
        mock_engine.dispose = AsyncMock()

        await init_db_module.reset_database()

        mock_load_entities.assert_called_once()
        self.assertEqual(mock_conn.execute.await_count, 2)
        drop_sql = mock_conn.execute.call_args_list[0].args[0].text
        create_sql = mock_conn.execute.call_args_list[1].args[0].text
        self.assertIn("DROP SCHEMA", drop_sql)
        self.assertIn("CREATE SCHEMA", create_sql)
        mock_conn.run_sync.assert_awaited_once_with(mock_base.metadata.create_all)
        mock_engine.dispose.assert_awaited_once()

    @patch.object(init_db_module, "load_all_entities")
    @patch.object(init_db_module, "Database")
    async def test_disposes_engine_even_if_create_fails(
        self, mock_db_class, mock_load_entities
    ):
        """Exception from create_all propagates; engine.dispose is not called since
        it is inside the same transaction context that raises."""
        mock_engine = MagicMock()
        mock_db_class.return_value.get_engine.return_value = mock_engine

        mock_conn = AsyncMock()
        mock_conn.run_sync.side_effect = Exception("create failed")
        mock_ctx = AsyncMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_ctx.__aexit__ = AsyncMock(return_value=False)
        mock_engine.begin.return_value = mock_ctx
        mock_engine.dispose = AsyncMock()

        with self.assertRaises(Exception):
            await init_db_module.reset_database()

        mock_engine.dispose.assert_not_awaited()


class TestMain(unittest.TestCase):
    """Tests for main() orchestration of reset and alembic stamp."""

    @patch.object(init_db_module, "command")
    @patch.object(init_db_module, "Config")
    @patch.object(init_db_module, "asyncio")
    def test_resets_db_then_stamps_head(self, mock_asyncio, mock_config, mock_command):
        """reset_database runs first, then alembic stamp head is called."""
        mock_cfg = MagicMock()
        mock_config.return_value = mock_cfg

        init_db_module.main()

        mock_asyncio.run.assert_called_once()
        mock_config.assert_called_once_with("alembic.ini")
        mock_command.stamp.assert_called_once_with(mock_cfg, "head")

    @patch.object(init_db_module, "command")
    @patch.object(init_db_module, "Config")
    @patch.object(init_db_module, "asyncio")
    def test_stamp_not_called_if_reset_fails(
        self, mock_asyncio, mock_config, mock_command
    ):
        """alembic stamp is skipped when reset_database raises an exception."""

        def raise_and_close(coro):
            coro.close()
            raise Exception("reset failed")

        mock_asyncio.run.side_effect = raise_and_close

        with self.assertRaises(Exception):
            init_db_module.main()

        mock_command.stamp.assert_not_called()


if __name__ == "__main__":
    unittest.main()
