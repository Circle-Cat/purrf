# Implement those function in this file
# get_ldap_by_ld(id)
# list_directory_all_people_ldap(client_people)


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


def list_directory_all_people_ldap():
    """
    Retrieves a dictionary of sender IDs to LDAP identifiers from the Google People API.

    This function fetches all directory people from the Google People API, extracts their sender IDs and LDAP
    identifiers, and returns them as a dictionary.

    Steps:
    1.  Validates the provided People API client.
    2.  Fetches directory people in batches using pagination.
    3.  Extracts the sender ID and LDAP identifier from each person's email address.
    4.  Stores the sender ID and LDAP identifier in a dictionary.
    5.  Logs the number of people retrieved from the directory.

    Returns:
        dict: A dictionary mapping sender IDs (str) to LDAP identifiers (str).

    Raises:
        ValueError: If no valid people client provided.
        googleapiclient.errors.HttpError: If an error occurs during the API call.
        KeyError: If the expected data structure is not present in the API response.
        IndexError: If the email address list is empty.
    """
    client_people = GoogleClientFactory().create_people_client()
    if not client_people:
        raise ValueError(NO_CLIENT_ERROR_MSG.format(client_name=PEOPLE_API_NAME))

    directory_people = []
    formatted_people = {}
    page_token = None
    while True:
        req = client_people.people().listDirectoryPeople(
            readMask="emailAddresses",
            pageSize=DEFAULT_PAGE_SIZE,
            sources=["DIRECTORY_SOURCE_TYPE_DOMAIN_PROFILE"],
            pageToken=page_token,
        )
        try:
            response = _execute_request(req)
        except HttpError as e:
            logging.error(
                "Error fetching directory people (page_token=%s): %s",
                page_token,
                e,
                exc_info=True,
            )
            raise RuntimeError("Unable to fetch directory people") from e

        people = response.get("people")
        if people is None:
            raise ValueError(
                "list_directory_all_people_ldap is missing 'people' field "
            )

        directory_people.extend(people)
        page_token = response.get("nextPageToken")
        if not page_token:
            break
    for person in directory_people:
        emailAddresses_data = person.get("emailAddresses")[0]
        id = emailAddresses_data.get("metadata", {}).get("source", {}).get("id", {})
        ldap = emailAddresses_data.get("value", "").split("@")[0]
        formatted_people[id] = ldap

    if not formatted_people:
        raise ValueError("No directory people were found in the domain.")

    logging.info(RETRIEVED_PEOPLE_INFO_MSG.format(count=len(formatted_people)))
    return formatted_people


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
