from backend.entity.mentorship_pairs_entity import MentorshipPairsEntity
from backend.entity.users_entity import UsersEntity
from sqlalchemy import select, or_, case, update, func, cast, type_coerce, literal, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.dialects.postgresql import JSONB, array
from backend.common.mentorship_enums import PairStatus


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
            .where(
                cast(meeting_elements.c.value, JSONB)["meeting_id"].astext != meeting_id
            )
            .scalar_subquery()
        )

        target_meeting_json = {"google_meetings": [{"meeting_id": meeting_id}]}

        stmt = (
            update(MentorshipPairsEntity)
            .where(
                or_(
                    MentorshipPairsEntity.mentor_id == user_id,
                    MentorshipPairsEntity.mentee_id == user_id,
                ),
                MentorshipPairsEntity.meeting_log.contains(target_meeting_json),
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

    async def clear_google_meetings_by_user_pair_and_round(
        self,
        session: AsyncSession,
        current_user_id: int,
        partner_id: int,
        round_id: int,
    ) -> bool:
        """
        Clear the google_meetings list in meeting_log for a mentorship pair
        identified by two users within a given round.

        Note:
            This method performs a direct database update. If callers need to access the
            latest pair data afterward from an already-loaded ORM object, they should call
            `session.refresh(...)` to ensure the entity reflects the updated state.

        Args:
            session (AsyncSession): Active async database session.
            current_user_id (int): One user in the pair.
            partner_id (int): The other user in the pair.
            round_id (int): The mentorship round ID.

        Returns:
            bool: True if a pair was updated, otherwise False.
        """
        if not current_user_id or not partner_id or not round_id:
            raise ValueError("Invalid input parameters")

        stmt = (
            update(MentorshipPairsEntity)
            .where(
                MentorshipPairsEntity.round_id == round_id,
                MentorshipPairsEntity.mentor_id.in_([current_user_id, partner_id]),
                MentorshipPairsEntity.mentee_id.in_([current_user_id, partner_id]),
                MentorshipPairsEntity.mentor_id != MentorshipPairsEntity.mentee_id,
            )
            .values(
                meeting_log=func.jsonb_set(
                    func.coalesce(
                        func.nullif(
                            MentorshipPairsEntity.meeting_log,
                            cast(literal("null"), JSONB),
                        ),
                        type_coerce({}, JSONB),
                    ),
                    array(["google_meetings"]),
                    type_coerce([], JSONB),
                    True,
                )
            )
            .returning(MentorshipPairsEntity.pair_id)
        )

        result = await session.execute(stmt)
        return result.scalar_one_or_none() is not None

    async def append_google_meeting(
        self,
        session: AsyncSession,
        pair_id: int,
        meeting_entry: dict,
    ) -> None:
        """
        Append a Google Meet entry to the `meeting_log.google_meetings` array for a given pair.

        This method performs an atomic in-database update using PostgreSQL `jsonb_set`
        and concatenation (`||`) to safely append a new meeting record without triggering
        read-modify-write race conditions.

        If `meeting_log` or `google_meetings` does not exist, they will be initialized
        automatically.

        Args:
            session (AsyncSession):
                The SQLAlchemy async database session used to execute the update.

            pair_id (int):
                The unique identifier of the mentorship pair whose meeting log
                should be updated.

            meeting_entry (dict):
                A JSON-serializable dictionary representing a Google Meet record.
                This will be appended as a new element in the `google_meetings` array.

        Returns:
            None

        Raises:
            sqlalchemy.exc.SQLAlchemyError:
                If the database operation fails.

        Notes:
            - This operation is fully atomic at the database level and safe under concurrency.
            - Uses `jsonb_set` + `coalesce` to ensure missing fields are initialized.
            - Avoids loading the existing JSON into application memory.
        """
        stmt = (
            update(MentorshipPairsEntity)
            .where(MentorshipPairsEntity.pair_id == pair_id)
            .values(
                meeting_log=func.jsonb_set(
                    func.coalesce(
                        func.nullif(
                            MentorshipPairsEntity.meeting_log,
                            text("'null'::jsonb"),
                        ),
                        type_coerce({}, JSONB),
                    ),
                    array(["google_meetings"]),
                    func.coalesce(
                        MentorshipPairsEntity.meeting_log["google_meetings"],
                        type_coerce([], JSONB),
                    ).op("||")(
                        func.jsonb_build_array(type_coerce(meeting_entry, JSONB))
                    ),
                )
            )
        )
        await session.execute(stmt)

    async def do_google_meetings_exist_in_log(
        self,
        session: AsyncSession,
        user_id: int,
        round_id: int,
        partner_id: int,
        meeting_ids: list[str],
    ) -> bool:
        """
        Check whether all given Google meeting IDs exist in meeting_log for the
        specified mentorship pair.

        Args:
            session (AsyncSession): Active async database session.
            user_id (int): Current user ID.
            round_id (int): The mentorship round ID.
            partner_id (int): The partner user's ID.
            meeting_ids (list[str]): Google Calendar event IDs to check.

        Returns:
            bool: True if all meeting IDs exist for the pair, otherwise False.
        """
        if not user_id or not round_id or not partner_id or not meeting_ids:
            return False

        cleaned_meeting_ids = sorted({str(mid) for mid in meeting_ids if mid})
        if not cleaned_meeting_ids:
            return False

        meeting_elements = (
            func.jsonb_array_elements(
                func.coalesce(
                    MentorshipPairsEntity.meeting_log["google_meetings"],
                    type_coerce([], JSONB),
                )
            )
            .table_valued("value")
            .alias("meeting_elements")
        )

        stmt = (
            select(
                func.count(
                    func.distinct(
                        cast(meeting_elements.c.value, JSONB)["meeting_id"].astext
                    )
                )
            )
            .select_from(MentorshipPairsEntity)
            .select_from(meeting_elements)
            .where(
                MentorshipPairsEntity.round_id == round_id,
                or_(
                    (MentorshipPairsEntity.mentor_id == user_id)
                    & (MentorshipPairsEntity.mentee_id == partner_id),
                    (MentorshipPairsEntity.mentor_id == partner_id)
                    & (MentorshipPairsEntity.mentee_id == user_id),
                ),
                cast(meeting_elements.c.value, JSONB)["meeting_id"].astext.in_(
                    cleaned_meeting_ids
                ),
            )
        )

        result = await session.execute(stmt)
        found_count = result.scalar_one()

        return found_count == len(cleaned_meeting_ids)

    async def remove_meetings_from_log(
        self,
        session: AsyncSession,
        user_id: int,
        meeting_ids: list[str],
    ) -> list[int]:
        """
        Remove Google meeting entries from meeting_log JSONB for pairs associated
        with the current user.

        Returns:
            list[int]: Affected pair IDs.
        """
        if not user_id or not meeting_ids:
            return []

        cleaned_meeting_ids = sorted({str(mid) for mid in meeting_ids if mid})
        if not cleaned_meeting_ids:
            return []

        meeting_elements = (
            func.jsonb_array_elements(
                func.coalesce(
                    MentorshipPairsEntity.meeting_log["google_meetings"],
                    type_coerce([], JSONB),
                )
            )
            .table_valued("value")
            .alias("meeting_elements")
        )

        exists_condition = (
            select(1)
            .select_from(meeting_elements)
            .where(
                cast(meeting_elements.c.value, JSONB)["meeting_id"].astext.in_(
                    cleaned_meeting_ids
                )
            )
            .correlate(MentorshipPairsEntity)
            .exists()
        )

        filtered_meeting_list = func.coalesce(
            select(func.jsonb_agg(meeting_elements.c.value))
            .select_from(meeting_elements)
            .where(
                ~cast(meeting_elements.c.value, JSONB)["meeting_id"].astext.in_(
                    cleaned_meeting_ids
                )
            )
            .scalar_subquery(),
            type_coerce([], JSONB),
        )

        stmt = (
            update(MentorshipPairsEntity)
            .where(
                or_(
                    MentorshipPairsEntity.mentor_id == user_id,
                    MentorshipPairsEntity.mentee_id == user_id,
                ),
                exists_condition,
            )
            .values(
                meeting_log=func.jsonb_set(
                    func.coalesce(
                        func.nullif(
                            MentorshipPairsEntity.meeting_log,
                            text("'null'::jsonb"),
                        ),
                        type_coerce({}, JSONB),
                    ),
                    array(["google_meetings"]),
                    filtered_meeting_list,
                    True,
                )
            )
            .returning(MentorshipPairsEntity.pair_id)
        )

        result = await session.execute(stmt)
        return [row[0] for row in result.fetchall()]
