import uuid
from datetime import datetime, timedelta, timezone as dt_timezone, date
from zoneinfo import ZoneInfo

from sqlalchemy.ext.asyncio import AsyncSession

from backend.common.mentorship_enums import (
    MEETING_SUMMARY_TEMPLATE,
    MeetingSource,
    PairStatus,
)
from backend.common.name_utils import partner_display_name
from backend.entity.mentorship_meeting_entity import MentorshipMeetingEntity
from backend.dto.meeting_dto import MeetingDto
from backend.dto.meeting_create_dto import MeetingCreateDto
from backend.dto.google_meeting_response_detail_dto import (
    GoogleMeetingResponseDetailDto,
)
from backend.dto.google_meeting_batch_create_response_dto import (
    GoogleMeetingBatchCreateResponseDto,
    GoogleMeetingCreateFailureDto,
)
from backend.dto.user_context_dto import UserContextDto
from backend.common.permissions import Permission
from backend.dto.google_meeting_delete_response_dto import (
    GoogleMeetingDeleteResponseDto,
)


class MeetingService:
    def __init__(
        self,
        logger,
        mentorship_pairs_repository,
        mentorship_mapper,
        users_repository,
        meeting_scheduling_service,
        mentorship_calendar_id,
        mentorship_meeting_repository,
    ):
        """
        Args:
            logger: Shared app logger.
            mentorship_pairs_repository: Mentorship pair data access.
            mentorship_mapper: Entity/DTO mapper.
            users_repository: User data access.
            meeting_scheduling_service: Domain-agnostic Calendar/Meet transport.
            mentorship_calendar_id: The Google Calendar mentorship meetings are
                created on and deleted from. Per-environment, so this
                environment's deletes cannot reach another environment's events.
            mentorship_meeting_repository: Data access for individual
                mentorship meeting rows (``mentorship_meeting`` table), the
                replacement for ``mentorship_pairs.meeting_log``.
        """
        self.logger = logger
        self.mentorship_pairs_repository = mentorship_pairs_repository
        self.mentorship_mapper = mentorship_mapper
        self.users_repository = users_repository
        self.meeting_scheduling_service = meeting_scheduling_service
        self.mentorship_calendar_id = mentorship_calendar_id
        self.mentorship_meeting_repository = mentorship_meeting_repository

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
        current_user = await self.users_repository.get_user_by_user_id(
            session=session, user_id=user_context.user_id
        )

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
        pair_ids = []
        for p in pair_entity:
            partner_id = (
                p.mentor_id if p.mentee_id == current_user.user_id else p.mentee_id
            )
            grouped_pairs.append((p, partner_id))
            pair_ids.append(p.pair_id)

        # A user can have more than a couple of pairs here -- mentor_id/mentee_id
        # matching in get_pairs_by_user_and_round has no status filter, so N
        # includes cancelled pairs too. One batched query avoids an N+1.
        meetings_by_pair_id = (
            await self.mentorship_meeting_repository.get_meetings_by_pairs(
                session=session, pair_ids=pair_ids
            )
        )
        # v1's contract is MANUAL-only -- it never showed google_meetings even
        # after PR A migrated those rows into this same table. GOOGLE (and
        # LEGACY) rows must stay invisible here; map_to_meeting_v2_dto is the
        # path that merges both generations.
        meetings_by_pair = {
            pair_id: [
                m for m in meetings if m.source == MeetingSource.MANUAL
            ]
            for pair_id, meetings in meetings_by_pair_id.items()
        }

        return self.mentorship_mapper.map_to_meeting_dto(
            round_id=round_id,
            user_timezone=current_user.timezone,
            grouped_pairs=grouped_pairs,
            meetings_by_pair=meetings_by_pair,
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
        current_user = await self.users_repository.get_user_by_user_id(
            session=session, user_id=user_context.user_id
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

        # Conflict-check against this pair's existing MANUAL meetings only --
        # matching the old behavior, which compared only against
        # `meeting_time_list` and never against `google_meetings`. GOOGLE rows
        # are excluded here on purpose, not merely because
        # `get_meetings_by_pair` defaults to excluding LEGACY.
        existing_meetings = await self.mentorship_meeting_repository.get_meetings_by_pair(
            session=session, pair_id=pair_entity.pair_id
        )
        existing_manual_meetings = [
            m for m in existing_meetings if m.source == MeetingSource.MANUAL
        ]

        if self._has_time_conflict(
            existing_manual_meetings, data.start_datetime, data.end_datetime
        ):
            self.logger.warning(
                "[MeetingService] upsert failed for mentee_id=%s, round_id=%s. Duplicate slot: %s - %s",
                current_user.user_id,
                data.round_id,
                data.start_datetime,
                data.end_datetime,
            )
            raise ValueError("This time slot already exists.")

        new_meeting = MentorshipMeetingEntity(
            meeting_id=str(uuid.uuid4()),
            pair_id=pair_entity.pair_id,
            source=MeetingSource.MANUAL,
            start_datetime=data.start_datetime,
            end_datetime=data.end_datetime,
            is_completed=data.is_completed,
        )
        await self.mentorship_meeting_repository.insert_meeting(
            session=session, meeting=new_meeting
        )

        # Assigned directly rather than left for the ORM to refresh: the
        # UPDATE above sets `completed_count` from a scalar subquery, which
        # `synchronize_session="auto"` cannot handle via the cheap "evaluate"
        # strategy, so it falls back to "fetch" -- which EXPIRES
        # `completed_count` on this loaded pair rather than repopulating it.
        # The mapper reads `pair.completed_count` after `session.commit()`
        # below; an expired attribute read there would trigger an implicit
        # lazy load and raise MissingGreenlet under async. Assigning the
        # value we already have sidesteps that. (Known, accepted cost: this
        # also marks the attribute dirty, so the flush at commit re-issues an
        # UPDATE with the same value on an already-locked row.)
        pair_entity.completed_count = (
            await self.mentorship_meeting_repository.recalculate_completed_count(
                session=session, pair_id=pair_entity.pair_id
            )
        )

        updated_meetings = await self.mentorship_meeting_repository.get_meetings_by_pair(
            session=session, pair_id=pair_entity.pair_id
        )
        # Same v1 MANUAL-only contract as the read path above.
        updated_manual_meetings = [
            m for m in updated_meetings if m.source == MeetingSource.MANUAL
        ]

        await session.commit()

        return self.mentorship_mapper.map_to_meeting_dto(
            round_id=data.round_id,
            user_timezone=current_user.timezone,
            grouped_pairs=[(pair_entity, pair_entity.mentor_id)],
            meetings_by_pair={pair_entity.pair_id: updated_manual_meetings},
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
        current_user = await self.users_repository.get_user_by_user_id(
            session=session, user_id=user_context.user_id
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
        current_user_name = partner_display_name(
            first_name=current_user.first_name,
            last_name=current_user.last_name,
            preferred_name=current_user.preferred_name,
        )
        partner_name = partner_display_name(
            first_name=partner.first_name,
            last_name=partner.last_name,
            preferred_name=partner.preferred_name,
        )
        summary = MEETING_SUMMARY_TEMPLATE.format(
            current_user_name=current_user_name,
            partner_name=partner_name,
        )

        # Both attendees' contact addresses come from user_emails (their
        # primary, or the claim seeded from their login while they are still
        # in front of the verify wall). Address resolution, the idempotent
        # insert and opening the Meet space now live in the shared service.
        meeting = await self.meeting_scheduling_service.schedule(
            session,
            summary=summary,
            start_utc=start_datetime,
            end_utc=end_datetime,
            attendee_user_ids=[current_user.user_id, partner.user_id],
            calendar_id=self.mentorship_calendar_id,
        )

        new_meeting = MentorshipMeetingEntity(
            meeting_id=meeting["google_event_id"],
            pair_id=pair.pair_id,
            source=MeetingSource.GOOGLE,
            start_datetime=start_datetime,
            end_datetime=end_datetime,
            is_completed=False,
            meet_link=meeting["meet_link"],
            # `conference_id` is the scheduling service's key name for the
            # Meet code; the column is named `google_meeting_code` instead
            # because a Meet API "conference record" is a different,
            # per-occurrence concept. The rename is deliberate.
            google_meeting_code=meeting["conference_id"],
            entry_points=meeting["entry_points"],
        )

        # Persist the meeting row -- writes only mentorship_meeting, never
        # pair.meeting_log.
        try:
            await self.mentorship_meeting_repository.insert_meeting(
                session=session, meeting=new_meeting
            )
            await session.commit()
        except Exception as e:
            self.logger.error(
                "[MeetingService] DB write failed after Google meeting creation, "
                "event_id=%s may be orphaned: %s",
                meeting["google_event_id"],
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
            meeting_id=new_meeting.meeting_id,
            meet_link=new_meeting.meet_link,
            attendees=[current_user.user_id, partner.user_id],
            start_datetime=start_datetime.isoformat(),
            end_datetime=end_datetime.isoformat(),
            is_completed=new_meeting.is_completed,
            entry_points=new_meeting.entry_points,
        )

        return response_detail

    def _expand_occurrences(
        self,
        timezone: str,
        start_date: date,
        start_time: str,
        duration_minutes: int,
        interval_weeks: int,
        count: int,
    ) -> list[tuple[datetime, datetime]]:
        """Expand wall-clock recurrence into DST-correct (start_utc, end_utc) pairs."""
        tz = ZoneInfo(timezone)
        hour, minute = (int(p) for p in start_time.split(":"))
        naive_start = datetime(
            start_date.year, start_date.month, start_date.day, hour, minute
        )
        pairs = []
        for i in range(count):
            naive_i = naive_start + timedelta(weeks=interval_weeks * i)
            start_utc = naive_i.replace(tzinfo=tz).astimezone(dt_timezone.utc)
            end_utc = start_utc + timedelta(minutes=duration_minutes)
            pairs.append((start_utc, end_utc))
        return pairs

    async def create_google_meetings_batch(
        self,
        session_factory,
        user_context: UserContextDto,
        partner_id: int,
        round_id: int,
        timezone: str,
        start_date: date,
        start_time: str,
        duration_minutes: int,
        interval_weeks: int = 1,
        count: int = 1,
    ) -> GoogleMeetingBatchCreateResponseDto:
        """
        Create one or more mentorship meetings from a wall-clock recurrence spec.

        Wall-clock inputs are expanded to DST-correct UTC pairs, then each
        occurrence is created via `create_google_meeting` in its own session
        (best-effort: a single failure is captured, not raised).
        """
        occurrences = self._expand_occurrences(
            timezone=timezone,
            start_date=start_date,
            start_time=start_time,
            duration_minutes=duration_minutes,
            interval_weeks=interval_weeks,
            count=count,
        )

        created = []
        failed = []
        for index, (start_utc, end_utc) in enumerate(occurrences):
            try:
                async with session_factory() as session:
                    detail = await self.create_google_meeting(
                        session=session,
                        user_context=user_context,
                        partner_id=partner_id,
                        round_id=round_id,
                        start_datetime=start_utc,
                        end_datetime=end_utc,
                    )
                created.append(detail)
            except Exception as e:
                self.logger.warning(
                    "[MeetingService] batch occurrence %d failed for "
                    "round_id=%s partner_id=%s: %s",
                    index,
                    round_id,
                    partner_id,
                    e,
                )
                failed.append(
                    GoogleMeetingCreateFailureDto(
                        index=index,
                        start_datetime=start_utc.isoformat(),
                        reason=str(e),
                    )
                )

        self.logger.info(
            "[MeetingService] batch create for round_id=%s partner_id=%s: "
            "created=%d failed=%d",
            round_id,
            partner_id,
            len(created),
            len(failed),
        )
        return GoogleMeetingBatchCreateResponseDto(created=created, failed=failed)

    async def delete_google_meetings(
        self,
        session: AsyncSession,
        user_context: UserContextDto,
        deletions: list[dict],
    ) -> GoogleMeetingDeleteResponseDto:
        """
        Delete Google Calendar meetings across one or more mentorship pairs.

        The Calendar-side deletion is unchanged from before this table
        switch: it is still handed the bare `meeting_id`, which for a GOOGLE
        row equals the Calendar event id (see MentorshipMeetingEntity). Only
        the database side -- the existence check beforehand and the removal
        afterward -- now goes through `mentorship_meeting_repository` instead
        of the JSONB `meeting_log` column.

        Returns:
            GoogleMeetingDeleteResponseDto: IDs that were successfully deleted and failed.

        Raises:
            ValueError:
                - If deletions is empty.
                - If no mentorship pair matches a deletion's round_id/partner_id.
                - If any meeting_ids do not exist as GOOGLE rows for that pair.
        """
        if not deletions:
            raise ValueError("deletions must not be empty.")

        all_meeting_ids: list[str] = []
        # Which pair each requested meeting id belongs to, resolved here
        # while validating existence. Needed afterward because
        # `delete_meetings`/`recalculate_completed_count` operate per
        # pair_id, while Calendar's `cancel` call below is batched across
        # every pair in this request.
        pair_id_by_meeting_id: dict[str, int] = {}

        for deletion in deletions:
            pairs = await self.mentorship_pairs_repository.get_pairs_by_user_and_round(
                session=session,
                user_id=user_context.user_id,
                round_id=deletion["round_id"],
            )
            pair = next(
                (
                    p
                    for p in pairs
                    if deletion["partner_id"] in (p.mentor_id, p.mentee_id)
                ),
                None,
            )
            if pair is None:
                raise ValueError(
                    f"Some meetings were not found for round_id={deletion['round_id']}, "
                    f"partner_id={deletion['partner_id']}."
                )

            existing_meetings = (
                await self.mentorship_meeting_repository.get_meetings_by_pair(
                    session=session, pair_id=pair.pair_id
                )
            )
            existing_google_ids = {
                m.meeting_id
                for m in existing_meetings
                if m.source == MeetingSource.GOOGLE
            }
            requested_ids = deletion["meeting_ids"]
            all_exist = bool(requested_ids) and all(
                mid in existing_google_ids for mid in requested_ids
            )

            if not all_exist:
                raise ValueError(
                    f"Some meetings were not found for round_id={deletion['round_id']}, "
                    f"partner_id={deletion['partner_id']}."
                )

            for mid in requested_ids:
                pair_id_by_meeting_id[mid] = pair.pair_id
            all_meeting_ids.extend(requested_ids)

        (
            succeeded_event_ids,
            failed_event_ids,
        ) = await self.meeting_scheduling_service.cancel(
            all_meeting_ids, calendar_id=self.mentorship_calendar_id
        )

        if succeeded_event_ids:
            deduped_succeeded_ids = list(dict.fromkeys(succeeded_event_ids))
            affected_pair_ids = {
                pair_id_by_meeting_id[mid] for mid in deduped_succeeded_ids
            }

            for pair_id in affected_pair_ids:
                ids_for_pair = [
                    mid
                    for mid in deduped_succeeded_ids
                    if pair_id_by_meeting_id[mid] == pair_id
                ]
                await self.mentorship_meeting_repository.delete_meetings(
                    session=session, pair_id=pair_id, meeting_ids=ids_for_pair
                )
                # Same rationale as upsert_meetings: assign the returned
                # value directly rather than relying on the caller to
                # refresh anything, since nothing here holds a loaded pair
                # entity to refresh in the first place.
                await self.mentorship_meeting_repository.recalculate_completed_count(
                    session=session, pair_id=pair_id
                )

            await session.commit()

        self.logger.info(
            "[MeetingService] Deleted Google meetings for user_id=%s. succeeded=%s, failed=%s",
            user_context.user_id,
            succeeded_event_ids,
            failed_event_ids,
        )

        return GoogleMeetingDeleteResponseDto(
            succeeded_meeting_ids=succeeded_event_ids,
            failed_meeting_ids=failed_event_ids,
        )

    def _has_time_conflict(
        self,
        existing_meetings: list[MentorshipMeetingEntity],
        new_start: datetime,
        new_end: datetime,
    ) -> bool:
        """
        Returns True if the new time slot overlaps with any existing meeting row.

        Args:
            existing_meetings (list[MentorshipMeetingEntity]): Meeting rows to
                check against. Callers are expected to have already narrowed
                this to whatever source(s) should participate in the check
                (e.g. MANUAL only) -- this method does not filter by source.
            new_start (datetime): Start datetime of the new slot, UTC.
            new_end (datetime): End datetime of the new slot, UTC.

        Returns:
            bool: True if a conflict exists, False otherwise.
        """
        return any(
            new_start < e.end_datetime and new_end > e.start_datetime
            for e in existing_meetings
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
        current_user = await self.users_repository.get_user_by_user_id(
            session=session, user_id=user_context.user_id
        )

        is_admin = user_context.has_permission(Permission.MENTORSHIP_ADMIN_READ)
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
        pair_ids = []
        for p in pair_entity:
            partner_id = (
                p.mentor_id if p.mentee_id == current_user.user_id else p.mentee_id
            )
            grouped_pairs.append((p, partner_id))
            pair_ids.append(p.pair_id)

        # Unlike v1, v2's contract merges both generations -- MANUAL and
        # GOOGLE rows both flow through unfiltered; only LEGACY (excluded by
        # the repository's own default) has nothing to show here.
        meetings_by_pair = (
            await self.mentorship_meeting_repository.get_meetings_by_pairs(
                session=session, pair_ids=pair_ids
            )
        )

        return self.mentorship_mapper.map_to_meeting_v2_dto(
            round_id=round_id,
            user_timezone=current_user.timezone,
            grouped_pairs=grouped_pairs,
            meetings_by_pair=meetings_by_pair,
            include_details=is_detail_allowed,
        )
