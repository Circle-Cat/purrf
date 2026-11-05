from datetime import datetime
from backend.dto.base_internal_dto import BaseInternalDTO


class CalendarDTO(BaseInternalDTO):
    calendar_id: str
    summary: str
    # "owner" | "writer" | "reader" | "freeBusyReader" as returned by
    # calendarList.list. Used to tell Purrf's own operational calendars (owned
    # by the impersonated bot account) from real organizational calendars
    # (created by people and shared in). Defaults to "" so existing
    # construction sites that do not care keep working.
    access_role: str = ""


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
