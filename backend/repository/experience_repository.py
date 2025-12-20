from backend.entity.experience_entity import ExperienceEntity
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession


class ExperienceRepository:
    """
    Repository for handling database operations related to ExperienceEntity.
    """

    async def get_experience_by_user_id(
        self, session: AsyncSession, user_id: int
    ) -> ExperienceEntity | None:
        """
        Retrieve the ExperienceEntity for a given user ID (1:1 relationship).
        """
        if not user_id:
            return None

        result = await session.execute(
            select(ExperienceEntity).where(ExperienceEntity.user_id == user_id)
        )

        return result.scalars().one_or_none()

    async def upsert_experience(
        self, session: AsyncSession, entity: ExperienceEntity
    ) -> ExperienceEntity:
        """
        Inserts or updates an ExperienceEntity in the database.

        Uses session.merge() to update the record if a matching primary key exists,
        or inserts a new one otherwise.

        Args:
            session (AsyncSession): The active async database session.
            entity (ExperienceEntity): The entity containing work history data.

        Returns:
            ExperienceEntity: The merged entity instance synchronized with the session.
        """
        merged_entity = await session.merge(entity)
        await session.flush()

        return merged_entity

    async def update_work_history(
        self,
        session: AsyncSession,
        user_id: int,
        new_work_history: list[dict],
    ) -> ExperienceEntity | None:
        """
        Update the work experience data for a given user ID (1:1 relationship)
        and return the updated experience entity.
        """
        result = await session.execute(
            update(ExperienceEntity)
            .where(ExperienceEntity.user_id == user_id)
            .values(work_history=new_work_history)
            .returning(ExperienceEntity)
        )

        return result.scalars().one_or_none()
