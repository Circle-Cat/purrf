from tenacity import retry, stop_after_attempt, wait_exponential
from src.common.logger import get_logger
from src.common.google_client import GoogleClientFactory

logger = get_logger()


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
        raise ValueError(f"No valid people client provided.")

    try:
        profile = (
            client_people.people()
            .get(resourceName=f"people/{user_id}", personFields="emailAddresses")
            .execute()
        )
    except Exception as e:
        logger.error(f"Failed to fetch profile for user {user_id}: {e}")
        raise RuntimeError(
            f"Unexpected error fetching profile for user {user_id}"
        ) from e

    email_addresses = profile.get("emailAddresses", [])
    if email_addresses:
        email = email_addresses[0].get("value", "")
        if email:
            local_part = email.split("@")[0]
            logger.info(f"Retrieved LDAP '{local_part}' for ID '{user_id}'.")
            return local_part
    logger.warning(f"No email found for person ID: {user_id}.")
    return None
