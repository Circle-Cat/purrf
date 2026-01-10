from backend.dto.rounds_dto import RoundsDto, TimelineDto
from backend.dto.partner_dto import PartnerDto
from backend.entity.users_entity import UsersEntity
from backend.entity.mentorship_round_entity import MentorshipRoundEntity


class MentorshipMapper:
    """
    Mapper for converting mentorship round database entities to DTOs.
    """

    def map_to_rounds_dto(self, rounds: list[MentorshipRoundEntity]) -> list[RoundsDto]:
        """Maps a list of MentorshipRoundEntity objects to a list of RoundsDto objects."""
        return [
            RoundsDto(
                id=r.round_id,
                name=r.name,
                required_meetings=r.required_meetings,
                timeline=self._map_timeline(r.description) if r.description else None,
            )
            for r in rounds
        ]

    def _map_timeline(self, d: dict) -> TimelineDto:
        """
        Maps a dictionary containing timeline data to a TimelineDto.

        Args:
            d (dict): A dictionary containing timeline-related datetime fields.

        Returns:
            TimelineDto: A TimelineDto populated with the corresponding timeline values.
        """
        return TimelineDto(
            promotion_start_at=d.get("promotion_start_at"),
            application_deadline_at=d.get("application_deadline_at"),
            review_start_at=d.get("review_start_at"),
            acceptance_notification_at=d.get("acceptance_notification_at"),
            matching_completed_at=d.get("matching_completed_at"),
            match_notification_at=d.get("match_notification_at"),
            first_meeting_deadline_at=d.get("first_meeting_deadline_at"),
            meetings_completion_deadline_at=d.get("meetings_completion_deadline_at"),
            feedback_deadline_at=d.get("feedback_deadline_at"),
        )

    def map_to_partner_dto(self, user_entities: list[UsersEntity]) -> list[PartnerDto]:
        """Maps a list of UsersEntity objects to a list of PartnerDto objects."""
        return [
            PartnerDto(
                id=u.user_id,
                first_name=u.first_name,
                last_name=u.last_name,
                preferred_name=u.preferred_name or u.first_name,
                primary_email=u.primary_email,
            )
            for u in user_entities
        ]
