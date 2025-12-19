from backend.entity.experience_entity import ExperienceEntity
from sqlalchemy import select
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
