"""An admin's edits to a matching run's result, laid over what the matcher wrote.

The matcher's result is never changed. The draft holds only the mentees an admin
changed, so going back to the matcher's choice is deleting an entry, and every
reader -- the review page, the problems list, publishing later -- sees the same
matcher result with the same draft on top.
"""

from dataclasses import dataclass

from pydantic import BaseModel, ConfigDict

from backend.mentorship.matching_contract import MenteeResult

REASON_LIMIT = 300


class DraftEntry(BaseModel):
    """One mentee as an admin left them. ``mentor_id`` None means no mentor."""

    model_config = ConfigDict(extra="forbid")

    mentor_id: str | None = None
    recommendation_reason: str = ""
    edited_by: str
    edited_at: str


@dataclass(frozen=True)
class EffectiveRow:
    """A mentee's outcome once the draft is applied."""

    mentor_id: str | None
    recommendation_reason: str
    # The chosen mentor's score: the matcher's own when unchanged, the
    # candidate's when moved to one, None with no mentor.
    score: int | None
    edited: bool
    result: MenteeResult  # the matcher's, unchanged


def apply_draft(results: dict, draft: dict[str, DraftEntry]) -> dict[str, EffectiveRow]:
    """Every mentee's outcome with the draft laid over the matcher's result.

    Args:
        results (dict[str, MenteeResult]): The matcher's result by mentee id.
        draft (dict[str, DraftEntry]): The saved draft by mentee id. Entries for
            mentees the run does not hold are ignored.

    Returns:
        dict[str, EffectiveRow]: By mentee id, one per mentee in ``results``.
    """
    rows: dict[str, EffectiveRow] = {}
    for mentee_id, result in results.items():
        entry = draft.get(mentee_id)
        if entry is None:
            rows[mentee_id] = EffectiveRow(
                mentor_id=result.mentor_id,
                recommendation_reason=result.recommendation_reason,
                score=result.score,
                edited=False,
                result=result,
            )
            continue
        rows[mentee_id] = EffectiveRow(
            mentor_id=entry.mentor_id,
            recommendation_reason=entry.recommendation_reason,
            score=_score_of(result, entry.mentor_id),
            edited=True,
            result=result,
        )
    return rows


def _score_of(result, mentor_id: str | None) -> int | None:
    if mentor_id is None:
        return None
    if mentor_id == result.mentor_id:
        return result.score
    return next((c.score for c in result.candidates if c.mentor_id == mentor_id), None)


def allowed_mentors(result) -> set[str | None]:
    """Who a mentee may be given: nobody, the matcher's choice, a candidate."""
    return {None, result.mentor_id, *(c.mentor_id for c in result.candidates)}


def is_matchers_choice(result, mentor_id: str | None, reason: str) -> bool:
    """Whether an edit leaves the mentee exactly as the matcher had them."""
    return mentor_id == result.mentor_id and reason == result.recommendation_reason


def assigned_counts(rows: dict[str, EffectiveRow]) -> dict[str, int]:
    """How many mentees each mentor is given, draft included."""
    counts: dict[str, int] = {}
    for row in rows.values():
        if row.mentor_id is not None:
            counts[row.mentor_id] = counts.get(row.mentor_id, 0) + 1
    return counts


def problems(rows: dict[str, EffectiveRow], slots: dict[str, int]) -> list[dict]:
    """What has to be fixed before the result can be published.

    Args:
        rows (dict[str, EffectiveRow]): Every mentee, draft applied.
        slots (dict[str, int]): Each mentor's slots in this run.

    Returns:
        list[dict]: ``{"code", ...ids}`` entries: mentors over their slots in
            mentor id order, then per mentee (in mentee id order) a reason over
            the limit or a matched mentee with no reason.
    """
    found: list[dict] = []
    counts = assigned_counts(rows)
    for mentor_id in sorted(counts, key=user_id_order):
        if counts[mentor_id] > slots.get(mentor_id, 1):
            found.append({
                "code": "over_slots",
                "mentor_id": mentor_id,
                "assigned": counts[mentor_id],
                "slots": slots.get(mentor_id, 1),
            })
    for mentee_id in sorted(rows, key=user_id_order):
        row = rows[mentee_id]
        if row.mentor_id is None:
            continue
        if len(row.recommendation_reason) > REASON_LIMIT:
            found.append({"code": "reason_too_long", "mentee_id": mentee_id})
        elif not row.recommendation_reason.strip():
            found.append({"code": "no_reason", "mentee_id": mentee_id})
    return found


def user_id_order(user_id: str) -> tuple:
    """Numeric ids in number order, anything else after them."""
    return (0, int(user_id), "") if user_id.isdigit() else (1, 0, user_id)
