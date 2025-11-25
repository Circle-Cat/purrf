import unittest
from unittest.mock import MagicMock, call  # Import call for multiple assertions
from backend.consumers.gerrit_processor_service import GerritProcessorService
from backend.common.constants import (
    PullStatus,  # Not used in the provided test, but kept for context
    GERRIT_DEDUPE_REVIEWED_KEY,
    GERRIT_CL_REVIEWED_FIELD,
    GerritChangeStatus,
    THREE_MONTHS_IN_SECONDS,
    GERRIT_STATS_PROJECT_BUCKET_KEY,
    GERRIT_STATS_BUCKET_KEY,  # New: Import global stats key
    GERRIT_UNMERGED_CL_KEY_BY_PROJECT,  # Existing, but good to be explicit
    GERRIT_UNMERGED_CL_KEY_GLOBAL,  # New: Import global unmerged CL key
    GERRIT_STATUS_TO_FIELD_TEMPLATE,  # New: Import for change_merged
    GERRIT_LOC_MERGED_FIELD,  # New: Import for change_merged
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
        self.mock_redis = MagicMock()
        self.mock_puller_factory = MagicMock()
        self.mock_retry = MagicMock()
        self.mock_date_util = MagicMock()
        self.mock_gerrit_client = MagicMock()

        self.service = GerritProcessorService(
            logger=self.mock_logger,
            redis_client=self.mock_redis,
            pubsub_puller_factory=self.mock_puller_factory,
            retry_utils=self.mock_retry,
            date_time_util=self.mock_date_util,
            gerrit_client=self.mock_gerrit_client,
        )

        self.mock_retry.get_retry_on_transient.side_effect = lambda func: func()

        # Preset date utility to return a fixed weekly bucket for assertion
        self.bucket_value = "2025-W20"
        self.mock_date_util.compute_buckets_weekly.return_value = self.bucket_value

        self.mock_project_value = "experiment"

    def test_patchset_created_new_cl(self):
        """Test real-format first patchset event to verify status tracking logic for project-specific and global keys"""
        payload = {
            "type": "patchset-created",
            "patchSet": {"number": 1, "sizeInsertions": 14},
            "change": {
                "number": 7043,
                "project": self.mock_project_value,
                "owner": {"username": "bob"},
                "status": "NEW",
                "createdOn": 1761278745,
            },
            "eventCreatedOn": 1761278745,
        }

        self.service.store_payload(payload)

        # Assert project-specific key
        expected_key_project = GERRIT_UNMERGED_CL_KEY_BY_PROJECT.format(
            ldap="bob",
            project=self.mock_project_value,
            cl_status=GerritChangeStatus.NEW.value,
        )
        # Assert global key
        expected_key_global = GERRIT_UNMERGED_CL_KEY_GLOBAL.format(
            ldap="bob", cl_status=GerritChangeStatus.NEW.value
        )

        mock_pipeline = self.mock_redis.pipeline.return_value

        mock_pipeline.zadd.assert_has_calls(
            [
                call(expected_key_project, {7043: 1761278745}),
                call(expected_key_global, {7043: 1761278745}),
            ],
            any_order=True,
        )
        mock_pipeline.execute.assert_called_once()  # Ensure pipeline was executed

    def test_comment_added_by_human(self):
        """Test real-format human comment event to verify deduplication and statistics logic for project-specific and global keys"""
        payload = {
            "type": "comment-added",
            "author": {"username": "alice"},  # Not owner/bot
            "change": {
                "number": 7043,
                "project": self.mock_project_value,
                "owner": {"username": "bob"},
            },
            "eventCreatedOn": 1761279121,
            "comment": "Patch Set 1: LGTM+1",
        }

        # Mock Redis deduplication check: first comment (not in set)
        self.mock_redis.sismember.return_value = False

        mock_pipeline = MagicMock()
        self.mock_redis.pipeline.return_value = mock_pipeline

        self.service.store_payload(payload)

        # Check deduplication key
        dedupe_key = GERRIT_DEDUPE_REVIEWED_KEY.format(change_number=7043)
        self.mock_redis.sismember.assert_called_once_with(dedupe_key, "alice")

        # Assert project-specific stats key generation and increment execution
        stats_key_project = GERRIT_STATS_PROJECT_BUCKET_KEY.format(
            ldap="alice", project=self.mock_project_value, bucket=self.bucket_value
        )
        mock_pipeline.hincrby.assert_any_call(
            stats_key_project, GERRIT_CL_REVIEWED_FIELD, 1
        )

        # Assert global stats key generation and increment execution
        stats_key_global = GERRIT_STATS_BUCKET_KEY.format(
            ldap="alice", bucket=self.bucket_value
        )
        mock_pipeline.hincrby.assert_any_call(
            stats_key_global, GERRIT_CL_REVIEWED_FIELD, 1
        )

        mock_pipeline.sadd.assert_called_once_with(dedupe_key, "alice")
        mock_pipeline.expire.assert_called_once_with(
            dedupe_key, THREE_MONTHS_IN_SECONDS
        )
        mock_pipeline.execute.assert_called_once()

    def test_comment_added_by_bot(self):
        """Test bot comment event (e.g., Presubmit) to verify it's skipped"""
        payload = {
            "type": "comment-added",
            "author": {"username": "CatBot"},  # Bot account
            "change": {"number": 7044, "owner": {"username": "bob"}},
            "comment": "Patch Set 1: Verified+1",
        }

        # Execute processing
        self.service.store_payload(payload)

        # Verify: No Redis operations executed (bot comments are skipped)
        self.mock_redis.sismember.assert_not_called()
        self.mock_redis.pipeline.assert_not_called()

    def test_change_merged(self):
        """Test real-format merge event to verify statistics and status cleanup logic for project-specific and global keys"""

        payload = {
            "type": "change-merged",
            "eventCreatedOn": 1761280203,
            "change": {
                "number": 7043,
                "project": self.mock_project_value,
                "owner": {"username": "bob"},
            },
            "patchSet": {"sizeInsertions": 18},  # Insertions in merged patchset
        }

        mock_pipeline = MagicMock()
        self.mock_redis.pipeline.return_value = mock_pipeline
        self.mock_gerrit_client.get_change_by_change_id.return_value = {
            "insertions": 16
        }

        self.service.store_payload(payload)

        # Merge statistics updated (LOC and merge count) for project-specific
        stats_key_project = GERRIT_STATS_PROJECT_BUCKET_KEY.format(
            ldap="bob", project=self.mock_project_value, bucket=self.bucket_value
        )
        mock_pipeline.hincrby.assert_any_call(
            stats_key_project, GERRIT_LOC_MERGED_FIELD, 16
        )
        mock_pipeline.hincrby.assert_any_call(
            stats_key_project,
            GERRIT_STATUS_TO_FIELD_TEMPLATE.format(
                status=GerritChangeStatus.MERGED.value
            ),
            1,
        )

        # Merge statistics updated (LOC and merge count) for global
        stats_key_global = GERRIT_STATS_BUCKET_KEY.format(
            ldap="bob", bucket=self.bucket_value
        )
        mock_pipeline.hincrby.assert_any_call(
            stats_key_global, GERRIT_LOC_MERGED_FIELD, 16
        )
        mock_pipeline.hincrby.assert_any_call(
            stats_key_global,
            GERRIT_STATUS_TO_FIELD_TEMPLATE.format(
                status=GerritChangeStatus.MERGED.value
            ),
            1,
        )

        # Removed from NEW status set for project-specific
        new_status_key_project = GERRIT_UNMERGED_CL_KEY_BY_PROJECT.format(
            ldap="bob",
            project=self.mock_project_value,
            cl_status=GerritChangeStatus.NEW.value,
        )
        mock_pipeline.zrem.assert_any_call(new_status_key_project, 7043)

        # Removed from NEW status set for global
        new_status_key_global = GERRIT_UNMERGED_CL_KEY_GLOBAL.format(
            ldap="bob", cl_status=GerritChangeStatus.NEW.value
        )
        mock_pipeline.zrem.assert_any_call(new_status_key_global, 7043)

        # Ensure pipeline execution
        mock_pipeline.execute.assert_called_once()

    def test_change_abandoned(self):
        """Test real-format abandon event to verify status migration logic for project-specific and global keys"""
        payload = {
            "type": "change-abandoned",
            "eventCreatedOn": 1761280743,
            "change": {
                "number": 7041,
                "project": self.mock_project_value,
                "owner": {"username": "bob"},
                "status": "ABANDONED",
            },
            "reason": "test abandon",
        }

        mock_pipeline = MagicMock()
        self.mock_redis.pipeline.return_value = mock_pipeline

        self.service.store_payload(payload)

        # Verify: Migrated from NEW to ABANDONED set for project-specific
        new_key_project = GERRIT_UNMERGED_CL_KEY_BY_PROJECT.format(
            ldap="bob",
            project=self.mock_project_value,
            cl_status=GerritChangeStatus.NEW.value,
        )
        abandoned_key_project = GERRIT_UNMERGED_CL_KEY_BY_PROJECT.format(
            ldap="bob",
            project=self.mock_project_value,
            cl_status=GerritChangeStatus.ABANDONED.value,
        )
        mock_pipeline.zadd.assert_any_call(abandoned_key_project, {7041: 1761280743})
        mock_pipeline.zrem.assert_any_call(new_key_project, 7041)

        # Verify: Migrated from NEW to ABANDONED set for global
        new_key_global = GERRIT_UNMERGED_CL_KEY_GLOBAL.format(
            ldap="bob", cl_status=GerritChangeStatus.NEW.value
        )
        abandoned_key_global = GERRIT_UNMERGED_CL_KEY_GLOBAL.format(
            ldap="bob", cl_status=GerritChangeStatus.ABANDONED.value
        )
        mock_pipeline.zadd.assert_any_call(abandoned_key_global, {7041: 1761280743})
        mock_pipeline.zrem.assert_any_call(new_key_global, 7041)

        mock_pipeline.execute.assert_called_once()

    def test_change_restored(self):
        """Test real-format restore event to verify status migration and reviewer refresh for project-specific and global keys"""
        payload = {
            "type": "change-restored",
            "eventCreatedOn": 1761280835,
            "change": {
                "number": 7041,
                "project": self.mock_project_value,
                "owner": {"username": "bob"},
                "status": "NEW",
                "createdOn": 1761280000,
            },
        }

        mock_pipeline = MagicMock()
        self.mock_redis.pipeline.return_value = mock_pipeline

        self.service.store_payload(payload)

        # Status migrated from ABANDONED to NEW for project-specific
        new_key_project = GERRIT_UNMERGED_CL_KEY_BY_PROJECT.format(
            ldap="bob",
            project=self.mock_project_value,
            cl_status=GerritChangeStatus.NEW.value,
        )
        abandoned_key_project = GERRIT_UNMERGED_CL_KEY_BY_PROJECT.format(
            ldap="bob",
            project=self.mock_project_value,
            cl_status=GerritChangeStatus.ABANDONED.value,
        )
        mock_pipeline.zadd.assert_any_call(new_key_project, {7041: 1761280000})
        mock_pipeline.zrem.assert_any_call(abandoned_key_project, 7041)

        # Status migrated from ABANDONED to NEW for global
        new_key_global = GERRIT_UNMERGED_CL_KEY_GLOBAL.format(
            ldap="bob", cl_status=GerritChangeStatus.NEW.value
        )
        abandoned_key_global = GERRIT_UNMERGED_CL_KEY_GLOBAL.format(
            ldap="bob", cl_status=GerritChangeStatus.ABANDONED.value
        )
        mock_pipeline.zadd.assert_any_call(new_key_global, {7041: 1761280000})
        mock_pipeline.zrem.assert_any_call(abandoned_key_global, 7041)
        mock_pipeline.execute.assert_called_once()

    def test_duplicate_comment(self):
        """Test multiple comments from the same user on the same CL to verify deduplication"""
        payload = {
            "type": "comment-added",
            "author": {"username": "alice"},
            "change": {
                "number": 7043,
                "owner": {"username": "bob"},
                "project": self.mock_project_value,
            },
            "eventCreatedOn": 1761279121,  # Added timestamp for compute_buckets_weekly to be called
        }

        # Mock deduplication check: already reviewed
        self.mock_redis.sismember.return_value = True

        self.service.store_payload(payload)

        # Verify: No statistics update (duplicate count skipped)
        self.mock_redis.pipeline.assert_not_called()
        self.mock_redis.sismember.assert_called_once()  # sismember is still called to check for duplication


class TestPullGerrit(unittest.TestCase):
    def setUp(self):
        self.mock_logger = MagicMock()
        self.mock_redis = MagicMock()
        self.mock_puller_factory = MagicMock()
        self.mock_retry = MagicMock()
        self.mock_date_util = MagicMock()
        self.mock_gerrit_client = MagicMock()

        self.service = GerritProcessorService(
            logger=self.mock_logger,
            redis_client=self.mock_redis,
            pubsub_puller_factory=self.mock_puller_factory,
            retry_utils=self.mock_retry,
            date_time_util=self.mock_date_util,
            gerrit_client=self.mock_gerrit_client,
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
