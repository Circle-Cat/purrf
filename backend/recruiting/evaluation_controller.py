from fastapi import APIRouter

from backend.common.fast_api_response_wrapper import api_response
from backend.utils.permission_decorators import authenticate
from backend.dto.evaluation_dto import EvaluationSubmitDto
from backend.dto.user_context_dto import UserContextDto
from backend.common.api_endpoints import (
    RECRUITING_APPLICATION_EVALUATION_ENDPOINT,
    RECRUITING_EVALUATIONS_MINE_ENDPOINT,
)


class EvaluationController:
    """FastAPI routes for the assignee-facing interview evaluation scorecards.

    Both routes are plain login-gated (authenticate()): "may I write/read
    this evaluation" is a row-level check in EvaluationService (am I the
    current stage's assignee), not an enum permission.
    """

    def __init__(self, evaluation_service, database):
        """
        Args:
            evaluation_service (EvaluationService): Draft/confirm + listing logic.
            database: Async session provider.
        """
        self.evaluation_service = evaluation_service
        self.database = database
        self.router = APIRouter(tags=["recruiting-evaluation"])

        self.router.add_api_route(
            RECRUITING_APPLICATION_EVALUATION_ENDPOINT,
            endpoint=authenticate()(self.submit_evaluation),
            methods=["PUT"],
            response_model=None,
        )
        self.router.add_api_route(
            RECRUITING_EVALUATIONS_MINE_ENDPOINT,
            endpoint=authenticate()(self.get_mine),
            methods=["GET"],
            response_model=None,
        )

    async def submit_evaluation(
        self,
        current_user: UserContextDto,
        application_id: int,
        evaluation_data: EvaluationSubmitDto,
    ):
        """Save a draft, or confirm, an interview evaluation."""
        async with self.database.session() as session:
            result = await self.evaluation_service.submit(
                session, current_user, application_id, evaluation_data
            )
        return api_response(message="Evaluation saved.", data=result)

    async def get_mine(self, current_user: UserContextDto):
        """List every application currently assigned to the caller."""
        async with self.database.session() as session:
            result = await self.evaluation_service.get_mine(session, current_user)
        return api_response(message="Assignments fetched.", data=result)
