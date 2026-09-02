"""The scheduled training endpoint, called by a CronJob."""

from backend.common.api_endpoints import TRAINING_PACKAGE_CLEANUP_JOB_ENDPOINT
from backend.common.fast_api_response_wrapper import api_response
from backend.common.permissions import Permission
from backend.utils.permission_decorators import authenticate
from fastapi import APIRouter


class TrainingJobController:
    """Deletes the storage behind packages that a newer upload replaced.

    Gated on ``SYSTEM_BACKFILL_SCHEDULED``, a service-account permission no
    signed-in person holds, and POST only: deleting course files is not
    something a browser should cause by loading a URL.
    """

    def __init__(self, training_package_service, database):
        """
        Args:
            training_package_service (TrainingPackageService): The sweep.
            database: Async session provider.
        """
        self.training_package_service = training_package_service
        self.database = database
        self.router = APIRouter(tags=["training-jobs"])

        self.router.add_api_route(
            TRAINING_PACKAGE_CLEANUP_JOB_ENDPOINT,
            endpoint=authenticate(permissions=[Permission.SYSTEM_BACKFILL_SCHEDULED])(
                self.cleanup_packages
            ),
            methods=["POST"],
            response_model=None,
        )

    async def cleanup_packages(self):
        """Delete retired prefixes whose delay has elapsed."""
        async with self.database.session() as session:
            report = await self.training_package_service.delete_retired_prefixes(
                session
            )
        return api_response(
            message="Retired training packages cleaned up.", data=report
        )
