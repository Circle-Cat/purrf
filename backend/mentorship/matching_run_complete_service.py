"""What happens when the matcher job reports that a run finished.

Why the job calls in rather than Purrf watching for it: the notification
delivery route cannot be reused (it takes a notification id and looks up a row
that already exists, which the matcher cannot produce), the row cannot be
created up front (a PENDING notification older than ten minutes is swept and
republished, so the email would arrive ten minutes into a fifty-minute run),
and nothing in the backend starts a Pub/Sub pull loop that survives a pod
restart.

So one authenticated HTTP call, and the existing notification chain does the
rest: ``record_event`` writes the row and its after-commit listener publishes
to the topic already in use.

Identity is asserted twice. The gateway Worker verifies the Google token and
only forwards callers on its allow-list; this service verifies the same token
again and checks the same account, so a request arriving by any other path
carries nothing it will take.

Losing a callback is survivable by design: the results are in Redis and the
review screen reads them regardless. The only casualty is the email.
"""

from enum import StrEnum

from sqlalchemy.ext.asyncio import AsyncSession

from backend.common.mentorship_enums import MentorshipEvent
from backend.notification_management.event_recorder import record_event


class CompletionOutcome(StrEnum):
    """What the job is told, which is all the protocol with it there is.

    It retries a few times and then gives up, so anything a retry could fix is
    NOT_READY and anything it could not is ACCEPTED.
    """

    ACCEPTED = "accepted"
    NOT_READY = "not_ready"
    REFUSED = "refused"


class MatchingRunCompleteService:
    """Turns "the job finished" into a notification for whoever started it."""

    def __init__(
        self,
        logger,
        auth_service,
        matcher_job_subs,
        matching_storage,
        mentorship_round_repository,
    ):
        """
        Args:
            logger: Injected logger.
            auth_service (AuthenticationService): Verifies the Google token.
            matcher_job_subs: The service account ids whose tokens this accepts.
                Empty refuses everybody, which is the safe direction for a
                route nothing else guards.
            matching_storage (MatchingStorage): Reads the run and holds the
                marker that keeps one run from being announced twice.
            mentorship_round_repository: Reads the round's name for the email.
        """
        self.logger = logger
        self.auth_service = auth_service
        self.matcher_job_subs = matcher_job_subs
        self.matching_storage = matching_storage
        self.mentorship_round_repository = mentorship_round_repository

    def _refuse(self, reason: str) -> CompletionOutcome:
        """Log why, and refuse without saying which check failed."""
        self.logger.warning("[MatchingRunComplete] %s; refusing", reason)
        return CompletionOutcome.REFUSED

    def _caller_refusal(self, authorization: str) -> CompletionOutcome | None:
        """Refuse any caller that is not the provisioned matcher job.

        Returns:
            CompletionOutcome | None: REFUSED, or None when the caller is the job.
        """
        if not authorization.startswith("Bearer "):
            return self._refuse("request carried no token")

        try:
            claims = self.auth_service.verify_google_token(
                authorization.removeprefix("Bearer ")
            )
        except ValueError as error:
            return self._refuse(f"token rejected: {error}")

        if not self.matcher_job_subs:
            return self._refuse(
                "MATCHER_JOB_SUBS is missing or empty -- refusing every caller "
                "until it is configured"
            )

        if claims.get("sub") not in self.matcher_job_subs:
            return self._refuse("token sub is not the provisioned matcher job")

        return None

    async def complete(
        self, session: AsyncSession, authorization: str, run_id: str | None
    ) -> CompletionOutcome:
        """Announce a finished run to the administrator who started it.

        Commits its own transaction: it is called straight from the route, and
        the email is published only once the notification row is committed.

        Args:
            session (AsyncSession): A session this call owns.
            authorization (str): The request's Authorization header, or "".
            run_id (str | None): The run the job names, or None when the body
                could not be read.

        Returns:
            CompletionOutcome: REFUSED for a caller this does not know,
                NOT_READY while the run has yet to report, ACCEPTED otherwise --
                including for a run already announced and for a body that
                cannot be read.
        """
        refusal = self._caller_refusal(authorization)
        if refusal is not None:
            return refusal

        if run_id is None:
            # A retry produces the same unreadable body, so this is accepted
            # rather than asked for again.
            self.logger.warning("[MatchingRunComplete] unreadable body; accepting")
            return CompletionOutcome.ACCEPTED

        meta = self.matching_storage.read_meta(run_id)
        if meta is None:
            # Either the run expired or the job named one that was never
            # written. Neither improves on a retry, and there is nobody to
            # tell: who started it is what the envelope carries.
            self.logger.warning(
                "[MatchingRunComplete] run=%s has no envelope; accepting", run_id
            )
            return CompletionOutcome.ACCEPTED

        if self.matching_storage.already_notified(run_id):
            # Released here too: a crash between the announcement and the
            # release would otherwise hold the round until the lock expires.
            self.matching_storage.release_round(meta.round_id, run_id)
            self.logger.info(
                "[MatchingRunComplete] run=%s already announced; nothing to do",
                run_id,
            )
            return CompletionOutcome.ACCEPTED

        details = {
            "runId": run_id,
            "triggeredByUserId": meta.triggered_by_user_id,
        }
        try:
            result = self.matching_storage.read_run_result(run_id)
        except ValueError as error:
            # A result that arrived but cannot be used is a failure as far as
            # the person waiting is concerned, and the message says which count
            # disagreed. Retrying would report the same thing.
            details |= {"status": "failed", "error": str(error)}
            result = None
        else:
            if result is None:
                # The job says it finished before its own last write landed.
                # The one case a retry fixes.
                self.logger.info(
                    "[MatchingRunComplete] run=%s has not reported yet", run_id
                )
                return CompletionOutcome.NOT_READY
            details |= {
                "status": result.status,
                "error": result.error,
                "startedAt": result.started_at,
                "finishedAt": result.finished_at,
                "menteeCount": result.mentee_count,
                "mentorCount": self.matching_storage.mentor_count(run_id),
            }

        # The run is over either way, so the round is free for the next one.
        # Before the announcement, because a failure sending it answers 500,
        # which the job does not retry, and the lock would then sit out its
        # six hours on a run that ended long ago.
        self.matching_storage.release_round(meta.round_id, run_id)

        round_entity = await self.mentorship_round_repository.get_by_round_id(
            session, meta.round_id
        )
        details["roundName"] = getattr(round_entity, "name", None)
        await record_event(
            session,
            subject_type="mentorship_round",
            subject_id=meta.round_id,
            # Never the person who started the run. record_event discards the
            # actor from the recipients, and they are the only one to tell --
            # passing them sends nothing, silently. A finished run is the
            # system's own doing anyway.
            actor_id=None,
            event_type=MentorshipEvent.MATCHING_RUN_COMPLETED,
            details=details,
        )
        # The session never commits on its own, and the email is published
        # only once this does: without it the bell rolls back on close and
        # nothing is sent.
        await session.commit()

        # After the announcement, never before: marking first would mean a
        # crash in between turns every retry away and loses the email for good.
        self.matching_storage.mark_notified(run_id)
        self.logger.info(
            "[MatchingRunComplete] run=%s round=%s status=%s announced",
            run_id,
            meta.round_id,
            details.get("status"),
        )
        return CompletionOutcome.ACCEPTED
