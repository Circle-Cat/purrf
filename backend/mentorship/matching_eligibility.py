"""Who may go into a round's matching pool, decided from what is on record.

One person is checked against one round. A matching exemption, granted for a
person in a round through an approval, lifts the history check in that round
and clears everything before it: in later rounds only the round it was
granted in and the rounds after count.

No show and red flag are marks given through an approval. They are timed,
not counted by round: a mark counts only when it was approved after the
person's latest exemption, so an exemption clears every mark before it and
none after it, in the same round too.

History is the person's, not a role's: being short of meetings as a mentee
last round counts against registering as a mentor this round.
"""

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum


class IneligibleReason(StrEnum):
    """Why someone is not in the matching pool."""

    BLOCKED = "blocked"
    DEACTIVATED = "deactivated"
    NOT_TAKING_PART = "not_taking_part"
    TRAINING_NOT_DONE = "training_not_done"
    NO_OPEN_SLOTS = "no_open_slots"
    # The four below are history problems, the ones an exemption will lift.
    QUIT_AFTER_MATCH = "quit_after_match"
    MEETINGS_SHORT = "meetings_short"
    NO_SHOW = "no_show"
    RED_FLAG = "red_flag"


# The reasons an exemption lifts. Someone whose every reason is one of these
# is waiting on an exemption and nothing else.
HISTORY_REASONS = frozenset({
    IneligibleReason.QUIT_AFTER_MATCH,
    IneligibleReason.MEETINGS_SHORT,
    IneligibleReason.NO_SHOW,
    IneligibleReason.RED_FLAG,
})


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
    # A matching exemption was granted for them in this round.
    exempt_this_round: bool = False


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
    round_id: int | None = None


@dataclass(frozen=True)
class HistoryFinding:
    """One history problem and the round it comes from. A shortfall carries
    the meetings held and required; for a mentor, those of his shortest
    mentee."""

    reason: IneligibleReason
    round_id: int | None
    completed: int | None = None
    required: int | None = None


@dataclass(frozen=True)
class Mark:
    """A no show or red flag given to the person, the round it was given in,
    and when its approval was written."""

    reason: IneligibleReason
    round_id: int
    created_at: datetime


def history_findings(
    user_id: int,
    past_rounds: list[PastRound],
    exempted_round_ids: frozenset[int] = frozenset(),
) -> list[HistoryFinding]:
    """What the person's latest paired round holds against them.

    Only the latest earlier round in which they had a pair counts: a round
    they left before being matched, or were not matched in, neither counts
    against them nor clears an earlier one. An exemption is the exception:
    nothing before the round it was granted in counts, whether or not they
    were paired in that round.

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
        exempted_round_ids (frozenset[int]): Earlier rounds an exemption was
            granted for them in.

    Returns:
        list[HistoryFinding]: History problems, empty when there are none.
    """
    for past in past_rounds:
        own = [p for p in past.pairs if user_id in (p.mentor_id, p.mentee_id)]
        if not own:
            if past.round_id in exempted_round_ids:
                return []
            continue

        found: list[HistoryFinding] = []
        if user_id in past.quitters and not any(p.is_active for p in own):
            found.append(
                HistoryFinding(IneligibleReason.QUIT_AFTER_MATCH, past.round_id)
            )

        def total_of(mentee_id: int) -> int:
            return sum(
                p.completed_count or 0 for p in past.pairs if p.mentee_id == mentee_id
            )

        mentees_who_ran_to_end = {p.mentee_id for p in own if p.is_active}
        short = [
            total_of(m)
            for m in mentees_who_ran_to_end
            if total_of(m) < past.required_meetings
        ]
        if short:
            found.append(
                HistoryFinding(
                    IneligibleReason.MEETINGS_SHORT,
                    past.round_id,
                    completed=min(short),
                    required=past.required_meetings,
                )
            )
        return found
    return []


def history_problems(
    user_id: int,
    past_rounds: list[PastRound],
    exempted_round_ids: frozenset[int] = frozenset(),
) -> list[IneligibleReason]:
    """The reasons of ``history_findings``, in the same order.

    Args:
        user_id (int): The person.
        past_rounds (list[PastRound]): Earlier rounds, latest first.
        exempted_round_ids (frozenset[int]): Earlier rounds an exemption was
            granted for them in.

    Returns:
        list[IneligibleReason]: History reasons, empty when there are none.
    """
    return [
        f.reason for f in history_findings(user_id, past_rounds, exempted_round_ids)
    ]


def mark_findings(
    user_id: int,
    round_id: int | None,
    past_rounds: list[PastRound],
    marks: Iterable[Mark],
    exempted_at: datetime | None = None,
) -> list[HistoryFinding]:
    """The person's marks that keep them out of matching in this round.

    Only marks written after their latest exemption count. A no show counts
    when it is from this round or from the latest earlier round in which they
    had a pair; a red flag counts from this round or any earlier one. Marks
    from any other round are not their history here. Several marks of one
    kind in one round are one finding.

    Args:
        user_id (int): The person.
        round_id (int | None): The round being matched.
        past_rounds (list[PastRound]): Earlier rounds, latest first.
        marks (Iterable[Mark]): Every mark the person carries.
        exempted_at (datetime | None): When their latest exemption was
            written, None if they never had one.

    Returns:
        list[HistoryFinding]: Oldest mark first, empty when none count.
    """
    latest_paired = next(
        (
            past.round_id
            for past in past_rounds
            if any(user_id in (p.mentor_id, p.mentee_id) for p in past.pairs)
        ),
        None,
    )
    counted = {
        IneligibleReason.NO_SHOW: {round_id, latest_paired} - {None},
        IneligibleReason.RED_FLAG: ({round_id} | {p.round_id for p in past_rounds})
        - {None},
    }
    found: list[HistoryFinding] = []
    for mark in sorted(marks, key=lambda m: m.created_at):
        if exempted_at is not None and mark.created_at <= exempted_at:
            continue
        if mark.round_id not in counted.get(mark.reason, set()):
            continue
        finding = HistoryFinding(mark.reason, mark.round_id)
        if finding not in found:
            found.append(finding)
    return found


def ineligible_reasons(
    candidate: Candidate,
    past_rounds: list[PastRound],
    exempted_round_ids: frozenset[int] = frozenset(),
    *,
    round_id: int | None = None,
    marks: Iterable[Mark] = (),
    exempted_at: datetime | None = None,
) -> list[IneligibleReason]:
    """Every reason the candidate is not in the matching pool.

    An exemption in this round lifts the history of earlier rounds; marks
    are judged by time, so one written after that exemption still counts.

    Args:
        candidate (Candidate): The person and where they stand this round.
        past_rounds (list[PastRound]): Earlier rounds, latest first.
        exempted_round_ids (frozenset[int]): Earlier rounds an exemption was
            granted for them in.
        round_id (int | None): The round being matched.
        marks (Iterable[Mark]): Every mark the person carries.
        exempted_at (datetime | None): When their latest exemption was
            written.

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
    if not candidate.exempt_this_round:
        reasons.extend(
            history_problems(candidate.user_id, past_rounds, exempted_round_ids)
        )
    for finding in mark_findings(
        candidate.user_id, round_id, past_rounds, marks, exempted_at
    ):
        if finding.reason not in reasons:
            reasons.append(finding.reason)
    return reasons
