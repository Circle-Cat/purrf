import pandas as pd
import asyncio
import os
import io
import sys
import requests
import traceback
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from backend.entity.mentorship_round_entity import MentorshipRoundEntity
from backend.entity.mentorship_pairs_entity import MentorshipPairsEntity
from backend.entity.mentorship_round_participants_entity import (
    MentorshipRoundParticipantsEntity,
)
from backend.entity.users_entity import UsersEntity
from backend.common.database import Database
from backend.common.mentorship_enums import (
    PairStatus,
    MentorActionStatus,
    MenteeActionStatus,
    ApprovalStatus,
)
from backend.common.logger import get_logger

logger = get_logger()


def load_dataframe_from_path(path: str) -> pd.DataFrame:
    """
    Load a pandas DataFrame from a local file path or a remote URL.

    Supports CSV (local/remote) and Excel (local only, .xlsx).
    NaN values are converted to None.

    Args:
        path (str): Local path or HTTP(S) URL.

    Returns:
        pd.DataFrame: Loaded DataFrame with NaN values replaced by None.

    Raises:
        FileNotFoundError: If local file path does not exist.
        ValueError: If file extension is not supported.
        requests.HTTPError: If the HTTP request fails.
    """
    if path.startswith(("http://", "https://")):
        logger.info(f"Downloading remote file from: {path}")
        resp = requests.get(path)
        resp.raise_for_status()
        df = pd.read_csv(io.StringIO(resp.text), encoding="utf-8-sig")
    else:
        if not os.path.exists(path):
            raise FileNotFoundError(f"File not found: {path}")
        if path.lower().endswith(".xlsx"):
            df = pd.read_excel(path, engine="openpyxl")
        elif path.lower().endswith(".csv"):
            df = pd.read_csv(path, encoding="utf-8-sig")
        else:
            raise ValueError("Unsupported file type. Use .csv or .xlsx.")

    return df.where(pd.notnull(df), None)


class PairsBackfillService:
    """
    Service responsible for synchronizing mentor-mentee pairing data
    from source files to the database.

    - Performs bulk insert (not upsert) of pair data.
    - Validates email to user mapping strictly (fails on missing users).
    - Operations are performed directly on the Session for batch efficiency.
    """

    def __init__(self, round_name: str):
        """Initialize the pairs backfill service.

        Args:
            round_name (str): The name of the mentorship round target.
        """
        self.round_name = round_name

    async def _get_round_id_by_name(self, session: AsyncSession) -> int | None:
        """Retrieves the round ID for the configured round name."""
        result = await session.execute(
            select(MentorshipRoundEntity.round_id).where(
                MentorshipRoundEntity.name == self.round_name
            )
        )
        return result.scalar_one_or_none()

    async def _get_user_ids_by_email(
        self, session: AsyncSession, emails: list
    ) -> pd.DataFrame:
        """
        Batch queries user IDs for a list of emails.

        Args:
            session: (AsyncSession): SQLAlchemy session for database interaction.
            emails (list): List of mentor and mentee primary emails.

        Returns:
            pd.DataFrame: DataFrame with columns ['user_id', 'primary_email'].
        """
        result = await session.execute(
            select(UsersEntity.user_id, UsersEntity.primary_email).where(
                UsersEntity.primary_email.in_(emails)
            )
        )

        return pd.DataFrame(result.fetchall(), columns=["user_id", "primary_email"])

    async def _update_approval_status(
        self, session: AsyncSession, round_id: int, user_ids: list
    ):
        """
        Updates the approval status of participants to 'MATCHED' for the given round and user IDs.

        Args:
            session (AsyncSession): SQLAlchemy session for database interaction.
            round_id (int): The ID of the mentorship round.
            user_ids (List[int]): List of user IDs to update.
        """
        await session.execute(
            update(MentorshipRoundParticipantsEntity)
            .where(MentorshipRoundParticipantsEntity.round_id == round_id)
            .where(MentorshipRoundParticipantsEntity.user_id.in_(user_ids))
            .values(approval_status=ApprovalStatus.MATCHED)
        )

    def _parse_pairs_to_dataframe(
        self, df: pd.DataFrame, round_id: int, email_to_id: dict[str, int]
    ) -> pd.DataFrame:
        """
        Maps emails to user IDs and formats data for database insertion.

        Args:
            df (pd.DataFrame): Source data with 'mentor/mentee primary email'.
            round_id (int): The ID of the mentorship round.
            email_to_id (Dict[str, int]): Mapping from email to user_id.

        Returns:
            pd.DataFrame: DataFrame ready for insertion into the mentorship_pairs table.

        Raises:
            ValueError: If any email in the CSV cannot be found in the database.
        """
        df["mentor_id"] = df["mentor primary email"].map(email_to_id)
        df["mentee_id"] = df["mentee primary email"].map(email_to_id)

        missing_mask = df["mentor_id"].isna() | df["mentee_id"].isna()

        if missing_mask.any():
            missing_rows = df[missing_mask][
                ["mentor primary email", "mentee primary email"]
            ].to_dict(orient="records")

            logger.error(
                f"Validation Failed: The following users were not found in DB:\n{missing_rows}"
            )
            raise ValueError(
                "Aborting: Cannot backfill pairs because some users do not exist in the database."
            )

        pairs_df = df.assign(
            round_id=round_id,
            completed_count=0,
            status=PairStatus.ACTIVE,
            mentor_action_status=MentorActionStatus.PENDING,
            mentee_action_status=MenteeActionStatus.PENDING,
            recommendation_reason=df["reason"].str.slice(0, 300),
        )[
            [
                "round_id",
                "mentor_id",
                "mentee_id",
                "completed_count",
                "status",
                "mentor_action_status",
                "mentee_action_status",
                "recommendation_reason",
            ]
        ]
        return pairs_df

    async def backfill_pairs(self, session: AsyncSession, df: pd.DataFrame):
        """
        Backfill mentor-mentee pairs into the database.

        Args:
            session (AsyncSession): SQLAlchemy session for database interaction.
            df (pd.DataFrame): DataFrame containing the mentor-mentee pairs data.

        Raises:
            Exception: If an error occurs during the backfill operation, the exception is raised.
        """
        try:
            round_id = await self._get_round_id_by_name(session=session)
            if round_id is None:
                logger.warning(f"Round '{self.round_name}' not found.")
                raise ValueError(
                    f"Round '{self.round_name}' not found. Cannot continue."
                )

            emails = (
                pd.concat([
                    df["mentor primary email"],
                    df["mentee primary email"],
                ])
                .dropna()
                .drop_duplicates()
                .tolist()
            )
            df_users = await self._get_user_ids_by_email(session, emails)
            email_to_id = dict(zip(df_users["primary_email"], df_users["user_id"]))

            pairs_df = self._parse_pairs_to_dataframe(
                df=df, round_id=round_id, email_to_id=email_to_id
            )
            await session.execute(
                MentorshipPairsEntity.__table__.insert(),
                pairs_df.to_dict(orient="records"),
            )

            user_ids = (
                pd.concat([df["mentor_id"], df["mentee_id"]]).drop_duplicates().tolist()
            )
            await self._update_approval_status(session, round_id, user_ids)

            logger.info(
                f"Successfully inserted mentorship pairs for {self.round_name}."
            )

        except Exception as e:
            logger.error(f"Error in backfill operation: {e}")
            raise


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

    pairs_path = "backend/backfill/Matching_result.csv"
    round_name = "2026 1st round"

    service = PairsBackfillService(round_name=round_name)

    async with db.session() as session:
        try:
            df = load_dataframe_from_path(pairs_path)
            await service.backfill_pairs(session=session, df=df)
            await session.commit()
            logger.info("--- SCRIPT FINISHED SUCCESSFULLY ---")
        except Exception as e:
            logger.error(f"Error during script execution: {e}")
            await session.rollback()
            raise


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as e:
        logger.info(f"\nCRITICAL ERROR DURING EXECUTION: {e}")
        traceback.print_exc()
        sys.exit(1)
