import sys
import unittest
from unittest.mock import patch, MagicMock

sys.modules["backend"] = MagicMock()
sys.modules["backend.common"] = MagicMock()
sys.modules["backend.common.logger"] = MagicMock()

import tools.migrate_db.migrate_db as migrate_db_module  # noqa: E402


class TestMigrateDb(unittest.TestCase):
    """Tests for migrate_db.main() workspace validation and alembic upgrade call."""

    def test_exits_when_no_workspace_dir(self):
        """Exits with code 1 when BUILD_WORKSPACE_DIRECTORY is not set."""
        with patch.dict("os.environ", {}, clear=True):
            with self.assertRaises(SystemExit) as ctx:
                migrate_db_module.main()
            self.assertEqual(ctx.exception.code, 1)

    @patch.object(migrate_db_module, "command")
    @patch.object(migrate_db_module, "Config")
    @patch.object(migrate_db_module, "os")
    def test_applies_pending_migrations(self, mock_os, mock_config, mock_command):
        """chdir to workspace then call alembic upgrade head."""
        mock_os.environ.get.return_value = "/workspace"
        mock_cfg = MagicMock()
        mock_config.return_value = mock_cfg

        migrate_db_module.main()

        mock_os.chdir.assert_called_once_with("/workspace")
        mock_config.assert_called_once_with("alembic.ini")
        mock_command.upgrade.assert_called_once_with(mock_cfg, "head")

    @patch.object(migrate_db_module, "command")
    @patch.object(migrate_db_module, "Config")
    @patch.object(migrate_db_module, "os")
    def test_upgrade_failure_propagates(self, mock_os, mock_config, mock_command):
        """Exception raised by alembic upgrade is not swallowed."""
        mock_os.environ.get.return_value = "/workspace"
        mock_command.upgrade.side_effect = Exception("migration failed")

        with self.assertRaises(Exception, msg="migration failed"):
            migrate_db_module.main()

    @patch.object(migrate_db_module, "command")
    @patch.object(migrate_db_module, "Config")
    @patch.object(migrate_db_module, "os")
    def test_chdir_to_workspace_before_reading_config(
        self, mock_os, mock_config, mock_command
    ):
        """os.chdir is called before Config() so alembic.ini is read from the workspace."""
        mock_os.environ.get.return_value = "/workspace"
        call_order = []
        mock_os.chdir.side_effect = lambda _: call_order.append("chdir")
        mock_config.side_effect = lambda _: call_order.append("config") or MagicMock()

        migrate_db_module.main()

        self.assertEqual(call_order, ["chdir", "config"])


if __name__ == "__main__":
    unittest.main()
