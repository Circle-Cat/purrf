import csv
import io
from typing import Literal
from collections.abc import AsyncIterator
from sqlalchemy.ext.asyncio import AsyncSession
from backend.dto.participant_search_filter_dto import ParticipantSearchFilterDto
from backend.dto.participant_search_dto import ParticipantRowDto, ParticipantSearchDto
from backend.dto.participant_search_row_dto import ParticipantSearchRow
from backend.dto.partner_dto import PartnerDto
from backend.dto.admin_meeting_log_dto import AdminMeetingDto, AdminMeetingLogDto
from backend.common.mentorship_enums import (
    MENTORSHIP_ONBOARDING_CATEGORIES,
    MeetingNoteTag,
    ParticipantRole,
    TrainingCategory,
)
from backend.common.name_utils import partner_display_name

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
        self, row: ParticipantSearchRow
    ) -> list[AdminMeetingDto]:
        """
        Extract a row's meetings from its preloaded meeting log.

        Reuses the same v1/v2 mapping logic as get_meeting_log(), operating on
        the meeting_log already loaded with the search result instead of querying
        the pair again.

        Args:
            row (ParticipantSearchRow): A row fetched with need_meeting_log=True.

        Returns:
            list[AdminMeetingDto]: This row's meetings, oldest first.
        """
        meeting_log = row.meeting_log or {}
        google_meetings = meeting_log.get("google_meetings") or []
        meeting_time_list = meeting_log.get("meeting_time_list") or []

        if google_meetings:
            return [
                self.mentorship_mapper.map_to_admin_meeting_dto(
                    m,
                    is_completed=m["is_completed"],
                    note_tags=self._resolve_meeting_notes(
                        m, row.mentor_id, row.mentee_id
                    ),
                )
                for m in sorted(google_meetings, key=lambda m: m["created_datetime"])
            ]
        if meeting_time_list:
            return [
                self.mentorship_mapper.map_to_admin_meeting_dto(
                    m, is_completed=True, note_tags=[]
                )
                for m in sorted(meeting_time_list, key=lambda m: m["created_datetime"])
            ]
        return []

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

        Args:
            meeting (dict): A single Google meeting record from the pair's meeting_log.
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

    async def get_meeting_log(
        self, session: AsyncSession, pair_id: int
    ) -> AdminMeetingLogDto | None:
        """
        Fetch the meeting log for a mentorship pair.

        google_meetings and meeting_time_list are mutually exclusive; a pair with
        neither populated defaults to round_version "v2" with an empty meetings list.

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

        meeting_log = pair.meeting_log or {}
        google_meetings = meeting_log.get("google_meetings") or []
        meeting_time_list = meeting_log.get("meeting_time_list") or []

        if google_meetings:
            round_version = "v2"
            mentor_id = pair.mentor_id
            mentee_id = pair.mentee_id
            meetings = [
                self.mentorship_mapper.map_to_admin_meeting_dto(
                    m,
                    is_completed=m["is_completed"],
                    note_tags=self._resolve_meeting_notes(m, mentor_id, mentee_id),
                )
                for m in sorted(google_meetings, key=lambda m: m["created_datetime"])
            ]
        elif meeting_time_list:
            round_version = "v1"
            meetings = [
                self.mentorship_mapper.map_to_admin_meeting_dto(
                    m, is_completed=True, note_tags=[]
                )
                for m in sorted(meeting_time_list, key=lambda m: m["created_datetime"])
            ]
        else:
            round_version = "v2"
            meetings = []

        return AdminMeetingLogDto(round_version=round_version, meetings=meetings)

    async def stream_export_csv(
        self,
        filters: ParticipantSearchFilterDto,
        mode: Literal["summary", "detailed"] | None = None,
    ) -> AsyncIterator[bytes]:
        """
        Stream participant search results as BOM-prefixed UTF-8 CSV data chunks.

        Uses its own database session because StreamingResponse consumes
        this generator after the controller returns.

        An export row that fails to build is logged and skipped instead of
        aborting the stream. In detailed mode, a pair's meeting rows are
        built before writing to avoid partially exporting a participant
        when one meeting fails.

        Args:
            filters (ParticipantSearchFilterDto): Same filters as the search
                endpoint. filters.participation_status must be set, since it
                decides which column set the export uses.
            mode (Literal["summary", "detailed"] | None): "summary" (one row
                per participant record) or "detailed" (one row per meeting;
                a participant with no meetings still gets one row, with the
                meeting columns left blank). Required for a participant
                export. Ignored for a non-participant export.

        Yields:
            bytes: UTF-8 encoded CSV batch bytes.

        Raises:
            ValueError: If filters.participation_status is not set, or
                mode is not set for a participant export.
        """
        if filters.participation_status is None:
            raise ValueError("filters.participation_status is required for CSV export.")
        is_participant = filters.participation_status == "participant"
        if is_participant and mode is None:
            raise ValueError("mode is required for participant export.")
        need_meeting_log = is_participant and mode == "detailed"
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
                if mode == "detailed"
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
                    need_meeting_log=need_meeting_log,
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

                for row in rows:
                    try:
                        common = self._build_common_export_columns(
                            row, users_map, emails_map
                        )
                        if is_participant:
                            participant = self._build_participant_export_columns(
                                row, users_map, trainings_map, rounds_map
                            )
                            if mode == "summary":
                                csv_rows = [
                                    common
                                    + participant
                                    + [
                                        row.completed_count,
                                        self._get_required_meetings(row, rounds_map),
                                    ]
                                ]
                            else:
                                meetings = self._extract_meetings_for_row(row)
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
