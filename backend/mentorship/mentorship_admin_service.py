from sqlalchemy.ext.asyncio import AsyncSession
from backend.dto.participant_search_filter_dto import (
    ParticipantSearchFilterDto,
    UnregisteredFilterDto,
)
from backend.dto.participant_search_dto import (
    AttendanceIssueDto,
    ParticipantPairDto,
    ParticipantRowDto,
    ParticipantSearchDto,
    UnregisteredRowDto,
    UnregisteredSearchDto,
)
from backend.dto.participant_search_row_dto import (
    ParticipantSearchPairRow,
    ParticipantSearchRow,
)
from backend.dto.partner_dto import PartnerDto
from backend.dto.admin_meeting_log_dto import AdminMeetingLogDto
from backend.dto.round_feedback_dto import (
    AdminPartnerFeedbackDto,
    ParticipantFeedbackDto,
    RoundFeedbackDto,
)
from backend.dto.v2_meeting_batch_update_dto import V2MeetingBatchUpdateDto
from backend.common.exceptions import ConflictError
from backend.common.mentorship_enums import (
    MENTORSHIP_ONBOARDING_CATEGORIES,
    MeetingNoteTag,
    MeetingSource,
    PairStatus,
    ParticipantRole,
    TrainingCategory,
)
from backend.common.name_utils import user_display_name
from backend.entity.mentorship_meeting_entity import MentorshipMeetingEntity


class MentorshipAdminService:
    """Service for admin-facing mentorship participant search."""

    _ABSENT_TAGS = {
        MeetingNoteTag.UNKNOWN_ABSENT,
        MeetingNoteTag.MENTOR_ABSENT,
        MeetingNoteTag.MENTEE_ABSENT,
    }
    _SPECIFIC_LATE_TAGS = {MeetingNoteTag.MENTOR_LATE, MeetingNoteTag.MENTEE_LATE}

    def __init__(
        self,
        users_repository,
        participants_repository,
        rounds_repository,
        training_repository,
        pairs_repository,
        mentorship_mapper,
        logger,
        mentorship_meeting_repository,
        application_repository,
    ) -> None:
        self.users_repository = users_repository
        self.participants_repository = participants_repository
        self.rounds_repository = rounds_repository
        self.training_repository = training_repository
        self.pairs_repository = pairs_repository
        self.mentorship_mapper = mentorship_mapper
        self.logger = logger
        self.mentorship_meeting_repository = mentorship_meeting_repository
        self.application_repository = application_repository

    def _extract_emails(self, emails: list) -> tuple[str | None, list[str]]:
        """
        Split email records into a primary address and a list of alternatives.

        Args:
            emails (list[UserEmailsEntity]): Email records for a single user.

        Returns:
            tuple[str | None, list[str]]: Primary email (None if absent) and
            alternative emails.
        """
        primary_email = None
        alternative_emails = []
        for e in emails:
            if e.is_primary:
                primary_email = e.email
            else:
                alternative_emails.append(e.email)
        return primary_email, alternative_emails

    async def _fetch_batch_relations(
        self, session: AsyncSession, rows: list[ParticipantSearchRow]
    ) -> tuple[dict, dict, dict]:
        """
        Batch-fetch user, email, and training records referenced by a
        page of search rows.

        Args:
            session (AsyncSession): Active database async session.
            rows (list[ParticipantSearchRow]): One page/batch of search rows.

        Returns:
            tuple: (users_map, emails_map, trainings_map), keyed by user_id.
            trainings_map's values are further keyed by TrainingCategory.
        """
        mentorship_user_ids: set[int] = set()
        training_user_ids: set[int] = set()
        for row in rows:
            mentorship_user_ids.add(row.user_id)
            for pair in row.pairs:
                mentorship_user_ids.add(pair.mentor_id)
                mentorship_user_ids.add(pair.mentee_id)
            training_user_ids.add(row.user_id)

        users_map, emails_map = await self.users_repository.get_users_and_emails_by_ids(
            session, list(mentorship_user_ids)
        )

        trainings = (
            await self.training_repository.get_training_by_user_ids_and_categories(
                session,
                list(training_user_ids),
                categories=list(MENTORSHIP_ONBOARDING_CATEGORIES),
            )
        )
        trainings_map: dict = {}
        for t in trainings:
            trainings_map.setdefault(t.user_id, {})[t.category] = t.status

        return users_map, emails_map, trainings_map

    def _get_partner_user(
        self, user_id: int, pair: ParticipantSearchPairRow, users_map: dict
    ):
        """
        Resolve the other side of one of a participant's pairs.

        Args:
            user_id (int): The participant the row is about.
            pair (ParticipantSearchPairRow): One of that participant's pairs.
            users_map (dict[int, UsersEntity]): User records keyed by user_id.

        Returns:
            The partner's user record, or None if the partner isn't in
            users_map.
        """
        partner_id = pair.mentee_id if user_id == pair.mentor_id else pair.mentor_id
        return users_map.get(partner_id)

    def _attendance_issues(
        self, pair: ParticipantSearchPairRow, meetings: list[MentorshipMeetingEntity]
    ) -> list[AttendanceIssueDto]:
        """
        The pair's meetings that carry any note tag, in the repository's
        start_datetime order, tagged the same way the meeting log shows them.

        Args:
            pair (ParticipantSearchPairRow): The pair the meetings belong to.
            meetings (list[MentorshipMeetingEntity]): That pair's meetings.

        Returns:
            list[AttendanceIssueDto]: One entry per tagged meeting.
        """
        issues: list[AttendanceIssueDto] = []
        for meeting in meetings:
            note = self._resolve_meeting_notes_from_row(
                meeting, pair.mentor_id, pair.mentee_id
            )
            if note:
                issues.append(
                    AttendanceIssueDto(start_datetime=meeting.start_datetime, note=note)
                )
        return issues

    def _build_pair_dtos(
        self,
        row: ParticipantSearchRow,
        users_map: dict,
        meetings_by_pair: dict[int, list[MentorshipMeetingEntity]],
    ) -> list[ParticipantPairDto]:
        """
        Build the Pair column entries for a participant search row, keeping
        the row's pair_id order and skipping any pair whose partner can't be
        resolved.

        Args:
            row (ParticipantSearchRow): The row whose pairs to build.
            users_map (dict[int, UsersEntity]): User records keyed by user_id.
            meetings_by_pair (dict[int, list[MentorshipMeetingEntity]]): The
                page's meetings keyed by pair_id; a pair with none is absent.

        Returns:
            list[ParticipantPairDto]: One entry per resolvable pair.
        """
        pair_dtos: list[ParticipantPairDto] = []
        for pair in row.pairs:
            partner = self._get_partner_user(row.user_id, pair, users_map)
            if partner is None:
                continue
            pair_dtos.append(
                ParticipantPairDto(
                    pair_id=pair.pair_id,
                    partner=PartnerDto(
                        id=partner.user_id,
                        first_name=partner.first_name or "",
                        last_name=partner.last_name or "",
                        preferred_name=partner.preferred_name or "",
                        primary_email=None,
                        participant_role=None,
                        recommendation_reason=None,
                        is_active=pair.pair_status == PairStatus.ACTIVE,
                    ),
                    completed_meeting_count=pair.completed_count,
                    attendance_issues=self._attendance_issues(
                        pair, meetings_by_pair.get(pair.pair_id, [])
                    ),
                )
            )
        return pair_dtos

    def _get_required_meetings(
        self, row: ParticipantSearchRow, rounds_map: dict
    ) -> int | None:
        """
        Look up a row's required meeting count from its round.

        Args:
            row (ParticipantSearchRow): The row to look up a round for.
            rounds_map (dict[int, MentorshipRoundEntity]): Round records keyed by round_id.

        Returns:
            int | None: The round's required_meetings, or None if it has no round.
        """
        round_entity = rounds_map.get(row.round_id) if row.round_id else None
        return round_entity.required_meetings if round_entity else None

    async def search_participants(
        self,
        session: AsyncSession,
        filters: ParticipantSearchFilterDto,
        limit: int = 100,
        offset: int = 0,
        sort_by: str | None = None,
        order: str = "asc",
    ) -> ParticipantSearchDto:
        """
        Search mentorship participants and non-participants for admin with pagination.

        Executes the participant query, batch-fetches related user, email, round,
        training and meeting data, then assembles the response.

        Args:
            session (AsyncSession): Active database async session.
            filters (ParticipantSearchFilterDto): Filter criteria from the request.
            limit (int): Maximum number of rows to return. Defaults to 100.
            offset (int): Number of rows to skip for pagination. Defaults to 0.
            sort_by (str | None): Column to sort by (whitelisted in the repo).
                Unknown values fall back to the deterministic default order.
            order (str): "asc" or "desc" (default "asc").

        Returns:
            ParticipantSearchDto: Assembled participant rows and total count.
        """
        rows, total = await self.participants_repository.search_participants_for_admin(
            session, filters, limit, offset, sort_by, order
        )
        if not rows:
            return ParticipantSearchDto(participant_rows=[], total=total)

        users_map, emails_map, trainings_map = await self._fetch_batch_relations(
            session, rows
        )

        rounds = await self.rounds_repository.get_all_rounds(session)
        rounds_map = {r.round_id: r for r in rounds}

        meetings_by_pair = (
            await self.mentorship_meeting_repository.get_meetings_by_pairs(
                session, sorted({p.pair_id for row in rows for p in row.pairs})
            )
        )

        participant_rows: list[ParticipantRowDto] = []
        for row in rows:
            statuses = trainings_map.get(row.user_id, {})
            mentor_status = statuses.get(TrainingCategory.MENTORSHIP_MENTOR_ONBOARDING)
            mentee_status = statuses.get(TrainingCategory.MENTORSHIP_MENTEE_ONBOARDING)

            user = users_map[row.user_id]
            primary_email, alternative_emails = self._extract_emails(
                emails_map.get(row.user_id, [])
            )

            round_entity = rounds_map.get(row.round_id) if row.round_id else None

            participant_rows.append(
                ParticipantRowDto(
                    user_id=row.user_id,
                    round_id=row.round_id,
                    round_name=round_entity.name if round_entity else None,
                    first_name=user.first_name,
                    last_name=user.last_name,
                    preferred_name=user.preferred_name,
                    primary_email=primary_email,
                    alternative_emails=alternative_emails,
                    is_blocked=row.is_blocked,
                    is_deactivated=row.is_deactivated,
                    is_internal=row.is_internal,
                    participant_role=row.participant_role,
                    approval_status=row.approval_status,
                    mentor_onboarding_status=mentor_status,
                    mentee_onboarding_status=mentee_status,
                    pairs=self._build_pair_dtos(row, users_map, meetings_by_pair),
                    required_meetings=self._get_required_meetings(row, rounds_map),
                )
            )

        return ParticipantSearchDto(participant_rows=participant_rows, total=total)

    async def search_unregistered(
        self,
        session: AsyncSession,
        round_id: int,
        filters: UnregisteredFilterDto,
        limit: int = 100,
        offset: int = 0,
        order: str = "asc",
    ) -> UnregisteredSearchDto:
        """
        List the people admitted as a mentor or mentee who have not
        registered for a round, with what an admin chasing them needs: who
        they are, what they were admitted as, and how much they have taken
        part before.

        Args:
            session (AsyncSession): Active database async session.
            round_id (int): The round they have not registered for.
            filters (UnregisteredFilterDto): Person and admitted-role filters.
            limit (int): Maximum number of rows to return. Defaults to 100.
            offset (int): Number of rows to skip for pagination. Defaults to 0.
            order (str): "asc" or "desc" by user ID (default "asc").

        Returns:
            UnregisteredSearchDto: One row per person and the total count.

        Raises:
            ValueError: If the round does not exist.
        """
        round_entity = await self.rounds_repository.get_by_round_id(session, round_id)
        if round_entity is None:
            raise ValueError(f"Mentorship round {round_id} does not exist.")

        rows, total = await self.participants_repository.search_unregistered_for_admin(
            session, round_id, filters, limit, offset, order
        )
        if not rows:
            return UnregisteredSearchDto(rows=[], total=total)

        user_ids = [row.user_id for row in rows]
        users_map, emails_map = await self.users_repository.get_users_and_emails_by_ids(
            session, user_ids
        )
        roles_map = (
            await self.application_repository.list_hired_activity_roles_by_user_ids(
                session, user_ids
            )
        )
        rounds_map = (
            await self.participants_repository.list_registered_rounds_by_user_ids(
                session, user_ids
            )
        )

        result: list[UnregisteredRowDto] = []
        for row in rows:
            user = users_map[row.user_id]
            primary_email, alternative_emails = self._extract_emails(
                emails_map.get(row.user_id, [])
            )
            roles = roles_map.get(row.user_id, set())
            past_rounds = rounds_map.get(row.user_id, [])
            result.append(
                UnregisteredRowDto(
                    user_id=row.user_id,
                    first_name=user.first_name,
                    last_name=user.last_name,
                    preferred_name=user.preferred_name,
                    primary_email=primary_email,
                    alternative_emails=alternative_emails,
                    is_blocked=row.is_blocked,
                    is_deactivated=row.is_deactivated,
                    is_internal=row.is_internal,
                    admitted_roles=[
                        role
                        for role in (ParticipantRole.MENTOR, ParticipantRole.MENTEE)
                        if role in roles
                    ],
                    rounds_taken_part=len(past_rounds),
                    last_round_name=past_rounds[0].name if past_rounds else None,
                )
            )
        return UnregisteredSearchDto(rows=result, total=total)

    def _resolve_meeting_notes(
        self, meeting: dict, mentor_id: int, mentee_id: int
    ) -> list[MeetingNoteTag]:
        """
        Resolve note tags for a meeting based on its duration, absence, and lateness flags.

        Manual (v1) entries never carry these keys at all, so `.get()`
        returning None for each of them is what naturally yields an empty
        note list rather than a separate branch for that generation.

        Args:
            meeting (dict): A single meeting record (Google or manual) from
                the pair's meeting_log.
            mentor_id (int): User ID of the pair's mentor.
            mentee_id (int): User ID of the pair's mentee.

        Returns:
            list[MeetingNoteTag]: Note tags applicable to the meeting.
        """
        notes = []
        if meeting.get("has_insufficient_duration"):
            notes.append(MeetingNoteTag.INSUFFICIENT_DURATION)
        if meeting.get("has_unknown_absent"):
            notes.append(MeetingNoteTag.UNKNOWN_ABSENT)
        elif absent_user_id := meeting.get("absent_user_id"):
            if absent_user_id == mentor_id:
                notes.append(MeetingNoteTag.MENTOR_ABSENT)
            elif absent_user_id == mentee_id:
                notes.append(MeetingNoteTag.MENTEE_ABSENT)
        if meeting.get("has_unknown_late"):
            notes.append(MeetingNoteTag.UNKNOWN_LATE)
        else:
            late_user_ids = meeting.get("late_user_id") or []
            if mentor_id in late_user_ids:
                notes.append(MeetingNoteTag.MENTOR_LATE)
            if mentee_id in late_user_ids:
                notes.append(MeetingNoteTag.MENTEE_LATE)
        return notes

    def _resolve_meeting_notes_from_row(
        self,
        meeting: MentorshipMeetingEntity,
        mentor_id: int,
        mentee_id: int,
    ) -> list[MeetingNoteTag]:
        """
        Resolve note tags for a `mentorship_meeting` row's attendance columns.

        The entity-row twin of `_resolve_meeting_notes`, used by the read path
        that has switched from the JSONB column to querying
        `MentorshipMeetingRepository` directly. MANUAL rows always have these
        columns NULL (the `google_fields` CHECK constraint enforces it), so
        this naturally yields an empty list for them without a separate
        branch, same as the dict-based version does via missing keys.

        Args:
            meeting (MentorshipMeetingEntity): A single meeting row.
            mentor_id (int): User ID of the pair's mentor.
            mentee_id (int): User ID of the pair's mentee.

        Returns:
            list[MeetingNoteTag]: Note tags applicable to the meeting.
        """
        notes = []
        if meeting.has_insufficient_duration:
            notes.append(MeetingNoteTag.INSUFFICIENT_DURATION)
        if meeting.has_unknown_absent:
            notes.append(MeetingNoteTag.UNKNOWN_ABSENT)
        elif meeting.absent_user_id:
            if meeting.absent_user_id == mentor_id:
                notes.append(MeetingNoteTag.MENTOR_ABSENT)
            elif meeting.absent_user_id == mentee_id:
                notes.append(MeetingNoteTag.MENTEE_ABSENT)
        if meeting.has_unknown_late:
            notes.append(MeetingNoteTag.UNKNOWN_LATE)
        else:
            late_user_ids = meeting.late_user_ids or []
            if mentor_id in late_user_ids:
                notes.append(MeetingNoteTag.MENTOR_LATE)
            if mentee_id in late_user_ids:
                notes.append(MeetingNoteTag.MENTEE_LATE)
        return notes

    def _meeting_row_to_admin_dict(self, meeting: MentorshipMeetingEntity) -> dict:
        """
        Bridge a `MentorshipMeetingEntity` row into the dict shape
        `map_to_admin_meeting_dto` expects (the same shape a JSONB entry used
        to have), converting its datetime columns to the ISO strings
        `AdminMeetingDto`'s fields are typed as.

        Only called for MANUAL/GOOGLE rows, whose `start_datetime` /
        `end_datetime` / `created_datetime` are never NULL (only LEGACY rows
        have NULL times, and callers must exclude those before reaching here).

        Args:
            meeting (MentorshipMeetingEntity): A single meeting row.

        Returns:
            dict: meeting_id/start_datetime/end_datetime/created_datetime,
                with the datetimes as ISO strings.
        """
        return {
            "meeting_id": meeting.meeting_id,
            "start_datetime": meeting.start_datetime.isoformat(),
            "end_datetime": meeting.end_datetime.isoformat(),
            "created_datetime": meeting.created_datetime.isoformat(),
        }

    async def get_round_feedback(
        self, session: AsyncSession, round_id: int
    ) -> RoundFeedbackDto:
        """
        Everyone a round's feedback is asked of, with what each of them sent.

        What someone wrote about a partner stays on the writer's row: it is
        their view of the partner, not the partner's feedback.

        Args:
            session (AsyncSession): The active async database session.
            round_id (int): Mentorship round id.

        Returns:
            RoundFeedbackDto: The round, its counts, and one row per person.

        Raises:
            ValueError: The round does not exist.
        """
        round_entity = await self.rounds_repository.get_by_round_id(session, round_id)
        if round_entity is None:
            raise ValueError(f"Mentorship round {round_id} does not exist.")

        owed = await self.participants_repository.get_feedback_owed_in_round(
            session, round_id
        )
        partner_ids = {
            entry["partner_id"]
            for participant, _ in owed
            for entry in self._pair_feedback_entries(participant)
        }
        partners = {
            user.user_id: user
            for user in await self.users_repository.get_all_by_ids(
                session, list(partner_ids)
            )
        }

        rows = [
            self._participant_feedback(participant, user, partners)
            for participant, user in owed
        ]
        return RoundFeedbackDto(
            round_id=round_entity.round_id,
            round_name=round_entity.name,
            owed=len(rows),
            sent=sum(row.has_submitted for row in rows),
            participants=rows,
        )

    def _pair_feedback_entries(self, participant) -> list[dict]:
        """The participant's partner entries that name a partner."""
        entries = participant.pair_feedback
        if not isinstance(entries, list):
            return []
        return [
            e
            for e in entries
            if isinstance(e, dict) and e.get("partner_id") is not None
        ]

    def _participant_feedback(
        self, participant, user, partners: dict
    ) -> ParticipantFeedbackDto:
        """Map one owed participant and their feedback, if any."""
        program = participant.program_feedback
        submitted = isinstance(program, dict)
        program = program if submitted else {}

        partner_feedback = []
        for entry in self._pair_feedback_entries(participant):
            partner = partners.get(entry["partner_id"])
            partner_feedback.append(
                AdminPartnerFeedbackDto(
                    partner_id=entry["partner_id"],
                    partner_name=user_display_name(
                        first_name=partner.first_name,
                        last_name=partner.last_name,
                        preferred_name=partner.preferred_name,
                    )
                    if partner
                    else None,
                    rating=entry.get("rating"),
                    feedback=entry.get("feedback"),
                )
            )

        return ParticipantFeedbackDto(
            user_id=user.user_id,
            name=user_display_name(
                first_name=user.first_name,
                last_name=user.last_name,
                preferred_name=user.preferred_name,
            ),
            role=participant.participant_role,
            has_submitted=submitted,
            most_valuable_aspects=program.get("most_valuable_aspects"),
            challenges=program.get("challenges"),
            program_rating=program.get("program_rating"),
            partner_feedback=partner_feedback,
        )

    async def get_meeting_log(
        self, session: AsyncSession, pair_id: int
    ) -> AdminMeetingLogDto | None:
        """
        Fetch the meeting log for a mentorship pair.

        Args:
            session (AsyncSession): Active database async session.
            pair_id (int): ID of the mentorship pair.

        Returns:
            AdminMeetingLogDto | None: Meeting log for the pair, or None if the pair
            does not exist.
        """
        pair = await self.pairs_repository.get_pair_by_id(session, pair_id)
        if pair is None:
            return None
        return await self._build_meeting_log_dto(session, pair)

    async def _build_meeting_log_dto(
        self, session: AsyncSession, pair
    ) -> AdminMeetingLogDto:
        """
        Builds an AdminMeetingLogDto from a pair's `mentorship_meeting` rows.

        Reads MANUAL and GOOGLE rows for the pair in one query (LEGACY rows
        are excluded -- they carry no times and have nothing to show in this
        list). There is no separate priority branch per generation: a pair
        holding both generations shows both, in the order the repository
        already returned them, instead of one silently hiding the other.

        Ordering decision: this method trusts
        `MentorshipMeetingRepository.get_meetings_by_pair`'s own order
        (`start_datetime` ascending, then `created_datetime`, then
        `meeting_id`) rather than re-sorting by `created_datetime` to match
        this admin log's old JSONB-era order. See the PR report for the
        rationale; it is a deliberate, user-visible change, pinned by a test.

        round_version is derived from what the rows actually are rather than
        assumed: any GOOGLE row present means "v2"; only MANUAL rows means
        "v1"; no rows at all keeps the "v2" default.

        Args:
            session (AsyncSession): Active database async session.
            pair: The pair to build a meeting log for. Must have `pair_id`,
                `mentor_id`, and `mentee_id` populated.

        Returns:
            AdminMeetingLogDto: The pair's meeting log built from rows.
        """
        meetings = await self.mentorship_meeting_repository.get_meetings_by_pair(
            session, pair.pair_id
        )
        if not meetings:
            round_version = "v2"
        elif any(m.source == MeetingSource.GOOGLE for m in meetings):
            round_version = "v2"
        else:
            round_version = "v1"

        mentor_id = pair.mentor_id
        mentee_id = pair.mentee_id
        meeting_dtos = [
            self.mentorship_mapper.map_to_admin_meeting_dto(
                self._meeting_row_to_admin_dict(m),
                is_completed=m.is_completed,
                note_tags=self._resolve_meeting_notes_from_row(m, mentor_id, mentee_id),
            )
            for m in meetings
        ]

        return AdminMeetingLogDto(round_version=round_version, meetings=meeting_dtos)

    def _validate_note_tags(self, note: list[MeetingNoteTag] | None) -> None:
        """
        Raises ValueError if note combines mutually exclusive tags.

        At most one absent tag; unknown_late cannot combine with a specific
        late tag; mentor_late and mentee_late may coexist. The same role
        cannot be marked as both absent and late.
        """
        if note is None:
            return
        tags = set(note)
        if len(tags & self._ABSENT_TAGS) > 1:
            raise ValueError(f"note cannot combine more than one absent tag: {note}")
        if MeetingNoteTag.UNKNOWN_LATE in tags and tags & self._SPECIFIC_LATE_TAGS:
            raise ValueError(
                f"note cannot combine unknown_late with a specific late tag: {note}"
            )
        if (
            MeetingNoteTag.MENTOR_ABSENT in tags and MeetingNoteTag.MENTOR_LATE in tags
        ) or (
            MeetingNoteTag.MENTEE_ABSENT in tags and MeetingNoteTag.MENTEE_LATE in tags
        ):
            raise ValueError(
                f"note cannot mark the same role both absent and late: {note}"
            )

    def _validate_no_absent_if_completed(
        self, meeting: MentorshipMeetingEntity
    ) -> None:
        """
        Prevent `is_completed` and absent note tags from coexisting.

        Must be called after `is_completed` and `note` have been merged
        into `meeting`; otherwise it may validate against stale or
        partial state.

        Args:
            meeting (MentorshipMeetingEntity): The meeting row with
                `is_completed` and absent tag fields already resolved to
                their final values for this update.

        Raises:
            ValueError: If `is_completed` is true and an absent tag
                (unknown, mentor, or mentee) is set.
        """
        if meeting.is_completed and (
            meeting.has_unknown_absent or meeting.absent_user_id is not None
        ):
            raise ValueError(
                f"Cannot mark meeting {meeting.meeting_id} completed while a "
                "participant is marked absent."
            )

    def _apply_note_tags(
        self,
        meeting: MentorshipMeetingEntity,
        note: list[MeetingNoteTag],
        mentor_id: int,
        mentee_id: int,
    ) -> None:
        """
        Writes note's tags onto a meeting row's persisted attributes.

        `late_user_ids` (`ARRAY(Integer)`) is not `Mutable`-wrapped, so it is
        always assigned a whole new list here, never appended to in place --
        an in-place append would not be seen by the unit of work and would
        silently fail to persist.
        """
        meeting.has_insufficient_duration = MeetingNoteTag.INSUFFICIENT_DURATION in note
        meeting.has_unknown_absent = MeetingNoteTag.UNKNOWN_ABSENT in note
        if MeetingNoteTag.MENTOR_ABSENT in note:
            meeting.absent_user_id = mentor_id
        elif MeetingNoteTag.MENTEE_ABSENT in note:
            meeting.absent_user_id = mentee_id
        else:
            meeting.absent_user_id = None
        meeting.has_unknown_late = MeetingNoteTag.UNKNOWN_LATE in note
        late_user_ids = []
        if MeetingNoteTag.MENTOR_LATE in note:
            late_user_ids.append(mentor_id)
        if MeetingNoteTag.MENTEE_LATE in note:
            late_user_ids.append(mentee_id)
        meeting.late_user_ids = late_user_ids

    async def apply_v2_meeting_batch(
        self,
        session: AsyncSession,
        pair_id: int,
        batch: V2MeetingBatchUpdateDto,
    ) -> AdminMeetingLogDto:
        """
        Apply incremental updates/deletes to a pair's v2 meeting log.

        Locks the pair row for the duration of the transaction, applies all
        deletes then all updates against the current DB state (not the
        client's snapshot), recalculates completed_count, and returns the
        pair's latest meeting log.

        Args:
            session (AsyncSession): Active database async session.
            pair_id (int): The mentorship pair ID.
            batch (V2MeetingBatchUpdateDto): Meeting updates and deletions.

        Returns:
            AdminMeetingLogDto: The pair's meeting log after applying batch.

        Raises:
            ValueError: updates and deletes are both empty; the same
                meeting_id appears in both; a meeting_id doesn't exist among
                this pair's rows; or the pair itself doesn't exist.
            ConflictError: Any targeted meeting_id (update or delete) belongs
                to a MANUAL row (v1, read-only history). The check is
                per-row, not per-pair -- a pair holding both MANUAL and
                GOOGLE rows may still have its GOOGLE rows edited freely;
                only a targeted row that is itself MANUAL is rejected.
        """
        if not batch.updates and not batch.deletes:
            raise ValueError("updates and deletes must not both be empty.")

        update_ids = {item.meeting_id for item in batch.updates}
        delete_ids = set(batch.deletes)
        overlap = update_ids & delete_ids
        if overlap:
            raise ValueError(
                f"meeting_id(s) cannot appear in both updates and deletes: {sorted(overlap)}"
            )
        for item in batch.updates:
            self._validate_note_tags(item.note)

        pair = await self.pairs_repository.get_pair_by_id(
            session, pair_id, with_lock=True
        )
        if pair is None:
            raise ValueError(f"Mentorship pair {pair_id} not found.")

        meetings = await self.mentorship_meeting_repository.get_meetings_by_pair(
            session, pair_id
        )
        by_id = {m.meeting_id: m for m in meetings}
        target_ids = update_ids | delete_ids
        missing = target_ids - by_id.keys()
        if missing:
            raise ValueError(
                f"meeting_id(s) not found for this pair: {sorted(missing)}"
            )

        manual_targets = {
            mid for mid in target_ids if by_id[mid].source == MeetingSource.MANUAL
        }
        if manual_targets:
            raise ConflictError("Cannot edit a v1 (read-only) meeting log.")

        if delete_ids:
            await self.mentorship_meeting_repository.delete_meetings(
                session, pair_id, list(delete_ids)
            )
        for item in batch.updates:
            meeting = by_id[item.meeting_id]
            if item.is_completed is not None:
                meeting.is_completed = item.is_completed
            if item.note is not None:
                self._apply_note_tags(
                    meeting, item.note, pair.mentor_id, pair.mentee_id
                )
            if item.is_completed is not None or item.note is not None:
                self._validate_no_absent_if_completed(meeting)

        # Assigned directly rather than left for the ORM to refresh -- same
        # rationale as MeetingService.upsert_meetings: the UPDATE issued here
        # sets completed_count from a scalar subquery, which falls back to the
        # "fetch" synchronize strategy and EXPIRES completed_count on this
        # loaded pair rather than repopulating it; reading it after commit()
        # without reassigning would raise MissingGreenlet under async.
        pair.completed_count = (
            await self.mentorship_meeting_repository.recalculate_completed_count(
                session, pair_id
            )
        )

        await session.commit()

        self.logger.info(
            "[MentorshipAdminService] meeting log batch applied for pair_id=%s: updated=%d, deleted=%d",
            pair_id,
            len(batch.updates),
            len(delete_ids),
        )

        return await self._build_meeting_log_dto(session, pair)
