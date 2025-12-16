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
        Initialize a Database instance.

        Args:
            echo (bool): If True, SQLAlchemy will output executed SQL statements.
        """
        self.database_url = DATABASE_URL
        if not self.database_url:
            raise ValueError("DATABASE_URL must be set")
        self._engine = create_async_engine(self.database_url, echo=echo)
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
