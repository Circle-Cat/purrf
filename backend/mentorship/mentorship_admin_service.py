import csv
import io
from collections.abc import AsyncIterator
from sqlalchemy.ext.asyncio import AsyncSession
from backend.dto.participant_search_filter_dto import ParticipantSearchFilterDto
from backend.dto.participant_search_dto import ParticipantRowDto, ParticipantSearchDto
from backend.dto.participant_search_row_dto import ParticipantSearchRow
from backend.dto.partner_dto import PartnerDto
from backend.dto.admin_meeting_log_dto import AdminMeetingDto, AdminMeetingLogDto
from backend.dto.v2_meeting_batch_update_dto import V2MeetingBatchUpdateDto
from backend.common.exceptions import ConflictError
from backend.common.mentorship_enums import (
    MENTORSHIP_ONBOARDING_CATEGORIES,
    MeetingNoteTag,
    MeetingSource,
    ParticipantRole,
    TrainingCategory,
)
from backend.common.name_utils import partner_display_name
from backend.entity.mentorship_meeting_entity import MentorshipMeetingEntity

_EXPORT_BATCH_SIZE = 500
_UTF8_BOM = "\ufeff".encode("utf-8")
_CSV_FORMULA_PREFIXES = ("=", "+", "-", "@")


def _sanitize_csv_field(value: str | None) -> str | None:
    """
    Neutralize CSV formula injection in a text cell.

    If the value starts with a formula-triggering character ('=', '+', '-',
    or '@') after leading whitespace is ignored, prefix it with a single
    quote so spreadsheet applications treat it as literal text.

    Args:
        value (str | None): The raw cell value.

    Returns:
        str | None: The sanitized value, or the original value if no
        sanitization is required.
    """
    if value and value.lstrip().startswith(_CSV_FORMULA_PREFIXES):
        return f"'{value}"
    return value


_EXPORT_COMMON_COLUMNS = [
    "User ID",
    "First Name",
    "Last Name",
    "Preferred Name",
    "Primary Email",
    "Alternative Emails",
]
_EXPORT_PARTICIPANT_COLUMNS = [
    "Round",
    "Participant Role",
    "Approval Status",
    "Onboarding Status",
    "Matched User ID",
    "Matched User Name",
]
_EXPORT_NON_PARTICIPANT_COLUMNS = [
    "Mentor Onboarding Status",
    "Mentee Onboarding Status",
]
_EXPORT_MEETING_SUMMARY_COLUMNS = [
    "Completed Meetings",
    "Required Meetings",
]
_EXPORT_MEETING_DETAIL_COLUMNS = [
    "Complete Status",
    "Start Datetime (PT)",
    "End Datetime (PT)",
    "Note",
]


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
        date_time_util,
        database,
        logger,
        mentorship_meeting_repository,
    ) -> None:
        self.users_repository = users_repository
        self.participants_repository = participants_repository
        self.rounds_repository = rounds_repository
        self.training_repository = training_repository
        self.pairs_repository = pairs_repository
        self.mentorship_mapper = mentorship_mapper
        self.date_time_util = date_time_util
        self.database = database
        self.logger = logger
        self.mentorship_meeting_repository = mentorship_meeting_repository

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
            if row.mentor_id is not None:
                mentorship_user_ids.add(row.mentor_id)
            if row.mentee_id is not None:
                mentorship_user_ids.add(row.mentee_id)
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

    def _get_partner_user(self, row: ParticipantSearchRow, users_map: dict):
        """
        Resolve the matched partner's user record for a participant search row.

        Args:
            row (ParticipantSearchRow): The row to resolve a partner for.
            users_map (dict[int, UsersEntity]): User records keyed by user_id.

        Returns:
            The partner's user record, or None if the row has no pair or
            the partner isn't in users_map.
        """
        if row.pair_id is None:
            return None
        partner_id = row.mentee_id if row.user_id == row.mentor_id else row.mentor_id
        return users_map.get(partner_id)

    def _build_common_export_columns(
        self,
        row: ParticipantSearchRow,
        users_map: dict,
        emails_map: dict,
    ) -> list:
        """
        Build the CSV columns shared by every export row, participant or not.

        Args:
            row (ParticipantSearchRow): The row to build columns for.
            users_map (dict[int, UsersEntity]): User records keyed by user_id.
            emails_map (dict[int, list[UserEmailsEntity]]): Email records keyed by user_id.

        Returns:
            list: Columns in _EXPORT_COMMON_COLUMNS order.
        """
        user = users_map[row.user_id]
        primary_email, alternative_emails = self._extract_emails(
            emails_map.get(row.user_id, [])
        )
        return [
            row.user_id,
            _sanitize_csv_field(user.first_name),
            _sanitize_csv_field(user.last_name),
            _sanitize_csv_field(user.preferred_name),
            _sanitize_csv_field(primary_email),
            _sanitize_csv_field(";".join(alternative_emails)),
        ]

    def _build_participant_export_columns(
        self,
        row: ParticipantSearchRow,
        users_map: dict,
        trainings_map: dict,
        rounds_map: dict,
    ) -> list:
        """
        Build the CSV columns specific to a participant export row.

        Onboarding Status reflects the row's own participant role: mentee
        onboarding status if the row is a mentee, otherwise mentor
        onboarding status. The matched user's name follows the existing
        partner display-name convention (preferred name if available;
        otherwise "first last").

        Args:
            row (ParticipantSearchRow): The row to build columns for.
            users_map (dict[int, UsersEntity]): User records keyed by user_id.
            trainings_map (dict[int, dict[TrainingCategory, TrainingStatus]]): Training status keyed by user_id, then category.
            rounds_map (dict[int, MentorshipRoundEntity]): Round records keyed by round_id.

        Returns:
            list: Columns in _EXPORT_PARTICIPANT_COLUMNS order.
        """
        round_entity = rounds_map.get(row.round_id) if row.round_id else None

        statuses = trainings_map.get(row.user_id, {})
        mentor_status = statuses.get(TrainingCategory.MENTORSHIP_MENTOR_ONBOARDING)
        mentee_status = statuses.get(TrainingCategory.MENTORSHIP_MENTEE_ONBOARDING)
        if row.participant_role == ParticipantRole.MENTEE:
            onboarding_status = mentee_status
        else:
            onboarding_status = mentor_status

        matched_user_id = ""
        matched_user_name = ""
        partner = self._get_partner_user(row, users_map)
        if partner:
            matched_user_id = partner.user_id
            matched_user_name = partner_display_name(
                first_name=partner.first_name,
                last_name=partner.last_name,
                preferred_name=partner.preferred_name,
            )

        return [
            _sanitize_csv_field(round_entity.name) if round_entity else "",
            row.participant_role.value if row.participant_role else "",
            row.approval_status.value if row.approval_status else "",
            onboarding_status.value if onboarding_status else "",
            matched_user_id,
            _sanitize_csv_field(matched_user_name),
        ]

    def _build_non_participant_export_columns(
        self,
        row: ParticipantSearchRow,
        trainings_map: dict,
    ) -> list:
        """
        Build the CSV columns specific to a non-participant export row.

        Args:
            row (ParticipantSearchRow): The row to build columns for.
            trainings_map (dict[int, dict[TrainingCategory, TrainingStatus]]): Training status keyed by user_id, then category.

        Returns:
            list: Columns in _EXPORT_NON_PARTICIPANT_COLUMNS order.
        """
        statuses = trainings_map.get(row.user_id, {})
        mentor_status = statuses.get(TrainingCategory.MENTORSHIP_MENTOR_ONBOARDING)
        mentee_status = statuses.get(TrainingCategory.MENTORSHIP_MENTEE_ONBOARDING)
        return [
            mentor_status.value if mentor_status else "",
            mentee_status.value if mentee_status else "",
        ]

    def _extract_meetings_for_row(
        self,
        row: ParticipantSearchRow,
        meetings: list[MentorshipMeetingEntity],
    ) -> list[AdminMeetingDto]:
        """
        Build a row's meetings from its pair's pre-fetched `mentorship_meeting`
        rows.

        `meetings` is expected to already be this row's pair's slice of a
        batched `MentorshipMeetingRepository.get_meetings_by_pairs` result
        (the caller looks it up per row, keyed by pair_id, from one page-wide
        call) -- this method itself issues no query and does not re-sort:
        it trusts the repository's own order (`start_datetime` ascending,
        then `created_datetime`, then `meeting_id`), the same order
        `_build_meeting_log_dto` now trusts. That is a deliberate change from
        this method's old JSONB-era created_datetime sort, made so the two
        read paths agree.

        MANUAL and GOOGLE rows are shown together in whatever order they
        arrive in -- there is no priority branch that hides one generation
        in favor of the other. LEGACY rows (NULL times) are expected to
        already be excluded by the caller's `get_meetings_by_pairs` call.

        Args:
            row (ParticipantSearchRow): The row meetings are being extracted
                for (used only for mentor_id/mentee_id to resolve note tags).
            meetings (list[MentorshipMeetingEntity]): This row's pair's
                meeting rows, already ordered.

        Returns:
            list[AdminMeetingDto]: This row's meetings, in the given order.
        """
        return [
            self.mentorship_mapper.map_to_admin_meeting_dto(
                self._meeting_row_to_admin_dict(m),
                is_completed=m.is_completed,
                note_tags=self._resolve_meeting_notes_from_row(
                    m, row.mentor_id, row.mentee_id
                ),
            )
            for m in meetings
        ]

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

        Executes the participant query, batch-fetches related user, email, round, and
        training data, then assembles the response.

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

        participant_rows: list[ParticipantRowDto] = []
        for row in rows:
            statuses = trainings_map.get(row.user_id, {})
            mentor_status = statuses.get(TrainingCategory.MENTORSHIP_MENTOR_ONBOARDING)
            mentee_status = statuses.get(TrainingCategory.MENTORSHIP_MENTEE_ONBOARDING)

            user = users_map[row.user_id]
            primary_email, alternative_emails = self._extract_emails(
                emails_map.get(row.user_id, [])
            )

            partner = self._get_partner_user(row, users_map)
            matched_user = None
            if partner:
                matched_user = PartnerDto(
                    id=partner.user_id,
                    first_name=partner.first_name or "",
                    last_name=partner.last_name or "",
                    preferred_name=partner.preferred_name or "",
                    primary_email=None,
                    participant_role=None,
                    recommendation_reason=None,
                )

            round_entity = rounds_map.get(row.round_id) if row.round_id else None

            participant_rows.append(
                ParticipantRowDto(
                    user_id=row.user_id,
                    round_id=row.round_id,
                    round_name=round_entity.name if round_entity else None,
                    pair_id=row.pair_id,
                    first_name=user.first_name,
                    last_name=user.last_name,
                    preferred_name=user.preferred_name,
                    primary_email=primary_email,
                    alternative_emails=alternative_emails,
                    matched_user=matched_user,
                    participant_role=row.participant_role,
                    approval_status=row.approval_status,
                    mentor_onboarding_status=mentor_status,
                    mentee_onboarding_status=mentee_status,
                    completed_meeting_count=row.completed_count,
                    required_meetings=self._get_required_meetings(row, rounds_map),
                )
            )

        return ParticipantSearchDto(participant_rows=participant_rows, total=total)

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

    async def stream_export_csv(
        self,
        filters: ParticipantSearchFilterDto,
        expand_meetings: bool = False,
    ) -> AsyncIterator[bytes]:
        """
        Stream participant search results as BOM-prefixed UTF-8 CSV data chunks.

        Uses its own database session because StreamingResponse consumes
        this generator after the controller returns.

        An export row that fails to build is logged and skipped instead of
        aborting the stream. When expanding meetings, a pair's meeting rows
        are built before writing to avoid partially exporting a participant
        when one meeting fails.

        When expand_meetings needs meeting data, it is fetched with exactly
        one `mentorship_meeting_repository.get_meetings_by_pairs` call per
        page (grouped by pair_id, up to _EXPORT_BATCH_SIZE pairs), not one
        query per row -- the same batching this method already applies to
        users/emails/trainings via `_fetch_batch_relations`.

        Args:
            filters (ParticipantSearchFilterDto): Same filters as the search
                endpoint. filters.participation_status must be set, since it
                decides which column set the export uses.
            expand_meetings (bool): False (default) yields one row per
                participant record. True yields one row per meeting (a
                participant with no meetings still gets one row, with the
                meeting columns left blank). Ignored for a non-participant
                export, which has no meeting data.

        Yields:
            bytes: UTF-8 encoded CSV batch bytes.

        Raises:
            ValueError: If filters.participation_status is not set.
        """
        if filters.participation_status is None:
            raise ValueError("filters.participation_status is required for CSV export.")
        is_participant = filters.participation_status == "participant"
        need_meetings = is_participant and expand_meetings
        buffer = io.StringIO()
        writer = csv.writer(buffer)

        def drain_buffer() -> bytes:
            data = buffer.getvalue()
            buffer.seek(0)
            buffer.truncate(0)
            return data.encode("utf-8")

        if is_participant:
            meeting_columns = (
                _EXPORT_MEETING_DETAIL_COLUMNS
                if expand_meetings
                else _EXPORT_MEETING_SUMMARY_COLUMNS
            )
            header = (
                _EXPORT_COMMON_COLUMNS + _EXPORT_PARTICIPANT_COLUMNS + meeting_columns
            )
        else:
            header = _EXPORT_COMMON_COLUMNS + _EXPORT_NON_PARTICIPANT_COLUMNS
        writer.writerow(header)
        yield _UTF8_BOM + drain_buffer()

        async with self.database.session() as session:
            rounds = await self.rounds_repository.get_all_rounds(session)
            rounds_map = {r.round_id: r for r in rounds}

            offset = 0
            while True:
                rows = await self.participants_repository.iter_search_participants_for_admin(
                    session,
                    filters,
                    limit=_EXPORT_BATCH_SIZE,
                    offset=offset,
                )
                if not rows:
                    break

                (
                    users_map,
                    emails_map,
                    trainings_map,
                ) = await self._fetch_batch_relations(session, rows)

                # One batched call for the whole page instead of a per-row
                # query -- get_meetings_by_pairs excludes LEGACY rows (NULL
                # times) by default, which must never reach a meeting column
                # that expects a real datetime.
                meetings_by_pair: dict[int, list[MentorshipMeetingEntity]] = {}
                if need_meetings:
                    pair_ids = [row.pair_id for row in rows if row.pair_id is not None]
                    meetings_by_pair = (
                        await self.mentorship_meeting_repository.get_meetings_by_pairs(
                            session=session, pair_ids=pair_ids
                        )
                    )

                for row in rows:
                    try:
                        common = self._build_common_export_columns(
                            row, users_map, emails_map
                        )
                        if is_participant:
                            participant = self._build_participant_export_columns(
                                row, users_map, trainings_map, rounds_map
                            )
                            if not expand_meetings:
                                csv_rows = [
                                    common
                                    + participant
                                    + [
                                        row.completed_count,
                                        self._get_required_meetings(row, rounds_map),
                                    ]
                                ]
                            else:
                                meetings = self._extract_meetings_for_row(
                                    row, meetings_by_pair.get(row.pair_id, [])
                                )
                                if meetings:
                                    csv_rows = [
                                        common
                                        + participant
                                        + [
                                            "Completed"
                                            if meeting.is_completed
                                            else "Incomplete",
                                            self.date_time_util.format_iso_utc_to_pt(
                                                meeting.start_datetime,
                                                fmt="%Y-%m-%d %H:%M %Z",
                                            ),
                                            self.date_time_util.format_iso_utc_to_pt(
                                                meeting.end_datetime,
                                                fmt="%Y-%m-%d %H:%M %Z",
                                            ),
                                            "; ".join(
                                                tag.value for tag in meeting.note
                                            ),
                                        ]
                                        for meeting in meetings
                                    ]
                                else:
                                    csv_rows = [common + participant + ["", "", "", ""]]
                        else:
                            non_participant = (
                                self._build_non_participant_export_columns(
                                    row, trainings_map
                                )
                            )
                            csv_rows = [common + non_participant]
                    except Exception:
                        self.logger.exception(
                            "Failed to build CSV row during export, "
                            "skipping row: user_id=%s, pair_id=%s, "
                            "round_id=%s",
                            row.user_id,
                            row.pair_id,
                            row.round_id,
                        )
                        continue

                    for csv_row in csv_rows:
                        writer.writerow(csv_row)
                yield drain_buffer()
                offset += _EXPORT_BATCH_SIZE
