import re

from sqlalchemy.ext.asyncio import AsyncSession

from backend.common.onboarding_guide_enums import GuideProgressStatus
from backend.dto.guide_progress_dto import GuideProgressDto

# Snoozing a guide this many times counts as dismissing it.
MAX_GUIDE_SNOOZES = 3

GUIDE_KEY_PATTERN = re.compile(r"[a-z0-9-]{1,64}")

_FINAL_STATUSES = (GuideProgressStatus.COMPLETED, GuideProgressStatus.DISMISSED)


class GuideProgressService:
    """Reads and records which onboarding guides a user has finished, dismissed or snoozed.

    Called straight from the controller, so it commits its own writes.
    """

    def __init__(self, user_guide_progress_repository):
        """
        Args:
            user_guide_progress_repository (UserGuideProgressRepository):
                Guide progress data access.
        """
        self.user_guide_progress_repository = user_guide_progress_repository

    async def list_for_user(
        self, session: AsyncSession, user_id: int
    ) -> list[GuideProgressDto]:
        """List every guide the user has a record for.

        Args:
            session (AsyncSession): The active async database session.
            user_id (int): The caller.

        Returns:
            list[GuideProgressDto]: One entry per guide the user has finished,
            dismissed or snoozed; a guide never seen is absent.
        """
        rows = await self.user_guide_progress_repository.list_by_user(session, user_id)
        return [GuideProgressDto.model_validate(row) for row in rows]

    async def record(
        self,
        session: AsyncSession,
        user_id: int,
        guide_key: str,
        status: GuideProgressStatus,
    ) -> GuideProgressDto:
        """Record what the user just did with one guide, and commit it.

        Completing or dismissing overwrites whatever was there. Snoozing adds
        one to the count and becomes a dismissal at ``MAX_GUIDE_SNOOZES``.
        A snooze arriving for a guide already completed or dismissed changes
        nothing, count included, and the stored row is returned as it is: a
        tour closed in a second tab must not reopen a guide the user is done
        with.

        Args:
            session (AsyncSession): The active async database session.
            user_id (int): The caller.
            guide_key (str): The guide, lowercase letters, digits and hyphens,
                at most 64 characters.
            status (GuideProgressStatus): What the user did.

        Returns:
            GuideProgressDto: The row as stored after this call.

        Raises:
            ValueError: ``guide_key`` is not a valid key.
        """
        if not GUIDE_KEY_PATTERN.fullmatch(guide_key):
            raise ValueError(
                "Guide key must be 1 to 64 lowercase letters, digits or hyphens."
            )

        existing = await self.user_guide_progress_repository.get_for_update(
            session, user_id, guide_key
        )
        snooze_count = existing.snooze_count if existing is not None else 0

        if status == GuideProgressStatus.SNOOZED:
            if existing is not None and existing.status in _FINAL_STATUSES:
                return GuideProgressDto.model_validate(existing)
            snooze_count += 1
            if snooze_count >= MAX_GUIDE_SNOOZES:
                status = GuideProgressStatus.DISMISSED

        row = await self.user_guide_progress_repository.upsert(
            session,
            user_id=user_id,
            guide_key=guide_key,
            status=status,
            snooze_count=snooze_count,
        )
        result = GuideProgressDto.model_validate(row)
        await session.commit()
        return result
