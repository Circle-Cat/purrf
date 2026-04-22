from backend.dto.base_dto import BaseDto


class SpecificIndustryDto(BaseDto):
    swe: bool = False
    uiux: bool = False
    ds: bool = False
    pm: bool = False


class SkillsetsDto(BaseDto):
    resume_guidance: bool = False
    career_path_guidance: bool = False
    experience_sharing: bool = False
    industry_trends: bool = False
    technical_skills: bool = False
    soft_skills: bool = False
    networking: bool = False
    project_management: bool = False


class ProfileSurveyDto(BaseDto):
    # Mentor fields
    career_transition: str | None = None
    career_transition_other: str | None = None
    region: str | None = None
    region_other: str | None = None
    external_mentoring_exp: str | None = None
    # Mentee fields
    current_background: str | None = None
    current_background_other: str | None = None
    target_region: str | None = None
    target_region_other: str | None = None
