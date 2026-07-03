from dataclasses import dataclass
from typing import Literal

from backend.common.recruiting_enums import ApplicationStage

ValueType = Literal["pass_fail", "score", "notes"]


@dataclass(frozen=True)
class RubricField:
    """One field in a stage's fixed evaluation rubric."""

    id: str
    label: str
    value_type: ValueType
    # Whether this field pairs a free-text `notes` alongside its main value
    # (irrelevant for value_type="notes", which IS the free text).
    has_notes: bool = False


@dataclass(frozen=True)
class RubricSection:
    """A titled group of rubric fields, rendered together in the UI."""

    title: str
    fields: tuple[RubricField, ...]


RUBRICS: dict[ApplicationStage, tuple[RubricSection, ...]] = {
    ApplicationStage.RECRUITER_SCREENING: (
        RubricSection(
            "Background Fitness",
            (
                RubricField(
                    "bg_match",
                    "Does the candidate's background match the role requirements?",
                    "pass_fail",
                ),
                RubricField(
                    "bg_consistency",
                    "Are the candidate's resume, LinkedIn, and application answers consistent?",
                    "pass_fail",
                ),
                RubricField("bg_strength", "Background strength", "score", has_notes=True),
            ),
        ),
        RubricSection(
            "Cultural Fitness",
            (
                RubricField(
                    "format_compliance",
                    "Did the candidate meet the required format instructions?",
                    "pass_fail",
                ),
                RubricField(
                    "mission_alignment",
                    "Does the candidate demonstrate alignment with the community's mission?",
                    "pass_fail",
                ),
                RubricField("writing_quality", "Writing quality", "score", has_notes=True),
            ),
        ),
        RubricSection(
            "Overall Evaluation",
            (
                RubricField(
                    "overall",
                    "Should this candidate proceed to the next stage?",
                    "score",
                    has_notes=True,
                ),
            ),
        ),
    ),
    ApplicationStage.BEHAVIORAL: (
        RubricSection(
            "Team Effectiveness",
            (
                RubricField(
                    "ownership",
                    "Does the candidate take ownership and drive tasks to completion?",
                    "pass_fail",
                ),
                RubricField(
                    "communication",
                    "Does the candidate communicate effectively with teammates and managers to resolve issues and align expectations?",
                    "pass_fail",
                ),
                RubricField("execution_quality", "Execution quality", "score", has_notes=True),
            ),
        ),
        RubricSection(
            "Personal Effectiveness",
            (
                RubricField(
                    "prioritization",
                    "Does the candidate prioritize tasks effectively under constraints?",
                    "pass_fail",
                ),
                RubricField(
                    "growth",
                    "Has the candidate taken actions outside their comfort zone to learn or grow?",
                    "pass_fail",
                ),
                RubricField(
                    "self_development", "Self-development strength", "score", has_notes=True
                ),
            ),
        ),
        RubricSection(
            "Overall Evaluation",
            (
                RubricField(
                    "overall",
                    "Should this candidate proceed to the next stage?",
                    "score",
                    has_notes=True,
                ),
            ),
        ),
    ),
    ApplicationStage.TECH: (
        RubricSection(
            "Technical Ability",
            (
                RubricField(
                    "data_structures",
                    "Does the candidate select appropriate data structures and algorithms?",
                    "score",
                ),
                RubricField(
                    "correctness", "How correct and complete is the implementation?", "score"
                ),
                RubricField(
                    "debugging", "How effectively does the candidate identify and fix issues?", "score"
                ),
                RubricField(
                    "communication_clarity",
                    "How clearly does the candidate explain their thought process during problem-solving?",
                    "score",
                ),
            ),
        ),
        RubricSection(
            "Interview Record",
            (
                RubricField("problem_statement", "Problem Statement", "notes"),
                RubricField("candidate_approach", "Candidate Understanding and Approach", "notes"),
                RubricField("code_snippet", "Code Snippet", "notes"),
            ),
        ),
        RubricSection(
            "Overall Evaluation",
            (
                RubricField(
                    "overall",
                    "Should this candidate proceed to the next stage?",
                    "score",
                    has_notes=True,
                ),
            ),
        ),
    ),
    ApplicationStage.BOARD_REVIEW: (
        RubricSection(
            "Final Decision",
            (
                RubricField(
                    "final_decision",
                    "Should this candidate proceed to the offer stage / be rejected?",
                    "pass_fail",
                    has_notes=True,
                ),
            ),
        ),
    ),
}


def rubric_for(stage: ApplicationStage) -> tuple[RubricSection, ...]:
    """The fixed rubric for a stage.

    Args:
        stage (ApplicationStage): The interview stage.

    Returns:
        tuple[RubricSection, ...]: That stage's sections and fields.

    Raises:
        ValueError: If the stage has no rubric (not an interview stage).
    """
    rubric = RUBRICS.get(stage)
    if rubric is None:
        raise ValueError(f"Stage {stage!s} has no evaluation rubric.")
    return rubric


def _validate_field(field: RubricField, entry: dict) -> None:
    """Validate one field's answer shape (existing entry, ignores presence).

    Args:
        field (RubricField): The rubric field definition being checked.
        entry (dict): The submitted `{"value": ..., "notes": ...}` entry.

    Raises:
        ValueError: If the entry's shape doesn't match the field's type.
    """
    if field.value_type == "notes":
        if not isinstance(entry.get("notes"), str) or not entry["notes"].strip():
            raise ValueError(f"field {field.id!r} requires non-empty notes")
        return
    if field.value_type == "pass_fail":
        if not isinstance(entry.get("value"), bool):
            raise ValueError(f"field {field.id!r} requires a boolean value")
    elif field.value_type == "score":
        value = entry.get("value")
        if not isinstance(value, int) or isinstance(value, bool) or not (1 <= value <= 5):
            raise ValueError(f"field {field.id!r} requires an integer score 1-5")
    if field.has_notes:
        if not isinstance(entry.get("notes"), str) or not entry["notes"].strip():
            raise ValueError(f"field {field.id!r} requires non-empty notes")


def validate_responses(
    stage: ApplicationStage, responses: dict, *, require_complete: bool
) -> None:
    """Validate a submitted responses blob against its stage's rubric.

    Args:
        stage (ApplicationStage): The interview stage the responses are for.
        responses (dict): Field id -> {"value": ..., "notes": ...} entries.
        require_complete (bool): True on confirm (every field must be
            present and well-formed); False on draft save (only present
            fields are shape-checked; missing fields are fine).

    Raises:
        ValueError: On the first missing (when require_complete) or
            malformed field encountered.
    """
    for section in rubric_for(stage):
        for field in section.fields:
            entry = responses.get(field.id)
            if entry is None:
                if require_complete:
                    raise ValueError(f"field {field.id!r} is required")
                continue
            _validate_field(field, entry)
