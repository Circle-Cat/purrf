from enum import Enum

GOOGLE_USER_SCOPES_LIST = [
    "https://www.googleapis.com/auth/directory.readonly",
    "https://www.googleapis.com/auth/chat.spaces.readonly",
    "https://www.googleapis.com/auth/chat.memberships.readonly",
    "https://www.googleapis.com/auth/chat.messages.readonly",
    "https://www.googleapis.com/auth/calendar.readonly",
]

GOOGLE_ADMIN_SCOPES_LIST = [
    "https://www.googleapis.com/auth/admin.reports.audit.readonly",
]

MICROSOFT_SCOPES_LIST = ["https://graph.microsoft.com/.default"]


class GoogleChatEventType(str, Enum):
    CREATED = "created"
    UPDATED = "updated"
    DELETED = "deleted"


BASE_EVENT_TYPE = "google.workspace.chat.message.v1"

EVENT_TYPES = {
    f"{BASE_EVENT_TYPE}.{event_type.value}" for event_type in GoogleChatEventType
}

EXPIRATION_REMINDER_EVENT = "google.workspace.events.subscription.v1.expirationReminder"

# Constants for Redis keys
CREATED_GOOGLE_CHAT_MESSAGES_INDEX_KEY = "google:chat:created:{sender_ldap}:{space_id}"
DELETED_GOOGLE_CHAT_MESSAGES_INDEX_KEY = "google:chat:deleted:{sender_ldap}:{space_id}"

GOOGLE_CALENDAR_LIST_INDEX_KEY = "calendarlist"
GOOGLE_CALENDAR_EVENT_DETAIL_KEY = "event:{event_id}"
GOOGLE_EVENT_ATTENDANCE_KEY = "event:{event_id}:user:{ldap}:attendance"
GOOGLE_CALENDAR_USER_EVENTS_KEY = "calendar:{calendar_id}:user:{ldap}:events"

MICROSOFT_SUBSCRIPTION_CLIENT_STATE_SECRET_KEY = (
    "microsoft:client_state:{subscription_id}"
)
MICROSOFT_LDAP_KEY = "ldap:{account_status}"
MICROSOFT_CHAT_MESSAGES_INDEX_KEY = "microsoft:chat:{message_status}:{sender_ldap}"
MICROSOFT_CHAT_MESSAGES_DETAILS_KEY = "microsoft:messages:{message_id}"
MICROSOFT_CHAT_TOPICS = "microsoft:chat:topics"
PUBSUB_PULL_MESSAGES_STATUS_KEY = "pull_status:{subscription_id}"


class MicrosoftAccountStatus(str, Enum):
    ACTIVE = "active"
    TERMINATED = "terminated"
    ALL = "all"

    @classmethod
    def validate_status(cls, status: str) -> "MicrosoftAccountStatus":
        """Validate the input status to check if it is valid, and return the corresponding enum value."""
        try:
            return cls(status.lower())
        except ValueError:
            valid_statuses = [e.value for e in cls]
            raise ValueError(
                f"Invalid status. Valid values are: {', '.join(valid_statuses)}"
            )


MICROSOFT_USER_INFO_FILTER = "endswith(mail,'circlecat.org')"
MICROSOFT_USER_INFO_SELECT_FIELDS = ["displayName", "mail", "accountEnabled", "id"]
MICROSOFT_CONSISTENCY_HEADER = "ConsistencyLevel"
MICROSOFT_CONSISTENCY_VALUE = "eventual"
MICROSOFT_TEAMS_MESSAGES_SORTER = ["createdDateTime desc"]
MICROSOFT_TEAMS_MESSAGES_MAX_RESULT = 50

MICROSOFT_TEAMS_CHAT_SUBSCRIPTION_CLIENT_STATE_BYTE_LENGTH = 32
MICROSOFT_TEAMS_CHAT_SUBSCRIPTION_MAX_LIFETIME = 4320
MICROSOFT_TEAMS_CHAT_MESSAGES_SUBSCRIPTION_RESOURCE = "/chats/{chat_id}/messages"


class MicrosoftChatMessagesChangeType(str, Enum):
    CREATED = "created"
    UPDATED = "updated"
    DELETED = "deleted"

    @classmethod
    def is_supported(cls, value: str) -> bool:
        return value in cls._value2member_map_


class MicrosoftChatMessageAttachmentType(str, Enum):
    REFERENCE_LINK = "reference"
    MESSAGE_REFERENCE = "messageReference"


class MicrosoftChatMessageType(str, Enum):
    Message = ("message",)
    ChatEvent = ("chatEvent",)
    Typing = ("typing",)
    UnknownFutureValue = ("unknownFutureValue",)
    SystemEventMessage = ("systemEventMessage",)


class MicrosoftChatType(str, Enum):
    OneOnOne = ("oneOnOne",)
    Group = ("group",)
    Meeting = ("meeting",)
    UnknownFutureValue = ("unknownFutureValue",)


class PullStatus(Enum):
    RUNNING = ("running", "Pulling started for {subscription_id}.")
    FAILED = ("failed", "Pulling failed for {subscription_id}: {error}.")
    STOPPED = ("stopped", "Pulling explicitly stopped for {subscription_id}.")
    NOT_STARTED = ("not_started", "Pulling has not started for {subscription_id}.")

    def __init__(self, code, default_message_template):
        self.code = code
        self.default_message_template = default_message_template

    def format_message(self, **kwargs) -> str:
        return self.default_message_template.format(**kwargs)


# Constants for Gerrit
class GerritChangeStatus(str, Enum):
    OPEN = "open"
    NEW = "new"
    PENDING = "pending"
    REVIEWED = "reviewed"
    MERGED = "merged"
    ABANDONED = "abandoned"


ALL_GERRIT_STATUSES: list[str] = [status.value for status in GerritChangeStatus]

GERRIT_UNDER_REVIEW = "under_review"

GERRIT_UNDER_REVIEW_STATUSES = {
    GerritChangeStatus.OPEN,
    GerritChangeStatus.NEW,
    GerritChangeStatus.PENDING,
}
GERRIT_UNDER_REVIEW_STATUS_VALUES = {s.value for s in GERRIT_UNDER_REVIEW_STATUSES}

GERRIT_STATUS_TO_FIELD = {
    GerritChangeStatus.MERGED: "cl_merged",
    GerritChangeStatus.ABANDONED: "cl_abandoned",
    GERRIT_UNDER_REVIEW: "cl_under_review",
}

GERRIT_CL_REVIEWED_FIELD = "cl_reviewed"
GERRIT_LOC_MERGED_FIELD = "loc_merged"
GERRIT_DATE_BUCKET_TEMPLATE = "{start}_{end}"

# Gerrit Redis key templates
GERRIT_STATS_ALL_TIME_KEY = "gerrit:stats:{ldap}"
GERRIT_STATS_MONTHLY_BUCKET_KEY = "gerrit:stats:{ldap}:{bucket}"
GERRIT_STATS_PROJECT_BUCKET_KEY = "gerrit:stats:{ldap}:{project}:{bucket}"
GERRIT_CHANGE_STATUS_KEY = "gerrit:change_status"
GERRIT_DEDUPE_REVIEWED_KEY = "gerrit:dedupe:reviewed:{change_number}"


# Constants for Jira
class JiraIssueStatus(str, Enum):
    TODO = "todo"
    IN_PROGRESS = "in_progress"
    DONE = "done"
    ALL = "all"


# Jira status ID mapping to standard statuses
JIRA_STATUS_ID_MAP: dict[str, str] = {
    "4": JiraIssueStatus.TODO,
    "10000": JiraIssueStatus.TODO,
    "10301": JiraIssueStatus.TODO,
    "10302": JiraIssueStatus.TODO,
    "3": JiraIssueStatus.IN_PROGRESS,
    "10303": JiraIssueStatus.IN_PROGRESS,
    "10304": JiraIssueStatus.IN_PROGRESS,
    "10305": JiraIssueStatus.IN_PROGRESS,
    "10307": JiraIssueStatus.IN_PROGRESS,
    "10309": JiraIssueStatus.IN_PROGRESS,
    "10500": JiraIssueStatus.IN_PROGRESS,
    "5": JiraIssueStatus.IN_PROGRESS,
    "10200": JiraIssueStatus.IN_PROGRESS,
    "6": JiraIssueStatus.DONE,
    "10001": JiraIssueStatus.DONE,
    "10201": JiraIssueStatus.DONE,
    "10306": JiraIssueStatus.DONE,
}

ALL_JIRA_STATUSES: list[str] = [status.value for status in JiraIssueStatus]

# Excluded status ID (obsolete)
JIRA_EXCLUDED_STATUS_ID = "10100"

# Jira Redis key templates
JIRA_ISSUE_DETAILS_KEY = "jira:issue:{issue_id}"
JIRA_LDAP_PROJECT_STATUS_INDEX_KEY = (
    "jira:ldap:{ldap}:project:{project_id}:status:{status}"
)
JIRA_PROJECTS_KEY = "jira:project"

# Jira API configuration
JIRA_MAX_RESULTS_DEFAULT = 1000
JIRA_STORY_POINT_FIELD = "customfield_10106"
# Jira Redis key templates
JIRA_PROJECTS_KEY = "jira:project"
GERRIT_STAT_FIELDS = [
    "cl_merged",
    "cl_abandoned",
    "cl_under_review",
    "loc_merged",
    "cl_reviewed",
]

DATE_FORMAT_YMD = "%Y-%m-%d"
