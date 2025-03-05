CHAT_API_NAME = "chat"
CHAT_API_VERSION = "v1"
PEOPLE_API_NAME = "people"
PEOPLE_API_VERSION = "v1"

DEFAULT_SPACE_TYPE = "SPACE"
DEFAULT_PAGE_SIZE = 1000

MESSAGE_TYPE_CREATE = "create"

CREDENTIALS_SUCCESS_MSG = "Credentials retrieved successfully. Project ID: {project_id}"
USING_SERVICE_ACCOUNT_CREDENTIALS_MSG = "Using service account credentials."
USING_USER_CREDENTIALS_MSG = "Using user credentials."
USING_OTHER_CREDENTIALS_MSG = "Using other credentials type: {credentials_type}"
NO_CREDENTIALS_ERROR_MSG = "No valid credentials provided."
SERVICE_CREATED_MSG = "Created {api_name} client successfully."
NO_CLIENT_ERROR_MSG = "No valid {client_name} client provided."

RETRIEVED_SPACES_INFO_MSG = "Retrieved {count} {space_type} type Chat spaces."
RETRIEVED_PEOPLE_INFO_MSG = "Retrieved {count} people from directory."

FETCHING_MESSAGES_INFO_MSG = "Fetching messages for space ID: {space_id}"
FETCHED_MESSAGES_INFO_MSG = "Fetching {count} messages for space ID: {space_id}"
FETCHED_ALL_MESSAGES_INFO_MSG = "{count} messages fetched for all spaces"
SENDER_LDAP_NOT_FOUND_DEBUG_MSG = (
    "Sender LDAP not found for sender ID: {sender_id}, message: {message}"
)
STORED_MESSAGES_INFO_MSG = (
    "{stored_count} out of {total_count} messages stored in Redis successfully."
)
