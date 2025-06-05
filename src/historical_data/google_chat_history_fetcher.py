from src.common.google_client import GoogleClientFactory
from src.common.logger import get_logger
from googleapiclient.errors import HttpError
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)

logger = get_logger()


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
        raise ValueError(
            "Failed to fetch historical chat messages: Google People client is unavailable."
        )

    directory_people = []
    formatted_people = {}
    page_token = None
    while True:
        req = client_people.people().listDirectoryPeople(
            readMask="emailAddresses",
            pageSize=100,
            sources=["DIRECTORY_SOURCE_TYPE_DOMAIN_PROFILE"],
            pageToken=page_token,
        )
        try:
            response = _execute_request(req)
        except HttpError as e:
            logger.error(
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

    logger.info(
        "Successfully retrieved %d directory people from Google Workspace.",
        len(formatted_people),
    )
    return formatted_people
