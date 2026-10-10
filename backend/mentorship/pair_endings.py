"""What ending a pair does to the people in it, shared by every way a pair
ends: someone left with no active pair in the round is no longer matched."""

from backend.common.mentorship_enums import ApprovalStatus, PairStatus


async def unmatch_if_unpaired(
    session,
    *,
    participants_repository,
    pairs_repository,
    round_id: int,
    user_ids,
) -> set[int]:
    """Move each of these people from matched to un_matched when they have no
    active pair left in the round. Call it after the ended pairs are flushed.
    Does not flush, commit or write notes.

    Args:
        session (AsyncSession): The caller's open session.
        participants_repository: Reads and changes the registrations.
        pairs_repository: Reads each person's pairs in the round.
        round_id (int): The round.
        user_ids (Iterable[int]): Who to look at.

    Returns:
        set[int]: The people moved.
    """
    moved: set[int] = set()
    for user_id in dict.fromkeys(user_ids):
        pairs = await pairs_repository.get_pairs_by_user_and_round(
            session=session, user_id=user_id, round_id=round_id
        )
        if any(pair.status == PairStatus.ACTIVE for pair in pairs):
            continue
        participant = await participants_repository.get_by_user_id_and_round_id(
            session, user_id, round_id
        )
        if participant is None or participant.approval_status != ApprovalStatus.MATCHED:
            continue
        participant.approval_status = ApprovalStatus.UN_MATCHED
        moved.add(user_id)
    return moved
