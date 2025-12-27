from backend.dto.rounds_dto import RoundsDto, TimelineDto
from backend.entity.mentorship_round_entity import MentorshipRoundEntity


class MentorshipMapper:
    """
    Mapper for converting mentorship round database entities to DTOs.
    """

    def map_to_rounds_dto(self, rounds: list[MentorshipRoundEntity]) -> list[RoundsDto]:
        """Maps a list of MentroshipRoundEntity objects to a list of RoundsDto objects."""
        return [
            RoundsDto(
                id=r.round_id,
                name=r.name,
                required_meetings=r.required_meetings,
                timeline=TimelineDto(
                    start_date=r.description.get("start_date"),
                    end_date=r.description.get("end_date"),
                )
                if r.description
                else None,
            )
            for r in rounds
        ]
