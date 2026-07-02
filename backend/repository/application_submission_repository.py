from backend.entity.application_submission_entity import ApplicationSubmissionEntity
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


class ApplicationSubmissionRepository:
    """Database operations for append-only application submission versions."""

    async def get_current(
        self, session: AsyncSession, application_id: int
    ) -> ApplicationSubmissionEntity | None:
        """Return the highest-version submission for an application, or None."""
        result = await session.execute(
            select(ApplicationSubmissionEntity)
            .where(ApplicationSubmissionEntity.application_id == application_id)
            .order_by(ApplicationSubmissionEntity.version.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def list_by_application(
        self, session: AsyncSession, application_id: int
    ) -> list[ApplicationSubmissionEntity]:
        """Return all submission versions for an application, ascending by version."""
        result = await session.execute(
            select(ApplicationSubmissionEntity)
            .where(ApplicationSubmissionEntity.application_id == application_id)
            .order_by(ApplicationSubmissionEntity.version.asc())
        )
        return list(result.scalars().all())

    async def create(
        self, session: AsyncSession, entity: ApplicationSubmissionEntity
    ) -> ApplicationSubmissionEntity:
        """Insert a submission version and flush so its submission_id is populated."""
        session.add(entity)
        await session.flush()
        return entity

    async def update(
        self, session: AsyncSession, entity: ApplicationSubmissionEntity
    ) -> ApplicationSubmissionEntity:
        """Persist mutations to a submission version."""
        merged = await session.merge(entity)
        await session.flush()
        return merged
