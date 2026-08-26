import unittest
import uuid
from datetime import datetime, timezone

from backend.dto.preference_dto import (
    SpecificIndustryDto,
    SkillsetsDto,
    ProfileSurveyDto,
)
from backend.dto.registration_dto import GlobalPreferencesDto, RoundPreferencesDto
from backend.dto.rounds_dto import RoundsDto, TimelineDto
from backend.dto.meeting_dto import MeetingDto
from backend.dto.admin_meeting_log_dto import AdminMeetingDto
from backend.entity.users_entity import UsersEntity
from backend.entity.preference_entity import PreferenceEntity
from backend.entity.mentorship_pairs_entity import MentorshipPairsEntity
from backend.entity.mentorship_meeting_entity import MentorshipMeetingEntity
from backend.entity.mentorship_round_participants_entity import (
    MentorshipRoundParticipantsEntity,
)
from backend.entity.mentorship_round_entity import MentorshipRoundEntity
from backend.mentorship.mentorship_mapper import MentorshipMapper
from backend.common.mentorship_enums import (
    CommunicationMethod,
    ParticipantRole,
    PairStatus,
    MenteeActionStatus,
    MentorActionStatus,
    MeetingNoteTag,
    MeetingSource,
)


class TestMentorshipMapper(unittest.TestCase):
    def setUp(self):
        """Prepare test data."""
        self.now = datetime.now(timezone.utc)
        self.mapper = MentorshipMapper()

        self.test_dates = {
            "promotion_start_at": "2025-07-02T06:59:59Z",
            "mentor_application_deadline_at": "2025-07-16T06:59:59Z",
            "mentee_application_deadline_at": "2025-07-14T06:59:59Z",
            "training_notification_at": "2025-07-18T06:59:59Z",
            "training_deadline_at": "2025-07-25T06:59:59Z",
            "review_start_at": "2025-07-17T06:59:59Z",
            "acceptance_notification_at": "2025-07-31T06:59:59Z",
            "matching_completed_at": "2025-08-06T06:59:59Z",
            "match_notification_at": "2025-08-07T06:59:59Z",
            "first_meeting_deadline_at": "2025-08-21T06:59:59Z",
            "meeting_log_reminder_at": "2025-09-01T06:59:59Z",
            "meetings_completion_deadline_at": "2025-11-21T07:59:59Z",
            "feedback_start_at": "2025-11-22T07:59:59Z",
            "feedback_deadline_at": "2025-11-23T07:59:59Z",
        }

        self.mentorship_round_entities = [
            MentorshipRoundEntity(
                round_id=1,
                name="Spring-2025",
                description=self.test_dates,
                required_meetings=4,
            ),
            MentorshipRoundEntity(
                round_id=2, name="Summer-2025", description={}, required_meetings=5
            ),
            MentorshipRoundEntity(
                round_id=3, name="Spring-2026", description=None, required_meetings=5
            ),
        ]

        self.preference_entity = [
            PreferenceEntity(
                preferences_id=1,
                user_id=1,
                resume_guidance=False,
                career_path_guidance=False,
                experience_sharing=True,
                industry_trends=True,
                technical_skills=False,
                soft_skills=False,
                networking=False,
                project_management=True,
                specific_industry={
                    "swe": False,
                    "uiux": True,
                    "ds": False,
                    "pm": False,
                },
            ),
            PreferenceEntity(
                preferences_id=2,
                user_id=1,
                resume_guidance=None,
                specific_industry=None,
            ),
        ]

        self.participants_entity = [
            MentorshipRoundParticipantsEntity(
                participant_id=uuid.uuid4(),
                user_id=1,
                round_id=1,
                participant_role=ParticipantRole.MENTEE,
                expected_partner_user_id=[456],
                unexpected_partner_user_id=[],
                max_partners=1,
                goal="I want to learn project management skills.",
            ),
            MentorshipRoundParticipantsEntity(
                participant_id=uuid.uuid4(),
                user_id=1,
                round_id=2,
                participant_role=ParticipantRole.MENTEE,
                expected_partner_user_id=None,
                unexpected_partner_user_id=None,
                max_partners=None,
                goal=None,
            ),
        ]

        self.pair_entities = [
            MentorshipPairsEntity(
                pair_id=12,
                round_id=1,
                mentor_id=456,
                mentee_id=1,
                completed_count=1,
                status=PairStatus.ACTIVE,
                mentor_action_status=MentorActionStatus.CONFIRMED,
                mentee_action_status=MenteeActionStatus.CONFIRMED,
                recommendation_reason="Mutual preference.",
                meeting_log={
                    "meeting_time_list": [
                        {
                            "meeting_id": str(uuid.uuid4()),
                            "start_datetime": "2025-09-01T22:30:00Z",
                            "end_datetime": "2025-09-01T23:00:00Z",
                            "is_completed": True,
                            "created_datetime": "2025-08-30T07:42:00Z",
                        },
                        {
                            "meeting_id": str(uuid.uuid4()),
                            "end_datetime": "2025-09-02T18:00:00Z",
                            "is_completed": True,
                            "start_datetime": "2025-09-02T17:00:00Z",
                            "created_datetime": "2025-08-29T07:42:00Z",
                        },
                    ],
                },
            ),
            MentorshipPairsEntity(
                pair_id=11,
                round_id=2,
                mentor_id=20,
                mentee_id=1,
                completed_count=0,
                status=PairStatus.ACTIVE,
                mentor_action_status=MentorActionStatus.PENDING,
                mentee_action_status=MenteeActionStatus.TIME_PROPOSED,
                recommendation_reason="Skill alignment.",
                meeting_log=None,
            ),
        ]

        self.users = [
            UsersEntity(
                user_id=1,
                first_name="Alice",
                last_name="Admin",
                timezone="Asia/Shanghai",
                timezone_updated_at=datetime.now(timezone.utc),
                communication_channel=CommunicationMethod.EMAIL,
                is_active=True,
                updated_timestamp=datetime.now(timezone.utc),
            )
        ]

    def test_map_to_rounds_dto_with_full_data(self):
        """Test mapping mentorship round entities with complete timeline and count data."""
        pair_stats = {
            1: {
                "active_pairs": 5,
                "matched_participants": 10,
                "total_completed_meetings": 10,
            },
            2: {
                "active_pairs": 4,
                "matched_participants": 7,
                "total_completed_meetings": 6,
            },
        }

        dtos = self.mapper.map_to_rounds_dto(
            self.mentorship_round_entities,
            pair_stats=pair_stats,
        )
        dto = dtos[0]

        self.assertIsInstance(dto, RoundsDto)
        self.assertEqual(dto.id, 1)
        self.assertEqual(dto.name, "Spring-2025")
        self.assertEqual(dto.required_meetings, 4)

        expected_timeline = TimelineDto(**self.test_dates)
        self.assertIsNotNone(dto.timeline)
        self.assertEqual(dto.timeline, expected_timeline)

        self.assertEqual(dtos[0].active_pairs, 5)
        self.assertEqual(dtos[0].matched_participants, 10)
        self.assertEqual(dtos[0].total_completed_meetings, 10)
        self.assertEqual(dtos[1].active_pairs, 4)
        self.assertEqual(dtos[1].matched_participants, 7)
        self.assertEqual(dtos[1].total_completed_meetings, 6)
        self.assertIsNone(dtos[2].active_pairs)
        self.assertIsNone(dtos[2].matched_participants)
        self.assertIsNone(dtos[2].total_completed_meetings)

    def test_map_to_global_preferences_dto_success(self):
        """Test mapping preference entity to global preferences dto correctly."""
        dto = self.mapper.map_to_global_preferences_dto(self.preference_entity[0])

        self.assertIsInstance(dto, GlobalPreferencesDto)

        self.assertIsInstance(dto.skillsets, SkillsetsDto)
        self.assertFalse(dto.skillsets.resume_guidance)
        self.assertTrue(dto.skillsets.experience_sharing)

        self.assertIsInstance(dto.specific_industry, SpecificIndustryDto)
        self.assertFalse(dto.specific_industry.swe)
        self.assertTrue(dto.specific_industry.uiux)

    def test_map_to_global_preferences_dto_none_fields(self):
        """Should return default values when optional fields are not provided."""
        dto = self.mapper.map_to_global_preferences_dto(self.preference_entity[1])

        self.assertFalse(dto.skillsets.resume_guidance)
        self.assertFalse(dto.specific_industry.swe)
        self.assertFalse(dto.specific_industry.uiux)

    def test_map_to_round_preference_dto_success(self):
        """Test mapping mentorship round preference entity to round preferences dto correctly."""
        dto = self.mapper.map_to_round_preference_dto(self.participants_entity[0])

        self.assertIsInstance(dto, RoundPreferencesDto)

        self.assertEqual(
            dto.participant_role, self.participants_entity[0].participant_role
        )
        self.assertEqual(
            dto.expected_partner_ids,
            self.participants_entity[0].expected_partner_user_id,
        )
        self.assertEqual(
            dto.unexpected_partner_ids,
            self.participants_entity[0].unexpected_partner_user_id,
        )
        self.assertEqual(dto.max_partners, self.participants_entity[0].max_partners)
        self.assertEqual(dto.goal, self.participants_entity[0].goal)

    def test_map_to_round_preference_dto_none_fields(self):
        """Should return default values when optional fields are not provided."""
        dto = self.mapper.map_to_round_preference_dto(self.participants_entity[1])

        self.assertEqual(
            dto.participant_role, self.participants_entity[1].participant_role
        )
        self.assertEqual(dto.expected_partner_ids, [])
        self.assertEqual(dto.unexpected_partner_ids, [])
        self.assertEqual(dto.max_partners, 1)
        self.assertEqual(dto.goal, "")

    def test_map_to_meeting_dto_success(self):
        """Test mapping pair entities with meeting rows to meeting dto correctly."""
        pair_entity = self.pair_entities[0]
        # Deliberately blanked: the fixture's own `meeting_log` holds entries
        # with these exact same times (see setUp), so leaving it in place
        # would let a mapper that still reads `meeting_log` -- and ignores
        # `meetings_by_pair` entirely -- pass this test by coincidence.
        # Clearing it makes the test source-discriminating.
        pair_entity.meeting_log = None
        partner_id = pair_entity.mentor_id
        meeting_rows = [
            MentorshipMeetingEntity(
                meeting_id=str(uuid.uuid4()),
                pair_id=pair_entity.pair_id,
                source=MeetingSource.MANUAL,
                start_datetime=datetime.fromisoformat("2025-09-01T22:30:00+00:00"),
                end_datetime=datetime.fromisoformat("2025-09-01T23:00:00+00:00"),
                is_completed=True,
                created_datetime=datetime.fromisoformat("2025-08-30T07:42:00+00:00"),
            ),
            MentorshipMeetingEntity(
                meeting_id=str(uuid.uuid4()),
                pair_id=pair_entity.pair_id,
                source=MeetingSource.MANUAL,
                start_datetime=datetime.fromisoformat("2025-09-02T17:00:00+00:00"),
                end_datetime=datetime.fromisoformat("2025-09-02T18:00:00+00:00"),
                is_completed=True,
                created_datetime=datetime.fromisoformat("2025-08-29T07:42:00+00:00"),
            ),
        ]

        dto = self.mapper.map_to_meeting_dto(
            round_id=1,
            grouped_pairs=[(pair_entity, partner_id)],
            meetings_by_pair={pair_entity.pair_id: meeting_rows},
            completed_counts={pair_entity.pair_id: 1},
        )
        info = dto.meeting_info[0]

        self.assertIsInstance(dto, MeetingDto)
        self.assertEqual(dto.round_id, 1)

        self.assertEqual(info.partner_id, 456)
        self.assertEqual(info.participant_role, ParticipantRole.MENTEE)
        self.assertEqual(len(info.meeting_time_list), 2)

        self.assertTrue(info.meeting_time_list[0].is_completed)
        self.assertEqual(
            info.meeting_time_list[0].start_datetime.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "2025-09-01T22:30:00Z",
        )
        # completed_meetings_count comes from the counts handed in, not from
        # counting the rows in meetings_by_pair -- that mapping excludes
        # LEGACY rows, which are all a historical pairing has.
        self.assertEqual(info.completed_meetings_count, 1)

    def test_map_to_meeting_dto_takes_completed_count_from_the_caller(self):
        """completed_meetings_count comes from the counts handed in, not from
        mentorship_pairs.completed_count. Seeded so the two disagree: the
        column says 9, the caller counted 2. The counts cannot be derived from
        meetings_by_pair here -- that mapping excludes LEGACY rows, which are
        all a historical pairing has."""
        pair_entity = self.pair_entities[0]
        pair_entity.completed_count = 9

        dto = self.mapper.map_to_meeting_dto(
            round_id=1,
            grouped_pairs=[(pair_entity, 456)],
            meetings_by_pair={},
            completed_counts={pair_entity.pair_id: 2},
        )

        self.assertEqual(dto.meeting_info[0].completed_meetings_count, 2)

    def test_map_to_meeting_dto_reports_zero_when_the_pair_was_not_counted(self):
        """A pair missing from the counts reports 0 rather than raising."""
        pair_entity = self.pair_entities[0]
        pair_entity.completed_count = 9

        dto = self.mapper.map_to_meeting_dto(
            round_id=1,
            grouped_pairs=[(pair_entity, 456)],
            meetings_by_pair={},
            completed_counts={},
        )

        self.assertEqual(dto.meeting_info[0].completed_meetings_count, 0)

    def test_meeting_dto_no_meeting_log(self):
        """Test mapping pair entities absent from meetings_by_pair returns an empty meeting list."""
        pair_entity = self.pair_entities[1]
        partner_id = pair_entity.mentor_id

        dto = self.mapper.map_to_meeting_dto(
            round_id=2,
            grouped_pairs=[(pair_entity, partner_id)],
            meetings_by_pair={},
            completed_counts={pair_entity.pair_id: 0},
        )

        self.assertIsInstance(dto, MeetingDto)
        self.assertEqual(len(dto.meeting_info), 1)

        info = dto.meeting_info[0]
        self.assertEqual(info.meeting_time_list, [])

    def test_map_to_meeting_dto_excludes_legacy_rows(self):
        """LEGACY rows carry no times and must never appear in the list, even
        if a caller passes them in (e.g. via include_legacy=True); the
        completed count they represent still comes through via
        pair.completed_count, unaffected by this filtering."""
        pair_entity = self.pair_entities[0]
        pair_entity.completed_count = 5
        partner_id = pair_entity.mentor_id
        manual_row = MentorshipMeetingEntity(
            meeting_id=str(uuid.uuid4()),
            pair_id=pair_entity.pair_id,
            source=MeetingSource.MANUAL,
            start_datetime=datetime.fromisoformat("2025-09-01T22:30:00+00:00"),
            end_datetime=datetime.fromisoformat("2025-09-01T23:00:00+00:00"),
            is_completed=True,
            created_datetime=datetime.fromisoformat("2025-08-30T07:42:00+00:00"),
        )
        legacy_row = MentorshipMeetingEntity(
            meeting_id="legacy-12-1",
            pair_id=pair_entity.pair_id,
            source=MeetingSource.LEGACY,
            start_datetime=None,
            end_datetime=None,
            is_completed=True,
            created_datetime=datetime.fromisoformat("2020-01-01T00:00:00+00:00"),
        )

        dto = self.mapper.map_to_meeting_dto(
            round_id=1,
            grouped_pairs=[(pair_entity, partner_id)],
            meetings_by_pair={pair_entity.pair_id: [legacy_row, manual_row]},
            completed_counts={pair_entity.pair_id: 5},
        )
        info = dto.meeting_info[0]

        self.assertEqual(len(info.meeting_time_list), 1)
        self.assertEqual(info.meeting_time_list[0].meeting_id, manual_row.meeting_id)
        self.assertEqual(info.completed_meetings_count, 5)

    def test_map_to_meeting_dto_preserves_repository_order(self):
        """The v1 list order moved from JSONB insertion order to whatever
        order the repository hands back (start_datetime ascending, per
        MentorshipMeetingRepository). This mapper does not re-sort -- it must
        trust and pass through the given order exactly. Rows here are built
        with `created_datetime` deliberately in the OPPOSITE order from
        `start_datetime`, so a mapper that (accidentally or otherwise) sorted
        by creation time instead of trusting input order would produce a
        different, and therefore caught, result."""
        pair_entity = self.pair_entities[0]
        pair_entity.meeting_log = None
        partner_id = pair_entity.mentor_id

        earliest_start_but_created_last = MentorshipMeetingEntity(
            meeting_id="row-a",
            pair_id=pair_entity.pair_id,
            source=MeetingSource.MANUAL,
            start_datetime=datetime.fromisoformat("2025-09-01T10:00:00+00:00"),
            end_datetime=datetime.fromisoformat("2025-09-01T11:00:00+00:00"),
            is_completed=True,
            created_datetime=datetime.fromisoformat("2025-09-05T00:00:00+00:00"),
        )
        latest_start_but_created_first = MentorshipMeetingEntity(
            meeting_id="row-b",
            pair_id=pair_entity.pair_id,
            source=MeetingSource.MANUAL,
            start_datetime=datetime.fromisoformat("2025-09-10T10:00:00+00:00"),
            end_datetime=datetime.fromisoformat("2025-09-10T11:00:00+00:00"),
            is_completed=True,
            created_datetime=datetime.fromisoformat("2025-09-01T00:00:00+00:00"),
        )
        # Given in start_datetime-ascending order, as the repository contract
        # promises -- NOT in created_datetime order.
        repository_ordered_rows = [
            earliest_start_but_created_last,
            latest_start_but_created_first,
        ]

        dto = self.mapper.map_to_meeting_dto(
            round_id=1,
            grouped_pairs=[(pair_entity, partner_id)],
            meetings_by_pair={pair_entity.pair_id: repository_ordered_rows},
            completed_counts={pair_entity.pair_id: 0},
        )
        info = dto.meeting_info[0]

        self.assertEqual(
            [m.meeting_id for m in info.meeting_time_list],
            ["row-a", "row-b"],
        )

    def test_map_to_meeting_v2_dto_success(self):
        """Test mapping manual and google meeting rows into MeetingDto correctly.

        Rows are handed in already interleaved by start_datetime (as
        MentorshipMeetingRepository.get_meetings_by_pair(s) returns them) --
        manual/manual/google in the middle of the manual ones -- to pin that
        this method passes the given order through rather than concatenating
        manual rows before google rows.
        """
        pair_entity = self.pair_entities[0]
        partner_id = pair_entity.mentor_id
        pair_entity.completed_count = 2
        # Deliberately stale: v2 must read exclusively from `meetings_by_pair`
        # rows, never from this JSONB column.
        pair_entity.meeting_log = None

        manual_1 = MentorshipMeetingEntity(
            meeting_id="manual-1",
            pair_id=pair_entity.pair_id,
            source=MeetingSource.MANUAL,
            start_datetime=datetime.fromisoformat("2025-09-01T22:30:00+00:00"),
            end_datetime=datetime.fromisoformat("2025-09-01T23:00:00+00:00"),
            is_completed=True,
            created_datetime=datetime.fromisoformat("2025-08-30T07:42:00+00:00"),
        )
        google_1 = MentorshipMeetingEntity(
            meeting_id="google-1",
            pair_id=pair_entity.pair_id,
            source=MeetingSource.GOOGLE,
            start_datetime=datetime.fromisoformat("2025-09-02T22:30:00+00:00"),
            end_datetime=datetime.fromisoformat("2025-09-02T23:00:00+00:00"),
            is_completed=True,
            created_datetime=datetime.fromisoformat("2025-08-31T10:00:00+00:00"),
            has_unknown_absent=True,
            absent_user_id=123,
            has_unknown_late=False,
            late_user_ids=None,
            has_insufficient_duration=True,
        )
        manual_2 = MentorshipMeetingEntity(
            meeting_id="manual-2",
            pair_id=pair_entity.pair_id,
            source=MeetingSource.MANUAL,
            start_datetime=datetime.fromisoformat("2025-09-03T22:30:00+00:00"),
            end_datetime=datetime.fromisoformat("2025-09-03T23:00:00+00:00"),
            is_completed=False,
            created_datetime=datetime.fromisoformat("2025-08-30T07:42:00+00:00"),
        )
        # start_datetime order: manual_1, google_1, manual_2 -- google
        # sandwiched between two manual rows, NOT segregated by source.
        interleaved_rows = [manual_1, google_1, manual_2]

        dto = self.mapper.map_to_meeting_v2_dto(
            round_id=1,
            grouped_pairs=[(pair_entity, partner_id)],
            meetings_by_pair={pair_entity.pair_id: interleaved_rows},
            completed_counts={pair_entity.pair_id: 2},
        )
        info = dto.meeting_info[0]

        self.assertIsInstance(dto, MeetingDto)
        self.assertEqual(dto.round_id, 1)

        self.assertEqual(info.partner_id, 456)
        self.assertEqual(info.participant_role, ParticipantRole.MENTEE)
        self.assertEqual(info.completed_meetings_count, 2)
        self.assertEqual(len(info.meeting_time_list), 3)

        # Order must match the input exactly -- manual, google, manual --
        # proving this method interleaves by trusting given order rather
        # than concatenating all manual rows before all google rows.
        self.assertEqual(
            [m.meeting_id for m in info.meeting_time_list],
            ["manual-1", "google-1", "manual-2"],
        )

        self.assertTrue(info.meeting_time_list[0].is_completed)
        self.assertEqual(
            info.meeting_time_list[0].created_datetime.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "2025-08-30T07:42:00Z",
        )

        self.assertTrue(info.meeting_time_list[1].is_completed)
        self.assertEqual(
            info.meeting_time_list[1].created_datetime.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "2025-08-31T10:00:00Z",
        )

        self.assertFalse(info.meeting_time_list[2].is_completed)

    def test_map_to_meeting_v2_dto_detail_false_excludes_google_extra_fields(self):
        """Test google meeting extra fields are not populated when include_details=False."""
        pair_entity = self.pair_entities[0]
        partner_id = pair_entity.mentor_id
        pair_entity.completed_count = 1
        pair_entity.meeting_log = None

        google_row = MentorshipMeetingEntity(
            meeting_id="google-1",
            pair_id=pair_entity.pair_id,
            source=MeetingSource.GOOGLE,
            start_datetime=datetime.fromisoformat("2025-09-02T22:30:00+00:00"),
            end_datetime=datetime.fromisoformat("2025-09-02T23:00:00+00:00"),
            is_completed=True,
            created_datetime=datetime.fromisoformat("2025-08-31T10:00:00+00:00"),
            has_unknown_absent=True,
            absent_user_id=123,
            has_unknown_late=True,
            late_user_ids=[456],
            has_insufficient_duration=True,
        )

        dto = self.mapper.map_to_meeting_v2_dto(
            round_id=1,
            grouped_pairs=[(pair_entity, partner_id)],
            meetings_by_pair={pair_entity.pair_id: [google_row]},
            include_details=False,
            completed_counts={pair_entity.pair_id: 1},
        )
        info = dto.meeting_info[0]
        google_meeting = info.meeting_time_list[0]

        self.assertEqual(len(info.meeting_time_list), 1)
        self.assertEqual(info.completed_meetings_count, 1)
        self.assertEqual(google_meeting.meeting_id, "google-1")
        self.assertEqual(
            google_meeting.created_datetime.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "2025-08-31T10:00:00Z",
        )
        self.assertIsNone(google_meeting.has_unknown_absent)
        self.assertIsNone(google_meeting.absent_user_id)
        self.assertIsNone(google_meeting.has_unknown_late)
        self.assertIsNone(google_meeting.late_user_ids)
        self.assertIsNone(google_meeting.has_insufficient_duration)

    def test_map_to_meeting_v2_dto_detail_true_includes_google_extra_fields(self):
        """Test google meeting extra fields are populated when include_details=True.

        Also the PUR-525 pre-existing-bug pin: `late_user_ids` (plural) now
        reads from the real column of the same name, rather than the JSONB
        writer's `late_user_id` (singular) that never matched this read key --
        so it must carry a value here, not silently stay null.
        """
        pair_entity = self.pair_entities[0]
        partner_id = pair_entity.mentor_id
        pair_entity.completed_count = 1
        pair_entity.meeting_log = None

        google_row = MentorshipMeetingEntity(
            meeting_id="google-1",
            pair_id=pair_entity.pair_id,
            source=MeetingSource.GOOGLE,
            start_datetime=datetime.fromisoformat("2025-09-02T22:30:00+00:00"),
            end_datetime=datetime.fromisoformat("2025-09-02T23:00:00+00:00"),
            is_completed=True,
            created_datetime=datetime.fromisoformat("2025-08-31T10:00:00+00:00"),
            has_unknown_absent=True,
            absent_user_id=123,
            has_unknown_late=True,
            late_user_ids=[456],
            has_insufficient_duration=True,
        )

        dto = self.mapper.map_to_meeting_v2_dto(
            round_id=1,
            grouped_pairs=[(pair_entity, partner_id)],
            meetings_by_pair={pair_entity.pair_id: [google_row]},
            include_details=True,
            completed_counts={pair_entity.pair_id: 1},
        )
        info = dto.meeting_info[0]
        google_meeting = info.meeting_time_list[0]

        self.assertEqual(len(info.meeting_time_list), 1)
        self.assertEqual(info.completed_meetings_count, 1)
        self.assertEqual(google_meeting.meeting_id, "google-1")
        self.assertEqual(
            google_meeting.created_datetime.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "2025-08-31T10:00:00Z",
        )
        self.assertTrue(google_meeting.has_unknown_absent)
        self.assertEqual(google_meeting.absent_user_id, 123)
        self.assertTrue(google_meeting.has_unknown_late)
        # The bug-fix assertion: late_user_ids (plural) is populated.
        self.assertEqual(google_meeting.late_user_ids, [456])
        self.assertTrue(google_meeting.has_insufficient_duration)

    def test_map_to_meeting_v2_dto_no_meetings(self):
        """Test mapping a pair absent from meetings_by_pair returns an empty list."""
        pair_entity = self.pair_entities[1]
        partner_id = pair_entity.mentor_id
        pair_entity.completed_count = 0

        dto = self.mapper.map_to_meeting_v2_dto(
            round_id=2,
            grouped_pairs=[(pair_entity, partner_id)],
            meetings_by_pair={},
            completed_counts={pair_entity.pair_id: 0},
        )

        self.assertIsInstance(dto, MeetingDto)
        self.assertEqual(len(dto.meeting_info), 1)

        info = dto.meeting_info[0]
        self.assertEqual(info.meeting_time_list, [])
        self.assertEqual(info.completed_meetings_count, 0)

    def test_map_to_global_preferences_dto_with_profile_survey(self):
        """Profile survey data in entity should be mapped to ProfileSurveyDto."""
        entity = PreferenceEntity(
            preferences_id=3,
            user_id=1,
            profile_survey={"career_transition": "tech", "region": "us_west"},
        )
        dto = self.mapper.map_to_global_preferences_dto(entity)

        self.assertIsNotNone(dto.profile_survey)
        self.assertIsInstance(dto.profile_survey, ProfileSurveyDto)
        self.assertEqual(dto.profile_survey.career_transition, "tech")
        self.assertEqual(dto.profile_survey.region, "us_west")
        self.assertIsNone(dto.profile_survey.region_other)

    def test_map_to_global_preferences_dto_profile_survey_none(self):
        """When profile_survey is None on entity, dto should have None."""
        dto = self.mapper.map_to_global_preferences_dto(self.preference_entity[1])
        self.assertIsNone(dto.profile_survey)

    def test_map_to_round_preference_dto_with_current_stage_and_time_urgency(self):
        """current_stage and time_urgency should be mapped from entity to dto."""
        entity = MentorshipRoundParticipantsEntity(
            participant_id=uuid.uuid4(),
            user_id=1,
            round_id=1,
            participant_role=ParticipantRole.MENTEE,
            expected_partner_user_id=[],
            unexpected_partner_user_id=[],
            max_partners=1,
            goal="test goal",
            current_stage="exploring",
            time_urgency="high",
        )
        dto = self.mapper.map_to_round_preference_dto(entity)

        self.assertEqual(dto.current_stage, "exploring")
        self.assertEqual(dto.time_urgency, "high")

    def test_map_to_round_preference_dto_current_stage_time_urgency_none(self):
        """When current_stage and time_urgency are absent, they should be None in dto."""
        dto = self.mapper.map_to_round_preference_dto(self.participants_entity[1])
        self.assertIsNone(dto.current_stage)
        self.assertIsNone(dto.time_urgency)

    def test_map_to_meeting_v2_dto_excludes_legacy_rows(self):
        """LEGACY rows must never surface in the v2 list either, even if a
        caller somehow passed one in -- they carry no times and this method
        must not crash trying to build a MeetingTimeDto from null times."""
        pair_entity = self.pair_entities[0]
        partner_id = pair_entity.mentor_id
        pair_entity.completed_count = 5
        pair_entity.meeting_log = None

        google_row = MentorshipMeetingEntity(
            meeting_id="google-1",
            pair_id=pair_entity.pair_id,
            source=MeetingSource.GOOGLE,
            start_datetime=datetime.fromisoformat("2025-09-02T22:30:00+00:00"),
            end_datetime=datetime.fromisoformat("2025-09-02T23:00:00+00:00"),
            is_completed=True,
            created_datetime=datetime.fromisoformat("2025-08-31T10:00:00+00:00"),
        )
        legacy_row = MentorshipMeetingEntity(
            meeting_id="legacy-12-1",
            pair_id=pair_entity.pair_id,
            source=MeetingSource.LEGACY,
            start_datetime=None,
            end_datetime=None,
            is_completed=True,
            created_datetime=datetime.fromisoformat("2020-01-01T00:00:00+00:00"),
        )

        dto = self.mapper.map_to_meeting_v2_dto(
            round_id=1,
            grouped_pairs=[(pair_entity, partner_id)],
            meetings_by_pair={pair_entity.pair_id: [legacy_row, google_row]},
            include_details=True,
            completed_counts={pair_entity.pair_id: 5},
        )

        info = dto.meeting_info[0]
        self.assertEqual(len(info.meeting_time_list), 1)
        self.assertEqual(info.meeting_time_list[0].meeting_id, "google-1")
        self.assertEqual(info.completed_meetings_count, 5)

    def test_map_to_admin_meeting_dto(self):
        """Test mapping a raw meeting_log entry to an AdminMeetingDto."""
        meeting = {
            "meeting_id": "gm-1",
            "start_datetime": "2026-05-05T10:00:00",
            "end_datetime": "2026-05-05T11:00:00",
            "created_datetime": "2026-05-05T09:55:00",
        }

        dto = self.mapper.map_to_admin_meeting_dto(
            meeting,
            is_completed=True,
            note_tags=[MeetingNoteTag.MENTOR_LATE],
        )

        self.assertIsInstance(dto, AdminMeetingDto)
        self.assertEqual(dto.meeting_id, "gm-1")
        self.assertEqual(dto.start_datetime, "2026-05-05T10:00:00")
        self.assertEqual(dto.end_datetime, "2026-05-05T11:00:00")
        self.assertTrue(dto.is_completed)
        self.assertEqual(dto.note, [MeetingNoteTag.MENTOR_LATE])
        self.assertEqual(dto.create_datetime, "2026-05-05T09:55:00")


if __name__ == "__main__":
    unittest.main()
