from backend.dto.base_dto import BaseDto
from backend.dto.preference_dto import (
    SpecificIndustryDto,
    SkillsetsDto,
    ProfileSurveyDto,
)
from backend.common.mentorship_enums import ParticipantRole


class GlobalPreferencesDto(BaseDto):
    specific_industry: SpecificIndustryDto | None = None
    skillsets: SkillsetsDto
    profile_survey: ProfileSurveyDto | None = None


class RoundPreferencesDto(BaseDto):
    participant_role: ParticipantRole
    expected_partner_ids: list[int]
    unexpected_partner_ids: list[int]
    max_partners: int
    goal: str
    current_stage: str | None = None
    time_urgency: str | None = None


class RegistrationDto(BaseDto):
    is_registered: bool
    round_name: str
    global_preferences: GlobalPreferencesDto
    round_preferences: RoundPreferencesDto
