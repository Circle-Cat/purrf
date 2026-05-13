from pydantic import Field, field_validator
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from backend.dto.base_request_dto import BaseRequestDto
from datetime import date
from backend.common.mentorship_enums import CommunicationMethod, Degree


class UsersRequestDto(BaseRequestDto):
    first_name: str
    last_name: str
    timezone: str
    communication_method: CommunicationMethod
    preferred_name: str | None = None
    alternative_emails: list[str] = Field(default_factory=list)
    linkedin_link: str | None = None

    @field_validator("timezone")
    @classmethod
    def validate_timezone(cls, v: str) -> str:
        try:
            ZoneInfo(v)
        except (ZoneInfoNotFoundError, KeyError):
            raise ValueError(f"Invalid IANA timezone: {v!r}")
        return v


class WorkHistoryRequestDto(BaseRequestDto):
    id: str | None = None
    title: str
    company_or_organization: str
    start_date: date
    is_current_job: bool
    end_date: date | None = None


class EducationRequestDto(BaseRequestDto):
    id: str | None = None
    degree: Degree
    school: str
    field_of_study: str
    start_date: date
    end_date: date


class ProfileCreateDto(BaseRequestDto):
    user: UsersRequestDto | None = None
    work_history: list[WorkHistoryRequestDto] | None = None
    education: list[EducationRequestDto] | None = None
