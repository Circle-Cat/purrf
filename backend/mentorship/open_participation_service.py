"""The mentorship rounds that still hold someone.

An account cannot be deactivated while its owner is still in a round under
way: the mentorship admins withdraw them first, through the usual approval,
so a partner is never left paired with someone who has gone. Reads only.
"""

from datetime import datetime, timezone

from backend.common.mentorship_enums import ApprovalStatus, PairStatus
from backend.dto.block_dto import OpenMentorshipRoundDto
from backend.mentorship.exempt_matching_handler import exemption_target
from backend.mentorship.round_windows import in_progress_ends_at, is_in_progress
from backend.mentorship.withdraw_participant_handler import WITHDRAW_PARTICIPANT

# A registration in one of these is still in its round. Withdrawn and rejected
# are done with it.
_STILL_IN = frozenset({
    ApprovalStatus.SIGNED_UP,
    ApprovalStatus.MATCHED,
    ApprovalStatus.UN_MATCHED,
})


class OpenParticipationService:
    """Names the rounds under way a person is still in."""

    def __init__(
        self, participants_repository, pairs_repository, approval_service, logger
    ):
        """
        Args:
            participants_repository: The person's rounds and registrations.
            pairs_repository: Their pairs in each round.
            approval_service (ApprovalService): Pending withdrawal requests.
            logger: Injected logger.
        """
        self.participants_repository = participants_repository
        self.pairs_repository = pairs_repository
        self.approval_service = approval_service
        self.logger = logger

    async def list_open(self, session, user_id: int) -> list[OpenMentorshipRoundDto]:
        """Every round under way the person is still in, latest first.

        Args:
            session (AsyncSession): Active database async session.
            user_id (int): The person.

        Returns:
            list[OpenMentorshipRoundDto]: Empty when nothing holds them.
        """
        now = datetime.now(timezone.utc)
        rounds = (
            await self.participants_repository.list_registered_rounds_by_user_ids(
                session, [user_id]
            )
        ).get(user_id, [])
        found = []
        for round_ in rounds:
            if not is_in_progress(round_, now):
                continue
            participant = (
                await self.participants_repository.get_by_user_id_and_round_id(
                    session, user_id, round_.round_id
                )
            )
            if participant is None or participant.approval_status not in _STILL_IN:
                continue
            pairs = await self.pairs_repository.get_pairs_by_user_and_round(
                session=session, user_id=user_id, round_id=round_.round_id
            )
            found.append((round_, participant, pairs))
        if not found:
            return []

        targets = [exemption_target(round_.round_id, user_id) for round_, _, _ in found]
        pending = await self.approval_service.list_pending_for_targets(
            session, WITHDRAW_PARTICIPANT, targets
        )
        return [
            OpenMentorshipRoundDto(
                round_id=round_.round_id,
                round_name=round_.name,
                role=(
                    participant.participant_role.value
                    if participant.participant_role is not None
                    else None
                ),
                pair_count=sum(1 for pair in pairs if pair.status == PairStatus.ACTIVE),
                withdraw_pending=target in pending,
                ends_at=in_progress_ends_at(round_),
            )
            for (round_, participant, pairs), target in zip(found, targets)
        ]
