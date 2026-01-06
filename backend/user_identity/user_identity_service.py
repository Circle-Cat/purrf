from backend.entity.users_entity import UsersEntity
from sqlalchemy.ext.asyncio import AsyncSession


class UserIdentityService:
    """
    Service responsible for resolving internal user identities from external
    authentication identifiers.
    """

    def __init__(self, users_repository):
        self.users_repository = users_repository

    async def get_user_by_subject_identifier(
        self, session: AsyncSession, subject: str
    ) -> UsersEntity | None:
        """
        Resolve internal user entity from external subject identifier.

        Args:
            session (AsyncSession): Active database async session.
            subject (str): The `sub` claim from the JWT identifying the authenticated user.

        Returns:
            UsersEntity | None: The fetched user entity, or None if not found.
        """
        user = await self.users_repository.get_user_by_subject_identifier(
            session, subject
        )

        return user
