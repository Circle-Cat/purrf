import sys
import unittest
from unittest.mock import patch, MagicMock

sys.modules["backend"] = MagicMock()
sys.modules["backend.common"] = MagicMock()
sys.modules["backend.common.logger"] = MagicMock()

import tools.migrate_db.migrate_db as migrate_db_module  # noqa: E402


class TestResolveAlembicIni(unittest.TestCase):
    """Tests for _resolve_alembic_ini() across the two supported layouts."""

    def test_chdirs_to_workspace_when_run_under_bazel(self):
        """With BUILD_WORKSPACE_DIRECTORY set, chdir there and use the relative ini."""
        with patch.dict(
            "os.environ", {"BUILD_WORKSPACE_DIRECTORY": "/workspace"}, clear=True
        ):
            with patch("os.chdir") as mock_chdir:
                result = migrate_db_module._resolve_alembic_ini()

        mock_chdir.assert_called_once_with("/workspace")
        self.assertEqual(result, "alembic.ini")

    def test_uses_bundled_ini_when_no_workspace(self):
        """Without a workspace, resolve alembic.ini from the runfiles and do not chdir."""
        with patch.dict("os.environ", {}, clear=True):
            with patch("os.chdir") as mock_chdir:
                with patch.object(
                    migrate_db_module.Path, "is_file", return_value=True
                ):
                    result = migrate_db_module._resolve_alembic_ini()

        mock_chdir.assert_not_called()
        self.assertTrue(result.endswith("/alembic.ini"))
        self.assertNotEqual(result, "alembic.ini")

    def test_exits_when_bundled_ini_missing(self):
        """Exit 1 rather than let alembic fail with a confusing error later."""
        with patch.dict("os.environ", {}, clear=True):
            with patch.object(
                migrate_db_module.Path, "is_file", return_value=False
            ):
                with self.assertRaises(SystemExit) as ctx:
                    migrate_db_module._resolve_alembic_ini()

        self.assertEqual(ctx.exception.code, 1)


class TestMigrateDb(unittest.TestCase):
    """Tests for migrate_db.main() alembic upgrade call."""

    @patch.object(migrate_db_module, "command")
    @patch.object(migrate_db_module, "Config")
    @patch.object(migrate_db_module, "_resolve_alembic_ini")
    def test_applies_pending_migrations(self, mock_resolve, mock_config, mock_command):
        """The resolved ini path is handed to Config, then upgraded to head."""
        mock_resolve.return_value = "/runfiles/_main/alembic.ini"
        mock_cfg = MagicMock()
        mock_config.return_value = mock_cfg

        migrate_db_module.main()

        mock_config.assert_called_once_with("/runfiles/_main/alembic.ini")
        mock_command.upgrade.assert_called_once_with(mock_cfg, "head")

    @patch.object(migrate_db_module, "command")
    @patch.object(migrate_db_module, "Config")
    @patch.object(migrate_db_module, "_resolve_alembic_ini")
    def test_resolves_config_before_upgrading(
        self, mock_resolve, mock_config, mock_command
    ):
        """Resolution happens first; upgrade never runs against an unresolved config."""
        call_order = []
        mock_resolve.side_effect = lambda: call_order.append("resolve") or "alembic.ini"
        mock_command.upgrade.side_effect = lambda *_: call_order.append("upgrade")

        migrate_db_module.main()

        self.assertEqual(call_order, ["resolve", "upgrade"])

    @patch.object(migrate_db_module, "command")
    @patch.object(migrate_db_module, "Config")
    @patch.object(migrate_db_module, "_resolve_alembic_ini")
    def test_upgrade_failure_propagates(self, mock_resolve, mock_config, mock_command):
        """A failed migration must surface as a non-zero exit, not be swallowed."""
        mock_resolve.return_value = "alembic.ini"
        mock_command.upgrade.side_effect = Exception("migration failed")

        with self.assertRaises(Exception, msg="migration failed"):
            migrate_db_module.main()


if __name__ == "__main__":
    unittest.main()
