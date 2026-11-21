"""Leave balances overview end to end against a real database: seed users,
ledger balances and leave requests, run the engine overview, and verify
pending and available hours in the serialized DTO."""

import datetime
import json
import unittest
import uuid
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

from backend.common.leave_enums import (
    LeaveEntryType,
    LeaveRequestStatus,
    LeaveRequestType,
)
from backend.common.mentorship_enums import CommunicationMethod
from backend.dto.leave_overview_dto import LeaveOverviewDto
from backend.entity.leave_ledger_entity import LeaveLedgerEntity
from backend.entity.leave_request_entity import LeaveRequestEntity
from backend.entity.users_entity import UsersEntity
from backend.leave.leave_engine_service import LeaveEngineService
from backend.leave.leave_participants import ResolvedParticipants
from backend.repository.leave_ledger_repository import LeaveLedgerRepository
from backend.repository.leave_request_repository import LeaveRequestRepository
from backend.repository.users_repository import UsersRepository
from tests.backend_test.repository_test.base_repository_test_lib import (
    BaseRepositoryTestLib,
)

TODAY = datetime.date(2026, 4, 15)


def _user(first: str) -> UsersEntity:
    return UsersEntity(
        first_name=first,
        last_name=uuid.uuid4().hex[:8],
        timezone="UTC",
        timezone_updated_at=datetime.datetime.now(datetime.timezone.utc),
        communication_channel=CommunicationMethod.EMAIL,
        is_active=True,
        is_super_admin=False,
        updated_timestamp=datetime.datetime.now(datetime.timezone.utc),
    )


def _profile_json(level: str = "L2", annual_hours: int = 80) -> str:
    return json.dumps({
        "level": level,
        "annual_hours": annual_hours,
        "hire_date": "2024-01-15",
        "leave_date": None,
        "manager_ldap": "mgr",
        "account_enabled": True,
        "problems": [],
    })


class LeaveBalancesFlowTest(BaseRepositoryTestLib):
    async def asyncSetUp(self):
        await super().asyncSetUp()
        self.approver = _user("Mgr")
        await self.insert_entities([self.approver])

        self.redis = MagicMock()
        self.retry = MagicMock()
        self.retry.get_retry_on_transient = MagicMock(side_effect=lambda f, *a: f(*a))
        self.participants = MagicMock()
        self.participants.resolve = AsyncMock()

        self.service = LeaveEngineService(
            logger=MagicMock(),
            redis_client=self.redis,
            retry_utils=self.retry,
            participant_resolver=self.participants,
            leave_ledger_repository=LeaveLedgerRepository(),
            users_repository=UsersRepository(),
            leave_request_repository=LeaveRequestRepository(),
        )

    async def _overview_for(
        self,
        *people: tuple[
            str, Decimal, list[tuple[LeaveRequestType, LeaveRequestStatus, Decimal]]
        ],
    ) -> dict[str, dict]:
        """Seeds (ldap, balance, [(request_type, status, hours), ...]) and runs overview."""
        by_ldap: dict[str, int] = {}
        for idx, (ldap, balance, requests) in enumerate(people, start=1):
            user = _user(ldap.capitalize())
            await self.insert_entities([user])
            by_ldap[ldap] = user.user_id

            entities: list[object] = [
                LeaveLedgerEntity(
                    user_id=user.user_id,
                    entry_type=LeaveEntryType.MANUAL_ADJUSTMENT,
                    hours=balance,
                    effective_date=TODAY,
                    created_by=self.approver.user_id,
                    note="Seed balance",
                )
            ]
            for day_offset, (request_type, status, hours) in enumerate(requests):
                day = datetime.date(2026, 5, 1) + datetime.timedelta(
                    days=idx * 10 + day_offset
                )
                entities.append(
                    LeaveRequestEntity(
                        user_id=user.user_id,
                        type=request_type,
                        status=status,
                        hours=hours,
                        start_date=day,
                        end_date=day,
                        approver_user_id=self.approver.user_id,
                    )
                )
            await self.insert_entities(entities)

        self.redis.hgetall = MagicMock(
            return_value={ldap: _profile_json() for ldap in by_ldap}
        )
        self.participants.resolve = AsyncMock(
            return_value=ResolvedParticipants(
                by_ldap=by_ldap, unresolved=(), not_internal=()
            )
        )

        overview = await self.service.overview(self.session, today=TODAY)
        payload = LeaveOverviewDto.of(overview).model_dump(by_alias=True)
        return {person["ldap"]: person for person in payload["people"]}

    async def test_pending_paid_request_reduces_available_hours(self):
        """Undecided paid requests hold back hours from the balance."""
        by_ldap = await self._overview_for(
            (
                "alice",
                Decimal("40.00"),
                [(LeaveRequestType.PAID, LeaveRequestStatus.PENDING, Decimal("16.00"))],
            ),
        )

        self.assertEqual(by_ldap["alice"]["pendingHours"], "16.00")
        self.assertEqual(by_ldap["alice"]["availableHours"], "24.00")

    async def test_multiple_pending_paid_requests_sum_together(self):
        """Every undecided paid request for the same person adds up."""
        by_ldap = await self._overview_for(
            (
                "bob",
                Decimal("30.00"),
                [
                    (
                        LeaveRequestType.PAID,
                        LeaveRequestStatus.PENDING,
                        Decimal("8.00"),
                    ),
                    (
                        LeaveRequestType.PAID,
                        LeaveRequestStatus.PENDING,
                        Decimal("4.50"),
                    ),
                ],
            ),
        )

        self.assertEqual(by_ldap["bob"]["pendingHours"], "12.50")
        self.assertEqual(by_ldap["bob"]["availableHours"], "17.50")

    async def test_sick_and_holiday_exchange_requests_hold_nothing_back(self):
        """Sick leave and holiday exchange never reduce available paid hours."""
        by_ldap = await self._overview_for(
            (
                "cara",
                Decimal("24.00"),
                [
                    (
                        LeaveRequestType.SICK,
                        LeaveRequestStatus.PENDING,
                        Decimal("8.00"),
                    ),
                    (
                        LeaveRequestType.EXCHANGE,
                        LeaveRequestStatus.PENDING,
                        Decimal("8.00"),
                    ),
                ],
            ),
        )

        self.assertEqual(by_ldap["cara"]["pendingHours"], "0.00")
        self.assertEqual(by_ldap["cara"]["availableHours"], "24.00")

    async def test_decided_and_withdrawn_requests_are_not_counted_as_pending(self):
        """Approved, rejected, and withdrawn requests hold nothing back."""
        by_ldap = await self._overview_for(
            (
                "dave",
                Decimal("50.00"),
                [
                    (
                        LeaveRequestType.PAID,
                        LeaveRequestStatus.APPROVED,
                        Decimal("8.00"),
                    ),
                    (
                        LeaveRequestType.PAID,
                        LeaveRequestStatus.REJECTED,
                        Decimal("8.00"),
                    ),
                    (
                        LeaveRequestType.PAID,
                        LeaveRequestStatus.WITHDRAWN,
                        Decimal("8.00"),
                    ),
                ],
            ),
        )

        self.assertEqual(by_ldap["dave"]["pendingHours"], "0.00")
        self.assertEqual(by_ldap["dave"]["availableHours"], "50.00")

    async def test_available_hours_can_go_negative_when_pending_exceeds_balance(self):
        """Holding more than the current balance leaves a negative available figure."""
        by_ldap = await self._overview_for(
            (
                "erin",
                Decimal("4.00"),
                [(LeaveRequestType.PAID, LeaveRequestStatus.PENDING, Decimal("8.00"))],
            ),
        )

        self.assertEqual(by_ldap["erin"]["pendingHours"], "8.00")
        self.assertEqual(by_ldap["erin"]["availableHours"], "-4.00")

    async def test_each_person_sees_only_their_own_pending_hours(self):
        """Reading everybody at once never leaks one person's pending hours onto another."""
        by_ldap = await self._overview_for(
            (
                "alice",
                Decimal("40.00"),
                [(LeaveRequestType.PAID, LeaveRequestStatus.PENDING, Decimal("16.00"))],
            ),
            (
                "bob",
                Decimal("30.00"),
                [(LeaveRequestType.PAID, LeaveRequestStatus.PENDING, Decimal("6.50"))],
            ),
        )

        self.assertEqual(by_ldap["alice"]["pendingHours"], "16.00")
        self.assertEqual(by_ldap["alice"]["availableHours"], "24.00")
        self.assertEqual(by_ldap["bob"]["pendingHours"], "6.50")
        self.assertEqual(by_ldap["bob"]["availableHours"], "23.50")


if __name__ == "__main__":
    unittest.main()
