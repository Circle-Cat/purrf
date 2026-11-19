from pydantic import Field, model_validator
from backend.common.linkedin_url import normalize_linkedin_profile_url
from backend.dto.base_request_dto import BaseRequestDto
from backend.dto.preference_dto import (
    SpecificIndustryDto,
    SkillsetsDto,
)
from backend.common.mentorship_enums import ParticipantRole


class ProfileSurveyCreateDto(BaseRequestDto):
    # Mentor fields
    career_transition: str | None = Field(default=None, max_length=200)
    career_transition_other: str | None = Field(default=None, max_length=200)
    region: str | None = Field(default=None, max_length=200)
    region_other: str | None = Field(default=None, max_length=200)
    external_mentoring_exp: str | None = Field(default=None, max_length=200)
    # Mentee fields
    current_background: str | None = Field(default=None, max_length=200)
    current_background_other: str | None = Field(default=None, max_length=200)
    target_region: str | None = Field(default=None, max_length=200)
    target_region_other: str | None = Field(default=None, max_length=200)


class GlobalPreferencesDto(BaseRequestDto):
    specific_industry: SpecificIndustryDto | None = None
    skillsets: SkillsetsDto
    profile_survey: ProfileSurveyCreateDto | None = None


class RoundPreferencesDto(BaseRequestDto):
    participant_role: ParticipantRole
    expected_partner_ids: list[int] | None = None
    unexpected_partner_ids: list[int] | None = None
    max_partners: int
    goal: str | None = Field(default=None, max_length=300)
    current_stage: str | None = Field(default=None, max_length=100)
    time_urgency: str | None = Field(default=None, max_length=100)
    share_linkedin: bool | None = None


class RegistrationCreateDto(BaseRequestDto):
    global_preferences: GlobalPreferencesDto
    round_preferences: RoundPreferencesDto
    # Written back to the user's profile when share_linkedin is true.
    linkedin_link: str | None = None

    @model_validator(mode="after")
    def validate_shared_linkedin_link(self) -> "RegistrationCreateDto":
        if not self.round_preferences.share_linkedin:
            return self
        link = normalize_linkedin_profile_url(self.linkedin_link)
        if link is None:
            raise ValueError(
                "A linkedin.com profile link is required to share your LinkedIn."
            )
        # Bypasses validate_assignment, which would rerun this validator.
        self.__dict__["linkedin_link"] = link
        return self
