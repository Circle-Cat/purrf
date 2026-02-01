from backend.dto.base_dto import BaseDto


# Response DTO
class ActivitySummaryDto(BaseDto):
    ldap: str
    chat_count: int = 0
    meeting_hours: float = 0.0
    cl_merged: int = 0
    loc_merged: int = 0
    jira_issue_done: int = 0
