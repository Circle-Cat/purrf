import os
import sys

from alembic.config import Config
from alembic import command
from backend.common.logger import get_logger

logger = get_logger()


def main():
    """Generate an Alembic autogenerate migration script for pending model changes.

    Requires BUILD_WORKSPACE_DIRECTORY (set automatically by `bazel run`) so the
    script can write the generated file into the source tree rather than the
    Bazel sandbox.

    Usage:
        bazel run //tools/migrate_db:make_migration -- "<migration message>"
    """
    if len(sys.argv) < 2:
        logger.error(
            'Usage: bazel run //tools/migrate_db:make_migration -- "<migration message>"'
        )
        sys.exit(1)

    message = sys.argv[1]

    workspace_dir = os.environ.get("BUILD_WORKSPACE_DIRECTORY")
    if not workspace_dir:
        logger.error(
            "BUILD_WORKSPACE_DIRECTORY not set. Run this via `bazel run`, not directly."
        )
        sys.exit(1)

    os.chdir(workspace_dir)

    logger.info("Generating migration: %s", message)
    alembic_cfg = Config("alembic.ini")
    command.revision(alembic_cfg, message=message, autogenerate=True)
    logger.info("Migration file generated in alembic_setup/versions/")


if __name__ == "__main__":
    main()
