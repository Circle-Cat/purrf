import contextlib
from backend.common.environment_constants import DATABASE_URL
from typing import AsyncIterator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)


class Database:
    def __init__(self, echo=False):
        """
        Initialize a Database instance with an async SQLAlchemy engine and session factory.

        Creates an async engine configured for Neon's connection pooler:
        - pool_recycle=25: Recycle connections before Neon pooler's 30s idle timeout.
        - pool_pre_ping=True: Validate connections before use to avoid stale connection errors.

        Args:
            echo (bool): If True, SQLAlchemy will output executed SQL statements.

        Raises:
            ValueError: If the DATABASE_URL environment variable is not set.
        """
        self.database_url = DATABASE_URL
        if not self.database_url:
            raise ValueError("DATABASE_URL must be set")
        self._engine = create_async_engine(
            self.database_url,
            echo=echo,
            pool_recycle=25,
            pool_pre_ping=True,
        )
        self._session_factory = async_sessionmaker(
            bind=self._engine,
            autoflush=False,
            expire_on_commit=False,
        )

    def get_engine(self):
        """
        Expose the underlying SQLAlchemy async engine.

        This is usually needed only for external tools such as Alembic.
        """
        return self._engine

    async def close(self):
        """
        Dispose the database engine.

        Typically called on application shutdown to cleanly close connection pools.
        """
        await self._engine.dispose()

    @contextlib.asynccontextmanager
    async def session(self) -> AsyncIterator[AsyncSession]:
        """
        Provide a transactional session context manager.

        This handles session lifecycle automatically:
        - create session
        - yield it to the caller
        - rollback on error
        - close session at the end

        Note:
            Whether to automatically commit is up to your project pattern.
            If the service layer performs explicit `session.commit()`,
            do NOT commit here. For simple CRUD utilities, you could
            add `await session.commit()` before exiting.
        """
        session: AsyncSession = self._session_factory()
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
