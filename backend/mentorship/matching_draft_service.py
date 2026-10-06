"""Edits to a round's matching result: one admin at a time, saved as a draft.

The read side lays the draft over the matcher's result; this side only takes the
edit lock and writes the draft.
"""

from datetime import datetime, timedelta, timezone

from backend.common.exceptions import ConflictError
from backend.common.name_utils import user_display_name
from backend.mentorship.matching_draft import (
    DraftEntry,
    allowed_mentors,
    is_matchers_choice,
)


class MatchingDraftService:
    """Takes and releases a run's edit lock and saves its draft."""

    def __init__(self, matching_storage, users_repository, logger):
        """
        Args:
            matching_storage: Where the run, its draft and its lock live.
            users_repository: Names the admin holding the lock.
            logger: Injected logger.
        """
        self.matching_storage = matching_storage
        self.users_repository = users_repository
        self.logger = logger

    def _editable_run(self, round_id: int) -> tuple[str, dict]:
        """The round's run and its result, if it is one that can be edited.

        Raises:
            ValueError: The round has no run, or its run has not succeeded.
        """
        run_id = self.matching_storage.current_run_id(round_id)
        reported = (
            self.matching_storage.read_run_result(run_id)
            if run_id is not None
            else None
        )
        if reported is None or reported.status != "succeeded":
            raise ValueError(f"Round {round_id} has no matching result to edit.")
        return run_id, self.matching_storage.read_all_results(run_id)

    async def _holder_name(self, session, user_id: str) -> str | None:
        people = await self.users_repository.get_all_by_ids(session, [int(user_id)])
        if not people:
            return None
        person = people[0]
        return user_display_name(
            first_name=person.first_name,
            last_name=person.last_name,
            preferred_name=person.preferred_name,
        )

    async def take_lock(self, session, round_id: int, user_id: int) -> dict:
        """Take the round's run for editing, or renew the lock already held.

        Args:
            session (AsyncSession): The active async database session.
            round_id (int): Round whose run is edited.
            user_id (int): The admin asking.

        Returns:
            dict: ``user_id``, ``name`` and ``expires_at`` of the lock.

        Raises:
            ValueError: No result to edit.
            ConflictError: Another admin holds the lock.
        """
        run_id, _ = self._editable_run(round_id)
        me = str(user_id)
        if not self.matching_storage.take_edit_lock(run_id, me):
            held = self.matching_storage.edit_lock(run_id)
            holder = held[0] if held else None
            name = await self._holder_name(session, holder) if holder else None
            raise ConflictError(f"Being edited by {name or f'user {holder}'}.")
        _, seconds = self.matching_storage.edit_lock(run_id) or (me, 0)
        return {
            "user_id": me,
            "name": await self._holder_name(session, me),
            "expires_at": (
                datetime.now(timezone.utc) + timedelta(seconds=seconds)
            ).isoformat(timespec="seconds"),
        }

    def release_lock(self, round_id: int, user_id: int) -> None:
        """Give the lock back if this admin holds it; nothing otherwise."""
        run_id = self.matching_storage.current_run_id(round_id)
        if run_id is not None:
            self.matching_storage.release_edit_lock(run_id, str(user_id))

    def save_changes(self, round_id: int, user_id: int, changes) -> dict:
        """Write an editing session's changes into the draft and release the lock.

        A change that leaves a mentee exactly as the matcher had them removes
        that mentee from the draft. A mentee may only be given one of her
        candidates, the matcher's choice, or nobody.

        Args:
            round_id (int): Round whose run is edited.
            user_id (int): The admin saving.
            changes: Each with ``mentee_id``, ``mentor_id`` (None for nobody)
                and ``recommendation_reason``.

        Returns:
            dict: ``draft_count``, how many mentees the draft now changes.

        Raises:
            ValueError: No result to edit, an unknown mentee, or a mentor the
                mentee may not be given.
            ConflictError: The admin does not hold the lock.
        """
        run_id, results = self._editable_run(round_id)
        me = str(user_id)
        held = self.matching_storage.edit_lock(run_id)
        if held is None or held[0] != me:
            raise ConflictError(
                "Your editing lock has ended; open the result for editing again."
            )

        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        entries: dict[str, DraftEntry] = {}
        removed: list[str] = []
        for change in changes:
            result = results.get(change.mentee_id)
            if result is None:
                raise ValueError(f"Mentee {change.mentee_id} is not in this run.")
            if change.mentor_id not in allowed_mentors(result):
                raise ValueError(
                    f"Mentor {change.mentor_id} is not a candidate for mentee "
                    f"{change.mentee_id}."
                )
            if is_matchers_choice(
                result, change.mentor_id, change.recommendation_reason
            ):
                removed.append(change.mentee_id)
            else:
                entries[change.mentee_id] = DraftEntry(
                    mentor_id=change.mentor_id,
                    recommendation_reason=change.recommendation_reason,
                    edited_by=me,
                    edited_at=now,
                )

        self.matching_storage.write_draft(run_id, entries, removed)
        self.matching_storage.release_edit_lock(run_id, me)
        self.logger.info(
            "[MatchingDraftService] run=%s user=%s set=%d removed=%d",
            run_id,
            me,
            len(entries),
            len(removed),
        )
        return {"draft_count": len(self.matching_storage.read_draft(run_id))}
