"""Reads a round's matching run back for review.

Nothing here writes. A run is found through the round's pointer rather than by
id, because the pointer is the only thing that outlives the review: an admin
comes back days later with a round in hand and nothing else.
"""

from backend.common.mentorship_enums import MatchingRunStatus
from backend.common.name_utils import user_display_name


def _needs_attention(row) -> tuple:
    """Sort key placing the rows an admin has to act on at the top.

    The three outcomes rank before the score does, because a mutual choice
    carries no score at all: reading its absence as zero would sort the pairs
    needing least review in among the weakest ones.
    """
    mentee_id, result = row
    if result.mentor_id is None:
        return (0, 0, mentee_id)
    if result.match_type == "mutual_yes":
        return (2, 0, mentee_id)
    return (1, -result.score, mentee_id)


def _ids_on(rows) -> list[str]:
    """Every user id a page mentions: its mentees, their mentors, the alternatives."""
    ids: list[str] = []
    for mentee_id, result in rows:
        ids.append(mentee_id)
        if result.mentor_id is not None:
            ids.append(result.mentor_id)
        ids.extend(candidate.mentor_id for candidate in result.candidates)
    return ids


class MatchingRunReadService:
    """Answers what state a round's run is in, and what it produced."""

    def __init__(
        self,
        matching_storage,
        mentorship_pairs_repository,
        users_repository,
        logger,
    ):
        """
        Args:
            matching_storage: Where a run's input and result live.
            mentorship_pairs_repository: Says whether the result was published.
            users_repository: Resolves the ids a result is written in.
            logger: Injected logger.
        """
        self.matching_storage = matching_storage
        self.mentorship_pairs_repository = mentorship_pairs_repository
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

    async def _named(self, session, user_ids) -> list[dict]:
        """Pair each id with its display name, keeping ids that resolve to none.

        A name that cannot be found leaves ``name`` null rather than dropping
        the person: a mentor missing from a list of mentors nobody was given is
        worse than one shown without a name, and the caller renders the
        placeholder so that every surface writes it the same way.
        """
        names = await self._name_map(session, user_ids)
        return [
            {"user_id": user_id, "name": names.get(user_id)} for user_id in user_ids
        ]

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

        finished = {
            **started,
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
        matched_count = sum(
            1 for result in results.values() if result.mentor_id is not None
        )
        return {
            **finished,
            "status": MatchingRunStatus.SUCCEEDED,
            "mentee_count": reported.mentee_count,
            "matched_count": matched_count,
            "unmatched_count": len(results) - matched_count,
            "unmatched_mentor_ids": reported.unmatched_mentor_ids,
        }, results

    async def read_overview(self, session, round_id: int) -> dict:
        """Describe the round's most recent run.

        Args:
            session (AsyncSession): The active async database session.
            round_id (int): Round whose run is wanted.

        Returns:
            dict: The run's status and what that status carries.
        """
        run, results = self._read_run(round_id)
        if results is None:
            return run

        return {
            **{
                key: value
                for key, value in run.items()
                if key != "unmatched_mentor_ids"
            },
            "unmatched_mentors": await self._named(
                session, run["unmatched_mentor_ids"]
            ),
            "published": await self.mentorship_pairs_repository.has_pairs_for_round(
                session, round_id
            ),
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
            "matched_count": run.get("matched_count", 0),
            "unmatched_count": run.get("unmatched_count", 0),
            "total": 0,
            "items": [],
        }
        if results is None:
            return page

        selected = [
            (mentee_id, result)
            for mentee_id, result in results.items()
            if matched is None or (result.mentor_id is not None) is matched
        ]
        # Ordered by how much of a person's attention the row needs: nobody
        # found, then the scored ones weakest last, then the mutual choices that
        # need none. Ties break on mentee id so the same run always pages the
        # same way.
        selected.sort(key=_needs_attention)
        rows = selected[offset : offset + limit]

        names = await self._name_map(session, _ids_on(rows))
        return {
            **page,
            "total": len(selected),
            "items": [
                self._item(mentee_id, result, names) for mentee_id, result in rows
            ],
        }

    def _item(self, mentee_id: str, result, names: dict[str, str]) -> dict:
        """Render one mentee's row, ids and names together."""
        return {
            "mentee": {"user_id": mentee_id, "name": names.get(mentee_id)},
            "mentor": None
            if result.mentor_id is None
            else {"user_id": result.mentor_id, "name": names.get(result.mentor_id)},
            "score": result.score,
            "match_type": result.match_type,
            "recommendation_reason": result.recommendation_reason,
            "diagnostic_reason": result.diagnostic_reason,
            "candidates": [
                {
                    "user_id": candidate.mentor_id,
                    "name": names.get(candidate.mentor_id),
                    "score": candidate.score,
                }
                for candidate in result.candidates
            ],
        }
