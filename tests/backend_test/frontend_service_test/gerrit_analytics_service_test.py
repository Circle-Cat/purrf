import unittest
from unittest.mock import MagicMock, patch, call
from datetime import date, datetime, timezone
from backend.frontend_service.gerrit_analytics_service import GerritAnalyticsService
from backend.common.constants import (
    GERRIT_STATS_PROJECT_BUCKET_KEY,
    GERRIT_UNMERGED_CL_KEY_BY_PROJECT,
    GERRIT_UNMERGED_CL_KEY_GLOBAL,
    ZSET_MIN_SCORE,
    GerritChangeStatus,
    GERRIT_CL_MERGED_FIELD,
    GERRIT_CL_ABANDONED_FIELD,
    GERRIT_CL_UNDER_REVIEW_FIELD,
    GERRIT_CL_REVIEWED_FIELD,
    GERRIT_LOC_MERGED_FIELD,
    GERRIT_STATS_BUCKET_KEY,
)


class TestGerritAnalyticsService(unittest.TestCase):
    def setUp(self):
        self.logger = MagicMock()
        self.redis_client = MagicMock()
        self.retry_utils = MagicMock()
        self.ldap_service = MagicMock()
        self.date_time_util = MagicMock()
        self.gerrit_client = MagicMock()

        self.mock_start_datetime = datetime(2025, 10, 21, tzinfo=timezone.utc)
        self.mock_end_datetime = datetime(2025, 10, 28, tzinfo=timezone.utc)
        self.date_time_util.get_start_end_timestamps.return_value = (
            self.mock_start_datetime,
            self.mock_end_datetime,
        )
        self.date_time_util.get_week_buckets.return_value = ["2025W42", "2025W43"]

        self.retry_utils.get_retry_on_transient.side_effect = (
            lambda func, *args, **kwargs: func(*args, **kwargs)
        )

        self.service = GerritAnalyticsService(
            logger=self.logger,
            redis_client=self.redis_client,
            retry_utils=self.retry_utils,
            ldap_service=self.ldap_service,
            date_time_util=self.date_time_util,
            gerrit_client=self.gerrit_client,
        )

        self.mock_pipeline = MagicMock()
        self.redis_client.pipeline.return_value = self.mock_pipeline
        self.default_hgetall_data = {
            GERRIT_CL_MERGED_FIELD: "10",
            GERRIT_CL_REVIEWED_FIELD: "5",
            GERRIT_LOC_MERGED_FIELD: "100",
        }
        self.mock_pipeline.reset_mock()

    @patch("backend.frontend_service.gerrit_analytics_service.datetime")
    def test_empty_project_list_defaults_to_global(self, mock_dt):
        """
        Test that when project_list is empty, None, or contains empty strings,
        the global statistics (project=None) are queried.
        """
        ldap_list = ["user_global"]
        project_list_variants = [[], None, ["", None]]

        week_buckets = self.date_time_util.get_week_buckets.return_value

        for proj_list in project_list_variants:
            with self.subTest(project_list=proj_list):
                self.setUp()
                mock_now_instance = MagicMock()
                mock_now_instance.date.return_value = date(2025, 10, 28)  # 2025-10-28
                mock_dt.now.return_value = mock_now_instance
                self.ldap_service.get_all_active_interns_and_employees_ldaps.return_value = ldap_list

                effective_projects = [
                    p for p in (proj_list or []) if p and p.strip()
                ] or [None]

                # HGETALL * len(week_buckets) + ZCOUNT * 2 (Abandoned + New)
                expected_results = []
                for _ in range(len(ldap_list) * len(effective_projects)):
                    # HGETALL results (weekly stats)
                    for _ in week_buckets:
                        expected_results.append(self.default_hgetall_data)
                    # ZCOUNT results
                    expected_results.append(2)  # Abandoned count
                    expected_results.append(2)  # Under Review count

                self.mock_pipeline.execute.return_value = expected_results

                result_stats = self.service.get_gerrit_stats(
                    ldap_list=ldap_list,
                    start_date_str="2025-10-21",
                    end_date_str="2025-10-28",
                    project_list=proj_list,
                    include_full_stats=True,
                    include_all_projects=False,
                )

                expected_calls = []
                for ldap in ldap_list:
                    for project in effective_projects:
                        for bucket in week_buckets:
                            # 1. HGETALL (Weekly Stats)
                            stats_key = GERRIT_STATS_BUCKET_KEY.format(
                                ldap=ldap, bucket=bucket
                            )
                            expected_calls.append(call.hgetall(stats_key))

                        # 2. abandoned CL (ZCOUNT)
                        abandoned_cl_search_key = GERRIT_UNMERGED_CL_KEY_GLOBAL.format(
                            ldap=ldap, cl_status=GerritChangeStatus.ABANDONED.value
                        )
                        expected_calls.append(
                            call.zcount(
                                abandoned_cl_search_key,
                                self.mock_start_datetime.timestamp(),
                                self.mock_end_datetime.timestamp(),
                            )
                        )

                        # 3. under review CL (ZCOUNT)
                        under_review_cl_search_key = (
                            GERRIT_UNMERGED_CL_KEY_GLOBAL.format(
                                ldap=ldap, cl_status=GerritChangeStatus.NEW.value
                            )
                        )
                        expected_calls.append(
                            call.zcount(
                                under_review_cl_search_key,
                                ZSET_MIN_SCORE,
                                self.mock_end_datetime.timestamp(),
                            )
                        )

                self.mock_pipeline.assert_has_calls(expected_calls, any_order=False)
                # Check ZCOUNT and HGETALL counts
                self.assertEqual(
                    self.mock_pipeline.hgetall.call_count,
                    len(ldap_list) * len(effective_projects) * len(week_buckets),
                )
                self.assertEqual(
                    self.mock_pipeline.zcount.call_count,
                    len(ldap_list) * len(effective_projects) * 2,
                )  # abandoned + new

                hgetall_multiplier = len(week_buckets) * len(effective_projects)
                zcount_multiplier = len(effective_projects)

                expected_merged = 10 * hgetall_multiplier
                expected_abandoned = 2 * zcount_multiplier
                expected_under_review = 2 * zcount_multiplier

                user_ldap = ldap_list[0]  # "user_global"

                self.assertIn(user_ldap, result_stats)
                self.assertEqual(
                    result_stats[user_ldap][GERRIT_CL_MERGED_FIELD], expected_merged
                )
                self.assertEqual(
                    result_stats[user_ldap][GERRIT_CL_ABANDONED_FIELD],
                    expected_abandoned,
                )
                self.assertEqual(
                    result_stats[user_ldap][GERRIT_CL_UNDER_REVIEW_FIELD],
                    expected_under_review,
                )

    @patch("backend.frontend_service.gerrit_analytics_service.datetime")
    def test_full_stats_with_under_review_today_and_projects(self, mock_dt):
        """
        Test full stats (abandoned, under-review) when end_date is today.
        In this case, all types of statistics (including under_review) should be queried and filtered by projects.
        """
        mock_now_instance = MagicMock()
        mock_now_instance.date.return_value = date(2025, 10, 28)  # 2025-10-28
        mock_dt.now.return_value = mock_now_instance

        ldap_list = ["user1", "user2"]
        project_list = ["projA", "projB"]
        week_buckets = self.date_time_util.get_week_buckets.return_value

        expected_results = []
        for _ in range(len(ldap_list) * len(project_list)):
            # 2 HGETALL results (weekly stats)
            expected_results.append(self.default_hgetall_data)
            expected_results.append(self.default_hgetall_data)
            # 1 ZCOUNT result (abandoned)
            expected_results.append(2)
            # 1 ZCOUNT result (under review)
            expected_results.append(2)

        self.mock_pipeline.execute.return_value = expected_results

        result = self.service.get_gerrit_stats(
            ldap_list=ldap_list,
            start_date_str="2025-10-21",
            end_date_str="2025-10-28",
            project_list=project_list,
            include_full_stats=True,
            include_all_projects=False,
        )

        # Verify pipeline call order and arguments
        expected_calls = []

        for ldap in ldap_list:
            for project in project_list:
                # Weekly stats
                for bucket in week_buckets:
                    expected_calls.append(
                        call.hgetall(
                            GERRIT_STATS_PROJECT_BUCKET_KEY.format(
                                ldap=ldap, project=project, bucket=bucket
                            )
                        )
                    )

                # Abandoned CL
                expected_calls.append(
                    call.zcount(
                        GERRIT_UNMERGED_CL_KEY_BY_PROJECT.format(
                            ldap=ldap,
                            project=project,
                            cl_status=GerritChangeStatus.ABANDONED.value,
                        ),
                        self.mock_start_datetime.timestamp(),
                        self.mock_end_datetime.timestamp(),
                    )
                )

                # Under review CL
                expected_calls.append(
                    call.zcount(
                        GERRIT_UNMERGED_CL_KEY_BY_PROJECT.format(
                            ldap=ldap,
                            project=project,
                            cl_status=GerritChangeStatus.NEW.value,
                        ),
                        ZSET_MIN_SCORE,
                        self.mock_end_datetime.timestamp(),
                    )
                )

        self.mock_pipeline.assert_has_calls(expected_calls, any_order=False)
        self.assertEqual(
            self.mock_pipeline.hgetall.call_count,
            len(ldap_list) * len(project_list) * len(week_buckets),
        )  # 2 * 2 * 2 = 8
        self.assertEqual(
            self.mock_pipeline.zcount.call_count, len(ldap_list) * len(project_list) * 2
        )  # 2 * 2 * 2 = 8 (abandoned + new)

        # Verify aggregated results
        hgetall_multiplier = len(week_buckets) * len(project_list)  # 4
        zcount_multiplier = len(project_list)  # 2

        expected_merged = 10 * hgetall_multiplier  # 40
        expected_reviewed = 5 * hgetall_multiplier  # 20
        expected_loc = 100 * hgetall_multiplier  # 400
        expected_abandoned = 2 * zcount_multiplier  # 4
        expected_under_review = 2 * zcount_multiplier  # 4

        for ldap in ldap_list:
            self.assertIn(ldap, result)
            self.assertEqual(result[ldap][GERRIT_CL_MERGED_FIELD], expected_merged)
            self.assertEqual(result[ldap][GERRIT_CL_REVIEWED_FIELD], expected_reviewed)
            self.assertEqual(result[ldap][GERRIT_LOC_MERGED_FIELD], expected_loc)
            self.assertEqual(
                result[ldap][GERRIT_CL_ABANDONED_FIELD], expected_abandoned
            )
            self.assertEqual(
                result[ldap][GERRIT_CL_UNDER_REVIEW_FIELD], expected_under_review
            )

    @patch("backend.frontend_service.gerrit_analytics_service.datetime")
    def test_basic_global_stats_no_full_stats_not_today(self, mock_dt):
        """
        Test basic case: no project list, full stats not included, and end_date is not today.
        Only global weekly statistics should be queried, and include_under_review should be False.
        """
        mock_now_instance = MagicMock()
        mock_now_instance.date.return_value = date(2025, 10, 29)  # 2025-10-29
        mock_dt.now.return_value = mock_now_instance

        ldap_list = ["user1"]

        expected_results = [
            self.default_hgetall_data,  # For 2025W42
            self.default_hgetall_data,  # For 2025W43
        ]
        self.mock_pipeline.execute.return_value = expected_results

        result = self.service.get_gerrit_stats(
            ldap_list=ldap_list,
            start_date_str="2025-10-21",
            end_date_str="2025-10-28",
            include_full_stats=False,
            include_all_projects=True,
        )

        # Expected Redis calls: only global weekly stats
        expected_hgetall_calls = [
            call.hgetall(
                GERRIT_STATS_BUCKET_KEY.format(ldap="user1", bucket="2025W42")
            ),
            call.hgetall(
                GERRIT_STATS_BUCKET_KEY.format(ldap="user1", bucket="2025W43")
            ),
        ]

        self.mock_pipeline.assert_has_calls(expected_hgetall_calls, any_order=False)
        self.assertEqual(
            self.mock_pipeline.hgetall.call_count,
            len(ldap_list) * len(self.date_time_util.get_week_buckets.return_value),
        )
        self.mock_pipeline.zcount.assert_not_called()

        self.assertIn("user1", result)

        self.assertEqual(result["user1"][GERRIT_CL_MERGED_FIELD], 10 * 2)
        self.assertEqual(result["user1"][GERRIT_CL_REVIEWED_FIELD], 5 * 2)
        self.assertEqual(result["user1"][GERRIT_LOC_MERGED_FIELD], 100 * 2)
        self.assertEqual(result["user1"][GERRIT_CL_ABANDONED_FIELD], 0)
        self.assertEqual(result["user1"][GERRIT_CL_UNDER_REVIEW_FIELD], 0)

    @patch("backend.frontend_service.gerrit_analytics_service.datetime")
    def test_no_active_ldap_users_found(self, mock_dt):
        """
        Test when ldap_service.get_all_active_interns_and_employees_ldaps returns empty,
        the method should return an empty dictionary and log a warning.
        """
        self.ldap_service.get_all_active_interns_and_employees_ldaps.return_value = []

        result = self.service.get_gerrit_stats(
            start_date_str="2025-10-21", end_date_str="2025-10-28"
        )

        self.assertEqual(result, {})
        self.ldap_service.get_all_active_interns_and_employees_ldaps.assert_called_once()


if __name__ == "__main__":
    unittest.main()
