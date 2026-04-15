import os
import sys

from alembic.config import Config
from alembic import command
from backend.common.logger import get_logger

logger = get_logger()


def main():
    """
    Apply pending Alembic migrations to the database without dropping any data.

    Use this script when deploying schema changes to an existing database.
    For a fresh database setup, use tools/migrate_db/init_db.py instead.
    """
    workspace_dir = os.environ.get("BUILD_WORKSPACE_DIRECTORY")
    if not workspace_dir:
        logger.error(
            "BUILD_WORKSPACE_DIRECTORY not set. Run this via `bazel run`, not directly."
        )
        sys.exit(1)

    os.chdir(workspace_dir)

    logger.info("Running alembic upgrade head...")
    alembic_cfg = Config("alembic.ini")
    command.upgrade(alembic_cfg, "head")
    logger.info("Migration complete.")


if __name__ == "__main__":
    main()
