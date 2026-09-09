import unittest
from unittest.mock import AsyncMock, MagicMock

from backend.common.constants import (
    LDAP_KEY_TEMPLATE,
    MicrosoftAccountStatus,
    MicrosoftGroups,
)
from backend.common.mentorship_enums import TrainingCategory
from backend.user_identity.internal_onboarding_training import (
    InternalOnboardingTrainingService,
)

_INTERNS_KEY = LDAP_KEY_TEMPLATE.format(
    account_status=MicrosoftAccountStatus.ACTIVE.value,
    group=MicrosoftGroups.INTERNS.value,
)


class TestInternalOnboardingTrainingService(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.logger = MagicMock()
        self.redis = MagicMock()
        self.redis.hexists = MagicMock(return_value=False)
        # Mirrors RetryUtils.get_retry_on_transient: call the callable.
        self.retry_utils = MagicMock()
        self.retry_utils.get_retry_on_transient = lambda fn, *args: fn(*args)
        self.onboarding = MagicMock()
        self.onboarding.ensure_onboarding_training = AsyncMock()
        self.session = AsyncMock()
        self.service = InternalOnboardingTrainingService(
            logger=self.logger,
            redis_client=self.redis,
            retry_utils=self.retry_utils,
            onboarding_training_service=self.onboarding,
        )

    def _assigned_categories(self):
        return [
            call.kwargs["category"]
            for call in self.onboarding.ensure_onboarding_training.await_args_list
        ]

    async def test_an_employee_who_is_not_an_intern_owes_only_the_culture_course(self):
        await self.service.ensure_for_internal(
            session=self.session, user_id=7, email="ada@circlecat.org"
        )

        self.assertEqual(
            self._assigned_categories(), [TrainingCategory.CORPORATE_CULTURE_COURSE]
        )

    async def test_an_intern_owes_the_culture_course_and_the_residency_course(self):
        self.redis.hexists = MagicMock(return_value=True)

        await self.service.ensure_for_internal(
            session=self.session, user_id=7, email="ada@u.circlecat.org"
        )

        self.assertEqual(
            self._assigned_categories(),
            [
                TrainingCategory.CORPORATE_CULTURE_COURSE,
                TrainingCategory.RESIDENCY_PROGRAM_ONBOARDING,
            ],
        )

    async def test_both_courses_are_gated_on_a_live_package(self):
        """Same gate as the manual path, or the two would assign different
        sets of people."""
        self.redis.hexists = MagicMock(return_value=True)

        await self.service.ensure_for_internal(
            session=self.session, user_id=7, email="ada@circlecat.org"
        )

        for call in self.onboarding.ensure_onboarding_training.await_args_list:
            self.assertTrue(call.kwargs["require_live_package"])

    async def test_neither_course_carries_a_deadline(self):
        self.redis.hexists = MagicMock(return_value=True)

        await self.service.ensure_for_internal(
            session=self.session, user_id=7, email="ada@circlecat.org"
        )

        for call in self.onboarding.ensure_onboarding_training.await_args_list:
            self.assertIsNone(call.kwargs.get("deadline"))

    async def test_the_intern_lookup_reads_the_key_the_daily_sync_writes(self):
        """The ldap is the corp address's local part, exactly as
        MicrosoftMemberSyncService derives it. Drift here fails silently."""
        await self.service.ensure_for_internal(
            session=self.session, user_id=7, email="ada.lovelace@u.circlecat.org"
        )

        self.redis.hexists.assert_called_once_with(_INTERNS_KEY, "ada.lovelace")

    async def test_a_redis_failure_leaves_the_culture_course_assigned(self):
        """A directory outage must never cost somebody their sign-in."""
        self.redis.hexists = MagicMock(side_effect=ConnectionError("redis is down"))

        await self.service.ensure_for_internal(
            session=self.session, user_id=7, email="ada@circlecat.org"
        )

        self.assertEqual(
            self._assigned_categories(), [TrainingCategory.CORPORATE_CULTURE_COURSE]
        )
        self.logger.warning.assert_called_once()

    async def test_is_intern_is_false_when_the_directory_cannot_be_read(self):
        self.redis.hexists = MagicMock(side_effect=ConnectionError("redis is down"))

        self.assertFalse(self.service.is_intern("ada"))

    async def test_is_intern_is_true_for_a_member_of_the_active_interns_group(self):
        self.redis.hexists = MagicMock(return_value=True)

        self.assertTrue(self.service.is_intern("ada"))

    async def test_does_not_commit(self):
        """The caller owns the transaction, so the training rows and the
        is_internal flag stand or fall together."""
        await self.service.ensure_for_internal(
            session=self.session, user_id=7, email="ada@circlecat.org"
        )

        self.session.commit.assert_not_awaited()


if __name__ == "__main__":
    unittest.main()
