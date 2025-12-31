from pydantic import Field
from backend.dto.base_request_dto import BaseRequestDto
from datetime import date
from backend.common.mentorship_enums import CommunicationMethod, UserTimezone, Degree


class UsersRequestDto(BaseRequestDto):
    first_name: str
    last_name: str
    timezone: UserTimezone
    communication_method: CommunicationMethod
    preferred_name: str | None = None
    alternative_emails: list[str] = Field(default_factory=list)
    linkedin_link: str | None = None


class WorkHistoryRequestDto(BaseRequestDto):
    id: str | None
    title: str
    company_or_organization: str
    start_date: date
    is_current_job: bool
    end_date: date | None = None


class EducationRequestDto(BaseRequestDto):
    id: str | None
    degree: Degree
    school: str
    field_of_study: str
    start_date: date
    end_date: date


class ProfileCreateDto(BaseRequestDto):
    user: UsersRequestDto | None = None
    work_history: list[WorkHistoryRequestDto] = Field(default_factory=list)
    education: list[EducationRequestDto] = Field(default_factory=list)
