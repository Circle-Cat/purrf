"""The data contract between Purrf and purrf-matcher, defined once, here.

The transport is Redis, and the unit of the contract is one addressable value.
A schema describing a document nobody stores cannot be validated against
anything, which is what the previous pair of schemas had become: they described
a payload and a result that Redis never holds, because the two person lists are
key names now and the pairs are spread one per field.

    match:{run}:meta          MatchingMeta       Purrf writes, last
    match:{run}:in:mentors    PersonRecord       Purrf writes, one per field
    match:{run}:in:mentees    PersonRecord       Purrf writes, one per field
    match:{run}:out           MenteeResult       the matcher writes, one per field
    match:{run}:result_meta   MatchingRunResult  the matcher writes, last

Both repositories keep a copy of the JSON Schema generated from these models,
and nothing syncs them, so each direction carries its own version: Purrf stamps
META_VERSION, the matcher stamps RESULT_VERSION, and each reader checks the one
it receives. Separate constants on purpose -- a single number covering both
directions made a change to either contract look like a change to both.
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

META_VERSION = 1
RESULT_VERSION = 1

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
    career_transition: (
        Literal["none_cs_background", "via_cs_masters", "via_work_experience"] | None
    ) = None
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
    transition_type: (
        Literal[
            "none_cs_background",
            "via_cs_masters",
            "via_work_experience",
            "considering_transition",
        ]
        | None
    ) = None
    transition_type_other: str | None = None
    urgency: Literal["3m", "6m", "1y_plus", "no_timeline"] | None = None
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


class MatchingMeta(_Strict):
    """The envelope for one run, written after the two person hashes.

    It is the commit marker. A reader that cannot find it is looking at a run
    Purrf has not finished writing and has to stop, because the alternative --
    reading the people that are there so far -- succeeds and produces a round
    that is quietly short.
    """

    contract_version: int = META_VERSION
    # Repeats the run id that is already in the key, on purpose: the job takes
    # its run id from the environment, and comparing the two catches a job
    # pointed at a different run.
    run_id: str
    round_id: int
    generated_at: str | None = None
    # The matcher never reads this. It rides along because nothing else outlives
    # the run, and the completion notice has to reach whoever started it.
    triggered_by_user_id: str | None = None
    # Every coded answer above, with the sentence the participant read. Carried
    # once per run rather than per person: a consumer that renders an answer
    # should never have to keep its own translation, which is how one ended up
    # printing a raw code and another inverted the meaning of an option.
    vocabularies: dict[str, dict[str, str]] = Field(default_factory=dict)


class Candidate(_Strict):
    """A mentor the admin can swap in, in a list whose order is the ranking.

    There is no rank field. With the assigned mentor left out of the list, a
    stored rank could mean either the position here or the position in the full
    ranking, and nothing would catch the two being read apart.
    """

    mentor_id: str
    score: int
    diagnostic_reason: str = ""


class MenteeResult(_Strict):
    """One mentee's outcome, stored under that mentee's id.

    ``recommendation_reason`` is the mentee-facing text and is editable;
    ``diagnostic_reason`` is the scoring breakdown and belongs only on the review
    screen. They are named apart because the old CSV import mapped the breakdown
    into the mentee-facing field and truncated it.

    ``score`` carries real scores only. The matcher decides its hard rules with
    sentinels (+1000 for a mutual choice, -1000 when either side refused), and a
    sentinel that reached this field would be read as a score by whoever is
    comparing the assignment against its alternatives.
    """

    mentor_id: str | None = None
    score: int | None = None
    match_type: Literal["mutual_yes", "hungarian"] | None = None
    # Deliberately no max_length, though the column it ends up in is
    # String(300). The matcher truncates at its own exit; a length check here
    # would turn one over-long sentence into a run nobody can open, and the
    # review screen -- where an admin sees the text and a counter, and can trim
    # it -- is the thing that would stop opening. A column constraint fails one
    # row; a constraint on this model fails a run.
    recommendation_reason: str = ""
    diagnostic_reason: str = ""
    candidates: list[Candidate] = Field(default_factory=list, max_length=3)

    @model_validator(mode="after")
    def _outcome_is_one_of_three_shapes(self):
        """Unmatched, mutual choice, or scored assignment -- and never a mix.

        ``score`` is absent in two of the three, so it is not what a reader
        branches on; ``mentor_id`` is. Checked here so a malformed row fails
        when it arrives rather than on the review screen.
        """
        if self.mentor_id is None:
            if self.match_type is not None or self.score is not None:
                raise ValueError(
                    "an unmatched mentee carries neither score nor match_type"
                )
        elif self.match_type is None:
            raise ValueError("an assigned mentor needs a match_type")
        elif self.match_type == "mutual_yes":
            if self.score is not None:
                raise ValueError(
                    "a mutual choice is not scored; match_type already says so"
                )
        elif self.score is None:
            raise ValueError("a hungarian assignment carries its score")
        return self

    @model_validator(mode="after")
    def _candidates_are_alternatives(self):
        """The assigned mentor is not among his own alternatives.

        The list is what the admin can swap in, so keeping the current mentor in
        it spends one of three slots offering a change that changes nothing.
        """
        if self.mentor_id is not None and any(
            candidate.mentor_id == self.mentor_id for candidate in self.candidates
        ):
            raise ValueError("the assigned mentor is listed among the candidates")
        return self

    @model_validator(mode="after")
    def _candidates_are_in_ranking_order(self):
        """Position in the list is the rank, so the list has to be sorted.

        Nothing else records the ranking -- there is no rank field -- and the
        review screen renders them in the order they arrive. Ties break on
        mentor_id so that the same input always produces the same list.
        """
        ranked = sorted(
            self.candidates,
            key=lambda candidate: (-candidate.score, candidate.mentor_id),
        )
        if self.candidates != ranked:
            raise ValueError(
                "candidates are not in ranking order (score descending, then mentor_id)"
            )
        return self


class MatchingRunResult(_Strict):
    """Written after the last mentee, and the run's commit marker.

    A failed run is this value and nothing else: ``out`` stays empty, so a null
    ``mentor_id`` always means nobody was assigned and never that the run died
    partway.
    """

    # No default, unlike the meta Purrf stamps itself. This is the one model
    # Purrf only ever reads, and a default would let an absent version read as
    # the current one. MenteeResult carries no version of its own precisely
    # because this check is supposed to have happened first.
    contract_version: int
    run_id: str
    round_id: int
    status: Literal["succeeded", "failed"]
    started_at: str
    finished_at: str
    matcher_version: str
    run_date: str
    # How many fields ``out`` should hold. Purrf knows the same number as HLEN
    # of the mentee hash; the two together say whether a short run lost people
    # on the way in or on the way out, which decides whose logs to read.
    mentee_count: int
    error: str | None = None
    # Not derivable from ``out``: a mentor may take several mentees, and one who
    # took fewer than his cap is not unmatched.
    unmatched_mentor_ids: list[str] = Field(default_factory=list)

    @field_validator("contract_version")
    @classmethod
    def _reject_a_version_this_reader_does_not_know(cls, value):
        """A matcher image that has fallen behind is refused, not guessed at."""
        if value != RESULT_VERSION:
            raise ValueError(
                f"result contract_version {value} is not supported; "
                f"this reader knows {RESULT_VERSION}"
            )
        return value
