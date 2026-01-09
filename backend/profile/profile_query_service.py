from sqlalchemy.ext.asyncio import AsyncSession
from backend.dto.profile_dto import ProfileDto
from backend.dto.user_context_dto import UserContextDto


class ProfileQueryService:
    """
    Service to assemble a complete user profile, including optional training,
    work experience, and education information.

    This service fetches entities from repositories and maps them to DTOs
    suitable for API responses or further processing.
    """

    def __init__(
        self,
        user_identity_service,
        experience_repository,
        training_repository,
        profile_mapper,
    ):
        """
        Initialize ProfileQueryService with required repositories.

        Args:
            user_identity_service: Service responsible for retrieving user identity information.
            experience_repository: Repository handling ExperienceEntity.
            training_repository: Repository handling TrainingEntity.
            profile_mapper: Mapper used to convert entities into ProfileDto.
        """
        self.user_identity_service = user_identity_service
        self.experience_repository = experience_repository
        self.training_repository = training_repository
        self.profile_mapper = profile_mapper

    async def get_profile(
        self,
        session: AsyncSession,
        user_info: UserContextDto,
        include_training: bool,
        include_work_history: bool,
        include_education: bool,
    ) -> tuple[ProfileDto, bool]:
        """
        Retrieve a user's profile based on the provided user context.

        This method:
        1. Loads the user entity by `user_info`.
        2. Conditionally loads related experience and training data
        based on the provided include flags.
        3. Maps the loaded entities into a ProfileDto.

        Args:
            session (AsyncSession): Active SQLAlchemy async session.
            user_info (UserContextDto): DTO containing user info (sub, email, roles).
            include_training (bool): Whether to include training information.
            include_work_history (bool): Whether to include work history information.
            include_education (bool): Whether to include education information.

        Returns:
            tuple[ProfileDto, bool]:
                ProfileDto: DTO containing only the requested fields.
                should_commit: True if the transaction needs to be committed.
        """

        (
            users_entity,
            should_commit,
        ) = await self.user_identity_service.get_user(
            session=session, user_info=user_info
        )

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
        ), should_commit
