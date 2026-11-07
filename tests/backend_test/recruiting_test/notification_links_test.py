import unittest
from datetime import date, datetime, timezone
from decimal import Decimal

from backend.admin.block_service import (
    BLOCK_TARGET,
    BLOCK_USER,
    RAISE_PERMISSION_BY_SOURCE,
    RECRUITING_APPLICATION_SOURCE,
)
from backend.common.approval_enums import ApprovalRequestStatus
from backend.common.communication_enums import ContextType
from backend.common.inbox_enums import INBOX_SUBJECT_TYPE, InboxEvent
from backend.common.leave_enums import (
    LEAVE_APPROVAL,
    LEAVE_REQUEST_SUBJECT,
    LeaveEvent,
    LeaveRequestStatus,
    LeaveRequestType,
)
from backend.common.mentorship_email_enums import (
    MENTORSHIP_EMAIL_SEND_SUBJECT_TYPE,
    MentorshipEmailSendStatus,
)
from backend.common.mentorship_enums import CommunicationMethod, MentorshipEvent
from backend.common.ops_enums import OPS_ALERT_SUBJECT_TYPE, OpsEvent
from backend.common.permissions import Permission
from backend.common.recruiting_enums import (
    ApplicationStage,
    JobKind,
    JobStatus,
    RecruitingEvent,
)
from backend.common.user_enums import USER_SUBJECT_TYPE, UserEvent
from backend.entity.application_assignment_entity import (
    ApplicationAssignmentEntity,
)
from backend.entity.application_entity import ApplicationEntity
from backend.entity.approval_request_entity import ApprovalRequestEntity
from backend.entity.email_thread_entity import EmailThreadEntity
from backend.entity.event_entity import EventEntity
from backend.entity.job_entity import JobEntity
from backend.entity.leave_request_entity import LeaveRequestEntity
from backend.entity.mentorship_email_send_entity import MentorshipEmailSendEntity
from backend.entity.mentorship_round_entity import MentorshipRoundEntity
from backend.entity.user_permissions_entity import UserPermissionsEntity
from backend.entity.users_entity import UsersEntity
from backend.mentorship.end_pair_handler import END_PAIR
from backend.mentorship.exempt_matching_handler import EXEMPT_MATCHING
from backend.mentorship.publish_matching_handler import PUBLISH_MATCHING
from backend.recruiting import notification_links
from backend.recruiting.notification_links import link_for, links_for_page
from tests.backend_test.repository_test.base_repository_test_lib import (
    BaseRepositoryTestLib,
)

# Every id differs from every other, so a link that read the wrong one --
# the job's id for the application's, the round's for the person's -- cannot
# pass by coincidence.
OWNER = 9101
ASSIGNEE = 9102
READER = 9103
SUPER_ADMIN = 9104
CANDIDATE = 9105
EMPLOYEE = 9106
MANAGER = 9107
RAISER = 9108
REVIEWER = 9109
TARGET = 9110
MENTEE = 9111
MENTOR = 9112
PERSON = 9113

JOB = 7201
APPLICATION = 7302
ROUND = 7403
THREAD = 7504
SEND = 7605
LEAVE = 7706

PUBLISH_REQUEST = 8801
EXEMPT_REQUEST = 8802
END_PAIR_REQUEST = 8803
LEAVE_REQUEST = 8804
MENTORSHIP_BLOCK = 8805
RECRUITING_BLOCK = 8806
RECRUITING_BLOCK_ON_APPLICATION = 8807


def _user(user_id: int, *, is_super_admin: bool = False) -> UsersEntity:
    return UsersEntity(
        user_id=user_id,
        first_name="U",
        last_name=str(user_id),
        timezone="America/Los_Angeles",
        timezone_updated_at=datetime.now(timezone.utc),
        communication_channel=CommunicationMethod.EMAIL,
        is_active=True,
        is_super_admin=is_super_admin,
        updated_timestamp=datetime.now(timezone.utc),
    )


def _event(event_type, subject_type, subject_id, details=None, event_id=1):
    event = EventEntity(
        subject_type=subject_type,
        subject_id=subject_id,
        actor_id=None,
        event_type=event_type,
        details=details or {},
    )
    event.event_id = event_id
    return event


def _application_event(event_type):
    return _event(event_type, "application", APPLICATION)


def _request(request_id, action, target_type, target_id, payload, raised_by, reviewer):
    return ApprovalRequestEntity(
        request_id=request_id,
        action=action,
        target_type=target_type,
        target_id=target_id,
        payload=payload,
        raised_by=raised_by,
        reviewer_id=reviewer,
        status=ApprovalRequestStatus.PENDING,
    )


class NotificationLinksTest(BaseRepositoryTestLib):
    async def asyncSetUp(self):
        await super().asyncSetUp()
        await self.insert_entities(
            [
                _user(user_id)
                for user_id in (
                    OWNER,
                    ASSIGNEE,
                    READER,
                    CANDIDATE,
                    EMPLOYEE,
                    MANAGER,
                    RAISER,
                    REVIEWER,
                    TARGET,
                    MENTEE,
                    MENTOR,
                    PERSON,
                )
            ]
            + [_user(SUPER_ADMIN, is_super_admin=True)]
        )
        await self.insert_entities([
            JobEntity(
                job_id=JOB,
                kind=JobKind.EMPLOYMENT,
                title="Backend Engineer",
                status=JobStatus.PUBLISHED,
                pipeline_config={"ownerIds": [OWNER]},
            ),
            MentorshipRoundEntity(
                round_id=ROUND,
                name="Fall 2026",
                onboarding_deadline_at=datetime(2026, 9, 15, tzinfo=timezone.utc),
            ),
            UserPermissionsEntity(
                user_id=READER,
                permission_name=Permission.RECRUITING_APPLICATION_READ_ALL.value,
                granted_source="admin",
                granted_by=None,
            ),
        ])
        await self.insert_entities([
            ApplicationEntity(
                application_id=APPLICATION,
                job_id=JOB,
                user_id=CANDIDATE,
                stage=ApplicationStage.APPLIED,
            ),
        ])

    async def _assign(self, *assignees):
        await self.insert_entities([
            ApplicationAssignmentEntity(
                application_id=APPLICATION,
                stage=ApplicationStage.APPLIED,
                round=1,
                assignee_id=assignee,
                assigned_by=OWNER,
            )
            for assignee in assignees
        ])

    async def _link(self, event, user_id):
        return await link_for(self.session, event, user_id)

    # Recruiting

    async def test_posting_reviews_open_the_posting(self):
        for event_type in (
            RecruitingEvent.REVIEW_OPENED,
            RecruitingEvent.REVIEW_REASSIGNED,
            RecruitingEvent.REVIEW_DECIDED,
        ):
            with self.subTest(event_type):
                event = _event(event_type, "job", JOB, {"reviewId": PUBLISH_REQUEST})
                self.assertEqual(
                    await self._link(event, REVIEWER), f"/recruiting/postings/{JOB}"
                )

    async def test_an_owner_opens_the_application(self):
        await self._assign(ASSIGNEE)
        event = _application_event(RecruitingEvent.STAGE_CHANGED)

        self.assertEqual(
            await self._link(event, OWNER), f"/recruiting/applications/{APPLICATION}"
        )

    async def test_a_pure_assignee_opens_it_to_evaluate(self):
        """Without evaluate mode an assignee who cannot view the application
        lands on an empty right column."""
        await self._assign(ASSIGNEE)
        for event_type in (
            RecruitingEvent.STAGE_CHANGED,
            RecruitingEvent.ROUND_ADVANCED,
            RecruitingEvent.REASSIGNED,
            RecruitingEvent.INTERVIEW_SCHEDULED,
            RecruitingEvent.INTERVIEW_UPDATED,
            RecruitingEvent.INTERVIEW_CANCELLED,
            RecruitingEvent.AUTO_ASSIGNED,
            RecruitingEvent.MENTIONED,
        ):
            with self.subTest(event_type):
                self.assertEqual(
                    await self._link(_application_event(event_type), ASSIGNEE),
                    f"/recruiting/applications/{APPLICATION}?mode=evaluate",
                )

    async def test_an_assignee_granted_read_all_opens_it_plainly(self):
        await self._assign(READER)

        self.assertEqual(
            await self._link(
                _application_event(RecruitingEvent.INTERVIEW_SCHEDULED), READER
            ),
            f"/recruiting/applications/{APPLICATION}",
        )

    async def test_a_super_admin_assignee_opens_it_plainly(self):
        """A super admin holds read.all without a grant row."""
        await self._assign(SUPER_ADMIN)

        self.assertEqual(
            await self._link(
                _application_event(RecruitingEvent.INTERVIEW_SCHEDULED), SUPER_ADMIN
            ),
            f"/recruiting/applications/{APPLICATION}",
        )

    async def test_an_assignee_who_owns_the_posting_opens_it_plainly(self):
        await self._assign(OWNER)

        self.assertEqual(
            await self._link(_application_event(RecruitingEvent.REASSIGNED), OWNER),
            f"/recruiting/applications/{APPLICATION}",
        )

    async def test_someone_mentioned_who_is_not_assigned_opens_it_plainly(self):
        await self._assign(ASSIGNEE)

        self.assertEqual(
            await self._link(_application_event(RecruitingEvent.MENTIONED), PERSON),
            f"/recruiting/applications/{APPLICATION}",
        )

    async def test_owner_only_and_email_events_open_the_application_plainly(self):
        """These never reach an assignee as one, so even one who is reads
        the plain page."""
        await self._assign(ASSIGNEE)
        for event_type in (
            RecruitingEvent.APPLICATION_SUBMITTED,
            RecruitingEvent.AUTO_REJECTED,
            RecruitingEvent.BLACKLISTED,
            RecruitingEvent.SUB_STATUS_CHANGED,
            RecruitingEvent.EVALUATION_CONFIRMED,
            RecruitingEvent.EMAIL_RECEIVED,
            RecruitingEvent.EMAIL_BOUNCED,
        ):
            with self.subTest(event_type):
                self.assertEqual(
                    await self._link(_application_event(event_type), ASSIGNEE),
                    f"/recruiting/applications/{APPLICATION}",
                )

    # Inbox

    async def test_needs_reply_opens_the_service_it_names(self):
        event = _event(
            InboxEvent.NEEDS_REPLY, INBOX_SUBJECT_TYPE, THREAD, {"service": "inquiries"}
        )

        self.assertEqual(await self._link(event, PERSON), "/inbox?service=inquiries")

    async def test_a_bounce_opens_the_service_of_its_thread(self):
        await self.insert_entities([
            EmailThreadEntity(
                thread_id=THREAD,
                gmail_thread_id="g-links",
                context_type=ContextType.MENTORSHIP_INBOX,
            )
        ])
        event = _event(
            InboxEvent.BOUNCED, INBOX_SUBJECT_TYPE, THREAD, {"senderUserId": PERSON}
        )

        self.assertEqual(await self._link(event, PERSON), "/inbox?service=mentorship")

    async def test_a_bounce_whose_thread_is_gone_opens_the_inbox(self):
        event = _event(InboxEvent.BOUNCED, INBOX_SUBJECT_TYPE, THREAD)

        self.assertEqual(await self._link(event, PERSON), "/inbox")

    # Leave

    async def _leave(self):
        await self.insert_entities([
            LeaveRequestEntity(
                leave_request_id=LEAVE,
                user_id=EMPLOYEE,
                type=LeaveRequestType.PAID,
                start_date=date(2026, 11, 9),
                end_date=date(2026, 11, 10),
                start_time=None,
                end_time=None,
                hours=Decimal("16"),
                status=LeaveRequestStatus.PENDING,
                approver_user_id=MANAGER,
                reason=None,
            ),
        ])
        await self.insert_entities([
            _request(
                LEAVE_REQUEST,
                LEAVE_APPROVAL,
                LEAVE_REQUEST_SUBJECT,
                str(LEAVE),
                {},
                EMPLOYEE,
                MANAGER,
            )
        ])

    async def test_a_filed_leave_request_opens_the_approvals(self):
        await self._leave()
        event = _event(
            LeaveEvent.REQUEST_SUBMITTED,
            LEAVE_REQUEST_SUBJECT,
            LEAVE,
            {"requestId": LEAVE_REQUEST},
        )

        self.assertEqual(await self._link(event, MANAGER), "/leave/approvals")

    async def test_a_decision_opens_the_employees_requests(self):
        await self._leave()
        event = _event(
            LeaveEvent.REQUEST_DECIDED,
            LEAVE_REQUEST_SUBJECT,
            LEAVE,
            {"requestId": LEAVE_REQUEST, "decision": "approved"},
        )

        self.assertEqual(await self._link(event, EMPLOYEE), "/leave/requests")

    async def test_a_withdrawal_opens_the_managers_approvals(self):
        await self._leave()
        event = _event(
            LeaveEvent.REQUEST_DECIDED,
            LEAVE_REQUEST_SUBJECT,
            LEAVE,
            {"requestId": LEAVE_REQUEST, "decision": "withdrawn"},
        )

        self.assertEqual(await self._link(event, MANAGER), "/leave/approvals")

    # Mentorship approvals

    async def _approvals(self):
        await self.insert_entities([
            _request(
                PUBLISH_REQUEST,
                PUBLISH_MATCHING,
                "matching_run",
                "run-1",
                {"round_id": ROUND},
                RAISER,
                REVIEWER,
            ),
            _request(
                EXEMPT_REQUEST,
                EXEMPT_MATCHING,
                "round_user",
                f"{ROUND}:{PERSON}",
                {"round_id": ROUND, "user_id": PERSON},
                RAISER,
                REVIEWER,
            ),
            _request(
                END_PAIR_REQUEST,
                END_PAIR,
                "pair",
                "pair-1",
                {
                    "round_id": ROUND,
                    "pair_id": 1,
                    "mentor_id": MENTOR,
                    "mentee_id": MENTEE,
                },
                RAISER,
                REVIEWER,
            ),
        ])

    def _approval_event(self, event_type, request_id, action):
        return _event(
            event_type,
            "mentorship_round",
            ROUND,
            {"requestId": request_id, "action": action},
        )

    async def test_a_publish_request_opens_the_matching_page(self):
        await self._approvals()
        for event_type, user_id in (
            (MentorshipEvent.APPROVAL_REQUESTED, REVIEWER),
            (MentorshipEvent.APPROVAL_REASSIGNED, REVIEWER),
            (MentorshipEvent.APPROVAL_DECIDED, RAISER),
        ):
            with self.subTest(event_type):
                event = self._approval_event(
                    event_type, PUBLISH_REQUEST, PUBLISH_MATCHING
                )
                self.assertEqual(
                    await self._link(event, user_id),
                    f"/mentorship-management/matching/{ROUND}",
                )

    async def test_a_waiting_request_opens_the_person_in_review_mode(self):
        await self._approvals()
        for event_type in (
            MentorshipEvent.APPROVAL_REQUESTED,
            MentorshipEvent.APPROVAL_REASSIGNED,
        ):
            with self.subTest(event_type):
                event = self._approval_event(
                    event_type, EXEMPT_REQUEST, EXEMPT_MATCHING
                )
                self.assertEqual(
                    await self._link(event, REVIEWER),
                    f"/mentorship-management/participants/{PERSON}"
                    f"?round={ROUND}&review={EXEMPT_REQUEST}",
                )

    async def test_ending_a_pair_opens_the_mentee(self):
        await self._approvals()
        event = self._approval_event(
            MentorshipEvent.APPROVAL_REQUESTED, END_PAIR_REQUEST, END_PAIR
        )

        self.assertEqual(
            await self._link(event, REVIEWER),
            f"/mentorship-management/participants/{MENTEE}"
            f"?round={ROUND}&review={END_PAIR_REQUEST}",
        )

    async def test_a_decided_request_opens_the_person_without_review(self):
        await self._approvals()
        event = self._approval_event(
            MentorshipEvent.APPROVAL_DECIDED, EXEMPT_REQUEST, EXEMPT_MATCHING
        )

        self.assertEqual(
            await self._link(event, RAISER),
            f"/mentorship-management/participants/{PERSON}?round={ROUND}",
        )

    # Mentorship, other

    async def test_a_participant_email_opens_their_page_for_the_round(self):
        for event_type in (
            MentorshipEvent.EMAIL_RECEIVED,
            MentorshipEvent.EMAIL_BOUNCED,
        ):
            with self.subTest(event_type):
                event = _event(
                    event_type,
                    INBOX_SUBJECT_TYPE,
                    THREAD,
                    {"userId": PERSON, "roundId": ROUND, "threadId": THREAD},
                )
                self.assertEqual(
                    await self._link(event, REVIEWER),
                    f"/mentorship-management/participants/{PERSON}?round={ROUND}",
                )

    async def test_a_prepared_send_opens_the_participants_of_its_round(self):
        await self.insert_entities([
            MentorshipEmailSendEntity(
                send_id=SEND,
                round_id=ROUND,
                stage="match_result",
                kit_draft_id=11,
                kit_draft_subject="Your match",
                created_by=RAISER,
                status=MentorshipEmailSendStatus.SCHEDULED,
                sender_address="notification-test@circlecat.org",
                kit_tag_name="purrf · Fall 2026",
            )
        ])
        event = _event(
            MentorshipEvent.EMAIL_SEND_PREPARED,
            MENTORSHIP_EMAIL_SEND_SUBJECT_TYPE,
            SEND,
            {"stage": "match_result"},
        )

        self.assertEqual(
            await self._link(event, RAISER), f"/mentorship-management?round={ROUND}"
        )

    async def test_a_finished_run_opens_the_matching_page(self):
        event = _event(
            MentorshipEvent.MATCHING_RUN_COMPLETED, "mentorship_round", ROUND
        )

        self.assertEqual(
            await self._link(event, RAISER), f"/mentorship-management/matching/{ROUND}"
        )

    async def test_an_admission_opens_the_applicants_dashboard(self):
        event = _application_event(MentorshipEvent.MENTOR_ADMITTED)

        self.assertEqual(await self._link(event, CANDIDATE), "/dashboard/me")

    # Block requests

    async def _blocks(self):
        await self.insert_entities([
            _request(
                MENTORSHIP_BLOCK,
                BLOCK_USER,
                BLOCK_TARGET,
                str(TARGET),
                {"raised_from": "mentorship_participant"},
                RAISER,
                REVIEWER,
            ),
            _request(
                RECRUITING_BLOCK,
                BLOCK_USER,
                BLOCK_TARGET,
                str(PERSON),
                {"raised_from": "recruiting_application"},
                RAISER,
                REVIEWER,
            ),
            _request(
                RECRUITING_BLOCK_ON_APPLICATION,
                BLOCK_USER,
                BLOCK_TARGET,
                str(CANDIDATE),
                {
                    "raised_from": "recruiting_application",
                    "application_id": APPLICATION,
                },
                RAISER,
                REVIEWER,
            ),
        ])

    async def test_a_block_request_opens_the_account(self):
        await self._blocks()
        for event_type in (
            UserEvent.BLOCK_REQUESTED,
            UserEvent.BLOCK_REQUEST_REASSIGNED,
        ):
            with self.subTest(event_type):
                event = _event(
                    event_type,
                    USER_SUBJECT_TYPE,
                    TARGET,
                    {"requestId": MENTORSHIP_BLOCK},
                )
                self.assertEqual(
                    await self._link(event, REVIEWER),
                    f"/admin/accounts?user_id={TARGET}",
                )

    async def test_a_decided_block_opens_the_account_for_the_reviewer(self):
        await self._blocks()
        event = _event(
            UserEvent.BLOCK_REQUEST_DECIDED,
            USER_SUBJECT_TYPE,
            TARGET,
            {"requestId": MENTORSHIP_BLOCK, "decision": "withdrawn"},
        )

        self.assertEqual(
            await self._link(event, REVIEWER), f"/admin/accounts?user_id={TARGET}"
        )

    async def test_a_decided_block_opens_the_participant_for_a_mentorship_raiser(self):
        await self._blocks()
        event = _event(
            UserEvent.BLOCK_REQUEST_DECIDED,
            USER_SUBJECT_TYPE,
            TARGET,
            {"requestId": MENTORSHIP_BLOCK, "decision": "approved"},
        )

        self.assertEqual(
            await self._link(event, RAISER),
            f"/mentorship-management/participants/{TARGET}",
        )

    async def test_a_decided_block_opens_the_application_for_a_recruiting_raiser(self):
        await self._blocks()
        for decision in ("approved", "rejected"):
            with self.subTest(decision):
                event = _event(
                    UserEvent.BLOCK_REQUEST_DECIDED,
                    USER_SUBJECT_TYPE,
                    CANDIDATE,
                    {
                        "requestId": RECRUITING_BLOCK_ON_APPLICATION,
                        "decision": decision,
                    },
                )
                self.assertEqual(
                    await self._link(event, RAISER),
                    f"/recruiting/applications/{APPLICATION}",
                )

    async def test_a_decided_recruiting_block_still_opens_the_account_for_the_reviewer(
        self,
    ):
        await self._blocks()
        event = _event(
            UserEvent.BLOCK_REQUEST_DECIDED,
            USER_SUBJECT_TYPE,
            CANDIDATE,
            {"requestId": RECRUITING_BLOCK_ON_APPLICATION, "decision": "rejected"},
        )

        self.assertEqual(
            await self._link(event, REVIEWER), f"/admin/accounts?user_id={CANDIDATE}"
        )

    async def test_a_decided_block_has_no_link_for_a_recruiting_raiser_without_an_application(
        self,
    ):
        await self._blocks()
        event = _event(
            UserEvent.BLOCK_REQUEST_DECIDED,
            USER_SUBJECT_TYPE,
            PERSON,
            {"requestId": RECRUITING_BLOCK, "decision": "rejected"},
        )

        self.assertIsNone(await self._link(event, RAISER))

    # Ops

    async def test_a_gmail_sync_alert_has_no_link(self):
        event = _event(OpsEvent.GMAIL_SYNC_ALERT, OPS_ALERT_SUBJECT_TYPE, 1)

        self.assertIsNone(await self._link(event, SUPER_ADMIN))

    # A page

    async def test_a_page_links_every_event_by_id(self):
        await self._approvals()
        await self._assign(ASSIGNEE)
        events = [
            _event(
                MentorshipEvent.APPROVAL_REQUESTED,
                "mentorship_round",
                ROUND,
                {"requestId": EXEMPT_REQUEST},
                event_id=61,
            ),
            _event(
                RecruitingEvent.AUTO_ASSIGNED, "application", APPLICATION, event_id=62
            ),
            _event(OpsEvent.GMAIL_SYNC_ALERT, OPS_ALERT_SUBJECT_TYPE, 1, event_id=63),
        ]

        links = await links_for_page(self.session, events, ASSIGNEE)

        self.assertEqual(
            links,
            {
                61: f"/mentorship-management/participants/{PERSON}"
                f"?round={ROUND}&review={EXEMPT_REQUEST}",
                62: f"/recruiting/applications/{APPLICATION}?mode=evaluate",
                63: None,
            },
        )

    async def test_a_page_judges_ownership_by_the_postings_it_is_handed(self):
        """The bell hands over the postings it loaded; a posting that names
        the recipient as owner keeps them out of evaluate mode."""
        await self._assign(ASSIGNEE)
        handed = JobEntity(
            job_id=JOB,
            kind=JobKind.EMPLOYMENT,
            title="Backend Engineer",
            status=JobStatus.PUBLISHED,
            pipeline_config={"ownerIds": [ASSIGNEE]},
        )
        event = _application_event(RecruitingEvent.REASSIGNED)

        links = await links_for_page(
            self.session,
            [event],
            ASSIGNEE,
            jobs_by_application={APPLICATION: handed},
        )

        self.assertEqual(links, {1: f"/recruiting/applications/{APPLICATION}"})


class NotificationLinkConstantsTest(unittest.TestCase):
    def test_action_names_are_the_handlers(self):
        self.assertEqual(notification_links.PUBLISH_MATCHING, PUBLISH_MATCHING)
        self.assertEqual(notification_links.END_PAIR, END_PAIR)

    def test_the_block_sources_are_the_services(self):
        self.assertIn(
            notification_links.MENTORSHIP_PARTICIPANT_SOURCE, RAISE_PERMISSION_BY_SOURCE
        )
        self.assertEqual(
            notification_links.RECRUITING_APPLICATION_SOURCE,
            RECRUITING_APPLICATION_SOURCE,
        )


if __name__ == "__main__":
    unittest.main()
