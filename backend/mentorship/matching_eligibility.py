"""Who may go into a round's matching pool, decided from what is on record.

One person is checked against one round. The checks that only an approval can
lift -- no show, red flag -- and the exemption that lifts the history check
arrive with the approval work; until then nobody carries them, so a person's
history is read from every earlier round they were paired in.

History is the person's, not a role's: being short of meetings as a mentee
last round counts against registering as a mentor this round.
"""

from dataclasses import dataclass
from enum import StrEnum


class IneligibleReason(StrEnum):
    """Why someone is not in the matching pool."""

    BLOCKED = "blocked"
    DEACTIVATED = "deactivated"
    NOT_TAKING_PART = "not_taking_part"
    TRAINING_NOT_DONE = "training_not_done"
    NO_OPEN_SLOTS = "no_open_slots"
    # The two below are history problems, the ones an exemption will lift.
    QUIT_AFTER_MATCH = "quit_after_match"
    MEETINGS_SHORT = "meetings_short"


@dataclass(frozen=True)
class Candidate:
    """A person registered for the round being matched."""

    user_id: int
    is_blocked: bool
    is_active: bool
    # signed_up, matched or un_matched this round.
    is_taking_part: bool
    # The onboarding course for their role in this round is done now.
    training_done: bool
    open_slots: int


@dataclass(frozen=True)
class PastPair:
    mentor_id: int
    mentee_id: int
    is_active: bool
    completed_count: int


@dataclass(frozen=True)
class PastRound:
    """An earlier round as far as the people being checked are concerned.

    ``pairs`` holds every pair of those people in the round and every pair of
    their mentees, so a mentee's meetings can be added up across a change of
    mentor. ``quitters`` are the people whose status in the round says they
    left it.
    """

    required_meetings: int
    pairs: tuple[PastPair, ...]
    quitters: frozenset[int]


def history_problems(
    user_id: int, past_rounds: list[PastRound]
) -> list[IneligibleReason]:
    """What the person's latest paired round holds against them.

    Only the latest earlier round in which they had a pair counts: a round
    they left before being matched, or were not matched in, neither counts
    against them nor clears an earlier one.

    In that round:

    - Quitting after being matched counts. A pair ended by the partner
      quitting, or by an admin changing partners, counts against neither.
    - A mentee's meetings are her total over all her pairs that round, ended
      ones included, so a change of mentor does not cost her the meetings
      held before it. She is short when a pair of hers ran to the end and the
      total is under the round's requirement.
    - A mentor is short when any mentee of his whose pair with him ran to the
      end is short by that same total, even if he took her over midway.

    Args:
        user_id (int): The person.
        past_rounds (list[PastRound]): Earlier rounds, latest first.

    Returns:
        list[IneligibleReason]: History reasons, empty when there are none.
    """
    for past in past_rounds:
        own = [p for p in past.pairs if user_id in (p.mentor_id, p.mentee_id)]
        if not own:
            continue

        reasons: list[IneligibleReason] = []
        if user_id in past.quitters and not any(p.is_active for p in own):
            reasons.append(IneligibleReason.QUIT_AFTER_MATCH)

        def mentee_short(mentee_id: int) -> bool:
            total = sum(
                p.completed_count or 0 for p in past.pairs if p.mentee_id == mentee_id
            )
            return total < past.required_meetings

        mentees_who_ran_to_end = {p.mentee_id for p in own if p.is_active}
        if any(mentee_short(m) for m in mentees_who_ran_to_end):
            reasons.append(IneligibleReason.MEETINGS_SHORT)
        return reasons
    return []


def ineligible_reasons(
    candidate: Candidate, past_rounds: list[PastRound]
) -> list[IneligibleReason]:
    """Every reason the candidate is not in the matching pool.

    Args:
        candidate (Candidate): The person and where they stand this round.
        past_rounds (list[PastRound]): Earlier rounds, latest first.

    Returns:
        list[IneligibleReason]: Empty when the candidate is eligible.
    """
    reasons: list[IneligibleReason] = []
    if candidate.is_blocked:
        reasons.append(IneligibleReason.BLOCKED)
    if not candidate.is_active:
        reasons.append(IneligibleReason.DEACTIVATED)
    if not candidate.is_taking_part:
        reasons.append(IneligibleReason.NOT_TAKING_PART)
    if not candidate.training_done:
        reasons.append(IneligibleReason.TRAINING_NOT_DONE)
    if candidate.open_slots < 1:
        reasons.append(IneligibleReason.NO_OPEN_SLOTS)
    reasons.extend(history_problems(candidate.user_id, past_rounds))
    return reasons
