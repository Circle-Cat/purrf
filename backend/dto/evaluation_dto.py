"""Evaluation DTOs for the interview evaluation feature (PR2).

Covers submitting/confirming an evaluator's scorecard for an application and
the shapes returned to the client (single evaluation and the caller's "My
Evaluations" list).
"""

from datetime import datetime

from backend.dto.base_dto import BaseDto
from backend.dto.base_request_dto import BaseRequestDto
from backend.common.recruiting_enums import ApplicationStage


class EvaluationSubmitDto(BaseRequestDto):
    """Save a draft or confirm an evaluation."""

    responses: dict
    confirm: bool = False


class EvaluationDto(BaseDto):
    """One evaluator's scorecard, as returned to the client."""

    id: int
    application_id: int
    stage: ApplicationStage
    round: int
    evaluator_id: int
    responses: dict
    is_confirmed: bool
    confirmed_at: datetime | None = None


class MyEvaluationDto(BaseDto):
    """One row in the caller's 'My Evaluations' list."""

    application_id: int
    job_title: str
    applicant_name: str
    stage: ApplicationStage
    round: int
    is_confirmed: bool
    is_current: bool
