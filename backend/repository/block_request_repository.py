from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from backend.common.user_enums import BlockRequestStatus
from backend.entity.block_request_entity import BlockRequestEntity


class BlockRequestRepository:
    """
    Repository for block_request rows. Storage only: who may decide a request
    and who may reassign it are service-layer rules, not conditions here.
    """

    async def create(
        self,
        session: AsyncSession,
        *,
        target_user_id: int,
        raised_by: int,
        raised_from: str,
        reason: str,
        reviewer_id: int,
    ) -> BlockRequestEntity:
        """
        Open a pending request. Does not commit -- the calling service owns the
        transaction; the row is flushed so the caller gets its request_id.

        Args:
            session (AsyncSession): The active async database session.
            target_user_id (int): The user the request asks to block.
            raised_by (int): The user raising it.
            raised_from (str): The domain page it came from, for display.
            reason (str): Why the block is being asked for.
            reviewer_id (int): The USER_ADMIN holder named to decide it.

        Returns:
            BlockRequestEntity: The new pending row.
        """
        row = BlockRequestEntity(
            target_user_id=target_user_id,
            raised_by=raised_by,
            raised_from=raised_from,
            reason=reason,
            reviewer_id=reviewer_id,
            status=BlockRequestStatus.PENDING,
        )
        session.add(row)
        await session.flush()
        return row

    async def get(
        self, session: AsyncSession, request_id: int
    ) -> BlockRequestEntity | None:
        """
        One request by id, whatever its status.

        Args:
            session (AsyncSession): The active async database session.
            request_id (int): The request to fetch.

        Returns:
            BlockRequestEntity | None: The row, or None when there is no such
                request.
        """
        result = await session.execute(
            select(BlockRequestEntity).where(
                BlockRequestEntity.request_id == request_id
            )
        )
        return result.scalars().one_or_none()

    async def get_pending_for_target(
        self, session: AsyncSession, target_user_id: int
    ) -> BlockRequestEntity | None:
        """
        The open request against a user, if there is one. Used both to keep a
        second request from being raised and to supersede the open one when an
        operator blocks the target directly.

        Args:
            session (AsyncSession): The active async database session.
            target_user_id (int): The user the request is against.

        Returns:
            BlockRequestEntity | None: The oldest pending row, or None.
        """
        result = await session.execute(
            select(BlockRequestEntity)
            .where(
                BlockRequestEntity.target_user_id == target_user_id,
                BlockRequestEntity.status == BlockRequestStatus.PENDING,
            )
            .order_by(BlockRequestEntity.created_at)
        )
        return result.scalars().first()

    async def list_pending_for_reviewer(
        self, session: AsyncSession, reviewer_id: int
    ) -> list[BlockRequestEntity]:
        """
        The requests this reviewer still has to decide. Scoped to the named
        reviewer: a request is addressed to one person, and a queue addressed
        to a permission is a queue addressed to nobody.

        Args:
            session (AsyncSession): The active async database session.
            reviewer_id (int): The named reviewer.

        Returns:
            list[BlockRequestEntity]: Pending rows, oldest first.
        """
        result = await session.execute(
            select(BlockRequestEntity)
            .where(
                BlockRequestEntity.reviewer_id == reviewer_id,
                BlockRequestEntity.status == BlockRequestStatus.PENDING,
            )
            .order_by(BlockRequestEntity.created_at)
        )
        return list(result.scalars().all())

    async def set_reviewer(
        self, session: AsyncSession, request_id: int, reviewer_id: int
    ) -> None:
        """
        Hand a pending request to a different reviewer. No extra column: the
        move lives in the event log, not in the row.

        Args:
            session (AsyncSession): The active async database session.
            request_id (int): The request to reassign.
            reviewer_id (int): The reviewer to hand it to.
        """
        await session.execute(
            update(BlockRequestEntity)
            .where(BlockRequestEntity.request_id == request_id)
            .values(reviewer_id=reviewer_id)
        )

    async def close(
        self,
        session: AsyncSession,
        request_id: int,
        *,
        status: BlockRequestStatus,
        decided_by: int,
        decision_note: str | None,
    ) -> None:
        """
        Close a request with a terminal status. Does not commit -- the calling
        service owns the transaction.

        Args:
            session (AsyncSession): The active async database session.
            request_id (int): The request to close.
            status (BlockRequestStatus): The terminal status. SUPERSEDED is not
                a decision, but it is still recorded with the actor whose direct
                block closed it.
            decided_by (int): The user whose action closed it.
            decision_note (str | None): Free-text note on the decision.
        """
        await session.execute(
            update(BlockRequestEntity)
            .where(BlockRequestEntity.request_id == request_id)
            .values(
                status=status,
                decided_by=decided_by,
                decided_at=func.now(),
                decision_note=decision_note,
            )
        )
