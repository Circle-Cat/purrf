from backend.entity.application_entity import ApplicationEntity
from backend.entity.users_entity import UsersEntity
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


class ApplicationRepository:
    """Database operations for ApplicationEntity (one row per job+user)."""

    async def list_by_job(
        self, session: AsyncSession, job_id: int
    ) -> list[tuple[ApplicationEntity, UsersEntity]]:
        """Return every application for a job, joined with its applicant.

        Args:
            session (AsyncSession): The active DB session.
            job_id (int): The job whose applications to list.

        Returns:
            list[tuple[ApplicationEntity, UsersEntity]]: (application, user)
                pairs ordered by application_id (stable board card order).
        """
        result = await session.execute(
            select(ApplicationEntity, UsersEntity)
            .join(UsersEntity, ApplicationEntity.user_id == UsersEntity.user_id)
            .where(ApplicationEntity.job_id == job_id)
            .order_by(ApplicationEntity.application_id)
        )
        return [tuple(row) for row in result.all()]

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

    async def get_by_id(
        self,
        session: AsyncSession,
        application_id: int,
        *,
        for_update: bool = False,
    ) -> ApplicationEntity | None:
        """Return the application with this application_id, or None.

        When ``for_update`` is True the row is selected ``FOR UPDATE`` so a
        concurrent stage/sub-status decision on the same application blocks
        until this transaction commits (mirrors
        ``JobReviewRepository.get``'s row lock).
        """
        stmt = select(ApplicationEntity).where(
            ApplicationEntity.application_id == application_id,
        )
        if for_update:
            stmt = stmt.with_for_update()
        result = await session.execute(stmt)
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
