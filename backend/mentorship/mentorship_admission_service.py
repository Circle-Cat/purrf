from sqlalchemy.ext.asyncio import AsyncSession

from backend.common.mentorship_enums import MentorshipEvent, ParticipantRole
from backend.common.recruiting_enums import JobKind
from backend.notification_management.event_recorder import record_event


class MentorshipAdmissionService:
    """Everything that happens to a person when they are admitted.

    Recruiting has three sites that admit someone -- a manual move to HIRED
    and two screening auto-hires -- and each used to call
    ``OnboardingTrainingService.ensure_for_admitted`` directly. Adding the
    admission email as a second call at all three would have put a
    mentor-only condition into recruiting, which has no business knowing that
    mentorship has roles. This service owns the whole rule instead, and the
    three sites call it.
    """

    def __init__(
        self, logger, onboarding_training_service, mentorship_round_repository
    ):
        """
        Args:
            logger: Application logger.
            onboarding_training_service (OnboardingTrainingService): Assigns
                the onboarding task, for mentors and mentees alike.
            mentorship_round_repository (MentorshipRoundRepository): Finds the
                round the admitted mentor should register for.
        """
        self.logger = logger
        self.onboarding_training_service = onboarding_training_service
        self.mentorship_round_repository = mentorship_round_repository

    async def on_admitted(self, session: AsyncSession, application, job) -> None:
        """Assign the onboarding training, and tell an admitted mentor.

        Call after the stage change is written and before the commit: the
        recipient resolver reads this same session, and the event, the
        notification and the training row belong in the caller's transaction
        so an admission that rolls back leaves none of them behind.

        Only mentors are emailed. Mentees are deliberately left out even
        though they owe the same training, so the training call happens for
        both before the role check.

        Args:
            session (AsyncSession): Session inside the caller's open
                transaction.
            application (ApplicationEntity): The application just admitted.
            job (JobEntity): The posting it belongs to.
        """
        await self.onboarding_training_service.ensure_for_admitted(
            session=session, user_id=application.user_id, job=job
        )

        if (
            job.kind != JobKind.ACTIVITY
            or job.mentorship_role != ParticipantRole.MENTOR
        ):
            return

        open_round = (
            await self.mentorship_round_repository.get_open_mentor_registration_round(
                session
            )
        )
        description = (open_round.description or {}) if open_round else {}

        await record_event(
            session,
            subject_type="application",
            subject_id=application.application_id,
            # Never the acting user, on any path. Two of the three call sites
            # admit someone in response to that person's own submission, so
            # naming them the actor would have ``record_event`` discard the
            # only recipient -- no notification row, no email, and no error.
            # Who admitted them is on the timeline already, in the
            # accompanying recruiting.stage_changed event.
            actor_id=None,
            event_type=MentorshipEvent.MENTOR_ADMITTED,
            details={
                "mentorshipRole": ParticipantRole.MENTOR.value,
                "roundId": open_round.round_id if open_round else None,
                "roundName": open_round.name if open_round else None,
                # The two timestamps are carried as the raw strings found in
                # the JSONB, not parsed and re-serialised: their two writers
                # disagree on format, and the renderer owns the one tolerant
                # parse. Snapshotted rather than looked up at render time
                # because a redelivery hours later may find a different round
                # open, or none, and two deliveries of one admission must not
                # say different things.
                "registrationDeadlineAt": description.get(
                    "mentor_application_deadline_at"
                ),
                "matchNotificationAt": description.get("match_notification_at"),
            },
        )
        self.logger.info(
            "[MentorshipAdmissionService] recorded mentor admission for "
            "application %s (round %s).",
            application.application_id,
            open_round.round_id if open_round else None,
        )
