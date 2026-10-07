from collections.abc import Collection

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from backend.common.approval_enums import ApprovalRequestStatus
from backend.entity.approval_request_entity import ApprovalRequestEntity


class ApprovalRequestRepository:
    """
    Repository for approval_request rows. Storage only: who may raise, decide,
    reassign or withdraw a request are rules of the approval service and its
    handlers, not conditions here.
    """

    async def create(
        self,
        session: AsyncSession,
        *,
        action: str,
        target_type: str,
        target_id: str,
        payload: dict,
        reason: str | None,
        raised_by: int,
        reviewer_id: int,
    ) -> ApprovalRequestEntity:
        """
        Open a pending request. Does not commit -- the calling service owns the
        transaction; the row is flushed so the caller gets its request_id, and
        so a second pending request on the same target fails here.

        Args:
            session (AsyncSession): The active async database session.
            action (str): What is being asked for.
            target_type (str): The kind of thing it is about.
            target_id (str): Which one.
            payload (dict): Whatever else the action needs, fixed from now on.
            reason (str | None): Why the raiser is asking.
            raised_by (int): The user raising it.
            reviewer_id (int): The user named to decide it.

        Returns:
            ApprovalRequestEntity: The new pending row.

        Raises:
            sqlalchemy.exc.IntegrityError: When the target already has a
                pending request for this action.
        """
        row = ApprovalRequestEntity(
            action=action,
            target_type=target_type,
            target_id=target_id,
            payload=payload,
            reason=reason,
            raised_by=raised_by,
            reviewer_id=reviewer_id,
            status=ApprovalRequestStatus.PENDING,
        )
        session.add(row)
        await session.flush()
        return row

    async def get(
        self, session: AsyncSession, request_id: int, *, for_update: bool = False
    ) -> ApprovalRequestEntity | None:
        """
        One request by id, whatever its status.

        Args:
            session (AsyncSession): The active async database session.
            request_id (int): The request to fetch.
            for_update (bool): Lock the row until the transaction ends, so a
                decision, a reassignment and a withdrawal cannot interleave.

        Returns:
            ApprovalRequestEntity | None: The row, or None when there is no
                such request.
        """
        stmt = select(ApprovalRequestEntity).where(
            ApprovalRequestEntity.request_id == request_id
        )
        if for_update:
            stmt = stmt.with_for_update()
        result = await session.execute(stmt)
        return result.scalars().one_or_none()

    async def get_pending_for_target(
        self, session: AsyncSession, action: str, target_type: str, target_id: str
    ) -> ApprovalRequestEntity | None:
        """
        The request this target is waiting on for this action, if any. The
        partial unique index guarantees there is at most one.

        Args:
            session (AsyncSession): The active async database session.
            action (str): The action.
            target_type (str): The kind of target.
            target_id (str): The target.

        Returns:
            ApprovalRequestEntity | None: The pending row, or None.
        """
        result = await session.execute(
            select(ApprovalRequestEntity).where(
                ApprovalRequestEntity.action == action,
                ApprovalRequestEntity.target_type == target_type,
                ApprovalRequestEntity.target_id == target_id,
                ApprovalRequestEntity.status == ApprovalRequestStatus.PENDING,
            )
        )
        return result.scalars().one_or_none()

    async def list_pending_for_targets(
        self,
        session: AsyncSession,
        action: str,
        target_type: str,
        target_ids: Collection[str],
    ) -> list[ApprovalRequestEntity]:
        """The pending requests on any of these targets, for a list that
        shows each row's request beside it.

        Args:
            session (AsyncSession): The active async database session.
            action (str): The action.
            target_type (str): The kind of target.
            target_ids (Collection[str]): The targets.

        Returns:
            list[ApprovalRequestEntity]: At most one per target.
        """
        if not target_ids:
            return []
        result = await session.execute(
            select(ApprovalRequestEntity).where(
                ApprovalRequestEntity.action == action,
                ApprovalRequestEntity.target_type == target_type,
                ApprovalRequestEntity.target_id.in_(list(target_ids)),
                ApprovalRequestEntity.status == ApprovalRequestStatus.PENDING,
            )
        )
        return list(result.scalars().all())

    async def get_latest_closed_for_target(
        self, session: AsyncSession, action: str, target_type: str, target_id: str
    ) -> ApprovalRequestEntity | None:
        """
        The most recently closed request on this target for this action, so
        a page can show why the last one was turned down.

        Args:
            session (AsyncSession): The active async database session.
            action (str): The action.
            target_type (str): The kind of target.
            target_id (str): The target.

        Returns:
            ApprovalRequestEntity | None: The newest non-pending row, or None.
        """
        result = await session.execute(
            select(ApprovalRequestEntity)
            .where(
                ApprovalRequestEntity.action == action,
                ApprovalRequestEntity.target_type == target_type,
                ApprovalRequestEntity.target_id == target_id,
                ApprovalRequestEntity.status != ApprovalRequestStatus.PENDING,
            )
            .order_by(
                ApprovalRequestEntity.decided_at.desc().nulls_last(),
                ApprovalRequestEntity.request_id.desc(),
            )
            .limit(1)
        )
        return result.scalars().one_or_none()

    async def list_pending_for_reviewer(
        self, session: AsyncSession, reviewer_id: int, actions: Collection[str]
    ) -> list[ApprovalRequestEntity]:
        """
        The requests of these actions this reviewer still has to decide.

        Args:
            session (AsyncSession): The active async database session.
            reviewer_id (int): The named reviewer.
            actions (Collection[str]): Which actions to include, so each page
                lists only its own.

        Returns:
            list[ApprovalRequestEntity]: Pending rows, oldest first.
        """
        if not actions:
            return []
        result = await session.execute(
            select(ApprovalRequestEntity)
            .where(
                ApprovalRequestEntity.reviewer_id == reviewer_id,
                ApprovalRequestEntity.status == ApprovalRequestStatus.PENDING,
                ApprovalRequestEntity.action.in_(list(actions)),
            )
            .order_by(
                ApprovalRequestEntity.created_at, ApprovalRequestEntity.request_id
            )
        )
        return list(result.scalars().all())

    async def list_pending_raised_by(
        self, session: AsyncSession, raised_by: int, actions: Collection[str]
    ) -> list[ApprovalRequestEntity]:
        """
        The open requests of these actions this person raised.

        Args:
            session (AsyncSession): The active async database session.
            raised_by (int): The person who raised them.
            actions (Collection[str]): Which actions to include.

        Returns:
            list[ApprovalRequestEntity]: Pending rows, oldest first.
        """
        if not actions:
            return []
        result = await session.execute(
            select(ApprovalRequestEntity)
            .where(
                ApprovalRequestEntity.raised_by == raised_by,
                ApprovalRequestEntity.status == ApprovalRequestStatus.PENDING,
                ApprovalRequestEntity.action.in_(list(actions)),
            )
            .order_by(
                ApprovalRequestEntity.created_at, ApprovalRequestEntity.request_id
            )
        )
        return list(result.scalars().all())

    async def set_reviewer(
        self, session: AsyncSession, request_id: int, reviewer_id: int
    ) -> bool:
        """
        Hand a pending request to a different reviewer. The move itself lives
        in the event log, not in the row.

        Args:
            session (AsyncSession): The active async database session.
            request_id (int): The request to reassign.
            reviewer_id (int): The reviewer to hand it to.

        Returns:
            bool: True if the move landed, False if the request was closed
                first.
        """
        result = await session.execute(
            update(ApprovalRequestEntity)
            .where(
                ApprovalRequestEntity.request_id == request_id,
                ApprovalRequestEntity.status == ApprovalRequestStatus.PENDING,
            )
            .values(reviewer_id=reviewer_id)
        )
        return result.rowcount == 1

    async def close(
        self,
        session: AsyncSession,
        request_id: int,
        *,
        status: ApprovalRequestStatus,
        decided_by: int,
        decision_comment: str | None,
    ) -> bool:
        """
        Close a pending request. Does not commit -- the calling service owns
        the transaction.

        Only a PENDING row is closed, and the caller is told whether one was,
        so two closes racing each other cannot both apply.

        Args:
            session (AsyncSession): The active async database session.
            request_id (int): The request to close.
            status (ApprovalRequestStatus): The terminal status.
            decided_by (int): The user whose action closed it.
            decision_comment (str | None): The reason given, if any.

        Returns:
            bool: True if this call closed the request, False if it was
                already closed.
        """
        result = await session.execute(
            update(ApprovalRequestEntity)
            .where(
                ApprovalRequestEntity.request_id == request_id,
                ApprovalRequestEntity.status == ApprovalRequestStatus.PENDING,
            )
            .values(
                status=status,
                decided_by=decided_by,
                decided_at=func.now(),
                decision_comment=decision_comment,
            )
        )
        return result.rowcount == 1
