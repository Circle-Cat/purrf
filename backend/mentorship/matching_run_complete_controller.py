"""The endpoint the matcher job calls when a run finishes.

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
only forwards callers on its allow-list; this route verifies the same token
again and checks the same account, so a request arriving by any other path
carries nothing it will take.

Losing a callback is survivable by design: the results are in Redis and the
review screen reads them regardless. The only casualty is the email.
"""

from http import HTTPStatus

from fastapi import APIRouter, Request, Response

from backend.common.api_endpoints import MENTORSHIP_MATCH_RUN_COMPLETE
from backend.common.mentorship_enums import MentorshipEvent
from backend.notification_management.event_recorder import record_event


class MatchingRunCompleteController:
    """Turns "the job finished" into a notification for whoever started it."""

    def __init__(
        self,
        logger,
        auth_service,
        matcher_job_subs,
        matching_storage,
        mentorship_round_repository,
        database,
    ):
        """
        Args:
            logger: Injected logger.
            auth_service (AuthenticationService): Verifies the Google token.
            matcher_job_subs: The service account ids whose tokens this route
                accepts. Empty refuses everybody, which is the safe direction
                for a route nothing else guards.
            matching_storage (MatchingStorage): Reads the run and holds the
                marker that keeps one run from being announced twice.
            mentorship_round_repository: Reads the round's name for the email.
            database: Async session provider.
        """
        self.logger = logger
        self.auth_service = auth_service
        self.matcher_job_subs = matcher_job_subs
        self.matching_storage = matching_storage
        self.mentorship_round_repository = mentorship_round_repository
        self.database = database
        self.router = APIRouter(tags=["mentorship-matching"])
        self.router.add_api_route(
            MENTORSHIP_MATCH_RUN_COMPLETE,
            endpoint=self.complete,
            methods=["POST"],
            response_model=None,
        )

    def _refuse(self, reason: str) -> Response:
        """Log why and answer 403 without saying which check failed."""
        self.logger.warning("[MatchingRunComplete] %s; refusing", reason)
        return Response(status_code=HTTPStatus.FORBIDDEN)

    async def complete(self, request: Request) -> Response:
        """Announce a finished run to the administrator who started it.

        The status code is the whole protocol with the job: it retries a few
        times and then gives up, so anything a retry could fix answers 503 and
        anything it could not answers 200.

        Args:
            request (Request): The job's callback, carrying ``run_id``.

        Returns:
            Response: 403 for a caller this route does not know, 503 while the
                run has yet to report, 200 otherwise -- including for a run
                already announced and for a body that cannot be read.
        """
        authorization = request.headers.get("Authorization", "")
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

        try:
            run_id = (await request.json())["run_id"]
        except (KeyError, TypeError, ValueError):
            # A retry produces the same unreadable body, so this is accepted
            # rather than asked for again.
            self.logger.warning("[MatchingRunComplete] unreadable body; accepting")
            return Response(status_code=HTTPStatus.OK)

        if self.matching_storage.already_notified(run_id):
            self.logger.info(
                "[MatchingRunComplete] run=%s already announced; nothing to do",
                run_id,
            )
            return Response(status_code=HTTPStatus.OK)

        meta = self.matching_storage.read_meta(run_id)
        if meta is None:
            # Either the run expired or the job named one that was never
            # written. Neither improves on a retry, and there is nobody to
            # tell: who started it is what the envelope carries.
            self.logger.warning(
                "[MatchingRunComplete] run=%s has no envelope; accepting", run_id
            )
            return Response(status_code=HTTPStatus.OK)

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
                return Response(status_code=HTTPStatus.SERVICE_UNAVAILABLE)
            details |= {
                "status": result.status,
                "error": result.error,
                "startedAt": result.started_at,
                "finishedAt": result.finished_at,
                "menteeCount": result.mentee_count,
                "mentorCount": self.matching_storage.mentor_count(run_id),
            }

        async with self.database.session() as session:
            round_entity = await self.mentorship_round_repository.get_by_round_id(
                session, meta.round_id
            )
            details["roundName"] = getattr(round_entity, "name", None)
            await record_event(
                session,
                subject_type="mentorship_round",
                subject_id=meta.round_id,
                # Never the person who started the run. record_event discards
                # the actor from the recipients, and they are the only one to
                # tell -- passing them sends nothing, silently. A finished run
                # is the system's own doing anyway.
                actor_id=None,
                event_type=MentorshipEvent.MATCHING_RUN_COMPLETED,
                details=details,
            )

        # After the announcement, never before: marking first would mean a
        # crash in between turns every retry away and loses the email for good.
        self.matching_storage.mark_notified(run_id)
        self.logger.info(
            "[MatchingRunComplete] run=%s round=%s status=%s announced",
            run_id,
            meta.round_id,
            details.get("status"),
        )
        return Response(status_code=HTTPStatus.OK)
