"""Starts a matching run: build the input, store it, hand it to the job.

Nothing is recorded in the database. A run is identified by its id and found in
storage under it, and how far along it is comes from Cloud Run. The tables that
will hold a reviewed result arrive with the screens that review it.
"""

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
            matching_payload_service: Builds the payload from the database.
            matching_storage: Where the payload goes.
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
        run_date: str | None = None,
    ) -> dict:
        """Build a round's matching input, store it, and start the job.

        Args:
            session (AsyncSession): The active async database session.
            round_id (int): Round being matched.
            participant_ids (list[int]): Users to include, all registered for it.
            run_date (str | None): ``YYYY-MM-DD`` to score as though it were that
                day; today when absent.

        Returns:
            dict: ``run_id``, ``gcs_prefix`` and ``execution_name``. The job takes
                about an hour at present sizes, so this returns as soon as it has
                started rather than waiting for a result.

        Raises:
            ValueError: A requested user is not registered for the round, the
                selection has no mentor or no mentee, or storage or the job is
                not configured in this environment.
        """
        run_id = new_run_id(round_id)
        payload = await self.matching_payload_service.build_matching_payload(
            session, round_id, participant_ids, run_id=run_id
        )

        # Input first, then the trigger. Failing here leaves an unused file in
        # storage; the other order would leave a job looking for input that was
        # never written.
        gcs_prefix = self.matching_storage.write_payload(run_id, payload)
        execution_name = self.matching_job_client.start(run_id, run_date=run_date)

        self.logger.info(
            "[MatchingRunService] run=%s round=%s mentors=%d mentees=%d execution=%s",
            run_id,
            round_id,
            len(payload.mentors),
            len(payload.mentees),
            execution_name,
        )
        return {
            "run_id": run_id,
            "gcs_prefix": gcs_prefix,
            "execution_name": execution_name,
        }
