"""Recording that a notification reached someone some other way -- Teams,
Google Chat, a call -- as a note. That note is what makes the stage count as
notified for them; nothing else is stored, and nothing undoes it."""

from datetime import datetime, timezone

from backend.common.exceptions import ConflictError, NotFoundError
from backend.common.mentorship_email_enums import MentorshipEmailStage
from backend.common.mentorship_enums import ParticipantNoteTag
from backend.dto.mentorship_email_dto import (
    NotificationMarkResultDto,
    NotificationMarkSkipDto,
)
from backend.mentorship.round_windows import is_in_progress

ALREADY_NOTIFIED = "already_notified"
NOT_OFFERED = "not_offered"

# What can reach someone not registered for the round; the invitation is only
# for them. The same split the Kit send dialog offers.
_NOT_REGISTERED_STAGES = frozenset({
    MentorshipEmailStage.ROUND_RECRUITMENT,
    MentorshipEmailStage.ADMISSION,
    MentorshipEmailStage.ONBOARDING_REMINDER,
})


def stage_offered(stage: MentorshipEmailStage, registered: bool) -> bool:
    """Whether this notification can be marked for someone registered for
    the round or not."""
    if registered:
        return stage != MentorshipEmailStage.ROUND_RECRUITMENT
    return stage in _NOT_REGISTERED_STAGES


class NotificationMarkService:
    """Marks people notified by hand, one note each."""

    def __init__(
        self,
        note_repository,
        participants_repository,
        rounds_repository,
        users_repository,
        mentorship_email_repository,
        logger,
    ):
        """
        Args:
            note_repository: Writes the notes.
            participants_repository: Tells who is registered for the round.
            rounds_repository: Reads the round, to check it is in progress.
            users_repository: Checks the people exist.
            mentorship_email_repository: Reads who is already notified.
            logger: Injected logger.
        """
        self.note_repository = note_repository
        self.participants_repository = participants_repository
        self.rounds_repository = rounds_repository
        self.users_repository = users_repository
        self.email_repository = mentorship_email_repository
        self.logger = logger

    async def mark(
        self,
        session,
        *,
        round_id: int,
        user_ids: list[int],
        stage: MentorshipEmailStage,
        body: str,
        actor_id: int,
    ) -> NotificationMarkResultDto:
        """Write a ``notified`` note on each person not already notified of
        this stage and offered it, by the actor. Commits once.

        Args:
            session (AsyncSession): Active database async session.
            round_id (int): The round, which must be in progress.
            user_ids (list[int]): The people; repeats count once.
            stage (MentorshipEmailStage): Which notification.
            body (str): How it was sent, already validated.
            actor_id (int): Who is marking.

        Returns:
            NotificationMarkResultDto: Who was marked, and who was skipped
                and why.

        Raises:
            NotFoundError: The round or one of the people does not exist.
            ConflictError: The round is not in progress (code
                ``round_not_in_progress``).
        """
        round_ = await self.rounds_repository.get_by_round_id(session, round_id)
        if round_ is None:
            raise NotFoundError(f"Mentorship round {round_id} does not exist.")
        if not is_in_progress(round_, datetime.now(timezone.utc)):
            raise ConflictError(
                "Notifications can only be marked while the round is in progress.",
                code="round_not_in_progress",
            )
        ids = list(dict.fromkeys(user_ids))
        found = {
            user.user_id
            for user in await self.users_repository.get_all_by_ids(session, ids)
        }
        missing = [user_id for user_id in ids if user_id not in found]
        if missing:
            raise NotFoundError(f"User {missing[0]} does not exist.")

        registered = {
            user.user_id
            for user, _ in await self.participants_repository.list_round_registrations(
                session, round_id
            )
        }
        reached = [
            *await self.email_repository.list_sent_stages(session, round_id),
            *await self.email_repository.list_manual_stages(session, round_id),
        ]
        already = {user_id for user_id, done in reached if done == stage}

        marked: list[int] = []
        skipped: list[NotificationMarkSkipDto] = []
        for user_id in ids:
            if not stage_offered(stage, user_id in registered):
                skipped.append(
                    NotificationMarkSkipDto(user_id=user_id, reason=NOT_OFFERED)
                )
                continue
            if user_id in already:
                skipped.append(
                    NotificationMarkSkipDto(user_id=user_id, reason=ALREADY_NOTIFIED)
                )
                continue
            await self.note_repository.create(
                session,
                user_id=user_id,
                round_id=round_id,
                author_user_id=actor_id,
                body=body,
                tag=ParticipantNoteTag.NOTIFIED,
                notification_stage=stage.value,
            )
            marked.append(user_id)
        await session.commit()
        self.logger.info(
            "[NotificationMarkService] round=%s stage=%s marked=%d skipped=%d by=%s",
            round_id,
            stage.value,
            len(marked),
            len(skipped),
            actor_id,
        )
        return NotificationMarkResultDto(marked=marked, skipped=skipped)
