import asyncio
import uuid
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from backend.common.constants import DATETIME_UTC_FORMAT
from backend.common.mentorship_enums import MEETING_SUMMARY_TEMPLATE, PairStatus
from backend.dto.meeting_dto import MeetingDto
from backend.dto.meeting_create_dto import MeetingCreateDto
from backend.dto.google_meeting_detail_dto import GoogleMeetingDetailDto
from backend.dto.google_meeting_response_detail_dto import (
    GoogleMeetingResponseDetailDto,
)
from backend.dto.user_context_dto import UserContextDto
from backend.common.user_role import UserRole


class MeetingService:
    def __init__(
        self,
        logger,
        mentorship_pairs_repository,
        mentorship_mapper,
        user_identity_service,
        google_service,
    ):
        self.logger = logger
        self.mentorship_pairs_repository = mentorship_pairs_repository
        self.mentorship_mapper = mentorship_mapper
        self.user_identity_service = user_identity_service
        self.google_service = google_service

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

        grouped_pairs = []
        for p in pair_entity:
            partner_id = (
                p.mentor_id if p.mentee_id == current_user.user_id else p.mentee_id
            )
            grouped_pairs.append((p, partner_id))

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
                    "created_datetime": datetime.utcnow().strftime(DATETIME_UTC_FORMAT),
                }
            ]
        }
        pair_entity.completed_count = sum(
            1
            for m in pair_entity.meeting_log["meeting_time_list"]
            if m.get("is_completed")
        )

        saved_pair = await self.mentorship_pairs_repository.upsert_pairs(
            session=session, entity=pair_entity
        )

        await session.commit()

        return self.mentorship_mapper.map_to_meeting_dto(
            round_id=data.round_id,
            user_timezone=current_user.timezone,
            grouped_pairs=[(saved_pair, saved_pair.mentor_id)],
        )

    async def create_google_meeting(
        self,
        session: AsyncSession,
        user_context: UserContextDto,
        partner_id: int,
        round_id: int,
        start_datetime: datetime,
        end_datetime: datetime,
    ) -> GoogleMeetingResponseDetailDto:
        """
        Create a Google Calendar meeting for a mentorship pair and persist the details.

        Resolves both participants, creates a Google Calendar event with Meet link,
        appends the meeting record to the pair's meeting_log, and returns the
        created meeting details.

        Args:
            session (AsyncSession): The SQLAlchemy async session.
            user_context (UserContextDto): Context identifying the current user.
            partner_id (int): The user ID of the mentorship partner.
            round_id (int): The mentorship round ID.
            start_datetime (datetime): The meeting start time.
            end_datetime (datetime): The meeting end time.

        Returns:
            GoogleMeetingResponseDetailDto: The created meeting details.

        Raises:
            ValueError: If the partner is not found.
        """
        # Resolve current user
        current_user, _ = await self.user_identity_service.get_user(
            session=session, user_info=user_context
        )

        # Get pair and partner info
        pair_result = await self.mentorship_pairs_repository.get_pair_with_partner_by_round_and_users_and_status(
            session=session,
            round_id=round_id,
            user_id=current_user.user_id,
            partner_id=partner_id,
            status=PairStatus.ACTIVE,
            with_lock=True,
        )
        if pair_result is None:
            self.logger.error(
                "[MeetingService] No active mentorship pair found for user_id=%s, "
                "partner_id=%s, round_id=%s",
                current_user.user_id,
                partner_id,
                round_id,
            )
            raise ValueError(
                "No mentorship pair found for the specified partner in this round."
            )

        pair, partner = pair_result

        # Build summary
        current_user_name = current_user.preferred_name or current_user.first_name
        partner_name = partner.preferred_name or partner.first_name
        summary = MEETING_SUMMARY_TEMPLATE.format(
            current_user_name=current_user_name,
            partner_name=partner_name,
        )

        # Generate unique IDs for idempotency
        event_id = uuid.uuid4().hex
        request_id = str(uuid.uuid4())

        # Call Google Calendar API
        attendees_emails = [current_user.primary_email, partner.primary_email]
        google_result = await asyncio.to_thread(
            self.google_service.insert_google_meeting,
            summary=summary,
            start_time=start_datetime,
            end_time=end_datetime,
            attendees_emails=attendees_emails,
            request_id=request_id,
            event_id=event_id,
        )

        # Update Meet space access type to OPEN
        meeting_code = (google_result.get("conferenceData") or {}).get("conferenceId")
        if meeting_code:
            try:
                space_name = await self.google_service.get_meet_space_name(meeting_code)
                await self.google_service.update_meet_space_type_to_open(space_name)
            except Exception as e:
                self.logger.warning(
                    "[MeetingService] Non-fatal: failed to set Meet space %s to OPEN: %s",
                    meeting_code,
                    e,
                )

        # Build internal meeting detail DTO
        conference_data = google_result.get("conferenceData", {})
        meeting_detail = GoogleMeetingDetailDto(
            meeting_id=google_result.get("id", ""),
            meet_link=google_result.get("hangoutLink", ""),
            start_datetime=start_datetime.isoformat(),
            end_datetime=end_datetime.isoformat(),
            is_completed=False,
            entry_points=conference_data.get("entryPoints", []),
            conference_id=conference_data.get("conferenceId"),
        )

        # Persist meeting log
        try:
            await self.mentorship_pairs_repository.append_google_meeting(
                session=session,
                pair_id=pair.pair_id,
                meeting_entry=meeting_detail.model_dump(),
            )
            await session.commit()
        except Exception as e:
            self.logger.error(
                "[MeetingService] DB write failed after Google meeting creation, "
                "event_id=%s may be orphaned: %s",
                event_id,
                e,
                exc_info=True,
            )
            raise

        self.logger.info(
            "[MeetingService] Meeting created for round_id=%s, user_id=%s, partner_id=%s",
            round_id,
            current_user.user_id,
            partner_id,
        )

        # Convert to response DTO
        response_detail = GoogleMeetingResponseDetailDto(
            meeting_id=meeting_detail.meeting_id,
            meet_link=meeting_detail.meet_link,
            attendees=[current_user.user_id, partner.user_id],
            start_datetime=meeting_detail.start_datetime,
            end_datetime=meeting_detail.end_datetime,
            is_completed=meeting_detail.is_completed,
            entry_points=meeting_detail.entry_points,
        )

        return response_detail

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

    async def get_meetings_by_user_and_round_v2(
        self,
        session: AsyncSession,
        user_context: UserContextDto,
        round_id: int,
        include_details: bool,
    ) -> MeetingDto:
        """
        Retrieve the mentorship meeting logs for the current user in a specific round (v2).

        This method resolves the current user, determines whether detailed output is allowed,
        fetches the user's mentorship pairs for the given round, and maps the result into a
        MeetingDto.
        """
        (current_user, should_commit) = await self.user_identity_service.get_user(
            session=session, user_info=user_context
        )

        if should_commit:
            await session.commit()

        is_admin = UserRole.MENTORSHIP_ADMIN in (user_context.roles or [])
        is_detail_allowed = include_details and is_admin

        pair_entity = (
            await self.mentorship_pairs_repository.get_pairs_by_user_and_round(
                session=session,
                user_id=current_user.user_id,
                round_id=round_id,
            )
        )

        if not pair_entity:
            self.logger.warning(
                "[MeetingService] Fetch pairs failed: no pair record found for user %s in round %s",
                current_user.user_id,
                round_id,
            )
            return MeetingDto(
                round_id=round_id,
                user_timezone=current_user.timezone,
                meeting_info=[],
            )

        grouped_pairs = []
        for p in pair_entity:
            partner_id = (
                p.mentor_id if p.mentee_id == current_user.user_id else p.mentee_id
            )
            grouped_pairs.append((p, partner_id))

        return self.mentorship_mapper.map_to_meeting_v2_dto(
            round_id=round_id,
            user_timezone=current_user.timezone,
            grouped_pairs=grouped_pairs,
            include_details=is_detail_allowed,
        )
