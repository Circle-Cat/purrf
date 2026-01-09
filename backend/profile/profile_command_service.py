from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timezone, timedelta
from uuid import uuid4
from backend.entity.users_entity import UsersEntity
from backend.dto.profile_create_dto import (
    WorkHistoryRequestDto,
    EducationRequestDto,
    ProfileCreateDto,
)
from backend.entity.experience_entity import ExperienceEntity


class ProfileCommandService:
    """
    Service responsible for handling user-related commands in the profile domain.

    This includes operations such as updating user records in the database.
    It interacts with the UsersRepository to persist UsersEntity instances.
    """

    def __init__(self, users_repository, logger, experience_repository):
        """
        Initialize the ProfileCommandService with a UsersRepository instance.

        Args:
            users_repository: Repository responsible for CRUD operations on UsersEntity.
            experience_repository: Repository responsible for CRUD operations on ExperienceEntity.
            logger: The logger instance for logging messages.
        """
        self.users_repository = users_repository
        self.logger = logger
        self.experience_repository = experience_repository

    async def update_users(
        self,
        session: AsyncSession,
        latest_profile: ProfileCreateDto,
        users: UsersEntity,
    ):
        """
        Update an existing user entity with data from the latest profile.

        Behavior:
        The user's timezone can only be changed once every 30 days. If a
        timezone change is requested before the cooldown period has elapsed,
        a ValueError is raised.

        All other user fields are updated unconditionally based on the latest
        profile data.

        Args:
            session (AsyncSession): The active database session.
            latest_profile (ProfileCreateDto): The incoming profile data used
                to update the user.
            users (UsersEntity): The existing user entity to be updated.

        Returns:
            UsersEntity: The updated user entity persisted in the database.

        Raises:
            ValueError: If the timezone is updated within 30 days of the last
                timezone change.
            Exception: If the database operation fails during the update.
        """
        latest_users_data = latest_profile.user
        if not latest_users_data:
            return

        # Handle timezone update with 30-day restriction
        if latest_users_data.timezone != users.timezone:
            last_update_time = users.timezone_updated_at
            now = datetime.now(timezone.utc)
            if now < last_update_time + timedelta(days=30):
                raise ValueError("Timezone can only be updated once every 30 days")

            users.timezone = latest_users_data.timezone
            users.timezone_updated_at = now

        # Update other fields (no restriction)
        users.first_name = latest_users_data.first_name
        users.last_name = latest_users_data.last_name
        users.communication_method = latest_users_data.communication_method
        users.preferred_name = latest_users_data.preferred_name
        users.alternative_emails = latest_users_data.alternative_emails
        users.linkedin_link = latest_users_data.linkedin_link
        users.updated_timestamp = datetime.now(timezone.utc)

        try:
            updated_user = await self.users_repository.upsert_users(session, users)
            self.logger.info(
                "[ProfileCommandService] user updated successfully. UserID: %s",
                updated_user.user_id,
            )
            return updated_user
        except Exception as e:
            self.logger.error(
                "[ProfileCommandService] failed to update user for user ID %s. Error: %s",
                users.user_id,
                str(e),
            )
            raise

    def _ensure_ids_and_detect_new(
        self, data: list[EducationRequestDto | WorkHistoryRequestDto]
    ) -> bool:
        """
        Ensures all items have an ID.
        Assigns IDs to new items in-place.

        Returns True if any new item was detected.
        """
        has_new_items = False

        for item in data:
            if not item.id:
                item.id = str(uuid4())
                has_new_items = True

        return has_new_items

    async def _upsert_experience_data(
        self,
        session,
        user_id: int,
        field_name: str,
        data: list[EducationRequestDto | WorkHistoryRequestDto],
    ):
        """
        Create or update a user's experience-related data (education or work history).

        Behavior:
        - Ensures each incoming item has a stable `id`. New items without an `id`
          will be assigned one in-place.
        - Converts request DTOs into snake_case dictionaries suitable for database storage.
        - If an existing ExperienceEntity is found and no new items are detected:
            - Compares the incoming data with the current stored data
              while ignoring order.
            - If the content is identical, the database update is skipped to
              avoid unnecessary writes.
        - If no ExperienceEntity exists for the user, a new one is created.
        - Otherwise, the specified experience field is fully replaced with the
          incoming data (full overwrite semantics).

        Args:
            session: Active SQLAlchemy async session.
            user_id (int): Internal user ID.
            field_name (str): Name of the experience field to update.
                Expected values are "education" or "work_history".
            data (list[EducationRequestDto | WorkHistoryRequestDto]):
                Incoming experience data from the API request.

        Returns:
            ExperienceEntity: The created or updated experience entity.
        """
        experience_entity = await self.experience_repository.get_experience_by_user_id(
            session, user_id
        )

        has_new_items = self._ensure_ids_and_detect_new(data)

        new_data_dicts = [item.to_db_dict() for item in data]

        if experience_entity and data and not has_new_items:
            current_data_dicts = getattr(experience_entity, field_name) or []

            if len(current_data_dicts) == len(new_data_dicts):
                sorted_current = sorted(current_data_dicts, key=lambda x: x.get("id"))
                sorted_new = sorted(new_data_dicts, key=lambda x: x.get("id"))

                if sorted_current == sorted_new:
                    self.logger.info(
                        "[ProfileCommandService] no content change for user_id=%s in %s (order ignored). Skipping.",
                        user_id,
                        field_name,
                    )
                    return experience_entity

        if not experience_entity:
            experience_entity = ExperienceEntity(user_id=user_id)

        setattr(experience_entity, field_name, new_data_dicts)
        experience_entity.updated_timestamp = datetime.now(timezone.utc)

        await self.experience_repository.upsert_experience(session, experience_entity)
        self.logger.info(
            "[ProfileCommandService] updated %s for user_id=%s.", field_name, user_id
        )
        return experience_entity

    async def update_work_history(
        self,
        session,
        latest_profile: ProfileCreateDto,
        user_id: int,
    ):
        """
        Updates user's work history.
        """
        return await self._upsert_experience_data(
            session,
            user_id,
            "work_history",
            latest_profile.work_history,
        )

    async def update_education(
        self,
        session,
        latest_profile: ProfileCreateDto,
        user_id: int,
    ):
        """
        Updates user's education history.
        """
        return await self._upsert_experience_data(
            session,
            user_id,
            "education",
            latest_profile.education,
        )
