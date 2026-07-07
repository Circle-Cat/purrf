from sqlalchemy.ext.asyncio import AsyncSession
from backend.dto.participant_search_filter_dto import ParticipantSearchFilterDto
from backend.dto.participant_search_dto import ParticipantRowDto, ParticipantSearchDto
from backend.dto.partner_dto import PartnerDto
from backend.dto.admin_meeting_log_dto import AdminMeetingLogDto
from backend.common.mentorship_enums import (
    MeetingNoteTag,
    ParticipantRole,
    TrainingCategory,
    TrainingStatus,
)
from backend.entity.user_emails_entity import UserEmailsEntity


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
    ) -> None:
        self.users_repository = users_repository
        self.participants_repository = participants_repository
        self.rounds_repository = rounds_repository
        self.training_repository = training_repository
        self.pairs_repository = pairs_repository
        self.mentorship_mapper = mentorship_mapper

    def _extract_emails(
        self, emails: list[UserEmailsEntity]
    ) -> tuple[str | None, list[str]]:
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

    def _is_onboarding_completed(
        self,
        participant_role: ParticipantRole | None,
        mentor_status: TrainingStatus | None,
        mentee_status: TrainingStatus | None,
    ) -> bool:
        """
        Return True if onboarding is completed for the given role and training statuses.

        For participants, only the training category matching their role is checked.
        For non-participants (no role), either category being DONE counts as completed;
        no records yields False.

        Args:
            participant_role (ParticipantRole | None): The user's role, or None for
                non-participants.
            mentor_status (TrainingStatus | None): Mentor onboarding training status.
            mentee_status (TrainingStatus | None): Mentee onboarding training status.

        Returns:
            bool: True if onboarding is completed, False otherwise.
        """
        if participant_role == ParticipantRole.MENTOR:
            return mentor_status == TrainingStatus.DONE
        if participant_role == ParticipantRole.MENTEE:
            return mentee_status == TrainingStatus.DONE
        return (
            mentor_status == TrainingStatus.DONE or mentee_status == TrainingStatus.DONE
        )

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

        Executes the main participant query, batch-fetches user/email/round/training
        data, and assembles each row into a ParticipantRowDto. If onboarding_status
        is specified, it is applied during row processing on the already-paginated
        result set. This means total always reflects the repository count before
        onboarding_status filtering.

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

        all_user_ids: set[int] = set()
        participant_user_ids: set[int] = set()
        for row in rows:
            all_user_ids.add(row.user_id)
            if row.mentor_id is not None:
                all_user_ids.add(row.mentor_id)
            if row.mentee_id is not None:
                all_user_ids.add(row.mentee_id)
            participant_user_ids.add(row.user_id)

        users_map, emails_map = await self.users_repository.get_users_and_emails_by_ids(
            session, list(all_user_ids)
        )

        rounds = await self.rounds_repository.get_all_rounds(session)
        rounds_map = {r.round_id: r for r in rounds}

        trainings = (
            await self.training_repository.get_training_by_user_ids_and_categories(
                session,
                list(participant_user_ids),
                categories=[
                    TrainingCategory.MENTORSHIP_MENTOR_ONBOARDING,
                    TrainingCategory.MENTORSHIP_MENTEE_ONBOARDING,
                ],
            )
        )
        trainings_map: dict[int, dict[TrainingCategory, TrainingStatus]] = {}
        for t in trainings:
            trainings_map.setdefault(t.user_id, {})[t.category] = t.status

        is_completed = None
        if filters.onboarding_status:
            is_completed = filters.onboarding_status == "completed"

        participant_rows: list[ParticipantRowDto] = []
        for row in rows:
            statuses = trainings_map.get(row.user_id, {})
            mentor_status = statuses.get(TrainingCategory.MENTORSHIP_MENTOR_ONBOARDING)
            mentee_status = statuses.get(TrainingCategory.MENTORSHIP_MENTEE_ONBOARDING)

            result = self._is_onboarding_completed(
                row.participant_role, mentor_status, mentee_status
            )
            if is_completed is not None and result != is_completed:
                continue

            user = users_map[row.user_id]
            primary_email, alternative_emails = self._extract_emails(
                emails_map.get(row.user_id, [])
            )

            matched_user = None
            if row.pair_id is not None:
                if row.user_id == row.mentor_id:
                    partner_id = row.mentee_id
                else:
                    partner_id = row.mentor_id
                partner = users_map.get(partner_id)
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
                    required_meetings=round_entity.required_meetings
                    if round_entity
                    else None,
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
            late_user_ids = meeting.get("late_user_ids") or []
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
