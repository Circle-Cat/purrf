import pandas as pd
import asyncio
import json
import os
from sqlalchemy import select
from backend.entity.users_entity import UsersEntity
from backend.entity.experience_entity import ExperienceEntity
from backend.entity.preference_entity import PreferenceEntity
from backend.entity.mentorship_round_participants_entity import (
    MentorshipRoundParticipantsEntity,
)
from backend.entity.mentorship_round_entity import MentorshipRoundEntity
from backend.common.database import Database
from backend.common.mentorship_enums import ParticipantRole
from backend.common.logger import get_logger

logger = get_logger()

# Skill columns from PreferenceEntity. Order matches the export template.
# Emitted as `t`/`f` per the matching-data spec.
SKILLSET_COLUMNS = [
    "resume_guidance",
    "career_path_guidance",
    "experience_sharing",
    "industry_trends",
    "technical_skills",
    "soft_skills",
    "networking",
    "project_management",
]

# specific_industry is emitted as a JSON object with all four keys present.
INDUSTRY_KEYS = ["swe", "ds", "pm", "uiux"]

# ─── Survey encodings ───────────────────────────────────────────────────────
# Each map below translates a backend storage key into the matching-data spec
# code emitted in the CSV. The "Frontend label" lines are the exact text shown
# in MentorshipRegistrationDialog.jsx so the mapping stays auditable.

# Mentor — career_transition (backend key already matches spec code)
#   none   "No. My undergraduate background was already in the CS field."
#   path_a "Yes, Path A: Non-CS undergraduate background → CS master's degree → technical role."
#   path_b "Yes, Path B: Non-CS undergraduate background → transitioned into a technical role after several years of work experience."
#   other  "Other: Please briefly describe."
CAREER_TRANSITION_CODES = {"none", "path_a", "path_b"}

# Mentor — development_region (backend stores under survey.region)
#   us     "United States"
#   canada "Canada"
#   china  "China"
#   other  "Other region: Please specify."
DEVELOPMENT_REGION_CODES = {"us", "canada", "china"}

# Mentor — prev_mentoring_exp (backend external_mentoring_exp → spec midpoint integer)
#   none   "No"                                  → 0
#   1_to_3 "1-3 mentoring experiences"           → 2
#   3_plus "More than 3 mentoring experiences"   → 4
PREV_MENTORING_EXP_MAP = {"none": 0, "1_to_3": 2, "3_plus": 4}

# Mentee — transition_type (backend stores under survey.current_background)
#   cs_grad          "All degrees within the CS field, currently following a technical job-search path."
#   non_cs_cs_master "Non-CS undergraduate background, currently pursuing or recently completed a CS master's degree, looking for a first technical role."
#   non_tech_to_tech "Have previous non-technical work experience and aiming to transition into a technical role."
#   non_cs_starting  "Non-CS undergraduate background, have not started transitioning into CS yet, but are considering getting started."
#   other            "Other: Please specify."
TRANSITION_TYPE_MAP = {
    "cs_grad": "none",
    "non_cs_cs_master": "path_a",
    "non_tech_to_tech": "path_b",
    "non_cs_starting": "considering",
}

# Mentee — mentee_stage (backend round_pref.current_stage)
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

# Mentee — urgency (backend round_pref.time_urgency)
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

# Mentee — job_market_region (backend survey.target_region)
#   us, canada, china, other  — same labels as REGION_OPTIONS on the mentor side.
JOB_MARKET_REGION_CODES = {"us", "canada", "china"}


MENTOR_COLUMNS = [
    "user_id",
    "first_name",
    "last_name",
    "preferred_name",
    "primary_email",
    "timezone",
    "communication_channel",
    "linkedin_link",
    *SKILLSET_COLUMNS,
    "specific_industry",
    "max_partners",
    "expected_partner_user_id",
    "unexpected_partner_user_id",
    "goal",
    "education",
    "work_history",
    "career_transition",
    "development_region",
    "prev_mentoring_exp",
]

MENTEE_COLUMNS = [
    "user_id",
    "first_name",
    "last_name",
    "preferred_name",
    "timezone",
    "communication_channel",
    "primary_email",
    "alternative_emails",
    "linkedin_link",
    *SKILLSET_COLUMNS,
    "specific_industry",
    "expected_partner_user_id",
    "unexpected_partner_user_id",
    "goal",
    "education",
    "work_history",
    "transition_type",
    "mentee_stage",
    "urgency",
    "job_market_region",
]


def _bool_to_tf(value) -> str:
    return "t" if value else "f"


def _format_id_list(id_list: list[int] | None) -> str:
    if not id_list:
        return ""
    return ", ".join(map(str, id_list))


def _join_emails(emails: list[str] | None) -> str:
    if not emails:
        return ""
    return ", ".join(emails)


def _industry_object(specific_industry: dict | None) -> str:
    src = specific_industry or {}
    obj = {key: bool(src.get(key, False)) for key in INDUSTRY_KEYS}
    return json.dumps(obj, ensure_ascii=False)


def _json_records(records: list | None, date_keys: tuple[str, ...]) -> str:
    """Serializes education / work_history as a JSON array, dropping
    1970-xx-xx placeholder dates so the consumer does not need to filter them."""
    if not records:
        return ""
    cleaned = []
    for record in records:
        item = dict(record)
        for key in date_keys:
            value = item.get(key)
            if isinstance(value, str) and value.startswith("1970-"):
                item[key] = None
        cleaned.append(item)
    return json.dumps(cleaned, ensure_ascii=False)


def _encode_other(
    value: str | None,
    valid_codes: set[str],
    other_text: str | None,
) -> str:
    """Encodes a survey radio whose spec form is either a fixed code or `other:<text>`."""
    if not value:
        return ""
    if value in valid_codes:
        return value
    if value == "other":
        return f"other:{other_text or ''}"
    return value


def _encode_mapped_other(
    value: str | None,
    code_map: dict[str, str],
    other_text: str | None,
) -> str:
    """Like _encode_other, but with a translation table from backend keys to spec codes."""
    if not value:
        return ""
    if value in code_map:
        return code_map[value]
    if value == "other":
        return f"other:{other_text or ''}"
    return value


async def fetch_participants_data(
    session, round_id
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Fetches participant data for a specific round and separates them into
    Mentor and Mentee DataFrames using the matching-data spec encoding
    (snake_case columns, `t`/`f` flags, JSON nested fields).

    Only users (internal or external) who have an active registration for the
    given round are included. Users without a row in
    mentorship_round_participants for this round are excluded.

    Args:
        session (AsyncSession): The active database session.
        round_id (int): The mentorship round to filter participants on.

    Returns:
        tuple[pd.DataFrame, pd.DataFrame]: (mentors_df, mentees_df) in template order.
    """
    stmt = (
        select(
            UsersEntity,
            MentorshipRoundParticipantsEntity,
            ExperienceEntity,
            PreferenceEntity,
        )
        .join(
            MentorshipRoundParticipantsEntity,
            (UsersEntity.user_id == MentorshipRoundParticipantsEntity.user_id)
            & (MentorshipRoundParticipantsEntity.round_id == round_id),
        )
        .outerjoin(ExperienceEntity, UsersEntity.user_id == ExperienceEntity.user_id)
        .outerjoin(PreferenceEntity, UsersEntity.user_id == PreferenceEntity.user_id)
        .where(UsersEntity.is_active.is_(True))
    )

    rows = (await session.execute(stmt)).all()

    export_mentors = []
    export_mentees = []

    for user, part, exp, pref in rows:
        is_mentor = bool(part and part.participant_role == ParticipantRole.MENTOR)
        survey = (pref.profile_survey or {}) if pref else {}

        skill_cells = {
            col: _bool_to_tf(getattr(pref, col, False) if pref else False)
            for col in SKILLSET_COLUMNS
        }

        base = {
            "user_id": user.user_id,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "preferred_name": user.preferred_name or "",
            "timezone": user.timezone.value if user.timezone else "",
            "communication_channel": (
                user.communication_channel.value if user.communication_channel else ""
            ),
            "primary_email": user.primary_email,
            "linkedin_link": user.linkedin_link or "",
            **skill_cells,
            "specific_industry": _industry_object(
                pref.specific_industry if pref else None
            ),
            "expected_partner_user_id": (
                _format_id_list(part.expected_partner_user_id) if part else ""
            ),
            "unexpected_partner_user_id": (
                _format_id_list(part.unexpected_partner_user_id) if part else ""
            ),
            "goal": (part.goal or "") if part else "",
            "education": _json_records(
                exp.education if exp else None, ("start_date", "end_date")
            ),
            "work_history": _json_records(
                exp.work_history if exp else None, ("start_date", "end_date")
            ),
        }

        if is_mentor:
            export_mentors.append({
                **base,
                "max_partners": (
                    part.max_partners if part and part.max_partners is not None else 1
                ),
                "career_transition": _encode_other(
                    survey.get("career_transition"),
                    CAREER_TRANSITION_CODES,
                    survey.get("career_transition_other"),
                ),
                "development_region": _encode_other(
                    survey.get("region"),
                    DEVELOPMENT_REGION_CODES,
                    survey.get("region_other"),
                ),
                "prev_mentoring_exp": PREV_MENTORING_EXP_MAP.get(
                    survey.get("external_mentoring_exp") or "", ""
                ),
            })
        else:
            export_mentees.append({
                **base,
                "alternative_emails": _join_emails(user.alternative_emails),
                "transition_type": _encode_mapped_other(
                    survey.get("current_background"),
                    TRANSITION_TYPE_MAP,
                    survey.get("current_background_other"),
                ),
                "mentee_stage": MENTEE_STAGE_MAP.get(
                    (part.current_stage or "") if part else "", ""
                ),
                "urgency": URGENCY_MAP.get(
                    (part.time_urgency or "") if part else "", ""
                ),
                "job_market_region": _encode_other(
                    survey.get("target_region"),
                    JOB_MARKET_REGION_CODES,
                    survey.get("target_region_other"),
                ),
            })

    df_mentors = pd.DataFrame(export_mentors, columns=MENTOR_COLUMNS)
    df_mentees = pd.DataFrame(export_mentees, columns=MENTEE_COLUMNS)
    return df_mentors, df_mentees


async def list_rounds(session) -> list[MentorshipRoundEntity]:
    """Returns all mentorship rounds ordered by round_id descending."""
    stmt = select(MentorshipRoundEntity).order_by(MentorshipRoundEntity.round_id.desc())
    return list((await session.execute(stmt)).scalars())


def prompt_round_selection(rounds: list[MentorshipRoundEntity]) -> int | None:
    """Prints available rounds and prompts the user to pick one by index.
    Returns the round_id of the chosen row, or None if the user aborts."""
    if not rounds:
        print("No mentorship rounds found in the database.")
        return None

    print("\nAvailable mentorship rounds:")
    print(f"{'Index':<6} Name")
    print("-" * 60)
    for index, round_row in enumerate(rounds, start=1):
        print(f"{index:<6} {round_row.name}")

    while True:
        choice = input(
            f"\nEnter an index 1-{len(rounds)} to export (or 'q' to quit): "
        ).strip()
        if choice.lower() in {"q", "quit", "exit"}:
            return None
        if not choice.isdigit():
            print("Please enter a number.")
            continue
        value = int(choice)
        if 1 <= value <= len(rounds):
            return rounds[value - 1].round_id
        print(f"Index out of range, must be between 1 and {len(rounds)}.")


async def main():
    """Entry point for the mentor export script."""
    logger.info("Starting Mentor Export...")

    base_dir = os.getenv("BUILD_WORKSPACE_DIRECTORY")

    db = Database(echo=False)

    try:
        # Use a short-lived session for the round list; the pooled connection
        # cannot stay open while we wait on the blocking input() prompt — Neon
        # closes idle connections after ~30s, which would crash the next query.
        async with db.session() as session:
            rounds = await list_rounds(session)

        round_id = prompt_round_selection(rounds)
        if round_id is None:
            logger.info("No round selected, aborting export.")
            return

        logger.info("Exporting round_id=%s", round_id)
        mentor_path = os.path.join(
            base_dir, f"backend/backfill/Mentor_export_round_{round_id}.csv"
        )
        mentee_path = os.path.join(
            base_dir, f"backend/backfill/Mentee_export_round_{round_id}.csv"
        )

        async with db.session() as session:
            df_mentor, df_mentee = await fetch_participants_data(
                session, round_id=round_id
            )

        # Always write both files with the full template header, even when a
        # role has zero participants in the round, so consumers can rely on
        # the column set being present.
        df_mentor.to_csv(mentor_path, index=False, encoding="utf-8-sig")
        logger.info("Exported %d mentors to %s", len(df_mentor), mentor_path)
        if df_mentor.empty:
            logger.warning("Mentor CSV written with header only — no mentors found.")

        df_mentee.to_csv(mentee_path, index=False, encoding="utf-8-sig")
        logger.info("Exported %d mentees to %s", len(df_mentee), mentee_path)
        if df_mentee.empty:
            logger.warning("Mentee CSV written with header only — no mentees found.")
    except Exception as e:
        logger.error("Export failed: %s", e)
        raise
    finally:
        await db.close()


if __name__ == "__main__":
    asyncio.run(main())
