from typing import Literal

from pydantic import field_validator, model_validator

from backend.dto.base_request_dto import BaseRequestDto

QuestionType = Literal[
    "short_text", "long_text", "single_choice", "multi_choice", "exact_text"
]

# Which optional fields each question type is allowed to carry.
_ALLOWED_FIELDS: dict[str, set[str]] = {
    "short_text": set(),
    "long_text": {"max_length", "max_words"},
    "single_choice": {"options", "other_option"},
    "multi_choice": {"options", "max_selections", "other_option"},
    "exact_text": {"expected_value"},
}


class ShowWhenDto(BaseRequestDto):
    """Single-layer conditional-visibility rule on a question.

    Renders the owning question only when the referenced question's answer
    matches ``equals`` (exact match for scalar answers; membership for
    multi_choice). Enforcement of visibility at submit time is flow-two.
    """

    question_id: str
    equals: str


class QuestionDto(BaseRequestDto):
    """One submission-form question (self-written compact model, no @rjsf)."""

    id: str
    type: QuestionType
    label: str
    required: bool = False
    show_when: ShowWhenDto | None = None
    options: list[str] | None = None
    max_selections: int | None = None
    max_length: int | None = None
    max_words: int | None = None
    expected_value: str | None = None
    other_option: str | None = None

    @field_validator("label")
    @classmethod
    def label_nonempty(cls, v: str) -> str:
        """Reject blank labels (whitespace already stripped by BaseRequestDto).

        Args:
            v (str): The candidate label.

        Returns:
            str: The validated, non-empty label.

        Raises:
            ValueError: If the label is empty.
        """
        if not v:
            raise ValueError("Question label must be non-empty")
        return v

    @model_validator(mode="after")
    def validate_type_fields(self) -> "QuestionDto":
        """Enforce per-type field presence/bounds and reject foreign fields.

        Returns:
            QuestionDto: self, when valid.

        Raises:
            ValueError: If a field is set that the type does not allow, or a
                required-by-type field is missing/invalid.
        """
        allowed = _ALLOWED_FIELDS[self.type]
        present = {
            name
            for name in (
                "options",
                "max_selections",
                "max_length",
                "max_words",
                "expected_value",
                "other_option",
            )
            if getattr(self, name) is not None
        }
        foreign = present - allowed
        if foreign:
            raise ValueError(f"{self.type} question may not set {sorted(foreign)}")

        if self.type in ("single_choice", "multi_choice"):
            if not self.options:
                raise ValueError(f"{self.type} requires a non-empty options list")
            if any(not opt or not opt.strip() for opt in self.options):
                raise ValueError("options entries must be non-empty")
        if self.type == "multi_choice" and self.max_selections is not None:
            if not (1 <= self.max_selections <= len(self.options)):
                raise ValueError("max_selections must be within [1, len(options)]")
        if self.type == "long_text":
            if self.max_length is not None and self.max_length <= 0:
                raise ValueError("max_length must be > 0")
            if self.max_words is not None and self.max_words <= 0:
                raise ValueError("max_words must be > 0")
        if self.type == "exact_text":
            if not self.expected_value or not self.expected_value.strip():
                raise ValueError("exact_text requires a non-empty expected_value")
        if self.other_option is not None and self.other_option not in (
            self.options or []
        ):
            raise ValueError("other_option must be one of options")
        return self


class FormSchemaDto(BaseRequestDto):
    """A posting's submission form: an ordered list of questions."""

    questions: list[QuestionDto] = []

    @model_validator(mode="after")
    def validate_schema(self) -> "FormSchemaDto":
        """Enforce unique ids and valid single-layer showWhen references.

        Returns:
            FormSchemaDto: self, when valid.

        Raises:
            ValueError: On duplicate ids, or a showWhen referencing a missing
                question or itself.
        """
        ids = [q.id for q in self.questions]
        if len(ids) != len(set(ids)):
            raise ValueError("question ids must be unique within a form")
        id_set = set(ids)
        for q in self.questions:
            if q.show_when is None:
                continue
            target = q.show_when.question_id
            if target == q.id:
                raise ValueError(f"question {q.id} showWhen cannot reference itself")
            if target not in id_set:
                raise ValueError(
                    f"question {q.id} showWhen references unknown question {target}"
                )
        return self


PipelineStage = Literal["recruiter_screening", "behavioral", "tech", "board_review"]
_ASSIGNABLE_DEFAULT_STAGES = {"recruiter_screening", "behavioral"}


class PipelineStageDto(BaseRequestDto):
    """One stage selected into a posting's pipeline."""

    stage: PipelineStage
    rounds: int
    referral_skippable: bool = False
    default_assignee_id: int | None = None

    @field_validator("rounds")
    @classmethod
    def rounds_positive(cls, v: int) -> int:
        """Require at least one round.

        Args:
            v (int): The candidate round count.

        Returns:
            int: The validated round count.

        Raises:
            ValueError: If fewer than one round.
        """
        if v < 1:
            raise ValueError("rounds must be >= 1")
        return v

    @model_validator(mode="after")
    def assignee_stage_restriction(self) -> "PipelineStageDto":
        """default_assignee_id may only be pre-set on screening/behavioral.

        Returns:
            PipelineStageDto: self, when valid.

        Raises:
            ValueError: If default_assignee_id is set on tech/board_review.
        """
        if (
            self.default_assignee_id is not None
            and self.stage not in _ASSIGNABLE_DEFAULT_STAGES
        ):
            raise ValueError(
                "default_assignee_id is only allowed on recruiter_screening/behavioral"
            )
        return self


class PipelineConfigDto(BaseRequestDto):
    """A posting's interview pipeline: an owner plus ordered selected stages."""

    owner_id: int | None = None
    stages: list[PipelineStageDto] = []

    @model_validator(mode="after")
    def no_duplicate_stages(self) -> "PipelineConfigDto":
        """Reject the same stage selected twice.

        Returns:
            PipelineConfigDto: self, when valid.

        Raises:
            ValueError: On a duplicate stage.
        """
        seen = [s.stage for s in self.stages]
        if len(seen) != len(set(seen)):
            raise ValueError("a stage may appear at most once in the pipeline")
        return self


class ScreenRuleConditionDto(BaseRequestDto):
    """The matching condition of a machine-screening rule."""

    source: Literal["email_domain", "answer"]
    operator: Literal["equals", "in", "not_in"]
    value: str | list[str]
    question_id: str | None = None

    @model_validator(mode="after")
    def validate_source_shape(self) -> "ScreenRuleConditionDto":
        """email_domain forbids question_id and not_in; answer requires question_id.

        Returns:
            ScreenRuleConditionDto: self, when valid.

        Raises:
            ValueError: On an illegal source/operator/question_id combination.
        """
        if self.source == "email_domain":
            if self.question_id is not None:
                raise ValueError("email_domain condition must not set question_id")
            if self.operator not in ("equals", "in"):
                raise ValueError("email_domain operator must be equals or in")
        else:  # answer
            if not self.question_id:
                raise ValueError("answer condition requires question_id")
        return self


class ScreenRuleDto(BaseRequestDto):
    """A single machine-screening rule (condition -> action)."""

    id: str
    condition: ScreenRuleConditionDto
    action: Literal["reject", "qualify"]


class ScreenRulesDto(BaseRequestDto):
    """The configurable machine-screening rule set (pre-screening gate)."""

    rules: list[ScreenRuleDto] = []

    @model_validator(mode="after")
    def unique_ids(self) -> "ScreenRulesDto":
        """Reject duplicate rule ids.

        Returns:
            ScreenRulesDto: self, when valid.

        Raises:
            ValueError: On a duplicate rule id.
        """
        ids = [r.id for r in self.rules]
        if len(ids) != len(set(ids)):
            raise ValueError("screen-rule ids must be unique")
        return self


class ProfileConfigDto(BaseRequestDto):
    """Per-posting profile-section requirement levels."""

    education: Literal["required", "optional", "off"] = "optional"
    work_experience: Literal["required", "optional", "off"] = "optional"
    resume: Literal["required", "optional", "off"] = "optional"
