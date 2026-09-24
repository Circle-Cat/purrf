from datetime import datetime, timezone

from backend.common.mentorship_enums import RoundStatus
from backend.mentorship.mentorship_mapper import MentorshipMapper
from backend.mentorship.round_windows import (
    is_feedback_editable,
    is_feedback_open,
    round_status,
)
from backend.repository.mentorship_round_repository import MentorshipRoundRepository
from backend.repository.mentorship_pairs_repository import MentorshipPairsRepository
from backend.entity.mentorship_round_entity import MentorshipRoundEntity
from backend.dto.rounds_dto import RoundSlotsDto, RoundsDto
from backend.dto.rounds_create_dto import RoundsCreateDto

from sqlalchemy.ext.asyncio import AsyncSession


class RoundsService:
    """Service for managing mentorship rounds."""

    def __init__(
        self,
        mentorship_round_repository: MentorshipRoundRepository,
        mentorship_mapper: MentorshipMapper,
        mentorship_pairs_repository: MentorshipPairsRepository,
    ):
        """
        Initializes the RoundsService with required dependencies.

        Args:
            mentorship_round_repository (MentorshipRoundRepository):
                The repository for accessing mentorship round data.
            mentorship_mapper (MentorshipMapper):
                The mapper for converting database entities to DTOs.
            mentorship_pairs_repository (MentorshipPairsRepository):
                The repository for round stats queries.
        """
        self.mentorship_round_repository = mentorship_round_repository
        self.mentorship_mapper = mentorship_mapper
        self.mentorship_pairs_repository = mentorship_pairs_repository

    async def get_all_rounds(
        self, session: AsyncSession, include_details: bool = False
    ) -> list[RoundsDto]:
        """
        Retrieve all mentorship rounds and map them to DTOs.

        Args:
            session (AsyncSession): Active database async session.
            include_details (bool): If True, populates matched_participants and
                total_completed_meetings (for active pairs only) in each RoundsDto.

        Returns:
            list[RoundsDto]: A list of RoundsDto objects representing the mentorship rounds.
        """
        all_round_entities = await self.mentorship_round_repository.get_all_rounds(
            session
        )

        if not include_details:
            return self.mentorship_mapper.map_to_rounds_dto(all_round_entities)

        pair_stats = await self.mentorship_pairs_repository.get_pair_stats(session)

        return self.mentorship_mapper.map_to_rounds_dto(all_round_entities, pair_stats)

    async def get_round_slots(self, session: AsyncSession) -> RoundSlotsDto:
        """
        Resolve which rounds the Personal Dashboard acts on right now.

        Everything is evaluated against one server-side instant, so the
        dashboard, registration and the admission email agree on which round
        is open and whether it still is.

        Args:
            session (AsyncSession): Active database async session.

        Returns:
            RoundSlotsDto: The registration, matching, feedback and default
                round slots.
        """
        now = datetime.now(timezone.utc)
        repo = self.mentorship_round_repository

        open_round = await repo.get_open_registration_round(session, now)
        registration_round = open_round or await repo.get_latest_promoted_round(
            session, now
        )
        can_view_match = bool(
            registration_round
            and registration_round.match_notification_at
            and registration_round.feedback_deadline_at
            and registration_round.match_notification_at
            <= now
            <= registration_round.feedback_deadline_at
        )

        rounds = await repo.get_all_rounds(session)
        # Only promoted rounds count, as for the registration round.
        is_feedback_enabled = any(
            r.promotion_start_at is not None
            and is_feedback_open(r, now)
            and is_feedback_editable(r, now)
            for r in rounds
        )
        # get_all_rounds lists the latest meetings deadline first, so the
        # first match is the most recent round in that status.
        statuses = [(r.round_id, round_status(r, now)) for r in rounds]
        active_round_id = next(
            (rid for rid, status in statuses if status == RoundStatus.ACTIVE),
            None,
        )
        if active_round_id is None:
            active_round_id = next(
                (rid for rid, status in statuses if status == RoundStatus.UPCOMING),
                None,
            )

        return RoundSlotsDto(
            registration_round_id=(
                registration_round.round_id if registration_round else None
            ),
            registration_round_name=(
                registration_round.name if registration_round else None
            ),
            registration_deadline_at=(
                registration_round.onboarding_deadline_at
                if registration_round
                else None
            ),
            is_registration_open=open_round is not None,
            can_view_match=can_view_match,
            is_feedback_enabled=is_feedback_enabled,
            active_round_id=active_round_id,
        )

    async def upsert_rounds(
        self, session: AsyncSession, data: RoundsCreateDto
    ) -> RoundsDto:
        """
        Inserts a new MentorshipRoundEntity object or updates an existing one in the database.

        Args:
            session (AsyncSession): Active database async session.
            data(RoundsCreateDto):The data transfer object containing information about the round.

        Returns:
            RoundsDto: The DTO synchronized with the database, reflecting the latest state,
            generated keys, and default values.
        """

        if data.id is None:
            round = MentorshipRoundEntity()
        else:
            round = await self.mentorship_round_repository.get_by_round_id(
                session, data.id
            )

            if round is None:
                raise ValueError("Round with given ID does not exist.")

        round.name = data.name
        # The two average scores are not taken from the request: they are
        # derived from submitted feedback (ParticipationService), and the round
        # form never sends them, so copying them would clear them on every edit.
        round.expectations = data.expectations
        # Only the dates the caller sent are written: an omitted one keeps its
        # stored value, an explicit null clears it.
        for field in data.timeline.model_fields_set:
            setattr(round, field, getattr(data.timeline, field))
        round.required_meetings = data.required_meetings

        round = await self.mentorship_round_repository.upsert_round(session, round)
        await session.commit()

        return self.mentorship_mapper.map_to_rounds_dto([round])[0]
