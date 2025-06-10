from enum import Enum

GOOGLE_SCOPES_LIST = [
    "https://www.googleapis.com/auth/directory.readonly",
    "https://www.googleapis.com/auth/chat.spaces.readonly",
    "https://www.googleapis.com/auth/chat.memberships.readonly",
    "https://www.googleapis.com/auth/chat.messages.readonly",
    "https://www.googleapis.com/auth/calendar.readonly",
]

MICROSOFT_SCOPES_LIST = ["https://graph.microsoft.com/.default"]


class GoogleChatEventType(str, Enum):
    CREATED = "created"
    UPDATED = "updated"
    DELETED = "deleted"


# Constants for Redis keys
CREATED_GOOGLE_CHAT_MESSAGES_INDEX_KEY = "google:chat:created:{sender_ldap}:{space_id}"
DELETED_GOOGLE_CHAT_MESSAGES_INDEX_KEY = "google:chat:deleted:{sender_ldap}:{space_id}"

MICROSOFT_LDAP_KEY = "ldap:{account_status}"


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
MICROSOFT_USER_INFO_SELECT_FIELDS = ["displayName", "mail", "accountEnabled"]
MICROSOFT_CONSISTENCY_HEADER = "ConsistencyLevel"
MICROSOFT_CONSISTENCY_VALUE = "eventual"

MICROSOFT_TEAMS_CHAT_SUBSCRIPTION_MAX_LIFETIME = 4320
MICROSOFT_TEAMS_CHAT_MESSAGES_SUBSCRIPTION_RESOURCE = "/chats/{chat_id}/messages"


class MicrosoftChatMessagesChangeType(str, Enum):
    CREATED = "created"
    UPDATED = "updated"
    DELETED = "deleted"
