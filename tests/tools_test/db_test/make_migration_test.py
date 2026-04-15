import sys
import unittest
from unittest.mock import patch, MagicMock

sys.modules["backend"] = MagicMock()
sys.modules["backend.common"] = MagicMock()
sys.modules["backend.common.logger"] = MagicMock()

import tools.migrate_db.make_migration as make_migration_module  # noqa: E402


class TestMakeMigration(unittest.TestCase):
    """Tests for make_migration.main() argument validation and alembic revision call."""

    def test_exits_when_no_message_arg(self):
        """Exits with code 1 when no migration message is provided."""
        with patch("sys.argv", ["make_migration"]):
            with self.assertRaises(SystemExit) as ctx:
                make_migration_module.main()
            self.assertEqual(ctx.exception.code, 1)

    def test_exits_when_no_workspace_dir(self):
        """Exits with code 1 when BUILD_WORKSPACE_DIRECTORY is not set."""
        with patch("sys.argv", ["make_migration", "add column"]):
            with patch.dict("os.environ", {}, clear=True):
                with self.assertRaises(SystemExit) as ctx:
                    make_migration_module.main()
                self.assertEqual(ctx.exception.code, 1)

    @patch.object(make_migration_module, "command")
    @patch.object(make_migration_module, "Config")
    @patch.object(make_migration_module, "os")
    def test_generates_migration_with_message(self, mock_os, mock_config, mock_command):
        """chdir to workspace, then call alembic revision --autogenerate with the message."""
        mock_os.environ.get.return_value = "/workspace"
        mock_cfg = MagicMock()
        mock_config.return_value = mock_cfg

        with patch("sys.argv", ["make_migration", "add user table"]):
            make_migration_module.main()

        mock_os.chdir.assert_called_once_with("/workspace")
        mock_config.assert_called_once_with("alembic.ini")
        mock_command.revision.assert_called_once_with(
            mock_cfg, message="add user table", autogenerate=True
        )

    @patch.object(make_migration_module, "command")
    @patch.object(make_migration_module, "Config")
    @patch.object(make_migration_module, "os")
    def test_uses_first_arg_as_message(self, mock_os, mock_config, mock_command):
        """Only the first positional argument is used as the migration message."""
        mock_os.environ.get.return_value = "/workspace"
        mock_cfg = MagicMock()
        mock_config.return_value = mock_cfg

        with patch("sys.argv", ["make_migration", "expected message", "extra arg"]):
            make_migration_module.main()

        mock_command.revision.assert_called_once_with(
            mock_cfg, message="expected message", autogenerate=True
        )


if __name__ == "__main__":
    unittest.main()
