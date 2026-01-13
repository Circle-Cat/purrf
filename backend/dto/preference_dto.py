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
