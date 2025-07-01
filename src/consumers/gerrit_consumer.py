import json
from src.consumers.pubsub_puller import PubSubPuller
from src.common.redis_client import RedisClientFactory
from src.historical_data.gerrit_history_fetcher import (
    store_change,
    compute_buckets,
    bump_cl_reviewed,
)
from src.common.constants import (
    PullStatus,
    GERRIT_DEDUPE_REVIEWED_KEY,
)
from src.common.logger import get_logger

logger = get_logger()


def _store_comment_event(payload: dict, redis_client) -> None:
    """
    Handle a comment-added Pub/Sub event: increment cl_reviewed for the commenter,
    but do NOT bump cl_under_review or other status counters.
    Ensures idempotency via a per‐change, per‐user Redis SET.
    """
    change = payload.get("change", {})
    commenter = payload.get("author", {}).get("username")
    owner = change.get("owner", {}).get("username")
    if not commenter or commenter == owner:
        return

    project = change.get("project")
    bucket = compute_buckets(change.get("created", ""))
    change_number = change.get("_number") or change.get("number")
    dedupe_key = GERRIT_DEDUPE_REVIEWED_KEY.format(change_number=change_number)

    added = redis_client.sadd(dedupe_key, commenter)
    if added == 0:
        return

    pipe = redis_client.pipeline()
    bump_cl_reviewed(pipe, commenter, project, bucket)

    pipe.expire(dedupe_key, 60 * 60 * 24 * 90)
    pipe.execute()


def store_payload(payload: dict):
    """
    Stores a Gerrit Pub/Sub payload into Redis counters.

    - For non-comment events, delegates to `store_change` (which handles status, LOC, under-review, etc).
    - For "comment-added" events, only increments cl_reviewed (once per user/change), skipping cl_under_review.

    Args:
        payload (dict): The raw Pub/Sub message data, must include:
            - "type": e.g. "comment-added" or "change-merged" etc.
            - "change": Gerrit change dict (with owner, number, project, created).
            - For comment events: top-level "author" field with "username".
    Raises:
        ValueError: if Redis client is unavailable.
    """
    event_type = payload.get("type")
    change = payload.get("change", {})

    redis_client = RedisClientFactory().create_redis_client()
    if not redis_client:
        raise ValueError("Redis client not created.")

    if event_type == "comment-added":
        _store_comment_event(payload, redis_client)
    else:
        store_change(change)


def _process_message(message):
    """
    Process a single Pub/Sub message.

    - Decodes the message data from UTF-8 JSON.
    - Dispatches the resulting payload to `store_payload`.
    - Acknowledges the message on success.
    - Logs and negatively acknowledges the message on failure.

    Args:
        message: A Pub/Sub message object, expected to have:
            - .data (bytes): the raw JSON payload
            - .ack(): method to acknowledge successful processing
            - .nack(): method to signal processing failure
    """
    try:
        payload = json.loads(message.data.decode("utf-8"))
        store_payload(payload)
        message.ack()
    except Exception as err:
        logger.error(
            "[pull_gerrit] failed to process message %s: %s",
            getattr(message, "message_id", "<no-id>"),
            err,
            exc_info=True,
        )
        message.nack()


def pull_gerrit(project_id: str, subscription_id: str):
    """
    Start pulling Gerrit Pub/Sub messages for the given project and subscription,
    processing each change synchronously via `store_change`.

    Args:
        project_id (str): Google Cloud project ID (non-empty).
        subscription_id (str): Pub/Sub subscription ID (non-empty).

    Raises:
        ValueError: If either `project_id` or `subscription_id` is empty.
    """
    if not project_id:
        raise ValueError("project_id must be a non-empty string")
    if not subscription_id:
        raise ValueError("subscription_id must be a non-empty string")

    puller = PubSubPuller(project_id, subscription_id)

    puller.start_pulling_messages(_process_message)

    status = puller.check_pulling_messages_status()
    if status.task_status != PullStatus.RUNNING.code:
        logger.error(
            "Failed to start Gerrit pull for subscription %s: %s",
            subscription_id,
            status.message,
        )
        raise RuntimeError(f"Unable to start gerrit puller: {status.message}")

    logger.info(
        "Started gerrit pull for subscription %s: %s",
        subscription_id,
        status.task_status,
    )
