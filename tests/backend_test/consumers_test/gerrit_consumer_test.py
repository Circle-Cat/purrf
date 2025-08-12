import unittest
from unittest.mock import patch, MagicMock
from backend.consumers.gerrit_consumer import (
    store_payload,
    pull_gerrit,
)
from backend.consumers.pubsub_puller import PullStatusResponse
from backend.common.constants import (
    PullStatus,
    GERRIT_CL_REVIEWED_FIELD,
    GERRIT_STATS_ALL_TIME_KEY,
    GERRIT_STATS_MONTHLY_BUCKET_KEY,
    GERRIT_STATS_PROJECT_BUCKET_KEY,
    GERRIT_DEDUPE_REVIEWED_KEY,
)


class TestStorePayload(unittest.TestCase):
    @patch("backend.consumers.gerrit_consumer.store_change")
    @patch("backend.consumers.gerrit_consumer.RedisClientFactory")
    def test_non_comment_delegates_to_store_change(
        self, mock_redis_factory, mock_store_change
    ):
        fake_redis = MagicMock()
        mock_redis_factory.return_value.create_redis_client.return_value = fake_redis
        payload = {"type": "change-merged", "change": {"foo": "bar"}}

        store_payload(payload)

        mock_store_change.assert_called_once_with({"foo": "bar"})

    @patch("backend.consumers.gerrit_consumer.compute_buckets")
    @patch("backend.consumers.gerrit_consumer.RedisClientFactory")
    def test_comment_added_increments_review_counts(
        self, mock_redis_factory, mock_compute_buckets
    ):
        fake_redis = MagicMock()
        fake_pipeline = MagicMock()
        fake_redis.pipeline.return_value = fake_pipeline
        fake_redis.sadd.return_value = 1

        mock_redis_factory.return_value.create_redis_client.return_value = fake_redis
        mock_compute_buckets.return_value = "2025-07-01_2025-07-31"

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

        store_payload(payload)

        dedupe_key = GERRIT_DEDUPE_REVIEWED_KEY.format(change_number=123)
        fake_redis.sadd.assert_called_once_with(dedupe_key, commenter)

        all_key = GERRIT_STATS_ALL_TIME_KEY.format(ldap=commenter)
        month_key = GERRIT_STATS_MONTHLY_BUCKET_KEY.format(
            ldap=commenter, bucket="2025-07-01_2025-07-31"
        )
        proj_key = GERRIT_STATS_PROJECT_BUCKET_KEY.format(
            ldap=commenter, project="proj", bucket="2025-07-01_2025-07-31"
        )

        self.assertEqual(fake_pipeline.hincrby.call_count, 3)
        fake_pipeline.hincrby.assert_any_call(all_key, GERRIT_CL_REVIEWED_FIELD, 1)
        fake_pipeline.hincrby.assert_any_call(month_key, GERRIT_CL_REVIEWED_FIELD, 1)
        fake_pipeline.hincrby.assert_any_call(proj_key, GERRIT_CL_REVIEWED_FIELD, 1)

        fake_pipeline.expire.assert_called_once_with(dedupe_key, 60 * 60 * 24 * 90)
        fake_pipeline.execute.assert_called_once()

    @patch("backend.consumers.gerrit_consumer.compute_buckets")
    @patch("backend.consumers.gerrit_consumer.RedisClientFactory")
    def test_comment_added_idempotent_on_repeat(
        self, mock_redis_factory, mock_compute_buckets
    ):
        fake_redis = MagicMock()
        fake_pipeline = MagicMock()
        fake_redis.pipeline.return_value = fake_pipeline
        fake_redis.sadd.return_value = 0

        mock_redis_factory.return_value.create_redis_client.return_value = fake_redis
        mock_compute_buckets.return_value = "2025-07-01_2025-07-31"

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

        store_payload(payload)

        fake_pipeline.hincrby.assert_not_called()
        fake_pipeline.expire.assert_not_called()
        fake_pipeline.execute.assert_not_called()


class TestPullGerrit(unittest.TestCase):
    def setUp(self):
        self.fake_status = PullStatusResponse(
            subscription_id="test-sub",
            task_status=PullStatus.RUNNING.code,
            message="Puller started",
            timestamp="2025-07-01T00:00:00Z",
        )

    @patch("backend.consumers.gerrit_consumer.PubSubPuller")
    def test_pull_gerrit_success(self, mock_puller_cls):
        mock_puller = MagicMock()
        mock_puller.check_pulling_messages_status.return_value = self.fake_status
        mock_puller_cls.return_value = mock_puller

        result = pull_gerrit(project_id="proj1", subscription_id="sub1")

        mock_puller.start_pulling_messages.assert_called_once()
        mock_puller.check_pulling_messages_status.assert_called_once()
        self.assertIsNone(result)

    def test_pull_gerrit_missing_project(self):
        with self.assertRaises(ValueError) as cm:
            pull_gerrit(project_id="", subscription_id="sub1")
        self.assertIn("project_id", str(cm.exception))

    def test_pull_gerrit_missing_subscription(self):
        with self.assertRaises(ValueError) as cm:
            pull_gerrit(project_id="proj1", subscription_id="")
        self.assertIn("subscription_id", str(cm.exception))


if __name__ == "__main__":
    unittest.main()
