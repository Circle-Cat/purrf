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
    JIRA_SERVER,
    JIRA_USER,
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
from backend.repository.notification_repository import NotificationRepository
from backend.repository.application_repository import ApplicationRepository
from backend.repository.application_assignment_repository import (
    ApplicationAssignmentRepository,
)
from backend.repository.application_activity_repository import (
    ApplicationActivityRepository,
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
from backend.recruiting.board_service import BoardService
from backend.recruiting.board_controller import BoardController
from backend.recruiting.blacklist_service import BlacklistService
from backend.recruiting.blacklist_controller import BlacklistController
from backend.recruiting.evaluation_service import EvaluationService
from backend.recruiting.evaluation_controller import EvaluationController
from backend.recruiting.audit_service import AuditService
from backend.recruiting.audit_controller import AuditController
from backend.common.environment_constants import RESUME_BUCKET
from backend.common.auth0_client import Auth0Client
from backend.repository.users_repository import UsersRepository
from backend.repository.user_identities_repository import UserIdentitiesRepository
from backend.repository.user_emails_repository import UserEmailsRepository
from backend.repository.user_permissions_repository import UserPermissionsRepository
from backend.repository.experience_repository import ExperienceRepository
from backend.repository.training_repository import TrainingRepository
from backend.repository.mentorship_round_repository import MentorshipRoundRepository
from backend.repository.mentorship_pairs_repository import MentorshipPairsRepository
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
        self.google_chat_client = self.google_client.create_chat_client()
        self.google_people_client = self.google_client.create_people_client()
        self.jira_client = JiraClient(
            jira_server=jira_server,
            jira_user=jira_user,
            logger=self.logger,
            retry_utils=self.retry_utils,
        ).get_jira_client()
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
            users_repository=self.users_repository,
            logger=self.logger,
        )
        self.mentorship_round_repository = MentorshipRoundRepository()
        self.mentorship_pairs_repository = MentorshipPairsRepository()
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
        )
        self.registration_service = RegistrationService(
            logger=self.logger,
            preferences_repository=self.preferences_repository,
            mentorship_round_repository=self.mentorship_round_repository,
            mentorship_round_participants_repository=self.mentorship_round_participants_repo,
            participation_service=self.participation_service,
            mentorship_mapper=self.mentorship_mapper,
            training_repository=self.training_repository,
            application_repository=self.application_repository,
        )
        self.meeting_service = MeetingService(
            logger=self.logger,
            mentorship_pairs_repository=self.mentorship_pairs_repository,
            mentorship_mapper=self.mentorship_mapper,
            users_repository=self.users_repository,
            google_service=self.google_service,
        )
        self.meet_attendance_service = MeetAttendanceService(
            logger=self.logger,
            google_service=self.google_service,
            mentorship_pairs_repository=self.mentorship_pairs_repository,
            mentorship_round_repository=self.mentorship_round_repository,
            users_repository=self.users_repository,
            user_identities_repository=self.user_identities_repository,
            user_emails_repository=self.user_emails_repository,
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
        )
        self.permission_admin_controller = PermissionAdminController(
            self.permission_admin_service,
            database=self.database,
        )
        self.notification_repository = NotificationRepository()
        self.job_review_repository = JobReviewRepository()
        self.recruiting_mapper = RecruitingMapper()
        self.job_service = JobService(
            self.job_repository,
            self.recruiting_mapper,
            self.user_permissions_repository,
            self.job_review_repository,
            self.notification_repository,
        )
        self.recruiting_controller = RecruitingController(
            job_service=self.job_service,
            database=self.database,
        )
        self.application_assignment_repository = ApplicationAssignmentRepository()
        self.application_activity_repository = ApplicationActivityRepository()
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
            self.application_activity_repository,
            self.notification_repository,
        )
        self.application_controller = ApplicationController(
            self.application_service,
            self.job_service,
            self.resume_storage,
            self.database,
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
            self.application_activity_repository,
            self.application_comment_repository,
            self.application_comment_mention_repository,
            self.evaluation_repository,
            self.notification_repository,
        )
        self.board_controller = BoardController(
            self.board_service,
            self.database,
        )
        self.blacklist_service = BlacklistService(self.users_repository)
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
            self.application_activity_repository,
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
            launchdarkly_client=self.launchdarkly_client,
            database=self.database,
            logger=self.logger,
        )
