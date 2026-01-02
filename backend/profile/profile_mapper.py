from backend.dto.profile_dto import ProfileDto
from backend.dto.users_dto import UsersDto
from backend.dto.work_history_dto import WorkHistoryDto
from backend.dto.education_dto import EducationDto
from backend.dto.training_dto import TrainingDto
from backend.entity.users_entity import UsersEntity
from backend.entity.experience_entity import ExperienceEntity
from backend.entity.training_entity import TrainingEntity


class ProfileMapper:
    """
    Optimized mapper for Profile data.
    """

    def map_to_profile_dto(
        self,
        user: UsersEntity,
        experience: ExperienceEntity | None,
        trainings: list[TrainingEntity] | None,
        include_work_history: bool = True,
        include_education: bool = True,
    ) -> ProfileDto:
        """Assemble a complete ProfileDto with optional work history and education."""
        return ProfileDto(
            id=user.user_id,
            user=self._map_user(user),
            work_history=self._map_work_history(experience)
            if include_work_history
            else [],
            education=self._map_education(experience) if include_education else [],
            training=[self._map_training(t) for t in (trainings or [])],
        )

    def _map_user(self, entity: UsersEntity) -> UsersDto:
        """Map basic user information."""
        return UsersDto(
            id=entity.user_id,
            first_name=entity.first_name,
            last_name=entity.last_name,
            preferred_name=entity.preferred_name,
            timezone=entity.timezone,
            timezone_updated_at=entity.timezone_updated_at,
            communication_method=entity.communication_channel,
            primary_email=entity.primary_email,
            alternative_emails=entity.alternative_emails or [],
            linkedin_link=entity.linkedin_link,
            updated_timestamp=entity.updated_timestamp,
        )

    def _map_work_history(
        self, entity: ExperienceEntity | None
    ) -> list[WorkHistoryDto]:
        """Map work history records."""
        if not entity or not entity.work_history:
            return []

        return [
            WorkHistoryDto(
                id=item.get("id"),
                title=item.get("title"),
                company_or_organization=item.get("company_or_organization"),
                start_date=item.get("start_date"),
                end_date=item.get("end_date"),
                is_current_job=item.get("is_current_job", False),
            )
            for item in entity.work_history
        ]

    def _map_education(self, entity: ExperienceEntity | None) -> list[EducationDto]:
        """Map education records."""
        if not entity or not entity.education:
            return []

        return [
            EducationDto(
                id=item.get("id"),
                degree=item.get("degree"),
                school=item.get("school"),
                field_of_study=item.get("field_of_study"),
                start_date=item.get("start_date"),
                end_date=item.get("end_date"),
            )
            for item in entity.education
        ]

    def _map_training(self, entity: TrainingEntity) -> TrainingDto:
        """Map a training record."""
        return TrainingDto(
            id=entity.training_id,
            category=entity.category,
            status=entity.status,
            link=entity.link,
            deadline=entity.deadline,
            completed_timestamp=entity.completed_timestamp,
        )
