import os
import sys
from pathlib import Path

from alembic.config import Config
from alembic import command
from backend.common.logger import get_logger

logger = get_logger()


def _resolve_alembic_ini() -> str:
    """Locate the alembic.ini to run against.

    Two call sites with two different layouts:

    - `bazel run //tools/migrate_db` sets BUILD_WORKSPACE_DIRECTORY. Chdir there
      and read the ini from the source tree, so a migration that was just
      authored is picked up without rebuilding.
    - The migration container has no source tree. alembic.ini and alembic_setup/
      ride along in the runfiles through the //:alembic_files data dep, at the
      workspace root two directories above this file. alembic.ini resolves
      script_location as %(here)s/alembic_setup, which is relative to the ini
      itself, so no chdir is needed.
    """
    workspace_dir = os.environ.get("BUILD_WORKSPACE_DIRECTORY")
    if workspace_dir:
        os.chdir(workspace_dir)
        return "alembic.ini"

    bundled = Path(__file__).resolve().parents[2] / "alembic.ini"
    if not bundled.is_file():
        logger.error("alembic.ini not found at %s", bundled)
        sys.exit(1)
    return str(bundled)


def main():
    """
    Apply pending Alembic migrations to the database without dropping any data.

    Use this script when deploying schema changes to an existing database.
    For a fresh database setup, use tools/init_db.py instead.
    """
    alembic_ini = _resolve_alembic_ini()

    logger.info("Running alembic upgrade head...")
    alembic_cfg = Config(alembic_ini)
    command.upgrade(alembic_cfg, "head")
    logger.info("Migration complete.")


if __name__ == "__main__":
    main()
