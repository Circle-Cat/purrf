from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from backend.entity.training_entity import TrainingEntity


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
