import unittest
from datetime import date, datetime, timezone
from backend.dto.rounds_dto import RoundsDto, TimelineDto
from backend.entity.mentorship_round_entity import MentorshipRoundEntity
from backend.mentorship.mentorship_mapper import MentorshipMapper


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


if __name__ == "__main__":
    unittest.main()
