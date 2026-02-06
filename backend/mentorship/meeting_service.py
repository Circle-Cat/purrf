import uuid

from backend.dto.meeting_dto import MeetingDto
from backend.dto.meeting_create_dto import MeetingCreateDto
from backend.dto.user_context_dto import UserContextDto
from backend.common.constants import DATETIME_UTC_FORMAT
from sqlalchemy.ext.asyncio import AsyncSession


class MeetingService:
    def __init__(
        self,
        logger,
        mentorship_pairs_repository,
        mentorship_mapper,
        user_identity_service,
    ):
        self.logger = logger
        self.mentorship_pairs_repository = mentorship_pairs_repository
        self.mentorship_mapper = mentorship_mapper
        self.user_identity_service = user_identity_service

    async def get_meetings_by_user_and_round(
        self, session: AsyncSession, user_context: UserContextDto, round_id: int
    ) -> MeetingDto:
        """
        Retrieve the mentorship meeting logs for the current user in a specific round.

        This method resolves the current user, identifies their matched pairs for the given round,
        and maps the meeting logs and associated role context into a structured MeetingDto.

        Args:
            session (AsyncSession): The SQLAlchemy async session.
            user_context (UserContextDto): Context identifying the current user.
            round_id (int): The mentorship round ID.

        Returns:
            MeetingDto: A DTO containing meeting information and partner roles.
        """
        (current_user, should_commit) = await self.user_identity_service.get_user(
            session=session, user_info=user_context
        )

        if should_commit:
            await session.commit()

        pair_entity = (
            await self.mentorship_pairs_repository.get_pairs_by_user_and_round(
                session=session, user_id=current_user.user_id, round_id=round_id
            )
        )
        if not pair_entity:
            self.logger.warning(
                "[MeetingService] Fetch pairs failed: no pair record found for user %s in round %s",
                current_user.user_id,
                round_id,
            )
            return MeetingDto(
                round_id=round_id, user_timezone=current_user.timezone, meeting_info=[]
            )

        grouped_pairs = [
            (p, p.mentor_id if p.mentee_id == current_user.user_id else p.mentee_id)
            for p in pair_entity
        ]

        return self.mentorship_mapper.map_to_meeting_dto(
            round_id=round_id,
            user_timezone=current_user.timezone,
            grouped_pairs=grouped_pairs,
        )

    async def upsert_meetings(
        self,
        session: AsyncSession,
        user_context: UserContextDto,
        data: MeetingCreateDto,
    ) -> MeetingDto:
        """
        Create or update meeting logs for the current user in a specific mentorship round.

        Validates for time slot conflicts, appends or updates the meeting records,
        and returns the synchronized meeting state.

        Args:
            session (AsyncSession): The SQLAlchemy async session.
            user_context (UserContextDto): Context identifying the current user.
            data (MeetingCreateDto): The new meeting data to be persisted.

        Returns:
            MeetingDto: The updated meeting logs after the upsert operation.
        """
        current_user, _ = await self.user_identity_service.get_user(
            session=session, user_info=user_context
        )

        pair_entity = (
            await self.mentorship_pairs_repository.get_pair_by_mentee_and_round(
                session=session, mentee_id=current_user.user_id, round_id=data.round_id
            )
        )

        if not pair_entity:
            self.logger.error(
                "[MeetingService] Upsert failed: no pair record found for mentee_id=%s in round_id=%s",
                current_user.user_id,
                data.round_id,
            )
            raise ValueError(
                "The current user is not matched as a mentee in this round."
            )

        current_log = (
            pair_entity.meeting_log if isinstance(pair_entity.meeting_log, dict) else {}
        )
        existing_slots = (
            current_log.get("meeting_time_list")
            if isinstance(current_log.get("meeting_time_list"), list)
            else []
        )

        new_start = data.start_datetime.strftime(DATETIME_UTC_FORMAT)
        new_end = data.end_datetime.strftime(DATETIME_UTC_FORMAT)

        if self._has_time_conflict(existing_slots, new_start, new_end):
            self.logger.warning(
                "[MeetingService] upsert failed for mentee_id=%s, round_id=%s. Duplicate slot: %s - %s",
                current_user.user_id,
                data.round_id,
                new_start,
                new_end,
            )
            raise ValueError("This time slot already exists.")

        pair_entity.meeting_log = {
            "meeting_time_list": existing_slots
            + [
                {
                    "meeting_id": str(uuid.uuid4()),
                    "start_datetime": new_start,
                    "end_datetime": new_end,
                    "is_completed": data.is_completed,
                }
            ]
        }

        saved_pair = await self.mentorship_pairs_repository.upsert_pairs(
            session=session, entity=pair_entity
        )

        await session.commit()

        return self.mentorship_mapper.map_to_meeting_dto(
            round_id=data.round_id,
            user_timezone=current_user.timezone,
            grouped_pairs=[(saved_pair, saved_pair.mentor_id)],
        )

    def _has_time_conflict(
        self, existing_slots: list, new_start: str, new_end: str
    ) -> bool:
        """
        Returns True if the new time slot overlaps with any existing slot.

        Args:
            existing_slots (list): List of existing meeting slot dicts with "start_datetime" and "end_datetime".
            new_start (str): Start datetime of the new slot in UTC string format.
            new_end (str): End datetime of the new slot in UTC string format.

        Returns:
            bool: True if a conflict exists, False otherwise.
        """
        return any(
            new_start < e["end_datetime"] and new_end > e["start_datetime"]
            for e in existing_slots
        )
