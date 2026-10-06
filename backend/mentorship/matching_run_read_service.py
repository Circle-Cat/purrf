"""Reads a round's matching run back for review.

Nothing here writes. A run is found through the round's pointer rather than by
id, because the pointer is the only thing that outlives the review: an admin
comes back days later with a round in hand and nothing else.
"""

from datetime import datetime, timedelta, timezone

from backend.common.mentorship_enums import MatchingRunStatus
from backend.common.name_utils import user_display_name
from backend.mentorship.matching_draft import (
    apply_draft,
    assigned_counts,
    problems,
    user_id_order,
)


def _needs_attention(item) -> tuple:
    """Sort key placing the rows an admin has to act on at the top.

    The three outcomes rank before the score does, because a mutual choice
    carries no score at all: reading its absence as zero would sort the pairs
    needing least review in among the weakest ones. A mutual choice an admin
    has changed is no longer one.
    """
    mentee_id, row = item
    if row.mentor_id is None:
        return (0, 0, mentee_id)
    if row.result.match_type == "mutual_yes" and not row.edited:
        return (2, 0, mentee_id)
    return (1, -(row.score or 0), mentee_id)


def _ids_on(items) -> list[str]:
    """Every user id a page mentions: its mentees, their mentors as they stand
    and as the matcher chose, and the alternatives."""
    ids: list[str] = []
    for mentee_id, row in items:
        ids.append(mentee_id)
        ids.extend(
            user_id
            for user_id in (row.mentor_id, row.result.mentor_id)
            if user_id is not None
        )
        ids.extend(candidate.mentor_id for candidate in row.result.candidates)
    return ids


def _candidates(result, names: dict[str, str]) -> list[dict]:
    return [
        {
            "user_id": candidate.mentor_id,
            "name": names.get(candidate.mentor_id),
            "score": candidate.score,
        }
        for candidate in result.candidates
    ]


def _named(user_id: str | None, names: dict[str, str]) -> dict | None:
    return None if user_id is None else {"user_id": user_id, "name": names.get(user_id)}


def _partner_ids_on(records) -> list[str]:
    """Every id the given people asked to be, or not to be, paired with."""
    return [
        user_id
        for record in records
        for user_id in (*record.expected_partner_ids, *record.unexpected_partner_ids)
    ]


def _profile(record, names: dict[str, str]) -> dict | None:
    """A person as the matcher saw them, with partner ids named.

    Everything the run was given about them, less what the row says already
    (name, role) and with the two partner lists carrying names beside ids.
    """
    if record is None:
        return None

    def named(ids):
        return [{"user_id": user_id, "name": names.get(user_id)} for user_id in ids]

    return {
        **record.model_dump(
            exclude={
                "role",
                "display_name",
                "expected_partner_ids",
                "unexpected_partner_ids",
            }
        ),
        "expected_partners": named(record.expected_partner_ids),
        "unexpected_partners": named(record.unexpected_partner_ids),
    }


class MatchingRunReadService:
    """Answers what state a round's run is in, and what it produced."""

    def __init__(
        self,
        matching_storage,
        users_repository,
        logger,
    ):
        """
        Args:
            matching_storage: Where a run's input, result and draft live.
            users_repository: Resolves the ids a result is written in.
            logger: Injected logger.
        """
        self.matching_storage = matching_storage
        self.users_repository = users_repository
        self.logger = logger

    async def _name_map(self, session, user_ids) -> dict[str, str]:
        """Resolve a page's worth of ids to display names in one query.

        The contract writes ids as strings and the database keys them as
        integers, so one that is not a number belongs to neither and is left
        out of the query rather than allowed to fail it.

        Args:
            session (AsyncSession): The active async database session.
            user_ids (Iterable[str]): Ids as the result carries them, in any
                order and with repeats.

        Returns:
            dict[str, str]: Name by id, as strings, holding only the ids that
                resolved.
        """
        numeric = []
        for user_id in dict.fromkeys(user_ids):
            try:
                numeric.append(int(user_id))
            except (TypeError, ValueError):
                self.logger.warning("Result carries an id that is not one: %s", user_id)

        people = await self.users_repository.get_all_by_ids(session, numeric)
        return {
            str(person.user_id): user_display_name(
                first_name=person.first_name,
                last_name=person.last_name,
                preferred_name=person.preferred_name,
            )
            for person in people
        }

    def _read_run(self, round_id: int) -> tuple[dict, dict | None]:
        """Find the round's run and read as far as its state allows.

        Both endpoints start here, so they cannot disagree about what state a
        round is in. The result is read only once it is worth reading: a run
        still going, or one that failed, never touches the result hash.

        Args:
            round_id (int): Round whose run is wanted.

        Returns:
            tuple[dict, dict | None]: What is known about the run as a whole,
                and every mentee's outcome when there is one to read.
        """
        run_id = self.matching_storage.current_run_id(round_id)
        if run_id is None:
            return {"status": MatchingRunStatus.NEVER_RUN}, None

        meta = self.matching_storage.read_meta(run_id)
        if meta is None:
            # The pointer outlives nothing else: both expire together at three
            # months, so an envelope that is gone means the run is gone.
            return {"status": MatchingRunStatus.NEVER_RUN}, None

        started = {
            "run_id": run_id,
            "started_at": meta.generated_at,
            "triggered_by_user_id": meta.triggered_by_user_id,
            "mentor_count": self.matching_storage.mentor_count(run_id),
            "mentee_count": self.matching_storage.mentee_count(run_id),
        }

        try:
            reported = self.matching_storage.read_run_result(run_id)
        except ValueError as incomplete:
            # Not raised onward. A result that does not hold one row per mentee
            # is this run's own outcome, and the admin who waited an hour needs
            # to see which count disagreed rather than a failed request.
            self.logger.warning("Run %s cannot be reviewed: %s", run_id, incomplete)
            return {
                **started,
                "status": MatchingRunStatus.UNUSABLE,
                "error": str(incomplete),
            }, None

        if reported is None:
            return {**started, "status": MatchingRunStatus.RUNNING}, None

        # Once the matcher has reported, its own clock owns both ends. The
        # envelope's timestamp is when Purrf wrote the input, which is not
        # when the job began -- on a run whose input was seeded by hand the
        # two were nineteen hours apart for work that took thirty-four
        # seconds, and anybody subtracting one from the other would have
        # believed it. It stays, under a name that says what it is.
        finished = {
            **started,
            "input_written_at": started["started_at"],
            "started_at": reported.started_at,
            "finished_at": reported.finished_at,
            "matcher_version": reported.matcher_version,
            "run_date": reported.run_date,
        }
        if reported.status == "failed":
            return {
                **finished,
                "status": MatchingRunStatus.FAILED,
                "error": reported.error,
            }, None

        # Only this branch reads the whole result. A round being polled while it
        # runs never reaches here, and by the time it does nobody is polling.
        results = self.matching_storage.read_all_results(run_id)
        return {
            **finished,
            "status": MatchingRunStatus.SUCCEEDED,
            "mentee_count": reported.mentee_count,
        }, results

    def _rows(self, run_id: str, results: dict) -> dict:
        """Every mentee with the run's saved draft laid over the result."""
        return apply_draft(results, self.matching_storage.read_draft(run_id))

    async def read_overview(self, session, round_id: int) -> dict:
        """Describe the round's most recent run.

        Once it has succeeded, everything counted here -- who is matched, the
        mentors given nobody, each mentor's slots in use, the problems in the
        way of publishing -- includes the saved draft.

        Args:
            session (AsyncSession): The active async database session.
            round_id (int): Round whose run is wanted.

        Returns:
            dict: The run's status and what that status carries.
        """
        run, results = self._read_run(round_id)
        starter = run.get("triggered_by_user_id")
        if results is None:
            if starter is not None:
                names = await self._name_map(session, [starter])
                run = {**run, "triggered_by_name": names.get(starter)}
            return run

        run_id = run["run_id"]
        rows = self._rows(run_id, results)
        mentors = self.matching_storage.read_all_people(run_id, "mentor")
        slots = {
            mentor_id: record.max_partners or 1 for mentor_id, record in mentors.items()
        }
        counts = assigned_counts(rows)
        mentor_ids = sorted(mentors, key=user_id_order)
        unmatched = [m for m in mentor_ids if counts.get(m, 0) == 0]
        found = problems(rows, slots)
        lock = self.matching_storage.edit_lock(run_id)

        names = await self._name_map(
            session,
            ([starter] if starter is not None else [])
            + ([lock[0]] if lock else [])
            + mentor_ids
            + [p["mentee_id"] for p in found if "mentee_id" in p],
        )
        matched = sum(1 for row in rows.values() if row.mentor_id is not None)
        return {
            **run,
            "triggered_by_name": names.get(starter) if starter is not None else None,
            "matched_count": matched,
            "unmatched_count": len(rows) - matched,
            "unmatched_mentors": [_named(m, names) for m in unmatched],
            "edit_lock": None
            if lock is None
            else {
                "user_id": lock[0],
                "name": names.get(lock[0]),
                "expires_at": (
                    datetime.now(timezone.utc) + timedelta(seconds=lock[1])
                ).isoformat(timespec="seconds"),
            },
            "draft_count": sum(1 for row in rows.values() if row.edited),
            "mentor_slots": [
                {
                    **_named(m, names),
                    "slots": slots[m],
                    "assigned": counts.get(m, 0),
                }
                for m in mentor_ids
            ],
            "problems": [
                {
                    "code": p["code"],
                    "mentor": _named(p.get("mentor_id"), names),
                    "mentee": _named(p.get("mentee_id"), names),
                    "assigned": p.get("assigned"),
                    "slots": p.get("slots"),
                }
                for p in found
            ],
        }

    async def read_results(
        self,
        session,
        round_id: int,
        limit: int = 100,
        offset: int = 0,
        matched: bool | None = None,
    ) -> dict:
        """Return one page of the run's result.

        The whole result is sorted and sliced here rather than paged out of
        Redis. A hash has no order, so a cursor could not offer a page number, a
        filter, or a total -- and the three of them are what a review screen is.
        At a few thousand mentees the result is around a megabyte, well inside
        the size of a single Upstash request.

        Args:
            session (AsyncSession): The active async database session.
            round_id (int): Round whose run is wanted.
            limit (int): How many mentees to return.
            offset (int): How many to skip.
            matched (bool | None): Keep only the placed or only the unplaced;
                everybody when absent.

        Returns:
            dict: The run's status, the counts that describe the whole run, the
                number of rows the filter left, and the page itself.
        """
        run, results = self._read_run(round_id)
        page = {
            "status": run["status"],
            "matched_count": 0,
            "unmatched_count": 0,
            "total": 0,
            "items": [],
        }
        if results is None:
            return page

        run_id = run["run_id"]
        rows = self._rows(run_id, results)
        matched_count = sum(1 for row in rows.values() if row.mentor_id is not None)
        selected = [
            (mentee_id, row)
            for mentee_id, row in rows.items()
            if matched is None or (row.mentor_id is not None) is matched
        ]
        # Ordered by how much of a person's attention the row needs: nobody
        # found, then the scored ones, then the mutual choices that need none.
        # Ties break on mentee id so the same run always pages the same way.
        selected.sort(key=_needs_attention)
        items = selected[offset : offset + limit]

        mentees = self.matching_storage.read_people(
            run_id, "mentee", [mentee_id for mentee_id, _ in items]
        )
        mentors = self.matching_storage.read_people(
            run_id,
            "mentor",
            sorted(
                {row.mentor_id for _, row in items if row.mentor_id is not None},
                key=user_id_order,
            ),
        )
        names = await self._name_map(
            session,
            _ids_on(items) + _partner_ids_on([*mentees.values(), *mentors.values()]),
        )
        return {
            **page,
            "matched_count": matched_count,
            "unmatched_count": len(rows) - matched_count,
            "total": len(selected),
            "items": [
                self._item(
                    mentee_id,
                    row,
                    names,
                    mentee_profile=mentees.get(mentee_id),
                    mentor_profile=mentors.get(row.mentor_id),
                )
                for mentee_id, row in items
            ],
        }

    async def read_unmatched(
        self, session, round_id: int, limit: int = 100, offset: int = 0
    ) -> dict:
        """Return one page of the people the run left without a partner.

        One row per person rather than per mentee, so the mentors nobody was
        given sit in the same list as the mentees nobody was found for. Mentees
        come first, then mentors, each in user id order.

        Args:
            session (AsyncSession): The active async database session.
            round_id (int): Round whose run is wanted.
            limit (int): How many people to return.
            offset (int): How many to skip.

        Returns:
            dict: The run's status, how many people are unmatched, and the page.
        """
        run, results = self._read_run(round_id)
        page = {"status": run["status"], "total": 0, "items": []}
        if results is None:
            return page

        run_id = run["run_id"]
        rows = self._rows(run_id, results)
        counts = assigned_counts(rows)
        people = [
            ("mentee", mentee_id, rows[mentee_id])
            for mentee_id in sorted(rows, key=user_id_order)
            if rows[mentee_id].mentor_id is None
        ] + [
            ("mentor", mentor_id, None)
            for mentor_id in sorted(
                self.matching_storage.read_all_people(run_id, "mentor"),
                key=user_id_order,
            )
            if counts.get(mentor_id, 0) == 0
        ]
        page_people = people[offset : offset + limit]

        profiles = {
            role: self.matching_storage.read_people(
                run_id, role, [user_id for r, user_id, _ in page_people if r == role]
            )
            for role in ("mentee", "mentor")
        }
        names = await self._name_map(
            session,
            [user_id for _, user_id, _ in page_people]
            + [
                user_id
                for _, _, row in page_people
                if row is not None
                for user_id in (
                    row.result.mentor_id,
                    *(c.mentor_id for c in row.result.candidates),
                )
                if user_id is not None
            ]
            + _partner_ids_on([
                record for by_id in profiles.values() for record in by_id.values()
            ]),
        )
        return {
            **page,
            "total": len(people),
            "items": [
                {
                    "person": {"user_id": user_id, "name": names.get(user_id)},
                    "role": role,
                    "profile": _profile(profiles[role].get(user_id), names),
                    **(
                        {"diagnostic_reason": "", "candidates": []}
                        if row is None
                        else {
                            "diagnostic_reason": row.result.diagnostic_reason,
                            "candidates": _candidates(row.result, names),
                            "edited": row.edited,
                            "matcher_mentor": _named(row.result.mentor_id, names),
                            "matcher_reason": row.result.recommendation_reason,
                            "recommendation_reason": row.recommendation_reason,
                        }
                    ),
                }
                for role, user_id, row in page_people
            ],
        }

    def _item(
        self,
        mentee_id: str,
        row,
        names: dict[str, str],
        *,
        mentee_profile,
        mentor_profile,
    ) -> dict:
        """Render one mentee's row as it stands with the draft, beside what the
        matcher chose, with both people as the run was given them."""
        result = row.result
        return {
            "mentee_profile": _profile(mentee_profile, names),
            "mentor_profile": _profile(mentor_profile, names),
            "mentee": {"user_id": mentee_id, "name": names.get(mentee_id)},
            "mentor": _named(row.mentor_id, names),
            "score": row.score,
            "match_type": result.match_type,
            "recommendation_reason": row.recommendation_reason,
            "diagnostic_reason": result.diagnostic_reason,
            "candidates": _candidates(result, names),
            "edited": row.edited,
            "matcher_mentor": _named(result.mentor_id, names),
            "matcher_reason": result.recommendation_reason,
        }
