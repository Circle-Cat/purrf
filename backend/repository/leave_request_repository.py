import datetime
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.common.leave_enums import LeaveRequestStatus, LeaveRequestType
from backend.entity.leave_request_entity import LeaveRequestEntity

# A day already claimed by one of these cannot be claimed again. Rejected and
# withdrawn requests deducted nothing, so their days are free.
BLOCKING_STATUSES = (LeaveRequestStatus.PENDING, LeaveRequestStatus.APPROVED)


class LeaveRequestRepository:
    """Leave and exchange requests.

    Nothing here commits; the service owns the transaction, because approving a
    request writes a ledger row in the same breath as changing its status.
    """

    async def add(
        self, session: AsyncSession, request: LeaveRequestEntity
    ) -> LeaveRequestEntity:
        """Stores a new request and returns it with its id assigned.

        Args:
            session: Active async session. Not committed.
            request: The request to store.

        Returns:
            The same entity, flushed, so the caller can report its id.
        """
        session.add(request)
        await session.flush()
        return request

    async def get_by_id(
        self, session: AsyncSession, request_id: int, *, for_update: bool = False
    ) -> LeaveRequestEntity | None:
        """One request, or None.

        Args:
            session: Active async session.
            request_id: Its id.
            for_update: Take a row lock, held until this transaction commits.
                Anyone else reading the same row this way waits, and reads the
                decided status rather than the pending one they would otherwise
                still see. Required of everything that decides a request; a
                plain read must not ask for it.

        Returns:
            The request, or None when there is no such row.
        """
        stmt = select(LeaveRequestEntity).where(
            LeaveRequestEntity.leave_request_id == request_id
        )
        if for_update:
            stmt = stmt.with_for_update()
        result = await session.execute(stmt)
        return result.scalars().one_or_none()

    async def list_overlapping(
        self,
        session: AsyncSession,
        user_id: int,
        start_date: datetime.date,
        end_date: datetime.date,
    ) -> list[LeaveRequestEntity]:
        """This person's live requests whose days intersect ``[start, end]``.

        Deliberately blind to type. An exchange says "I am at work that day"
        and leave says the opposite; the day cannot be both, and letting the two
        coexist is also what would make an exchanged day exploitable -- taking
        leave across it would hand back the day just bought.

        Args:
            session: Active async session.
            user_id: Whose requests.
            start_date: First day of the range being asked for.
            end_date: Last day of it.

        Returns:
            Every pending or approved request that touches the range, oldest
            first, so an error message can name them in a stable order.
        """
        result = await session.execute(
            select(LeaveRequestEntity)
            .where(
                LeaveRequestEntity.user_id == user_id,
                LeaveRequestEntity.status.in_(BLOCKING_STATUSES),
                LeaveRequestEntity.start_date <= end_date,
                LeaveRequestEntity.end_date >= start_date,
            )
            .order_by(LeaveRequestEntity.leave_request_id)
        )
        return list(result.scalars().all())

    async def sum_pending_paid_hours(
        self, session: AsyncSession, user_id: int
    ) -> Decimal:
        """Hours held back by requests that are waiting for a decision.

        A pending request writes nothing to the ledger -- the ledger records
        facts, and a request nobody has decided is not one yet -- so a balance
        has to hold its hours back separately or the same hours could be spent
        twice over.

        Only paid leave reserves anything. Sick leave never touches the
        balance, and an approved request is already in the ledger.

        Args:
            session: Active async session.
            user_id: Whose requests.

        Returns:
            The total, or ``0.00`` when nothing is waiting -- never None, since
            a balance subtracts this.
        """
        result = await session.execute(
            select(
                func.coalesce(func.sum(LeaveRequestEntity.hours), Decimal("0.00"))
            ).where(
                LeaveRequestEntity.user_id == user_id,
                LeaveRequestEntity.type == LeaveRequestType.PAID,
                LeaveRequestEntity.status == LeaveRequestStatus.PENDING,
            )
        )
        return result.scalar_one()

    async def list_for_user(
        self, session: AsyncSession, user_id: int
    ) -> list[LeaveRequestEntity]:
        """One person's own requests, whatever their state.

        Args:
            session: Active async session.
            user_id: Whose requests.

        Returns:
            Newest first, by the day the leave starts.
        """
        result = await session.execute(
            select(LeaveRequestEntity)
            .where(LeaveRequestEntity.user_id == user_id)
            .order_by(
                LeaveRequestEntity.start_date.desc(),
                LeaveRequestEntity.leave_request_id.desc(),
            )
        )
        return list(result.scalars().all())

    async def list_for_approver(
        self,
        session: AsyncSession,
        approver_user_id: int,
        statuses: list[LeaveRequestStatus],
    ) -> list[LeaveRequestEntity]:
        """Requests pointing at one approver, in the states asked for.

        The approver is a snapshot taken when the request was submitted, so a
        change of manager leaves history pointing at whoever actually decided.

        Args:
            session: Active async session.
            approver_user_id: The approver.
            statuses: Which states to include.

        Returns:
            Oldest first: a queue is worked from the front.
        """
        result = await session.execute(
            select(LeaveRequestEntity)
            .where(
                LeaveRequestEntity.approver_user_id == approver_user_id,
                LeaveRequestEntity.status.in_(statuses),
            )
            .order_by(LeaveRequestEntity.leave_request_id)
        )
        return list(result.scalars().all())
