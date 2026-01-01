from datetime import datetime
from backend.dto.base_internal_dto import BaseInternalDTO


class CalendarDTO(BaseInternalDTO):
    calendar_id: str
    summary: str


class AttendanceDTO(BaseInternalDTO):
    ldap: str
    join_time: datetime
    leave_time: datetime


class CalendarEventDTO(BaseInternalDTO):
    event_id: str
    calendar_id: str
    summary: str = ""
    start: datetime
    is_recurring: bool = False
    meeting_code: str

    @property
    def start_ts(self) -> int:
        """Returns the event start time as a Unix timestamp."""
        return int(self.start.timestamp())
