from unittest import IsolatedAsyncioTestCase, main
from unittest.mock import patch, AsyncMock, MagicMock
from backend.historical_data.microsoft_member_sync_service import (
    MicrosoftMemberSyncService,
)


def make_mock_user(
    id: str, mail: str, display_name: str, account_enabled: bool
) -> MagicMock:
    """Helper function to create a mock user object."""
    user = MagicMock()
    user.id = id
    user.mail = mail
    user.display_name = display_name
    user.account_enabled = account_enabled
    return user


def make_mock_group(id: str, display_name: str) -> MagicMock:
    """Helper function to create a mock group object."""
    group = MagicMock()
    group.id = id
    group.display_name = display_name
    return group


class TestMicrosoftMemberSyncService(IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.mock_logger = MagicMock()
        self.mock_redis = MagicMock()
        self.mock_microsoft_service = AsyncMock()
        self.mock_pipeline = MagicMock()
        self.mock_redis.pipeline.return_value = self.mock_pipeline
        self.mock_retry_utils = MagicMock()
        self.mock_retry_utils.get_retry_on_transient.side_effect = (
            lambda func, *args, **kwargs: func()
        )
        self.microsoft_member_service = MicrosoftMemberSyncService(
            logger=self.mock_logger,
            redis_client=self.mock_redis,
            microsoft_service=self.mock_microsoft_service,
            retry_utils=self.mock_retry_utils,
        )

        self.mock_interns_group = make_mock_group(
            id="interns_group_id_123", display_name="Interns"
        )
        self.mock_employees_group = make_mock_group(
            id="employees_group_id_456", display_name="Employees"
        )
        self.mock_other_group = make_mock_group(
            id="other_group_id_789", display_name="Others"
        )

    def test_get_current_redis_members_by_group_and_status_success(self):
        mock_redis_data = [
            {
                "intern1@test.com": "Intern One",
                "intern2@test.com": "Intern Two",
            },  # active interns
            {"employee1@test.com": "Employee One"},  # active employees
            {},  # active volunteers (empty)
            {},  # terminated interns (empty)
            {
                "terminated_emp1@test.com": "Terminated Employee One"
            },  # terminated employees
            {},  # terminated volunteers (empty)
        ]
        self.mock_pipeline.execute.return_value = mock_redis_data

        expected_result = {
            ("active", "interns"): {
                "intern1@test.com": "Intern One",
                "intern2@test.com": "Intern Two",
            },
            ("active", "employees"): {"employee1@test.com": "Employee One"},
            ("active", "volunteers"): {},
            ("terminated", "interns"): {},
            ("terminated", "employees"): {
                "terminated_emp1@test.com": "Terminated Employee One"
            },
            ("terminated", "volunteers"): {},
        }

        result = self.microsoft_member_service.get_current_redis_members_by_group_and_status()

        self.assertEqual(result, expected_result)
        self.mock_redis.pipeline.assert_called_once()
        self.mock_retry_utils.get_retry_on_transient.assert_called_once()

    def test_get_current_redis_members_by_group_and_status_empty_redis(self):
        mock_redis_data = [{} for _ in range(6)]
        self.mock_pipeline.execute.return_value = mock_redis_data

        expected_result = {
            ("active", "interns"): {},
            ("active", "employees"): {},
            ("active", "volunteers"): {},
            ("terminated", "interns"): {},
            ("terminated", "employees"): {},
            ("terminated", "volunteers"): {},
        }

        result = self.microsoft_member_service.get_current_redis_members_by_group_and_status()

        self.assertEqual(result, expected_result)
        self.mock_redis.pipeline.assert_called_once()
        self.mock_retry_utils.get_retry_on_transient.assert_called_once()

    async def test_get_latest_members_by_group_and_status_success(self):
        self.mock_microsoft_service.list_all_groups.return_value = [
            self.mock_interns_group,
            self.mock_employees_group,
            self.mock_other_group,
        ]

        self.mock_microsoft_service.get_group_members.side_effect = [
            [
                make_mock_user(
                    id="user_intern_1",
                    mail="intern1@test.com",
                    display_name="Intern One",
                    account_enabled=True,
                )
            ],
            [
                make_mock_user(
                    id="user_emp_1",
                    mail="employee1@test.com",
                    display_name="Employee One",
                    account_enabled=True,
                ),
                make_mock_user(
                    id="user_term_emp_1",
                    mail="terminated_emp1@test.com",
                    display_name="Terminated Employee One",
                    account_enabled=False,
                ),
            ],
        ]

        self.mock_microsoft_service.get_all_microsoft_members.return_value = [
            make_mock_user(
                id="user_intern_1",
                mail="intern1@test.com",
                display_name="Intern One",
                account_enabled=True,
            ),
            make_mock_user(
                id="user_emp_1",
                mail="employee1@test.com",
                display_name="Employee One",
                account_enabled=True,
            ),
            make_mock_user(
                id="user_vol_1",
                mail="vol1@test.com",
                display_name="Volunteer One",
                account_enabled=True,
            ),
            make_mock_user(
                id="user_term_emp_1",
                mail="terminated_emp1@test.com",
                display_name="Terminated Employee One",
                account_enabled=False,
            ),
        ]

        expected_result = {
            ("active", "interns"): {"intern1": "Intern One"},
            ("active", "employees"): {"employee1": "Employee One"},
            ("active", "volunteers"): {"vol1": "Volunteer One"},
            ("terminated", "interns"): {},
            ("terminated", "employees"): {"terminated_emp1": "Terminated Employee One"},
            ("terminated", "volunteers"): {},
        }

        result = (
            await self.microsoft_member_service.get_latest_members_by_group_and_status()
        )

        self.assertDictEqual(result, expected_result)
        self.mock_microsoft_service.list_all_groups.assert_called_once()
        self.mock_microsoft_service.get_all_microsoft_members.assert_called_once()

    async def test_get_latest_members_by_group_and_status_no_members_found(self):
        self.mock_microsoft_service.list_all_groups.return_value = [
            self.mock_interns_group,
            self.mock_employees_group,
            self.mock_other_group,
        ]

        self.mock_microsoft_service.get_group_members.side_effect = [], []
        self.mock_microsoft_service.get_all_microsoft_members.return_value = []

        with self.assertRaises(RuntimeError):
            await self.microsoft_member_service.get_latest_members_by_group_and_status()

    async def test_get_latest_members_by_group_and_status_invalid_mail(self):
        self.mock_microsoft_service.list_all_groups.return_value = [
            self.mock_interns_group,
            self.mock_employees_group,
            self.mock_other_group,
        ]

        self.mock_microsoft_service.get_group_members.side_effect = [
            [
                make_mock_user(
                    id="user_intern_1",
                    mail="intern1test.com",
                    display_name="Intern One",
                    account_enabled=True,
                )
            ],
            [
                make_mock_user(
                    id="user_emp_1",
                    mail="",
                    display_name="Employee One",
                    account_enabled=True,
                )
            ],
        ]

        self.mock_microsoft_service.get_all_microsoft_members.return_value = [
            make_mock_user(
                id="user_intern_1",
                mail="intern1test.com",
                display_name="Intern One",
                account_enabled=True,
            ),
            make_mock_user(
                id="user_emp_1",
                mail="",
                display_name="Employee One",
                account_enabled=True,
            ),
        ]
        expected_result = {
            ("active", "interns"): {},
            ("active", "employees"): {},
            ("active", "volunteers"): {},
            ("terminated", "interns"): {},
            ("terminated", "employees"): {},
            ("terminated", "volunteers"): {},
        }
        result = (
            await self.microsoft_member_service.get_latest_members_by_group_and_status()
        )

        self.assertEqual(result, expected_result)
        self.mock_microsoft_service.list_all_groups.assert_called_once()
        self.mock_microsoft_service.get_all_microsoft_members.assert_called_once()

    @patch(
        "backend.historical_data.microsoft_member_sync_service.MicrosoftMemberSyncService.get_current_redis_members_by_group_and_status"
    )
    @patch(
        "backend.historical_data.microsoft_member_sync_service.MicrosoftMemberSyncService.get_latest_members_by_group_and_status"
    )
    async def test_sync_microsoft_members_full_sync(
        self, mock_get_latest_data, mock_get_current_data
    ):
        mock_get_current_data.return_value = {
            ("active", "interns"): {},
            ("active", "employees"): {},
            ("active", "volunteers"): {},
            ("terminated", "interns"): {},
            ("terminated", "employees"): {},
            ("terminated", "volunteers"): {},
        }
        mock_get_latest_data.return_value = {
            ("active", "interns"): {"ldap1": "Intern One"},
            ("active", "employees"): {"ldap2": "Employee One"},
            ("active", "volunteers"): {},
            ("terminated", "interns"): {},
            ("terminated", "employees"): {"ldap3": "Terminated Employee"},
            ("terminated", "volunteers"): {},
        }

        await self.microsoft_member_service.sync_microsoft_members_to_redis()

        self.mock_pipeline.hset.assert_any_call(
            "ldap:active:interns", mapping={"ldap1": "Intern One"}
        )
        self.mock_pipeline.hset.assert_any_call(
            "ldap:active:employees", mapping={"ldap2": "Employee One"}
        )
        self.mock_pipeline.hset.assert_any_call(
            "ldap:terminated:employees", mapping={"ldap3": "Terminated Employee"}
        )
        self.mock_pipeline.hdel.assert_not_called()
        self.mock_pipeline.execute.assert_called_once()

    @patch(
        "backend.historical_data.microsoft_member_sync_service.MicrosoftMemberSyncService.get_current_redis_members_by_group_and_status"
    )
    @patch(
        "backend.historical_data.microsoft_member_sync_service.MicrosoftMemberSyncService.get_latest_members_by_group_and_status"
    )
    async def test_sync_microsoft_members_incremental_update(
        self, mock_get_latest_data, mock_get_current_data
    ):
        mock_get_current_data.return_value = {
            ("active", "employees"): {
                "ldap1": "Employee One",  # Member to be deleted
                "ldap2": "Employee Two",  # Member to be updated
                "ldap3": "Employee Three",  # Member to remain unchanged
            },
            ("active", "interns"): {"intern1": "Intern One"},  # Unchanged group
        }

        mock_get_latest_data.return_value = {
            ("active", "employees"): {
                "ldap2": "Employee Two-Updated",  # Updated member
                "ldap3": "Employee Three",  # Unchanged
                "ldap4": "Employee Four",  # New member to be added
            },
            ("active", "interns"): {"intern1": "Intern One"},  # Unchanged
        }

        await self.microsoft_member_service.sync_microsoft_members_to_redis()

        self.mock_pipeline.hdel.assert_called_once_with(
            "ldap:active:employees", "ldap1"
        )
        self.mock_pipeline.hset.assert_called_once_with(
            "ldap:active:employees",
            mapping={
                "ldap2": "Employee Two-Updated",
                "ldap4": "Employee Four",
            },
        )
        self.mock_pipeline.execute.assert_called_once()

    @patch(
        "backend.historical_data.microsoft_member_sync_service.MicrosoftMemberSyncService.get_current_redis_members_by_group_and_status"
    )
    @patch(
        "backend.historical_data.microsoft_member_sync_service.MicrosoftMemberSyncService.get_latest_members_by_group_and_status"
    )
    async def test_sync_microsoft_members_delete_all(
        self, mock_get_latest_data, mock_get_current_data
    ):
        mock_get_current_data.return_value = {
            ("active", "employees"): {"ldap1": "Employee One"},
        }
        mock_get_latest_data.return_value = {
            ("active", "employees"): {},
            ("active", "interns"): {},
        }

        await self.microsoft_member_service.sync_microsoft_members_to_redis()

        self.mock_pipeline.hdel.assert_called_once_with(
            "ldap:active:employees", "ldap1"
        )
        self.assertEqual(self.mock_pipeline.hset.call_count, 0)
        self.mock_pipeline.execute.assert_called_once()


if __name__ == "__main__":
    main()
