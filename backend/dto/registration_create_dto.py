from backend.dto.base_request_dto import BaseRequestDto
from backend.dto.preference_dto import SpecificIndustryDto, SkillsetsDto
from backend.common.mentorship_enums import ParticipantRole


class GlobalPreferencesDto(BaseRequestDto):
    specific_industry: SpecificIndustryDto | None = None
    skillsets: SkillsetsDto


class RoundPreferencesDto(BaseRequestDto):
    participant_role: ParticipantRole
    expected_partner_ids: list[int] | None = None
    unexpected_partner_ids: list[int] | None = None
    max_partners: int
    goal: str | None = None


class RegistrationCreateDto(BaseRequestDto):
    global_preferences: GlobalPreferencesDto
    round_preferences: RoundPreferencesDto
