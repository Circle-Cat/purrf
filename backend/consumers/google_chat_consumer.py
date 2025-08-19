from tenacity import retry, stop_after_attempt, wait_exponential
from backend.common.logger import get_logger
from backend.common.google_client import GoogleClientFactory
from backend.utils.google_chat_message_store import store_messages
from backend.consumers.pubsub_puller import PubSubPuller
import json
from backend.common.constants import (
    EXPIRATION_REMINDER_EVENT,
    EVENT_TYPES,
)

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
        raise ValueError("No valid people client provided.")

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


def pull_messages(project_id, subscription_id):
    """
    Listens to the given Pub/Sub subscription and processes incoming events.

    For each event:
      - If the event type is "google.workspace.events.subscription.v1.expirationReminder",
        renews the subscription using subscriptions.update().
      - Otherwise, uses get_ldap_by_id(senderId) to obtain the sender's LDAP,
        then stores the event in Redis.

    Args:
        subscription_id (str): The Pub/Sub subscription ID to listen on.
        project_id (str): The Google Cloud project ID associated with the subscription.

    Returns:
        None: This function runs continuously and does not return until interrupted.

    Raises:
        ValueError: If any required field (e.g., senderId, spaceName, message) is missing from the payload.
        googleapiclient.errors.HttpError: If an error occurs during the subscription renewal process
    """

    logger.info(
        "Starting pull_messages with project_id: '%s' and subscription_id: '%s'",
        project_id,
        subscription_id,
    )

    if not subscription_id or not project_id:
        missing = []
        if not subscription_id:
            missing.append("subscription_id")
        if not project_id:
            missing.append("project_id")
        if missing:
            raise ValueError(
                f"Missing required field(s) for pull_messages: {', '.join(missing)}"
            )

    def callback(message):
        logger.info("Received message: %s", message)
        attributes = message.attributes
        message_type_full = attributes.get("ce-type")

        try:
            data = json.loads(message.data.decode("utf-8"))
            logger.info(data)
        except (UnicodeDecodeError, json.JSONDecodeError) as err:
            logger.error("Failed to decode/parse message data: %s", err)
            message.nack()
            return

        subscription_info = data.get("subscription")
        if message_type_full == EXPIRATION_REMINDER_EVENT:
            subscription_name = subscription_info.get("name")
            if not subscription_name:
                logger.error(
                    "No subscription_name provided in payload for expiration reminder event."
                )
                message.nack()
                raise ValueError(
                    "No subscription_name provided in payload for expiration reminder event."
                )
            logger.info("Renewing subscription: %s", subscription_name)
            renew_subscription(project_id, subscription_name)
            message.ack()
            logger.info("Subscription renewed and message acknowledged.")
            return

        if message_type_full in EVENT_TYPES:
            message_type = message_type_full.split(".")[-1] if message_type_full else ""

            chat_message = data.get("message")

            sender_name = chat_message.get("sender", {}).get("name", "")
            sender_id = sender_name.split("/")[1] if sender_name else ""

            sender_ldap = get_ldap_by_id(sender_id) if sender_id else ""

            store_messages(sender_ldap, chat_message, message_type)

            message.ack()
            logger.info("Message processed and acknowledged.")

    puller = PubSubPuller(project_id, subscription_id)
    puller.start_pulling_messages(callback)


def renew_subscription(project_id, subscription_name):
    """
    Renews a subscription by calling subscriptions.update() of the Workspace Events API.
    Sets the expiration_policy to an empty dict to ensure the subscription never expires.
    """
    service = GoogleClientFactory().create_workspaceevents_client()

    BODY = {
        "ttl": {"seconds": 0},
    }

    response = (
        service.subscriptions()
        .patch(name=subscription_name, updateMask="ttl", body=BODY)
        .execute()
    )
    logger.info("Renew subscription response: %s", response)
