"""Survey answers as stored, and what the participant actually read.

Codes here are the contract's, not the form's storage keys, and every one of
them ships with the sentence it stands for. A matching run carries these tables
so that nothing downstream has to keep its own copy of what an answer means --
there were three such copies, and one of them was wrong in both directions: it
rendered "More than 1 year; long-term planning" as "within 1 year", under a key
that never matched anyway.

Labels are verbatim from MentorshipRegistrationDialog.jsx. Change the wording
there and change it here.
"""

# Mentor -- "Do you have experience transitioning into CS / tech from another
# field?". Stored under survey.career_transition.
CAREER_TRANSITION_MAP = {
    "none": "none_cs_background",
    "path_a": "via_cs_masters",
    "path_b": "via_work_experience",
}

CAREER_TRANSITION_LABELS = {
    "none_cs_background": "No. My undergraduate background was already in the CS field.",
    "via_cs_masters": (
        "Yes, Path A: Non-CS undergraduate background -> CS master's degree -> "
        "technical role."
    ),
    "via_work_experience": (
        "Yes, Path B: Non-CS undergraduate background -> transitioned into a "
        "technical role after several years of work experience."
    ),
}

# Mentee -- "Which of the following best describes your current situation?".
# Stored under survey.current_background.
#
# Deliberately lands in the same vocabulary as the mentor question above, which
# is how a pair is judged to have taken the same route.
TRANSITION_TYPE_MAP = {
    "cs_grad": "none_cs_background",
    "non_cs_cs_master": "via_cs_masters",
    "non_tech_to_tech": "via_work_experience",
    "non_cs_starting": "considering_transition",
}

TRANSITION_TYPE_LABELS = {
    "none_cs_background": (
        "All degrees within the CS field, currently following a technical "
        "job-search path."
    ),
    "via_cs_masters": (
        "Non-CS undergraduate background, currently pursuing or recently completed "
        "a CS master's degree, looking for a first technical role."
    ),
    "via_work_experience": (
        "Have previous non-technical work experience and aiming to transition into "
        "a technical role."
    ),
    "considering_transition": (
        "Non-CS undergraduate background, have not started transitioning into CS "
        "yet, but are considering getting started."
    ),
}

# Mentor -- "Which region are you currently primarily based in for career
# development?". Stored under survey.region.
DEVELOPMENT_REGION_MAP = {"us": "us", "canada": "canada", "china": "china"}

DEVELOPMENT_REGION_LABELS = {
    "us": "United States",
    "canada": "Canada",
    "china": "China",
}

# Mentee -- "Which job market region are you targeting?". Stored under
# survey.target_region.
JOB_MARKET_REGION_MAP = dict(DEVELOPMENT_REGION_MAP)
JOB_MARKET_REGION_LABELS = dict(DEVELOPMENT_REGION_LABELS)

# Mentor -- "Do you have experience mentoring others outside of the CircleCat
# Mentorship Program?". Stored under survey.external_mentoring_exp.
#
# The bucket is the whole answer. The form offers three and never asked for a
# number, so anything downstream that prints a count is inventing one.
EXTERNAL_MENTORING_EXP_MAP = {
    "none": "none",
    "1_to_3": "1_to_3",
    "3_plus": "3_plus",
}

EXTERNAL_MENTORING_EXP_LABELS = {
    "none": "No",
    "1_to_3": "1-3 mentoring experiences",
    "3_plus": "More than 3 mentoring experiences",
}

# Mentee -- "Which stage are you currently in?". Stored on the participant row
# as current_stage.
MENTEE_STAGE_MAP = {
    "job_searching": "job_searching",
    "employed_growing": "employed_growth",
    "changing_direction": "career_switch",
    "grad_school": "grad_planning",
}

MENTEE_STAGE_LABELS = {
    "job_searching": "Currently job searching / preparing for job applications.",
    "employed_growth": "Currently employed, hoping to grow / advance in my career.",
    "career_switch": "Hoping to switch tracks / transition into a different field.",
    "grad_planning": "Planning for graduate school / applications.",
}

# Mentee -- "How urgent is your timeline?". Stored on the participant row as
# time_urgency.
URGENCY_MAP = {
    "within_3_months": "3m",
    "within_6_months": "6m",
    "1_year_plus": "1y_plus",
    "no_timeline": "no_timeline",
}

URGENCY_LABELS = {
    "3m": "Need support within 3 months.",
    "6m": "Within 6 months.",
    "1y_plus": "More than 1 year; long-term planning.",
    "no_timeline": "No clear timeline yet.",
}

# "Which skills can you provide guidance on?" / "Which skills do you hope to
# gain guidance on?". At most three may be picked, which is worth knowing before
# reading an unticked box as a statement of disinterest.
SKILL_LABELS = {
    "resume_guidance": "Resume/LinkedIn Profile",
    "career_path_guidance": "Career Path Guidance",
    "experience_sharing": "Experience Sharing",
    "industry_trends": "Industry Trends",
    "technical_skills": "Technical Skills Development",
    "soft_skills": "Soft Skills Enhancement",
    "networking": "Networking",
    "project_management": "Project Management",
}

# Mentee -- "Which industry are you interested in?". Exactly one is picked, and
# mentors are not asked at all.
INDUSTRY_LABELS = {
    "swe": "Software Engineering",
    "uiux": "UI / UX",
    "ds": "Data Science",
    "pm": "Product Management",
}

# Every coded vocabulary a payload uses, shipped with the payload so a consumer
# never has to hold its own copy.
VOCABULARIES = {
    "career_transition": CAREER_TRANSITION_LABELS,
    "transition_type": TRANSITION_TYPE_LABELS,
    "development_region": DEVELOPMENT_REGION_LABELS,
    "job_market_region": JOB_MARKET_REGION_LABELS,
    "external_mentoring_exp": EXTERNAL_MENTORING_EXP_LABELS,
    "mentee_stage": MENTEE_STAGE_LABELS,
    "urgency": URGENCY_LABELS,
    "skills": SKILL_LABELS,
    "specific_industry": INDUSTRY_LABELS,
}


def mapped_code_or_none(value: str | None, code_map: dict[str, str]) -> str | None:
    """Translate a stored answer into its contract code.

    "other" and anything unrecognised resolve to None; the free text that goes
    with "other" travels in its own field rather than inside this one.
    """
    return code_map.get((value or "").strip())


def other_text_or_none(value: str | None, other_text: str | None) -> str | None:
    """Return the free text, but only when "other" was actually chosen."""
    if (value or "").strip() != "other":
        return None
    return (other_text or "").strip() or None
