from backend.entity.users_entity import UsersEntity
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


class UsersRepository:
    """
    Repository for handling database operations related to UsersEntity.
    """

    async def get_user_by_user_id(
        self, session: AsyncSession, user_id: int
    ) -> UsersEntity | None:
        """
        Retrieve a users entity by its user ID.

        This method expects an externally managed AsyncSession, typically provided
        by the service layer within a transactional context.

        Args:
            session (AsyncSession): The active async database session.
            user_id (int): The ID of the user to retrieve.

        Returns:
            UsersEntity | None: The matching user entity if found; otherwise None.
        """
        result = await session.execute(
            select(UsersEntity).where(UsersEntity.user_id == user_id)
        )

        return result.scalars().one_or_none()
