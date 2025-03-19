import json
from google.authentication_utils import GoogleClientFactory
from redis_dal.redis_utils import store_messages
from google.chat_utils import get_ldap_by_id
import logging
from google.constants import (
    SUBSCRIBER_API_NAME,
    EXPIRATION_REMINDER_EVENT,
    EVENT_TYPES,
)


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

    logging.info(
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
        raise ValueError(
            MISSING_FIELDS_MSG.format(
                fields=", ".join(missing), method="pull messages", data=data
            )
        )

    subscriber = GoogleClientFactory().create_subscriber_client()
    if not subscriber:
        raise ValueError(NO_CLIENT_ERROR_MSG.format(client_name=SUBSCRIBER_API_NAME))

    subscription_path = subscriber.subscription_path(project_id, subscription_id)

    def callback(message):
        logging.info("Received message: %s", message)
        attributes = message.attributes
        message_type_full = attributes.get("ce-type")

        try:
            data = json.loads(message.data.decode("utf-8"))
            logging.info(data)
        except (UnicodeDecodeError, json.JSONDecodeError) as err:
            logging.error("Failed to decode/parse message data: %s", err)
            message.nack()
            return

        subscription_info = data.get("subscription")
        if message_type_full == EXPIRATION_REMINDER_EVENT:
            subscription_name = subscription_info.get("name")
            if not subscription_name:
                logging.error(
                    "No subscription_name provided in payload for expiration reminder event."
                )
                message.nack()
                raise ValueError(
                    "No subscription_name provided in payload for expiration reminder event."
                )
            logging.info("Renewing subscription: %s", subscription_name)
            renew_subscription(project_id, subscription_name)
            message.ack()
            logging.info("Subscription renewed and message acknowledged.")
            return

        if message_type_full in EVENT_TYPES:
            message_type = message_type_full.split(".")[-1] if message_type_full else ""

            chat_message = data.get("message")

            sender_name = chat_message.get("sender", {}).get("name", "")
            sender_id = sender_name.split("/")[1] if sender_name else ""

            sender_ldap = get_ldap_by_id(sender_id) if sender_id else ""

            store_messages(sender_ldap, chat_message, message_type)

            message.ack()
            logging.info("Message processed and acknowledged.")

    streaming_pull_future = subscriber.subscribe(subscription_path, callback=callback)
    try:
        streaming_pull_future.result()
    except TimeoutError:
        streaming_pull_future.cancel()
        logging.error("Stopped listening to subscription.")
        streaming_pull_future.result()


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
    logging.info("Renew subscription response: %s", response)
