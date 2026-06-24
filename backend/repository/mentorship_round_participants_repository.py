from backend.entity.mentorship_round_entity import MentorshipRoundEntity
from backend.entity.mentorship_round_participants_entity import (
    MentorshipRoundParticipantsEntity,
)
from backend.entity.mentorship_pairs_entity import MentorshipPairsEntity
from backend.entity.users_entity import UsersEntity
from backend.entity.user_emails_entity import UserEmailsEntity
from backend.common.mentorship_enums import ParticipantRole
from backend.dto.participant_search_row_dto import ParticipantSearchRow
from backend.dto.participant_search_filter_dto import ParticipantSearchFilterDto
from sqlalchemy import TIMESTAMP, Float, cast, func, select, and_, or_
from sqlalchemy.orm import aliased
from sqlalchemy.ext.asyncio import AsyncSession


class MentorshipRoundParticipantsRepository:
    """
    Repository for handling database operations related to MentorshipRoundParticipantsEntity.
    """

    async def get_by_user_id_and_round_id(
        self, session: AsyncSession, user_id: int, round_id: int
    ) -> MentorshipRoundParticipantsEntity | None:
        """
        Retrieve a mentorship round participant by user_id and round_id.

        Args:
            session (AsyncSession): The active async database session.
            user_id (int): User id.
            round_id (int): Mentorship round id.

        Returns:
            MentorshipRoundParticipantsEntity | None: The matching participant or None.
        """
        result = await session.execute(
            select(MentorshipRoundParticipantsEntity).where(
                and_(
                    MentorshipRoundParticipantsEntity.user_id == user_id,
                    MentorshipRoundParticipantsEntity.round_id == round_id,
                )
            )
        )

        return result.scalars().one_or_none()

    async def get_recent_participant_by_user_id(
        self, session: AsyncSession, user_id: int
    ) -> MentorshipRoundParticipantsEntity | None:
        """
        Retrieve the most recent mentorship round participant for a user,
        ordered by the round's meetings_completion_deadline_at descending.

        Rounds without meetings_completion_deadline_at are skipped because
        their timeline is not finalized.

        Args:
            session (AsyncSession): The active async database session.
            user_id (int): User id.

        Returns:
            MentorshipRoundParticipantsEntity | None: The matching participant or None.
        """
        result = await session.execute(
            select(MentorshipRoundParticipantsEntity)
            .join(
                MentorshipRoundEntity,
                MentorshipRoundEntity.round_id
                == MentorshipRoundParticipantsEntity.round_id,
            )
            .where(
                MentorshipRoundParticipantsEntity.user_id == user_id,
                MentorshipRoundEntity.description[
                    "meetings_completion_deadline_at"
                ].astext.isnot(None),
            )
            .order_by(
                cast(
                    MentorshipRoundEntity.description[
                        "meetings_completion_deadline_at"
                    ].astext,
                    TIMESTAMP(timezone=True),
                ).desc()
            )
            .limit(1)
        )

        return result.scalars().one_or_none()

    async def get_average_program_rating_by_round_and_role(
        self,
        session: AsyncSession,
        round_id: int,
        role: ParticipantRole,
    ) -> float:
        """
        Compute the average program_rating for all participants in a round with a specific role.

        Args:
            session (AsyncSession): The active async database session.
            round_id (int): Mentorship round id.
            role (ParticipantRole): The participant role to filter by.

        Returns:
            float: The average program_rating.
        """
        result = await session.execute(
            select(
                func.avg(
                    cast(
                        MentorshipRoundParticipantsEntity.program_feedback[
                            "program_rating"
                        ].astext,
                        Float,
                    )
                )
            ).where(
                and_(
                    MentorshipRoundParticipantsEntity.round_id == round_id,
                    MentorshipRoundParticipantsEntity.participant_role == role,
                    MentorshipRoundParticipantsEntity.program_feedback[
                        "program_rating"
                    ].astext.isnot(None),
                )
            )
        )
        return result.scalar_one_or_none()

    def _build_admin_search_stmt(self, filters) -> select:
        """
        Build the base SELECT statement for the admin participant search.

        Applies all filter conditions from the provided filter DTO.
        ORDER BY, LIMIT, and OFFSET are intentionally excluded so the
        same statement can be reused for both result queries and
        COUNT(*) subqueries.

        Args:
            filters (ParticipantSearchFilterDto): Filter parameters to apply.

        Returns:
            Select: A SQLAlchemy SELECT statement with all filter conditions applied.
        """
        stmt = (
            select(
                UsersEntity.user_id.label("user_id"),
                MentorshipRoundParticipantsEntity.round_id.label("round_id"),
                MentorshipPairsEntity.pair_id.label("pair_id"),
                MentorshipRoundParticipantsEntity.participant_role.label(
                    "participant_role"
                ),
                MentorshipRoundParticipantsEntity.approval_status.label(
                    "approval_status"
                ),
                MentorshipPairsEntity.completed_count.label("completed_count"),
                MentorshipPairsEntity.mentor_id.label("mentor_id"),
                MentorshipPairsEntity.mentee_id.label("mentee_id"),
            )
            .select_from(UsersEntity)
            .outerjoin(
                MentorshipRoundParticipantsEntity,
                MentorshipRoundParticipantsEntity.user_id == UsersEntity.user_id,
            )
            .outerjoin(
                MentorshipPairsEntity,
                and_(
                    or_(
                        MentorshipPairsEntity.mentor_id == UsersEntity.user_id,
                        MentorshipPairsEntity.mentee_id == UsersEntity.user_id,
                    ),
                    MentorshipPairsEntity.round_id
                    == MentorshipRoundParticipantsEntity.round_id,
                ),
            )
        )

        if filters.user_id is not None:
            stmt = stmt.where(UsersEntity.user_id == filters.user_id)

        if filters.participation_status == "participant":
            stmt = stmt.where(MentorshipRoundParticipantsEntity.user_id.is_not(None))
        elif filters.participation_status == "non_participant":
            stmt = stmt.where(MentorshipRoundParticipantsEntity.user_id.is_(None))

        if filters.name:
            pattern = f"%{filters.name}%"
            stmt = stmt.where(
                or_(
                    UsersEntity.first_name.ilike(pattern),
                    UsersEntity.last_name.ilike(pattern),
                    UsersEntity.preferred_name.ilike(pattern),
                )
            )

        if filters.email:
            pattern = f"%{filters.email}%"
            stmt = stmt.where(
                select(UserEmailsEntity.email_id)
                .where(
                    UserEmailsEntity.user_id == UsersEntity.user_id,
                    UserEmailsEntity.email.ilike(pattern),
                )
                .exists()
            )

        if filters.matched_user:
            pattern = f"%{filters.matched_user}%"
            PartnerUser = aliased(UsersEntity, name="partner")
            stmt = stmt.where(
                select(PartnerUser.user_id)
                .where(
                    or_(
                        PartnerUser.user_id == MentorshipPairsEntity.mentor_id,
                        PartnerUser.user_id == MentorshipPairsEntity.mentee_id,
                    ),
                    PartnerUser.user_id != UsersEntity.user_id,
                    or_(
                        PartnerUser.first_name.ilike(pattern),
                        PartnerUser.last_name.ilike(pattern),
                        PartnerUser.preferred_name.ilike(pattern),
                    ),
                )
                .exists()
            )

        if filters.round_id is not None:
            stmt = stmt.where(
                MentorshipRoundParticipantsEntity.round_id == filters.round_id
            )

        if filters.participant_role is not None:
            stmt = stmt.where(
                MentorshipRoundParticipantsEntity.participant_role
                == filters.participant_role
            )

        if filters.approval_status is not None:
            stmt = stmt.where(
                MentorshipRoundParticipantsEntity.approval_status
                == filters.approval_status
            )

        return stmt

    async def search_participants_for_admin(
        self,
        session: AsyncSession,
        filters: ParticipantSearchFilterDto,
        limit: int,
        offset: int,
    ) -> tuple[list[ParticipantSearchRow], int]:
        """
        Run the admin participant search and return paginated results.

        The same base query is reused for both the COUNT(*) query and the
        paginated data query to ensure consistent filtering.

        Args:
            session (AsyncSession): Active database session.
            filters (ParticipantSearchFilterDto): Filter parameters.
            limit (int): Maximum number of rows to return.
            offset (int): Number of rows to skip.

        Returns:
            tuple[list[ParticipantSearchRow], int]:
                Matching participant rows and the total number of matches
                before pagination.
        """
        base_stmt = self._build_admin_search_stmt(filters)

        total = (
            await session.scalar(select(func.count()).select_from(base_stmt.subquery()))
            or 0
        )

        data_stmt = (
            base_stmt.order_by(
                UsersEntity.last_name.asc().nulls_last(),
                UsersEntity.first_name.asc().nulls_last(),
                MentorshipRoundParticipantsEntity.round_id.asc().nulls_last(),
                MentorshipPairsEntity.pair_id.asc().nulls_last(),
                UsersEntity.user_id.asc(),
            )
            .limit(limit)
            .offset(offset)
        )
        result = await session.execute(data_stmt)
        rows = [
            ParticipantSearchRow(
                user_id=row.user_id,
                round_id=row.round_id,
                pair_id=row.pair_id,
                participant_role=row.participant_role,
                approval_status=row.approval_status,
                completed_count=row.completed_count,
                mentor_id=row.mentor_id,
                mentee_id=row.mentee_id,
            )
            for row in result.all()
        ]
        return rows, int(total)

    async def upsert_participant(
        self, session: AsyncSession, entity: MentorshipRoundParticipantsEntity
    ) -> MentorshipRoundParticipantsEntity:
        """
        Inserts or updates a MentorshipRoundParticipantsEntity in the database.

        Args:
            session (AsyncSession): Active async database session.
            entity (MentorshipRoundParticipantsEntity): The entity containing
                mentorship round participation data.

        Returns:
            MentorshipRoundParticipantsEntity: The merged entity instance synchronized with the session.
        """
        merged_entity = await session.merge(entity)
        await session.flush()

        return merged_entity
