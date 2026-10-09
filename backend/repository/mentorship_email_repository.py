from collections.abc import Collection
from datetime import datetime, timedelta

from sqlalchemy import func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from backend.common.mentorship_email_enums import (
    MentorshipEmailRecipientResult,
    MentorshipEmailSendStatus,
)
from backend.entity.mentorship_email_recipient_entity import (
    MentorshipEmailRecipientEntity,
)
from backend.entity.mentorship_email_send_entity import MentorshipEmailSendEntity
from backend.entity.users_entity import UsersEntity


class MentorshipEmailRepository:
    """Storage for Kit sends and their recipients. Never commits -- the calling
    service owns the transaction."""

    async def create_send(
        self,
        session: AsyncSession,
        *,
        round_id: int,
        stage: str,
        kit_draft_id: int,
        kit_draft_subject: str,
        created_by: int,
        sender_address: str,
        kit_tag_name: str,
        kit_tag_id: int,
        kit_broadcast_id: int,
        recipients: list[tuple[int, str | None]],
    ) -> MentorshipEmailSendEntity:
        send = MentorshipEmailSendEntity(
            round_id=round_id,
            stage=stage,
            kit_draft_id=kit_draft_id,
            kit_draft_subject=kit_draft_subject,
            created_by=created_by,
            sender_address=sender_address,
            kit_tag_name=kit_tag_name,
            kit_tag_id=kit_tag_id,
            kit_broadcast_id=kit_broadcast_id,
            status=MentorshipEmailSendStatus.DRAFT,
            tag_deleted=False,
        )
        session.add(send)
        await session.flush()
        for user_id, email in recipients:
            session.add(
                MentorshipEmailRecipientEntity(
                    send_id=send.send_id,
                    user_id=user_id,
                    email=email,
                    result=MentorshipEmailRecipientResult.PENDING
                    if email
                    else MentorshipEmailRecipientResult.IMPORT_FAILED,
                    failure_reason=None if email else "no_email",
                )
            )
        await session.flush()
        return send

    async def get_send(
        self, session: AsyncSession, send_id: int, *, for_update: bool = False
    ) -> MentorshipEmailSendEntity | None:
        stmt = (
            select(MentorshipEmailSendEntity)
            .where(MentorshipEmailSendEntity.send_id == send_id)
            .execution_options(populate_existing=True)
        )
        if for_update:
            stmt = stmt.with_for_update()
        return (await session.execute(stmt)).scalar_one_or_none()

    async def list_sends(
        self,
        session: AsyncSession,
        round_id: int,
        statuses: Collection[MentorshipEmailSendStatus],
    ) -> list[MentorshipEmailSendEntity]:
        stmt = (
            select(MentorshipEmailSendEntity)
            .where(
                MentorshipEmailSendEntity.round_id == round_id,
                MentorshipEmailSendEntity.status.in_(list(statuses)),
            )
            .order_by(MentorshipEmailSendEntity.send_id)
        )
        return list((await session.execute(stmt)).scalars())

    async def list_sent_stages(
        self, session: AsyncSession, round_id: int
    ) -> list[tuple[int, str]]:
        """(user_id, stage) pairs that Kit actually sent in this round: the send
        finished and this person was handed to Kit as an active subscriber."""
        stmt = (
            select(
                MentorshipEmailRecipientEntity.user_id,
                MentorshipEmailSendEntity.stage,
            )
            .join(
                MentorshipEmailSendEntity,
                MentorshipEmailSendEntity.send_id
                == MentorshipEmailRecipientEntity.send_id,
            )
            .where(
                MentorshipEmailSendEntity.round_id == round_id,
                MentorshipEmailSendEntity.status == MentorshipEmailSendStatus.SENT,
                MentorshipEmailRecipientEntity.result
                == MentorshipEmailRecipientResult.HANDED_TO_KIT,
            )
            .distinct()
            .order_by(
                MentorshipEmailRecipientEntity.user_id,
                MentorshipEmailSendEntity.stage,
            )
        )
        return [
            (user_id, stage) for user_id, stage in (await session.execute(stmt)).all()
        ]

    async def list_scheduled_stages(
        self, session: AsyncSession, round_id: int
    ) -> list[tuple[int, str, datetime]]:
        """(user_id, stage, send_at) for every send of this round that was
        confirmed but not yet sent by Kit, leaving out the people Kit will not
        reach. A send still importing counts: its recipients not yet handed to
        Kit are still pending."""
        stmt = (
            select(
                MentorshipEmailRecipientEntity.user_id,
                MentorshipEmailSendEntity.stage,
                MentorshipEmailSendEntity.send_at,
            )
            .join(
                MentorshipEmailSendEntity,
                MentorshipEmailSendEntity.send_id
                == MentorshipEmailRecipientEntity.send_id,
            )
            .where(
                MentorshipEmailSendEntity.round_id == round_id,
                MentorshipEmailSendEntity.status.in_([
                    MentorshipEmailSendStatus.PREPARING,
                    MentorshipEmailSendStatus.SCHEDULED,
                ]),
                MentorshipEmailSendEntity.send_at.is_not(None),
                MentorshipEmailRecipientEntity.result.in_([
                    MentorshipEmailRecipientResult.PENDING,
                    MentorshipEmailRecipientResult.HANDED_TO_KIT,
                ]),
            )
            .order_by(
                MentorshipEmailRecipientEntity.user_id,
                MentorshipEmailSendEntity.send_at,
                MentorshipEmailSendEntity.stage,
            )
        )
        return [tuple(row) for row in (await session.execute(stmt)).all()]

    async def list_recipients(
        self, session: AsyncSession, send_id: int
    ) -> list[MentorshipEmailRecipientEntity]:
        stmt = (
            select(MentorshipEmailRecipientEntity)
            .where(MentorshipEmailRecipientEntity.send_id == send_id)
            .order_by(MentorshipEmailRecipientEntity.recipient_id)
        )
        return list((await session.execute(stmt)).scalars())

    async def list_pending_recipients(
        self, session: AsyncSession, send_id: int
    ) -> list[MentorshipEmailRecipientEntity]:
        stmt = (
            select(MentorshipEmailRecipientEntity)
            .where(
                MentorshipEmailRecipientEntity.send_id == send_id,
                MentorshipEmailRecipientEntity.result
                == MentorshipEmailRecipientResult.PENDING,
            )
            .order_by(MentorshipEmailRecipientEntity.recipient_id)
        )
        return list((await session.execute(stmt)).scalars())

    async def list_pending_recipients_with_greeting_name(
        self, session: AsyncSession, send_id: int
    ) -> list[tuple[MentorshipEmailRecipientEntity, str | None]]:
        """Pending recipients with the name Kit greets them by: the preferred
        name when set, else the first name."""
        stmt = (
            select(
                MentorshipEmailRecipientEntity,
                UsersEntity.preferred_name,
                UsersEntity.first_name,
            )
            .join(
                UsersEntity,
                UsersEntity.user_id == MentorshipEmailRecipientEntity.user_id,
            )
            .where(
                MentorshipEmailRecipientEntity.send_id == send_id,
                MentorshipEmailRecipientEntity.result
                == MentorshipEmailRecipientResult.PENDING,
            )
            .order_by(MentorshipEmailRecipientEntity.recipient_id)
        )
        return [
            (row, (preferred or "").strip() or first)
            for row, preferred, first in (await session.execute(stmt)).all()
        ]

    async def list_unreached_recipients_with_users(
        self, session: AsyncSession, send_id: int
    ) -> list[tuple[MentorshipEmailRecipientEntity, UsersEntity]]:
        """Recipients that were not handed to Kit, with their user rows."""
        stmt = (
            select(MentorshipEmailRecipientEntity, UsersEntity)
            .join(
                UsersEntity,
                UsersEntity.user_id == MentorshipEmailRecipientEntity.user_id,
            )
            .where(
                MentorshipEmailRecipientEntity.send_id == send_id,
                MentorshipEmailRecipientEntity.result.in_(
                    MentorshipEmailRecipientResult.unreachable()
                ),
            )
            .order_by(MentorshipEmailRecipientEntity.recipient_id)
        )
        return [(row, user) for row, user in (await session.execute(stmt)).all()]

    async def count_by_result(
        self, session: AsyncSession, send_id: int
    ) -> dict[MentorshipEmailRecipientResult, int]:
        stmt = (
            select(MentorshipEmailRecipientEntity.result, func.count())
            .where(MentorshipEmailRecipientEntity.send_id == send_id)
            .group_by(MentorshipEmailRecipientEntity.result)
        )
        counts = {r: 0 for r in MentorshipEmailRecipientResult}
        for result, n in (await session.execute(stmt)).all():
            counts[result] = n
        return counts

    async def claim_for_prepare(
        self, session: AsyncSession, send_id: int, *, now: datetime, lease: timedelta
    ) -> bool:
        """Take the prepare lease for one send. Succeeds when nobody holds it or
        the holder has gone quiet for longer than `lease` (a killed pod)."""
        stmt = (
            update(MentorshipEmailSendEntity)
            .where(
                MentorshipEmailSendEntity.send_id == send_id,
                MentorshipEmailSendEntity.status == MentorshipEmailSendStatus.PREPARING,
                or_(
                    MentorshipEmailSendEntity.prepare_claimed_at.is_(None),
                    MentorshipEmailSendEntity.prepare_claimed_at < now - lease,
                ),
            )
            .values(prepare_claimed_at=now, updated_at=now)
            .returning(MentorshipEmailSendEntity.send_id)
            .execution_options(synchronize_session=False)
        )
        claimed = (await session.execute(stmt)).scalar_one_or_none() is not None
        if claimed:
            send = await session.get(MentorshipEmailSendEntity, send_id)
            if send is not None:
                await session.refresh(send)
        return claimed

    async def recent_recipient_user_ids(
        self,
        session: AsyncSession,
        *,
        round_id: int,
        stage: str,
        since: datetime,
        exclude_send_id: int,
    ) -> set[int]:
        stmt = (
            select(MentorshipEmailRecipientEntity.user_id)
            .join(
                MentorshipEmailSendEntity,
                MentorshipEmailSendEntity.send_id
                == MentorshipEmailRecipientEntity.send_id,
            )
            .where(
                MentorshipEmailSendEntity.round_id == round_id,
                MentorshipEmailSendEntity.stage == stage,
                MentorshipEmailSendEntity.send_id != exclude_send_id,
                MentorshipEmailSendEntity.status.in_([
                    MentorshipEmailSendStatus.SCHEDULED,
                    MentorshipEmailSendStatus.SENT,
                ]),
                MentorshipEmailSendEntity.created_at >= since,
                MentorshipEmailRecipientEntity.result
                == MentorshipEmailRecipientResult.HANDED_TO_KIT,
            )
        )
        return set((await session.execute(stmt)).scalars())
