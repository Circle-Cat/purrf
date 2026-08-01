from backend.entity.mentorship_pairs_entity import MentorshipPairsEntity
from backend.entity.users_entity import UsersEntity
from sqlalchemy import select, or_, case, func
from sqlalchemy.ext.asyncio import AsyncSession
from backend.common.mentorship_enums import PairStatus


class MentorshipPairsRepository:
    """
    Repository for handling database operations related to MentorshipPairsEntity.
    """

    async def get_pair_stats(self, session: AsyncSession) -> dict[int, dict]:
        """
        Retrieve matched participant count and completed meeting count per round,
        considering only active pairs.

        Returns:
            dict[int, dict]: Mapping of round_id to
                {"active_pairs": int, "matched_participants": int, "total_completed_meetings": int}.
        """
        result = await session.execute(
            select(
                MentorshipPairsEntity.round_id,
                func.count().label("active_pairs"),
                (
                    func.count(func.distinct(MentorshipPairsEntity.mentor_id))
                    + func.count(func.distinct(MentorshipPairsEntity.mentee_id))
                ).label("matched_participants"),
                func.sum(MentorshipPairsEntity.completed_count).label(
                    "total_completed_meetings"
                ),
            )
            .where(MentorshipPairsEntity.status == PairStatus.ACTIVE)
            .group_by(MentorshipPairsEntity.round_id)
        )
        return {
            row.round_id: {
                "active_pairs": row.active_pairs,
                "matched_participants": row.matched_participants,
                "total_completed_meetings": row.total_completed_meetings or 0,
            }
            for row in result.all()
        }

    async def get_all_partner_ids(
        self, session: AsyncSession, user_id: int
    ) -> list[int]:
        """
        Retrieve a list of unique partner IDs (mentors or mentees) for a given user ID.

        This method identifies the user's role in each relationship:
        - If the user is the mentor, it returns the associated mentee's ID.
        - If the user is the mentee, it returns the associated mentor's ID.

        Args:
            session (AsyncSession): The active async database session.
            user_id (int): The ID of the user whose partners are being retrieved.

        Returns:
            list[int]: A list of unique partner IDs. Returns an empty list if
                    no partners are found or user_id is invalid.
        """
        if not user_id:
            return []

        partner_id_case = case(
            (
                MentorshipPairsEntity.mentor_id == user_id,
                MentorshipPairsEntity.mentee_id,
            ),
            else_=MentorshipPairsEntity.mentor_id,
        ).label("partner_id")

        result = await session.execute(
            select(partner_id_case)
            .where(
                or_(
                    MentorshipPairsEntity.mentor_id == user_id,
                    MentorshipPairsEntity.mentee_id == user_id,
                )
            )
            .distinct()
        )

        return result.scalars().all()

    async def upsert_pairs(
        self, session: AsyncSession, entity: MentorshipPairsEntity
    ) -> MentorshipPairsEntity:
        """
        Inserts or updates a MentorshipPairsEntity in the database.

        Args:
            session (AsyncSession): Active async database session.
            entity (MentorshipPairsEntity): The entity containing pairs data.

        Returns:
            MentorshipPairsEntity: The merged entity instance synchronized with the session.
        """
        merged_entity = await session.merge(entity)
        await session.flush()

        return merged_entity

    async def upsert_pairs_batch(
        self, session: AsyncSession, entities: list[MentorshipPairsEntity]
    ) -> list[MentorshipPairsEntity]:
        """
        Inserts or updates multiple MentorshipPairsEntity rows with a single flush.

        Args:
            session (AsyncSession): Active async database session.
            entities (list[MentorshipPairsEntity]): Entities to upsert.

        Returns:
            list[MentorshipPairsEntity]: The merged entity instances.
        """
        merged = [await session.merge(entity) for entity in entities]
        await session.flush()
        return merged

    async def get_pairs_with_partner_info(
        self, session: AsyncSession, user_id: int, round_id: int
    ) -> list[tuple[MentorshipPairsEntity, UsersEntity]]:
        """
        Retrieve all mentorship pairs for a given user in a specific round,
        along with the corresponding partner's user information.

        This query returns each mentorship pair where the given user participates
        either as a mentor or a mentee, and joins the UsersEntity table to fetch
        the *other* participant (i.e., the partner) in the pair.

        Args:
            session (AsyncSession): The SQLAlchemy async session used to execute the query.
            user_id (int): The ID of the current user (mentor or mentee).
            round_id (int): The mentorship round ID to filter pairs.

        Returns:
            list[tuple[MentorshipPairsEntity, UsersEntity]]:
                A list of tuples where:
                - The first element is a MentorshipPairsEntity representing the pairing.
                - The second element is a UsersEntity representing the partner user.
        """
        stmt = (
            select(MentorshipPairsEntity, UsersEntity)
            .join(
                UsersEntity,
                case(
                    (
                        MentorshipPairsEntity.mentor_id == user_id,
                        UsersEntity.user_id == MentorshipPairsEntity.mentee_id,
                    ),
                    else_=UsersEntity.user_id == MentorshipPairsEntity.mentor_id,
                ),
            )
            .where(
                MentorshipPairsEntity.round_id == round_id,
                or_(
                    MentorshipPairsEntity.mentor_id == user_id,
                    MentorshipPairsEntity.mentee_id == user_id,
                ),
            )
        )
        result = await session.execute(stmt)
        return result.all()

    async def get_pairs_by_user_and_round(
        self, session: AsyncSession, user_id: int, round_id: int
    ) -> list[MentorshipPairsEntity]:
        if not user_id or not round_id:
            return []

        result = await session.execute(
            select(MentorshipPairsEntity).where(
                MentorshipPairsEntity.round_id == round_id,
                or_(
                    MentorshipPairsEntity.mentor_id == user_id,
                    MentorshipPairsEntity.mentee_id == user_id,
                ),
            )
        )

        return result.scalars().all()

    async def get_pair_by_id(
        self, session: AsyncSession, pair_id: int, *, with_lock: bool = False
    ) -> MentorshipPairsEntity | None:
        """
        Fetch a mentorship pair by its pair ID.

        Args:
            session (AsyncSession): Active database async session.
            pair_id (int): ID of the mentorship pair.
            with_lock (bool): If True, acquires a FOR UPDATE row lock to
                serialize concurrent admin writes to this pair.

        Returns:
            MentorshipPairsEntity | None: The matching pair, or None if not found.
        """
        stmt = select(MentorshipPairsEntity).where(
            MentorshipPairsEntity.pair_id == pair_id
        )
        if with_lock:
            stmt = stmt.with_for_update(of=MentorshipPairsEntity)
        result = await session.execute(stmt)
        return result.scalars().one_or_none()

    async def get_pair_by_mentee_and_round(
        self, session: AsyncSession, mentee_id: int, round_id: int
    ) -> MentorshipPairsEntity | None:
        result = await session.execute(
            select(MentorshipPairsEntity).where(
                MentorshipPairsEntity.round_id == round_id,
                MentorshipPairsEntity.mentee_id == mentee_id,
            )
        )

        return result.scalars().one_or_none()

    async def get_pair_with_partner_by_round_and_users_and_status(
        self,
        session: AsyncSession,
        round_id: int,
        user_id: int,
        partner_id: int,
        status: PairStatus,
        with_lock: bool = False,
    ) -> tuple[MentorshipPairsEntity, UsersEntity] | None:
        """
        Retrieve a mentorship pair and the corresponding partner user
        by round, user IDs, and status.

        This method searches for a mentorship pair within a specific round
        where the given two users are matched (regardless of mentor/mentee order)
        and the pair has the specified status. If a match is found, it also
        returns the partner user's entity.

        Args:
            session (AsyncSession): The active database session.
            round_id (int): The round identifier to filter pairs.
            user_id (int): The current user's ID.
            partner_id (int): The partner user's ID.
            status (PairStatus): The expected status of the mentorship pair.
            with_lock (bool): If True, acquires a FOR UPDATE row lock on the pair row
                to prevent concurrent status changes until the transaction commits.

        Returns:
            tuple[MentorshipPairsEntity, UsersEntity] | None:
                A tuple containing:
                    - MentorshipPairsEntity: The matched mentorship pair.
                    - UsersEntity: The partner user's entity.
                Returns None if no matching pair is found.
        """
        partner_join_condition = UsersEntity.user_id == case(
            (
                MentorshipPairsEntity.mentor_id == user_id,
                MentorshipPairsEntity.mentee_id,
            ),
            else_=MentorshipPairsEntity.mentor_id,
        )

        stmt = (
            select(MentorshipPairsEntity, UsersEntity)
            .join(UsersEntity, partner_join_condition)
            .where(
                MentorshipPairsEntity.round_id == round_id,
                MentorshipPairsEntity.status == status,
                or_(
                    (MentorshipPairsEntity.mentor_id == user_id)
                    & (MentorshipPairsEntity.mentee_id == partner_id),
                    (MentorshipPairsEntity.mentor_id == partner_id)
                    & (MentorshipPairsEntity.mentee_id == user_id),
                ),
            )
        )

        if with_lock:
            stmt = stmt.with_for_update(of=MentorshipPairsEntity)

        result = await session.execute(stmt)
        return result.one_or_none()

    async def get_active_pairs_by_round(
        self, session: AsyncSession, round_id: int
    ) -> list[MentorshipPairsEntity]:
        """
        Retrieve all active mentorship pairs for a given round.

        Args:
            session (AsyncSession): The active async database session.
            round_id (int): The mentorship round ID.

        Returns:
            list[MentorshipPairsEntity]: All active pairs in the round.
        """
        result = await session.execute(
            select(MentorshipPairsEntity).where(
                MentorshipPairsEntity.round_id == round_id,
                MentorshipPairsEntity.status == PairStatus.ACTIVE,
            )
        )

        return result.scalars().all()
