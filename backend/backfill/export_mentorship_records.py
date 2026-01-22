import pandas as pd
import asyncio
import os
from datetime import datetime
from sqlalchemy import select, union_all
from backend.entity.users_entity import UsersEntity
from backend.entity.experience_entity import ExperienceEntity
from backend.entity.preference_entity import PreferenceEntity
from backend.entity.mentorship_round_participants_entity import (
    MentorshipRoundParticipantsEntity,
)
from backend.common.database import Database
from backend.common.mentorship_enums import ParticipantRole
from backend.common.logger import get_logger

logger = get_logger()

SKILLSET_COL_MAP = {
    "resume_guidance": "Resume/LinkedIn Profile",
    "career_path_guidance": "Career Path Guidance",
    "experience_sharing": "Experience Sharing",
    "industry_trends": "Industry Trends",
    "technical_skills": "Technical Skills Development",
    "soft_skills": "Soft Skills Enhancement",
    "networking": "Networking",
    "project_management": "Project Management",
}

INDUSTRY_MAP = {
    "swe": "Software Engineering",
    "ds": "Data Science/ML",
    "pm": "Product/Program Management",
    "uiux": "UI/UX Design",
}


def _format_date(date_str: str) -> str:
    """Formats date to 'MMM YYYY' and hides '1970-01-01'."""
    if not date_str or date_str == "1970-01-01":
        return ""
    try:
        return datetime.strptime(date_str, "%Y-%m-%d").strftime("%b %Y")
    except Exception:
        return date_str


def _get_edu_summary(edu_list: list) -> str:
    """Format education history in a compact."""
    if not edu_list:
        return ""

    items = []
    for e in edu_list:
        start = _format_date(e.get("start_date"))
        end = _format_date(e.get("end_date"))

        date_range = f" ({start} - {end})" if start or end else ""

        items.append(
            f"{e.get('degree')} in {e.get('field_of_study')}, {e.get('school')}{date_range}"
        )

    return "\n".join(items)


def _get_work_summary(work_list: list) -> str:
    """Format work history in a compact, readable style."""
    if not work_list:
        return ""

    items = []
    for w in work_list:
        start = _format_date(w.get("start_date"))
        end = "Present" if w.get("is_current_job") else _format_date(w.get("end_date"))
        date_range = f" ({start} - {end})" if start or end else ""

        items.append(
            f"{w.get('title')}, {w.get('company_or_organization')}{date_range}"
        )

    return "\n".join(items)


def _format_id_list(id_list: list[int] | None) -> str:
    """Formats expected or unexpected partner user id."""
    if not id_list:
        return ""
    return ", ".join(map(str, id_list))


async def fetch_participants_data(
    session, round_id
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Fetches active participant data for a specific round and separates them into
    Mentor and Mentee DataFrames.

    This method will filters all active users, distinguishes between internal and externel
    users base on their primary email, ensuring all internal users are included in the
    export, even if they have not signed up for the current round.
    External users are only included if they have explicitly signed up for the specified round.

    Args:
        session (AsyncSession): The active database session used to execute the query.
        round_id (int): The specific ID of the mentorship round to filter participants.

    Returns:
        tuple[pd.DataFrame, pd.DataFrame]:
            - Dataframe contains data for Mentors.
            - Dataframe contains data for Mentees.
    """
    stmt_circlecat = (
        select(
            UsersEntity,
            MentorshipRoundParticipantsEntity,
            ExperienceEntity,
            PreferenceEntity,
        )
        .outerjoin(
            MentorshipRoundParticipantsEntity,
            (UsersEntity.user_id == MentorshipRoundParticipantsEntity.user_id)
            & (MentorshipRoundParticipantsEntity.round_id == round_id),
        )
        .outerjoin(ExperienceEntity, UsersEntity.user_id == ExperienceEntity.user_id)
        .outerjoin(PreferenceEntity, UsersEntity.user_id == PreferenceEntity.user_id)
        .where(UsersEntity.is_active.is_(True))
        .where(UsersEntity.primary_email.like("%circlecat.org"))
    )

    stmt_external = (
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
        .where(UsersEntity.primary_email.not_like("%circlecat.org"))
    )

    union_stmt = select(
        UsersEntity,
        MentorshipRoundParticipantsEntity,
        ExperienceEntity,
        PreferenceEntity,
    ).from_statement(union_all(stmt_circlecat, stmt_external))

    rows = (await session.execute(union_stmt)).all()

    export_mentors = []
    export_mentees = []

    for user, part, exp, pref in rows:
        if part:
            is_mentor = part.participant_role == ParticipantRole.MENTOR
            goal = part.goal if part.goal is not None else ""
            expected_partners = _format_id_list(part.expected_partner_user_id)
            unexpected_partners = _format_id_list(part.unexpected_partner_user_id)
            max_partners = (
                part.max_partners if part and part.max_partners is not None else 1
            )
        else:
            is_mentor = False
            goal = ""
            expected_partners = []
            unexpected_partners = []
            max_partners = 1

        active_skills = (
            [
                name
                for col, name in SKILLSET_COL_MAP.items()
                if getattr(pref, col, False)
            ]
            if pref
            else []
        )
        active_industries = (
            [
                INDUSTRY_MAP.get(k, k)
                for k, v in (pref.specific_industry or {}).items()
                if v
            ]
            if pref
            else []
        )

        skills_header = "Areas of Expertise" if is_mentor else "Preferred Skills"
        industry_header = (
            "Mentoring Industries" if is_mentor else "Preferred Industries"
        )

        prefix = {
            "User ID": user.user_id,
            "Preferred Name": user.preferred_name,
            "Timezone": user.timezone.value if user.timezone else "",
            skills_header: ", ".join(active_skills),
            industry_header: ", ".join(active_industries),
            "Education Background": _get_edu_summary(exp.education) if exp else "",
        }

        suffix = {
            "Goal": goal,
            "Preferred Partners": expected_partners,
            "Excluded Partners": unexpected_partners,
            "Max Partners": max_partners,
        }

        if is_mentor:
            export_mentors.append({
                **prefix,
                "Work Experience": _get_work_summary(exp.work_history) if exp else "",
                **suffix,
            })
        else:
            export_mentees.append({**prefix, **suffix})

    return pd.DataFrame(export_mentors), pd.DataFrame(export_mentees)


async def main():
    """Entry point for the mentor export script."""
    logger.info("Starting Mentor Export...")

    base_dir = os.getenv("BUILD_WORKSPACE_DIRECTORY")

    mentor_path = os.path.join(base_dir, "backend/backfill/Mentor_export.csv")
    mentee_path = os.path.join(base_dir, "backend/backfill/Mentee_export.csv")

    db = Database(echo=False)

    async with db.session() as session:
        try:
            df_mentor, df_mentee = await fetch_participants_data(session, round_id=1)

            if not df_mentor.empty:
                df_mentor.to_csv(mentor_path, index=False, encoding="utf-8-sig")
                logger.info(
                    f"Successfully exported {len(df_mentor)} mentors to {mentor_path}"
                )
            else:
                logger.warning("No mentor data found.")

            if not df_mentee.empty:
                df_mentee.to_csv(mentee_path, index=False, encoding="utf-8-sig")
                logger.info(
                    f"Successfully exported {len(df_mentee)} mentees to {mentee_path}"
                )
            else:
                logger.warning("No mentee data found.")

        except Exception as e:
            logger.error(f"Export failed: {e}")
            raise e


if __name__ == "__main__":
    asyncio.run(main())
