import json
from unittest import main, IsolatedAsyncioTestCase
from unittest.mock import MagicMock, AsyncMock

from backend.leave.employment_sync_service import (
    EmploymentSyncService,
    EMPLOYEES_GROUP_KEY,
    LEAVE_EMPLOYMENT_KEY,
)


def make_graph_user(
    user_id,
    mail,
    employee_type="Full-time Employee",
    office_location="CN-CAN-ZQ",
    job_title="Software Engineer (L3)",
    hire_date="2024-03-01T00:00:00Z",
    leave_date=None,
    manager_mail="bob@circlecat.org",
):
    user = MagicMock()
    user.id = user_id
    user.mail = mail
    user.employee_type = employee_type
    user.office_location = office_location
    user.job_title = job_title
    user.employee_hire_date = hire_date
    user.employee_leave_date_time = leave_date
    if manager_mail is None:
        user.manager = None
    else:
        manager = MagicMock()
        manager.mail = manager_mail
        user.manager = manager
    return user


class EmploymentSyncServiceTest(IsolatedAsyncioTestCase):
    def setUp(self):
        self.logger = MagicMock()
        self.redis_client = MagicMock()
        self.microsoft_service = MagicMock()
        self.retry_utils = MagicMock()
        self.retry_utils.get_retry_on_transient = lambda fn, *a, **kw: fn(*a, **kw)
        self.service = EmploymentSyncService(
            self.logger, self.redis_client, self.microsoft_service, self.retry_utils
        )

    def _stub_redis(self, employee_ldaps, cached_profiles):
        """Routes hgetall by key -- group membership and profiles are two hashes."""
        by_key = {
            EMPLOYEES_GROUP_KEY: {ldap: "Display Name" for ldap in employee_ldaps},
            LEAVE_EMPLOYMENT_KEY: cached_profiles,
        }
        self.redis_client.hgetall.side_effect = lambda key: by_key.get(key, {})

    async def test_takes_the_manager_from_the_expanded_payload(self):
        """One expanded query carries every manager; no per-user lookup."""
        self.microsoft_service.get_all_microsoft_members = AsyncMock(
            return_value=[make_graph_user("id-alice", "alice@circlecat.org")]
        )
        self._stub_redis(employee_ldaps=["alice", "carl", "dana"], cached_profiles={})
        pipe = self.redis_client.pipeline.return_value

        await self.service.sync_employment_profiles_to_redis()

        written = json.loads(pipe.hset.call_args.kwargs["mapping"]["alice"])
        self.assertEqual(written["manager_ldap"], "bob")

    async def test_writes_one_profile_per_in_scope_person(self):
        self.microsoft_service.get_all_microsoft_members = AsyncMock(
            return_value=[make_graph_user("id-alice", "alice@circlecat.org")]
        )
        self._stub_redis(employee_ldaps=["alice", "carl", "dana"], cached_profiles={})
        pipe = self.redis_client.pipeline.return_value

        await self.service.sync_employment_profiles_to_redis()

        written = pipe.hset.call_args.kwargs["mapping"]
        self.assertEqual(list(written.keys()), ["alice"])
        self.assertEqual(
            json.loads(written["alice"]),
            {
                "level": "L3",
                "annual_hours": 80,
                "hire_date": "2024-03-01",
                "leave_date": None,
                "manager_ldap": "bob",
                "problems": [],
            },
        )

    async def test_removes_people_who_left_the_scope(self):
        self.microsoft_service.get_all_microsoft_members = AsyncMock(
            return_value=[make_graph_user("id-alice", "alice@circlecat.org")]
        )
        self._stub_redis(
            employee_ldaps=["alice"],
            cached_profiles={"alice": "{}", "gone": "{}"},
        )
        pipe = self.redis_client.pipeline.return_value

        await self.service.sync_employment_profiles_to_redis()

        pipe.hdel.assert_called_once()
        self.assertEqual(pipe.hdel.call_args.args[1:], ("gone",))

    async def test_writes_nothing_when_no_profile_changed(self):
        unchanged = json.dumps(
            {
                "level": "L3",
                "annual_hours": 80,
                "hire_date": "2024-03-01",
                "leave_date": None,
                "manager_ldap": "bob",
                "problems": [],
            },
            sort_keys=True,
        )
        self.microsoft_service.get_all_microsoft_members = AsyncMock(
            return_value=[make_graph_user("id-alice", "alice@circlecat.org")]
        )
        self._stub_redis(employee_ldaps=["alice"], cached_profiles={"alice": unchanged})
        pipe = self.redis_client.pipeline.return_value

        await self.service.sync_employment_profiles_to_redis()

        pipe.hset.assert_not_called()
        pipe.execute.assert_not_called()

    async def test_a_missing_manager_still_produces_a_profile(self):
        """One unconfigured person must not abort the sync -- it is recorded as a problem."""
        self.microsoft_service.get_all_microsoft_members = AsyncMock(
            return_value=[
                make_graph_user("id-alice", "alice@circlecat.org", manager_mail=None)
            ]
        )
        self._stub_redis(employee_ldaps=["alice", "carl", "dana"], cached_profiles={})
        pipe = self.redis_client.pipeline.return_value

        await self.service.sync_employment_profiles_to_redis()

        written = json.loads(pipe.hset.call_args.kwargs["mapping"]["alice"])
        self.assertEqual(written["problems"], ["missing_manager"])

    async def test_returns_the_coverage_report(self):
        """The report is the deliverable of this slice, so the caller gets it back."""
        self.microsoft_service.get_all_microsoft_members = AsyncMock(
            return_value=[
                make_graph_user("id-alice", "alice@circlecat.org"),
                make_graph_user(
                    "id-carl", "carl@circlecat.org", employee_type="Intern"
                ),
            ]
        )
        self._stub_redis(employee_ldaps=["alice", "carl", "dana"], cached_profiles={})

        report = await self.service.sync_employment_profiles_to_redis()

        self.assertEqual(report.fetched_count, 2)
        self.assertEqual(report.in_scope_count, 1)
        self.assertEqual(report.level_distribution, {"L3": 1})

    async def test_employee_group_membership_comes_from_redis_not_graph(self):
        """The member sync wrote that hash earlier in the same run."""
        self.microsoft_service.get_all_microsoft_members = AsyncMock(
            return_value=[make_graph_user("id-alice", "alice@circlecat.org")]
        )
        self._stub_redis(employee_ldaps=["alice"], cached_profiles={})

        await self.service.sync_employment_profiles_to_redis()

        self.redis_client.hgetall.assert_any_call(EMPLOYEES_GROUP_KEY)
        self.microsoft_service.list_all_groups.assert_not_called()
        self.microsoft_service.get_group_members.assert_not_called()

    async def test_an_employee_with_a_blank_admission_field_is_reported(self):
        """Otherwise a China full-timer with a blank employeeType accrues nothing, silently."""
        self.microsoft_service.get_all_microsoft_members = AsyncMock(
            return_value=[
                make_graph_user("id-erin", "erin@circlecat.org", employee_type=None)
            ]
        )
        self._stub_redis(employee_ldaps=["erin"], cached_profiles={})

        report = await self.service.sync_employment_profiles_to_redis()

        self.assertEqual(report.in_scope_count, 0)
        self.assertEqual(report.unknown_eligibility, {"erin": ["employeeType"]})

    async def test_a_volunteer_with_the_same_blank_field_is_not_reported(self):
        self.microsoft_service.get_all_microsoft_members = AsyncMock(
            return_value=[
                make_graph_user("id-vera", "vera@circlecat.org", employee_type=None)
            ]
        )
        self._stub_redis(employee_ldaps=[], cached_profiles={})

        report = await self.service.sync_employment_profiles_to_redis()

        self.assertEqual(report.unknown_eligibility, {})


if __name__ == "__main__":
    main()
