from backend.dto.base_dto import BaseDto
from backend.dto.preference_dto import SpecificIndustryDto, SkillsetsDto
from backend.common.mentorship_enums import ParticipantRole


class GlobalPreferencesDto(BaseDto):
    specific_industry: SpecificIndustryDto | None = None
    skillsets: SkillsetsDto


class RoundPreferencesDto(BaseDto):
    participant_role: ParticipantRole
    expected_partner_ids: list[int]
    unexpected_partner_ids: list[int]
    max_partners: int
    goal: str


class RegistrationDto(BaseDto):
    is_registered: bool
    round_name: str
    global_preferences: GlobalPreferencesDto
    round_preferences: RoundPreferencesDto
