import unittest
from unittest.mock import MagicMock
from backend.consumers.gerrit_processor_service import GerritProcessorService
from backend.common.constants import (
    PullStatus,
    GERRIT_DEDUPE_REVIEWED_KEY,
)
from dataclasses import dataclass


@dataclass
class PullStatusResponse:
    subscription_id: str
    task_status: str
    message: str
    timestamp: str | None


class TestStorePayload(unittest.TestCase):
    def setUp(self):
        self.mock_logger = MagicMock()
        self.mock_redis_client = MagicMock()
        self.mock_gerrit_sync_service = MagicMock()
        self.mock_pubsub_puller_factory = MagicMock()
        self.mock_retry_utils = MagicMock()
        self.service = GerritProcessorService(
            logger=self.mock_logger,
            redis_client=self.mock_redis_client,
            gerrit_sync_service=self.mock_gerrit_sync_service,
            pubsub_puller_factory=self.mock_pubsub_puller_factory,
            retry_utils=self.mock_retry_utils,
        )

    def test_non_comment_delegates_to_store_change(self):
        payload = {"type": "change-merged", "change": {"foo": "bar"}}
        self.service.store_payload(payload)
        self.mock_gerrit_sync_service.store_change.assert_called_once_with({
            "foo": "bar"
        })

    def test_comment_added_increments_review_counts(self):
        fake_pipeline = MagicMock()
        self.mock_redis_client.pipeline.return_value = fake_pipeline
        self.mock_redis_client.sadd.return_value = 1
        self.mock_gerrit_sync_service.compute_buckets.return_value = (
            "2025-07-01_2025-07-31"
        )

        commenter = "alice"
        owner = "bob"
        payload = {
            "type": "comment-added",
            "author": {"username": commenter},
            "change": {
                "owner": {"username": owner},
                "project": "proj",
                "created": "2025-07-18 22:00:00.000000",
                "_number": 123,
            },
        }

        self.service.store_payload(payload)

        dedupe_key = GERRIT_DEDUPE_REVIEWED_KEY.format(change_number=123)
        self.mock_redis_client.sadd.assert_called_once_with(dedupe_key, commenter)
        fake_pipeline.expire.assert_called_once_with(dedupe_key, 60 * 60 * 24 * 90)

        self.assertTrue(self.mock_retry_utils.get_retry_on_transient.called)

        self.mock_gerrit_sync_service.bump_cl_reviewed.assert_called_once_with(
            fake_pipeline, commenter, "proj", "2025-07-01_2025-07-31"
        )

    def test_comment_added_idempotent_on_repeat(self):
        fake_pipeline = MagicMock()
        self.mock_redis_client.pipeline.return_value = fake_pipeline
        self.mock_redis_client.sadd.return_value = 0
        self.mock_gerrit_sync_service.compute_buckets.return_value = (
            "2025-07-01_2025-07-31"
        )

        payload = {
            "type": "comment-added",
            "author": {"username": "alice"},
            "change": {
                "owner": {"username": "bob"},
                "project": "proj",
                "created": "2025-07-18 22:00:00.000000",
                "_number": 123,
            },
        }

        self.service.store_payload(payload)

        fake_pipeline.hincrby.assert_not_called()
        fake_pipeline.expire.assert_not_called()
        fake_pipeline.execute.assert_not_called()


class TestPullGerrit(unittest.TestCase):
    def setUp(self):
        self.mock_logger = MagicMock()
        self.mock_redis = MagicMock()
        self.mock_gerrit_sync = MagicMock()
        self.mock_puller_factory = MagicMock()
        self.service = GerritProcessorService(
            logger=self.mock_logger,
            redis_client=self.mock_redis,
            gerrit_sync_service=self.mock_gerrit_sync,
            pubsub_puller_factory=self.mock_puller_factory,
        )

        self.fake_status = PullStatusResponse(
            subscription_id="test-sub",
            task_status=PullStatus.RUNNING.code,
            message="Puller started",
            timestamp="2025-07-01T00:00:00Z",
        )

    def test_pull_gerrit_success(self):
        mock_puller = MagicMock()
        self.mock_puller_factory.get_puller_instance.return_value = mock_puller

        result = self.service.pull_gerrit(project_id="proj1", subscription_id="sub1")

        mock_puller.start_pulling_messages.assert_called_once()
        self.assertIsNone(result)

    def test_pull_gerrit_missing_project(self):
        with self.assertRaises(ValueError) as cm:
            self.service.pull_gerrit(project_id="", subscription_id="sub1")
        self.assertIn("project_id", str(cm.exception))

    def test_pull_gerrit_missing_subscription(self):
        with self.assertRaises(ValueError) as cm:
            self.service.pull_gerrit(project_id="proj1", subscription_id="")
        self.assertIn("subscription_id", str(cm.exception))


if __name__ == "__main__":
    unittest.main()
