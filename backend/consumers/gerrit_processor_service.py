import json
from backend.common.constants import (
    GERRIT_DEDUPE_REVIEWED_KEY,
)


class GerritProcessorService:
    def __init__(
        self,
        logger,
        redis_client,
        gerrit_sync_service,
        pubsub_puller_factory,
        retry_utils=None,
    ):
        """
        Args:
            logger: Logger instance.
            redis_client: Redis client instance.
            gerrit_sync_service: GerritSyncService instance (handles storing changes).
            pubsub_puller_factory: Factory that creates PubSubPuller(project_id, subscription_id).
            retry_utils: Optional retry utility.
        """
        self.logger = logger
        self.redis_client = redis_client
        self.gerrit_sync_service = gerrit_sync_service
        self.pubsub_puller_factory = pubsub_puller_factory
        self.retry_utils = retry_utils

    def _store_comment_event(self, payload: dict) -> None:
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
        bucket = self.gerrit_sync_service.compute_buckets(change.get("created", ""))
        change_number = change.get("_number") or change.get("number")
        dedupe_key = GERRIT_DEDUPE_REVIEWED_KEY.format(change_number=change_number)

        added = self.redis_client.sadd(dedupe_key, commenter)
        if added == 0:
            return

        pipe = self.redis_client.pipeline()
        self.gerrit_sync_service.bump_cl_reviewed(pipe, commenter, project, bucket)

        pipe.expire(dedupe_key, 60 * 60 * 24 * 90)
        self.retry_utils.get_retry_on_transient(pipe.execute)

    def store_payload(self, payload: dict):
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

        if event_type == "comment-added":
            self._store_comment_event(payload)
        else:
            self.gerrit_sync_service.store_change(change)

    def _process_message(self, message):
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
            self.store_payload(payload)
            message.ack()
        except Exception as err:
            self.logger.error(
                "[pull_gerrit] failed to process message %s: %s",
                getattr(message, "message_id", "<no-id>"),
                err,
                exc_info=True,
            )
            message.nack()

    def pull_gerrit(self, project_id: str, subscription_id: str):
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

        puller = self.pubsub_puller_factory.get_puller_instance(
            project_id, subscription_id
        )

        puller.start_pulling_messages(self._process_message)
