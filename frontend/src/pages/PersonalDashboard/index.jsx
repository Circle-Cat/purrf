import MentorshipInfoBanner from "@/pages/PersonalDashboard/components/MentorshipInfoBanner";
import { WorkActivityDataCard } from "@/pages/PersonalDashboard/components/WorkActivityDataCard";
import MentorshipParticipantsCard from "@/pages/PersonalDashboard/components/MentorshipParticipantsCard";
import { useMentorshipData } from "@/pages/PersonalDashboard/hooks/useMentorshipData";
import { useWorkActivityData } from "@/pages/PersonalDashboard/hooks/useWorkActivityData";
import MyApplicationsCard from "@/pages/PersonalDashboard/components/MyApplicationsCard";
import { useMyApplications } from "@/hooks/useMyApplications";
import { useOnboardingTrainingReminder } from "@/pages/PersonalDashboard/hooks/useOnboardingTrainingReminder";
import { useRegistrationReminder } from "@/pages/PersonalDashboard/hooks/useRegistrationReminder";
import { useAuth } from "@/context/auth";
import { PERMISSIONS } from "@/constants/Permissions";
import { MentorshipRoundStatus } from "@/constants/MentorshipRoundStatus";
import { GoogleMeetingControl } from "@/pages/PersonalDashboard/components/GoogleMeetingControl";
import LeaveApprovalsCard from "@/pages/PersonalDashboard/components/LeaveApprovalsCard";
import { useLeaveApprovals } from "@/pages/Leave/hooks/useLeaveApprovals";
import { useLeaveEnabled } from "@/pages/Leave/hooks/useLeaveEnabled";

/**
 * PersonalDashboard
 *
 * Main dashboard page for the current user.
 *
 * Responsibilities:
 * - Display a welcome header.
 * - Load mentorship-related data via `useMentorshipData`.
 * - Pass mentorship state and actions down to `MentorshipInfoBanner`.
 *
 * This component itself contains no business logic;
 * all data fetching and state management are delegated to hooks.
 *
 * @returns {JSX.Element}
 */
const PersonalDashboard = () => {
  const {
    applications,
    isLoading: isApplicationsLoading,
    loadError: applicationsLoadError,
    load: loadApplications,
    hiredMentorshipRoles,
  } = useMyApplications();

  // Only show the mentorship section, and only start fetching mentorship
  // data, once we've actually confirmed at least one mentorship admission
  // — not while the applications fetch is still loading or has errored.
  // A slow or failed fetch hides the section (the user can retry via My
  // Applications' own retry button) rather than firing a wasted
  // mentorship-data fetch.
  const showMentorshipSection =
    !isApplicationsLoading &&
    !applicationsLoadError &&
    hiredMentorshipRoles.length > 0;

  useOnboardingTrainingReminder({ enabled: showMentorshipSection });

  const {
    registration, // Registration data for the current or most recent round
    isRegistrationOpen, // Whether the registration period is currently open
    registrationDeadlineAt, // Deadline the registration window is measured against
    regRoundName, // Display name of the round taking registrations
    isFeedbackEnabled, // Whether the feedback phase is currently active
    registrationEntries, // One entry per role the user may register under, each with its own deadline
    registeredRole, // Role an existing registration settled on, or null
    loadRegistrationForRole, // Fetches one role's registration form prefill
    saveRegistration, // Function to submit or update registration data
    pastPartners, // List of past mentorship partners
    isPartnersLoading, // Whether partner data is currently loading
    loadPastPartners, // Function to trigger loading of past partners
    refreshRegistration, // Function to refresh registration data
    canViewMatch, // Whether the matching result is visible to the user (e.g. during the announcement period)
    matchResult, // The Matching result data
    matchResultRoundName, // Display name of the matching result round
    roundSelectionData, // Sorted list of all rounds and the active round ID for the round selector
    selectedRoundId, // Currently selected round ID for the participant card
    handleRoundChange, // Callback to update the selected round
    participantDetails, // Round info, per-partner meeting overview, and user role
    refreshMeetings, // Trigger a refresh of meeting log data for the selected round
    isParticipantCardLoading, // Whether the participant card data is currently loading
    isLoading: isMentorshipLoading, // Whether the rounds and registration fetch is still in flight
    userTimezone, // Current user's IANA timezone string from their profile
  } = useMentorshipData({
    enabled: showMentorshipSection,
    hiredMentorshipRoles,
  });

  useRegistrationReminder({
    enabled: showMentorshipSection,
    isLoading: isMentorshipLoading,
    isRegistered: Boolean(registration?.isRegistered),
    isRegistrationOpen,
    registrationDeadlineAt,
    roundName: regRoundName,
  });

  const { permissions } = useAuth();
  const canViewActivitySummary = permissions?.includes(
    PERMISSIONS.DASHBOARD_ACTIVITY_SUMMARY_READ,
  );

  const { summary, isPersonalSummaryLoading, fetchPersonalSummary } =
    useWorkActivityData({ enabled: canViewActivitySummary });

  // Whether the viewer decides anybody else's leave is only knowable by
  // asking: it is not a permission, and a manager who is outside the leave
  // population has no employment profile to read it off. So this fetch is
  // unconditional, unlike the sections gated on data we already hold.
  const isLeaveEnabled = useLeaveEnabled();
  const { isApprover, pendingCount } = useLeaveApprovals({
    enabled: isLeaveEnabled,
  });

  const currentSelectedRound = roundSelectionData?.sortedRounds?.find(
    (round) => Number(round.id) === Number(selectedRoundId),
  );

  const isCurrentRoundActive =
    currentSelectedRound?.status === MentorshipRoundStatus.ACTIVE;

  return (
    <div className="personal-dashboard space-y-5">
      {/* Welcome header */}
      <div className="flex items-start justify-between shrink-0">
        <div className="flex items-center gap-2">
          <span role="img" aria-label="clapping hands" className="text-xl">
            &#x1F44F;
          </span>
          <h2 className="m-0 text-lg font-medium">Welcome</h2>
        </div>

        {showMentorshipSection && (
          <GoogleMeetingControl
            meetingRoundId={
              isCurrentRoundActive ? Number(selectedRoundId) : null
            }
            onRefresh={refreshMeetings}
            userTimezone={userTimezone}
          />
        )}
      </div>

      {/* My Applications card */}
      <MyApplicationsCard
        applications={applications}
        isLoading={isApplicationsLoading}
        loadError={applicationsLoadError}
        onRetry={loadApplications}
      />

      {showMentorshipSection && (
        <>
          {/* Mentorship information banner */}
          <MentorshipInfoBanner
            registration={registration}
            isRegistrationOpen={isRegistrationOpen}
            isFeedbackEnabled={isFeedbackEnabled}
            registrationEntries={registrationEntries}
            registeredRole={registeredRole}
            loadRegistrationForRole={loadRegistrationForRole}
            onSaveRegistration={saveRegistration}
            pastPartners={pastPartners}
            isPartnersLoading={isPartnersLoading}
            onLoadPastPartners={loadPastPartners}
            refreshRegistration={refreshRegistration}
            matchResult={matchResult}
            matchResultRoundName={matchResultRoundName}
            canViewMatch={canViewMatch}
          />

          {/* Mentorship participant card */}
          <MentorshipParticipantsCard
            userTimezone={userTimezone}
            roundSelectionData={roundSelectionData}
            selectedRoundId={selectedRoundId}
            onRoundChange={handleRoundChange}
            isParticipantCardLoading={isParticipantCardLoading}
            participantDetails={participantDetails}
            refreshMeetings={refreshMeetings}
          />
        </>
      )}

      {/* Leave approvals. A sibling of the employee-facing leave blocks,
          never nested inside them: a manager outside the leave population
          decides their reports' requests and has no balance of their own. */}
      {isApprover && <LeaveApprovalsCard pendingCount={pendingCount} />}

      {/* Work Activity Data Card */}
      {canViewActivitySummary && (
        <WorkActivityDataCard
          initialData={summary}
          isLoading={isPersonalSummaryLoading}
          onSearch={({ startDate, endDate }) =>
            fetchPersonalSummary(startDate, endDate)
          }
        />
      )}
    </div>
  );
};

export default PersonalDashboard;
