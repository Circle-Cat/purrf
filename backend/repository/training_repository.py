from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from backend.entity.training_entity import TrainingEntity
from backend.common.mentorship_enums import TrainingCategory


class TrainingRepository:
    async def get_training_by_user_id(
        self, session: AsyncSession, user_id: int
    ) -> list[TrainingEntity]:
        """
        Fetch all training records for a given user_id.
        """
        result = await session.execute(
            select(TrainingEntity).where(TrainingEntity.user_id == user_id)
        )
        trainings = result.scalars().all()
        return trainings

    async def get_training_by_user_id_and_category(
        self, session: AsyncSession, user_id: int, category: TrainingCategory
    ) -> TrainingEntity | None:
        """
        Fetch a training record for a given user_id and category.
        """
        result = await session.execute(
            select(TrainingEntity).where(
                TrainingEntity.user_id == user_id,
                TrainingEntity.category == category,
            )
        )
        return result.scalars().one_or_none()

    async def get_training_by_user_ids_and_categories(
        self,
        session: AsyncSession,
        user_ids: list[int],
        categories: list[TrainingCategory],
    ) -> list[TrainingEntity]:
        """
        Batch-fetch training records for a list of user IDs and categories.

        Args:
            session (AsyncSession): The active async database session.
            user_ids (list[int]): A list of user IDs to retrieve training records for.
            categories (list[TrainingCategory]): Training categories to filter by.

        Returns:
            list[TrainingEntity]: Matching training records. Returns an empty list if
            user_ids is empty or no records match.
        """
        if not user_ids:
            return []
        result = await session.execute(
            select(TrainingEntity).where(
                TrainingEntity.user_id.in_(user_ids),
                TrainingEntity.category.in_(categories),
            )
        )
        return result.scalars().all()

    async def upsert_training(
        self, session: AsyncSession, entity: TrainingEntity
    ) -> TrainingEntity:
        """
        Inserts or updates a TrainingEntity object in the database.
        """
        merged_entity = await session.merge(entity)
        await session.flush()
        return merged_entity
