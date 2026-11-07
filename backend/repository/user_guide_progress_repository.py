from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from backend.common.onboarding_guide_enums import GuideProgressStatus
from backend.entity.user_guide_progress_entity import UserGuideProgressEntity


class UserGuideProgressRepository:
    """Database operations for UserGuideProgressEntity."""

    async def list_by_user(
        self, session: AsyncSession, user_id: int
    ) -> list[UserGuideProgressEntity]:
        """List every guide row one user has, ordered by guide key.

        Args:
            session (AsyncSession): The active async database session.
            user_id (int): The user whose rows to list.

        Returns:
            list[UserGuideProgressEntity]: The user's rows; guides the user has
            never seen have none.
        """
        result = await session.execute(
            select(UserGuideProgressEntity)
            .where(UserGuideProgressEntity.user_id == user_id)
            .order_by(UserGuideProgressEntity.guide_key)
        )
        return list(result.scalars().all())

    async def get_for_update(
        self, session: AsyncSession, user_id: int, guide_key: str
    ) -> UserGuideProgressEntity | None:
        """Fetch one user's row for one guide and lock it until the transaction ends.

        The lock keeps two overlapping snoozes from both reading the same
        count and writing the same next value.

        Args:
            session (AsyncSession): The active async database session.
            user_id (int): The user the row belongs to.
            guide_key (str): The guide the row is about.

        Returns:
            UserGuideProgressEntity | None: The row, or None if the user has
            never seen the guide.
        """
        result = await session.execute(
            select(UserGuideProgressEntity)
            .where(
                UserGuideProgressEntity.user_id == user_id,
                UserGuideProgressEntity.guide_key == guide_key,
            )
            .with_for_update()
        )
        return result.scalars().one_or_none()

    async def upsert(
        self,
        session: AsyncSession,
        user_id: int,
        guide_key: str,
        status: GuideProgressStatus,
        snooze_count: int,
    ) -> UserGuideProgressEntity:
        """Create or overwrite one user's row for one guide.

        One statement rather than a read and an insert, so two first writes
        that overlap end as one row instead of a primary key violation.
        ``created_at`` is left out of the update, so it keeps the time of the
        first write; ``updated_at`` moves on every write.

        Args:
            session (AsyncSession): The active async database session.
            user_id (int): The user the row belongs to.
            guide_key (str): The guide the row is about.
            status (GuideProgressStatus): The status to store.
            snooze_count (int): The snooze count to store.

        Returns:
            UserGuideProgressEntity: The stored row.
        """
        statement = (
            insert(UserGuideProgressEntity)
            .values(
                user_id=user_id,
                guide_key=guide_key,
                status=status,
                snooze_count=snooze_count,
            )
            .on_conflict_do_update(
                index_elements=[
                    UserGuideProgressEntity.user_id,
                    UserGuideProgressEntity.guide_key,
                ],
                set_={
                    "status": status,
                    "snooze_count": snooze_count,
                    "updated_at": func.now(),
                },
            )
            .returning(UserGuideProgressEntity)
        )
        result = await session.execute(
            statement, execution_options={"populate_existing": True}
        )
        return result.scalars().one()
