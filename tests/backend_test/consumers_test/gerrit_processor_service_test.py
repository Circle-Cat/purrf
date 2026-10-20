import unittest
from unittest.mock import MagicMock, call  # Import call for multiple assertions
from backend.consumers.gerrit_processor_service import GerritProcessorService
from backend.common.constants import (
    GERRIT_DEDUPE_MERGED_KEY,
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


class TestStorePayload(unittest.TestCase):
    def setUp(self):
        self.mock_logger = MagicMock()
        self.mock_redis = MagicMock()
        self.mock_retry = MagicMock()
        self.mock_date_util = MagicMock()
        self.mock_gerrit_client = MagicMock()

        self.service = GerritProcessorService(
            logger=self.mock_logger,
            redis_client=self.mock_redis,
            retry_utils=self.mock_retry,
            date_time_util=self.mock_date_util,
            gerrit_client=self.mock_gerrit_client,
        )

        self.mock_retry.get_retry_on_transient.side_effect = lambda func: func()
        self.mock_retry.execute_pipeline.side_effect = (
            lambda pipeline: pipeline.execute()
        )

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

        # First comment from this user on this CL: SADD adds a member
        self.mock_redis.sadd.return_value = 1

        mock_pipeline = MagicMock()
        self.mock_redis.pipeline.return_value = mock_pipeline

        self.service.store_payload(payload)

        # The dedupe set is claimed atomically, before anything is counted
        dedupe_key = GERRIT_DEDUPE_REVIEWED_KEY.format(change_number=7043)
        self.mock_redis.sadd.assert_called_once_with(dedupe_key, "alice")
        self.mock_redis.sismember.assert_not_called()

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

        mock_pipeline.sadd.assert_not_called()
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
        self.mock_redis.sadd.assert_not_called()
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

        # Already in the dedupe set: SADD adds nothing
        self.mock_redis.sadd.return_value = 0

        self.service.store_payload(payload)

        # Verify: No statistics update (duplicate count skipped)
        self.mock_redis.pipeline.assert_not_called()
        self.mock_redis.sadd.assert_called_once()

    def test_comment_whose_count_fails_releases_its_claim(self):
        """A failed write must leave the redelivery free to count it."""
        payload = {
            "type": "comment-added",
            "author": {"username": "alice"},
            "change": {
                "number": 7043,
                "owner": {"username": "bob"},
                "project": self.mock_project_value,
            },
            "eventCreatedOn": 1761279121,
        }
        self.mock_redis.sadd.return_value = 1
        self.mock_redis.pipeline.return_value.execute.side_effect = ConnectionError()

        with self.assertRaises(ConnectionError):
            self.service.store_payload(payload)

        dedupe_key = GERRIT_DEDUPE_REVIEWED_KEY.format(change_number=7043)
        self.mock_redis.srem.assert_called_once_with(dedupe_key, "alice")

    def _merged_payload(self):
        return {
            "type": "change-merged",
            "eventCreatedOn": 1761280203,
            "change": {
                "number": 7043,
                "project": self.mock_project_value,
                "owner": {"username": "bob"},
            },
        }

    def test_change_merged_claims_the_change_before_counting(self):
        self.mock_redis.set.return_value = True
        self.mock_gerrit_client.get_change_by_change_id.return_value = {
            "insertions": 16
        }

        self.service.store_payload(self._merged_payload())

        self.mock_redis.set.assert_called_once_with(
            GERRIT_DEDUPE_MERGED_KEY.format(change_number=7043),
            1,
            nx=True,
            ex=THREE_MONTHS_IN_SECONDS,
        )
        self.mock_redis.pipeline.return_value.execute.assert_called_once()

    def test_redelivered_change_merged_is_counted_once(self):
        """Pub/Sub push is at-least-once; a second copy must not add to the stats."""
        self.mock_redis.set.return_value = None
        self.mock_gerrit_client.get_change_by_change_id.return_value = {
            "insertions": 16
        }

        self.service.store_payload(self._merged_payload())

        self.mock_redis.pipeline.assert_not_called()

    def test_change_merged_whose_count_fails_releases_its_claim(self):
        self.mock_redis.set.return_value = True
        self.mock_gerrit_client.get_change_by_change_id.return_value = {
            "insertions": 16
        }
        self.mock_redis.pipeline.return_value.execute.side_effect = ConnectionError()

        with self.assertRaises(ConnectionError):
            self.service.store_payload(self._merged_payload())

        self.mock_redis.delete.assert_called_once_with(
            GERRIT_DEDUPE_MERGED_KEY.format(change_number=7043)
        )


if __name__ == "__main__":
    unittest.main()
