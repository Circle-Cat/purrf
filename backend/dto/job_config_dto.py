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
    "single_choice": {"options"},
    "multi_choice": {"options", "max_selections"},
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
