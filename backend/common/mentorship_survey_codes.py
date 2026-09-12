"""Survey answers as stored, translated into the codes the matcher reads.

Two callers share these tables: the matching payload builder and the legacy CSV
export. They query separately -- the payload is a subset of the export's columns
with different types -- but a code that means one thing in one and another thing
in the other is the failure this module exists to prevent.

Each "Frontend label" line is the exact text in MentorshipRegistrationDialog.jsx,
so a wording change there is visibly a change here too.
"""

# Mentor -- career_transition. The stored key already matches the code.
#   none   "No. My undergraduate background was already in the CS field."
#   path_a "Yes, Path A: Non-CS undergraduate background -> CS master's degree -> technical role."
#   path_b "Yes, Path B: Non-CS undergraduate background -> transitioned into a technical role
#           after several years of work experience."
#   other  "Other: Please briefly describe."
CAREER_TRANSITION_CODES = {"none", "path_a", "path_b"}

# Mentor -- development_region, stored under survey.region.
#   us / canada / china / other ("Other region: Please specify.")
DEVELOPMENT_REGION_CODES = {"us", "canada", "china"}

# Mentor -- external_mentoring_exp.
#   none   "No"
#   1_to_3 "1-3 mentoring experiences"
#   3_plus "More than 3 mentoring experiences"
#
# The question asks about mentoring done *outside* the CircleCat program, so it
# answers nothing about rounds run here. The bucket is the whole answer: the form
# offers three, and no finer number was ever collected. An earlier export mapped
# these to midpoint integers (2 and 4) and match rationales printed the midpoint
# as a precise count.
EXTERNAL_MENTORING_EXP_CODES = {"none", "1_to_3", "3_plus"}

# Mentee -- transition_type, stored under survey.current_background.
#   cs_grad          "All degrees within the CS field, currently following a technical
#                     job-search path."
#   non_cs_cs_master "Non-CS undergraduate background, currently pursuing or recently
#                     completed a CS master's degree, looking for a first technical role."
#   non_tech_to_tech "Have previous non-technical work experience and aiming to transition
#                     into a technical role."
#   non_cs_starting  "Non-CS undergraduate background, have not started transitioning into
#                     CS yet, but are considering getting started."
#   other            "Other: Please specify."
TRANSITION_TYPE_MAP = {
    "cs_grad": "none",
    "non_cs_cs_master": "path_a",
    "non_tech_to_tech": "path_b",
    "non_cs_starting": "considering",
}

# Mentee -- mentee_stage, stored on the participant row as current_stage.
#   job_searching      "Currently job searching / preparing for job applications."
#   employed_growing   "Currently employed, hoping to grow / advance in my career."
#   changing_direction "Hoping to switch tracks / transition into a different field."
#   grad_school        "Planning for graduate school / applications."
MENTEE_STAGE_MAP = {
    "job_searching": "job_searching",
    "employed_growing": "employed_growth",
    "changing_direction": "career_switch",
    "grad_school": "grad_planning",
}

# Mentee -- urgency, stored on the participant row as time_urgency.
#   within_3_months "Need support within 3 months."
#   within_6_months "Within 6 months."
#   1_year_plus     "More than 1 year; long-term planning."
#   no_timeline     "No clear timeline yet."
URGENCY_MAP = {
    "within_3_months": "3m",
    "within_6_months": "6m",
    "1_year_plus": "1y_plus",
    "no_timeline": "none",
}

# Mentee -- job_market_region, stored under survey.target_region.
JOB_MARKET_REGION_CODES = {"us", "canada", "china"}

# Mentor -- prev_mentoring_exp, for the legacy CSV export only. The matching
# payload carries the bucket instead; see EXTERNAL_MENTORING_EXP_CODES.
PREV_MENTORING_EXP_MAP = {"none": 0, "1_to_3": 2, "3_plus": 4}


def code_or_none(value: str | None, valid_codes: set[str]) -> str | None:
    """Return the stored key when it is a known code, else None.

    "other" and anything unrecognised resolve to None; the free text that goes
    with "other" travels in its own field rather than inside this one.
    """
    value = (value or "").strip()
    return value if value in valid_codes else None


def mapped_code_or_none(value: str | None, code_map: dict[str, str]) -> str | None:
    """Translate a stored key into its code, or None when it has no translation."""
    return code_map.get((value or "").strip())


def other_text_or_none(value: str | None, other_text: str | None) -> str | None:
    """Return the free text, but only when "other" was actually chosen."""
    if (value or "").strip() != "other":
        return None
    return (other_text or "").strip() or None
