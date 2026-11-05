from typing import Annotated
from pydantic import Field, field_validator, model_validator
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from backend.dto.base_request_dto import BaseRequestDto
from datetime import date, datetime, timedelta, timezone
from backend.common.mentorship_enums import CommunicationMethod, Degree

# Stripped by BaseRequestDto before the length check, so whitespace is blank.
RequiredText = Annotated[str, Field(min_length=1)]

# The latest local date anywhere: a month the user has already reached must
# never read as the future because the server is still in the previous one.
_EARLIEST_TIMEZONE = timezone(timedelta(hours=14))


def _check_start_and_end(start_date: date, end_date: date | None) -> None:
    """
    Apply the profile form's date rules, at month precision like the form.

    Raises:
        ValueError: If the start month is after the current month, or the end
            month is before the start month.
    """
    today = datetime.now(_EARLIEST_TIMEZONE).date()
    if (start_date.year, start_date.month) > (today.year, today.month):
        raise ValueError("Start date cannot be in the future")
    if end_date is not None and (end_date.year, end_date.month) < (
        start_date.year,
        start_date.month,
    ):
        raise ValueError("End date cannot be earlier than start date")


class UsersRequestDto(BaseRequestDto):
    first_name: str
    last_name: str
    timezone: str
    communication_method: CommunicationMethod
    preferred_name: str | None = None
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
    title: RequiredText
    company_or_organization: RequiredText
    start_date: date
    is_current_job: bool
    end_date: date | None = None

    @model_validator(mode="after")
    def validate_dates(self) -> "WorkHistoryRequestDto":
        if self.is_current_job:
            _check_start_and_end(self.start_date, None)
            return self
        if self.end_date is None:
            raise ValueError("End date is required unless this is a current job")
        _check_start_and_end(self.start_date, self.end_date)
        return self


class EducationRequestDto(BaseRequestDto):
    id: str | None = None
    degree: Degree
    school: RequiredText
    field_of_study: RequiredText
    start_date: date
    end_date: date

    @model_validator(mode="after")
    def validate_dates(self) -> "EducationRequestDto":
        _check_start_and_end(self.start_date, self.end_date)
        return self


class ProfileCreateDto(BaseRequestDto):
    user: UsersRequestDto | None = None
    work_history: list[WorkHistoryRequestDto] | None = None
    education: list[EducationRequestDto] | None = None
