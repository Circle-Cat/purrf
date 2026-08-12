import os
from backend.common.logger import get_logger
from backend.utils.retry_utils import RetryUtils
from backend.common.redis_client import RedisClient
from backend.common.google_client import GoogleClient
from backend.common.jira_client import JiraClient
from backend.service.google_service import GoogleService
from backend.common.microsoft_graph_service_client import MicrosoftGraphServiceClient
from backend.common.json_schema_validator import JsonSchemaValidator
from backend.common.gerrit_client import GerritClient
from backend.service.microsoft_service import MicrosoftService
from backend.notification_management.microsoft_chat_subscription_service import (
    MicrosoftChatSubscriptionService,
)
from backend.notification_management.google_chat_subscription_service import (
    GoogleChatSubscriptionService,
)

from backend.notification_management.notification_controller import (
    NotificationController,
)
from backend.utils.google_chat_message_utils import GoogleChatMessagesUtils
from backend.consumers.consumer_controller import ConsumerController
from backend.utils.microsoft_chat_message_util import MicrosoftChatMessageUtil
from backend.utils.date_time_util import DateTimeUtil
from backend.consumers.microsoft_message_processor_service import (
    MicrosoftMessageProcessorService,
)
from backend.consumers.google_chat_processor_service import GoogleChatProcessorService
from backend.consumers.pubsub_puller_factory import PubSubPullerFactory
from backend.consumers.pubsub_puller import PubSubPuller
from backend.consumers.gerrit_processor_service import GerritProcessorService
from backend.consumers.pubsub_pull_manager import PubSubPullManager
from backend.consumers.pubsub_sync_pull_service import PubSubSyncPullService
from backend.historical_data.historical_controller import HistoricalController
from backend.historical_data.microsoft_member_sync_service import (
    MicrosoftMemberSyncService,
)
from backend.historical_data.google_calendar_sync_service import (
    GoogleCalendarSyncService,
)
from backend.historical_data.gerrit_sync_service import GerritSyncService
from backend.internal_activity_service.ldap_service import LdapService
from backend.internal_activity_service.jira_analytics_service import (
    JiraAnalyticsService,
)
from backend.internal_activity_service.google_calendar_analytics_service import (
    GoogleCalendarAnalyticsService,
)
from backend.internal_activity_service.internal_activity_controller import (
    InternalActivityController,
)
from backend.internal_activity_service.microsoft_chat_analytics_service import (
    MicrosoftChatAnalyticsService,
)
from backend.internal_activity_service.microsoft_meeting_chat_topic_cache_service import (
    MicrosoftMeetingChatTopicCacheService,
)
from backend.internal_activity_service.gerrit_analytics_service import (
    GerritAnalyticsService,
)
from backend.historical_data.microsoft_chat_history_sync_service import (
    MicrosoftChatHistorySyncService,
)
from backend.historical_data.jira_history_sync_service import JiraHistorySyncService
from backend.service.jira_search_service import JiraSearchService
from backend.internal_activity_service.google_chat_analytics_service import (
    GoogleChatAnalyticsService,
)
from backend.internal_activity_service.summary_service import SummaryService
from backend.common.environment_constants import (
    GMAIL_SENDER_RECRUITING,
    GMAIL_SENDER_NOTIFICATION,
    JIRA_SERVER,
    JIRA_USER,
    MENTORSHIP_CALENDAR_ID,
    INTERVIEW_CALENDAR_ID,
    NOTIFICATION_PUSHER_SUBS,
    NOTIFICATION_TOPIC,
    USER_EMAIL,
)
from backend.historical_data.google_chat_history_sync_service import (
    GoogleChatHistorySyncService,
)
from backend.common.asyncio_event_loop_manager import AsyncioEventLoopManager
from backend.utils.fast_app_factory import FastAppFactory
from backend.authentication.authentication_controller import AuthenticationController
from backend.authentication.authentication_service import AuthenticationService
from backend.authentication.email_management_service import EmailManagementService
from backend.authentication.email_management_controller import (
    EmailManagementController,
)
from backend.admin.permission_admin_service import PermissionAdminService
from backend.admin.permission_admin_controller import PermissionAdminController
from backend.repository.job_repository import JobRepository
from backend.repository.job_review_repository import JobReviewRepository
from backend.repository.event_repository import EventRepository
from backend.repository.notification_repository import NotificationRepository
from backend.repository.application_repository import ApplicationRepository
from backend.repository.application_assignment_repository import (
    ApplicationAssignmentRepository,
)
from backend.repository.application_interview_repository import (
    ApplicationInterviewRepository,
)
from backend.repository.application_comment_repository import (
    ApplicationCommentRepository,
)
from backend.repository.application_comment_mention_repository import (
    ApplicationCommentMentionRepository,
)
from backend.repository.application_submission_repository import (
    ApplicationSubmissionRepository,
)
from backend.repository.evaluation_repository import EvaluationRepository
from backend.recruiting.recruiting_mapper import RecruitingMapper
from backend.recruiting.job_service import JobService
from backend.recruiting.recruiting_controller import RecruitingController
from backend.recruiting.resume_storage import ResumeStorage
from backend.recruiting.application_service import ApplicationService
from backend.recruiting.application_controller import ApplicationController
from backend.recruiting.application_access import ApplicationAccess
from backend.recruiting.board_service import BoardService
from backend.recruiting.email_sync_service import EmailSyncService
from backend.recruiting.board_controller import BoardController
from backend.recruiting.interview_scheduling_service import InterviewSchedulingService
from backend.recruiting.blacklist_service import BlacklistService
from backend.recruiting.blacklist_controller import BlacklistController
from backend.recruiting.evaluation_service import EvaluationService
from backend.recruiting.evaluation_controller import EvaluationController
from backend.recruiting.audit_service import AuditService
from backend.recruiting.audit_controller import AuditController
from backend.recruiting.notification_service import RecruitingNotificationService
from backend.recruiting.notification_controller import RecruitingNotificationController
from backend.communication.notification_email_service import NotificationEmailService
from backend.notification_management.notification_event_email_service import (
    NotificationEventEmailService,
)
from backend.notification_management.delivery_service import DeliveryService
from backend.notification_management.delivery_controller import (
    NotificationDeliveryController,
)
from backend.common.environment_constants import RESUME_BUCKET
from backend.common.auth0_client import Auth0Client
from backend.repository.users_repository import UsersRepository
from backend.repository.user_identities_repository import UserIdentitiesRepository
from backend.repository.user_emails_repository import UserEmailsRepository
from backend.repository.email_thread_repository import EmailThreadRepository
from backend.repository.email_message_repository import EmailMessageRepository
from backend.common.gmail_client import GmailClient
from backend.communication.email_conversation_service import EmailConversationService
from backend.communication.meeting_scheduling_service import MeetingSchedulingService
from backend.repository.user_permissions_repository import UserPermissionsRepository
from backend.repository.experience_repository import ExperienceRepository
from backend.repository.training_repository import TrainingRepository
from backend.repository.mentorship_round_repository import MentorshipRoundRepository
from backend.repository.mentorship_pairs_repository import MentorshipPairsRepository
from backend.repository.mentorship_meeting_repository import (
    MentorshipMeetingRepository,
)
from backend.repository.mentorship_round_participants_repository import (
    MentorshipRoundParticipantsRepository,
)
from backend.repository.preferences_repository import PreferencesRepository
from backend.mentorship.mentorship_mapper import MentorshipMapper
from backend.mentorship.mentorship_controller import MentorshipController
from backend.mentorship.mentorship_admin_service import MentorshipAdminService
from backend.mentorship.mentorship_admin_controller import MentorshipAdminController
from backend.mentorship.rounds_service import RoundsService
from backend.mentorship.participation_service import ParticipationService
from backend.mentorship.registration_service import RegistrationService
from backend.mentorship.meeting_service import MeetingService
from backend.mentorship.meet_attendance_service import MeetAttendanceService
from backend.mentorship.onboarding_training_service import OnboardingTrainingService
from backend.profile.profile_query_service import ProfileQueryService
from backend.profile.profile_command_service import ProfileCommandService
from backend.profile.profile_mapper import ProfileMapper
from backend.profile.profile_service import ProfileService
from backend.common.database import Database
from backend.profile.profile_controller import ProfileController
from backend.user_identity.user_identity_service import UserIdentityService
from backend.common.launchdarkly_client import LaunchDarklyClient
from backend.service.launchdarkly_service import LaunchDarklyService


class AppDependencyBuilder:
    """
    A builder class responsible for constructing all service and controller dependencies
    used throughout the application.

    This class acts as a centralized place for wiring together core infrastructure such as:
    - Logging
    - Redis client
    - Microsoft Graph client
    - Business services (e.g. MicrosoftService, MicrosoftChatService)
    - HTTP API controllers (e.g. HistoryController, InternalActivityController, ConsumerController)

    Example:
        builder = AppDependencyBuilder()
        app = create_app(notification_controller = builder.notification_controller)
    """

    def __init__(self):
        jira_server = os.getenv(JIRA_SERVER)
        jira_user = os.getenv(JIRA_USER)

        # Each scenario writes to its own per-environment Calendar container.
        # Missing values fail here, at startup: a service falling back to the
        # impersonated account's primary calendar is exactly what lets one
        # environment's delete or reschedule reach another environment's event.
        mentorship_calendar_id = os.getenv(MENTORSHIP_CALENDAR_ID)
        if not mentorship_calendar_id:
            raise ValueError(f"Missing environment variable: {MENTORSHIP_CALENDAR_ID}")
        interview_calendar_id = os.getenv(INTERVIEW_CALENDAR_ID)
        if not interview_calendar_id:
            raise ValueError(f"Missing environment variable: {INTERVIEW_CALENDAR_ID}")

        # The fully qualified Pub/Sub topic publish_on_commit publishes to.
        # Missing this must fail at startup, not silently no-op every publish
        # for the life of the process.
        notification_topic_path = os.getenv(NOTIFICATION_TOPIC)
        if not notification_topic_path:
            raise ValueError(f"Missing environment variable: {NOTIFICATION_TOPIC}")

        notification_pusher_subs = frozenset(
            sub.strip()
            for sub in (os.getenv(NOTIFICATION_PUSHER_SUBS) or "").split(",")
            if sub.strip()
        )

        # No presence check here: GoogleClient already validates USER_EMAIL and
        # raises before this point, so repeating it would just be noise.
        user_email = os.getenv(USER_EMAIL)

        self.logger = get_logger()
        self.retry_utils = RetryUtils()

        self.launchdarkly_client = LaunchDarklyClient(logger=self.logger)
        self.launchdarkly_service = LaunchDarklyService(
            logger=self.logger,
            launchdarkly_client=self.launchdarkly_client,
        )

        self.gerrit_client = GerritClient()
        self.redis_client = RedisClient(
            logger=self.logger,
            retry_utils=self.retry_utils,
        ).get_redis_client()
        self.graph_client = MicrosoftGraphServiceClient().get_graph_service_client
        self.google_client = GoogleClient(
            logger=self.logger,
            retry_utils=self.retry_utils,
        )
        self.json_schema_validator = JsonSchemaValidator(logger=self.logger)
        self.google_workspaceevents_client = (
            self.google_client.create_workspaceevents_client()
        )
        self.subscriber_client = self.google_client.create_subscriber_client()
        self.notification_publisher_client = (
            self.google_client.create_publisher_client()
        )
        self.notification_topic_path = notification_topic_path
        self.notification_pusher_subs = notification_pusher_subs
        self.google_chat_client = self.google_client.create_chat_client()
        self.google_people_client = self.google_client.create_people_client()
        # Constructed, not connected: the services below open the connection on
        # the first call that needs Jira. Missing configuration still fails
        # here, at startup.
        self.jira_client = JiraClient(
            jira_server=jira_server,
            jira_user=jira_user,
            logger=self.logger,
            retry_utils=self.retry_utils,
        )
        self.google_calendar_client = self.google_client.create_calendar_client()
        self.google_reports_client = self.google_client.create_reports_client()
        self.meet_spaces_client = self.google_client.create_meet_spaces_client()
        self.meet_conference_records_client = (
            self.google_client.create_meet_conference_records_client()
        )

        self.microsoft_service = MicrosoftService(
            logger=self.logger,
            graph_service_client=self.graph_client,
            retry_utils=self.retry_utils,
        )
        self.microsoft_chat_subscription_service = MicrosoftChatSubscriptionService(
            logger=self.logger,
            redis_client=self.redis_client,
            microsoft_service=self.microsoft_service,
        )
        self.google_chat_subscription_service = GoogleChatSubscriptionService(
            logger=self.logger,
            retry_utils=self.retry_utils,
            google_workspaceevents_client=self.google_workspaceevents_client,
        )
        self.notification_controller = NotificationController(
            microsoft_chat_subscription_service=self.microsoft_chat_subscription_service,
            google_chat_subscription_service=self.google_chat_subscription_service,
        )
        self.date_time_util = DateTimeUtil(logger=self.logger)
        self.microsoft_chat_message_util = MicrosoftChatMessageUtil(
            logger=self.logger,
            redis_client=self.redis_client,
            microsoft_service=self.microsoft_service,
            date_time_util=self.date_time_util,
            retry_utils=self.retry_utils,
        )
        self.gerrit_sync_service = GerritSyncService(
            logger=self.logger,
            redis_client=self.redis_client,
            gerrit_client=self.gerrit_client,
            retry_utils=self.retry_utils,
            date_time_util=self.date_time_util,
        )
        self.asyncio_event_loop_manager = AsyncioEventLoopManager()

        self.pubsub_puller_factory = PubSubPullerFactory(
            puller_creator=PubSubPuller,
            logger=self.logger,
            redis_client=self.redis_client,
            subscriber_client=self.subscriber_client,
            asyncio_event_loop_manager=self.asyncio_event_loop_manager,
        )
        self.pubsub_pull_manager = PubSubPullManager(
            pubsub_puller_factory=self.pubsub_puller_factory
        )
        self.microsoft_message_processor_service = MicrosoftMessageProcessorService(
            logger=self.logger,
            pubsub_puller_factory=self.pubsub_puller_factory,
            microsoft_chat_message_util=self.microsoft_chat_message_util,
        )
        self.google_chat_messages_utils = GoogleChatMessagesUtils(
            logger=self.logger,
            redis_client=self.redis_client,
            retry_utils=self.retry_utils,
        )
        self.google_service = GoogleService(
            logger=self.logger,
            google_chat_client=self.google_chat_client,
            google_people_client=self.google_people_client,
            google_workspaceevents_client=self.google_workspaceevents_client,
            retry_utils=self.retry_utils,
            google_calendar_client=self.google_calendar_client,
            meet_spaces_client=self.meet_spaces_client,
            meet_conference_records_client=self.meet_conference_records_client,
        )
        self.google_chat_processor_service = GoogleChatProcessorService(
            logger=self.logger,
            pubsub_puller_factory=self.pubsub_puller_factory,
            google_chat_messages_utils=self.google_chat_messages_utils,
            google_service=self.google_service,
        )
        self.gerrit_processor_service = GerritProcessorService(
            logger=self.logger,
            redis_client=self.redis_client,
            pubsub_puller_factory=self.pubsub_puller_factory,
            retry_utils=self.retry_utils,
            date_time_util=self.date_time_util,
            gerrit_client=self.gerrit_client,
        )
        self.pubsub_sync_pull_service = PubSubSyncPullService(
            logger=self.logger,
            subscriber_client=self.subscriber_client,
            microsoft_chat_message_util=self.microsoft_chat_message_util,
            google_chat_processor_service=self.google_chat_processor_service,
            gerrit_processor_service=self.gerrit_processor_service,
            asyncio_event_loop_manager=self.asyncio_event_loop_manager,
        )
        self.consumer_controller = ConsumerController(
            pubsub_sync_pull_service=self.pubsub_sync_pull_service,
        )

        self.microsoft_member_sync_service = MicrosoftMemberSyncService(
            logger=self.logger,
            redis_client=self.redis_client,
            microsoft_service=self.microsoft_service,
            retry_utils=self.retry_utils,
        )
        self.microsoft_chat_history_sync_service = MicrosoftChatHistorySyncService(
            logger=self.logger,
            microsoft_service=self.microsoft_service,
            microsoft_chat_message_util=self.microsoft_chat_message_util,
        )
        self.jira_search_service = JiraSearchService(
            logger=self.logger,
            jira_client=self.jira_client,
            retry_utils=self.retry_utils,
        )
        self.jira_history_sync_service = JiraHistorySyncService(
            logger=self.logger,
            redis_client=self.redis_client,
            jira_client=self.jira_client,
            jira_search_service=self.jira_search_service,
            date_time_util=self.date_time_util,
            retry_utils=self.retry_utils,
        )
        self.ldap_service = LdapService(
            logger=self.logger,
            redis_client=self.redis_client,
            retry_utils=self.retry_utils,
        )
        self.google_calendar_sync_service = GoogleCalendarSyncService(
            logger=self.logger,
            redis_client=self.redis_client,
            google_calendar_client=self.google_calendar_client,
            google_reports_client=self.google_reports_client,
            retry_utils=self.retry_utils,
            google_service=self.google_service,
            bot_account_email=user_email,
        )
        self.google_chat_history_sync_service = GoogleChatHistorySyncService(
            logger=self.logger,
            google_service=self.google_service,
            google_chat_message_utils=self.google_chat_messages_utils,
        )
        self.historical_controller = HistoricalController(
            microsoft_member_sync_service=self.microsoft_member_sync_service,
            microsoft_chat_history_sync_service=self.microsoft_chat_history_sync_service,
            jira_history_sync_service=self.jira_history_sync_service,
            google_calendar_sync_service=self.google_calendar_sync_service,
            date_time_utils=self.date_time_util,
            gerrit_sync_service=self.gerrit_sync_service,
            google_chat_history_sync_service=self.google_chat_history_sync_service,
        )
        self.microsoft_chat_analytics_service = MicrosoftChatAnalyticsService(
            logger=self.logger,
            redis_client=self.redis_client,
            date_time_util=self.date_time_util,
            ldap_service=self.ldap_service,
            retry_utils=self.retry_utils,
        )
        self.microsoft_meeting_chat_topic_cache_service = (
            MicrosoftMeetingChatTopicCacheService(
                logger=self.logger,
                redis_client=self.redis_client,
                microsoft_service=self.microsoft_service,
                retry_utils=self.retry_utils,
            )
        )
        self.jira_analytics_service = JiraAnalyticsService(
            logger=self.logger,
            redis_client=self.redis_client,
            retry_utils=self.retry_utils,
            date_time_util=self.date_time_util,
            ldap_service=self.ldap_service,
        )
        self.google_calendar_analytics_service = GoogleCalendarAnalyticsService(
            logger=self.logger,
            redis_client=self.redis_client,
            retry_utils=self.retry_utils,
            ldap_service=self.ldap_service,
        )
        self.gerrit_analytics_service = GerritAnalyticsService(
            logger=self.logger,
            redis_client=self.redis_client,
            retry_utils=self.retry_utils,
            ldap_service=self.ldap_service,
            date_time_util=self.date_time_util,
            gerrit_client=self.gerrit_client,
        )
        self.google_chat_analytics_service = GoogleChatAnalyticsService(
            logger=self.logger,
            redis_client=self.redis_client,
            retry_utils=self.retry_utils,
            date_time_util=self.date_time_util,
            google_service=self.google_service,
            ldap_service=self.ldap_service,
        )
        self.summary_service = SummaryService(
            ldap_service=self.ldap_service,
            microsoft_chat_analytics_service=self.microsoft_chat_analytics_service,
            google_calendar_analytics_service=self.google_calendar_analytics_service,
            google_chat_analytics_service=self.google_chat_analytics_service,
            gerrit_analytics_service=self.gerrit_analytics_service,
            jira_analytics_service=self.jira_analytics_service,
            date_time_util=self.date_time_util,
        )
        self.internal_activity_controller = InternalActivityController(
            ldap_service=self.ldap_service,
            microsoft_chat_analytics_service=self.microsoft_chat_analytics_service,
            microsoft_meeting_chat_topic_cache_service=self.microsoft_meeting_chat_topic_cache_service,
            jira_analytics_service=self.jira_analytics_service,
            google_calendar_analytics_service=self.google_calendar_analytics_service,
            date_time_util=self.date_time_util,
            gerrit_analytics_service=self.gerrit_analytics_service,
            google_chat_analytics_service=self.google_chat_analytics_service,
            summary_service=self.summary_service,
            launchdarkly_service=self.launchdarkly_service,
        )
        self.users_repository = UsersRepository()
        self.user_identities_repository = UserIdentitiesRepository()
        self.user_emails_repository = UserEmailsRepository()
        self.user_permissions_repository = UserPermissionsRepository()
        self.training_repository = TrainingRepository()
        # Built here, next to its repository, because both ApplicationService
        # and BoardService take it and are constructed further down.
        self.onboarding_training_service = OnboardingTrainingService(
            logger=self.logger,
            training_repository=self.training_repository,
        )
        self.database = Database(echo=False)
        self.user_identity_service = UserIdentityService(
            logger=self.logger,
            users_repository=self.users_repository,
            user_identities_repository=self.user_identities_repository,
            user_emails_repository=self.user_emails_repository,
            user_permissions_repository=self.user_permissions_repository,
        )
        self.authentication_service = AuthenticationService(logger=self.logger)
        self.authentication_controller = AuthenticationController(
            user_emails_repository=self.user_emails_repository,
            database=self.database,
        )
        self.auth0_client = Auth0Client(logger=self.logger)
        self.email_management_service = EmailManagementService(
            auth0_client=self.auth0_client,
            user_emails_repository=self.user_emails_repository,
            user_identities_repository=self.user_identities_repository,
            user_permissions_repository=self.user_permissions_repository,
            users_repository=self.users_repository,
            logger=self.logger,
        )
        self.mentorship_round_repository = MentorshipRoundRepository()
        self.mentorship_pairs_repository = MentorshipPairsRepository()
        self.mentorship_meeting_repository = MentorshipMeetingRepository()
        self.mentorship_round_participants_repo = (
            MentorshipRoundParticipantsRepository()
        )
        self.preferences_repository = PreferencesRepository()
        self.job_repository = JobRepository()
        self.application_repository = ApplicationRepository()
        self.mentorship_mapper = MentorshipMapper()
        self.rounds_service = RoundsService(
            mentorship_round_repository=self.mentorship_round_repository,
            mentorship_mapper=self.mentorship_mapper,
            mentorship_pairs_repository=self.mentorship_pairs_repository,
        )
        self.participation_service = ParticipationService(
            logger=self.logger,
            users_repository=self.users_repository,
            mentorship_pairs_repository=self.mentorship_pairs_repository,
            mentorship_round_participants_repo=self.mentorship_round_participants_repo,
            mentorship_round_repository=self.mentorship_round_repository,
            mentorship_mapper=self.mentorship_mapper,
            user_emails_repository=self.user_emails_repository,
        )
        self.registration_service = RegistrationService(
            logger=self.logger,
            preferences_repository=self.preferences_repository,
            mentorship_round_repository=self.mentorship_round_repository,
            mentorship_round_participants_repository=self.mentorship_round_participants_repo,
            participation_service=self.participation_service,
            mentorship_mapper=self.mentorship_mapper,
            onboarding_training_service=self.onboarding_training_service,
            application_repository=self.application_repository,
        )
        self.meeting_scheduling_service = MeetingSchedulingService(
            logger=self.logger,
            google_service=self.google_service,
            user_emails_repository=self.user_emails_repository,
        )
        self.meeting_service = MeetingService(
            logger=self.logger,
            mentorship_pairs_repository=self.mentorship_pairs_repository,
            mentorship_mapper=self.mentorship_mapper,
            users_repository=self.users_repository,
            meeting_scheduling_service=self.meeting_scheduling_service,
            mentorship_calendar_id=mentorship_calendar_id,
            mentorship_meeting_repository=self.mentorship_meeting_repository,
        )
        self.meet_attendance_service = MeetAttendanceService(
            logger=self.logger,
            google_service=self.google_service,
            mentorship_pairs_repository=self.mentorship_pairs_repository,
            mentorship_round_repository=self.mentorship_round_repository,
            users_repository=self.users_repository,
            user_identities_repository=self.user_identities_repository,
            user_emails_repository=self.user_emails_repository,
            mentorship_meeting_repository=self.mentorship_meeting_repository,
        )
        self.mentorship_controller = MentorshipController(
            rounds_service=self.rounds_service,
            participation_service=self.participation_service,
            registration_service=self.registration_service,
            meeting_service=self.meeting_service,
            launchdarkly_service=self.launchdarkly_service,
            database=self.database,
            meet_attendance_sync_service=self.meet_attendance_service,
        )
        self.mentorship_admin_service = MentorshipAdminService(
            users_repository=self.users_repository,
            participants_repository=self.mentorship_round_participants_repo,
            rounds_repository=self.mentorship_round_repository,
            training_repository=self.training_repository,
            pairs_repository=self.mentorship_pairs_repository,
            mentorship_mapper=self.mentorship_mapper,
            date_time_util=self.date_time_util,
            database=self.database,
            logger=self.logger,
            mentorship_meeting_repository=self.mentorship_meeting_repository,
        )
        self.mentorship_admin_controller = MentorshipAdminController(
            mentorship_admin_service=self.mentorship_admin_service,
            database=self.database,
        )
        self.experience_repository = ExperienceRepository()
        self.profile_mapper = ProfileMapper()
        self.profile_query_service = ProfileQueryService(
            users_repository=self.users_repository,
            experience_repository=self.experience_repository,
            training_repository=self.training_repository,
            profile_mapper=self.profile_mapper,
            user_emails_repository=self.user_emails_repository,
        )
        self.profile_command_service = ProfileCommandService(
            users_repository=self.users_repository,
            experience_repository=self.experience_repository,
            logger=self.logger,
        )
        self.profile_service = ProfileService(
            query_service=self.profile_query_service,
            command_service=self.profile_command_service,
            users_repository=self.users_repository,
        )
        self.profile_controller = ProfileController(
            profile_service=self.profile_service,
            database=self.database,
        )
        self.email_management_controller = EmailManagementController(
            email_management_service=self.email_management_service,
            database=self.database,
        )
        self.permission_admin_service = PermissionAdminService(
            self.users_repository,
            self.user_permissions_repository,
            self.user_emails_repository,
        )
        self.permission_admin_controller = PermissionAdminController(
            self.permission_admin_service,
            database=self.database,
        )
        self.notification_repository = NotificationRepository()
        self.event_repository = EventRepository()
        self.job_review_repository = JobReviewRepository()
        self.recruiting_mapper = RecruitingMapper()
        # Person-anchored email transport, needed by the notification email
        # channel below. GmailClient reads the GMAIL_* credentials from the
        # env itself (use placeholder values locally -- real secrets are only
        # needed to actually send/read mail).
        #
        # The From addresses are read here instead: one per sending service,
        # so the transport stays unaware of which services exist. Recruiting
        # and notifications each get their own. Missing is fatal at startup
        # rather than defaulted -- an unowned From is silently rewritten by
        # Gmail, so a wrong or absent value would surface as mail from the
        # wrong identity, not as an error.
        recruiting_sender = os.getenv(GMAIL_SENDER_RECRUITING)
        if not recruiting_sender:
            raise ValueError(f"Missing environment variable: {GMAIL_SENDER_RECRUITING}")
        self.notification_sender_address = os.getenv(GMAIL_SENDER_NOTIFICATION)
        if not self.notification_sender_address:
            raise ValueError(
                f"Missing environment variable: {GMAIL_SENDER_NOTIFICATION}"
            )
        self.gmail_client = GmailClient(
            logger=self.logger,
            retry_utils=self.retry_utils,
            sender_addresses=[recruiting_sender, self.notification_sender_address],
        )
        self.recruiting_notification_service = RecruitingNotificationService(
            self.notification_repository,
            self.application_repository,
            self.job_repository,
            self.users_repository,
        )
        self.notification_email_service = NotificationEmailService(
            gmail_client=self.gmail_client,
            logger=self.logger,
            sender_address=self.notification_sender_address,
        )
        # The delivery pipeline for the new event-based notification rows:
        # NotificationEventEmailService renders (by event_type, via
        # notification_renderers's registrations) and resolves the
        # recipient's address, then hands off to notification_email_service
        # above for the actual Gmail send. DeliveryService wraps that in the
        # claim/settle state machine; NotificationDeliveryController is the
        # Pub/Sub push endpoint that drives it.
        self.notification_event_email_service = NotificationEventEmailService(
            user_emails_repository=self.user_emails_repository,
            email_service=self.notification_email_service,
        )
        self.delivery_service = DeliveryService(
            email_service=self.notification_event_email_service,
        )
        self.notification_delivery_controller = NotificationDeliveryController(
            delivery_service=self.delivery_service,
            publisher=self.notification_publisher_client,
            topic_path=self.notification_topic_path,
            database=self.database,
            auth_service=self.authentication_service,
            pusher_subs=self.notification_pusher_subs,
        )
        self.job_service = JobService(
            self.job_repository,
            self.recruiting_mapper,
            self.user_permissions_repository,
            self.job_review_repository,
            self.notification_repository,
            self.users_repository,
            self.user_emails_repository,
            self.event_repository,
        )
        self.application_assignment_repository = ApplicationAssignmentRepository()
        self.application_interview_repository = ApplicationInterviewRepository()
        self.application_comment_repository = ApplicationCommentRepository()
        self.application_comment_mention_repository = (
            ApplicationCommentMentionRepository()
        )
        self.application_submission_repository = ApplicationSubmissionRepository()
        self.resume_storage = ResumeStorage(os.getenv(RESUME_BUCKET))
        self.evaluation_repository = EvaluationRepository()
        self.application_service = ApplicationService(
            self.application_repository,
            self.application_submission_repository,
            self.job_repository,
            self.users_repository,
            self.recruiting_mapper,
            self.application_assignment_repository,
            self.notification_repository,
            self.user_emails_repository,
            self.onboarding_training_service,
        )
        self.application_controller = ApplicationController(
            self.application_service,
            self.job_service,
            self.resume_storage,
            self.database,
        )
        # Person-anchored email (recruiting Emails tab). self.gmail_client and
        # recruiting_sender were constructed earlier, alongside the
        # notification email channel, since JobService/ApplicationService
        # need self.notification_repository before they are built above.
        self.email_thread_repository = EmailThreadRepository()
        self.email_message_repository = EmailMessageRepository()
        self.email_conversation_service = EmailConversationService(
            gmail_client=self.gmail_client,
            thread_repository=self.email_thread_repository,
            message_repository=self.email_message_repository,
            sender_address=recruiting_sender,
        )
        self.email_sync_service = EmailSyncService(
            gmail_client=self.gmail_client,
            email_conversation_service=self.email_conversation_service,
            application_repository=self.application_repository,
            logger=self.logger,
        )
        self.recruiting_controller = RecruitingController(
            job_service=self.job_service,
            email_sync_service=self.email_sync_service,
            database=self.database,
        )

        # Shared owner/assignee gating + interview-evaluator validation, used
        # by both BoardService (via its thin delegating methods) and
        # InterviewSchedulingService.
        self.application_access = ApplicationAccess(
            self.application_repository,
            self.job_repository,
            self.application_assignment_repository,
            self.user_permissions_repository,
        )
        # Built before BoardService, which delegates its ghost-meeting cleanup
        # (change_stage/set_round's `cancelInterview`) here. The dependency is
        # one-way: this service never calls back into BoardService.
        self.interview_scheduling_service = InterviewSchedulingService(
            self.logger,
            self.application_access,
            self.application_repository,
            self.application_assignment_repository,
            self.application_interview_repository,
            self.users_repository,
            self.user_emails_repository,
            self.meeting_scheduling_service,
            self.recruiting_mapper,
            interview_calendar_id,
        )
        self.board_service = BoardService(
            self.job_repository,
            self.application_repository,
            self.application_submission_repository,
            self.users_repository,
            self.recruiting_mapper,
            self.resume_storage,
            self.application_assignment_repository,
            self.user_permissions_repository,
            self.event_repository,
            self.application_comment_repository,
            self.application_comment_mention_repository,
            self.evaluation_repository,
            self.notification_repository,
            self.user_emails_repository,
            self.email_conversation_service,
            self.email_sync_service,
            self.application_interview_repository,
            self.application_access,
            self.interview_scheduling_service,
            self.onboarding_training_service,
        )
        self.board_controller = BoardController(
            self.board_service,
            self.database,
            self.interview_scheduling_service,
        )
        self.blacklist_service = BlacklistService(
            self.users_repository, self.user_emails_repository
        )
        self.blacklist_controller = BlacklistController(
            self.blacklist_service,
            self.database,
        )
        self.evaluation_service = EvaluationService(
            self.application_repository,
            self.application_assignment_repository,
            self.evaluation_repository,
            self.job_repository,
            self.users_repository,
            self.application_submission_repository,
        )
        self.evaluation_controller = EvaluationController(
            self.evaluation_service,
            self.database,
        )
        self.audit_service = AuditService(
            self.job_repository,
            self.application_repository,
        )
        self.audit_controller = AuditController(
            self.audit_service,
            self.database,
        )
        self.recruiting_notification_controller = RecruitingNotificationController(
            self.recruiting_notification_service,
            self.database,
        )
        self.fast_app_factory = FastAppFactory(
            authentication_controller=self.authentication_controller,
            authentication_service=self.authentication_service,
            user_identity_service=self.user_identity_service,
            user_permissions_repository=self.user_permissions_repository,
            notification_controller=self.notification_controller,
            historical_controller=self.historical_controller,
            consumer_controller=self.consumer_controller,
            internal_activity_controller=self.internal_activity_controller,
            profile_controller=self.profile_controller,
            mentorship_controller=self.mentorship_controller,
            mentorship_admin_controller=self.mentorship_admin_controller,
            email_management_controller=self.email_management_controller,
            permission_admin_controller=self.permission_admin_controller,
            recruiting_controller=self.recruiting_controller,
            application_controller=self.application_controller,
            board_controller=self.board_controller,
            blacklist_controller=self.blacklist_controller,
            evaluation_controller=self.evaluation_controller,
            audit_controller=self.audit_controller,
            recruiting_notification_controller=self.recruiting_notification_controller,
            notification_delivery_controller=self.notification_delivery_controller,
            notification_publisher=self.notification_publisher_client,
            notification_topic_path=self.notification_topic_path,
            launchdarkly_client=self.launchdarkly_client,
            database=self.database,
            logger=self.logger,
        )
