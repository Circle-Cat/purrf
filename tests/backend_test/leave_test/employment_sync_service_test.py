import json
from decimal import Decimal
from unittest import main, IsolatedAsyncioTestCase
from unittest.mock import MagicMock, AsyncMock

from backend.common.leave_enums import LeaveEntryType
from backend.leave.leave_participants import ResolvedParticipants

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
    account_enabled=True,
):
    user = MagicMock()
    user.id = user_id
    user.mail = mail
    user.employee_type = employee_type
    user.office_location = office_location
    user.job_title = job_title
    user.employee_hire_date = hire_date
    user.employee_leave_date_time = leave_date
    user.account_enabled = account_enabled
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
        self.session = MagicMock()
        self.session.commit = AsyncMock()
        self.database = MagicMock()
        self.database.session.return_value.__aenter__.return_value = self.session
        self.database.session.return_value.__aexit__.return_value = None
        self.ledger_repository = MagicMock()
        self.ledger_repository.add_entries = AsyncMock()
        self.resolver = MagicMock()
        self.resolver.resolve = AsyncMock(
            return_value=ResolvedParticipants(
                by_ldap={"alice": 10}, unresolved=(), not_internal=()
            )
        )
        self.service = EmploymentSyncService(
            self.logger,
            self.redis_client,
            self.microsoft_service,
            self.retry_utils,
            self.database,
            self.ledger_repository,
            self.resolver,
        )

    def _cached(self, level="L3", annual_hours=80):
        return json.dumps(
            {
                "level": level,
                "annual_hours": annual_hours,
                "hire_date": "2024-03-01",
                "leave_date": None,
                "manager_ldap": "bob",
                "account_enabled": True,
                "problems": [],
            },
            sort_keys=True,
        )

    def _level_changes(self):
        return [
            entry
            for call in self.ledger_repository.add_entries.await_args_list
            for entry in call.args[1]
        ]

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
                "account_enabled": True,
                "problems": [],
            },
        )

    async def test_a_disabled_account_reaches_the_profile_as_disabled(self):
        """The accrual engine's only fallback for "has left" when Azure carries
        no leave date -- which is the state one of the five China full-timers is
        actually in. It has to survive the whole path into Redis."""
        self.microsoft_service.get_all_microsoft_members = AsyncMock(
            return_value=[
                make_graph_user(
                    "id-alice", "alice@circlecat.org", account_enabled=False
                )
            ]
        )
        self._stub_redis(employee_ldaps=["alice"], cached_profiles={})
        pipe = self.redis_client.pipeline.return_value

        await self.service.sync_employment_profiles_to_redis()

        written = json.loads(pipe.hset.call_args.kwargs["mapping"]["alice"])
        self.assertFalse(written["account_enabled"])

    async def test_an_entitlement_change_is_recorded_on_the_ledger(self):
        """The accrual engine needs the date its rate changed; Azure keeps only
        the current value. Zero hours, because the row is read for its date."""
        self.microsoft_service.get_all_microsoft_members = AsyncMock(
            return_value=[make_graph_user("id-alice", "alice@circlecat.org")]
        )
        self._stub_redis(
            employee_ldaps=["alice"],
            cached_profiles={"alice": self._cached(level="L1", annual_hours=0)},
        )

        await self.service.sync_employment_profiles_to_redis()

        entry = self._level_changes()[0]
        self.assertEqual(entry.entry_type, LeaveEntryType.LEVEL_CHANGE)
        self.assertEqual(entry.user_id, 10)
        self.assertEqual(entry.hours, Decimal("0.00"))
        self.assertEqual(entry.note, "L1 -> L3")

    async def test_the_ledger_row_lands_before_redis_is_overwritten(self):
        """Detection compares against last night's cached profile. Writing
        Redis first and then failing on the database would erase the evidence
        and the change would never be noticed again."""
        order = []
        self.ledger_repository.add_entries = AsyncMock(
            side_effect=lambda *a, **k: order.append("ledger")
        )
        pipe = self.redis_client.pipeline.return_value
        pipe.execute.side_effect = lambda *a, **k: order.append("redis")
        self.microsoft_service.get_all_microsoft_members = AsyncMock(
            return_value=[make_graph_user("id-alice", "alice@circlecat.org")]
        )
        self._stub_redis(
            employee_ldaps=["alice"],
            cached_profiles={"alice": self._cached(level="L1", annual_hours=0)},
        )

        await self.service.sync_employment_profiles_to_redis()

        self.assertEqual(order, ["ledger", "redis"])

    async def test_a_promotion_that_does_not_change_the_entitlement_writes_nothing(
        self,
    ):
        """L2, L3 and L4 all sit at 80h, so a move between them changes no
        number. A row would only reset the proportion for nothing."""
        self.microsoft_service.get_all_microsoft_members = AsyncMock(
            return_value=[make_graph_user("id-alice", "alice@circlecat.org")]
        )
        self._stub_redis(
            employee_ldaps=["alice"],
            cached_profiles={"alice": self._cached(level="L2", annual_hours=80)},
        )

        await self.service.sync_employment_profiles_to_redis()

        self.assertEqual(self._level_changes(), [])

    async def test_a_first_sighting_writes_nothing(self):
        """Nothing to compare against. Treating an arrival as a change would
        start their accrual today and lose the year to date."""
        self.microsoft_service.get_all_microsoft_members = AsyncMock(
            return_value=[make_graph_user("id-alice", "alice@circlecat.org")]
        )
        self._stub_redis(employee_ldaps=["alice"], cached_profiles={})

        await self.service.sync_employment_profiles_to_redis()

        self.assertEqual(self._level_changes(), [])

    async def test_a_title_that_stops_parsing_writes_nothing(self):
        """An unparseable title yields 0h, which looks like a demotion. Acting
        on it would freeze that person's accrual until somebody noticed."""
        self.microsoft_service.get_all_microsoft_members = AsyncMock(
            return_value=[
                make_graph_user(
                    "id-alice", "alice@circlecat.org", job_title="Software Engineer"
                )
            ]
        )
        self._stub_redis(
            employee_ldaps=["alice"],
            cached_profiles={"alice": self._cached()},
        )

        await self.service.sync_employment_profiles_to_redis()

        self.assertEqual(self._level_changes(), [])

    async def test_a_title_that_starts_parsing_writes_nothing_either(self):
        """The mirror image: a typo being fixed. Recording it would restart the
        proportion today and drop the hours they should already have had."""
        self.microsoft_service.get_all_microsoft_members = AsyncMock(
            return_value=[make_graph_user("id-alice", "alice@circlecat.org")]
        )
        self._stub_redis(
            employee_ldaps=["alice"],
            cached_profiles={"alice": self._cached(level=None, annual_hours=0)},
        )

        await self.service.sync_employment_profiles_to_redis()

        self.assertEqual(self._level_changes(), [])

    async def test_someone_with_no_purrf_account_is_reported_not_written(self):
        self.resolver.resolve.return_value = ResolvedParticipants(
            by_ldap={}, unresolved=("alice",), not_internal=()
        )
        self.microsoft_service.get_all_microsoft_members = AsyncMock(
            return_value=[make_graph_user("id-alice", "alice@circlecat.org")]
        )
        self._stub_redis(
            employee_ldaps=["alice"],
            cached_profiles={"alice": self._cached(level="L1", annual_hours=0)},
        )

        await self.service.sync_employment_profiles_to_redis()

        self.assertEqual(self._level_changes(), [])
        self.logger.warning.assert_called()

    async def test_nobody_changing_level_touches_no_session(self):
        """The ordinary night. No level change means no database work at all."""
        self.microsoft_service.get_all_microsoft_members = AsyncMock(
            return_value=[make_graph_user("id-alice", "alice@circlecat.org")]
        )
        self._stub_redis(
            employee_ldaps=["alice"], cached_profiles={"alice": self._cached()}
        )

        await self.service.sync_employment_profiles_to_redis()

        self.database.session.assert_not_called()
        self.resolver.resolve.assert_not_awaited()

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
                "account_enabled": True,
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
