from sqlalchemy.ext.asyncio import AsyncSession
from backend.dto.participant_search_filter_dto import ParticipantSearchFilterDto
from backend.dto.participant_search_dto import ParticipantRowDto, ParticipantSearchDto
from backend.dto.partner_dto import PartnerDto
from backend.common.mentorship_enums import (
    ParticipantRole,
    TrainingCategory,
    TrainingStatus,
)


class MentorshipAdminService:
    """Service for admin-facing mentorship participant search."""

    def __init__(
        self,
        users_repository,
        participants_repository,
        rounds_repository,
        training_repository,
    ) -> None:
        self.users_repository = users_repository
        self.participants_repository = participants_repository
        self.rounds_repository = rounds_repository
        self.training_repository = training_repository

    _ROLE_ONBOARDING_CATEGORY: dict[ParticipantRole, TrainingCategory] = {
        ParticipantRole.MENTOR: TrainingCategory.MENTORSHIP_MENTOR_ONBOARDING,
        ParticipantRole.MENTEE: TrainingCategory.MENTORSHIP_MENTEE_ONBOARDING,
    }

    @staticmethod
    def _derive_onboarding_status(role: ParticipantRole, user_trainings: list) -> str:
        required = MentorshipAdminService._ROLE_ONBOARDING_CATEGORY[role]
        return (
            "completed"
            if any(
                t.category == required and t.status == TrainingStatus.DONE
                for t in user_trainings
            )
            else "incomplete"
        )

    async def search_participants(
        self,
        session: AsyncSession,
        filters: ParticipantSearchFilterDto,
        limit: int = 100,
        offset: int = 0,
    ) -> ParticipantSearchDto:
        """
        Search mentorship participants for admin with pagination.

        Executes the main participant query, batch-fetches user/email/round/training
        data, and assembles each row into a ParticipantRowDto. If onboarding_status
        is specified, it is applied after assembly on the already-paginated result set.
        This means total always reflects the repository count before onboarding_status
        filtering.

        Args:
            session (AsyncSession): Active database async session.
            filters (ParticipantSearchFilterDto): Filter criteria from the request.
            limit (int): Maximum number of rows to return. Defaults to 100.
            offset (int): Number of rows to skip for pagination. Defaults to 0.

        Returns:
            ParticipantSearchDto: Assembled participant rows and total count.
        """
        rows, total = await self.participants_repository.search_participants_for_admin(
            session, filters, limit, offset
        )
        if not rows:
            return ParticipantSearchDto(participant_rows=[], total=total)

        all_user_ids = set()
        participant_user_ids = set()
        for row in rows:
            all_user_ids.add(row.user_id)
            if row.mentor_id is not None:
                all_user_ids.add(row.mentor_id)
            if row.mentee_id is not None:
                all_user_ids.add(row.mentee_id)
            participant_user_ids.add(row.user_id)

        users_map, emails_map = await self.users_repository.get_users_and_emails_by_ids(
            session, all_user_ids
        )

        rounds = await self.rounds_repository.get_all_rounds(session)
        rounds_map = {r.round_id: r for r in rounds}

        trainings_map = await self.training_repository.get_training_by_user_ids(
            session, participant_user_ids
        )

        participant_rows: list[ParticipantRowDto] = []
        for row in rows:
            user = users_map[row.user_id]
            user_emails = emails_map.get(row.user_id, [])
            primary_email = next((e.email for e in user_emails if e.is_primary), None)
            alternative_emails = [e.email for e in user_emails if not e.is_primary]

            matched_user = None
            if row.mentor_id is not None and row.mentee_id is not None:
                if row.user_id == row.mentor_id:
                    partner_id = row.mentee_id
                else:
                    partner_id = row.mentor_id
                partner = users_map.get(partner_id)
                if partner:
                    matched_user = PartnerDto(
                        id=partner.user_id,
                        first_name=partner.first_name or "",
                        last_name=partner.last_name or "",
                        preferred_name=partner.preferred_name or "",
                        primary_email=None,
                        participant_role=None,
                        recommendation_reason=None,
                    )

            round_entity = rounds_map.get(row.round_id) if row.round_id else None

            participant_rows.append(
                ParticipantRowDto(
                    user_id=row.user_id,
                    round_id=row.round_id,
                    round_name=round_entity.name if round_entity else None,
                    pair_id=row.pair_id,
                    first_name=user.first_name,
                    last_name=user.last_name,
                    preferred_name=user.preferred_name,
                    primary_email=primary_email,
                    alternative_emails=alternative_emails,
                    matched_user=matched_user,
                    participant_role=row.participant_role,
                    approval_status=row.approval_status,
                    onboarding_status=(
                        self._derive_onboarding_status(
                            row.participant_role, trainings_map.get(row.user_id, [])
                        )
                        if row.participant_role is not None
                        else None
                    ),
                    completed_meeting_count=row.completed_count,
                    required_meetings=(
                        round_entity.required_meetings if round_entity else None
                    ),
                )
            )

        if filters.onboarding_status:
            participant_rows = [
                r
                for r in participant_rows
                if r.onboarding_status == filters.onboarding_status
            ]

        return ParticipantSearchDto(participant_rows=participant_rows, total=total)
