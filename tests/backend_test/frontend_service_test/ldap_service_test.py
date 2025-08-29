from unittest import TestCase, main
from unittest.mock import MagicMock

from backend.common.constants import (
    LDAP_KEY_TEMPLATE,
    MicrosoftAccountStatus,
    MicrosoftGroups,
)
from backend.frontend_service.ldap_service import LdapService


class TestLdapService(TestCase):
    def setUp(self):
        self.logger = MagicMock()
        self.redis_client = MagicMock()
        self.retry_utils = MagicMock()
        self.service = LdapService(
            logger=self.logger,
            redis_client=self.redis_client,
            retry_utils=self.retry_utils,
        )
        self.retry_utils.get_retry_on_transient.side_effect = (
            lambda fn, *args, **kwargs: fn(*args, **kwargs)
        )

    def test_get_ldaps_by_status_and_group_single_status_and_group(self):
        status = MicrosoftAccountStatus.ACTIVE
        groups = [MicrosoftGroups.EMPLOYEES]

        pipeline_mock = MagicMock()
        self.redis_client.pipeline.return_value = pipeline_mock

        expected_redis_result = [{"alice": "Alice", "bob": "Bob"}]
        pipeline_mock.execute.return_value = expected_redis_result

        result = self.service.get_ldaps_by_status_and_group(status, groups)

        self.redis_client.pipeline.assert_called_once()
        key = LDAP_KEY_TEMPLATE.format(
            account_status=status.value, group=groups[0].value
        )
        pipeline_mock.hgetall.assert_called_once_with(key)
        self.retry_utils.get_retry_on_transient.assert_called_once_with(
            pipeline_mock.execute
        )

        expected_output = {"employees": {"active": {"alice": "Alice", "bob": "Bob"}}}
        self.assertEqual(result, expected_output)

    def test_get_ldaps_by_status_and_group_all_status_multiple_groups(self):
        status = MicrosoftAccountStatus.ALL
        groups = [MicrosoftGroups.EMPLOYEES, MicrosoftGroups.INTERNS]

        pipeline_mock = MagicMock()
        self.redis_client.pipeline.return_value = pipeline_mock

        redis_results = [
            {"emp_active": "Emp Active"},
            {"emp_term": "Emp Terminated"},
            {"intern_active": "Intern Active"},
            {},
        ]
        pipeline_mock.execute.return_value = redis_results

        result = self.service.get_ldaps_by_status_and_group(status, groups)

        self.assertEqual(pipeline_mock.hgetall.call_count, 4)

        expected_output = {
            "employees": {
                "active": {"emp_active": "Emp Active"},
                "terminated": {"emp_term": "Emp Terminated"},
            },
            "interns": {
                "active": {"intern_active": "Intern Active"},
                "terminated": {},
            },
        }
        self.assertEqual(result, expected_output)

    def test_get_ldaps_by_status_and_group_no_groups(self):
        status = MicrosoftAccountStatus.ACTIVE
        groups = []

        with self.assertRaises(TypeError):
            self.service.get_ldaps_by_status_and_group(status, groups)

    def test_get_ldaps_by_groups_and_no_status(self):
        status = None
        groups = [MicrosoftGroups.EMPLOYEES, MicrosoftGroups.INTERNS]

        with self.assertRaises(TypeError):
            self.service.get_ldaps_by_status_and_group(status, groups)

    def test_get_ldaps_by_status_and_group_redis_returns_nothing(self):
        status = MicrosoftAccountStatus.ACTIVE
        groups = [MicrosoftGroups.EMPLOYEES]

        pipeline_mock = MagicMock()
        self.redis_client.pipeline.return_value = pipeline_mock
        pipeline_mock.execute.return_value = [{}]

        result = self.service.get_ldaps_by_status_and_group(status, groups)

        expected_output = {"employees": {"active": {}}}
        self.assertEqual(result, expected_output)

    def test_returns_all_ldaps_from_all_groups_and_statuses(self):
        pipeline = MagicMock()
        self.redis_client.pipeline.return_value = pipeline
        pipeline.hkeys.side_effect = lambda key: None
        pipeline.execute.return_value = [["ldap1"], ["ldap2"], ["ldap3"], []]

        result = self.service.get_all_ldaps()

        expected_keys = []
        for group in MicrosoftGroups:
            for status in (
                MicrosoftAccountStatus.ACTIVE,
                MicrosoftAccountStatus.TERMINATED,
            ):
                expected_keys.append(
                    LDAP_KEY_TEMPLATE.format(
                        account_status=status.value,
                        group=group.value,
                    )
                )

        actual_keys = [args[0] for args, _ in pipeline.hkeys.call_args_list]

        self.assertEqual(set(result), {"ldap1", "ldap2", "ldap3"})
        self.assertEqual(set(actual_keys), set(expected_keys))

    def test_empty_pipeline_execute_returns_empty_list(self):
        pipeline = MagicMock()
        self.redis_client.pipeline.return_value = pipeline
        pipeline.hkeys.side_effect = lambda key: None
        pipeline.execute.return_value = []

        result = self.service.get_all_ldaps()
        self.assertEqual(result, [])

    def test_pipeline_execute_with_empty_ldaps(self):
        pipeline = MagicMock()
        self.redis_client.pipeline.return_value = pipeline
        pipeline.hkeys.side_effect = lambda key: None
        pipeline.execute.return_value = [[], []]

        result = self.service.get_all_ldaps()
        self.assertEqual(result, [])


if __name__ == "__main__":
    main()
