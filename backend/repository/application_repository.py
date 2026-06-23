from backend.entity.application_entity import ApplicationEntity
from backend.common.recruiting_enums import ApplicationStage
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession


class ApplicationRepository:
    """Database operations for ApplicationEntity."""

    async def create_application(self, session: AsyncSession, entity: ApplicationEntity) -> ApplicationEntity:
        """Insert a new application and flush so its id is populated."""
        session.add(entity)
        await session.flush()
        return entity

    async def get_by_id(self, session: AsyncSession, application_id: int) -> ApplicationEntity | None:
        """Return the application with the given id, or None."""
        if not application_id:
            return None
        result = await session.execute(
            select(ApplicationEntity).where(ApplicationEntity.application_id == application_id)
        )
        return result.scalar_one_or_none()

    async def list_active_by_job(self, session: AsyncSession, job_id: int) -> list[ApplicationEntity]:
        """Return non-terminal (board) applications for a job, newest first."""
        result = await session.execute(
            select(ApplicationEntity)
            .where(
                ApplicationEntity.job_id == job_id,
                ApplicationEntity.stage.notin_(
                    [ApplicationStage.HIRED, ApplicationStage.REJECTED, ApplicationStage.OFFER_DECLINED]
                ),
            )
            .order_by(desc(ApplicationEntity.created_datetime))
        )
        return list(result.scalars().all())

    async def get_latest_rejected(
        self, session: AsyncSession, user_id: int, job_id: int
    ) -> ApplicationEntity | None:
        """Return the most recent REJECTED application for (user, job), or None."""
        result = await session.execute(
            select(ApplicationEntity)
            .where(
                ApplicationEntity.user_id == user_id,
                ApplicationEntity.job_id == job_id,
                ApplicationEntity.stage == ApplicationStage.REJECTED,
            )
            .order_by(desc(ApplicationEntity.rejected_at))
        )
        return result.scalars().first()

    async def update_application(self, session: AsyncSession, entity: ApplicationEntity) -> ApplicationEntity:
        """Persist mutations to an attached/merged application entity."""
        merged = await session.merge(entity)
        await session.flush()
        return merged
