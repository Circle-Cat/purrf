from pydantic import model_validator

from backend.dto.base_dto import BaseDto
from backend.dto.base_request_dto import BaseRequestDto
from backend.common.recruiting_enums import JobKind, JobStatus
from backend.common.mentorship_enums import ParticipantRole
from backend.dto.job_config_dto import (
    FormSchemaDto,
    PipelineConfigDto,
    ProfileConfigDto,
    ScreenRulesDto,
)


class JobCreateDto(BaseRequestDto):
    """Request body for creating/updating a posting (incl. all config)."""

    title: str
    description: str | None = None
    kind: JobKind = JobKind.ACTIVITY
    mentorship_role: ParticipantRole | None = None
    form_schema: FormSchemaDto | None = None
    pipeline_config: PipelineConfigDto | None = None
    screen_rules: ScreenRulesDto | None = None
    profile_config: ProfileConfigDto | None = None
    cooldown_days: int | None = None

    @model_validator(mode="after")
    def validate_answer_rules_against_form(self) -> "JobCreateDto":
        """Cross-check ``answer`` screen-rules against the form's questions.

        Each ``answer`` rule's question_id must reference a question in
        form_schema; when that question is a choice question, the rule's
        value(s) must be among its options.

        Returns:
            JobCreateDto: self, when valid.

        Raises:
            ValueError: On a dangling question_id or an out-of-options value.
        """
        if not self.screen_rules:
            return self
        questions = {
            q.id: q for q in (self.form_schema.questions if self.form_schema else [])
        }
        for rule in self.screen_rules.rules:
            cond = rule.condition
            if cond.source != "answer":
                continue
            q = questions.get(cond.question_id)
            if q is None:
                raise ValueError(
                    f"screen-rule {rule.id} references unknown question {cond.question_id}"
                )
            if q.type in ("single_choice", "multi_choice"):
                values = cond.value if isinstance(cond.value, list) else [cond.value]
                bad = [v for v in values if v not in (q.options or [])]
                if bad:
                    raise ValueError(
                        f"screen-rule {rule.id} value(s) {bad} not in options of {q.id}"
                    )
        return self


class JobDto(BaseDto):
    """Response shape for a posting (config stored/returned as raw JSONB dicts)."""

    id: int
    title: str
    description: str | None = None
    kind: JobKind
    mentorship_role: ParticipantRole | None = None
    status: JobStatus
    form_schema: dict | None = None
    pipeline_config: dict | None = None
    screen_rules: dict | None = None
    profile_config: dict | None = None
    pending_payload: dict | None = None
    last_reject_comment: str | None = None
    was_published: bool = False
    cooldown_days: int | None = None


class PublicJobDto(BaseDto):
    """Candidate-safe projection of a published posting.

    Deliberately excludes internal recruiting config that must never reach a
    candidate: ``screen_rules`` (auto-reject logic), ``pipeline_config``
    (internal stages + staff ``ownerId``/``defaultAssigneeId``), the
    ``pending_*`` fields, and ``last_reject_comment``. Only what the
    applicant-facing form needs is exposed.
    """

    id: int
    title: str
    description: str | None = None
    kind: JobKind
    mentorship_role: ParticipantRole | None = None
    form_schema: dict | None = None
    profile_config: dict | None = None


class PublicJobSummaryDto(BaseDto):
    """Candidate-safe list-card projection of a published posting.

    The browse page needs only what a job card shows. Everything else --
    the application form config and every internal recruiting field -- is
    served by ``PublicJobDto`` (detail) or internal DTOs, never here.
    """

    id: int
    title: str
    kind: JobKind
    description: str | None = None
