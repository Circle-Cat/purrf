SCOPES_LIST = [
    "https://www.googleapis.com/auth/directory.readonly",
    "https://www.googleapis.com/auth/chat.spaces.readonly",
    "https://www.googleapis.com/auth/chat.memberships.readonly",
    "https://www.googleapis.com/auth/chat.messages.readonly",
]

CHAT_API_NAME = "chat"
CHAT_API_VERSION = "v1"
PEOPLE_API_NAME = "people"
PEOPLE_API_VERSION = "v1"

USER_EMAIL = "USER_EMAIL"

DEFAULT_SPACE_TYPE = "SPACE"
DEFAULT_PAGE_SIZE = 1000

CREDENTIALS_SUCCESS_MSG = "Credentials retrieved successfully. Project ID: {project_id}"
NO_CREDENTIALS_ERROR_MSG = "No valid credentials provided."
USING_CREDENTIALS_MSG = "Using Credentials type: {credentials_type}"
IMPERSONATE_USER_MSG = "Impersonating user: {user_email}"
SERVICE_CREATED_MSG = "Created {api_name} client successfully."
NO_CLIENT_ERROR_MSG = "No valid {client_name} client provided."

RETRIEVED_SPACES_INFO_MSG = "Retrieved {count} {space_type} type Chat spaces."
RETRIEVED_PEOPLE_INFO_MSG = "Retrieved {count} people from directory."
