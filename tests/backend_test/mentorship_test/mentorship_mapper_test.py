import unittest
import uuid
from datetime import date, datetime, timezone

from backend.dto.preference_dto import SpecificIndustryDto, SkillsetsDto
from backend.dto.registration_dto import GlobalPreferencesDto, RoundPreferencesDto
from backend.dto.rounds_dto import RoundsDto, TimelineDto
from backend.dto.partner_dto import PartnerDto
from backend.entity.users_entity import UsersEntity
from backend.entity.preference_entity import PreferenceEntity
from backend.entity.mentorship_round_participants_entity import (
    MentorshipRoundParticipantsEntity,
)
from backend.entity.mentorship_round_entity import MentorshipRoundEntity
from backend.mentorship.mentorship_mapper import MentorshipMapper
from backend.common.mentorship_enums import (
    UserTimezone,
    CommunicationMethod,
    ParticipantRole,
)


class TestMentorshipMapper(unittest.TestCase):
    def setUp(self):
        """Prepare test data."""
        self.now = datetime.now(timezone.utc)
        self.mapper = MentorshipMapper()

        self.test_dates = {
            "promotion_start_at": date(2025, 7, 1),
            "application_deadline_at": date(2025, 7, 15),
            "review_start_at": date(2025, 7, 16),
            "acceptance_notification_at": date(2025, 7, 30),
            "matching_completed_at": date(2025, 8, 5),
            "match_notification_at": date(2025, 8, 6),
            "first_meeting_deadline_at": date(2025, 8, 20),
            "meetings_completion_deadline_at": date(2025, 11, 20),
            "feedback_deadline_at": date(2025, 11, 22),
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

        self.users = [
            UsersEntity(
                user_id=1,
                first_name="Alice",
                last_name="Admin",
                timezone=UserTimezone.ASIA_SHANGHAI,
                timezone_updated_at=datetime.now(timezone.utc),
                communication_channel=CommunicationMethod.EMAIL,
                primary_email="alice@example.com",
                is_active=True,
                updated_timestamp=datetime.now(timezone.utc),
                subject_identifier=str(uuid.uuid4()),
            )
        ]

    def test_map_to_rounds_dto_with_full_data(self):
        """Test mapping a mentorship round entity with complete timeline data."""
        dtos = self.mapper.map_to_rounds_dto(self.mentorship_round_entities)
        dto = dtos[0]

        self.assertIsInstance(dto, RoundsDto)
        self.assertEqual(dto.id, 1)
        self.assertEqual(dto.name, "Spring-2025")
        self.assertEqual(dto.required_meetings, 4)

        expected_timeline = TimelineDto(**self.test_dates)
        self.assertIsNotNone(dto.timeline)
        self.assertEqual(dto.timeline, expected_timeline)

    def test_map_to_partner_dto_with_full_data(self):
        """Test mapping users entity has preferred_name to partner dto."""
        self.users[0].preferred_name = "Amy"
        dtos = self.mapper.map_to_partner_dto(self.users)
        dto = dtos[0]

        self.assertIsInstance(dto, PartnerDto)
        self.assertEqual(dto.id, self.users[0].user_id)
        self.assertEqual(dto.first_name, self.users[0].first_name)
        self.assertEqual(dto.last_name, self.users[0].last_name)
        self.assertEqual(dto.preferred_name, self.users[0].preferred_name)
        self.assertEqual(dto.primary_email, self.users[0].primary_email)

    def test_map_to_partner_dto_without_preferred_name(self):
        """Test mapping users entity with no preferred_name to partner dto."""
        dtos = self.mapper.map_to_partner_dto(self.users)
        dto = dtos[0]

        self.assertIsInstance(dto, PartnerDto)
        self.assertEqual(dto.preferred_name, self.users[0].first_name)

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


if __name__ == "__main__":
    unittest.main()
