# Implement those function in this file
# get_ldap_by_ld(id)

from tools.log.logger import setup_logger
import logging
from google.authentication_utils import GoogleClientFactory
from googleapiclient.errors import HttpError
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)
from google.constants import (
    NO_CLIENT_ERROR_MSG,
    CHAT_API_NAME,
    PEOPLE_API_NAME,
    DEFAULT_PAGE_SIZE,
    RETRIEVED_PEOPLE_INFO_MSG,
    RETRIEVED_ID_INFO_MSG,
    NO_EMAIL_FOUND_ERROR_MSG,
)
from google.authentication_utils import GoogleClientFactory

setup_logger()


@retry(
    retry=retry_if_exception_type(HttpError),
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=3),
    reraise=True,
)
def _execute_request(request):
    return request.execute()


@retry(
    reraise=True,
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=3),
)
def get_ldap_by_id(user_id):
    """
    Retrieves the LDAP identifier (local part of the email) for a given person ID using the Google People API.

    This function fetches the profile of a person identified by their ID and extracts the local part of their
    email address to return as the LDAP identifier.

    Args:
        id (str): The unique identifier of the person in the Google People API.

    Returns:
        str or None: The LDAP identifier (local part of the email) if found, otherwise None.

    Raises:
        ValueError: If no valid People API client is provided.
        googleapiclient.errors.HttpError: If an error occurs during the API call.
    """

    client_people = GoogleClientFactory().create_people_client()
    if not client_people:
        raise ValueError(NO_CLIENT_ERROR_MSG.format(client_name=PEOPLE_API_NAME))

    try:
        profile = (
            client_people.people()
            .get(resourceName=f"people/{user_id}", personFields="emailAddresses")
            .execute()
        )
    except Exception as e:
        logging.error(f"Failed to fetch profile for user {user_id}: {e}")
        raise RuntimeError(
            f"Unexpected error fetching profile for user {user_id}"
        ) from e

    email_addresses = profile.get("emailAddresses", [])
    if email_addresses:
        email = email_addresses[0].get("value", "")
        if email:
            local_part = email.split("@")[0]
            logging.info(
                RETRIEVED_ID_INFO_MSG.format(local_part=local_part, id=user_id)
            )
            return local_part
    logging.warning(NO_EMAIL_FOUND_ERROR_MSG.format(id=user_id))
    return None
