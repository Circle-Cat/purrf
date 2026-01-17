import pandas as pd
import sys
import os
import asyncio
import traceback
import io
import requests
import json
import uuid
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from backend.entity.users_entity import UsersEntity
from backend.entity.experience_entity import ExperienceEntity
from backend.entity.preference_entity import PreferenceEntity
from backend.entity.mentorship_round_entity import MentorshipRoundEntity
from backend.entity.mentorship_round_participants_entity import (
    MentorshipRoundParticipantsEntity,
)
from backend.common.mentorship_enums import CommunicationMethod, UserTimezone
from backend.common.database import Database
from backend.repository.users_repository import UsersRepository
from backend.repository.experience_repository import ExperienceRepository
from backend.repository.preferences_repository import PreferencesRepository
from backend.repository.mentorship_round_repository import MentorshipRoundRepository
from backend.common.logger import get_logger
from backend.common.mentorship_enums import (
    ParticipantRole,
    ApprovalStatus,
)

logger = get_logger()

DEFAULT_DATE_STR = "1970-01-01"

TIMEZONE_MAP = {
    "PST": UserTimezone.AMERICA_LOS_ANGELES,
    "EST": UserTimezone.AMERICA_NEW_YORK,
    "MST": UserTimezone.AMERICA_DENVER,
    "GMT": UserTimezone.ASIA_SHANGHAI,
}

COMM_MAP = {
    "email": CommunicationMethod.EMAIL,
    "google_chat": CommunicationMethod.GOOGLE_CHAT,
    None: CommunicationMethod.EMAIL,
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

INDUSTRY_MAP = {
    "Software Engineering": "swe",
    "Data Science": "ds",
    "Machine Learning": "ds",
    "Product Management": "pm",
    "Technical Program Management": "pm",
    "UI/UX Design": "uiux",
}


def load_dataframe_from_path(path: str) -> pd.DataFrame:
    """
    Load a pandas DataFrame from a local file path or a remote HTTP(S) URL.

    The function supports CSV and Excel files. Remote URLs are always treated
    as CSV files. Local files are loaded based on their file extension.

    - CSV files are read using UTF-8 with BOM support.
    - Excel files (.xls, .xlsx) are read using the openpyxl engine.
    - All NaN values are converted to None for downstream compatibility.

    Args:
        path (str): Local filesystem path or HTTP(S) URL to a CSV or Excel file.

    Returns:
        pd.DataFrame: Loaded DataFrame with NaN values replaced by None.

    Raises:
        FileNotFoundError: If the local file path does not exist.
        ValueError: If the file extension is not supported.
        requests.HTTPError: If the HTTP request fails.
        pandas.errors.ParserError: If the file content cannot be parsed.
    """
    if path.startswith("http://") or path.startswith("https://"):
        resp = requests.get(path)
        resp.raise_for_status()
        df = pd.read_csv(io.StringIO(resp.text), encoding="utf-8-sig")
    else:
        if not os.path.exists(path):
            raise FileNotFoundError(path)
        if path.lower().endswith((".xlsx", ".xls")):
            df = pd.read_excel(path, engine="openpyxl")
        elif path.lower().endswith(".csv"):
            df = pd.read_csv(path, encoding="utf-8-sig")
        else:
            raise ValueError("Unsupported file type")
    df = df.where(pd.notnull(df), None)
    return df


class MentorshipImportService:
    """
    Service responsible for importing mentorship-related users from tabular data.

    This service supports:
    - Upserting mentor and mentee users into the database
    - Normalizing user profile fields (timezone, communication channel, emails)
    - Handling partial or malformed rows gracefully with logging

    It operates within an async SQLAlchemy session and delegates all persistence
    operations to repository classes.
    """

    def __init__(self, user_repo, exp_repo, pref_repo, round_repo):
        """
        Initialize the mentorship import service.

        Args:
            user_repo: Repository responsible for user persistence operations.
            exp_repo: Repository responsible for experience-related persistence.
            pref_repo: Repository responsible for preferences-related persistence.
            round_repo: Repository responsible for rounds-related persistence.
        """
        self.user_repo = user_repo
        self.exp_repo = exp_repo
        self.pref_repo = pref_repo
        self.round_repo = round_repo

    async def _upsert_user_base(
        self, session: AsyncSession, email: str, data: dict
    ) -> UsersEntity:
        """
        Create or update a user entity based on email and provided profile data.

        If the user does not already exist, a new UsersEntity is created with
        a manually generated subject identifier. The user is always marked
        as active and as having mentorship mentor experience.

        Args:
            session (AsyncSession): Active database session.
            email (str): Primary email address identifying the user.
            data (dict): Normalized user profile data.

        Returns:
            UsersEntity: The upserted user entity.
        """
        email = email.strip().lower()
        user = await self.user_repo.get_user_by_primary_email(session, email)

        if not user:
            user = UsersEntity(primary_email=email)
            user.subject_identifier = f"manual|{email}"

        user.first_name = data.get("first_name")
        user.last_name = data.get("last_name")
        user.preferred_name = data.get("preferred_name")
        user.linkedin_link = data.get("linkedin")
        user.is_active = data.get("is_active")

        user.timezone = self._parse_timezone(data.get("timezone"))
        user.communication_channel = data.get("comm_channel", CommunicationMethod.EMAIL)
        user.timezone_updated_at = datetime(1970, 1, 1, tzinfo=timezone.utc)
        user.has_mentorship_mentor_experience = True

        if data.get("alt_emails"):
            user.alternative_emails = data["alt_emails"]

        return await self.user_repo.upsert_users(session, user)

    def _parse_timezone(self, tz_string: str) -> UserTimezone:
        """
        Parse a human-readable timezone string into a UserTimezone enum.

        The function strips extra annotations (e.g., "(GMT-8)") and defaults
        to America/Los_Angeles when parsing fails or input is invalid.

        Args:
            tz_string (str): Raw timezone string from input data.

        Returns:
            UserTimezone: Parsed timezone enum.
        """
        if not tz_string or not isinstance(tz_string, str):
            return UserTimezone.AMERICA_LOS_ANGELES

        clean_tz = tz_string.split("(")[0].strip().upper()

        return TIMEZONE_MAP.get(clean_tz, UserTimezone.AMERICA_LOS_ANGELES)

    def _parse_date_to_iso(self, value) -> str | None:
        """
        Normalize various date-like inputs to ISO date string (YYYY-MM-DD).

        Returns None if value is empty, NaN, or invalid.
        """
        if value is None or pd.isna(value):
            return None

        try:
            return pd.to_datetime(value).date().isoformat()
        except Exception:
            return None

    def _parse_skillsets_to_dict(self, skillset_str: str) -> dict:
        """
        Parse a raw skillset string into a boolean dictionary.

        The input string is expected to be a comma-separated list of skillset keys.
        Each known skillset is mapped to a boolean flag indicating whether it
        was selected by the user.

        If the input is empty or NaN, all skillset flags will be set to False.

        Example:
            Input: "resumeGuidance, networking"
            Output: {
                "resume_guidance": True,
                "networking": True,
                ...
            }

        Args:
            skillset_str: Raw skillset string from the source data

        Return:
            Dictionary mapping skillset columns to boolean values
        """
        result = {col: False for col in SKILLSET_COL_MAP.values()}
        if not skillset_str or pd.isna(skillset_str):
            return result
        items = [i.strip() for i in str(skillset_str).split(",")]
        for item in items:
            if item in SKILLSET_COL_MAP:
                result[SKILLSET_COL_MAP[item]] = True
        return result

    def _parse_industries_to_fixed_dict(self, industry_str: str) -> dict:
        """
        Parse a raw industry string into a fixed industry boolean dictionary.

        The returned dictionary always contains the same set of industry keys
        (swe, uiux, ds, pm), each mapped to a boolean value.

        The input may contain comma- or semicolon-separated values.
        Unknown industries are ignored.

        If the input is empty or NaN, all industries will be set to False.

        Args:
            industry_str: Raw industry string from the source data

        Return:
            Dictionary with fixed industry keys and boolean values
        """

        result = {"swe": False, "uiux": False, "ds": False, "pm": False}
        if not industry_str or pd.isna(industry_str):
            return result
        raw_items = [i.strip() for i in str(industry_str).replace(";", ",").split(",")]
        for item in raw_items:
            key = INDUSTRY_MAP.get(item)
            if key in result:
                result[key] = True
        return result

    async def _upsert_experience_data(
        self, session: AsyncSession, user_id: int, row: pd.Series
    ):
        """
        Parse and upsert education and work history data for a user.

        Education and work history are parsed from raw user data.
        If both education and work history are missing or invalid,
        the function exits without making any database changes.

        Any existing experience record will be updated; otherwise,
        a new experience entity will be created.

        Parsing errors are logged and do not interrupt the overall sync flow.

        Args:
            session: Active async database session
            user_id: ID of the user whose experience data is being synced
            row: Pandas Series containing raw user data
        """
        raw_edu_str = row.get("education") or row.get("mentee.education")
        past_history_raw = row.get("past_work_history")

        formatted_edu_list: list[dict] = []
        formatted_work_list: list[dict] = []

        # Education
        if raw_edu_str and not pd.isna(raw_edu_str):
            try:
                edu_data = (
                    json.loads(raw_edu_str)
                    if isinstance(raw_edu_str, str)
                    else raw_edu_str
                )

                for item in edu_data:
                    formatted_edu_list.append({
                        "id": str(uuid.uuid4()),
                        "degree": item.get("degree"),
                        "school": item.get("school") or "",
                        "field_of_study": item.get("field_of_study") or "",
                        "start_date": self._parse_date_to_iso(item.get("start_date"))
                        or DEFAULT_DATE_STR,
                        "end_date": self._parse_date_to_iso(item.get("end_date"))
                        or DEFAULT_DATE_STR,
                    })
            except (json.JSONDecodeError, TypeError) as e:
                logger.warning(
                    "Failed to parse education data for user %s: %s",
                    user_id,
                    e,
                )

        # Work History
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
                        "start_date": self._parse_date_to_iso(entry.get("start_date"))
                        or DEFAULT_DATE_STR,
                        "end_date": self._parse_date_to_iso(entry.get("end_date")),
                        "is_current_job": entry.get("end_date")
                        in [None, "Present", "present"],
                    })
            except (json.JSONDecodeError, TypeError) as e:
                logger.warning(
                    "Failed to parse work history for user %s: %s",
                    user_id,
                    e,
                )

        # Early Return
        if not formatted_edu_list and not formatted_work_list:
            logger.debug(
                "No experience data found for user %s, skipping upsert",
                user_id,
            )
            return

        # Upsert
        experience = await self.exp_repo.get_experience_by_user_id(session, user_id)
        if not experience:
            experience = ExperienceEntity(user_id=user_id)

        experience.education = formatted_edu_list
        experience.work_history = formatted_work_list

        await self.exp_repo.upsert_experience(session, experience)

    async def _upsert_preference(
        self, session: AsyncSession, user_id: int, skillset_raw: str, industry_raw: str
    ):
        """
        Parse and upsert user preference data.

        This method converts raw skillset and industry strings into
        structured preference fields and persists them to the database.

        Existing preference records are updated; otherwise, a new
        preference entity is created.

        Any parsing or persistence error is logged and re-raised
        to ensure upstream visibility.

        Args:
            session: Active async database session
            user_id: ID of the user whose preferences are being synced
            skillset_raw: Raw skillset string
            industry_raw: Raw industry string
        """

        try:
            pref = await self.pref_repo.get_preferences_by_user_id(session, user_id)
            if not pref:
                pref = PreferenceEntity(user_id=user_id)

            skill_bools = self._parse_skillsets_to_dict(skillset_raw)
            for attr, value in skill_bools.items():
                setattr(pref, attr, value)

            pref.specific_industry = self._parse_industries_to_fixed_dict(industry_raw)
            await self.pref_repo.upsert_preference(session, pref)
        except Exception as e:
            logger.error(f"Error syncing preferences for user_id {user_id}: {e}")
            raise e

    async def sync_next_round_participants_from_row(
        self, session: AsyncSession, df: pd.DataFrame, participant_role: ParticipantRole
    ):
        """
        Sync participant records for the next mentorship round from a DataFrame.

        This method imports participants into the predefined next round
        ("2026 1st round") for users whose `r1_2026_enrolled` value is "YES".

        Args:
            session (AsyncSession): Active async SQLAlchemy session.
            df (pd.DataFrame): Source data containing user emails, matched partner
                information, and retention feedback.
            participant_role (ParticipantRole): Role of the participant in the round
                (e.g. mentor or mentee).

        Behavior:
            - Looks up the round ID for the hard-coded next round name ("2026 1st round").
            - Resolves users and partners via primary email.
            - Creates `MentorshipRoundParticipantsEntity` records with expected and
            unexpected partner preferences.

        Logging:
            - Logs an error if the target round cannot be found.
            - Logs warnings when a user or partner cannot be resolved.

        Returns:
            None
        """
        # Get round id by name
        round_stmt = select(MentorshipRoundEntity.round_id).where(
            MentorshipRoundEntity.name == "2026 1st round"
        )
        round_result = await session.execute(round_stmt)
        round_id = round_result.scalar_one_or_none()

        if not round_id:
            logger.error("Error: Round '2026 1st round' not found.")
            return

        participants: list[MentorshipRoundParticipantsEntity] = []
        for _, row in df.iterrows():
            # Check if the current user is willing to enroll in the next round
            next_round_enroll = row.get("r1_2026_enrolled")
            if (
                pd.isna(next_round_enroll)
                or str(next_round_enroll).strip().lower() != "yes"
            ):
                continue

            # Get user_id by primary_email using the repository
            email_raw = (
                row.get("primary_email")
                or row.get("mentee_profile.primary_email")
                or ""
            )
            if pd.isna(email_raw) or not str(email_raw).strip():
                continue

            email = str(email_raw).strip().lower()
            # Parse retention feedback
            partner_email = row.get("2025 3rd - Matched Mentee Email") or row.get(
                "2025 3rd Round - Matched Mentor Email"
            )
            retention_feedback = row.get("2025 3rd - Retention Feedback") or row.get(
                "2025 3rd Round - Retention Feedback"
            )

            user = await self.user_repo.get_user_by_primary_email(session, email)

            if not user:
                logger.warning(
                    f"Mentor {email} not found in database. Skipping round participation."
                )
                continue

            expected_partner_user_id = None
            unexpected_partner_user_id = None

            if pd.notna(partner_email):
                partner_user = await self.user_repo.get_user_by_primary_email(
                    session, partner_email.strip().lower()
                )

                if partner_user:
                    # Logic: if they want to continue, add to expected; if they want someone else, add to unexpected
                    if retention_feedback == "Continue with my current mentor/mentee":
                        expected_partner_user_id = [partner_user.user_id]
                    elif (
                        retention_feedback
                        == "Be matched with a different mentor/mentee"
                    ):
                        unexpected_partner_user_id = [partner_user.user_id]

            # 3. Create Participation Entity
            new_participant = MentorshipRoundParticipantsEntity(
                round_id=round_id,
                user_id=user.user_id,
                participant_role=participant_role,
                expected_partner_user_id=expected_partner_user_id or [],
                unexpected_partner_user_id=unexpected_partner_user_id or [],
                approval_status=ApprovalStatus.SIGNED_UP,
            )
            participants.append(new_participant)

        session.add_all(participants)

    async def sync_mentor_users_from_row(self, session: AsyncSession, df: pd.DataFrame):
        """
        Import mentor users from a DataFrame.

        Each row is treated as an independent mentor record. Errors in individual
        rows are logged and do not halt the import process.

        Args:
            session (AsyncSession): Active database session.
            df (pd.DataFrame): Mentor data loaded from CSV or Excel.
        """
        for index, row in df.iterrows():
            try:
                user_data = {
                    "first_name": row["first_name"],
                    "last_name": row["last_name"],
                    "preferred_name": row["preferred_name"],
                    "linkedin": row.get("linkedIn"),
                    "timezone": row.get("timezone"),
                    "comm_channel": COMM_MAP.get(row.get("preferred_comms_channel")),
                    "is_active": row.get("eligible"),
                }
                user = await self._upsert_user_base(
                    session, row["primary_email"], user_data
                )
                await self._upsert_experience_data(session, user.user_id, row)
                await self._upsert_preference(
                    session,
                    user.user_id,
                    row.get("skillsets"),
                    row.get("mentoring_field"),
                )

            except Exception as e:
                logger.error(
                    f"Error importing mentor at row {index} ({row.get('primary_email')}): {e}"
                )

    async def sync_mentee_users_from_row(self, session: AsyncSession, df: pd.DataFrame):
        """
        Import mentee users from a DataFrame.

        Rows missing a primary email are skipped. Alternative emails are parsed
        from comma-separated strings when present.

        Args:
            session (AsyncSession): Active database session.
            df (pd.DataFrame): Mentee data loaded from CSV or Excel.
        """
        for index, row in df.iterrows():
            try:
                email = row.get("mentee_profile.primary_email")
                if not email or pd.isna(email):
                    continue

                alt_emails = row.get("mentee_profile.alternative_emails")
                user_data = {
                    "first_name": row.get("mentee_profile.first_name"),
                    "last_name": row.get("mentee_profile.last_name"),
                    "preferred_name": row.get("mentee_profile.preferred_name"),
                    "linkedin": row.get("mentee_profile.linkedin"),
                    "timezone": row.get("mentee_profile.timezone"),
                    "alt_emails": [e.strip() for e in str(alt_emails).split(",")]
                    if pd.notna(alt_emails)
                    else [],
                    "is_active": row.get("mentee_profile.eligible"),
                }
                user = await self._upsert_user_base(session, email, user_data)
                await self._upsert_experience_data(session, user.user_id, row)

                skill_col = "2025 3rd Round - skillsets"
                industry_col = "2025 3rd Round - Which specific industry or field are you most interested in?"
                await self._upsert_preference(
                    session, user.user_id, row.get(skill_col), row.get(industry_col)
                )
            except Exception as e:
                logger.error(f"Error importing mentee at row {index} ({email}): {e}")

    async def sync_rounds_from_row(
        self,
        session: AsyncSession,
        df: pd.DataFrame,
    ):
        """
        Sync mentorship round definitions from a DataFrame.

        Each row represents a mentorship round and will be upserted into the database.
        Rows without a valid round name are skipped.

        Timeline-related date fields are normalized into ISO date strings and stored
        as a JSON object in the `description` column.
        """

        for _, row in df.iterrows():
            name = row.get("name")
            if not name or pd.isna(name):
                continue

            timeline = {
                "promotion_start_at": self._parse_date_to_iso(
                    row.get("promotion_start_at")
                ),
                "application_deadline_at": self._parse_date_to_iso(
                    row.get("application_deadline_at")
                ),
                "review_start_at": self._parse_date_to_iso(row.get("review_start_at")),
                "acceptance_notification_at": self._parse_date_to_iso(
                    row.get("acceptance_notification_at")
                ),
                "matching_completed_at": self._parse_date_to_iso(
                    row.get("matching_completed_at")
                ),
                "match_notification_at": self._parse_date_to_iso(
                    row.get("match_notification_at")
                ),
                "first_meeting_deadline_at": self._parse_date_to_iso(
                    row.get("first_meeting_deadline_at")
                ),
                "meetings_completion_deadline_at": self._parse_date_to_iso(
                    row.get("meetings_completion_deadline_at")
                ),
                "feedback_deadline_at": self._parse_date_to_iso(
                    row.get("feedback_deadline_at")
                ),
            }

            required_meetings = row.get("required_meetings") or 5

            round_entity = MentorshipRoundEntity(
                name=name,
                required_meetings=int(required_meetings),
                description=timeline,
            )
            await self.round_repo.upsert_round(session=session, entity=round_entity)


async def main():
    """
    Entry point for the mentorship import script.

    This function:
    - Initializes the database connection
    - Loads mentor and mentee CSV files
    - Performs user upserts within a single transactional session
    - Commits on success or rolls back on failure
    """
    logger.info("Script started...")
    db = Database(echo=True)
    service = MentorshipImportService(
        user_repo=UsersRepository(),
        exp_repo=ExperienceRepository(),
        pref_repo=PreferencesRepository(),
        round_repo=MentorshipRoundRepository(),
    )

    mentor_path = "backend/backfill/Mentor.csv"
    mentee_path = "backend/backfill/Mentee.csv"
    rounds_path = "backend/backfill/Rounds.csv"

    async with db.session() as session:
        try:
            df_rounds = load_dataframe_from_path(rounds_path)
            await service.sync_rounds_from_row(session, df_rounds)

            df_mentor = load_dataframe_from_path(mentor_path)
            await service.sync_mentor_users_from_row(session, df_mentor)

            df_mentee = load_dataframe_from_path(mentee_path)
            await service.sync_mentee_users_from_row(session, df_mentee)

            await service.sync_next_round_participants_from_row(
                session, df_mentor, ParticipantRole.MENTOR
            )
            await service.sync_next_round_participants_from_row(
                session, df_mentee, ParticipantRole.MENTEE
            )

            await session.commit()
            logger.info("Import successful!")
        except Exception as e:
            await session.rollback()
            logger.warning(f"Global Import Failure: {e}")


if __name__ == "__main__":
    try:
        asyncio.run(main())
        logger.info("--- SCRIPT FINISHED SUCCESSFULLY ---")
    except Exception as e:
        logger.info(f"\nCRITICAL ERROR DURING EXECUTION: {e}")
        traceback.print_exc()
        sys.exit(1)
