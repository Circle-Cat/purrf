import pandas as pd
import sys
import os
import asyncio
import traceback
from datetime import datetime, timezone, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

import json
import uuid
from backend.entity.users_entity import UsersEntity
from backend.entity.training_entity import TrainingEntity
from backend.entity.preference_entity import PreferenceEntity
from backend.entity.experience_entity import ExperienceEntity
from backend.common.mentorship_enums import (
    CommunicationMethod,
    UserTimezone,
    TrainingCategory,
    TrainingStatus,
)
from backend.common.database import Database
from backend.repository.users_repository import UsersRepository
from backend.repository.preferences_repository import PreferencesRepository
from backend.repository.experience_repository import ExperienceRepository
from backend.common.logger import get_logger


logger = get_logger()

DEFAULT_DATETIME_UTC = datetime(1970, 1, 1, tzinfo=timezone.utc)
PST = timezone(timedelta(hours=-8))
PDT = timezone(timedelta(hours=-7))

TIMEZONE_MAP = {
    "PST": UserTimezone.AMERICA_LOS_ANGELES,
    "EST": UserTimezone.AMERICA_NEW_YORK,
    "MST": UserTimezone.AMERICA_DENVER,
    "GMT": UserTimezone.ASIA_SHANGHAI,
}

INDUSTRY_COL = (
    "2026 2nd Round - Which specific industry or field are you most interested in?"
)
SKILLSET_COL = "2026 2nd Round - Skillsets"


INDUSTRY_MAP = {
    "Software Engineering": "swe",
    "Data Science": "ds",
    "Machine Learning": "ds",
    "Product Management": "pm",
    "Technical Program Management": "pm",
    "UI/UX Design": "uiux",
    "AI multi-agent system": "ds",
}

SKILLSET_COL_MAP = {
    "Resume/LinkedIn Profile": "resume_guidance",
    "Career Path Guidance": "career_path_guidance",
    "Experience Sharing": "experience_sharing",
    "Industry Trends": "industry_trends",
    "Technical Skills Development": "technical_skills",
    "Technical Skills": "technical_skills",
    "Soft Skills Enhancement": "soft_skills",
    "Soft Skills": "soft_skills",
    "Networking": "networking",
    "Project Management": "project_management",
}


def load_dataframe_from_path(path: str) -> pd.DataFrame:
    if not os.path.exists(path):
        raise FileNotFoundError(path)
    if path.lower().endswith((".xlsx", ".xls")):
        df = pd.read_excel(path, engine="openpyxl")
    elif path.lower().endswith(".csv"):
        df = pd.read_csv(path, encoding="utf-8-sig")
    else:
        raise ValueError("Unsupported file type")
    return df.where(pd.notnull(df), None)


DEFAULT_DATE_STR = "1970-01-01"


def _parse_date_to_iso(value) -> str | None:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    try:
        return pd.to_datetime(value).date().isoformat()
    except Exception:
        return None


def _parse_timezone(tz_string: str) -> UserTimezone:
    if not tz_string or not isinstance(tz_string, str):
        return UserTimezone.AMERICA_LOS_ANGELES
    clean_tz = tz_string.split("(")[0].strip().upper()
    return TIMEZONE_MAP.get(clean_tz, UserTimezone.AMERICA_LOS_ANGELES)


def _parse_deadline(deadline_str) -> datetime | None:
    if not deadline_str or pd.isna(deadline_str):
        return None
    s = str(deadline_str).strip()
    if "PST" in s:
        tz = PST
        clean = s.replace(" PST", "").strip()
    elif "PDT" in s:
        tz = PDT
        clean = s.replace(" PDT", "").strip()
    else:
        logger.warning("Missing timezone in deadline: %s", deadline_str)
        return None
    try:
        return (
            datetime.strptime(clean, "%Y-%m-%d %H:%M")
            .replace(tzinfo=tz)
            .astimezone(timezone.utc)
        )
    except ValueError:
        logger.warning("Failed to parse deadline: %s", deadline_str)
        return None


def _parse_skillsets_to_dict(skillset_str: str) -> dict:
    result = {col: False for col in SKILLSET_COL_MAP.values()}
    if not skillset_str or pd.isna(skillset_str):
        return result
    items = [i.strip() for i in str(skillset_str).split(",")]
    for item in items:
        if item in SKILLSET_COL_MAP:
            result[SKILLSET_COL_MAP[item]] = True
    return result


def _parse_industries_to_fixed_dict(industry_str: str) -> dict:
    result = {"swe": False, "uiux": False, "ds": False, "pm": False}
    if not industry_str or pd.isna(industry_str):
        return result
    raw_items = [i.strip() for i in str(industry_str).replace(";", ",").split(",")]
    for item in raw_items:
        key = INDUSTRY_MAP.get(item)
        if key in result:
            result[key] = True
    return result


async def upsert_preference(
    session: AsyncSession, pref_repo, user_id: int, skillset_raw: str, industry_raw: str
):
    pref = await pref_repo.get_preferences_by_user_id(session, user_id)
    if not pref:
        pref = PreferenceEntity(user_id=user_id)

    skill_bools = _parse_skillsets_to_dict(skillset_raw)
    for attr, value in skill_bools.items():
        setattr(pref, attr, value)

    pref.specific_industry = _parse_industries_to_fixed_dict(industry_raw)
    await pref_repo.upsert_preference(session, pref)


async def upsert_experience(
    session: AsyncSession, exp_repo, user_id: int, row: pd.Series
):
    raw_edu_str = row.get("education")
    past_history_raw = row.get("past_work_history")

    formatted_edu_list: list[dict] = []
    formatted_work_list: list[dict] = []

    if raw_edu_str and not pd.isna(raw_edu_str):
        try:
            edu_data = (
                json.loads(raw_edu_str) if isinstance(raw_edu_str, str) else raw_edu_str
            )
            for item in edu_data:
                formatted_edu_list.append({
                    "id": str(uuid.uuid4()),
                    "degree": item.get("degree"),
                    "school": item.get("school") or "",
                    "field_of_study": item.get("field_of_study") or "",
                    "start_date": _parse_date_to_iso(item.get("start_date"))
                    or DEFAULT_DATE_STR,
                    "end_date": _parse_date_to_iso(item.get("end_date"))
                    or DEFAULT_DATE_STR,
                })
        except (json.JSONDecodeError, TypeError) as e:
            logger.warning("Failed to parse education for user %s: %s", user_id, e)

    if past_history_raw and not pd.isna(past_history_raw):
        try:
            past_history = (
                json.loads(past_history_raw)
                if isinstance(past_history_raw, str)
                else past_history_raw
            )
            for entry in past_history:
                formatted_work_list.append({
                    "id": str(uuid.uuid4()),
                    "title": entry.get("title"),
                    "company_or_organization": entry.get("company"),
                    "start_date": _parse_date_to_iso(entry.get("start_date"))
                    or DEFAULT_DATE_STR,
                    "end_date": _parse_date_to_iso(entry.get("end_date")),
                    "is_current_job": entry.get("end_date")
                    in [None, "Present", "present"],
                })
        except (json.JSONDecodeError, TypeError) as e:
            logger.warning("Failed to parse work history for user %s: %s", user_id, e)

    if not formatted_edu_list and not formatted_work_list:
        return

    experience = await exp_repo.get_experience_by_user_id(session, user_id)
    if not experience:
        experience = ExperienceEntity(user_id=user_id)

    experience.education = formatted_edu_list
    experience.work_history = formatted_work_list
    await exp_repo.upsert_experience(session, experience)


async def upsert_user(
    session: AsyncSession, users_repo, email: str, data: dict
) -> UsersEntity:
    email = email.strip().lower()
    user = await users_repo.get_user_by_primary_email(session, email)

    if not user:
        user = UsersEntity(primary_email=email)
        user.subject_identifier = f"manual|{email}"

    user.first_name = data.get("first_name")
    user.last_name = data.get("last_name")
    user.preferred_name = data.get("preferred_name")
    user.linkedin_link = data.get("linkedin")
    user.is_active = data.get("is_active")
    user.timezone = _parse_timezone(data.get("timezone"))
    user.communication_channel = CommunicationMethod.EMAIL
    user.timezone_updated_at = DEFAULT_DATETIME_UTC
    if data.get("alt_emails"):
        user.alternative_emails = data["alt_emails"]

    return await users_repo.upsert_users(session, user)


async def upsert_training(session: AsyncSession, user_id: int, row: pd.Series):
    category_raw = row.get("category")
    status_raw = row.get("status")
    deadline_raw = row.get("deadline")
    completed_raw = row.get("completed_timestamp")

    if not category_raw or pd.isna(category_raw):
        return

    try:
        category = TrainingCategory(str(category_raw).strip())
    except ValueError:
        logger.warning(
            "Unknown training category '%s' for user %s, skipping",
            category_raw,
            user_id,
        )
        return

    try:
        status = (
            TrainingStatus(str(status_raw).strip())
            if status_raw and not pd.isna(status_raw)
            else TrainingStatus.TO_DO
        )
    except ValueError:
        logger.warning(
            "Unknown training status '%s' for user %s, defaulting to TO_DO",
            status_raw,
            user_id,
        )
        status = TrainingStatus.TO_DO
    deadline = _parse_deadline(deadline_raw)
    completed_timestamp = DEFAULT_DATETIME_UTC
    if completed_raw and not pd.isna(completed_raw):
        try:
            completed_timestamp = (
                pd.to_datetime(completed_raw)
                .to_pydatetime()
                .replace(tzinfo=timezone.utc)
            )
        except Exception:
            pass

    stmt = select(TrainingEntity).where(
        TrainingEntity.user_id == user_id,
        TrainingEntity.category == category,
    )
    result = await session.execute(stmt)
    existing = result.scalar_one_or_none()

    if existing:
        existing.status = status
        existing.deadline = deadline
        existing.completed_timestamp = completed_timestamp
    else:
        session.add(
            TrainingEntity(
                user_id=user_id,
                category=category,
                status=status,
                deadline=deadline,
                completed_timestamp=completed_timestamp,
            )
        )

    await session.flush()


async def main():
    logger.info("Script started...")
    db = Database(echo=True)
    users_repo = UsersRepository()
    pref_repo = PreferencesRepository()
    exp_repo = ExperienceRepository()

    mentee_path = "backend/backfill/Mentee.csv"

    async with db.session() as session:
        try:
            df = load_dataframe_from_path(mentee_path)

            for index, row in df.iterrows():
                email_raw = row.get("primary_email")
                if not email_raw or pd.isna(email_raw):
                    logger.warning("Row %s missing primary_email, skipping", index)
                    continue

                try:
                    alt_emails_raw = row.get("alternative_emails")
                    user_data = {
                        "first_name": row.get("first_name"),
                        "last_name": row.get("last_name"),
                        "preferred_name": row.get("preferred_name"),
                        "linkedin": row.get("linkedin"),
                        "timezone": row.get("timezone"),
                        "alt_emails": [
                            e.strip() for e in str(alt_emails_raw).split(",")
                        ]
                        if pd.notna(alt_emails_raw)
                        else [],
                        "is_active": row.get("eligible"),
                    }
                    user = await upsert_user(
                        session, users_repo, str(email_raw), user_data
                    )
                    await upsert_experience(session, exp_repo, user.user_id, row)
                    await upsert_preference(
                        session,
                        pref_repo,
                        user.user_id,
                        row.get(SKILLSET_COL),
                        row.get(INDUSTRY_COL),
                    )
                    await upsert_training(session, user.user_id, row)

                except Exception as e:
                    logger.error("Error at row %s (%s): %s", index, email_raw, e)

            await session.commit()
            logger.info("Import successful!")
        except Exception as e:
            await session.rollback()
            logger.error("Global import failure: %s", e)


if __name__ == "__main__":
    try:
        asyncio.run(main())
        logger.info("--- SCRIPT FINISHED SUCCESSFULLY ---")
    except Exception as e:
        logger.info("CRITICAL ERROR: %s", e)
        traceback.print_exc()
        sys.exit(1)
