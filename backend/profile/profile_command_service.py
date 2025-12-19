from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timezone

from backend.entity.users_entity import UsersEntity
from backend.common.mentorship_enums import UserTimezone, CommunicationMethod
from backend.dto.user_context_dto import UserContextDto


class ProfileCommandService:
    """
    Service responsible for handling user-related commands in the profile domain.

    This includes operations such as creating or updating user records in the database.
    It interacts with the UsersRepository to persist UsersEntity instances.
    """

    def __init__(self, users_repository, logger):
        """
        Initialize the ProfileCommandService with a UsersRepository instance.

        Args:
            users_repository: Repository responsible for CRUD operations on UsersEntity.
            logger: The logger instance for logging messages.
        """
        self.users_repository = users_repository
        self.logger = logger

    async def create_user(
        self, session: AsyncSession, user_info: UserContextDto
    ) -> UsersEntity:
        """
        Create a new UsersEntity in the database from UserContextDto.

        Args:
            session (AsyncSession): Active database session.
            user_info (UserContextDto): DTO containing user info (sub, email, roles).

        Returns:
            UsersEntity: The newly created user entity.
        """
        primary_email = user_info.primary_email
        sub = user_info.sub

        self.logger.info(
            "[ProfileCommandService] attempting to create/sync user. Email: %s, Sub: %s",
            primary_email,
            sub,
        )
        updated_user = await self._sync_user_subject_identifier(
            session=session, primary_email=primary_email, sub=sub
        )

        if updated_user:
            self.logger.info(
                "[ProfileCommandService] user synced successfully via primary email. UserID: %s",
                updated_user.user_id,
            )
            return updated_user

        self.logger.info(
            "[ProfileCommandService] no existing user found to sync. Creating a brand new record."
        )

        new_user = UsersEntity(
            subject_identifier=sub,
            primary_email=primary_email,
            first_name="",
            last_name="",
            preferred_name=None,
            timezone=UserTimezone.AMERICA_LOS_ANGELES,
            timezone_updated_at=datetime(1970, 1, 1, tzinfo=timezone.utc),
            communication_channel=CommunicationMethod.EMAIL,
            alternative_emails=[],
            linkedin_link=None,
            has_mentorship_mentor_experience=None,
            is_active=True,
            updated_timestamp=datetime.now(timezone.utc),
        )

        try:
            created_user = await self.users_repository.upsert_users(session, new_user)
            self.logger.info(
                "[ProfileCommandService] new user created successfully. UserID: %s",
                created_user.user_id,
            )
            return created_user
        except Exception as e:
            self.logger.error(
                "[ProfileCommandService] failed to create new user for sub %s. Error: %s",
                sub,
                str(e),
            )
            raise

    async def _sync_user_subject_identifier(
        self, session: AsyncSession, primary_email: str, sub: str
    ) -> UsersEntity | None:
        """
        Temporary method to link a historical user record with a subject_identifier (sub).
        Used to backfill Auth provider subject IDs for pre-allocated users.

        Args:
            session (AsyncSession): Active database session.
            primary_email (str): User primary email to locate the historical record.
            sub (str): The subject identifier from the Auth provider.

        Returns:
            UsersEntity | None: The updated user entity, or None if not found.
        """
        self.logger.debug(
            "[ProfileCommandService] checking for historical record with email: %s",
            primary_email,
        )
        existing_user = await self.users_repository.get_user_by_primary_email(
            session, primary_email
        )

        if not existing_user:
            return None

        self.logger.info(
            "[ProfileCommandService] historical record found for %s. Linking to sub and updating...",
            primary_email,
        )

        if existing_user.subject_identifier == sub:
            self.logger.warning(
                "[ProfileCommandService] user with email %s already linked to sub %s, skipping update",
                primary_email,
                sub,
            )
            return existing_user

        existing_user.subject_identifier = sub
        existing_user.updated_timestamp = datetime.now(timezone.utc)

        try:
            updated_user = await self.users_repository.upsert_users(
                session, existing_user
            )
            return updated_user
        except Exception as e:
            self.logger.error(
                "[ProfileCommandService] failed to sync historical user ID %s: %s",
                existing_user.user_id,
                str(e),
            )
            return None
