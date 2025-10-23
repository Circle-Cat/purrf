import unittest
from unittest.mock import MagicMock, call
from datetime import datetime
from backend.historical_data.gerrit_sync_service import GerritSyncService
from backend.common.constants import (
    GerritChangeStatus,
    GERRIT_CL_REVIEWED_FIELD,
    GERRIT_LOC_MERGED_FIELD,
    GERRIT_STATUS_TO_FIELD,
    GERRIT_STATS_ALL_TIME_KEY,
    GERRIT_STATS_BUCKET_KEY,
    GERRIT_STATS_PROJECT_BUCKET_KEY,
    GERRIT_CHANGE_STATUS_KEY,
    GERRIT_DEDUPE_REVIEWED_KEY,
    THREE_MONTHS_IN_SECONDS,
    GERRIT_PERSUBMIT_BOT,
    GERRIT_STATUS_TO_FIELD_TEMPLATE,
    GERRIT_UNMERGED_CL_KEY_BY_PROJECT,
    GERRIT_UNMERGED_CL_KEY_GLOBAL,
)


class TestGerritSyncService(unittest.TestCase):
    def setUp(self):
        self.MERGED_CHANGE = {
            "project": "project1",
            "status": "MERGED",
            "created": "2025-03-24 01:07:48.000000000",
            "updated": "2025-10-22 05:44:27.000000000",
            "submitted": "2025-10-21 01:55:34.000000000",
            "insertions": 934,
            "deletions": 741,
            "_number": 6672,
            "virtual_id_number": 6672,
            "owner": {"username": "jdoe"},
            "messages": [
                {
                    "author": {
                        "username": "jdoe",
                    },
                    "date": "2025-03-24 01:07:48.000000000",
                    "message": "Uploaded patch set 1.",
                },
                {
                    "author": {
                        "username": GERRIT_PERSUBMIT_BOT,
                    },
                    "date": "2025-03-24 01:07:58.000000000",
                    "message": "Patch Set 1:Presubmit-Check Started",
                },
                {
                    "author": {"username": "alice"},
                    "date": "2025-03-29 15:02:59.000000000",  # Earliest review time of alice
                    "message": "Good job.",
                },
                {
                    "author": {"username": "alice"},
                    "date": "2025-03-31 07:45:27.000000000",
                    "message": "LGTM +2.",
                },
            ],
        }

        self.UNDER_REVIEW_CHANGE = {
            "project": "project2",
            "status": "NEW",
            "created": "2024-09-24 07:05:40.000000000",
            "updated": "2025-10-22 05:49:00.000000000",
            "insertions": 30,
            "deletions": 24,
            "_number": 4554,
            "virtual_id_number": 4554,
            "owner": {
                "username": "eve",
            },
            "messages": [
                {
                    "author": {
                        "username": "eve",
                    },
                    "date": "2024-09-24 07:05:40.000000000",
                    "message": "Uploaded patch set 1.",
                },
                {
                    "author": {
                        "username": GERRIT_PERSUBMIT_BOT,
                    },
                    "date": "2024-09-24 07:05:50.000000000",
                    "message": "Patch Set 1:Presubmit-Check Started.",
                },
                {
                    "author": {
                        "username": "jdoe",
                    },
                    "date": "2025-10-22 05:49:00.000000000",
                    "message": "Patch Set 5: Approval+1 LGTM+2 Verified+1",
                },
            ],
        }

        self.ABANDONED_CHANGE = {
            "project": "project3",
            "status": "ABANDONED",
            "created": "2025-09-10 09:00:00.000000000",
            "updated": "2025-09-18 12:00:00.000000000",
            "insertions": 50,
            "deletions": 10,
            "_number": 7777,
            "virtual_id_number": 7777,
            "owner": {"username": "charlie"},
            "messages": [
                {
                    "author": {
                        "username": "charlie",
                    },
                    "date": "2025-09-10 09:00:00.000000000",
                    "message": "Uploaded patch set 1.",
                },
                {
                    "author": {"username": "eve"},
                    "date": "2025-09-16 11:00:00.000000000",
                    "message": "Patch Set 1: Code-Review+1",
                },
                {
                    "author": {"username": "jdoe"},
                    "date": "2025-09-17 13:30:00.000000000",
                    "message": "Patch Set 1: Code-Review-1",
                },
            ],
        }

        self.MOCK_GERRIT_CHANGES_BATCH = [
            self.MERGED_CHANGE,
            self.UNDER_REVIEW_CHANGE,
            self.ABANDONED_CHANGE,
        ]

        self.mock_logger = MagicMock()
        self.mock_redis = MagicMock()
        self.mock_pipe = MagicMock()
        self.mock_redis.pipeline.return_value = self.mock_pipe
        self.mock_redis.smembers.return_value = set()
        self.mock_redis.hget.return_value = None
        self.mock_date_time_util = MagicMock()

        self.mock_gerrit_client = MagicMock()
        self.mock_retry_utils = MagicMock()

        # Simulate date_time_util.parse_timestamp_without_microseconds
        self.dt_map = {
            "2025-03-24 01:07:48.000000000": datetime.fromisoformat(
                "2025-03-24T01:07:48"
            ),
            "2025-03-29 15:02:59.000000000": datetime.fromisoformat(
                "2025-03-29T15:02:59"
            ),
            "2025-03-31 07:45:27.000000000": datetime.fromisoformat(
                "2025-03-31T07:45:27"
            ),
            "2024-09-24 07:05:40.000000000": datetime.fromisoformat(
                "2024-09-24T07:05:40"
            ),
            "2025-10-22 05:49:00.000000000": datetime.fromisoformat(
                "2025-10-22T05:49:00"
            ),
            "2025-09-10 09:00:00.000000000": datetime.fromisoformat(
                "2025-09-10T09:00:00"
            ),
            "2025-09-16 11:00:00.000000000": datetime.fromisoformat(
                "2025-09-16T11:00:00"
            ),
            "2025-09-17 13:30:00.000000000": datetime.fromisoformat(
                "2025-09-17T13:30:00"
            ),
            "2025-10-21 01:55:34.000000000": datetime.fromisoformat(
                "2025-10-21T01:55:34"
            ),  # Submitted time for MERGED_CHANGE
            "2025-09-18 12:00:00.000000000": datetime.fromisoformat(
                "2025-09-18T12:00:00"
            ),  # Updated time for ABANDONED_CHANGE
        }
        self.mock_date_time_util.parse_timestamp_without_microseconds.side_effect = (
            lambda ts_str: self.dt_map.get(ts_str)
        )

        # Simulate date_time_util.compute_buckets_weekly to return "YYYY-MM-DD_YYYY-MM-DD"
        self.bucket_map = {
            # Owner's CL timestamps (strings) - only 'submitted' for merged is relevant for owner's HSET
            "2025-10-21 01:55:34.000000000": "2025-10-20_2025-10-26",  # MERGED_CHANGE submitted
            # Reviewer's first message timestamps (datetime objects)
            datetime.fromisoformat(
                "2025-03-29T15:02:59"
            ): "2025-03-24_2025-03-30",  # Alice's first review (project1)
            datetime.fromisoformat(
                "2025-10-22T05:49:00"
            ): "2025-10-20_2025-10-26",  # Jdoe's review for UNDER_REVIEW_CHANGE (project2)
            datetime.fromisoformat(
                "2025-09-16T11:00:00"
            ): "2025-09-15_2025-09-21",  # Eve's review for ABANDONED_CHANGE (project3)
            datetime.fromisoformat(
                "2025-09-17T13:30:00"
            ): "2025-09-15_2025-09-21",  # Jdoe's review for ABANDONED_CHANGE (project3)
            # Other timestamps used for ZADD scores, but not for HSET buckets directly
            "2025-10-22 05:49:00.000000000": "2025-10-20_2025-10-26",  # UNDER_REVIEW_CHANGE updated for ZADD score
            "2025-09-18 12:00:00.000000000": "2025-09-15_2025-09-21",  # ABANDONED_CHANGE updated for ZADD score
        }
        self.mock_date_time_util.compute_buckets_weekly.side_effect = (
            lambda ts_input: self.bucket_map.get(
                ts_input if isinstance(ts_input, str) else ts_input
            )
        )

        self.service = GerritSyncService(
            logger=self.mock_logger,
            redis_client=self.mock_redis,
            gerrit_client=self.mock_gerrit_client,
            retry_utils=self.mock_retry_utils,
            date_time_util=self.mock_date_time_util,
        )

    def test_fetch_and_store_changes_integrates_correctly_with_redis(self):
        """
        Test that the fetch_and_store_changes method correctly fetches Gerrit changes and stores them in Redis.
        It covers both project-specific and global weekly aggregations.
        """
        self.mock_gerrit_client.query_changes.side_effect = [
            self.MOCK_GERRIT_CHANGES_BATCH,
            [],  # Signal no more pages
        ]

        # Calculate expected timestamp scores for ZADD
        timestamp_under_review = datetime.fromisoformat(
            "2025-10-22T05:49:00"
        ).timestamp()
        timestamp_abandoned = datetime.fromisoformat("2025-09-18T12:00:00").timestamp()

        self.service.fetch_and_store_changes()

        self.mock_gerrit_client.query_changes.assert_called_once()

        # Jdoe's global stats for 2025-10-20_2025-10-26 will combine merged owner stats and reviewer stats
        jdoe_combined_global_stats = {
            GERRIT_STATUS_TO_FIELD_TEMPLATE.format(status="merged"): 1,
            GERRIT_LOC_MERGED_FIELD: 934,
            GERRIT_CL_REVIEWED_FIELD: 1,
        }

        expected_hset_calls = [
            # Owner: jdoe (Merged CL) - project-specific
            call(
                GERRIT_STATS_PROJECT_BUCKET_KEY.format(
                    ldap="jdoe", project="project1", bucket="2025-10-20_2025-10-26"
                ),
                mapping={
                    GERRIT_STATUS_TO_FIELD_TEMPLATE.format(status="merged"): 1,
                    GERRIT_LOC_MERGED_FIELD: 934,
                },
            ),
            # Owner/Reviewer: jdoe (Combined global for Merged CL owner & Under Review CL reviewer)
            call(
                GERRIT_STATS_BUCKET_KEY.format(
                    ldap="jdoe", bucket="2025-10-20_2025-10-26"
                ),
                mapping=jdoe_combined_global_stats,
            ),
            # Reviewer: alice (for Merged CL) - project-specific
            call(
                GERRIT_STATS_PROJECT_BUCKET_KEY.format(
                    ldap="alice", project="project1", bucket="2025-03-24_2025-03-30"
                ),
                mapping={GERRIT_CL_REVIEWED_FIELD: 1},
            ),
            # Reviewer: alice (for Merged CL) - global
            call(
                GERRIT_STATS_BUCKET_KEY.format(
                    ldap="alice", bucket="2025-03-24_2025-03-30"
                ),
                mapping={GERRIT_CL_REVIEWED_FIELD: 1},
            ),
            # Reviewer: jdoe (for Under Review CL) - project-specific
            call(
                GERRIT_STATS_PROJECT_BUCKET_KEY.format(
                    ldap="jdoe", project="project2", bucket="2025-10-20_2025-10-26"
                ),
                mapping={GERRIT_CL_REVIEWED_FIELD: 1},
            ),
            # Reviewer: eve (for Abandoned CL) - project-specific
            call(
                GERRIT_STATS_PROJECT_BUCKET_KEY.format(
                    ldap="eve", project="project3", bucket="2025-09-15_2025-09-21"
                ),
                mapping={GERRIT_CL_REVIEWED_FIELD: 1},
            ),
            # Reviewer: eve (for Abandoned CL) - global
            call(
                GERRIT_STATS_BUCKET_KEY.format(
                    ldap="eve", bucket="2025-09-15_2025-09-21"
                ),
                mapping={GERRIT_CL_REVIEWED_FIELD: 1},
            ),
            # Reviewer: jdoe (for Abandoned CL) - project-specific
            call(
                GERRIT_STATS_PROJECT_BUCKET_KEY.format(
                    ldap="jdoe", project="project3", bucket="2025-09-15_2025-09-21"
                ),
                mapping={GERRIT_CL_REVIEWED_FIELD: 1},
            ),
            # Reviewer: jdoe (for Abandoned CL) - global
            call(
                GERRIT_STATS_BUCKET_KEY.format(
                    ldap="jdoe", bucket="2025-09-15_2025-09-21"
                ),
                mapping={GERRIT_CL_REVIEWED_FIELD: 1},
            ),
        ]

        actual_hset_calls = self.mock_pipe.hset.call_args_list
        self.assertEqual(len(expected_hset_calls), len(actual_hset_calls))
        for expected_call in expected_hset_calls:
            self.assertIn(expected_call, actual_hset_calls)

        expected_sadd_processed = [
            (
                GERRIT_DEDUPE_REVIEWED_KEY.format(change_number=4554),
                frozenset({"jdoe"}),
            ),
            (
                GERRIT_DEDUPE_REVIEWED_KEY.format(change_number=7777),
                frozenset({"jdoe", "eve"}),
            ),
        ]

        actual_sadd_calls = self.mock_pipe.sadd.call_args_list
        actual_sadd_processed = []
        for c in actual_sadd_calls:
            key = c.args[0]
            members = frozenset(c.args[1:])
            actual_sadd_processed.append((key, members))

        self.assertEqual(
            len(expected_sadd_processed),
            len(actual_sadd_processed),
        )

        for expected_item in expected_sadd_processed:
            self.assertIn(expected_item, actual_sadd_processed)
        self.mock_pipe.expire.assert_has_calls(
            [
                call(
                    GERRIT_DEDUPE_REVIEWED_KEY.format(change_number=4554),
                    THREE_MONTHS_IN_SECONDS,
                ),
                call(
                    GERRIT_DEDUPE_REVIEWED_KEY.format(change_number=7777),
                    THREE_MONTHS_IN_SECONDS,
                ),
            ],
            any_order=True,
        )

        expected_zadd_calls = [
            # Unmerged CL: eve (NEW) - project-specific
            call(
                GERRIT_UNMERGED_CL_KEY_BY_PROJECT.format(
                    ldap="eve", project="project2", cl_status="new"
                ),
                {4554: timestamp_under_review},
            ),
            # Unmerged CL: eve (NEW) - global
            call(
                GERRIT_UNMERGED_CL_KEY_GLOBAL.format(ldap="eve", cl_status="new"),
                {4554: timestamp_under_review},
            ),
            # Unmerged CL: charlie (ABANDONED) - project-specific
            call(
                GERRIT_UNMERGED_CL_KEY_BY_PROJECT.format(
                    ldap="charlie", project="project3", cl_status="abandoned"
                ),
                {7777: timestamp_abandoned},
            ),
            # Unmerged CL: charlie (ABANDONED) - global
            call(
                GERRIT_UNMERGED_CL_KEY_GLOBAL.format(
                    ldap="charlie", cl_status="abandoned"
                ),
                {7777: timestamp_abandoned},
            ),
        ]

        actual_zadd_calls = self.mock_pipe.zadd.call_args_list
        self.assertEqual(len(expected_zadd_calls), len(actual_zadd_calls))
        for expected_call in expected_zadd_calls:
            self.assertIn(expected_call, actual_zadd_calls)

        self.mock_retry_utils.get_retry_on_transient.assert_called_once_with(
            self.mock_pipe.execute
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
        self.assertEqual(result, [[{"id": 1}, {"id": 2}], [{"id": 3}]])

        self.mock_gerrit_client.query_changes.assert_any_call(
            queries=[f"(status:{GerritChangeStatus.MERGED.value}) project:purrf"],
            limit=2,
            start=0,
            no_limit=False,
            options=[
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
                "DETAILED_ACCOUNTS",
                "MESSAGES",
            ],
            allow_incomplete=True,
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

        self.assertEqual(result, [[{"id": "x"}]])
        self.mock_gerrit_client.query_changes.assert_called_with(
            queries=[],
            limit=1,
            start=1,
            no_limit=False,
            options=[
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
                GERRIT_STATS_BUCKET_KEY.format(ldap="alice", bucket=bucket),
                GERRIT_STATUS_TO_FIELD[GerritChangeStatus.MERGED.value],
                1,
            ),
            (
                GERRIT_STATS_BUCKET_KEY.format(ldap="alice", bucket=bucket),
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
                GERRIT_STATS_BUCKET_KEY.format(ldap="rev1", bucket=bucket),
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
                GERRIT_STATS_BUCKET_KEY.format(ldap="rev2", bucket=bucket),
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

    def test_sync_gerrit_projects_success(self):
        """Tests that projects are fetched and stored in Redis."""
        mock_projects = {
            "project-a": {"id": "project-a", "state": "ACTIVE"},
            "project-b": {"id": "project-b", "state": "ACTIVE"},
        }
        self.mock_gerrit_client.get_projects.return_value = mock_projects

        result = self.service.sync_gerrit_projects()

        self.assertEqual(result, 2)
        self.mock_gerrit_client.get_projects.assert_called_once()
        self.assertEqual(len(self.mock_redis.method_calls), 1)

    def test_sync_gerrit_projects_no_projects(self):
        """Tests that nothing is added to Redis when no projects are found."""
        self.mock_gerrit_client.get_projects.return_value = {}

        result = self.service.sync_gerrit_projects()

        self.assertEqual(result, 0)
        self.mock_gerrit_client.get_projects.assert_called_once()
        self.mock_redis.sadd.assert_not_called()


if __name__ == "__main__":
    unittest.main()
