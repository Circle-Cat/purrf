from backend.common.database import Database
from backend.common.base import Base
from alembic.config import Config
from alembic import command
import os
from backend.common.environment_constants import DATABASE_URL
import asyncio
import pkgutil
import importlib
import backend.entity
from sqlalchemy import text
from backend.common.logger import get_logger

logger = get_logger()


def load_all_entities():
    """
    Automatically scan and import all modules under backend.entity.

    Importing these modules ensures that all SQLAlchemy model classes
    and their associated Table objects are registered into Base.metadata.

    This allows SQLAlchemy to correctly create all tables when
    Base.metadata.create_all() is executed.
    """
    package = backend.entity
    prefix = package.__name__ + "."  # e.g. "backend.entity."

    # Iterate through all modules inside backend.entity package
    for _, name, _ in pkgutil.iter_modules(package.__path__, prefix):
        logger.info(f"Auto importing model: {name}")
        importlib.import_module(name)


# 1. Encapsulate async DB logic inside an async function
async def reset_database():
    """
    Reset the PostgreSQL database by:
    1. Importing all SQLAlchemy entity modules.
    2. Dropping and recreating the public schema.
    3. Recreating all tables defined in Base.metadata.

    Notes:
    - The engine is created using our custom Database wrapper.
    - We explicitly drop and recreate schema instead of drop_all()
      to ensure full cleanup (including leftover objects).
    """
    load_all_entities()

    db = Database(os.getenv(DATABASE_URL), echo=False)
    engine = db.get_engine()

    async with engine.begin() as conn:
        # Drop and recreate the public schema
        logger.info("Dropping and recreating public schema...")
        await conn.execute(text("DROP SCHEMA public CASCADE;"))
        await conn.execute(text("CREATE SCHEMA public;"))

        # Create all SQLAlchemy tables
        logger.info("Creating all tables from Base.metadata...")
        await conn.run_sync(Base.metadata.create_all)

    # Explicitly dispose the engine to release connections
    await engine.dispose()
    logger.info("Database reset complete.")


# 2. Main entrypoint remains synchronous so the event loop fully closes
def main():
    """
    Main entrypoint for resetting the database and stamping Alembic.

    Steps:
    1. Execute async database reset logic via asyncio.run(),
       which creates and closes a dedicated event loop.
    2. Run Alembic stamp after the loop is closed
       (important because Alembic is synchronous).
    """
    logger.info("Resetting database tables...")
    asyncio.run(reset_database())

    logger.info("Stamping alembic head...")
    alembic_cfg = Config("alembic.ini")
    command.stamp(alembic_cfg, "head")
    logger.info("Alembic head stamped successfully.")


if __name__ == "__main__":
    main()
