from fastapi import APIRouter
from backend.dto.rounds_dto import RoundsDto
from backend.mentorship.rounds_service import RoundsService
from backend.common.fast_api_response_wrapper import api_response
from backend.common.api_endpoints import MENTORSHIP_ROUNDS_ENDPOINT


class MentorshipController:
    def __init__(self, mentorship_service: RoundsService, database):
        """
        Initialize the MentorshipController with required dependencies and register routes.

        Args:
            mentorship_service: RoundsService instance.
            databse (Database): Database access object providing async session management.
        """
        if not mentorship_service:
            raise ValueError("RoundsService instances is required.")

        self.mentorship_service = mentorship_service
        self.database = database

        self.router = APIRouter(tags=["rounds"])

        self.router.add_api_route(
            MENTORSHIP_ROUNDS_ENDPOINT,
            endpoint=self.get_all_rounds,
            methods=["GET"],
            response_model=None,
        )

    async def get_all_rounds(self):
        """
        Retrieve all mentorship rounds.

        Return:
            API response containing a list of rounds DTOs.
        """
        async with self.database.session() as session:
            rounds: list[RoundsDto] = await self.mentorship_service.get_all_rounds(
                session
            )

        return api_response(
            message="Successfully fetched all mentorship rounds.",
            data=rounds,
        )
