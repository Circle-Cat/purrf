from datetime import date
from backend.dto.base_dto import BaseDto


class WorkHistoryDto(BaseDto):
    id: str
    title: str
    company_or_organization: str
    start_date: date
    is_current_job: bool
    end_date: date | None = None
