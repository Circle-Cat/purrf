from backend.entity.user_emails_entity import UserEmailsEntity
from sqlalchemy.ext.asyncio import AsyncSession


class UserEmailsRepository:
    """
    Repository for handling database operations related to UserEmailsEntity.
    """

    async def upsert_email(
        self, session: AsyncSession, entity: UserEmailsEntity
    ) -> UserEmailsEntity:
        """
        Inserts or updates a UserEmailsEntity in the database.

        Uses session.merge() — inserts if no PK is set, otherwise updates the
        matching row.

        Args:
            session (AsyncSession): The active async database session.
            entity (UserEmailsEntity): The email row to persist.

        Returns:
            UserEmailsEntity: The entity synchronized with the database.
        """
        merged_entity = await session.merge(entity)
        await session.flush()

        return merged_entity
