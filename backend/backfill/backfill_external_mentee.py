import asyncio
import csv
import os
import sys
import traceback
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from backend.common.database import Database
from backend.common.logger import get_logger
from backend.common.mentorship_enums import (
    ApprovalStatus,
    CommunicationMethod,
    ParticipantRole,
    TrainingCategory,
    TrainingStatus,
    UserTimezone,
)
from backend.entity.experience_entity import ExperienceEntity
from backend.entity.mentorship_round_entity import MentorshipRoundEntity
from backend.entity.mentorship_round_participants_entity import (
    MentorshipRoundParticipantsEntity,
)
from backend.entity.preference_entity import PreferenceEntity
from backend.entity.training_entity import TrainingEntity
from backend.entity.users_entity import UsersEntity

logger = get_logger()


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
INDUSTRY_KEYS = ["swe", "ds", "pm", "uiux"]

_TIMEZONE_MAP = {e.value: e for e in UserTimezone}
_TRAINING_STATUS_MAP = {e.value: e for e in TrainingStatus}
DEFAULT_DATETIME_UTC = datetime(1970, 1, 1, tzinfo=timezone.utc)


def _read_csv(path: str) -> list[dict]:
    with open(path, encoding="utf-8-sig") as f:
        return [row for row in csv.DictReader(f) if any(row.values())]


def _parse_timezone(raw: str) -> UserTimezone:
    tz = _TIMEZONE_MAP.get(raw.strip())
    if tz is None:
        raise ValueError(f"Unknown timezone: {raw!r}")
    return tz


def _parse_training_status(raw: str) -> TrainingStatus:
    status = _TRAINING_STATUS_MAP.get(raw.strip())
    if status is None:
        raise ValueError(f"Unknown training status: {raw!r}")
    return status


def _parse_datetime_optional(raw: str) -> datetime | None:
    raw = raw.strip()
    return datetime.fromisoformat(raw) if raw else None


def _parse_skills(raw: str) -> dict[str, bool]:
    tags = {s.strip() for s in raw.split(",") if s.strip()}
    return {col: (col in tags) for col in SKILLSET_COLUMNS}


def _parse_industry(raw: str) -> dict[str, bool]:
    tags = {s.strip() for s in raw.split(",") if s.strip()}
    return {key: (key in tags) for key in INDUSTRY_KEYS}


def _parse_alternative_emails(raw: str) -> list[str] | None:
    emails = [e.strip() for e in raw.split(",") if e.strip()]
    return emails if emails else None


def _parse_bool(raw: str) -> bool:
    return raw.strip().lower() in {"true", "1", "yes"}


async def list_rounds(session) -> list[MentorshipRoundEntity]:
    """Returns all mentorship rounds ordered by round_id descending."""
    stmt = select(MentorshipRoundEntity).order_by(MentorshipRoundEntity.round_id.desc())
    return list((await session.execute(stmt)).scalars())


def prompt_round_selection(rounds: list[MentorshipRoundEntity]) -> int | None:
    """Prints available rounds and prompts the user to pick one by index.
    Returns the round_id of the chosen round, or None if the user aborts."""
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
            f"\nEnter an index 1-{len(rounds)} to import (or 'q' to quit): "
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
    """Entry point for the external mentee import script."""
    logger.info("Starting External Mentee Import...")

    base_dir = os.getenv("BUILD_WORKSPACE_DIRECTORY")
    user_info_and_preferences_path = os.path.join(
        base_dir, "backend/backfill/External_mentee_user_info_preferences.csv"
    )
    education_path = os.path.join(
        base_dir, "backend/backfill/External_mentee_education.csv"
    )
    work_history_path = os.path.join(
        base_dir, "backend/backfill/External_mentee_work_history.csv"
    )

    user_info_and_preferences = _read_csv(user_info_and_preferences_path)
    if not user_info_and_preferences:
        logger.error("No data rows found in %s", user_info_and_preferences_path)
        return
    logger.info("Loaded %d row(s) from user info CSV", len(user_info_and_preferences))

    edu_by_email: dict[str, list[dict]] = {}
    for row in _read_csv(education_path):
        email = row["primary_email"].strip().lower()
        edu_by_email.setdefault(email, []).append({
            k: v for k, v in row.items() if k != "primary_email"
        })
    logger.info("Loaded education data for %d user(s)", len(edu_by_email))

    work_by_email: dict[str, list[dict]] = {}
    for row in _read_csv(work_history_path):
        email = row["primary_email"].strip().lower()
        work_data = {k: v for k, v in row.items() if k != "primary_email"}
        work_data["is_current_job"] = _parse_bool(work_data.get("is_current_job", ""))
        work_by_email.setdefault(email, []).append(work_data)
    logger.info("Loaded work history data for %d user(s)", len(work_by_email))

    db = Database(echo=False)
    try:
        # Short-lived session before the blocking input(), avoids idle connection timeout.
        async with db.session() as session:
            rounds = await list_rounds(session)

        round_id = prompt_round_selection(rounds)
        if round_id is None:
            logger.info("No round selected, aborting import.")
            return

        selected_round = next(r for r in rounds if r.round_id == round_id)
        deadline_str = (selected_round.description or {}).get("application_deadline_at")
        if not deadline_str:
            raise ValueError(
                f"Round '{selected_round.name}' has no application_deadline_at in description."
            )
        training_deadline = datetime.fromisoformat(deadline_str) + timedelta(days=2)
        logger.info(
            "Selected round: '%s' (round_id=%d), training deadline: %s",
            selected_round.name,
            round_id,
            training_deadline.isoformat(),
        )

        async with db.session() as session:
            emails = [
                row["primary_email"].strip().lower()
                for row in user_info_and_preferences
            ]

            existing_users: dict[str, UsersEntity] = {
                u.primary_email: u
                for u in (
                    await session.execute(
                        select(UsersEntity).where(UsersEntity.primary_email.in_(emails))
                    )
                ).scalars()
            }
            # Upsert users, collect (row, user) user_rows
            user_rows: list[tuple[dict, UsersEntity]] = []
            for row in user_info_and_preferences:
                email = row["primary_email"].strip().lower()
                user = existing_users.get(email)
                if user is None:
                    user = UsersEntity(
                        primary_email=email,
                    )
                    session.add(user)

                user.first_name = row["first_name"].strip()
                user.last_name = row["last_name"].strip()
                user.preferred_name = row.get("preferred_name", "").strip() or None
                user.timezone = _parse_timezone(row["timezone"])
                user.timezone_updated_at = DEFAULT_DATETIME_UTC
                user.communication_channel = CommunicationMethod.EMAIL
                user.linkedin_link = row.get("linkedin_link", "").strip() or None
                user.alternative_emails = _parse_alternative_emails(
                    row.get("alternative_emails", "")
                )
                user.is_active = True
                user_rows.append((row, user))

            await session.flush()

            all_user_ids = [u.user_id for _, u in user_rows]

            # Bulk-fetch related records for all users
            existing_training: dict[int, TrainingEntity] = {
                t.user_id: t
                for t in (
                    await session.execute(
                        select(TrainingEntity).where(
                            TrainingEntity.user_id.in_(all_user_ids),
                            TrainingEntity.category
                            == TrainingCategory.MENTORSHIP_MENTEE_ONBOARDING,
                        )
                    )
                ).scalars()
            }
            existing_prefs: dict[int, PreferenceEntity] = {
                p.user_id: p
                for p in (
                    await session.execute(
                        select(PreferenceEntity).where(
                            PreferenceEntity.user_id.in_(all_user_ids)
                        )
                    )
                ).scalars()
            }
            existing_exp: dict[int, ExperienceEntity] = {
                e.user_id: e
                for e in (
                    await session.execute(
                        select(ExperienceEntity).where(
                            ExperienceEntity.user_id.in_(all_user_ids)
                        )
                    )
                ).scalars()
            }
            existing_participants: set[int] = {
                p.user_id
                for p in (
                    await session.execute(
                        select(MentorshipRoundParticipantsEntity).where(
                            MentorshipRoundParticipantsEntity.round_id == round_id,
                            MentorshipRoundParticipantsEntity.user_id.in_(all_user_ids),
                        )
                    )
                ).scalars()
            }

            # Upsert training / prefs / experience / participant
            for row, user in user_rows:
                email = user.primary_email
                training = existing_training.get(user.user_id)
                if training is None:
                    training = TrainingEntity(
                        user_id=user.user_id,
                        category=TrainingCategory.MENTORSHIP_MENTEE_ONBOARDING,
                    )
                    session.add(training)
                training.status = _parse_training_status(row["mentee_training_status"])
                training.completed_timestamp = _parse_datetime_optional(
                    row.get("training_completed_timestamp", "")
                )
                training.deadline = training_deadline

                pref = existing_prefs.get(user.user_id)
                if pref is None:
                    pref = PreferenceEntity(user_id=user.user_id)
                    session.add(pref)
                for col, val in _parse_skills(row.get("interested_skills", "")).items():
                    setattr(pref, col, val)
                pref.specific_industry = _parse_industry(
                    row.get("specific_industry", "")
                )

                raw_edu = edu_by_email.get(email)
                raw_work = work_by_email.get(email)
                if not raw_edu and not raw_work:
                    logger.warning(
                        "No education or work history found for %s, skipping", email
                    )
                else:
                    exp = existing_exp.get(user.user_id)
                    if exp is None:
                        exp = ExperienceEntity(user_id=user.user_id)
                        session.add(exp)
                    exp.education = (
                        [{"id": str(uuid.uuid4()), **e} for e in raw_edu]
                        if raw_edu
                        else None
                    )
                    exp.work_history = (
                        [{"id": str(uuid.uuid4()), **w} for w in raw_work]
                        if raw_work
                        else None
                    )
                if user.user_id not in existing_participants:
                    session.add(
                        MentorshipRoundParticipantsEntity(
                            user_id=user.user_id,
                            round_id=round_id,
                            participant_role=ParticipantRole.MENTEE,
                            approval_status=ApprovalStatus.SIGNED_UP,
                            max_partners=1,
                        )
                    )

            await session.commit()
            logger.info(
                "Successfully imported %d mentee(s) into round: %s",
                len(user_info_and_preferences),
                selected_round.name,
            )
    except Exception as e:
        logger.error("Import failed: %s", e)
        raise
    finally:
        await db.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
        logger.info("--- SCRIPT FINISHED SUCCESSFULLY ---")
    except Exception as e:
        logger.info("CRITICAL ERROR: %s", e)
        traceback.print_exc()
        sys.exit(1)
