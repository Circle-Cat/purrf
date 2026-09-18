"""A matching run's Redis keys: the input Purrf writes and the result it reads.

Postgres holds nothing about a run. There is no run table, no run id on a pair,
and no history of how many times a round was matched -- everything a run needs
in order to be reviewed and published lives under these keys for three months
and then goes away.

    match:round:{round_id}:lock      one run at a time per round, six hours
    match:round:{round_id}:current   how the review screen finds the run again
    match:{run_id}:meta              MatchingMeta, written last
    match:{run_id}:in:mentors        user_id -> PersonRecord
    match:{run_id}:in:mentees        user_id -> PersonRecord
    match:{run_id}:out               mentee_id -> MenteeResult, the matcher writes
    match:{run_id}:result_meta       MatchingRunResult, the matcher writes last

The lock and the pointer are separate keys on purpose. The lock has to expire on
its own so a run that dies takes the round's block with it; the pointer has to
outlive several days of review. One key cannot do both.
"""

from backend.common.constants import THREE_MONTHS_IN_SECONDS
from backend.mentorship.matching_contract import MatchingMeta, MatchingRunResult

# Matches the job's own timeout, so a run that dies without releasing the lock
# frees its round by itself and nobody has to abandon it by hand.
LOCK_TTL_SECONDS = 6 * 60 * 60

# Upstash refuses a request over 10 MB. A PersonRecord is around 2 KB, so three
# thousand people in one HSET comes close enough to matter. The limit counts
# bytes rather than fields because the records differ several-fold depending on
# how much education and work history somebody filled in -- a fixed number of
# fields per batch would be safe for one round and too large for the next.
MAX_WRITE_BYTES = 4 * 1024 * 1024


def round_lock_key(round_id: int) -> str:
    """Key holding the run id that currently owns this round."""
    return f"match:round:{round_id}:lock"


def round_current_key(round_id: int) -> str:
    """Key holding this round's most recent run id."""
    return f"match:round:{round_id}:current"


def meta_key(run_id: str) -> str:
    """Key holding the run's envelope."""
    return f"match:{run_id}:meta"


def mentors_key(run_id: str) -> str:
    """Hash of the run's mentors, keyed by user id."""
    return f"match:{run_id}:in:mentors"


def mentees_key(run_id: str) -> str:
    """Hash of the run's mentees, keyed by user id."""
    return f"match:{run_id}:in:mentees"


def out_key(run_id: str) -> str:
    """Hash of the run's results, keyed by mentee id."""
    return f"match:{run_id}:out"


def result_meta_key(run_id: str) -> str:
    """Key holding what the matcher reports about the run as a whole."""
    return f"match:{run_id}:result_meta"


def notified_key(run_id: str) -> str:
    """Key marking that this run's completion has already been announced."""
    return f"match:{run_id}:notified"


class MatchingStorage:
    """Reads and writes the Redis keys of a matching run."""

    def __init__(self, redis_client, logger):
        """
        Args:
            redis_client: Redis client, configured with decode_responses.
            logger: Injected logger.
        """
        self.redis_client = redis_client
        self.logger = logger

    def claim_round(self, round_id: int, run_id: str) -> bool:
        """Take the round's lock for this run.

        Args:
            round_id (int): Round being matched.
            run_id (str): Run asking for the round.

        Returns:
            bool: True when the lock was taken. False means another run has it,
                and ``running_run_id`` says which.
        """
        return bool(
            self.redis_client.set(
                round_lock_key(round_id), run_id, nx=True, ex=LOCK_TTL_SECONDS
            )
        )

    def running_run_id(self, round_id: int) -> str | None:
        """Return the run holding this round's lock, or None if it is free."""
        return self.redis_client.get(round_lock_key(round_id))

    def release_round(self, round_id: int, run_id: str) -> None:
        """Give the round's lock back, for a run that never started.

        The six-hour expiry covers a run that dies while working. It does not
        cover a run that fails before the job is even triggered -- selecting the
        wrong people would otherwise lock the round out for the rest of the
        afternoon over a mistake nobody had to wait for.

        Deletes only this run's own lock, so a delete arriving after the expiry
        cannot take a later run's turn away.
        """
        key = round_lock_key(round_id)
        if self.redis_client.get(key) != run_id:
            return
        self.redis_client.delete(key)

    def already_notified(self, run_id: str) -> bool:
        """Whether this run's completion has been announced already."""
        return bool(self.redis_client.exists(notified_key(run_id)))

    def mark_notified(self, run_id: str) -> None:
        """Record that this run's completion has been announced.

        Deliberately two calls rather than one ``SET NX`` used as the gate.
        A gate marks before the announcement goes out, and a crash in between
        then loses that announcement for good, because every retry is turned
        away by a mark for something that never happened. Reading first and
        writing afterwards risks the opposite: a retry that arrives mid-flight
        sends a second "matching finished" email, which costs a reader one
        glance.
        """
        self.redis_client.set(
            notified_key(run_id), "1", nx=True, ex=THREE_MONTHS_IN_SECONDS
        )

    def current_run_id(self, round_id: int) -> str | None:
        """Return this round's most recent run id, or None once it has expired."""
        return self.redis_client.get(round_current_key(round_id))

    def write_input(self, run_id: str, matching_input) -> None:
        """Write everything the matcher reads, and the pointer to find it by.

        The envelope goes last. It is the commit marker: a matcher that cannot
        read it is looking at a run whose people are still arriving, and has to
        stop rather than score whoever happens to be there.

        Args:
            run_id (str): Identifies the run.
            matching_input (MatchingInput): Envelope and both groups.
        """
        self._write_people(mentors_key(run_id), matching_input.mentors)
        self._write_people(mentees_key(run_id), matching_input.mentees)

        self.redis_client.set(
            meta_key(run_id),
            matching_input.meta.model_dump_json(),
            ex=THREE_MONTHS_IN_SECONDS,
        )
        self.redis_client.set(
            round_current_key(matching_input.meta.round_id),
            run_id,
            ex=THREE_MONTHS_IN_SECONDS,
        )
        self.logger.info(
            "[MatchingStorage] run=%s wrote mentors=%d mentees=%d",
            run_id,
            len(matching_input.mentors),
            len(matching_input.mentees),
        )

    def _write_people(self, key: str, people) -> None:
        """Fill one person hash in batches, then give the whole key its expiry."""
        batch: dict[str, str] = {}
        batch_bytes = 0
        for person in people:
            encoded = person.model_dump_json()
            size = len(encoded.encode("utf-8"))
            if batch and batch_bytes + size > MAX_WRITE_BYTES:
                self.redis_client.hset(key, mapping=batch)
                batch = {}
                batch_bytes = 0
            batch[person.user_id] = encoded
            batch_bytes += size
        if batch:
            self.redis_client.hset(key, mapping=batch)
        self.redis_client.expire(key, THREE_MONTHS_IN_SECONDS)

    def read_meta(self, run_id: str) -> MatchingMeta | None:
        """Return the run's envelope, or None if this run is not there.

        The envelope is what says who asked for the run: nothing outside it
        records that, so a completion notice has nowhere else to look.
        """
        raw = self.redis_client.get(meta_key(run_id))
        return None if raw is None else MatchingMeta.model_validate_json(raw)

    def mentor_count(self, run_id: str) -> int:
        """How many mentors the run was given."""
        return self.redis_client.hlen(mentors_key(run_id))

    def read_run_result(self, run_id: str) -> MatchingRunResult | None:
        """Return what the matcher reported, or None while it has yet to report.

        Reads ``result_meta`` first and refuses to look at ``out`` without it,
        which is why a mentee row carries no contract version of its own: the
        version is checked here, once, before anything is read.

        Args:
            run_id (str): Identifies the run.

        Returns:
            MatchingRunResult | None: None while the run is still going, or
                if it never reported at all.

        Raises:
            ValueError: The run reported success but ``out`` does not hold one
                row per mentee. Publishing it would mark the missing people as
                unmatched, which is why the count is checked before anybody is
                offered the result to review.
        """
        reported = self.redis_client.get(result_meta_key(run_id))
        if reported is None:
            return None

        result = MatchingRunResult.model_validate_json(reported)
        if result.status != "succeeded":
            return result

        written = self.redis_client.hlen(out_key(run_id))
        expected = self.redis_client.hlen(mentees_key(run_id))
        if not written == result.mentee_count == expected:
            # Which pair disagrees says where the people went missing: equal to
            # the matcher's own count means it read fewer than Purrf wrote,
            # unequal means it wrote fewer than it read.
            raise ValueError(
                f"Run {run_id} is incomplete: {written} results, "
                f"{result.mentee_count} reported, {expected} mentees sent."
            )
        return result
