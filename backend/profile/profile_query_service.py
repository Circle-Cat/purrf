from sqlalchemy.ext.asyncio import AsyncSession
from backend.dto.profile_dto import ProfileDto


class ProfileQueryService:
    """
    Service to assemble a complete user profile, including optional training,
    work experience, and education information.

    This service fetches entities from repositories and maps them to DTOs
    suitable for API responses or further processing.
    """

    def __init__(
        self,
        users_repository,
        experience_repository,
        training_repository,
        profile_mapper,
    ):
        """
        Initialize ProfileQueryService with required repositories.

        Args:
            users_repository: Repository handling UsersEntity.
            experience_repository: Repository handling ExperienceEntity.
            training_repository: Repository handling TrainingEntity.
            profile_mapper: Mapper used to convert entities into ProfileDto.
        """
        self.users_repository = users_repository
        self.experience_repository = experience_repository
        self.training_repository = training_repository
        self.profile_mapper = profile_mapper

    async def get_profile(
        self,
        session: AsyncSession,
        user_sub: str,
        include_training: bool,
        include_work_history: bool,
        include_education: bool,
    ) -> ProfileDto | None:
        """
        Retrieve a user's profile by subject identifier.

        This method:
        1. Loads the user entity by `user_sub`.
        2. Returns None if the user does not exist.
        3. Conditionally loads related experience and training data
        based on the provided include flags.
        4. Maps the loaded entities into a ProfileDto.

        Args:
            session (AsyncSession): Active SQLAlchemy async session.
            user_sub (str): Subject identifier of the user (e.g. from Auth provider).
            include_training (bool): Whether to include training information.
            include_work_history (bool): Whether to include work history information.
            include_education (bool): Whether to include education information.

        Returns:
            ProfileDto | None:
                A ProfileDto containing only the requested fields,
                or None if the user does not exist.
        """

        users_entity = await self.users_repository.get_user_by_subject_identifier(
            session, user_sub
        )
        if not users_entity:
            return None

        user_id = users_entity.user_id
        experience_entity = None
        training_entities = None

        if include_work_history or include_education:
            experience_entity = (
                await self.experience_repository.get_experience_by_user_id(
                    session, user_id
                )
            )

        if include_training:
            training_entities = await self.training_repository.get_training_by_user_id(
                session, user_id
            )

        return self.profile_mapper.map_to_profile_dto(
            user=users_entity,
            experience=experience_entity,
            trainings=training_entities,
            include_work_history=include_work_history,
            include_education=include_education,
        )
