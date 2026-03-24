from backend.entity.mentorship_pairs_entity import MentorshipPairsEntity
from backend.entity.users_entity import UsersEntity
from sqlalchemy import select, or_, case, update, func, cast, type_coerce
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.dialects.postgresql import JSONB, array


class MentorshipPairsRepository:
    """
    Repository for handling database operations related to MentorshipPairsEntity.
    """

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

    async def get_partner_ids_by_user_and_round(
        self, session: AsyncSession, user_id: int, round_id: int
    ) -> list[int]:
        """
        Retrieve a list of unique partner IDs (mentors or mentees) for a given user ID
        within a specific mentorship round.

        This method identifies the user's role in each relationship for the given round:
        - If the user is the mentor, it returns the associated mentee's ID.
        - If the user is the mentee, it returns the associated mentor's ID.

        Args:
            session (AsyncSession): The active async database session.
            user_id (int): The ID of the user whose partners are being retrieved.
            round_id (int): The ID of the mentorship round to filter by.

        Returns:
            list[int]: A list of unique partner IDs whthin the specific round. Returns
                    an empty list if no partners are found or user_id/round_id is invalid.
        """
        if not user_id or not round_id:
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
                ),
                MentorshipPairsEntity.round_id == round_id,
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

    async def remove_meeting_from_log(
        self, session: AsyncSession, user_id: int, meeting_id: str
    ) -> bool:
        """
        Remove a meeting entry from the meeting_log JSONB field for a mentorship pair
        associated with the given user.

        Note:
            This method performs a direct database update. If callers need to access the
            latest pair data afterward from an already-loaded ORM object, they should call
            `session.refresh(...)` to ensure the entity reflects the updated state.

        Args:
            session (AsyncSession): Active async database session.
            user_id (int): Current user ID. Must match mentor_id or mentee_id.
            meeting_id (str): The meeting ID to remove.

        Returns:
            bool: True if a meeting was removed, otherwise False.
        """
        meeting_elements = (
            func.jsonb_array_elements(
                MentorshipPairsEntity.meeting_log["google_meetings"]
            )
            .table_valued("value")
            .alias("meeting_elements")
        )

        filtered_meeting_list = (
            select(
                func.coalesce(
                    func.jsonb_agg(meeting_elements.c.value),
                    type_coerce([], JSONB),
                )
            )
            .select_from(meeting_elements)
            .where(cast(meeting_elements.c.value, JSONB)["meeting_id"].astext != meeting_id)
            .scalar_subquery()
        )

        target_meeting_json = {
            "google_meetings": [{"meeting_id": meeting_id}]
        }

        stmt = (
            update(MentorshipPairsEntity)
            .where(
                or_(
                    MentorshipPairsEntity.mentor_id == user_id,
                    MentorshipPairsEntity.mentee_id == user_id,
                ),
                MentorshipPairsEntity.meeting_log.contains(
                    target_meeting_json
                ),
            )
            .values(
                meeting_log=func.jsonb_set(
                    MentorshipPairsEntity.meeting_log,
                    array(["google_meetings"]),
                    filtered_meeting_list,
                    False,
                )
            )
            .returning(MentorshipPairsEntity.pair_id)
        )

        result = await session.execute(stmt)
        return result.scalar_one_or_none() is not None
