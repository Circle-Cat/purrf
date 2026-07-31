import copy
import unittest
from unittest.mock import MagicMock, AsyncMock
from dateutil.parser import isoparse
from backend.mentorship.mentorship_admin_service import MentorshipAdminService
from backend.dto.participant_search_filter_dto import ParticipantSearchFilterDto
from backend.dto.participant_search_row_dto import ParticipantSearchRow
from backend.dto.admin_meeting_log_dto import AdminMeetingDto
from backend.dto.v2_meeting_batch_update_dto import (
    V2MeetingBatchUpdateDto,
    V2MeetingUpdateItemDto,
)
from backend.entity.mentorship_meeting_entity import MentorshipMeetingEntity
from backend.common.exceptions import ConflictError
from backend.common.mentorship_enums import (
    ApprovalStatus,
    MeetingNoteTag,
    MeetingSource,
    ParticipantRole,
    TrainingCategory,
    TrainingStatus,
)


def _make_row(**kwargs):
    row_fields = dict(
        user_id=1,
        round_id=None,
        pair_id=None,
        participant_role=None,
        approval_status=None,
        completed_count=None,
        mentor_id=None,
        mentee_id=None,
    )
    row_fields.update(kwargs)
    return ParticipantSearchRow(**row_fields)


async def _collect_csv(agen) -> str:
    """Decodes with utf-8-sig to strip the leading UTF-8 BOM the export writes."""
    chunks = [chunk async for chunk in agen]
    return b"".join(chunks).decode("utf-8-sig")


def _make_pair(mentor_id=1, mentee_id=2, pair_id=1):
    pair = MagicMock()
    pair.pair_id = pair_id
    pair.mentor_id = mentor_id
    pair.mentee_id = mentee_id
    # A stand-in for the legacy JSONB blob. apply_v2_meeting_batch must never
    # read or write this -- present so the "left untouched" pin test has
    # something concrete to compare against.
    pair.meeting_log = {"untouched": True}
    return pair


def _make_meeting(
    meeting_id="m1",
    pair_id=1,
    source=MeetingSource.GOOGLE,
    start_datetime="2024-01-01T10:00:00+00:00",
    end_datetime="2024-01-01T11:00:00+00:00",
    is_completed=False,
    created_datetime="2024-01-01T09:00:00+00:00",
    absent_user_id=None,
    late_user_ids=None,
    has_unknown_absent=None,
    has_unknown_late=None,
    has_insufficient_duration=None,
):
    """A real (unpersisted) MentorshipMeetingEntity -- this is what the admin
    read and edit paths now work with instead of JSONB dict entries."""
    return MentorshipMeetingEntity(
        meeting_id=meeting_id,
        pair_id=pair_id,
        source=source,
        start_datetime=isoparse(start_datetime) if start_datetime else None,
        end_datetime=isoparse(end_datetime) if end_datetime else None,
        is_completed=is_completed,
        created_datetime=isoparse(created_datetime) if created_datetime else None,
        absent_user_id=absent_user_id,
        late_user_ids=late_user_ids,
        has_unknown_absent=has_unknown_absent,
        has_unknown_late=has_unknown_late,
        has_insufficient_duration=has_insufficient_duration,
    )


class TestMentorshipAdminService(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.mock_users_repo = MagicMock()
        self.mock_users_repo.get_users_and_emails_by_ids = AsyncMock()

        self.mock_participants_repo = MagicMock()
        self.mock_participants_repo.search_participants_for_admin = AsyncMock()
        self.mock_participants_repo.iter_search_participants_for_admin = AsyncMock()

        self.mock_rounds_repo = MagicMock()
        self.mock_rounds_repo.get_all_rounds = AsyncMock(return_value=[])

        self.mock_training_repo = MagicMock()
        self.mock_training_repo.get_training_by_user_ids_and_categories = AsyncMock(
            return_value=[]
        )

        self.mock_pairs_repo = MagicMock()
        self.mock_pairs_repo.get_pair_by_id = AsyncMock()

        self.mock_meeting_repo = MagicMock()
        self.mock_meeting_repo.get_meetings_by_pair = AsyncMock(return_value=[])
        self.mock_meeting_repo.get_meetings_by_pairs = AsyncMock(return_value={})
        self.mock_meeting_repo.delete_meetings = AsyncMock(return_value=0)
        self.mock_meeting_repo.recalculate_completed_count = AsyncMock(
            return_value=0
        )

        self.mock_mapper = MagicMock()
        self.mock_mapper.map_to_admin_meeting_dto.side_effect = (
            lambda meeting, *, is_completed, note_tags: AdminMeetingDto(
                meeting_id=meeting["meeting_id"],
                start_datetime=meeting["start_datetime"],
                end_datetime=meeting["end_datetime"],
                is_completed=is_completed,
                note=note_tags,
                create_datetime=meeting["created_datetime"],
            )
        )

        self.mock_session = AsyncMock()
        self.mock_database = MagicMock()
        self.mock_database.session.return_value.__aenter__.return_value = (
            self.mock_session
        )
        self.mock_database.session.return_value.__aexit__.return_value = None

        self.mock_date_time_util = MagicMock()
        self.mock_date_time_util.format_iso_utc_to_pt.side_effect = (
            lambda iso, fmt="%Y-%m-%d %H:%M %Z": f"PT({iso})"
        )
        self.mock_logger = MagicMock()

        self.service = MentorshipAdminService(
            users_repository=self.mock_users_repo,
            participants_repository=self.mock_participants_repo,
            rounds_repository=self.mock_rounds_repo,
            training_repository=self.mock_training_repo,
            pairs_repository=self.mock_pairs_repo,
            mentorship_mapper=self.mock_mapper,
            date_time_util=self.mock_date_time_util,
            database=self.mock_database,
            logger=self.mock_logger,
            mentorship_meeting_repository=self.mock_meeting_repo,
        )

    async def test_empty_rows_returns_immediately(self):
        """Returns empty result without calling other repos when no rows found."""
        self.mock_participants_repo.search_participants_for_admin.return_value = ([], 0)

        result = await self.service.search_participants(
            self.mock_session, ParticipantSearchFilterDto()
        )

        self.assertEqual(result.participant_rows, [])
        self.assertEqual(result.total, 0)
        self.mock_users_repo.get_users_and_emails_by_ids.assert_not_awaited()
        self.mock_rounds_repo.get_all_rounds.assert_not_awaited()
        self.mock_training_repo.get_training_by_user_ids_and_categories.assert_not_awaited()

    async def test_partner_ids_included_in_user_fetch(self):
        """users repo receives both the participant's and the partner's user_id."""
        self.mock_participants_repo.search_participants_for_admin.return_value = (
            [_make_row(user_id=1, pair_id=5, mentor_id=1, mentee_id=2)],
            1,
        )
        self.mock_users_repo.get_users_and_emails_by_ids.return_value = (
            {
                1: MagicMock(
                    user_id=1,
                    first_name="Alice",
                    last_name="Doe",
                    preferred_name="Alice Doe",
                ),
                2: MagicMock(
                    user_id=2,
                    first_name="Bob",
                    last_name="Smith",
                    preferred_name="Bob Smith",
                ),
            },
            {},
        )
        self.mock_rounds_repo.get_all_rounds.return_value = []
        self.mock_training_repo.get_training_by_user_ids_and_categories.return_value = []

        await self.service.search_participants(
            self.mock_session, ParticipantSearchFilterDto()
        )

        _, called_ids = self.mock_users_repo.get_users_and_emails_by_ids.call_args[0]
        self.assertEqual(set(called_ids), {1, 2})

    async def test_matched_user_resolves_partner_correctly(self):
        """matched_user always refers to the other participant in the pair."""
        self.mock_participants_repo.search_participants_for_admin.return_value = (
            [
                _make_row(
                    user_id=1,
                    pair_id=99,
                    mentor_id=1,
                    mentee_id=2,
                    participant_role=ParticipantRole.MENTOR,
                ),
                _make_row(
                    user_id=2,
                    pair_id=99,
                    mentor_id=1,
                    mentee_id=2,
                    participant_role=ParticipantRole.MENTEE,
                ),
            ],
            2,
        )
        self.mock_users_repo.get_users_and_emails_by_ids.return_value = (
            {
                1: MagicMock(
                    user_id=1,
                    first_name="Alice",
                    last_name="Doe",
                    preferred_name="Alice Doe",
                ),
                2: MagicMock(
                    user_id=2,
                    first_name="Bob",
                    last_name="Smith",
                    preferred_name="Bob Smith",
                ),
            },
            {},
        )
        self.mock_rounds_repo.get_all_rounds.return_value = []
        self.mock_training_repo.get_training_by_user_ids_and_categories.return_value = []

        result = await self.service.search_participants(
            self.mock_session, ParticipantSearchFilterDto()
        )

        rows = {r.user_id: r for r in result.participant_rows}
        self.assertEqual(rows[1].matched_user.id, 2)
        self.assertEqual(rows[2].matched_user.id, 1)

    async def test_onboarding_status_requires_done_training(self):
        """mentor/mentee_onboarding_status returns the raw TrainingStatus from the training record."""
        self.mock_participants_repo.search_participants_for_admin.return_value = (
            [
                _make_row(user_id=1, participant_role=ParticipantRole.MENTEE),
                _make_row(user_id=2, participant_role=ParticipantRole.MENTEE),
                _make_row(user_id=3, participant_role=ParticipantRole.MENTOR),
            ],
            3,
        )
        self.mock_users_repo.get_users_and_emails_by_ids.return_value = (
            {
                1: MagicMock(
                    user_id=1,
                    first_name="Alice",
                    last_name="Doe",
                    preferred_name="Alice Doe",
                ),
                2: MagicMock(
                    user_id=2,
                    first_name="Bob",
                    last_name="Smith",
                    preferred_name="Bob Smith",
                ),
                3: MagicMock(
                    user_id=3,
                    first_name="Carol",
                    last_name="Jones",
                    preferred_name="Carol Jones",
                ),
            },
            {},
        )
        self.mock_rounds_repo.get_all_rounds.return_value = []
        self.mock_training_repo.get_training_by_user_ids_and_categories.return_value = [
            MagicMock(
                user_id=1,
                category=TrainingCategory.MENTORSHIP_MENTEE_ONBOARDING,
                status=TrainingStatus.DONE,
            ),
            MagicMock(
                user_id=2,
                category=TrainingCategory.MENTORSHIP_MENTEE_ONBOARDING,
                status=TrainingStatus.IN_PROGRESS,
            ),
            MagicMock(
                user_id=3,
                category=TrainingCategory.MENTORSHIP_MENTOR_ONBOARDING,
                status=TrainingStatus.TO_DO,
            ),
        ]

        result = await self.service.search_participants(
            self.mock_session, ParticipantSearchFilterDto()
        )

        rows = {r.user_id: r for r in result.participant_rows}
        self.assertEqual(rows[1].mentee_onboarding_status, TrainingStatus.DONE)
        self.assertIsNone(rows[1].mentor_onboarding_status)
        self.assertEqual(rows[2].mentee_onboarding_status, TrainingStatus.IN_PROGRESS)
        self.assertIsNone(rows[2].mentor_onboarding_status)
        self.assertEqual(rows[3].mentor_onboarding_status, TrainingStatus.TO_DO)
        self.assertIsNone(rows[3].mentee_onboarding_status)

    async def test_get_meeting_log_pair_not_found(self):
        """Returns None when pair_id does not exist."""
        self.mock_pairs_repo.get_pair_by_id.return_value = None

        result = await self.service.get_meeting_log(self.mock_session, pair_id=999)

        self.assertIsNone(result)

    async def test_get_meeting_log_v2_notes_and_repository_order(self):
        """v2 (any GOOGLE row present): round_version v2, notes derived from
        row fields, meetings kept in the order the repository returned
        them (start_datetime ascending) -- not re-sorted by created_datetime."""
        pair = MagicMock()
        pair.pair_id = 1
        pair.mentor_id = 1
        pair.mentee_id = 2
        m1 = _make_meeting(
            meeting_id="m1",
            start_datetime="2024-01-01T10:00:00+00:00",
            created_datetime="2024-01-01T09:00:00+00:00",
            is_completed=False,
            absent_user_id=1,
            late_user_ids=[2],
        )
        m2 = _make_meeting(
            meeting_id="m2",
            start_datetime="2024-02-01T10:00:00+00:00",
            created_datetime="2024-02-01T09:00:00+00:00",
            is_completed=True,
        )
        self.mock_meeting_repo.get_meetings_by_pair.return_value = [m1, m2]
        self.mock_pairs_repo.get_pair_by_id.return_value = pair

        result = await self.service.get_meeting_log(self.mock_session, pair_id=1)

        self.assertEqual(result.round_version, "v2")
        self.assertEqual([m.meeting_id for m in result.meetings], ["m1", "m2"])
        self.assertIn(MeetingNoteTag.MENTOR_ABSENT, result.meetings[0].note)
        self.assertIn(MeetingNoteTag.MENTEE_LATE, result.meetings[0].note)
        self.assertEqual(result.meetings[1].note, [])
        self.mock_meeting_repo.get_meetings_by_pair.assert_awaited_once_with(
            self.mock_session, 1
        )

    async def test_get_meeting_log_keeps_repository_start_datetime_order(self):
        """Ordering decision, pinned: this path trusts the repository's
        start_datetime order rather than re-sorting by created_datetime --
        a row created later but scheduled earlier still comes first."""
        pair = MagicMock()
        pair.pair_id = 1
        pair.mentor_id = 1
        pair.mentee_id = 2
        early_start_late_created = _make_meeting(
            meeting_id="early-start",
            start_datetime="2024-01-01T10:00:00+00:00",
            created_datetime="2024-03-01T09:00:00+00:00",
        )
        late_start_early_created = _make_meeting(
            meeting_id="late-start",
            start_datetime="2024-02-01T10:00:00+00:00",
            created_datetime="2024-01-01T09:00:00+00:00",
        )
        # This is the order the real repository would return them in
        # (start_datetime ascending); if this method instead re-sorted by
        # created_datetime, the result would come out reversed.
        self.mock_meeting_repo.get_meetings_by_pair.return_value = [
            early_start_late_created,
            late_start_early_created,
        ]
        self.mock_pairs_repo.get_pair_by_id.return_value = pair

        result = await self.service.get_meeting_log(self.mock_session, pair_id=1)

        self.assertEqual(
            [m.meeting_id for m in result.meetings], ["early-start", "late-start"]
        )

    async def test_get_meeting_log_v1_reads_real_is_completed(self):
        """v1 (only MANUAL rows): round_version v1; is_completed is the
        row's real value, not hardcoded True; note is always empty (MANUAL
        rows have no attendance columns)."""
        pair = MagicMock()
        pair.pair_id = 1
        pair.mentor_id = 1
        pair.mentee_id = 2
        manual = _make_meeting(
            meeting_id="v1-m1",
            source=MeetingSource.MANUAL,
            is_completed=False,
        )
        self.mock_meeting_repo.get_meetings_by_pair.return_value = [manual]
        self.mock_pairs_repo.get_pair_by_id.return_value = pair

        result = await self.service.get_meeting_log(self.mock_session, pair_id=1)

        self.assertEqual(result.round_version, "v1")
        self.assertEqual(result.meetings[0].is_completed, False)
        self.assertEqual(result.meetings[0].note, [])

    async def test_get_meeting_log_no_rows_defaults_to_v2(self):
        """A pair with no meeting rows at all defaults to v2 with an empty list."""
        pair = MagicMock()
        pair.pair_id = 1
        pair.mentor_id = 1
        pair.mentee_id = 2
        self.mock_meeting_repo.get_meetings_by_pair.return_value = []
        self.mock_pairs_repo.get_pair_by_id.return_value = pair

        result = await self.service.get_meeting_log(self.mock_session, pair_id=1)

        self.assertEqual(result.round_version, "v2")
        self.assertEqual(result.meetings, [])

    async def test_get_meeting_log_mixed_pair_returns_both_generations(self):
        """A pair holding both MANUAL and GOOGLE rows shows both -- no
        priority branch hides the manual entries -- and round_version is v2
        because a GOOGLE row is present."""
        pair = MagicMock()
        pair.pair_id = 1
        pair.mentor_id = 1
        pair.mentee_id = 2
        manual = _make_meeting(
            meeting_id="manual-1",
            source=MeetingSource.MANUAL,
            start_datetime="2024-01-01T10:00:00+00:00",
            created_datetime="2024-01-01T09:00:00+00:00",
            is_completed=True,
        )
        google = _make_meeting(
            meeting_id="google-1",
            source=MeetingSource.GOOGLE,
            start_datetime="2024-02-01T10:00:00+00:00",
            created_datetime="2024-02-01T09:00:00+00:00",
            is_completed=False,
        )
        # Ordered as the repository would return them: start_datetime asc.
        self.mock_meeting_repo.get_meetings_by_pair.return_value = [manual, google]
        self.mock_pairs_repo.get_pair_by_id.return_value = pair

        result = await self.service.get_meeting_log(self.mock_session, pair_id=1)

        self.assertEqual(result.round_version, "v2")
        self.assertEqual(
            [m.meeting_id for m in result.meetings], ["manual-1", "google-1"]
        )
        self.assertTrue(result.meetings[0].is_completed)
        self.assertFalse(result.meetings[1].is_completed)

    async def test_get_meeting_log_v2_unknown_absent_and_unknown_late(self):
        """Unknown absent/late flags produce UNKNOWN_ABSENT/UNKNOWN_LATE tags."""
        pair = MagicMock()
        pair.pair_id = 1
        pair.mentor_id = 1
        pair.mentee_id = 2
        row = _make_meeting(
            meeting_id="m1", has_unknown_absent=True, has_unknown_late=True
        )
        self.mock_meeting_repo.get_meetings_by_pair.return_value = [row]
        self.mock_pairs_repo.get_pair_by_id.return_value = pair

        result = await self.service.get_meeting_log(self.mock_session, pair_id=1)

        self.assertEqual(
            result.meetings[0].note,
            [MeetingNoteTag.UNKNOWN_ABSENT, MeetingNoteTag.UNKNOWN_LATE],
        )

    async def test_get_meeting_log_v2_insufficient_duration(self):
        """has_insufficient_duration produces the INSUFFICIENT_DURATION tag."""
        pair = MagicMock()
        pair.pair_id = 1
        pair.mentor_id = 1
        pair.mentee_id = 2
        row = _make_meeting(meeting_id="m1", has_insufficient_duration=True)
        self.mock_meeting_repo.get_meetings_by_pair.return_value = [row]
        self.mock_pairs_repo.get_pair_by_id.return_value = pair

        result = await self.service.get_meeting_log(self.mock_session, pair_id=1)

        self.assertEqual(
            result.meetings[0].note, [MeetingNoteTag.INSUFFICIENT_DURATION]
        )

    async def test_get_meeting_log_v2_mentee_absent_and_mentor_late(self):
        """Mentee absence and mentor lateness are tagged from the opposite-role fields."""
        pair = MagicMock()
        pair.pair_id = 1
        pair.mentor_id = 1
        pair.mentee_id = 2
        row = _make_meeting(meeting_id="m1", absent_user_id=2, late_user_ids=[1])
        self.mock_meeting_repo.get_meetings_by_pair.return_value = [row]
        self.mock_pairs_repo.get_pair_by_id.return_value = pair

        result = await self.service.get_meeting_log(self.mock_session, pair_id=1)

        self.assertIn(MeetingNoteTag.MENTEE_ABSENT, result.meetings[0].note)
        self.assertIn(MeetingNoteTag.MENTOR_LATE, result.meetings[0].note)

    def test_build_common_export_columns_sanitizes_formula_injection(self):
        """Free-text fields starting with =, +, -, or @ get a leading single-quote
        so spreadsheet software treats them as literal text, not formulas."""
        row = _make_row(user_id=1)
        users_map = {
            1: MagicMock(
                user_id=1,
                first_name="=cmd|calc",
                last_name="+SUM(A1)",
                preferred_name="-1+1",
            ),
        }
        emails_map = {
            1: [
                MagicMock(is_primary=True, email="@evil.com"),
                MagicMock(is_primary=False, email="+alt@evil.com"),
            ]
        }

        common = self.service._build_common_export_columns(row, users_map, emails_map)

        self.assertEqual(common[1], "'=cmd|calc")  # first_name
        self.assertEqual(common[2], "'+SUM(A1)")  # last_name
        self.assertEqual(common[3], "'-1+1")  # preferred_name
        self.assertEqual(common[4], "'@evil.com")  # primary_email
        self.assertEqual(common[5], "'+alt@evil.com")  # alternative_emails joined

    def test_build_common_export_columns_sanitizes_leading_whitespace(self):
        """Sanitizes formula fields with leading whitespace while preserving the original value."""
        row = _make_row(user_id=1)
        users_map = {
            1: MagicMock(
                user_id=1, first_name=" =cmd|calc", last_name="Doe", preferred_name=None
            )
        }
        emails_map = {1: []}

        common = self.service._build_common_export_columns(row, users_map, emails_map)

        self.assertEqual(common[1], "' =cmd|calc")

    def test_build_common_export_columns_normal_and_none_values_unaffected(self):
        """Values that don't start with a formula-trigger character (including
        None) pass through unchanged."""
        row = _make_row(user_id=1)
        users_map = {
            1: MagicMock(
                user_id=1, first_name="Alice", last_name="Doe", preferred_name=None
            )
        }
        emails_map = {1: [MagicMock(is_primary=True, email="alice@example.com")]}

        common = self.service._build_common_export_columns(row, users_map, emails_map)

        self.assertEqual(common, [1, "Alice", "Doe", None, "alice@example.com", ""])

    def test_build_participant_export_columns_approval_status_raw_enum(self):
        """Approval Status column is the raw enum value, not a display string."""
        row = _make_row(user_id=1, approval_status=ApprovalStatus.UN_MATCHED)

        participant = self.service._build_participant_export_columns(
            row, users_map={}, trainings_map={}, rounds_map={}
        )

        self.assertEqual(participant[2], "un_matched")

    def test_build_participant_export_columns_no_pair_leaves_matched_user_blank(self):
        """A row with no pair_id has blank Matched User columns."""
        row = _make_row()

        participant = self.service._build_participant_export_columns(
            row, users_map={}, trainings_map={}, rounds_map={}
        )

        self.assertEqual(participant, ["", "", "", "", "", ""])

    def test_build_participant_export_columns_matched_name_formula_injection(self):
        """The matched user's name is sanitized the same as any other free-text field."""
        row = _make_row(
            user_id=1,
            pair_id=10,
            mentor_id=1,
            mentee_id=2,
            participant_role=ParticipantRole.MENTOR,
        )
        users_map = {
            2: MagicMock(
                user_id=2,
                first_name="=Mentee",
                last_name="Smith",
                preferred_name="@pref",
            ),
        }

        participant = self.service._build_participant_export_columns(
            row, users_map, trainings_map={}, rounds_map={}
        )

        # partner's preferred_name ("@pref") wins per partner_display_name and
        # gets sanitized after combining.
        self.assertEqual(participant[5], "'@pref")  # matched_user_name

    def test_build_participant_export_columns_matched_name_fallback(self):
        """Falls back to first last name and sanitizes the combined value."""
        row = _make_row(
            user_id=1,
            pair_id=10,
            mentor_id=1,
            mentee_id=2,
            participant_role=ParticipantRole.MENTOR,
        )
        users_map = {
            2: MagicMock(
                user_id=2, first_name="=Mentee", last_name="Smith", preferred_name=None
            ),
        }

        participant = self.service._build_participant_export_columns(
            row, users_map, trainings_map={}, rounds_map={}
        )

        self.assertEqual(participant[4], 2)  # matched_user_id
        self.assertEqual(
            participant[5], "'=Mentee Smith"
        )  # matched_user_name, sanitized

    def test_build_participant_export_columns_onboarding_status_mentee_role(self):
        """A mentee-role row's Onboarding Status is the mentee onboarding status,
        not the mentor one, even if both are set."""
        row = _make_row(user_id=1, participant_role=ParticipantRole.MENTEE)
        trainings_map = {
            1: {
                TrainingCategory.MENTORSHIP_MENTOR_ONBOARDING: TrainingStatus.DONE,
                TrainingCategory.MENTORSHIP_MENTEE_ONBOARDING: TrainingStatus.TO_DO,
            }
        }

        participant = self.service._build_participant_export_columns(
            row, users_map={}, trainings_map=trainings_map, rounds_map={}
        )

        self.assertEqual(participant[3], "to_do")

    def test_build_participant_export_columns_onboarding_status_mentor_role(self):
        """A mentor-role row's Onboarding Status is the mentor onboarding status."""
        row = _make_row(user_id=1, participant_role=ParticipantRole.MENTOR)
        trainings_map = {
            1: {
                TrainingCategory.MENTORSHIP_MENTOR_ONBOARDING: TrainingStatus.DONE,
                TrainingCategory.MENTORSHIP_MENTEE_ONBOARDING: TrainingStatus.TO_DO,
            }
        }

        participant = self.service._build_participant_export_columns(
            row, users_map={}, trainings_map=trainings_map, rounds_map={}
        )

        self.assertEqual(participant[3], "done")

    def test_build_non_participant_export_columns_returns_both_statuses(self):
        """A non-participant row exposes both mentor and mentee onboarding
        status, since it has no participant_role to disambiguate by."""
        row = _make_row(user_id=1)
        trainings_map = {
            1: {
                TrainingCategory.MENTORSHIP_MENTOR_ONBOARDING: TrainingStatus.DONE,
                TrainingCategory.MENTORSHIP_MENTEE_ONBOARDING: TrainingStatus.TO_DO,
            }
        }

        non_participant = self.service._build_non_participant_export_columns(
            row, trainings_map
        )

        self.assertEqual(non_participant, ["done", "to_do"])

    def test_build_non_participant_export_columns_blank_when_no_training(self):
        """A user with no training record has blank onboarding status columns."""
        row = _make_row()

        non_participant = self.service._build_non_participant_export_columns(
            row, trainings_map={}
        )

        self.assertEqual(non_participant, ["", ""])

    def test_extract_meetings_for_row_no_meetings_returns_empty_list(self):
        """A row whose pair has no meeting rows (or no pair at all) yields
        no meetings."""
        row = _make_row(user_id=1)
        self.assertEqual(self.service._extract_meetings_for_row(row, []), [])

    def test_extract_meetings_for_row_resolves_notes_from_rows(self):
        """Resolves notes using the row-based note logic
        (_resolve_meeting_notes_from_row), not the old dict-based one, and
        reads is_completed from the row rather than hardcoding it."""
        row = _make_row(user_id=1, mentor_id=10, mentee_id=20)
        meeting = _make_meeting(
            meeting_id="m1",
            start_datetime="2024-07-15T22:00:00+00:00",
            end_datetime="2024-07-15T23:00:00+00:00",
            created_datetime="2024-07-01T00:00:00+00:00",
            is_completed=False,
            absent_user_id=10,
        )

        meetings = self.service._extract_meetings_for_row(row, [meeting])

        self.assertEqual(len(meetings), 1)
        self.assertEqual(meetings[0].meeting_id, "m1")
        self.assertEqual(meetings[0].note, [MeetingNoteTag.MENTOR_ABSENT])
        self.assertFalse(meetings[0].is_completed)

    def test_extract_meetings_for_row_combines_manual_and_google_without_hiding_either(
        self,
    ):
        """A pair holding both MANUAL and GOOGLE rows shows both -- no
        priority branch hides one generation in favor of the other."""
        row = _make_row(user_id=1, mentor_id=10, mentee_id=20)
        manual = _make_meeting(
            meeting_id="v1-1",
            source=MeetingSource.MANUAL,
            start_datetime="2024-01-01T10:00:00+00:00",
            is_completed=False,
        )
        google = _make_meeting(
            meeting_id="g1",
            source=MeetingSource.GOOGLE,
            start_datetime="2024-02-01T10:00:00+00:00",
            is_completed=True,
        )

        meetings = self.service._extract_meetings_for_row(row, [manual, google])

        self.assertEqual([m.meeting_id for m in meetings], ["v1-1", "g1"])
        self.assertFalse(meetings[0].is_completed)  # real value, not forced True
        self.assertTrue(meetings[1].is_completed)

    def test_extract_meetings_for_row_preserves_repository_order_not_created_datetime(
        self,
    ):
        """Ordering unification, pinned: trusts whatever order `meetings` is
        handed in (the repository's start_datetime-then-created_datetime-
        then-meeting_id order) instead of re-sorting by created_datetime the
        way the JSONB-era version did. A row created later but scheduled
        earlier still comes first, matching get_meeting_log's ordering."""
        row = _make_row(user_id=1, mentor_id=10, mentee_id=20)
        later_start_earlier_created = _make_meeting(
            meeting_id="m-later-start",
            start_datetime="2024-02-01T10:00:00+00:00",
            created_datetime="2024-01-01T00:00:00+00:00",
        )
        earlier_start_later_created = _make_meeting(
            meeting_id="m-earlier-start",
            start_datetime="2024-01-01T10:00:00+00:00",
            created_datetime="2024-02-01T00:00:00+00:00",
        )
        # This is the order the real repository would return them in
        # (start_datetime ascending); a created_datetime sort would reverse it.
        meetings = [earlier_start_later_created, later_start_earlier_created]

        result = self.service._extract_meetings_for_row(row, meetings)

        self.assertEqual(
            [m.meeting_id for m in result], ["m-earlier-start", "m-later-start"]
        )

    async def test_missing_participation_status_raises_value_error(self):
        """Requires participation_status — an unfiltered "both" export isn't supported."""
        with self.assertRaises(ValueError):
            await self.service.stream_export_csv(
                ParticipantSearchFilterDto(), expand_meetings=False
            ).__anext__()

    async def test_summary_mode_emits_header_and_one_row_per_person(self):
        """Summary mode: header + one CSV row per participant row, no meeting query."""
        row = _make_row(user_id=1, round_id=None, pair_id=None)
        self.mock_participants_repo.iter_search_participants_for_admin.side_effect = [
            [row],
            [],
        ]
        self.mock_users_repo.get_users_and_emails_by_ids.return_value = (
            {
                1: MagicMock(
                    user_id=1, first_name="Alice", last_name="Doe", preferred_name=None
                )
            },
            {1: []},
        )

        csv_text = await _collect_csv(
            self.service.stream_export_csv(
                ParticipantSearchFilterDto(participation_status="participant"),
                expand_meetings=False,
            )
        )

        lines = csv_text.strip("\r\n").split("\r\n")
        self.assertEqual(
            lines[0].split(","),
            [
                "User ID",
                "First Name",
                "Last Name",
                "Preferred Name",
                "Primary Email",
                "Alternative Emails",
                "Round",
                "Participant Role",
                "Approval Status",
                "Onboarding Status",
                "Matched User ID",
                "Matched User Name",
                "Completed Meetings",
                "Required Meetings",
            ],
        )
        self.assertEqual(len(lines), 2)
        self.assertTrue(lines[1].startswith("1,Alice,Doe,,,,"))

        # Summary mode never needs meeting rows at all.
        self.mock_meeting_repo.get_meetings_by_pairs.assert_not_awaited()

    async def test_summary_mode_first_chunk_starts_with_utf8_bom(self):
        """The raw byte stream is prefixed with a UTF-8 BOM so Excel on
        Windows doesn't mojibake non-ASCII names."""
        self.mock_participants_repo.iter_search_participants_for_admin.side_effect = [
            []
        ]

        chunks = [
            chunk
            async for chunk in self.service.stream_export_csv(
                ParticipantSearchFilterDto(participation_status="participant"),
                expand_meetings=False,
            )
        ]

        self.assertTrue(chunks[0].startswith(b"\xef\xbb\xbf"))

    async def test_detailed_mode_emits_one_row_per_meeting_and_pt_formats_time(self):
        """Detailed mode: one CSV row per meeting, using the PT formatter."""
        row = _make_row(user_id=1, pair_id=1, mentor_id=1, mentee_id=2)
        meeting = _make_meeting(
            meeting_id="m1",
            pair_id=1,
            start_datetime="2024-07-15T22:00:00+00:00",
            end_datetime="2024-07-15T23:00:00+00:00",
            created_datetime="2024-07-01T00:00:00+00:00",
            is_completed=True,
        )
        self.mock_meeting_repo.get_meetings_by_pairs.return_value = {1: [meeting]}
        self.mock_participants_repo.iter_search_participants_for_admin.side_effect = [
            [row],
            [],
        ]
        self.mock_users_repo.get_users_and_emails_by_ids.return_value = (
            {
                1: MagicMock(
                    user_id=1, first_name="Alice", last_name="Doe", preferred_name=None
                )
            },
            {1: []},
        )

        csv_text = await _collect_csv(
            self.service.stream_export_csv(
                ParticipantSearchFilterDto(participation_status="participant"),
                expand_meetings=True,
            )
        )

        lines = csv_text.strip("\r\n").split("\r\n")
        self.assertEqual(
            lines[0].split(",")[-4:],
            [
                "Complete Status",
                "Start Datetime (PT)",
                "End Datetime (PT)",
                "Note",
            ],
        )
        self.assertIn("PT(2024-07-15T22:00:00+00:00)", lines[1])
        self.assertIn("Completed", lines[1])

        # Batched exactly once per page, with this page's pair_ids.
        self.mock_meeting_repo.get_meetings_by_pairs.assert_awaited_once_with(
            session=self.mock_session, pair_ids=[1]
        )

    async def test_detailed_mode_batches_meetings_once_for_a_multi_row_page(self):
        """Acceptance criterion: a page with several participant rows fetches
        meetings with exactly one get_meetings_by_pairs call, not one per row."""
        rows = [
            _make_row(user_id=uid, pair_id=pid, mentor_id=uid, mentee_id=uid + 100)
            for uid, pid in [(1, 10), (2, 20), (3, 30)]
        ]
        meetings_by_pair = {
            10: [_make_meeting(meeting_id="m10", pair_id=10)],
            20: [_make_meeting(meeting_id="m20", pair_id=20)],
            # pair 30 deliberately absent: get_meetings_by_pairs omits pairs
            # with no rows rather than mapping them to an empty list.
        }
        self.mock_meeting_repo.get_meetings_by_pairs.return_value = meetings_by_pair
        self.mock_participants_repo.iter_search_participants_for_admin.side_effect = [
            rows,
            [],
        ]
        self.mock_users_repo.get_users_and_emails_by_ids.return_value = (
            {
                uid: MagicMock(
                    user_id=uid, first_name=f"User{uid}", last_name="X", preferred_name=None
                )
                for uid in (1, 2, 3)
            },
            {1: [], 2: [], 3: []},
        )

        csv_text = await _collect_csv(
            self.service.stream_export_csv(
                ParticipantSearchFilterDto(participation_status="participant"),
                expand_meetings=True,
            )
        )

        # Exactly one batched call for the whole page, regardless of row count.
        self.mock_meeting_repo.get_meetings_by_pairs.assert_awaited_once_with(
            session=self.mock_session, pair_ids=[10, 20, 30]
        )
        lines = csv_text.strip("\r\n").split("\r\n")
        self.assertEqual(len(lines), 4)  # header + 3 rows (1 meeting row each)
        # Row for pair 30 (absent from the batch dict) gets blank meeting columns
        # via .get(pair_id, []), not a KeyError.
        row_for_pair_30 = next(line for line in lines[1:] if line.startswith("3,"))
        self.assertEqual(row_for_pair_30.split(",")[-4:], ["", "", "", ""])

    async def test_detailed_mode_skips_row_on_processing_failure_and_logs(self):
        """Logs and skips a row whose meeting data fails to process."""
        bad_row = _make_row(
            user_id=1,
            round_id=10,
            pair_id=100,
            mentor_id=1,
            mentee_id=2,
        )
        good_row = _make_row(
            user_id=2,
            round_id=20,
            pair_id=200,
            mentor_id=2,
            mentee_id=3,
        )
        bad_meeting = _make_meeting(
            meeting_id="m-bad",
            pair_id=100,
            start_datetime=None,  # never happens for real MANUAL/GOOGLE rows
            end_datetime="2024-07-15T23:00:00+00:00",
            created_datetime="2024-07-01T00:00:00+00:00",
            is_completed=True,
        )
        good_meeting = _make_meeting(
            meeting_id="m-good",
            pair_id=200,
            start_datetime="2024-07-15T22:00:00+00:00",
            end_datetime="2024-07-15T23:00:00+00:00",
            created_datetime="2024-07-01T00:00:00+00:00",
            is_completed=True,
        )
        self.mock_meeting_repo.get_meetings_by_pairs.return_value = {
            100: [bad_meeting],
            200: [good_meeting],
        }
        self.mock_participants_repo.iter_search_participants_for_admin.side_effect = [
            [bad_row, good_row],
            [],
        ]
        self.mock_users_repo.get_users_and_emails_by_ids.return_value = (
            {
                1: MagicMock(
                    user_id=1, first_name="Alice", last_name="Doe", preferred_name=None
                ),
                2: MagicMock(
                    user_id=2, first_name="Bob", last_name="Lee", preferred_name=None
                ),
            },
            {1: [], 2: []},
        )

        csv_text = await _collect_csv(
            self.service.stream_export_csv(
                ParticipantSearchFilterDto(participation_status="participant"),
                expand_meetings=True,
            )
        )

        lines = csv_text.strip("\r\n").split("\r\n")
        self.assertEqual(len(lines), 2)  # header + only the good row's meeting
        self.assertTrue(lines[1].startswith("2,Bob,Lee"))

        self.mock_logger.exception.assert_called_once()
        _, user_id_arg, pair_id_arg, round_id_arg = (
            self.mock_logger.exception.call_args.args
        )
        self.assertEqual((user_id_arg, pair_id_arg, round_id_arg), (1, 100, 10))

    async def test_detailed_mode_skips_whole_row_not_partial_meetings(self):
        """Skips the whole row when one meeting fails, avoiding partial meeting output."""

        def _format_or_raise(iso, fmt="%Y-%m-%d %H:%M %Z"):
            if iso == "2024-07-16T22:00:00+00:00":
                raise ValueError(f"Invalid ISO datetime string: {iso}")
            return f"PT({iso})"

        self.mock_date_time_util.format_iso_utc_to_pt.side_effect = _format_or_raise

        row = _make_row(user_id=1, round_id=10, pair_id=100, mentor_id=1, mentee_id=2)
        good_meeting = _make_meeting(
            meeting_id="m-good",
            pair_id=100,
            start_datetime="2024-07-15T22:00:00+00:00",
            end_datetime="2024-07-15T23:00:00+00:00",
            created_datetime="2024-07-01T00:00:00+00:00",
            is_completed=True,
        )
        bad_meeting = _make_meeting(
            meeting_id="m-bad",
            pair_id=100,
            start_datetime="2024-07-16T22:00:00+00:00",
            end_datetime="2024-07-16T23:00:00+00:00",
            created_datetime="2024-07-02T00:00:00+00:00",
            is_completed=True,
        )
        self.mock_meeting_repo.get_meetings_by_pairs.return_value = {
            100: [good_meeting, bad_meeting]
        }
        self.mock_participants_repo.iter_search_participants_for_admin.side_effect = [
            [row],
            [],
        ]
        self.mock_users_repo.get_users_and_emails_by_ids.return_value = (
            {
                1: MagicMock(
                    user_id=1, first_name="Alice", last_name="Doe", preferred_name=None
                )
            },
            {1: []},
        )

        csv_text = await _collect_csv(
            self.service.stream_export_csv(
                ParticipantSearchFilterDto(participation_status="participant"),
                expand_meetings=True,
            )
        )

        lines = csv_text.strip("\r\n").split("\r\n")
        self.assertEqual(len(lines), 1)  # header only — neither meeting written
        self.mock_logger.exception.assert_called_once()

    async def test_detailed_mode_keeps_row_with_no_meetings_blank(self):
        """Keeps a row with no meetings instead of dropping it, with blank meeting columns."""
        row = _make_row(user_id=1, pair_id=5)
        self.mock_meeting_repo.get_meetings_by_pairs.return_value = {}
        self.mock_participants_repo.iter_search_participants_for_admin.side_effect = [
            [row],
            [],
        ]
        self.mock_users_repo.get_users_and_emails_by_ids.return_value = (
            {
                1: MagicMock(
                    user_id=1, first_name="Alice", last_name="Doe", preferred_name=None
                )
            },
            {1: []},
        )

        csv_text = await _collect_csv(
            self.service.stream_export_csv(
                ParticipantSearchFilterDto(participation_status="participant"),
                expand_meetings=True,
            )
        )

        lines = csv_text.strip("\r\n").split("\r\n")
        self.assertEqual(len(lines), 2)  # header + one blank-meeting row
        self.assertEqual(lines[1].split(",")[-4:], ["", "", "", ""])

    async def test_non_participant_export_ignores_expand_meetings(self):
        """Ignores expand_meetings for non-participant exports."""
        row = _make_row(user_id=1, participant_role=None, pair_id=None)
        self.mock_participants_repo.iter_search_participants_for_admin.side_effect = [
            [row],
            [],
        ]
        self.mock_users_repo.get_users_and_emails_by_ids.return_value = (
            {
                1: MagicMock(
                    user_id=1, first_name="Alice", last_name="Doe", preferred_name=None
                )
            },
            {1: []},
        )
        self.mock_training_repo.get_training_by_user_ids_and_categories.return_value = [
            MagicMock(
                user_id=1,
                category=TrainingCategory.MENTORSHIP_MENTOR_ONBOARDING,
                status=TrainingStatus.DONE,
            )
        ]

        csv_text = await _collect_csv(
            self.service.stream_export_csv(
                ParticipantSearchFilterDto(participation_status="non_participant"),
                expand_meetings=True,
            )
        )

        lines = csv_text.strip("\r\n").split("\r\n")
        self.assertEqual(
            lines[0].split(","),
            [
                "User ID",
                "First Name",
                "Last Name",
                "Preferred Name",
                "Primary Email",
                "Alternative Emails",
                "Mentor Onboarding Status",
                "Mentee Onboarding Status",
            ],
        )
        self.assertEqual(lines[1], "1,Alice,Doe,,,,done,")

        # A non-participant export never needs meeting rows, even with
        # expand_meetings=True, since non-participants have no pair/meetings.
        self.mock_meeting_repo.get_meetings_by_pairs.assert_not_awaited()

    async def test_stops_paginating_on_empty_page(self):
        """The batch loop stops as soon as a page comes back empty."""
        row = _make_row(user_id=1)
        self.mock_participants_repo.iter_search_participants_for_admin.side_effect = [
            [row],
            [],
        ]
        self.mock_users_repo.get_users_and_emails_by_ids.return_value = (
            {
                1: MagicMock(
                    user_id=1, first_name="Alice", last_name="Doe", preferred_name=None
                )
            },
            {1: []},
        )

        await _collect_csv(
            self.service.stream_export_csv(
                ParticipantSearchFilterDto(participation_status="participant"),
                expand_meetings=False,
            )
        )

        self.assertEqual(
            self.mock_participants_repo.iter_search_participants_for_admin.await_count,
            2,
        )

    async def test_multiple_batches_paginate_with_incrementing_offset_and_bom_once(
        self,
    ):
        """Paginates across batches with incrementing offsets and a single BOM."""
        row1 = _make_row(user_id=1)
        row2 = _make_row(user_id=2)
        self.mock_participants_repo.iter_search_participants_for_admin.side_effect = [
            [row1],
            [row2],
            [],
        ]
        self.mock_users_repo.get_users_and_emails_by_ids.return_value = (
            {
                1: MagicMock(
                    user_id=1, first_name="Alice", last_name="Doe", preferred_name=None
                ),
                2: MagicMock(
                    user_id=2, first_name="Bob", last_name="Lee", preferred_name=None
                ),
            },
            {1: [], 2: []},
        )

        chunks = [
            chunk
            async for chunk in self.service.stream_export_csv(
                ParticipantSearchFilterDto(participation_status="participant"),
                expand_meetings=False,
            )
        ]

        self.assertTrue(chunks[0].startswith(b"\xef\xbb\xbf"))
        for later_chunk in chunks[1:]:
            self.assertFalse(later_chunk.startswith(b"\xef\xbb\xbf"))

        call_offsets = [
            call.kwargs["offset"]
            for call in self.mock_participants_repo.iter_search_participants_for_admin.call_args_list
        ]
        self.assertEqual(call_offsets, [0, 500, 1000])

        csv_text = b"".join(chunks).decode("utf-8-sig")
        lines = csv_text.strip("\r\n").split("\r\n")
        self.assertEqual(len(lines), 3)  # header + one row per batch
        self.assertTrue(lines[1].startswith("1,Alice,Doe"))
        self.assertTrue(lines[2].startswith("2,Bob,Lee"))

    def test_validate_note_tags_allows_valid_combinations(self):
        """Test that valid note tag combinations do not raise."""
        self.service._validate_note_tags(None)
        self.service._validate_note_tags([])
        self.service._validate_note_tags([
            MeetingNoteTag.MENTOR_LATE,
            MeetingNoteTag.MENTEE_LATE,
        ])

    def test_validate_note_tags_rejects_two_absent_tags(self):
        """Two absent tags in the same note list is invalid."""
        with self.assertRaises(ValueError):
            self.service._validate_note_tags([
                MeetingNoteTag.MENTOR_ABSENT,
                MeetingNoteTag.MENTEE_ABSENT,
            ])

    def test_validate_note_tags_rejects_unknown_late_with_specific_late(self):
        """Unknown and specific late tags are mutually exclusive."""
        with self.assertRaises(ValueError):
            self.service._validate_note_tags([
                MeetingNoteTag.UNKNOWN_LATE,
                MeetingNoteTag.MENTOR_LATE,
            ])

    def test_apply_note_tags_maps_every_tag_and_clears(self):
        """Every MeetingNoteTag maps correctly and clears unrelated attributes
        on the meeting row."""
        mentor_id, mentee_id = 1, 2
        cleared = {
            "has_insufficient_duration": False,
            "has_unknown_absent": False,
            "absent_user_id": None,
            "has_unknown_late": False,
            "late_user_ids": [],
        }
        cases = [
            (
                [MeetingNoteTag.INSUFFICIENT_DURATION],
                {**cleared, "has_insufficient_duration": True},
            ),
            ([MeetingNoteTag.UNKNOWN_ABSENT], {**cleared, "has_unknown_absent": True}),
            ([MeetingNoteTag.MENTOR_ABSENT], {**cleared, "absent_user_id": mentor_id}),
            ([MeetingNoteTag.MENTEE_ABSENT], {**cleared, "absent_user_id": mentee_id}),
            ([MeetingNoteTag.UNKNOWN_LATE], {**cleared, "has_unknown_late": True}),
            (
                [MeetingNoteTag.MENTOR_LATE, MeetingNoteTag.MENTEE_LATE],
                {**cleared, "late_user_ids": [mentor_id, mentee_id]},
            ),
            ([], cleared),
        ]
        for note, expected in cases:
            meeting = _make_meeting(
                has_insufficient_duration=True,
                has_unknown_absent=True,
                absent_user_id=999,
                has_unknown_late=True,
                late_user_ids=[999],
            )
            self.service._apply_note_tags(meeting, note, mentor_id, mentee_id)
            for field, value in expected.items():
                self.assertEqual(
                    getattr(meeting, field), value, f"note={note}, field={field}"
                )

    def test_apply_note_tags_reassigns_late_user_ids_not_appends(self):
        """late_user_ids must be a brand-new list object -- ARRAY(Integer) is
        not Mutable-wrapped, so an in-place append would not be detected by
        the unit of work and would silently fail to persist."""
        meeting = _make_meeting(late_user_ids=[999])
        original_list = meeting.late_user_ids

        self.service._apply_note_tags(
            meeting, [MeetingNoteTag.MENTOR_LATE], mentor_id=1, mentee_id=2
        )

        self.assertIsNot(meeting.late_user_ids, original_list)
        self.assertEqual(meeting.late_user_ids, [1])

    async def test_apply_batch_rejects_malformed_requests_before_touching_db(self):
        """Empty request, overlapping IDs, and invalid note combos are rejected before touching the DB."""
        cases = [
            V2MeetingBatchUpdateDto(),
            V2MeetingBatchUpdateDto(
                updates=[V2MeetingUpdateItemDto(meeting_id="m1", is_completed=True)],
                deletes=["m1"],
            ),
            V2MeetingBatchUpdateDto(
                updates=[
                    V2MeetingUpdateItemDto(
                        meeting_id="m1",
                        note=[
                            MeetingNoteTag.MENTOR_ABSENT,
                            MeetingNoteTag.MENTEE_ABSENT,
                        ],
                    )
                ]
            ),
        ]
        for batch in cases:
            with self.assertRaises(ValueError):
                await self.service.apply_v2_meeting_batch(self.mock_session, 1, batch)
        self.mock_pairs_repo.get_pair_by_id.assert_not_awaited()
        self.mock_meeting_repo.get_meetings_by_pair.assert_not_awaited()

    async def test_apply_batch_rejects_manual_only_row(self):
        """A pair with only a manual row still rejects editing it (baseline
        per-row rejection, not just the mixed-pair case below)."""
        pair = _make_pair()
        self.mock_pairs_repo.get_pair_by_id.return_value = pair
        self.mock_meeting_repo.get_meetings_by_pair.return_value = [
            _make_meeting(meeting_id="manual-1", source=MeetingSource.MANUAL)
        ]

        with self.assertRaises(ConflictError):
            await self.service.apply_v2_meeting_batch(
                self.mock_session, 1, V2MeetingBatchUpdateDto(deletes=["manual-1"])
            )
        self.mock_meeting_repo.delete_meetings.assert_not_awaited()

    async def test_apply_batch_manual_row_conflicts_even_when_pair_also_has_google_rows(
        self,
    ):
        """Per-row check, the headline fix: a manual row is rejected even
        though the same pair also holds an editable google row -- the exact
        case that made a mixed pair permanently uneditable under the old
        per-pair check."""
        pair = _make_pair()
        manual = _make_meeting(meeting_id="manual-1", source=MeetingSource.MANUAL)
        google = _make_meeting(meeting_id="google-1", source=MeetingSource.GOOGLE)
        self.mock_pairs_repo.get_pair_by_id.return_value = pair
        self.mock_meeting_repo.get_meetings_by_pair.return_value = [manual, google]

        with self.assertRaises(ConflictError):
            await self.service.apply_v2_meeting_batch(
                self.mock_session,
                1,
                V2MeetingBatchUpdateDto(deletes=["manual-1"]),
            )
        self.mock_meeting_repo.delete_meetings.assert_not_awaited()

    async def test_apply_batch_google_row_succeeds_on_same_mixed_pair(self):
        """The same mixed pair's google row can still be edited -- the other
        half of the headline fix."""
        pair = _make_pair()
        manual = _make_meeting(meeting_id="manual-1", source=MeetingSource.MANUAL)
        google = _make_meeting(
            meeting_id="google-1", source=MeetingSource.GOOGLE, is_completed=False
        )
        self.mock_pairs_repo.get_pair_by_id.return_value = pair
        self.mock_meeting_repo.get_meetings_by_pair.side_effect = [
            [manual, google],  # fetched inside apply_v2_meeting_batch
            [manual, google],  # re-fetched by the trailing _build_meeting_log_dto
        ]
        self.mock_meeting_repo.recalculate_completed_count.return_value = 1

        result = await self.service.apply_v2_meeting_batch(
            self.mock_session,
            1,
            V2MeetingBatchUpdateDto(
                updates=[
                    V2MeetingUpdateItemDto(meeting_id="google-1", is_completed=True)
                ]
            ),
        )

        self.assertTrue(google.is_completed)
        self.assertEqual(pair.completed_count, 1)
        self.mock_session.commit.assert_awaited_once()
        self.assertEqual(result.round_version, "v2")

    async def test_apply_batch_rejects_unknown_meeting_id(self):
        """A meeting_id not present among this pair's rows is a client error."""
        pair = _make_pair()
        self.mock_pairs_repo.get_pair_by_id.return_value = pair
        self.mock_meeting_repo.get_meetings_by_pair.return_value = [
            _make_meeting(meeting_id="m1", is_completed=False)
        ]

        with self.assertRaises(ValueError):
            await self.service.apply_v2_meeting_batch(
                self.mock_session, 1, V2MeetingBatchUpdateDto(deletes=["missing"])
            )

    async def test_apply_batch_mixed_update_and_delete(self):
        """Mixed updates, deletes, and no-op updates correctly recalculate
        completed_count; nothing in this method writes pair.meeting_log."""
        pair = _make_pair(mentor_id=10, mentee_id=20)
        original_meeting_log = copy.deepcopy(pair.meeting_log)
        m1 = _make_meeting(meeting_id="m1", is_completed=False)
        m2 = _make_meeting(meeting_id="m2", is_completed=True)
        m3 = _make_meeting(meeting_id="m3", is_completed=True, has_unknown_absent=True)
        self.mock_pairs_repo.get_pair_by_id.return_value = pair
        self.mock_meeting_repo.get_meetings_by_pair.side_effect = [
            [m1, m2, m3],  # fetched inside apply_v2_meeting_batch
            [m1, m3],  # re-fetched by the trailing _build_meeting_log_dto (m2 deleted)
        ]
        self.mock_meeting_repo.recalculate_completed_count.return_value = 2

        result = await self.service.apply_v2_meeting_batch(
            self.mock_session,
            1,
            V2MeetingBatchUpdateDto(
                updates=[
                    V2MeetingUpdateItemDto(
                        meeting_id="m1",
                        is_completed=True,
                        note=[MeetingNoteTag.MENTOR_ABSENT],
                    ),
                    V2MeetingUpdateItemDto(meeting_id="m3"),  # null fields: no-op
                ],
                deletes=["m2"],
            ),
        )

        self.mock_meeting_repo.delete_meetings.assert_awaited_once_with(
            self.mock_session, 1, ["m2"]
        )
        self.assertTrue(m1.is_completed)
        self.assertEqual(m1.absent_user_id, pair.mentor_id)
        self.assertTrue(m3.is_completed)  # unchanged: both update fields were null
        self.assertIsNone(m3.absent_user_id)  # untouched by the no-op update
        self.assertEqual(pair.completed_count, 2)
        self.mock_session.commit.assert_awaited_once()
        self.assertEqual(result.round_version, "v2")
        # Pin: apply_v2_meeting_batch must never read or write pair.meeting_log.
        self.assertEqual(pair.meeting_log, original_meeting_log)

    async def test_apply_batch_uses_row_lock_and_returns_meeting_log(self):
        """Loads the pair with with_lock=True and returns the pair's current
        meeting log built from rows after the edit."""
        pair = _make_pair()
        m1 = _make_meeting(meeting_id="m1", is_completed=True)
        self.mock_pairs_repo.get_pair_by_id.return_value = pair
        self.mock_meeting_repo.get_meetings_by_pair.side_effect = [[m1], []]
        self.mock_meeting_repo.recalculate_completed_count.return_value = 0

        result = await self.service.apply_v2_meeting_batch(
            self.mock_session, 1, V2MeetingBatchUpdateDto(deletes=["m1"])
        )

        self.mock_pairs_repo.get_pair_by_id.assert_awaited_once_with(
            self.mock_session, 1, with_lock=True
        )
        self.mock_meeting_repo.delete_meetings.assert_awaited_once_with(
            self.mock_session, 1, ["m1"]
        )
        self.assertEqual(result.round_version, "v2")
        self.assertEqual(result.meetings, [])


if __name__ == "__main__":
    unittest.main()
