"""The onboarding training an employee owes the moment they become internal.

Two of the four seed courses are owed by employment rather than by anything
recruiting decides: everybody internal owes the corporate culture course, and
interns additionally owe the residency programme onboarding. Neither had a
path that could ever assign it.

Intern-ness is not a purrf concept -- `users.user_type` knows only internal
and external -- so it is read from the Azure `interns` group snapshot the
daily `update-ldap` cron leaves in Redis, never from Graph directly.
"""

from backend.common.constants import (
    LDAP_KEY_TEMPLATE,
    MicrosoftAccountStatus,
    MicrosoftGroups,
)
from backend.common.mentorship_enums import TrainingCategory

_ACTIVE_INTERNS_KEY = LDAP_KEY_TEMPLATE.format(
    account_status=MicrosoftAccountStatus.ACTIVE.value,
    group=MicrosoftGroups.INTERNS.value,
)


class InternalOnboardingTrainingService:
    """Assigns the employment-driven onboarding courses."""

    def __init__(
        self,
        logger,
        redis_client,
        retry_utils,
        onboarding_training_service,
    ):
        """
        Args:
            logger: Application logger.
            redis_client: Redis client holding the daily Azure group snapshot.
            retry_utils (RetryUtils): Retries transient Redis failures.
            onboarding_training_service (OnboardingTrainingService): Creates
                the training rows.
        """
        self.logger = logger
        self.redis_client = redis_client
        self.retry_utils = retry_utils
        self.onboarding_training_service = onboarding_training_service

    async def ensure_for_internal(self, session, user_id: int, email: str) -> None:
        """Assign what this employee owes, if the courses can be finished.

        Both rows are gated on the course having a live package and being
        active -- the same gate `TrainingAssignmentService._assignable_course`
        applies -- so the automatic path never creates a row the manual path
        would refuse. Both are created without a deadline: nothing computes
        one for these two courses.

        Does not commit. The caller owns the transaction, so the training
        rows and the `is_internal` flag stand or fall together.

        Args:
            session: The active async database session.
            user_id (int): The employee who just became internal.
            email (str): Their corp address.
        """
        await self.onboarding_training_service.ensure_onboarding_training(
            session=session,
            user_id=user_id,
            category=TrainingCategory.CORPORATE_CULTURE_COURSE,
            require_live_package=True,
        )

        if self.is_intern(_ldap_of(email)):
            await self.onboarding_training_service.ensure_onboarding_training(
                session=session,
                user_id=user_id,
                category=TrainingCategory.RESIDENCY_PROGRAM_ONBOARDING,
                require_live_package=True,
            )

    def is_intern(self, ldap: str) -> bool:
        """Whether the Azure snapshot holds this ldap in the active interns.

        Answers False for an unreadable directory as well as for a
        non-intern. A directory lookup that blocked a sign-in would cost far
        more than the missed assignment, which stays missed until somebody
        assigns the course in bulk -- see the design's fallback.

        Args:
            ldap (str): The corp address's local part.

        Returns:
            bool: True only when the snapshot lists them.
        """
        try:
            return bool(
                self.retry_utils.get_retry_on_transient(
                    self.redis_client.hexists, _ACTIVE_INTERNS_KEY, ldap
                )
            )
        except Exception:
            self.logger.warning(
                "[InternalOnboardingTrainingService] could not read %s; "
                "treating ldap=%s as not an intern.",
                _ACTIVE_INTERNS_KEY,
                ldap,
                exc_info=True,
            )
            return False


def _ldap_of(email: str) -> str:
    """The local part, derived exactly as MicrosoftMemberSyncService does when
    it writes the snapshot. The two must not drift: a mismatch would silently
    make every lookup a miss."""
    return email.split("@")[0]
