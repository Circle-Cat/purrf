from fastapi import APIRouter
from backend.dto.rounds_dto import RoundsDto
from backend.dto.partner_dto import PartnerDto
from backend.dto.user_context_dto import UserContextDto
from backend.dto.registration_dto import RegistrationDto
from backend.dto.registration_create_dto import RegistrationCreateDto
from backend.common.fast_api_response_wrapper import api_response
from backend.utils.permission_decorators import authenticate
from backend.common.api_endpoints import (
    MENTORSHIP_ROUNDS_ENDPOINT,
    MENTORSHIP_ROUNDS_REGISTRATION_ENDPOINT,
    MENTORSHIP_PARTNERS_ENDPOINT,
)


class MentorshipController:
    def __init__(
        self,
        rounds_service,
        participation_service,
        registration_service,
        database,
    ):
        """
        Initialize the MentorshipController with required dependencies and register routes.

        Args:
            rounds_service: RoundsService instance.
            participation_service: ParticipationService instance.
            registration_service: RegistrationService instance.
            database (Database): Database access object providing async session management.
        """

        self.rounds_service = rounds_service
        self.participation_service = participation_service
        self.registration_service = registration_service
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

        self.router.add_api_route(
            MENTORSHIP_ROUNDS_REGISTRATION_ENDPOINT,
            endpoint=authenticate()(self.get_registration_info),
            methods=["GET"],
            response_model=None,
        )

        self.router.add_api_route(
            MENTORSHIP_ROUNDS_REGISTRATION_ENDPOINT,
            endpoint=authenticate()(self.update_registration_info),
            methods=["POST"],
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

    async def get_registration_info(self, current_user: UserContextDto, round_id: int):
        """
        Fetch the registration information for the current user in a specific mentorship round.

        Args:
            current_user (UserContextDto): The authenticated user context.
            round_id (int): The ID of the specific mentorship round the user is registering for.

        Returns:
            API response containing the unified RegistrationDto.
        """
        async with self.database.session() as session:
            registration_info: RegistrationDto = (
                await self.registration_service.get_registration_info(
                    session=session, user_context=current_user, round_id=round_id
                )
            )

        return api_response(
            message="Successfully fetched mentorship round registration information.",
            data=registration_info,
        )

    async def update_registration_info(
        self,
        current_user: UserContextDto,
        round_id: int,
        preferences_data: RegistrationCreateDto,
    ):
        """
        Update or create the registration information for the current user in a specific mentorship round.

        Args:
            current_user (UserContextDto): The authenticated user context.
            round_id (int): The ID of the specific mentorship round the user is registering for.
            preferences_data (RegistrationDto): A DTO containing updated global and round-specific preferences.
        """
        async with self.database.session() as session:
            updated_registration_info: RegistrationDto = (
                await self.registration_service.update_registration_info(
                    session=session,
                    user_context=current_user,
                    round_id=round_id,
                    preferences_data=preferences_data,
                )
            )

        return api_response(
            message="Successfully updated mentorship round registration information.",
            data=updated_registration_info,
        )
