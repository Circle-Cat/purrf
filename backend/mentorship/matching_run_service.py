"""Starts a matching run: take the round, build the input, hand it to the job.

Nothing is recorded in the database. A run is identified by its id, found in
Redis under it, and how far along it is comes from what the matcher has written
so far. The tables that will hold a reviewed result arrive with the screens that
review it.
"""

import asyncio
from datetime import date

from backend.common.exceptions import ConflictError
from backend.common.matching_job_client import MatcherJobNotStarted
from backend.mentorship.matching_payload_service import new_run_id


class MatchingRunService:
    """Turns a chosen list of participants into a running matcher job."""

    def __init__(
        self,
        matching_payload_service,
        matching_storage,
        matching_job_client,
        logger,
    ):
        """
        Args:
            matching_payload_service: Builds the input from the database.
            matching_storage: Where the input goes.
            matching_job_client: Starts the job that reads it.
            logger: Injected logger.
        """
        self.matching_payload_service = matching_payload_service
        self.matching_storage = matching_storage
        self.matching_job_client = matching_job_client
        self.logger = logger

    async def start_run(
        self,
        session,
        round_id: int,
        participant_ids: list[int],
        run_date: date | None = None,
        triggered_by_user_id: int | None = None,
    ) -> dict:
        """Take the round, write its matching input, and start the job.

        The round is claimed before anything is built, so two admins pressing
        the button together produce one run rather than two that overwrite each
        other's people. A failure that certainly left the job unstarted gives
        the round straight back: the lock's own expiry is there for a run that
        dies while working, not for one that never began. A trigger with no
        answer keeps the lock, because the job may be running on it.

        The round's pointer moves only once the job has been asked to start,
        so a failed start leaves the review screen on the round's last run.

        Args:
            session (AsyncSession): The active async database session.
            round_id (int): Round being matched.
            participant_ids (list[int]): Users to include, all registered for it.
            run_date (date | None): Day to score as though it were; today when
                absent.
            triggered_by_user_id (int | None): Who pressed the button. Carried in
                the envelope because nothing else outlives the run, and the
                completion notice goes to them.

        Returns:
            dict: ``run_id``. The job takes about an hour at present sizes, so
                this returns as soon as it has started rather than waiting.

        Raises:
            ConflictError: This round already has a run going.
            ValueError: A requested user is not registered for the round, the
                selection has no mentor or no mentee, or the job is not
                configured in this environment.
            requests.RequestException: The trigger got no answer. The round
                stays locked and points at this run, which may be running.
        """
        run_id = new_run_id(round_id)
        if not self.matching_storage.claim_round(round_id, run_id):
            running = self.matching_storage.running_run_id(round_id)
            raise ConflictError(
                f"Round {round_id} is already being matched"
                + (f" by run {running}." if running else ".")
            )

        try:
            matching_input = await self.matching_payload_service.build_matching_payload(
                session,
                round_id,
                participant_ids,
                run_id=run_id,
                triggered_by_user_id=(
                    str(triggered_by_user_id)
                    if triggered_by_user_id is not None
                    else None
                ),
            )

            # Input first, then the trigger. Failing here leaves keys nobody
            # reads and that expire on their own; the other order would leave a
            # job looking for input that was never written.
            await asyncio.to_thread(
                self.matching_storage.write_input, run_id, matching_input
            )
        except Exception:
            self.matching_storage.release_round(round_id, run_id)
            raise

        try:
            execution_name = await asyncio.to_thread(
                self.matching_job_client.start, run_id, run_date=run_date
            )
        except MatcherJobNotStarted:
            self.matching_storage.release_round(round_id, run_id)
            raise
        except Exception:
            # Cloud Run may have accepted it. Releasing now would let a second
            # press start another run over the same people.
            self.logger.error(
                "[MatchingRunService] run=%s round=%s trigger got no answer; "
                "keeping the lock",
                run_id,
                round_id,
            )
            self.matching_storage.point_round_at(round_id, run_id)
            raise

        self.matching_storage.point_round_at(round_id, run_id)

        self.logger.info(
            "[MatchingRunService] run=%s round=%s mentors=%d mentees=%d execution=%s",
            run_id,
            round_id,
            len(matching_input.mentors),
            len(matching_input.mentees),
            execution_name,
        )
        return {"run_id": run_id}
