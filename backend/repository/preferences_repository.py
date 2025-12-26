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

    async def upsert_preference(
        self, session: AsyncSession, entity: PreferenceEntity
    ) -> PreferenceEntity:
        """
        Inserts or updates a PreferenceEntity in the database.

        Args:
            session (AsyncSession): Active async database session.
            entity (PreferenceEntity): The entity containing preference data.

        Returns:
            PreferenceEntity: The merged entity instance synchronized with the session.
        """
        merged_entity = await session.merge(entity)
        await session.flush()

        return merged_entity
