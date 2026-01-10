import unittest
import uuid
from datetime import date, datetime, timezone

from backend.dto.rounds_dto import RoundsDto, TimelineDto
from backend.dto.partner_dto import PartnerDto
from backend.entity.users_entity import UsersEntity
from backend.entity.mentorship_round_entity import MentorshipRoundEntity
from backend.mentorship.mentorship_mapper import MentorshipMapper
from backend.common.mentorship_enums import UserTimezone, CommunicationMethod


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


if __name__ == "__main__":
    unittest.main()
