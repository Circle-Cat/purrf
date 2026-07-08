"""FastAPI routes for the cross-posting recruiting audit page — the only
view in this codebase not scoped to a job's own owners.
"""

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Query

from backend.common.fast_api_response_wrapper import api_response
from backend.common.permissions import Permission
from backend.utils.permission_decorators import authenticate
from backend.dto.user_context_dto import UserContextDto
from backend.common.api_endpoints import RECRUITING_AUDIT_OVERVIEW_ENDPOINT


class AuditController:
    """Read-only routes for the recruiting audit page, gated by
    ``Permission.RECRUITING_AUDIT_READ`` — a dedicated permission, not
    reused from ``RECRUITING_JOB_READ``, since this exposes
    application-level headcounts across every posting."""

    def __init__(self, audit_service, database):
        """
        Args:
            audit_service (AuditService): Cross-posting audit business logic.
            database: Async session provider.
        """
        self.audit_service = audit_service
        self.database = database
        self.router = APIRouter(tags=["recruiting-audit"])

        self.router.add_api_route(
            RECRUITING_AUDIT_OVERVIEW_ENDPOINT,
            endpoint=authenticate(permissions=[Permission.RECRUITING_AUDIT_READ])(
                self.get_overview
            ),
            methods=["GET"],
            response_model=None,
        )

    async def get_overview(
        self,
        current_user: UserContextDto,
        start_date: date = Query(..., alias="startDate"),
        end_date: date = Query(..., alias="endDate"),
        job_ids: Annotated[list[int], Query(alias="jobIds")] = [],
    ):
        """Return the audit page's open-positions count, job list, stage
        breakdown, and daily trend for the given date range and job
        selection."""
        async with self.database.session() as session:
            result = await self.audit_service.get_overview(
                session, start_date, end_date, job_ids
            )
        return api_response(message="Audit overview fetched.", data=result)
