# Implement those function in this file
# get_ldap_by_ld(id)
# list_directory_all_people_ldap(client_people)


from tools.log.logger import setup_logger
import logging
from google.authentication_utils import GoogleClientFactory
from google.constants import (
    RETRIEVED_SPACES_INFO_MSG,
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


def get_chat_spaces(space_type, page_size):
    """Retrieves a dictionary of Google Chat spaces with their display names.

    Args:
        space_type (str): The type of spaces to filter (e.g., SPACE, ROOM).
        page_size (int): The number of spaces to retrieve per page.

    Returns:
        dict: A dictionary where keys are space IDs and values are display names, or None if an error occurs.

    Examples:
        {
            "BBBA9AJg-Ty": "CircleCat Mentorship Program,
            "BVDL3CTY-AD": "Engineering Team Chat"
        }
    Raises:
        ValueError: If no valid chat client provided.
        googleapiclient.errors.HttpError: If an error occurs during the API call.
    """
    client_chat = GoogleClientFactory().create_chat_client()
    if not client_chat:
        raise ValueError(NO_CLIENT_ERROR_MSG.format(client_name=CHAT_API_NAME))

    space_display_names = {}
    page_token = None

    while True:
        response = (
            client_chat.spaces()
            .list(
                pageSize=page_size,
                filter=f'space_type = "{space_type}"',
                pageToken=page_token,
            )
            .execute()
        )
        spaces = response.get("spaces", [])
        for space in spaces:
            space_id = space.get("name").split("/")[1]
            display_name = space.get("displayName")
            space_display_names[space_id] = display_name

        page_token = response.get("nextPageToken")
        if not page_token:
            break

    logging.info(
        RETRIEVED_SPACES_INFO_MSG.format(
            count=len(space_display_names), space_type=space_type
        )
    )
    return space_display_names


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
        response = (
            client_people.people()
            .listDirectoryPeople(
                readMask="emailAddresses",
                pageSize=DEFAULT_PAGE_SIZE,
                sources=["DIRECTORY_SOURCE_TYPE_DOMAIN_PROFILE"],
                pageToken=page_token,
            )
            .execute()
        )
        people = response.get("people", [])
        directory_people.extend(people)
        page_token = response.get("nextPageToken")
        if not page_token:
            break
    for person in directory_people:
        emailAddresses_data = person.get("emailAddresses")[0]
        id = emailAddresses_data.get("metadata", {}).get("source", {}).get("id", {})
        ldap = emailAddresses_data.get("value", "").split("@")[0]
        formatted_people[id] = ldap

    logging.info(RETRIEVED_PEOPLE_INFO_MSG.format(count=len(formatted_people)))
    return formatted_people


def get_ldap_by_id(user_id):
    """
    Retrieves the LDAP identifier (local part of the email) for a given person ID using the Google People API.

    This function fetches the profile of a person identified by their ID and extracts the local part of their
    email address to return as the LDAP identifier.

    Args:
        user_id (str): The unique identifier of the person in the Google People API.

    Returns:
        str or None: The LDAP identifier (local part of the email) if found, otherwise None.

    Raises:
        ValueError: If no valid People API client is provided.
        googleapiclient.errors.HttpError: If an error occurs during the API call.
    """

    client = GoogleClientFactory()
    client_people = client.create_people_client()

    profile = (
        client_people.people()
        .get(resourceName=f"people/{user_id}", personFields="emailAddresses")
        .execute()
    )

    email_addresses = profile.get("emailAddresses", [])
    if email_addresses:
        email = email_addresses[0].get("value", "")
        if email:
            local_part = email.split("@")[0]
            logging.info(RETRIEVED_ID_INFO_MSG.format(local_part=local_part, id=user_id))
            return local_part
    logging.warning(NO_EMAIL_FOUND_ERROR_MSG.format(id=user_id))
    return None
