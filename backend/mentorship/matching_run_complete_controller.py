"""The endpoint the matcher job calls when a run finishes.

Everything it decides is in ``MatchingRunCompleteService``; this only turns the
request into that call and the outcome into a status code.
"""

from http import HTTPStatus

from fastapi import APIRouter, Request, Response

from backend.common.api_endpoints import MENTORSHIP_MATCH_RUN_COMPLETE
from backend.mentorship.matching_run_complete_service import CompletionOutcome

_STATUS = {
    CompletionOutcome.ACCEPTED: HTTPStatus.OK,
    CompletionOutcome.NOT_READY: HTTPStatus.SERVICE_UNAVAILABLE,
    CompletionOutcome.REFUSED: HTTPStatus.FORBIDDEN,
}


class MatchingRunCompleteController:
    """Carries the job's callback to the service that acts on it."""

    def __init__(self, matching_run_complete_service, database):
        """
        Args:
            matching_run_complete_service (MatchingRunCompleteService): Decides
                what the callback means and announces the run.
            database: Async session provider.
        """
        self.matching_run_complete_service = matching_run_complete_service
        self.database = database
        self.router = APIRouter(tags=["mentorship-matching"])
        self.router.add_api_route(
            MENTORSHIP_MATCH_RUN_COMPLETE,
            endpoint=self.complete,
            methods=["POST"],
            response_model=None,
        )

    async def complete(self, request: Request) -> Response:
        """Announce a finished run to the administrator who started it.

        Args:
            request (Request): The job's callback, carrying ``run_id``.

        Returns:
            Response: 403 for a caller the service refuses, 503 while the run
                has yet to report, 200 otherwise.
        """
        try:
            run_id = (await request.json())["run_id"]
        except (KeyError, TypeError, ValueError):
            run_id = None

        async with self.database.session() as session:
            outcome = await self.matching_run_complete_service.complete(
                session, request.headers.get("Authorization", ""), run_id
            )
        return Response(status_code=_STATUS[outcome])
