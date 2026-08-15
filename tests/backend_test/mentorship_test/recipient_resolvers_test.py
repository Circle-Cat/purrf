import unittest
from datetime import datetime, timezone

from backend.common.mentorship_enums import CommunicationMethod, ParticipantRole
from backend.common.recruiting_enums import ApplicationStage, JobKind, JobStatus
from backend.entity.application_entity import ApplicationEntity
from backend.entity.event_entity import EventEntity
from backend.entity.job_entity import JobEntity
from backend.entity.users_entity import UsersEntity
from backend.mentorship import notification_renderers  # noqa: F401 (registers)
from backend.mentorship import recipient_resolvers  # noqa: F401 (registers)
from backend.notification_management import recipient_registry, render_registry
from tests.backend_test.repository_test.base_repository_test_lib import (
    BaseRepositoryTestLib,
)


def _make_user(first_name="Ada", last_name="Lovelace") -> UsersEntity:
    return UsersEntity(
        first_name=first_name,
        last_name=last_name,
        timezone="America/Los_Angeles",
        timezone_updated_at=datetime.now(timezone.utc),
        communication_channel=CommunicationMethod.EMAIL,
        is_active=True,
        updated_timestamp=datetime.now(timezone.utc),
    )


class MentorAdmittedRecipientsTest(BaseRepositoryTestLib):
    async def test_the_admitted_applicant_is_the_only_recipient(self):
        """Not the posting's owners: this event exists to tell the person
        themselves, and staff already hear about the stage change."""
        applicant, owner = _make_user(), _make_user("Grace", "Hopper")
        await self.insert_entities([applicant, owner])
        job = JobEntity(
            kind=JobKind.ACTIVITY,
            mentorship_role=ParticipantRole.MENTOR,
            title="Mentorship Mentor",
            status=JobStatus.PUBLISHED,
        )
        await self.insert_entities([job])
        application = ApplicationEntity(
            job_id=job.job_id, user_id=applicant.user_id, stage=ApplicationStage.HIRED
        )
        await self.insert_entities([application])
        event = EventEntity(
            subject_type="application",
            subject_id=application.application_id,
            actor_id=None,
            event_type="mentorship.mentor_admitted",
            details={},
        )
        await self.insert_entities([event])

        recipients = await recipient_registry.resolve_recipients(self.session, event)

        self.assertEqual(recipients, {applicant.user_id})

    async def test_an_event_about_a_job_is_refused(self):
        """``subject_id`` would otherwise be read as an application id."""
        event = EventEntity(
            subject_type="job",
            subject_id=1,
            actor_id=None,
            event_type="mentorship.mentor_admitted",
            details={},
        )

        with self.assertRaises(ValueError):
            await recipient_registry.resolve_recipients(self.session, event)


class MentorshipRegistryExhaustivenessTest(unittest.TestCase):
    """Every mentorship event type that notifies someone must render.

    The recruiting pair of this test filters on the ``recruiting.`` prefix,
    so it never sees these.
    """

    def _mentorship_types(self, registry):
        return {
            event_type
            for event_type in registry
            if event_type.startswith("mentorship.")
        }

    def test_every_notifying_event_type_has_a_renderer(self):
        notifying = self._mentorship_types(recipient_registry._RESOLVERS)

        self.assertEqual(notifying - set(render_registry._RENDERERS), set())

    def test_no_mentorship_renderer_is_registered_outside_what_notifies(self):
        registered = self._mentorship_types(render_registry._RENDERERS)

        self.assertEqual(
            registered - self._mentorship_types(recipient_registry._RESOLVERS), set()
        )


if __name__ == "__main__":
    unittest.main()
