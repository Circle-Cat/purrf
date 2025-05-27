GOOGLE_SCOPES_LIST = [
    "https://www.googleapis.com/auth/directory.readonly",
    "https://www.googleapis.com/auth/chat.spaces.readonly",
    "https://www.googleapis.com/auth/chat.memberships.readonly",
    "https://www.googleapis.com/auth/chat.messages.readonly",
    "https://www.googleapis.com/auth/calendar.readonly",
]


GOOGLE_CHAT_EVENT_TYPE_CREATE = "created"
GOOGLE_CHAT_EVENT_TYPE_UPDATE = "updated"
GOOGLE_CHAT_EVENT_TYPE_DELETE = "deleted"

# Constants for google chat message field names
MESSAGE = "message"
NAME = "name"
MESSAGE_SENDER = "sender"
CREATE_TIME = "createTime"
MESSAGE_TEXT = "text"
MESSAGE_THREAD = "thread"
MESSAGE_SPACE = "space"
MESSAGE_LAST_UPDATE_TIME = "lastUpdateTime"
MESSAGE_DELETION_METADATA = "deletionMetadata"
MESSAGE_DELETION_TYPE = "deletionType"
VALUE = "value"
MESSAGE_THREAD_ID = "threadId"
MESSAGE_ATTACHMENT = "attachment"

# Constants for Redis keys and members
CREATED_GOOGLE_CHAT_MESSAGES_INDEX_KEY = "google:chat:created:{sender_ldap}:{space_id}"
DELETED_GOOGLE_CHAT_MESSAGES_INDEX_KEY = "google:chat:deleted:{sender_ldap}:{space_id}"
