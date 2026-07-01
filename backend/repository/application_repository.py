from backend.entity.application_entity import ApplicationEntity
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


class ApplicationRepository:
    """Database operations for ApplicationEntity (one row per job+user)."""

    async def get_by_job_and_user(
        self, session: AsyncSession, job_id: int, user_id: int
    ) -> ApplicationEntity | None:
        """Return the application for this job+user, or None."""
        result = await session.execute(
            select(ApplicationEntity).where(
                ApplicationEntity.job_id == job_id,
                ApplicationEntity.user_id == user_id,
            )
        )
        return result.scalar_one_or_none()

    async def create(
        self, session: AsyncSession, entity: ApplicationEntity
    ) -> ApplicationEntity:
        """Insert an application and flush so its application_id is populated."""
        session.add(entity)
        await session.flush()
        return entity

    async def update(
        self, session: AsyncSession, entity: ApplicationEntity
    ) -> ApplicationEntity:
        """Persist mutations to an application entity."""
        merged = await session.merge(entity)
        await session.flush()
        return merged
