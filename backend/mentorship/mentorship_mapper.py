from backend.dto.rounds_dto import RoundsDto, TimelineDto
from backend.dto.partner_dto import PartnerDto
from backend.dto.preference_dto import SpecificIndustryDto, SkillsetsDto
from backend.dto.registration_dto import GlobalPreferencesDto, RoundPreferencesDto
from backend.entity.preference_entity import PreferenceEntity
from backend.entity.mentorship_round_participants_entity import (
    MentorshipRoundParticipantsEntity,
)
from backend.entity.users_entity import UsersEntity
from backend.entity.mentorship_round_entity import MentorshipRoundEntity


class MentorshipMapper:
    """
    Mapper for converting mentorship-related database entities to DTOs.
    """

    def map_to_rounds_dto(self, rounds: list[MentorshipRoundEntity]) -> list[RoundsDto]:
        """Maps a list of MentorshipRoundEntity objects to a list of RoundsDto objects."""
        return [
            RoundsDto(
                id=r.round_id,
                name=r.name,
                mentee_average_score=r.mentee_average_score,
                mentor_average_score=r.mentor_average_score,
                expectations=r.expectations,
                required_meetings=r.required_meetings,
                timeline=self._map_timeline(r.description) if r.description else None,
            )
            for r in rounds
        ]

    def _map_timeline(self, d: dict) -> TimelineDto:
        """
        Maps a dictionary containing timeline data to a TimelineDto.

        Args:
            d (dict): A dictionary containing timeline-related datetime fields.

        Returns:
            TimelineDto: A TimelineDto populated with the corresponding timeline values.
        """
        return TimelineDto(
            promotion_start_at=d.get("promotion_start_at"),
            application_deadline_at=d.get("application_deadline_at"),
            review_start_at=d.get("review_start_at"),
            acceptance_notification_at=d.get("acceptance_notification_at"),
            matching_completed_at=d.get("matching_completed_at"),
            match_notification_at=d.get("match_notification_at"),
            first_meeting_deadline_at=d.get("first_meeting_deadline_at"),
            meetings_completion_deadline_at=d.get("meetings_completion_deadline_at"),
            feedback_deadline_at=d.get("feedback_deadline_at"),
        )

    def map_to_partner_dto(self, user_entities: list[UsersEntity]) -> list[PartnerDto]:
        """Maps a list of UsersEntity objects to a list of PartnerDto objects."""
        return [
            PartnerDto(
                id=u.user_id,
                first_name=u.first_name,
                last_name=u.last_name,
                preferred_name=u.preferred_name or u.first_name,
                primary_email=u.primary_email,
            )
            for u in user_entities
        ]

    def map_to_global_preferences_dto(
        self, preference_entity: PreferenceEntity
    ) -> GlobalPreferencesDto:
        """Maps a PreferencesEntity to a GlobalPreferencesDto."""
        industry_data = preference_entity.specific_industry or {}

        return GlobalPreferencesDto(
            specific_industry=SpecificIndustryDto(
                swe=industry_data.get("swe", False),
                uiux=industry_data.get("uiux", False),
                ds=industry_data.get("ds", False),
                pm=industry_data.get("pm", False),
            ),
            skillsets=SkillsetsDto(
                resume_guidance=preference_entity.resume_guidance or False,
                career_path_guidance=preference_entity.career_path_guidance or False,
                experience_sharing=preference_entity.experience_sharing or False,
                industry_trends=preference_entity.industry_trends or False,
                technical_skills=preference_entity.technical_skills or False,
                soft_skills=preference_entity.soft_skills or False,
                networking=preference_entity.networking or False,
                project_management=preference_entity.project_management or False,
            ),
        )

    def map_to_round_preference_dto(
        self, participants_entity: MentorshipRoundParticipantsEntity
    ) -> RoundPreferencesDto:
        """Maps a MentorshipRoundParticipantsEntity to a RoundPreferencesDto."""
        return RoundPreferencesDto(
            participant_role=participants_entity.participant_role,
            expected_partner_ids=list(
                participants_entity.expected_partner_user_id or []
            ),
            unexpected_partner_ids=list(
                participants_entity.unexpected_partner_user_id or []
            ),
            max_partners=participants_entity.max_partners
            if participants_entity.max_partners is not None
            else 1,
            goal=participants_entity.goal or "",
        )
