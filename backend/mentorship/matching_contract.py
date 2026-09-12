"""The data contract between Purrf and purrf-matcher, defined once, here.

Both repositories keep a copy of the JSON Schema generated from these models.
There is no automatic sync between them; `contract_version` is what catches a
copy that has fallen behind.
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

CONTRACT_VERSION = 1

SKILL_KEYS = (
    "resume_guidance",
    "career_path_guidance",
    "experience_sharing",
    "industry_trends",
    "technical_skills",
    "soft_skills",
    "networking",
    "project_management",
)

INDUSTRY_KEYS = ("swe", "ds", "pm", "uiux")


class _Strict(BaseModel):
    """Rejects unknown fields, so a renamed key fails instead of being ignored."""

    model_config = ConfigDict(extra="forbid")


class EducationRecord(_Strict):
    """One education entry. Dates are ``YYYY-MM-DD`` or absent."""

    degree: str = ""
    school: str = ""
    field_of_study: str = ""
    start_date: str | None = None
    end_date: str | None = None


class WorkHistoryRecord(_Strict):
    """One work history entry. Dates are ``YYYY-MM-DD`` or absent."""

    title: str = ""
    company: str = ""
    start_date: str | None = None
    end_date: str | None = None
    is_current_job: bool = False


class PersonRecord(_Strict):
    """A mentor or a mentee, carrying only what the matcher scores on.

    Contact fields and names beyond ``display_name`` are absent: the matcher has
    no consumer for them.
    """

    role: Literal["mentor", "mentee"]
    user_id: str
    display_name: str
    timezone: str = ""
    goal: str = ""
    skills: dict[str, bool]
    education: list[EducationRecord] = Field(default_factory=list)
    work_history: list[WorkHistoryRecord] = Field(default_factory=list)
    expected_partner_ids: list[str] = Field(default_factory=list)
    unexpected_partner_ids: list[str] = Field(default_factory=list)

    # Mentee only: the registration form asks this of mentees and not of mentors.
    specific_industry: dict[str, bool] | None = None

    # Mentor only.
    max_partners: int | None = None
    career_transition: Literal["none", "path_a", "path_b"] | None = None
    career_transition_other: str | None = None
    development_region: Literal["us", "canada", "china"] | None = None
    development_region_other: str | None = None

    # Self-reported, and about mentoring done *outside* CircleCat -- so it says
    # nothing about rounds run here. Carried as the bucket the form offered; the
    # export used to flatten it to a midpoint integer that rationales then
    # printed as a precise count.
    external_mentoring_exp: Literal["none", "1_to_3", "3_plus"] | None = None

    # Counted from Purrf's records. Completed means at least one meeting took
    # place, so a round whose mentee never answered raises only the first.
    mentorship_rounds_participated: int | None = None
    mentorship_rounds_completed: int | None = None

    # Mentee only.
    transition_type: Literal["none", "path_a", "path_b", "considering"] | None = None
    transition_type_other: str | None = None
    urgency: Literal["3m", "6m", "1y_plus", "none"] | None = None
    job_market_region: Literal["us", "canada", "china"] | None = None
    job_market_region_other: str | None = None
    mentee_stage: (
        Literal["job_searching", "employed_growth", "career_switch", "grad_planning"]
        | None
    ) = None

    @field_validator("user_id", mode="before")
    @classmethod
    def _stringify_user_id(cls, value):
        """Accept an integer id and carry it as a string.

        The matcher keys every score, reason and name lookup on this value, so it
        has to be one type the whole way through.
        """
        return str(value)

    @field_validator("skills")
    @classmethod
    def _require_every_skill_key(cls, value):
        """All eight keys, no more and no fewer -- the F1 score counts absences."""
        if set(value) != set(SKILL_KEYS):
            missing = sorted(set(SKILL_KEYS) - set(value))
            unknown = sorted(set(value) - set(SKILL_KEYS))
            raise ValueError(f"skills: missing {missing}, unknown {unknown}")
        return value

    @field_validator("specific_industry")
    @classmethod
    def _require_every_industry_key(cls, value):
        """All four keys when present; absent for mentors, who are never asked."""
        if value is None:
            return value
        if set(value) != set(INDUSTRY_KEYS):
            missing = sorted(set(INDUSTRY_KEYS) - set(value))
            unknown = sorted(set(value) - set(INDUSTRY_KEYS))
            raise ValueError(f"specific_industry: missing {missing}, unknown {unknown}")
        return value

    @model_validator(mode="after")
    def _industry_belongs_to_mentees(self):
        """Present for a mentee, absent for a mentor.

        A mentee who omits it would score zero on industry rather than fail, and
        a mentor who carries it is showing an answer left over from a round they
        took part in as a mentee.
        """
        if self.role == "mentee" and self.specific_industry is None:
            raise ValueError("specific_industry is required for a mentee")
        if self.role == "mentor" and self.specific_industry is not None:
            raise ValueError("specific_industry is never asked of a mentor")
        return self


class MatchingPayload(_Strict):
    """What Purrf writes to Cloud Storage for one matching run."""

    contract_version: int = CONTRACT_VERSION
    run_id: str
    round_id: int
    generated_at: str | None = None
    mentors: list[PersonRecord]
    mentees: list[PersonRecord]


class PairRecord(_Strict):
    """One final assignment.

    ``recommendation_reason`` is the mentee-facing text and is editable;
    ``diagnostic_reason`` is the scoring breakdown and belongs only on the review
    screen. They are named apart because the old CSV import mapped the breakdown
    into the mentee-facing field and truncated it.
    """

    mentee_id: str
    mentor_id: str
    score: int
    match_type: Literal["mutual_yes", "hungarian"]
    recommendation_reason: str = ""
    diagnostic_reason: str = ""


class CandidateRecord(_Strict):
    """A runner-up for one mentee. No recommendation text: the matcher only writes
    one for final pairs."""

    mentee_id: str
    mentor_id: str
    rank: int
    score: int
    diagnostic_reason: str = ""


class MatchingResult(_Strict):
    """What the matcher writes back. Pairs are keyed on user id, never on email."""

    contract_version: int = CONTRACT_VERSION
    run_id: str
    round_id: int
    status: Literal["succeeded", "failed"]
    started_at: str
    finished_at: str
    matcher_version: str
    run_date: str
    error: str | None = None
    pairs: list[PairRecord] = Field(default_factory=list)
    candidates: list[CandidateRecord] = Field(default_factory=list)
    unmatched_mentee_ids: list[str] = Field(default_factory=list)
    unmatched_mentor_ids: list[str] = Field(default_factory=list)
