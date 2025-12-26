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

    async def get_all_by_ids(self, session: AsyncSession, user_ids: list[int]):
        """
        Retrieve multiple users entities by a list of user IDs.

        Args:
            session (AsyncSession): The active async database session.
            user_ids (list[int]): A list of user IDs to retrieve.

        Returns:
            list[UsersEntity]: A list of matching user entities.
                               Returns an empty list if no matches are found.
        """
        if not user_ids:
            return []

        result = await session.execute(
            select(UsersEntity).where(UsersEntity.user_id.in_(user_ids))
        )
        return list(result.scalars().all())

    async def get_user_by_subject_identifier(
        self, session: AsyncSession, sub: str
    ) -> UsersEntity | None:
        """
        Retrieve a users entity by its subject identifier.

        This method expects an externally managed AsyncSession, typically provided
        by the service layer within a transactional context.

        Args:
            session (AsyncSession): The active async database session.
            sub (string): The subject identifier of the user to retrieve.

        Returns:
            UsersEntity | None: The matching user entity if found; otherwise None.
        """
        result = await session.execute(
            select(UsersEntity).where(UsersEntity.subject_identifier == sub)
        )

        return result.scalars().one_or_none()

    async def get_user_by_primary_email(
        self, session: AsyncSession, primary_email: str
    ) -> UsersEntity | None:
        """
        Retrieve a users entity by its primary email.

        This method expects an externally managed AsyncSession, typically provided
        by the service layer within a transactional context.

        Args:
            session (AsyncSession): The active async database session.
            primary_email (string): The primary email of the user to retrieve.

        Returns:
            UsersEntity | None: The matching user entity if found; otherwise None.
        """
        result = await session.execute(
            select(UsersEntity).where(UsersEntity.primary_email == primary_email)
        )

        return result.scalars().one_or_none()

    async def upsert_users(
        self, session: AsyncSession, entity: UsersEntity
    ) -> UsersEntity:
        """
        Inserts or updates a UsersEntity object in the database.

        This method using session.merge() handles data persistence, it will
        updates the entity if the primary key exists, or inserts it otherwise

        Args:
            session (AsyncSession): The active async database session.
            entity: The UsersEntity object containing the user data.

        Returns:
            UsersEntity: The entity object synchronized with the database, reflecting
            the latest state, generated keys, and default values.
        """
        merged_entity = await session.merge(entity)
        await session.flush()

        return merged_entity
