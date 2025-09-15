import unittest
from unittest.mock import MagicMock

from backend.historical_data.gerrit_sync_service import GerritSyncService
from backend.common.constants import (
    GerritChangeStatus,
    GERRIT_UNDER_REVIEW,
    GERRIT_CL_REVIEWED_FIELD,
    GERRIT_LOC_MERGED_FIELD,
    GERRIT_STATUS_TO_FIELD,
    GERRIT_STATS_ALL_TIME_KEY,
    GERRIT_STATS_MONTHLY_BUCKET_KEY,
    GERRIT_STATS_PROJECT_BUCKET_KEY,
    GERRIT_CHANGE_STATUS_KEY,
)


class TestGerritSyncService(unittest.TestCase):
    def setUp(self):
        self.mock_logger = MagicMock()
        self.mock_redis = MagicMock()
        self.mock_pipe = MagicMock()
        self.mock_redis.pipeline.return_value = self.mock_pipe
        self.mock_redis.smembers.return_value = set()
        self.mock_redis.hget.return_value = None

        self.mock_gerrit_client = MagicMock()
        self.mock_retry_utils = MagicMock()
        self.service = GerritSyncService(
            logger=self.mock_logger,
            redis_client=self.mock_redis,
            gerrit_client=self.mock_gerrit_client,
            retry_utils=self.mock_retry_utils,
        )

    def test_fetch_changes_pagination(self):
        fake_pages = [[{"id": 1}, {"id": 2}], [{"id": 3}], []]
        self.mock_gerrit_client.query_changes.side_effect = fake_pages

        result = list(
            self.service.fetch_changes(
                statuses=[GerritChangeStatus.MERGED.value],
                projects=["purrf"],
                max_changes=None,
                page_size=2,
            )
        )
        self.assertEqual(result, [{"id": 1}, {"id": 2}, {"id": 3}])

        self.mock_gerrit_client.query_changes.assert_any_call(
            queries=[f"(status:{GerritChangeStatus.MERGED.value}) project:purrf"],
            limit=2,
            start=0,
            no_limit=False,
            options=[
                "CURRENT_REVISION",
                "DETAILED_LABELS",
                "DETAILED_ACCOUNTS",
                "MESSAGES",
            ],
            allow_incomplete=True,
        )
        self.mock_gerrit_client.query_changes.assert_any_call(
            queries=[f"(status:{GerritChangeStatus.MERGED.value}) project:purrf"],
            limit=2,
            start=2,
            no_limit=False,
            options=[
                "CURRENT_REVISION",
                "DETAILED_LABELS",
                "DETAILED_ACCOUNTS",
                "MESSAGES",
            ],
            allow_incomplete=True,
        )

    def test_compute_buckets(self):
        bucket = self.service.compute_buckets("2025-05-14 13:00:00.000000")
        self.assertEqual(bucket, "2025-05-01_2025-05-31")

    def test_store_change_in_redis(self):
        """Merged change should run dedupe pipeline (no messages) and then status update pipeline."""
        change = {
            "owner": {"username": "alice"},
            "status": GerritChangeStatus.MERGED.value,
            "insertions": 10,
            "project": "projX",
            "created": "2025-05-14 00:00:00.000000",
            "messages": [],
            "_number": 42,
        }

        self.service.store_change(change)

        bucket = self.service.compute_buckets(change["created"])
        expected = [
            (
                GERRIT_STATS_ALL_TIME_KEY.format(ldap="alice"),
                GERRIT_STATUS_TO_FIELD[GerritChangeStatus.MERGED.value],
                1,
            ),
            (
                GERRIT_STATS_ALL_TIME_KEY.format(ldap="alice"),
                GERRIT_LOC_MERGED_FIELD,
                10,
            ),
            (
                GERRIT_STATS_MONTHLY_BUCKET_KEY.format(ldap="alice", bucket=bucket),
                GERRIT_STATUS_TO_FIELD[GerritChangeStatus.MERGED.value],
                1,
            ),
            (
                GERRIT_STATS_MONTHLY_BUCKET_KEY.format(ldap="alice", bucket=bucket),
                GERRIT_LOC_MERGED_FIELD,
                10,
            ),
            (
                GERRIT_STATS_PROJECT_BUCKET_KEY.format(
                    ldap="alice", project="projX", bucket=bucket
                ),
                GERRIT_STATUS_TO_FIELD[GerritChangeStatus.MERGED.value],
                1,
            ),
            (
                GERRIT_STATS_PROJECT_BUCKET_KEY.format(
                    ldap="alice", project="projX", bucket=bucket
                ),
                GERRIT_LOC_MERGED_FIELD,
                10,
            ),
        ]
        actual = [c.args for c in self.mock_pipe.hincrby.call_args_list]
        for exp in expected:
            self.assertIn(exp, actual)

        self.mock_pipe.hset.assert_called_with(
            GERRIT_CHANGE_STATUS_KEY, 42, GerritChangeStatus.MERGED.value
        )
        self.assertEqual(self.mock_pipe.execute.call_count, 2)
        self.assertEqual(self.mock_redis.pipeline.call_count, 2)

    def test_fetch_and_store_end_to_end(self):
        fake_pages = [
            [
                {
                    "owner": {"username": "bob"},
                    "status": GerritChangeStatus.NEW.value,
                    "insertions": 0,
                    "project": "p",
                    "created": "2025-05-14 00:00:00.000000",
                    "messages": [{"author": {"username": "charlie"}}],
                    "_number": 12345,
                }
            ],
            [],
        ]
        self.mock_gerrit_client.query_changes.side_effect = fake_pages

        self.service.fetch_and_store_changes(
            statuses=GerritChangeStatus.NEW.value,
            projects=["p"],
            max_changes=None,
            page_size=1,
        )

        self.assertEqual(self.mock_redis.pipeline.call_count, 2)
        calls = [c.args for c in self.mock_pipe.hincrby.call_args_list]

        self.assertIn(
            (
                GERRIT_STATS_ALL_TIME_KEY.format(ldap="bob"),
                GERRIT_STATUS_TO_FIELD[GERRIT_UNDER_REVIEW],
                1,
            ),
            calls,
        )
        self.assertIn(
            (
                GERRIT_STATS_ALL_TIME_KEY.format(ldap="charlie"),
                GERRIT_CL_REVIEWED_FIELD,
                1,
            ),
            calls,
        )

    def test_fetch_changes_with_no_filters(self):
        fake_pages = [[{"id": "x"}], []]
        self.mock_gerrit_client.query_changes.side_effect = fake_pages

        result = list(
            self.service.fetch_changes(
                statuses=None,
                projects=None,
                max_changes=None,
                page_size=1,
            )
        )

        self.assertEqual(result, [{"id": "x"}])
        self.mock_gerrit_client.query_changes.assert_called_with(
            queries=[],
            limit=1,
            start=1,
            no_limit=False,
            options=[
                "CURRENT_REVISION",
                "DETAILED_LABELS",
                "DETAILED_ACCOUNTS",
                "MESSAGES",
            ],
            allow_incomplete=True,
        )

    def test_store_change_with_multiple_reviewers(self):
        """
        Each distinct reviewer not in smembers() gets cl_reviewed +1
        across all-time, monthly, and project buckets.
        """
        change = {
            "owner": {"username": "dev1"},
            "status": GerritChangeStatus.NEW.value,
            "project": "demo",
            "created": "2025-05-10 08:00:00.000000",
            "_number": 100,
            "insertions": 5,
            "messages": [
                {"author": {"username": "rev1"}},
                {"author": {"username": "rev2"}},
                {"author": {"username": "rev1"}},
            ],
        }

        self.service.store_change(change)
        calls = [c.args for c in self.mock_pipe.hincrby.call_args_list]
        bucket = self.service.compute_buckets(change["created"])

        self.assertIn(
            (
                GERRIT_STATS_ALL_TIME_KEY.format(ldap="rev1"),
                GERRIT_CL_REVIEWED_FIELD,
                1,
            ),
            calls,
        )
        self.assertIn(
            (
                GERRIT_STATS_MONTHLY_BUCKET_KEY.format(ldap="rev1", bucket=bucket),
                GERRIT_CL_REVIEWED_FIELD,
                1,
            ),
            calls,
        )
        self.assertIn(
            (
                GERRIT_STATS_PROJECT_BUCKET_KEY.format(
                    ldap="rev1", project="demo", bucket=bucket
                ),
                GERRIT_CL_REVIEWED_FIELD,
                1,
            ),
            calls,
        )

        self.assertIn(
            (
                GERRIT_STATS_ALL_TIME_KEY.format(ldap="rev2"),
                GERRIT_CL_REVIEWED_FIELD,
                1,
            ),
            calls,
        )
        self.assertIn(
            (
                GERRIT_STATS_MONTHLY_BUCKET_KEY.format(ldap="rev2", bucket=bucket),
                GERRIT_CL_REVIEWED_FIELD,
                1,
            ),
            calls,
        )
        self.assertIn(
            (
                GERRIT_STATS_PROJECT_BUCKET_KEY.format(
                    ldap="rev2", project="demo", bucket=bucket
                ),
                GERRIT_CL_REVIEWED_FIELD,
                1,
            ),
            calls,
        )

        self.mock_pipe.expire.assert_called_once_with(
            "gerrit:dedupe:reviewed:100", 60 * 60 * 24 * 90
        )
        self.assertEqual(self.mock_redis.pipeline.call_count, 2)
        self.assertEqual(self.mock_pipe.execute.call_count, 2)

    def test_compute_buckets_invalid_timestamp(self):
        result = self.service.compute_buckets("bad input")
        pattern = r"\d{4}-\d{2}-01_\d{4}-\d{2}-\d{2}"
        self.assertRegex(result, pattern)


if __name__ == "__main__":
    unittest.main()
