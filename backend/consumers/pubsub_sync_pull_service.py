import json
import os
import time

from backend.common.constants import (
    ALL_GOOGLE_CHAT_EVENT_TYPES,
    EXPIRATION_REMINDER_EVENT,
)
from backend.common.environment_constants import (
    PUBSUB_PROJECT_ID,
    MICROSOFT_SUBSCRIPTION_ID,
    GOOGLE_CHAT_SUBSCRIPTION_ID,
    GERRIT_SUBSCRIPTION_ID,
)

# Idempotency note: messages may be redelivered if `acknowledge()` itself fails
# after `process_fn` succeeds, or if a sibling message's nack causes an early
# break. All registered processors (store_payload, process_event,
# sync_near_real_time_message_to_redis) MUST be idempotent on retry.


class PubSubSyncPullService:
    """
    Synchronous pull from Pub/Sub subscriptions.
    Loops until the subscription is drained, processing and acknowledging
    each batch before pulling the next.
    """

    def __init__(
        self,
        logger,
        subscriber_client,
        microsoft_chat_message_util,
        google_chat_processor_service,
        gerrit_processor_service,
        asyncio_event_loop_manager,
    ):
        self.logger = logger
        self.subscriber_client = subscriber_client
        self.microsoft_chat_message_util = microsoft_chat_message_util
        self.google_chat_processor_service = google_chat_processor_service
        self.gerrit_processor_service = gerrit_processor_service
        self.asyncio_event_loop_manager = asyncio_event_loop_manager

    def _pull_and_process(
        self,
        project_id,
        subscription_id,
        process_fn,
        max_messages=10,
        max_iterations=100,
        deadline_seconds=3000,
    ):
        """
        Pull messages from a subscription and process them.

        Args:
            project_id: GCP project ID.
            subscription_id: Pub/Sub subscription ID.
            process_fn: Callable that takes (data_bytes, attributes) and processes one message.
                        Should raise on failure (message will not be acked).
            max_messages: Max messages to pull per call.
            max_iterations: Hard cap on pull batches to prevent unbounded loops on
                            high-traffic subscriptions. Remaining messages are picked
                            up by the next cron tick. At the defaults (max_messages=10,
                            max_iterations=100), a single run processes at most 1000
                            messages. Adjust both together if traffic grows.
            deadline_seconds: Wall-clock budget for this call. Defaults to 50 minutes
                              so an hourly cron tick cannot overrun the next one even
                              if pull() stalls under a regional incident.

        Returns:
            dict with processed/failed counts.
        """
        subscription_path = self.subscriber_client.subscription_path(
            project_id, subscription_id
        )

        # Sets keyed by message_id so a poison pill that's redelivered N times
        # within the loop doesn't get counted N times. Final "failed" excludes
        # any message that eventually succeeded on retry within the same run.
        processed_ids = set()
        failed_ids = set()
        iterations = 0
        deadline = time.monotonic() + deadline_seconds

        while iterations < max_iterations:
            if time.monotonic() >= deadline:
                self.logger.warning(
                    "[PubSubSyncPullService] Hit deadline=%ds for %s/%s; remaining messages will be picked up next run.",
                    deadline_seconds,
                    project_id,
                    subscription_id,
                )
                break
            iterations += 1
            try:
                response = self.subscriber_client.pull(
                    subscription=subscription_path,
                    max_messages=max_messages,
                    timeout=60,
                )
            except Exception as e:
                self.logger.error(
                    "[PubSubSyncPullService] Pull failed for %s/%s: %s",
                    project_id,
                    subscription_id,
                    e,
                    exc_info=True,
                )
                break

            if not response.received_messages:
                self.logger.debug(
                    "[PubSubSyncPullService] No messages in %s/%s",
                    project_id,
                    subscription_id,
                )
                break

            ack_ids = []
            nack_ids = []
            for received in response.received_messages:
                msg = received.message
                try:
                    process_fn(msg.data, dict(msg.attributes))
                    ack_ids.append(received.ack_id)
                    processed_ids.add(msg.message_id)
                except Exception as e:
                    self.logger.error(
                        "[PubSubSyncPullService] Failed to process message %s in %s/%s: %s",
                        msg.message_id,
                        project_id,
                        subscription_id,
                        e,
                        exc_info=True,
                    )
                    nack_ids.append(received.ack_id)
                    failed_ids.add(msg.message_id)

            if ack_ids:
                self.subscriber_client.acknowledge(
                    subscription=subscription_path, ack_ids=ack_ids
                )
            if nack_ids:
                # Deadline=0 triggers immediate redelivery. Poison pills are
                # handled by the subscription's Dead Letter Topic configuration.
                self.subscriber_client.modify_ack_deadline(
                    subscription=subscription_path,
                    ack_ids=nack_ids,
                    ack_deadline_seconds=0,
                )
        else:
            # while/else fires only when the loop condition becomes false (no break).
            # That's exactly the iteration-cap case; deadline/empty/error all break.
            self.logger.warning(
                "[PubSubSyncPullService] Hit max_iterations=%d for %s/%s; remaining messages will be picked up next run.",
                max_iterations,
                project_id,
                subscription_id,
            )

        processed = len(processed_ids)
        failed = len(failed_ids - processed_ids)
        self.logger.info(
            "[PubSubSyncPullService] Sync pull %s/%s: processed=%d, failed=%d, iterations=%d",
            project_id,
            subscription_id,
            processed,
            failed,
            iterations,
        )
        return {"processed": processed, "failed": failed}

    def sync_pull_microsoft(
        self, project_id, subscription_id, max_messages=10, max_iterations=100
    ):
        """Sync pull and process Microsoft Teams messages."""

        def process_fn(data_bytes, attributes):
            data = json.loads(data_bytes.decode("utf-8"))
            change_type = data.get("changeType")
            resource = data.get("resource")
            self.asyncio_event_loop_manager.run_async_in_background_loop(
                self.microsoft_chat_message_util.sync_near_real_time_message_to_redis(
                    change_type, resource
                ),
                timeout=60,
            )

        return self._pull_and_process(
            project_id, subscription_id, process_fn, max_messages, max_iterations
        )

    def sync_pull_google_chat(
        self, project_id, subscription_id, max_messages=10, max_iterations=100
    ):
        """Sync pull and process Google Chat messages."""

        def process_fn(data_bytes, attributes):
            # Pre-filter unsupported events: returning normally → message is
            # acked. Otherwise the sync loop would nack-and-redeliver this
            # poison pill on every iteration up to max_iterations.
            message_type_full = attributes.get("ce-type")
            if (
                EXPIRATION_REMINDER_EVENT != message_type_full
                and message_type_full not in ALL_GOOGLE_CHAT_EVENT_TYPES
            ):
                self.logger.warning(
                    "[PubSubSyncPullService] Dropping unsupported Google Chat event: %s",
                    message_type_full,
                )
                return
            data = json.loads(data_bytes.decode("utf-8"))
            self.google_chat_processor_service.process_event(data, attributes)

        return self._pull_and_process(
            project_id, subscription_id, process_fn, max_messages, max_iterations
        )

    def sync_pull_gerrit(
        self, project_id, subscription_id, max_messages=10, max_iterations=100
    ):
        """Sync pull and process Gerrit events."""

        def process_fn(data_bytes, attributes):
            payload = json.loads(data_bytes.decode("utf-8"))
            self.gerrit_processor_service.store_payload(payload)

        return self._pull_and_process(
            project_id, subscription_id, process_fn, max_messages, max_iterations
        )

    def sync_pull_all(self, max_messages=10, max_iterations=100):
        """
        Pull and process messages from all three subscriptions.
        Uses environment variables for project_id and subscription_ids.

        Returns:
            dict with results per subscription.
        """
        project_id = os.getenv(PUBSUB_PROJECT_ID)
        if not project_id:
            self.logger.debug(
                "[PubSubSyncPullService] PUBSUB_PROJECT_ID not set, skipping sync pull"
            )
            return {}

        results = {}

        # Each subscription is isolated: an unexpected failure in one (e.g. a
        # setup-time error before _pull_and_process can catch it) must not
        # starve the remaining subscriptions.
        sources = (
            ("microsoft", MICROSOFT_SUBSCRIPTION_ID, self.sync_pull_microsoft),
            ("google_chat", GOOGLE_CHAT_SUBSCRIPTION_ID, self.sync_pull_google_chat),
            ("gerrit", GERRIT_SUBSCRIPTION_ID, self.sync_pull_gerrit),
        )
        for name, env_var, sync_fn in sources:
            sub = os.getenv(env_var)
            if not sub:
                continue
            try:
                results[name] = sync_fn(project_id, sub, max_messages, max_iterations)
            except Exception as e:
                self.logger.error(
                    "[PubSubSyncPullService] %s sync pull aborted: %s",
                    name,
                    e,
                    exc_info=True,
                )
                results[name] = {"processed": 0, "failed": 0}

        return results
