import unittest
import uuid
from datetime import date, datetime, timezone

from backend.dto.rounds_dto import RoundsDto, TimelineDto
from backend.dto.partner_dto import PartnerDto
from backend.entity.users_entity import UsersEntity
from backend.entity.mentorship_round_entity import MentorshipRoundEntity
from backend.mentorship.mentorship_mapper import MentorshipMapper
from backend.common.mentorship_enums import UserTimezone, CommunicationMethod


class TestMentorhsipMapper(unittest.TestCase):
    def setUp(self):
        """Prepare test data."""
        self.now = datetime.now(timezone.utc)

        self.mapper = MentorshipMapper()

        self.mentorship_round_entity = [
            MentorshipRoundEntity(
                round_id=1,
                name="Spring-2025",
                description={
                    "start_date": date(2025, 7, 1),
                    "end_date": date(2025, 11, 22),
                },
                required_meetings=4,
            ),
            MentorshipRoundEntity(
                round_id=2, name="Summer-2025", description=None, required_meetings=5
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
        """Test mapping mentorship round entity with complete data."""
        dtos = self.mapper.map_to_rounds_dto(self.mentorship_round_entity)
        dto = dtos[0]

        self.assertIsInstance(dto, RoundsDto)
        self.assertEqual(dto.id, 1)
        self.assertEqual(dto.name, "Spring-2025")
        self.assertEqual(dto.required_meetings, 4)
        self.assertEqual(
            dto.timeline,
            TimelineDto(start_date=date(2025, 7, 1), end_date=date(2025, 11, 22)),
        )

    def test_map_to_rounds_dto_without_description(self):
        """Test mapping mentorship round entity with missing description."""
        dtos = self.mapper.map_to_rounds_dto(self.mentorship_round_entity)
        dto = dtos[1]

        self.assertIsInstance(dto, RoundsDto)
        self.assertIsNone(dto.timeline)
        self.assertEqual(dto.id, 2)
        self.assertEqual(dto.name, "Summer-2025")
        self.assertEqual(dto.required_meetings, 5)

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
