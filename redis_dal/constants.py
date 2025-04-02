REDIS_HOST_PORT_ERROR_MSG = "Redis host or port not set in environment variables."
REDIS_CLIENT_CREATED_MSG = "Created Redis client {redis_client} successfully."

REDIS_KEY_FORMAT = "spaces/{space_id}:ldap:{sender_ldap}."
REDIS_MESSAGE_STORED_DEBUG_MSG = "Stored message in Redis: {redis_key}, score: {score}."

HOST = "REDIS_HOST"
PORT = "REDIS_PORT"
PASSWORD = "REDIS_PASSWORD"

TYPE_CREATE = "created"
TYPE_UPDATE = "updated"
TYPE_DELETE = "deleted"


# Constants for message field names
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
CHAT_INDEX_KEY_FORMAT = "{space_id}/{sender_ldap}"
