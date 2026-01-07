from fastapi import APIRouter
from backend.dto.rounds_dto import RoundsDto
from backend.dto.partner_dto import PartnerDto
from backend.dto.user_context_dto import UserContextDto
from backend.mentorship.rounds_service import RoundsService
from backend.mentorship.participation_service import ParticipationService
from backend.common.fast_api_response_wrapper import api_response
from backend.utils.permission_decorators import authenticate
from backend.common.api_endpoints import (
    MENTORSHIP_ROUNDS_ENDPOINT,
    MENTORSHIP_PARTNERS_ENDPOINT,
)


class MentorshipController:
    def __init__(
        self,
        rounds_service: RoundsService,
        participation_service: ParticipationService,
        database,
    ):
        """
        Initialize the MentorshipController with required dependencies and register routes.

        Args:
            rounds_service: RoundsService instance.
            participation_service: ParticipationService instance.
            database (Database): Database access object providing async session management.
        """
        if not rounds_service:
            raise ValueError("RoundsService instance is required.")
        if not participation_service:
            raise ValueError("ParticipationService instance is required.")

        self.rounds_service = rounds_service
        self.participation_service = participation_service
        self.database = database

        self.router = APIRouter(tags=["mentorship"])

        self.router.add_api_route(
            MENTORSHIP_ROUNDS_ENDPOINT,
            endpoint=self.get_all_rounds,
            methods=["GET"],
            response_model=None,
        )

        self.router.add_api_route(
            MENTORSHIP_PARTNERS_ENDPOINT,
            endpoint=authenticate()(self.get_partners_for_user),
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
            rounds: list[RoundsDto] = await self.rounds_service.get_all_rounds(session)

        return api_response(
            message="Successfully fetched all mentorship rounds.",
            data=rounds,
        )

    async def get_partners_for_user(
        self, current_user: UserContextDto, round_id: int | None = None
    ):
        """
        Retrieve mentorship partners for the current user.

        Args:
            current_user (UserContextDto): The authenticated user context object
                                        containing the user's unique ID (sub),
                                        email, and assigned roles.
            round_id (int | None): Mentorship round ID to filter partners.

        Return:
            API response containing a list of partner DTOs.
        """
        async with self.database.session() as session:
            partners: list[
                PartnerDto
            ] = await self.participation_service.get_partners_for_user(
                session=session, user_context=current_user, round_id=round_id
            )

        return api_response(
            message="Successfully fetched mentorship partners.",
            data=partners,
        )
