import pandas as pd
import sys
import os
import asyncio
import traceback
import io
import requests
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession

from backend.entity.users_entity import UsersEntity
from backend.common.mentorship_enums import CommunicationMethod, UserTimezone
from backend.common.database import Database
from backend.repository.users_repository import UsersRepository
from backend.repository.experience_repository import ExperienceRepository
from backend.common.logger import get_logger

logger = get_logger()

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

    def __init__(self, user_repo, exp_repo):
        """
        Initialize the mentorship import service.

        Args:
            user_repo: Repository responsible for user persistence operations.
            exp_repo: Repository responsible for experience-related persistence.
        """
        self.user_repo = user_repo
        self.exp_repo = exp_repo

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
        user.is_active = True

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
                }
                await self._upsert_user_base(session, row["primary_email"], user_data)

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
                }
                await self._upsert_user_base(session, email, user_data)

            except Exception as e:
                logger.error(f"Error importing mentee at row {index} ({email}): {e}")


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

    service = MentorshipImportService(UsersRepository(), ExperienceRepository())

    mentor_path = "backend/backfill/Mentor.csv"
    mentee_path = "backend/backfill/Mentee.csv"

    async with db.session() as session:
        try:
            df_mentor = load_dataframe_from_path(mentor_path)
            await service.sync_mentor_users_from_row(session, df_mentor)
            await session.flush()

            df_mentee = load_dataframe_from_path(mentee_path)
            await service.sync_mentee_users_from_row(session, df_mentee)

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
