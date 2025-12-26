from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from backend.entity.preference_entity import PreferenceEntity


class PreferencesRepository:
    """Repository for handling database operations related to PreferenceEntity."""

    async def get_preferences_by_user_id(
        self, session: AsyncSession, user_id: int
    ) -> PreferenceEntity | None:
        """Retrieve the PreferenceEntity for a given user ID (1:1 relationship)."""
        if not user_id:
            return None

        result = await session.execute(
            select(PreferenceEntity).where(PreferenceEntity.user_id == user_id)
        )

        return result.scalars().one_or_none()
