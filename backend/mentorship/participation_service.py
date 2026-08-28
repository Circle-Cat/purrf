from datetime import datetime, timezone
from dateutil.parser import isoparse
from dateutil.relativedelta import relativedelta
from backend.dto.partner_dto import PartnerDto
from backend.dto.matches_dto import MatchesDto
from backend.dto.user_context_dto import UserContextDto
from backend.dto.registration_dto import RoundPreferencesDto
from backend.dto.feedback_create_dto import FeedbackCreateDto
from backend.dto.feedback_dto import FeedbackDto
from backend.common.exceptions import ConflictError
from backend.common.mentorship_enums import ParticipantRole
from sqlalchemy.ext.asyncio import AsyncSession
from backend.common.mentorship_enums import (
    ApprovalStatus,
    MatchStatus,
    PairStatus,
)


class ParticipationService:
    """Service to retrieve mentorship participants information."""

    def __init__(
        self,
        logger,
        users_repository,
        mentorship_pairs_repository,
        mentorship_round_participants_repo,
        mentorship_round_repository,
        mentorship_mapper,
        user_emails_repository,
    ):
        """
        Initializes the ParticipationService with required dependencies.

        Args:
            logger: The logger instance for logging messages.
            users_repository (UsersRepository):
                The repository for accessing users entity data.
            mentorship_pairs_repository (MentorshipPairsRepository):
                The repository for accessing pairs entity data.
            mentorship_round_participants_repo (MentorshipRoundParticipantsRepository):
                The repository for accessing participants entity data.
            mentorship_round_repository (MentorshipRoundRepository):
                The repository for accessing mentorship round entity data.
            mentorship_mapper (MentorshipMapper):
                The mapper for converting mentorship rounds and entities to DTOs.
            user_emails_repository (UserEmailsRepository):
                Contact-email resolution for matched partners.
        """
        self.logger = logger
        self.users_repository = users_repository
        self.mentorship_pairs_repository = mentorship_pairs_repository
        self.mentorship_round_participants_repo = mentorship_round_participants_repo
        self.mentorship_round_repository = mentorship_round_repository
        self.mentorship_mapper = mentorship_mapper
        self.user_emails_repository = user_emails_repository

    async def get_partners_for_user(
        self,
        session: AsyncSession,
        user_context: UserContextDto,
        round_id: int | None = None,
    ) -> list[PartnerDto]:
        """
        Retrieve partial partner information for current user and map it to DTOs.

        This method:
        1. Resolves the internal user ID based on the provided UserContextDto.
        2. Determines the applicable mentorship round scope:
            - If round_id is not provided, returns partners associated with the current user
              across all mentorship rounds.
            - If round_id is provided, returns partners associated with the current user
              in the specified mentorship round.
        3. Returns partner information mapped to PartnerDto objects. Every
           pair the user holds in the round counts as a partner, each carrying
           `is_active`: a pairing that ended -- the mentor changed mid-round,
           or the counterpart quit -- is still the user's participation, and
           dropping it would leave them with an empty partner list. The
           primary_email field is populated only for a live pair, and only
           when round_id is provided and the user's approval status is
           MATCHED; otherwise None.

        Args:
            session (AsyncSession): Active database async session.
            user_context (UserContextDto): Authenticated user context.
            round_id (int | None): The ID of the mentorship round to filter by.

        Returns:
            list[PartnerDto]: A list of PartnerDto objects representing the matched users,
                            or an empty list if no users are found.
        """
        current_user_id = user_context.user_id

        if round_id is None:
            partner_ids = await self.mentorship_pairs_repository.get_all_partner_ids(
                session=session, user_id=current_user_id
            )
            if not partner_ids:
                self.logger.info(
                    "No partners found for user_id=%s, round_id=%s",
                    current_user_id,
                    round_id,
                )
                return []
            users = await self.users_repository.get_all_by_ids(
                session=session, user_ids=partner_ids
            )
            return [
                PartnerDto(
                    id=u.user_id,
                    first_name=u.first_name,
                    last_name=u.last_name,
                    preferred_name=u.preferred_name,
                    primary_email=None,
                )
                for u in users
            ]

        pairs_data = await self.mentorship_pairs_repository.get_pairs_with_partner_info(
            session=session,
            user_id=current_user_id,
            round_id=round_id,
        )
        if not pairs_data:
            self.logger.info(
                "No partners found for user_id=%s, round_id=%s",
                current_user_id,
                round_id,
            )
            return []
        participant = (
            await self.mentorship_round_participants_repo.get_by_user_id_and_round_id(
                session=session, user_id=current_user_id, round_id=round_id
            )
        )
        live_partner_ids = [
            p_user.user_id
            for pair, p_user in pairs_data
            if pair.status == PairStatus.ACTIVE
        ]
        contact_by_user_id = (
            await self.user_emails_repository.get_contact_emails_by_user_ids(
                session, live_partner_ids
            )
            if live_partner_ids
            and participant
            and participant.approval_status == ApprovalStatus.MATCHED
            else {}
        )

        return [
            PartnerDto(
                id=p_user.user_id,
                first_name=p_user.first_name,
                last_name=p_user.last_name,
                preferred_name=p_user.preferred_name,
                primary_email=contact_by_user_id.get(p_user.user_id),
                is_active=pair.status == PairStatus.ACTIVE,
            )
            for pair, p_user in pairs_data
        ]

    async def get_user_round_preferences(
        self,
        session: AsyncSession,
        user_id: int,
        round_id: int,
        participant_role: ParticipantRole | None,
    ) -> tuple[RoundPreferencesDto | None, bool]:
        """Retrieve preferences for a specific mentorship round.

        The role is supplied by the caller — the role the user chose to
        register this round under — and this method never infers one.
        Resolution:
        1. If the user has already registered for this round, that
           registration's role settles the round: its saved preferences come
           back as-is, and a request naming a different role is a conflict
           rather than a silent correction.
        2. Otherwise pre-fill from the user's most recent prior round in the
           SAME role, so a mentee's form is never seeded from a round they
           attended as a mentor (or vice versa).
        3. If there is no prior same-role round, return an empty default
           configuration carrying the supplied role.
        4. With no role supplied and no registration to show, there is
           nothing to prefill: return None.

        Args:
            session (AsyncSession): Active SQLAlchemy async session.
            user_id (int): The ID of the current user.
            round_id (int): The ID of the mentorship round.
            participant_role (ParticipantRole | None): Which role's form to
                answer for, or None to only report the current registration.

        Returns:
            tuple[RoundPreferencesDto | None, bool]
                - RoundPreferencesDto | None: The resolved round-specific
                  preferences, or None when there is nothing to prefill.
                - bool: Whether the user has registered for this round.

        Raises:
            ConflictError: The user is registered for this round under a
                different role than the one requested.
        """
        participant = (
            await self.mentorship_round_participants_repo.get_by_user_id_and_round_id(
                session=session, user_id=user_id, round_id=round_id
            )
        )
        if participant:
            if (
                participant_role is not None
                and participant.participant_role != participant_role
            ):
                raise ConflictError(
                    "You are already registered for this round as a "
                    f"{participant.participant_role.value}."
                )
            return self.mentorship_mapper.map_to_round_preference_dto(
                participants_entity=participant,
            ), True

        if participant_role is None:
            return None, False

        recent_same_role = await self.mentorship_round_participants_repo.get_recent_participant_by_user_id_and_role(
            session=session, user_id=user_id, participant_role=participant_role
        )
        if recent_same_role:
            return self.mentorship_mapper.map_to_round_preference_dto(
                participants_entity=recent_same_role,
            ), False

        return RoundPreferencesDto(
            participant_role=participant_role,
            expected_partner_ids=[],
            unexpected_partner_ids=[],
            max_partners=1,
            goal="",
        ), False

    async def get_my_match_result_by_round_id(
        self, session: AsyncSession, user_context: UserContextDto, round_id: int
    ) -> MatchesDto:
        """
        Retrieve the current user's mentorship match result for a specific round.

        This method resolves the current user from the provided user context,
        determines the user's participation and matching status for the given
        mentorship round, and returns the corresponding match result.

        A `rejected` status is reported with its pairings too, when there are
        any: the same status is stored for an application that was turned down
        and for someone who took part and then left, and only the pairing
        tells them apart.

        If the user is not in a MATCHED state, an empty partners list is returned
        along with the current match status. If the user is MATCHED, this method
        retrieves the user's mentorship pairs for the round and constructs
        partner details for each counterpart. A pairing that has since ended is
        still who the user was matched with, so it is reported with
        `is_active` false rather than left out; its contact email is withheld.

        Args:
            session (AsyncSession): The SQLAlchemy async session used for database operations.
            user_context (UserContextDto): Context information used to identify the current user.
            round_id (int): The mentorship round ID to retrieve match results for.

        Returns:
            MatchesDto:
                An object containing:
                - round_id: The mentorship round ID.
                - current_status: The user's match status for the round.
                - partners: A list of PartnerDto objects representing matched partners.
        """
        uid = user_context.user_id

        participant = (
            await self.mentorship_round_participants_repo.get_by_user_id_and_round_id(
                session=session, user_id=uid, round_id=round_id
            )
        )

        status_map = {
            ApprovalStatus.SIGNED_UP: MatchStatus.PENDING,
            ApprovalStatus.UN_MATCHED: MatchStatus.UNMATCHED,
            ApprovalStatus.REJECTED: MatchStatus.REJECTED,
            ApprovalStatus.MATCHED: MatchStatus.MATCHED,
        }
        current_status = (
            status_map.get(participant.approval_status, MatchStatus.UNKNOWN)
            if participant
            else MatchStatus.UNREGISTERED
        )

        partners: list[PartnerDto] = []

        # A pairing is reported for the two statuses that can have produced
        # one: the user is matched, or they took part and left -- `rejected`
        # covers quitting, being removed, and a mentor being suspended. The
        # remaining statuses never had a pairing, so the pairs table is not
        # touched for them.
        if current_status not in (MatchStatus.MATCHED, MatchStatus.REJECTED):
            return MatchesDto(
                round_id=round_id, current_status=current_status, partners=partners
            )

        pairs_data = await self.mentorship_pairs_repository.get_pairs_with_partner_info(
            session=session, user_id=uid, round_id=round_id
        )
        live_partner_ids = [
            p_user.user_id
            for pair, p_user in pairs_data
            if pair.status == PairStatus.ACTIVE
        ]
        contact_by_user_id = (
            await self.user_emails_repository.get_contact_emails_by_user_ids(
                session, live_partner_ids
            )
            if live_partner_ids
            else {}
        )

        for pair, p_user in pairs_data:
            partners.append(
                PartnerDto(
                    id=p_user.user_id,
                    preferred_name=p_user.preferred_name,
                    first_name=p_user.first_name,
                    last_name=p_user.last_name,
                    primary_email=contact_by_user_id.get(p_user.user_id),
                    participant_role=ParticipantRole.MENTEE
                    if pair.mentor_id == uid
                    else ParticipantRole.MENTOR,
                    recommendation_reason=pair.recommendation_reason,
                    is_active=pair.status == PairStatus.ACTIVE,
                )
            )

        return MatchesDto(
            round_id=round_id, current_status=current_status, partners=partners
        )

    async def get_program_feedback(
        self, session: AsyncSession, user_context: UserContextDto, round_id: int
    ) -> FeedbackDto:
        """
        Retrieve the current user's program feedback for a specific round.

        Args:
            session (AsyncSession): Active async database session.
            user_context (UserContextDto): Authenticated user context.
            round_id (int): The mentorship round ID.

        Returns:
            FeedbackDto: DTO containing participant role, submission state, and feedback data.

        Raises:
            ValueError: If the user has no participant record for this round.
        """

        self.logger.debug(
            "[ParticipationService] fetching program_feedback for user_id=%s, round_id=%s",
            user_context.user_id,
            round_id,
        )
        participant = (
            await self.mentorship_round_participants_repo.get_by_user_id_and_round_id(
                session=session, user_id=user_context.user_id, round_id=round_id
            )
        )
        if not participant:
            self.logger.error(
                "[ParticipationService] no participant record for user_id=%s, round_id=%s",
                user_context.user_id,
                round_id,
            )
            raise ValueError(
                f"No participant record found for current user, round_id={round_id}."
            )

        role = (
            participant.participant_role.value if participant.participant_role else None
        )
        raw = participant.program_feedback
        existing = raw if isinstance(raw, dict) else {}
        has_submitted = isinstance(raw, dict)
        partner_feedback_raw = participant.pair_feedback
        partner_feedback = (
            partner_feedback_raw if isinstance(partner_feedback_raw, list) else []
        )
        self.logger.debug(
            "[ParticipationService] program_feedback retrieved for user_id=%s, round_id=%s, has_submitted=%s",
            user_context.user_id,
            round_id,
            has_submitted,
        )

        return FeedbackDto(
            participant_role=role,
            has_submitted=has_submitted,
            most_valuable_aspects=existing.get("most_valuable_aspects"),
            challenges=existing.get("challenges"),
            program_rating=existing.get("program_rating"),
            partner_feedback=partner_feedback,
        )

    async def _feedback_closes_at(
        self, session: AsyncSession, round_id: int
    ) -> datetime | None:
        """
        Resolve the moment feedback stops being editable for a round.

        `feedback_deadline_at` is optional in the round form, so it falls back to
        a month past the (required) meetings deadline -- the same rule the
        dashboard uses to decide when to stop offering the form. A round with
        neither date configured has no cutoff at all rather than an immediate
        one, so a half-filled timeline cannot lock participants out.

        Args:
            session (AsyncSession): Active async database session.
            round_id (int): The mentorship round ID.

        Returns:
            datetime | None: The UTC cutoff, or None when the round sets no dates.
        """
        round_entity = await self.mentorship_round_repository.get_by_round_id(
            session, round_id
        )
        timeline = getattr(round_entity, "description", None) or {}

        raw = timeline.get("feedback_deadline_at")
        offset = relativedelta()
        if not raw:
            raw = timeline.get("meetings_completion_deadline_at")
            offset = relativedelta(months=1)
        if not raw:
            return None

        closes_at = isoparse(raw) + offset
        # Timelines predating timezone-aware storage are recorded in UTC.
        if closes_at.tzinfo is None:
            closes_at = closes_at.replace(tzinfo=timezone.utc)
        return closes_at

    async def _assert_feedback_open(self, session: AsyncSession, round_id: int) -> None:
        """
        Reject writes once the round's feedback window has closed.

        Args:
            session (AsyncSession): Active async database session.
            round_id (int): The mentorship round ID.

        Raises:
            ValueError: If the round's feedback window has already closed.
        """
        closes_at = await self._feedback_closes_at(session=session, round_id=round_id)
        if closes_at and datetime.now(timezone.utc) > closes_at:
            self.logger.warning(
                "[ParticipationService] feedback window closed for round_id=%s, closed_at=%s",
                round_id,
                closes_at.isoformat(),
            )
            raise ValueError("The feedback deadline for this round has passed.")

    async def upsert_program_feedback(
        self,
        session: AsyncSession,
        user_context: UserContextDto,
        round_id: int,
        feedback_data: FeedbackCreateDto,
    ) -> FeedbackDto:
        """
        Save or overwrite the current user's program feedback for a specific round,
        then recompute the round's average score for the participant's role.

        Answers stay editable for as long as the round's feedback window is open,
        so this is a plain overwrite rather than a one-shot submission.

        Args:
            session (AsyncSession): Active async database session.
            user_context (UserContextDto): Authenticated user context.
            round_id (int): The mentorship round ID.
            feedback_data (FeedbackCreateDto): The feedback payload to persist.

        Returns:
            FeedbackDto: The saved feedback DTO.

        Raises:
            ValueError: If the user has no participant record for this round, or
                if the round's feedback window has already closed.
        """

        self.logger.debug(
            "[ParticipationService] upserting program_feedback for user_id=%s, round_id=%s",
            user_context.user_id,
            round_id,
        )
        participant = (
            await self.mentorship_round_participants_repo.get_by_user_id_and_round_id(
                session=session, user_id=user_context.user_id, round_id=round_id
            )
        )
        if not participant:
            self.logger.error(
                "[ParticipationService] no participant record for user_id=%s, round_id=%s",
                user_context.user_id,
                round_id,
            )
            raise ValueError(
                f"No participant record found for user_id={user_context.user_id}, round_id={round_id}."
            )

        await self._assert_feedback_open(session=session, round_id=round_id)

        feedback_dump = feedback_data.model_dump(
            mode="json", by_alias=False, exclude_unset=False
        )
        partner_feedback = feedback_dump.pop("partner_feedback")

        participant.program_feedback = feedback_dump
        participant.pair_feedback = partner_feedback
        await self.mentorship_round_participants_repo.upsert_participant(
            session=session, entity=participant
        )

        await self._update_round_average_score(
            session=session, round_id=round_id, role=participant.participant_role
        )

        await session.commit()
        self.logger.info(
            "[ParticipationService] program_feedback saved for user_id=%s, round_id=%s",
            user_context.user_id,
            round_id,
        )

        role = (
            participant.participant_role.value if participant.participant_role else None
        )
        return FeedbackDto(
            participant_role=role,
            has_submitted=True,
            partner_feedback=partner_feedback,
            **feedback_dump,
        )

    async def _update_round_average_score(
        self,
        session: AsyncSession,
        round_id: int,
        role: ParticipantRole,
    ) -> None:
        """
        Recompute and persist the average program_rating for all participants of a given role in a round.

        Args:
            session (AsyncSession): Active async database session.
            round_id (int): The mentorship round ID.
            role (ParticipantRole): Determines which average score column to update.
        """
        avg = await self.mentorship_round_participants_repo.get_average_program_rating_by_round_and_role(
            session=session, round_id=round_id, role=role
        )
        if role == ParticipantRole.MENTEE:
            await self.mentorship_round_repository.update_mentee_average_score(
                session=session, round_id=round_id, value=avg
            )
        else:
            await self.mentorship_round_repository.update_mentor_average_score(
                session=session, round_id=round_id, value=avg
            )
        self.logger.debug(
            "[ParticipationService] updated %s_average_score=%.2f for round_id=%s",
            role.value,
            avg if avg is not None else 0,
            round_id,
        )
